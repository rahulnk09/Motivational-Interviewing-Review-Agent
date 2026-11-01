from mi_review.coder import ClientCode, CoderResult, TherapistCode
from mi_review.metrics import score
from mi_review.report import build_report, summarize_usage
from mi_review.schemas import LLMUsage, Transcript, Turn
from mi_review.supervisor import GlobalRating, Improvement, Strength, SupervisorOutput, _check

TURNS = [
    Turn(turn_id=0, role="therapist", speaker="S1", start_ms=41_000, text="What brings you in?"),
    Turn(turn_id=1, role="client", speaker="S2", start_ms=58_000, text="I want to cut back."),
    Turn(turn_id=2, role="therapist", speaker="S1", start_ms=75_000, text="You're ready for a change."),
]
TRANSCRIPT = Transcript(source="test", turns=TURNS, target_behavior="reducing vaping")
CODED = CoderResult(
    therapist={
        0: TherapistCode(turn_id=0, rationale="x", reflection="none", question="open", therapist_input="none",
                         main_behaviour="question", mi_behaviour="none", adherence="adherent"),
        2: TherapistCode(turn_id=2, rationale="x", reflection="complex", question="none", therapist_input="none",
                         main_behaviour="reflection", mi_behaviour="none", adherence="adherent"),
    },
    client={1: ClientCode(turn_id=1, rationale="x", talk_type="change")},
)


def _output(**kw):
    base = dict(
        empathy=GlobalRating(justification="Good listening at [T2].", evidence_turn_ids=[2, 99], score=4.0),
        collaboration=GlobalRating(justification="Shared agenda [T0, T2].", evidence_turn_ids=[0], score=3.5),
        strengths=[Strength(title="Reflection", skill="complex_reflection", insight="At [T2] you deepened it.", turn_ids=[1, 2])],
        improvements=[Improvement(title="Bad cite", trap="other", insight="x", turn_ids=[1, 42], better_response="y")],
        overall_summary="Solid [T0], then at T2 you reflected; T9 is unknown.",
        coaching_tips=["Reflect more after [T1]."],
    )
    return SupervisorOutput(**(base | kw))


def test_citation_check_filters_invalid_and_orders_therapist_first():
    out, check, warnings = _check(_output(), TRANSCRIPT)
    assert out.empathy.evidence_turn_ids == [2]
    assert out.strengths[0].turn_ids == [2, 1]
    assert out.improvements == [] and check.dropped_items == 1 and warnings
    assert (check.cited, check.valid) == (7, 5)


def test_report_resolves_timestamps_quotes_and_turn_refs():
    out, _, _ = _check(_output(), TRANSCRIPT)
    rubric = score([], empathy=out.empathy.score, collaboration=out.collaboration.score)
    usage = summarize_usage(None, [LLMUsage(step="coder", model="m", seconds=1.5, input_tokens=10, cached_tokens=4, output_tokens=5)], {"code": 1.6})
    report = build_report(session_id="s", transcript=TRANSCRIPT, coded=CODED, rubric=rubric, supervision=out,
                          models={"coder": "m"}, usage=usage, warnings=[])
    ev = report.what_went_well[0].evidence[0]
    assert (ev.turn_id, ev.timestamp, ev.quote) == (2, "01:15", "You're ready for a change.")
    assert report.empathy.justification == "Good listening at [01:15]."
    assert report.collaboration.justification == "Shared agenda [00:41, 01:15]."
    assert report.coaching_tips == ["Reflect more after [00:58]."]
    assert report.overall_summary == "Solid [00:41], then at 01:15 you reflected; T9 is unknown."
    assert report.transcript[1].client_code.talk_type == "change"
    assert report.usage.input_tokens == 10 and report.usage.total_seconds == 1.6
