"""Shared data models. LLM output schemas live next to their agents."""

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["therapist", "client"]


def format_ms(ms: int | None) -> str:
    if ms is None:
        return "--:--"
    seconds = ms // 1000
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


class Phrase(BaseModel):
    speaker: str
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


class GoldCodes(BaseModel):
    """AnnoMI expert labels (majority vote when several annotators)."""

    main_therapist_behaviour: str | None = None
    reflection_exists: bool | None = None
    reflection_subtype: str | None = None
    question_exists: bool | None = None
    question_subtype: str | None = None
    therapist_input_exists: bool | None = None
    therapist_input_subtype: str | None = None
    client_talk_type: str | None = None
    n_annotators: int = 1


class Turn(BaseModel):
    turn_id: int
    role: Role
    speaker: str
    start_ms: int
    end_ms: int | None = None
    text: str
    gold: GoldCodes | None = None

    @property
    def timestamp(self) -> str:
        return format_ms(self.start_ms)

    @property
    def words(self) -> int:
        return len(self.text.split())


class Transcript(BaseModel):
    source: str
    turns: list[Turn]
    target_behavior: str | None = None
    summary: str | None = None
    speaker_roles: dict[str, Role] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    mi_quality: str | None = None


class LLMUsage(BaseModel):
    step: str
    model: str
    seconds: float
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


class CUUsage(BaseModel):
    analyzer_id: str
    seconds: float
    from_cache: bool
    audio_hours: float | None = None
    video_hours: float | None = None
    tokens: dict[str, int] = Field(default_factory=dict)
