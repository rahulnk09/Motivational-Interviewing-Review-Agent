from mi_review.coder import ClientCode, CoderResult, TherapistCode, _chunks, _make_consistent, labels_from_codes, render_input, system_prompt
from mi_review.schemas import Transcript, Turn


def _tc(**kw):
    base = dict(turn_id=0, rationale="x", reflection="none", question="none", therapist_input="none",
                main_behaviour="other", mi_behaviour="none", adherence="neutral")
    return TherapistCode(**(base | kw))


def test_system_prompt_has_rules_and_examples():
    prompt = system_prompt()
    assert "{fewshot}" not in prompt
    assert "Example 1 (target behaviour:" in prompt and "-> talk_type=" in prompt


def test_consistency_fixes():
    fixed, changed = _make_consistent(_tc(main_behaviour="reflection"))
    assert changed and fixed.reflection == "simple"
    fixed, _ = _make_consistent(_tc(main_behaviour="question", mi_behaviour="confront", adherence="adherent"))
    assert fixed.question == "closed" and fixed.adherence == "non_adherent"
    assert _make_consistent(_tc())[1] is False


def test_render_marks_context_turns():
    tr = Transcript(source="t", target_behavior="quit smoking", turns=[
        Turn(turn_id=0, role="therapist", speaker="a", start_ms=0, text="Hi"),
        Turn(turn_id=1, role="client", speaker="b", start_ms=1, text="Hello"),
    ])
    text = render_input(tr, tr.turns, {1})
    assert "TARGET BEHAVIOUR: quit smoking" in text
    assert "[T0] CONTEXT THERAPIST: Hi" in text and "[T1] CLIENT: Hello" in text
    assert text.endswith("Code these 1 turns: T1")


def test_chunks():
    assert _chunks(50) == [(0, 50)]
    assert _chunks(200) == [(0, 80), (80, 160), (160, 200)]


def test_labels_from_codes():
    turns = [Turn(turn_id=0, role="therapist", speaker="a", start_ms=0, text="So you feel torn."),
             Turn(turn_id=1, role="client", speaker="b", start_ms=1, text="I want to quit.")]
    result = CoderResult(
        therapist={0: _tc(main_behaviour="reflection", reflection="complex", adherence="adherent")},
        client={1: ClientCode(turn_id=1, rationale="x", talk_type="change")},
    )
    labels = labels_from_codes(turns, result)
    assert labels[0].reflection == "complex" and labels[0].words == 4 and labels[1].talk_type == "change"
