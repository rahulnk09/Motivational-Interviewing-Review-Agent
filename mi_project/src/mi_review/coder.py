"""Coder agent: tags every turn with AnnoMI/MITI codes using structured outputs."""

import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from .config import ASSETS_DIR, PROMPTS_DIR, get_settings
from .llm import structured_call
from .metrics import TurnLabels
from .schemas import LLMUsage, Transcript, Turn

MAX_TURNS_PER_CALL = 120
WINDOW = 80
OVERLAP = 10


class TherapistCode(BaseModel):
    turn_id: int
    rationale: str = Field(description="Max 15 words: the decisive cue.")
    reflection: Literal["none", "simple", "complex"]
    question: Literal["none", "open", "closed"]
    therapist_input: Literal["none", "information", "advice", "negotiation", "options"]
    main_behaviour: Literal["reflection", "question", "therapist_input", "other"]
    mi_behaviour: Literal["affirm", "seek_collaboration", "emphasize_autonomy", "persuade_with_permission", "persuade", "confront", "none"]
    adherence: Literal["adherent", "non_adherent", "neutral"]


class ClientCode(BaseModel):
    turn_id: int
    rationale: str = Field(description="Max 15 words: the decisive cue.")
    talk_type: Literal["change", "sustain", "neutral"]


class CoderOutput(BaseModel):
    therapist_turns: list[TherapistCode]
    client_turns: list[ClientCode]


class CoderResult(BaseModel):
    therapist: dict[int, TherapistCode] = Field(default_factory=dict)
    client: dict[int, ClientCode] = Field(default_factory=dict)
    usage: list[LLMUsage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _render_fewshot(examples: list[dict]) -> str:
    blocks = []
    for i, ex in enumerate(examples, 1):
        lines = [f"Example {i} (target behaviour: {ex['topic']})"]
        if ex["context"]:
            lines.append(f"  CONTEXT {ex['context']['role'].upper()}: {ex['context']['text']}")
        turn, labels = ex["turn"], ex["turn"]["labels"]
        lines.append(f"  {turn['role'].upper()}: {turn['text']}")
        if turn["role"] == "client":
            lines.append(f"  -> talk_type={labels['client_talk_type']}")
        else:
            lines.append(
                f"  -> main_behaviour={labels['main_therapist_behaviour']}, reflection={labels['reflection']}, "
                f"question={labels['question']}, therapist_input={labels['therapist_input']}"
            )
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


@lru_cache
def system_prompt() -> str:
    fewshot = json.loads((ASSETS_DIR / "fewshot_coder.json").read_text(encoding="utf-8"))
    template = (PROMPTS_DIR / "coder_system.md").read_text(encoding="utf-8")
    return template.replace("{fewshot}", _render_fewshot(fewshot["examples"]))


def render_input(transcript: Transcript, turns: list[Turn], code_ids: set[int]) -> str:
    lines = [f"TARGET BEHAVIOUR: {transcript.target_behavior or 'unknown - infer it from the conversation'}", "", "TRANSCRIPT:"]
    for t in turns:
        marker = "" if t.turn_id in code_ids else "CONTEXT "
        lines.append(f"[T{t.turn_id}] {marker}{t.role.upper()}: {t.text}")
    ids = sorted(code_ids)
    lines += ["", f"Code these {len(ids)} turns: " + ", ".join(f"T{i}" for i in ids)]
    return "\n".join(lines)


def _chunks(n: int) -> list[tuple[int, int]]:
    if n <= MAX_TURNS_PER_CALL:
        return [(0, n)]
    return [(start, min(start + WINDOW, n)) for start in range(0, n, WINDOW)]


def _call(transcript: Transcript, turns: list[Turn], code_ids: set[int], step: str, model: str, effort: str, result: CoderResult) -> None:
    out, usage = structured_call(
        step=step, model=model, instructions=system_prompt(), input=render_input(transcript, turns, code_ids),
        schema=CoderOutput, effort=effort,
    )
    result.usage.append(usage)
    roles = {t.turn_id: t.role for t in transcript.turns}
    for code in out.therapist_turns:
        if code.turn_id in code_ids and roles.get(code.turn_id) == "therapist":
            result.therapist.setdefault(code.turn_id, code)
    for code in out.client_turns:
        if code.turn_id in code_ids and roles.get(code.turn_id) == "client":
            result.client.setdefault(code.turn_id, code)


def _make_consistent(code: TherapistCode) -> tuple[TherapistCode, bool]:
    fixes = {}
    if code.main_behaviour == "reflection" and code.reflection == "none":
        fixes["reflection"] = "simple"
    if code.main_behaviour == "question" and code.question == "none":
        fixes["question"] = "closed"
    if code.main_behaviour == "therapist_input" and code.therapist_input == "none":
        fixes["therapist_input"] = "information"
    if code.mi_behaviour in ("persuade", "confront") and code.adherence != "non_adherent":
        fixes["adherence"] = "non_adherent"
    return (code.model_copy(update=fixes), True) if fixes else (code, False)


def code_transcript(transcript: Transcript, model: str | None = None, effort: str | None = None) -> CoderResult:
    settings = get_settings()
    model = model or settings.coder_deployment
    effort = effort or settings.coder_effort
    turns = transcript.turns
    result = CoderResult()

    for start, end in _chunks(len(turns)):
        window = turns[max(0, start - OVERLAP):end]
        _call(transcript, window, {t.turn_id for t in turns[start:end]}, "coder", model, effort, result)

    missing = {t.turn_id for t in turns} - set(result.therapist) - set(result.client)
    if missing:
        result.warnings.append(f"coder skipped {len(missing)} turns; re-requested")
        _call(transcript, turns, missing, "coder-repair", model, effort, result)
        missing = {t.turn_id for t in turns} - set(result.therapist) - set(result.client)
    for turn_id in sorted(missing):
        result.warnings.append(f"T{turn_id} left uncoded after repair; defaulted")
        if transcript.turns[turn_id].role == "therapist":
            result.therapist[turn_id] = TherapistCode(
                turn_id=turn_id, rationale="not coded (default)", reflection="none", question="none",
                therapist_input="none", main_behaviour="other", mi_behaviour="none", adherence="neutral",
            )
        else:
            result.client[turn_id] = ClientCode(turn_id=turn_id, rationale="not coded (default)", talk_type="neutral")

    fixed = 0
    for turn_id, code in list(result.therapist.items()):
        result.therapist[turn_id], changed = _make_consistent(code)
        fixed += changed
    if fixed:
        result.warnings.append(f"{fixed} therapist codes made internally consistent")
    return result


def labels_from_codes(turns: list[Turn], result: CoderResult) -> list[TurnLabels]:
    out = []
    for t in turns:
        if t.role == "client":
            out.append(TurnLabels(role="client", words=t.words, talk_type=result.client[t.turn_id].talk_type))
        else:
            c = result.therapist[t.turn_id]
            out.append(TurnLabels(
                role="therapist", words=t.words, main_behaviour=c.main_behaviour, reflection=c.reflection,
                question=c.question, therapist_input=c.therapist_input, adherence=c.adherence,
            ))
    return out
