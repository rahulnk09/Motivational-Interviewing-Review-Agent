from mi_review import graph
from mi_review.coder import ClientCode, CoderResult, TherapistCode
from mi_review.schemas import LLMUsage, Transcript, Turn
from mi_review.supervisor import CitationCheck, GlobalRating, Strength, SupervisorOutput

TRANSCRIPT = Transcript(source="annomi:0", target_behavior="quit smoking", turns=[
    Turn(turn_id=0, role="therapist", speaker="therapist", start_ms=0, text="What would you like to change?"),
    Turn(turn_id=1, role="client", speaker="client", start_ms=5000, text="I want to quit."),
])


def _fake_code(transcript):
    return CoderResult(
        therapist={0: TherapistCode(turn_id=0, rationale="x", reflection="none", question="open", therapist_input="none",
                                    main_behaviour="question", mi_behaviour="none", adherence="adherent")},
        client={1: ClientCode(turn_id=1, rationale="x", talk_type="change")},
        usage=[LLMUsage(step="coder", model="fake", seconds=0.1, input_tokens=100, output_tokens=20)],
    )


def _fake_supervise(transcript, coded, rubric):
    out = SupervisorOutput(
        empathy=GlobalRating(justification="ok [T0]", evidence_turn_ids=[0], score=4.0),
        collaboration=GlobalRating(justification="ok", evidence_turn_ids=[0], score=3.5),
        strengths=[Strength(title="Open question", skill="open_question", insight="good", turn_ids=[0, 1])],
        improvements=[], overall_summary="fine", coaching_tips=["keep going"],
    )
    return out, LLMUsage(step="supervisor", model="fake", seconds=0.2, input_tokens=50, output_tokens=30), CitationCheck(), []


def test_pipeline_skips_cu_for_text_input_and_streams_progress(monkeypatch):
    monkeypatch.setattr(graph, "code_transcript", _fake_code)
    monkeypatch.setattr(graph, "supervise", _fake_supervise)
    monkeypatch.setattr(graph, "transcribe", lambda *a, **k: (_ for _ in ()).throw(AssertionError("CU must be skipped")))
    events = []
    report = graph.run_pipeline(transcript=TRANSCRIPT, on_event=events.append, save=False)

    assert [(e["stage"], e["status"]) for e in events] == [
        (s, st) for s in ("code", "metrics", "supervise", "assemble") for st in ("start", "done")
    ]
    assert report.session_id == "annomi-0"
    assert report.rubric.complete and report.empathy.justification == "ok [00:00]"
    assert report.what_went_well[0].evidence[1].quote == "I want to quit."
    assert report.usage.input_tokens == 150 and set(report.usage.stage_seconds) == {"code", "metrics", "supervise", "assemble"}
    assert report.usage.cu is None
