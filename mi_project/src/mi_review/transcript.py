"""Phrases -> speaker turns (volleys) with clinician/client role mapping."""

from collections import Counter

from .schemas import Phrase, Role, Transcript, Turn


def speaker_stats(phrases: list[Phrase]) -> dict[str, dict[str, int]]:
    stats: dict[str, Counter] = {}
    for p in phrases:
        s = stats.setdefault(p.speaker, Counter())
        s["phrases"] += 1
        s["words"] += len(p.text.split())
        s["questions"] += p.text.rstrip().endswith("?")
    return {k: dict(v) for k, v in stats.items()}


def infer_roles(phrases: list[Phrase], clinician_hint: str | None) -> tuple[dict[str, Role], list[str]]:
    """Clinician = CU ClinicianSpeaker field when valid, else the speaker asking the most questions."""
    stats = speaker_stats(phrases)
    warnings: list[str] = []
    if not stats:
        return {}, ["no speech detected"]
    heuristic = max(stats, key=lambda s: (stats[s]["questions"], stats[s]["words"]))
    if clinician_hint in stats:
        clinician = clinician_hint
        if clinician != heuristic:
            warnings.append(f"role check: CU says clinician={clinician_hint}, question heuristic says {heuristic}")
    else:
        clinician = heuristic
        warnings.append(f"CU clinician field unavailable ({clinician_hint!r}); used question heuristic -> {heuristic}")
    if len(stats) > 2:
        warnings.append(f"{len(stats)} speakers detected; all non-clinician speakers mapped to client")
    return {s: ("therapist" if s == clinician else "client") for s in stats}, warnings


def build_turns(phrases: list[Phrase], roles: dict[str, Role]) -> list[Turn]:
    """Merge consecutive phrases with the same role into one turn."""
    turns: list[Turn] = []
    for p in sorted(phrases, key=lambda x: x.start_ms):
        role = roles.get(p.speaker, "client")
        if turns and turns[-1].role == role:
            last = turns[-1]
            last.text = f"{last.text} {p.text}"
            last.end_ms = max(last.end_ms or p.end_ms, p.end_ms)
        else:
            turns.append(Turn(turn_id=len(turns), role=role, speaker=p.speaker, start_ms=p.start_ms, end_ms=p.end_ms, text=p.text))
    return turns


def transcript_from_ingest(ingest, source: str) -> Transcript:
    roles, warnings = infer_roles(ingest.phrases, ingest.fields.get("ClinicianSpeaker"))
    return Transcript(
        source=source,
        turns=build_turns(ingest.phrases, roles),
        target_behavior=ingest.fields.get("TargetBehavior"),
        summary=ingest.fields.get("SessionSummary"),
        speaker_roles=roles,
        warnings=warnings,
    )
