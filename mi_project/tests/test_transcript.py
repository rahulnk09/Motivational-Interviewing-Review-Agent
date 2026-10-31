from mi_review.schemas import Phrase
from mi_review.transcript import build_turns, infer_roles


def _p(speaker, start, text):
    return Phrase(speaker=speaker, start_ms=start, end_ms=start + 900, text=text)


PHRASES = [
    _p("Speaker 1", 0, "Hi, thanks for coming in."),
    _p("Speaker 1", 1000, "What brings you here today?"),
    _p("Speaker 2", 2000, "My wife wants me to drink less."),
    _p("Speaker 1", 3000, "She's worried about you."),
    _p("Speaker 1", 4000, "How do you feel about it?"),
    _p("Speaker 2", 5000, "I guess I could cut down."),
]


def test_merges_consecutive_phrases_into_turns():
    turns = build_turns(PHRASES, {"Speaker 1": "therapist", "Speaker 2": "client"})
    assert [t.role for t in turns] == ["therapist", "client", "therapist", "client"]
    assert turns[0].text == "Hi, thanks for coming in. What brings you here today?"
    assert (turns[0].start_ms, turns[0].end_ms) == (0, 1900)
    assert [t.turn_id for t in turns] == [0, 1, 2, 3]


def test_unordered_phrases_are_sorted():
    turns = build_turns(list(reversed(PHRASES)), {"Speaker 1": "therapist", "Speaker 2": "client"})
    assert turns[0].start_ms == 0 and turns[-1].start_ms == 5000


def test_roles_use_cu_hint_without_warning_when_heuristic_agrees():
    roles, warnings = infer_roles(PHRASES, "Speaker 1")
    assert roles == {"Speaker 1": "therapist", "Speaker 2": "client"}
    assert warnings == []


def test_roles_fall_back_to_question_heuristic():
    roles, warnings = infer_roles(PHRASES, None)
    assert roles["Speaker 1"] == "therapist"
    assert any("heuristic" in w for w in warnings)


def test_disagreement_and_extra_speakers_are_flagged():
    roles, warnings = infer_roles(PHRASES + [_p("Speaker 3", 6000, "In this video...")], "Speaker 2")
    assert roles["Speaker 2"] == "therapist" and roles["Speaker 3"] == "client"
    assert any("role check" in w for w in warnings)
    assert any("3 speakers" in w for w in warnings)


def test_merged_client_speakers_form_one_turn():
    phrases = PHRASES[:3] + [_p("Speaker 3", 2500, "And my doctor too.")]
    turns = build_turns(phrases, {"Speaker 1": "therapist", "Speaker 2": "client", "Speaker 3": "client"})
    assert turns[-1].text == "My wife wants me to drink less. And my doctor too."
