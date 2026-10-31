"""Supervisor agent: MITI global ratings plus grounded strengths, traps and coaching."""

import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from .coder import CoderResult
from .config import ASSETS_DIR, PROMPTS_DIR, get_settings
from .llm import structured_call
from .metrics import RubricResult
from .schemas import LLMUsage, Transcript

HalfPoint = Literal[1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
Skill = Literal[
    "complex_reflection", "simple_reflection", "summary", "open_question", "affirmation",
    "seeking_collaboration", "emphasizing_autonomy", "eliciting_change_talk", "softening_sustain_talk", "other",
]
Trap = Literal[
    "expert_trap", "question_answer_trap", "confrontation_denial_trap", "premature_focus_trap", "labeling_trap",
    "blaming_trap", "persuasion_without_permission", "missed_change_talk", "missed_reflection", "other",
]


class GlobalRating(BaseModel):
    justification: str = Field(description="2-3 sentences citing concrete moments.")
    evidence_turn_ids: list[int]
    score: HalfPoint


class Strength(BaseModel):
    title: str
    skill: Skill
    insight: str
    turn_ids: list[int] = Field(description="Therapist turn first, optionally the client turn showing impact.")


class Improvement(BaseModel):
    title: str
    trap: Trap
    insight: str
    turn_ids: list[int] = Field(description="Therapist turn first.")
    better_response: str = Field(description="What the clinician could have said instead, in the clinician's voice.")


class SupervisorOutput(BaseModel):
    empathy: GlobalRating
    collaboration: GlobalRating
    strengths: list[Strength]
    improvements: list[Improvement]
    overall_summary: str
    coaching_tips: list[str]


class CitationCheck(BaseModel):
    cited: int = 0
    valid: int = 0
    dropped_items: int = 0


def _render_anchor(anchor: dict) -> str:
    m = anchor["transcript_metrics"]
    lines = [
        f"{anchor['mi_quality'].upper()} quality excerpt (target behaviour: {anchor['topic']}; whole-session R:Q "
        f"{m['reflection_to_question']}, change talk ratio {m['change_talk_ratio']}, therapist input share {m['pct_therapist_input']})"
    ]
    for t in anchor["turns"]:
        lab = t["labels"]
        if t["role"] == "client":
            codes = lab["client_talk_type"]
        else:
            codes = f"{lab['main_therapist_behaviour']}; R={lab['reflection']}; Q={lab['question']}; input={lab['therapist_input']}"
        lines.append(f"  {t['role'].upper()} <{codes}>: {t['text']}")
    return "\n".join(lines)


@lru_cache
def system_prompt() -> str:
    anchors = json.loads((ASSETS_DIR / "supervisor_anchors.json").read_text(encoding="utf-8"))
    template = (PROMPTS_DIR / "supervisor_system.md").read_text(encoding="utf-8")
    return template.replace("{anchors}", "\n\n".join(_render_anchor(a) for a in anchors))


def render_metrics(rubric: RubricResult) -> str:
    c = rubric.counts
    lines = [
        f"- Therapist turns {c.therapist_turns}, client turns {c.client_turns}; therapist share of words "
        f"{rubric.therapist_word_share:.0%}" if rubric.therapist_word_share is not None else f"- Therapist turns {c.therapist_turns}",
        f"- Questions {c.questions} (open {c.open_questions}, closed {c.closed_questions}); reflections {c.reflections} "
        f"(simple {c.simple_reflections}, complex {c.complex_reflections}); turns with therapist input {c.therapist_inputs}",
        f"- MI-adherent turns {c.adherent}, MI-non-adherent turns {c.non_adherent}",
        f"- Client talk: change {c.change_talk}, sustain {c.sustain_talk}, neutral {c.neutral_talk}; change talk ratio "
        + ("n/a" if rubric.change_talk_ratio is None else f"{rubric.change_talk_ratio:.0%}"),
    ]
    for m in rubric.metrics:
        if m.level != "pending":
            lines.append(f"- {m.label}: {m.display} ({m.level.replace('_', ' ')}; basic {m.comparison} {m.basic}, advanced {m.comparison} {m.advanced})")
    return "\n".join(lines)


def render_input(transcript: Transcript, coded: CoderResult, rubric: RubricResult) -> str:
    lines = [f"TARGET BEHAVIOUR: {transcript.target_behavior or 'unknown'}", "", "SESSION METRICS:", render_metrics(rubric), "", "CODED TRANSCRIPT:"]
    for t in transcript.turns:
        if t.role == "therapist":
            c = coded.therapist[t.turn_id]
            codes = f"{c.main_behaviour}; R={c.reflection}; Q={c.question}; input={c.therapist_input}; MITI={c.mi_behaviour}; {c.adherence}"
        else:
            codes = coded.client[t.turn_id].talk_type
        lines.append(f"[T{t.turn_id} {t.timestamp}] {t.role.upper()} <{codes}>: {t.text}")
    return "\n".join(lines)


def _check(out: SupervisorOutput, transcript: Transcript) -> tuple[SupervisorOutput, CitationCheck, list[str]]:
    """Keep only citations to existing turns; feedback items must start with a therapist turn."""
    roles = {t.turn_id: t.role for t in transcript.turns}
    check = CitationCheck()
    warnings: list[str] = []

    def valid_ids(ids: list[int]) -> list[int]:
        check.cited += len(ids)
        kept = [i for i in dict.fromkeys(ids) if i in roles]
        check.valid += len(kept)
        return kept

    for rating in (out.empathy, out.collaboration):
        rating.evidence_turn_ids = valid_ids(rating.evidence_turn_ids)
    items = {"strengths": out.strengths, "improvements": out.improvements}
    for name, group in items.items():
        kept = []
        for item in group:
            ids = valid_ids(item.turn_ids)
            therapist_first = [i for i in ids if roles[i] == "therapist"][:1]
            ids = therapist_first + [i for i in ids if i not in therapist_first]
            if not therapist_first:
                check.dropped_items += 1
                warnings.append(f"dropped {name[:-1]} '{item.title}': no valid therapist turn cited")
                continue
            item.turn_ids = ids
            kept.append(item)
        setattr(out, name, kept[:3])
    return out, check, warnings


def supervise(
    transcript: Transcript, coded: CoderResult, rubric: RubricResult, model: str | None = None, effort: str | None = None
) -> tuple[SupervisorOutput, LLMUsage, CitationCheck, list[str]]:
    settings = get_settings()
    out, usage = structured_call(
        step="supervisor",
        model=model or settings.supervisor_deployment,
        instructions=system_prompt(),
        input=render_input(transcript, coded, rubric),
        schema=SupervisorOutput,
        effort=effort or settings.supervisor_effort,
    )
    out, check, warnings = _check(out, transcript)
    return out, usage, check, warnings
