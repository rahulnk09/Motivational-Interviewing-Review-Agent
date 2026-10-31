"""Deterministic MI rubric: 6 metrics -> 0-12 proficiency score, plus the client change talk ratio."""

from typing import Literal

from pydantic import BaseModel

from .schemas import Turn

Level = Literal["advanced", "basic", "below", "insufficient_data", "pending"]


class TurnLabels(BaseModel):
    """Role-normalised labels for one turn, from either the Coder agent or AnnoMI gold."""

    role: Literal["therapist", "client"]
    words: int
    main_behaviour: str | None = None
    reflection: str = "none"
    question: str = "none"
    therapist_input: str = "none"
    adherence: str | None = None
    talk_type: str | None = None


class Counts(BaseModel):
    therapist_turns: int = 0
    client_turns: int = 0
    therapist_words: int = 0
    client_words: int = 0
    questions: int = 0
    open_questions: int = 0
    closed_questions: int = 0
    reflections: int = 0
    simple_reflections: int = 0
    complex_reflections: int = 0
    therapist_inputs: int = 0
    adherent: int = 0
    non_adherent: int = 0
    change_talk: int = 0
    sustain_talk: int = 0
    neutral_talk: int = 0


class MetricResult(BaseModel):
    key: str
    label: str
    value: float | None
    display: str
    basic: float
    advanced: float
    comparison: Literal[">=", ">"]
    level: Level
    points: int
    note: str | None = None


class RubricResult(BaseModel):
    counts: Counts
    metrics: list[MetricResult]
    proficiency_points: int
    proficiency_max: int = 12
    proficiency_band: str
    complete: bool
    change_talk_ratio: float | None
    therapist_word_share: float | None


# (key, label, basic, advanced, comparison) — thresholds from mi_approach_document.md
RUBRIC = [
    ("empathy", "Empathy (1-5)", 3.5, 4.0, ">="),
    ("collaboration", "Collaboration (1-5)", 3.5, 4.0, ">="),
    ("reflection_to_question", "Reflection-to-Question Ratio", 1.0, 2.0, ">="),
    ("pct_open_questions", "% Open Questions", 0.40, 0.50, ">"),
    ("pct_complex_reflections", "% Complex Reflections", 0.40, 0.50, ">"),
    ("pct_mi_adherent", "% MI Adherent", 0.90, 1.00, ">="),
]
_PERCENT_KEYS = {"pct_open_questions", "pct_complex_reflections", "pct_mi_adherent"}


def labels_from_gold(turns: list[Turn]) -> list[TurnLabels]:
    out = []
    for t in turns:
        g = t.gold
        if t.role == "client":
            out.append(TurnLabels(role="client", words=t.words, talk_type=g.client_talk_type))
        else:
            out.append(TurnLabels(
                role="therapist", words=t.words, main_behaviour=g.main_therapist_behaviour,
                reflection=(g.reflection_subtype or "none") if g.reflection_exists else "none",
                question=(g.question_subtype or "none") if g.question_exists else "none",
                therapist_input=(g.therapist_input_subtype or "none") if g.therapist_input_exists else "none",
            ))
    return out


def count(labels: list[TurnLabels]) -> Counts:
    c = Counts()
    for lab in labels:
        if lab.role == "client":
            c.client_turns += 1
            c.client_words += lab.words
            c.change_talk += lab.talk_type == "change"
            c.sustain_talk += lab.talk_type == "sustain"
            c.neutral_talk += lab.talk_type == "neutral"
            continue
        c.therapist_turns += 1
        c.therapist_words += lab.words
        # One question / one reflection per turn (MITI: a volley gets a single question code)
        if lab.question != "none":
            c.questions += 1
            c.open_questions += lab.question == "open"
            c.closed_questions += lab.question == "closed"
        if lab.reflection != "none":
            c.reflections += 1
            c.simple_reflections += lab.reflection == "simple"
            c.complex_reflections += lab.reflection == "complex"
        c.therapist_inputs += lab.therapist_input != "none"
        c.adherent += lab.adherence == "adherent"
        c.non_adherent += lab.adherence == "non_adherent"
    return c


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def raw_values(c: Counts) -> dict[str, float | None]:
    """Metric values from counts. R:Q with no questions uses the reflection count (denominator 1)."""
    rq = None if c.questions == 0 and c.reflections == 0 else c.reflections / max(c.questions, 1)
    return {
        "reflection_to_question": rq,
        "pct_open_questions": _ratio(c.open_questions, c.questions),
        "pct_complex_reflections": _ratio(c.complex_reflections, c.reflections),
        "pct_mi_adherent": _ratio(c.adherent, c.adherent + c.non_adherent),
        "change_talk_ratio": _ratio(c.change_talk, c.change_talk + c.sustain_talk),
        "therapist_word_share": _ratio(c.therapist_words, c.therapist_words + c.client_words),
    }


def _level(value: float | None, basic: float, advanced: float, comparison: str) -> Level:
    def meets(threshold: float) -> bool:
        return value >= threshold - 1e-9 if comparison == ">=" else value > threshold + 1e-9

    if meets(advanced):
        return "advanced"
    return "basic" if meets(basic) else "below"


def _display(key: str, value: float | None) -> str:
    if value is None:
        return "n/a"
    if key in _PERCENT_KEYS:
        return f"{value:.0%}"
    if key == "reflection_to_question":
        return f"{value:.2f}"
    return f"{value:.1f}"


def band(points: int) -> str:
    if points >= 10:
        return "Advanced proficiency"
    return "Basic proficiency" if points >= 7 else "Developing"


def score(labels: list[TurnLabels], empathy: float | None = None, collaboration: float | None = None) -> RubricResult:
    c = count(labels)
    values = raw_values(c) | {"empathy": empathy, "collaboration": collaboration}
    metrics = []
    for key, label, basic, advanced, comparison in RUBRIC:
        value = values[key]
        note = None
        if value is None:
            level: Level = "pending" if key in ("empathy", "collaboration") else "insufficient_data"
        else:
            level = _level(value, basic, advanced, comparison)
            if key == "reflection_to_question" and c.questions == 0:
                note = "no questions asked; ratio uses the reflection count"
        points = {"advanced": 2, "basic": 1}.get(level, 0)
        metrics.append(MetricResult(
            key=key, label=label, value=value, display=_display(key, value), basic=basic, advanced=advanced,
            comparison=comparison, level=level, points=points, note=note,
        ))
    total = sum(m.points for m in metrics)
    return RubricResult(
        counts=c,
        metrics=metrics,
        proficiency_points=total,
        proficiency_band=band(total),
        complete=all(m.level != "pending" for m in metrics),
        change_talk_ratio=values["change_talk_ratio"],
        therapist_word_share=values["therapist_word_share"],
    )
