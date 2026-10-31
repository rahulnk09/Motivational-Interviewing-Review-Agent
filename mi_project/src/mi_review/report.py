"""Final report: rubric + supervisor feedback with timestamps and quotes resolved from turn ids."""

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .coder import ClientCode, CoderResult, TherapistCode
from .metrics import RubricResult
from .schemas import CUUsage, LLMUsage, Transcript, format_ms
from .supervisor import SupervisorOutput


class Evidence(BaseModel):
    turn_id: int
    role: str
    start_ms: int
    timestamp: str
    quote: str


class GlobalScore(BaseModel):
    score: float
    justification: str
    evidence: list[Evidence]


class FeedbackItem(BaseModel):
    kind: Literal["strength", "improvement"]
    title: str
    category: str
    insight: str
    better_response: str | None = None
    evidence: list[Evidence]

    @property
    def start_ms(self) -> int:
        return self.evidence[0].start_ms


class ReportTurn(BaseModel):
    turn_id: int
    role: str
    speaker: str
    start_ms: int
    end_ms: int | None
    timestamp: str
    text: str
    therapist_code: TherapistCode | None = None
    client_code: ClientCode | None = None


class UsageSummary(BaseModel):
    cu: CUUsage | None = None
    llm: list[LLMUsage] = Field(default_factory=list)
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    llm_seconds: float = 0
    stage_seconds: dict[str, float] = Field(default_factory=dict)
    total_seconds: float = 0


class Report(BaseModel):
    session_id: str
    created_at: str
    source: str
    clip_start_ms: int = 0
    clip_end_ms: int | None = None
    target_behavior: str | None
    session_summary: str | None
    speaker_roles: dict[str, str]
    models: dict[str, str]
    rubric: RubricResult
    empathy: GlobalScore
    collaboration: GlobalScore
    what_went_well: list[FeedbackItem]
    what_to_improve: list[FeedbackItem]
    overall_summary: str
    coaching_tips: list[str]
    transcript: list[ReportTurn]
    warnings: list[str] = Field(default_factory=list)
    usage: UsageSummary


def summarize_usage(cu: CUUsage | None, llm: list[LLMUsage], stage_seconds: dict[str, float] | None = None) -> UsageSummary:
    stage_seconds = stage_seconds or {}
    return UsageSummary(
        cu=cu,
        llm=llm,
        input_tokens=sum(u.input_tokens for u in llm),
        cached_tokens=sum(u.cached_tokens for u in llm),
        output_tokens=sum(u.output_tokens for u in llm),
        reasoning_tokens=sum(u.reasoning_tokens for u in llm),
        llm_seconds=round(sum(u.seconds for u in llm), 2),
        stage_seconds=stage_seconds,
        total_seconds=round(sum(stage_seconds.values()), 2),
    )


def build_report(
    *,
    session_id: str,
    transcript: Transcript,
    coded: CoderResult,
    rubric: RubricResult,
    supervision: SupervisorOutput,
    models: dict[str, str],
    usage: UsageSummary,
    warnings: list[str],
    clip_start_ms: int = 0,
    clip_end_ms: int | None = None,
) -> Report:
    turns = {t.turn_id: t for t in transcript.turns}

    def refs(text: str) -> str:
        """Replace [T12] / [T12, T14] turn references with their timestamps."""
        def stamp(match: re.Match) -> str:
            ids = [int(i) for i in re.findall(r"\d+", match.group(0))]
            return "[" + ", ".join(format_ms(turns[i].start_ms) for i in ids if i in turns) + "]"
        return re.sub(r"\[T\d+(?:\s*(?:,|and|-)\s*T?\d+)*\]", stamp, text)

    def evidence(ids: list[int]) -> list[Evidence]:
        return [Evidence(turn_id=i, role=turns[i].role, start_ms=turns[i].start_ms, timestamp=format_ms(turns[i].start_ms), quote=turns[i].text) for i in ids]

    def global_score(rating) -> GlobalScore:
        return GlobalScore(score=rating.score, justification=refs(rating.justification), evidence=evidence(rating.evidence_turn_ids))

    return Report(
        session_id=session_id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=transcript.source,
        clip_start_ms=clip_start_ms,
        clip_end_ms=clip_end_ms,
        target_behavior=transcript.target_behavior,
        session_summary=transcript.summary,
        speaker_roles=transcript.speaker_roles,
        models=models,
        rubric=rubric,
        empathy=global_score(supervision.empathy),
        collaboration=global_score(supervision.collaboration),
        what_went_well=[
            FeedbackItem(kind="strength", title=s.title, category=s.skill, insight=refs(s.insight), evidence=evidence(s.turn_ids))
            for s in supervision.strengths
        ],
        what_to_improve=[
            FeedbackItem(kind="improvement", title=i.title, category=i.trap, insight=refs(i.insight),
                         better_response=i.better_response, evidence=evidence(i.turn_ids))
            for i in supervision.improvements
        ],
        overall_summary=refs(supervision.overall_summary),
        coaching_tips=[refs(tip) for tip in supervision.coaching_tips],
        transcript=[
            ReportTurn(
                turn_id=t.turn_id, role=t.role, speaker=t.speaker, start_ms=t.start_ms, end_ms=t.end_ms,
                timestamp=t.timestamp, text=t.text,
                therapist_code=coded.therapist.get(t.turn_id), client_code=coded.client.get(t.turn_id),
            )
            for t in transcript.turns
        ],
        warnings=warnings,
        usage=usage,
    )
