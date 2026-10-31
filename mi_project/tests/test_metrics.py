import pytest

from mi_review.annomi import gold_metrics, load_transcript
from mi_review.metrics import TurnLabels, band, labels_from_gold, score


def T(**kw):
    return TurnLabels(role="therapist", words=10, **kw)


def C(talk):
    return TurnLabels(role="client", words=10, talk_type=talk)


def _m(result, key):
    return next(m for m in result.metrics if m.key == key)


def test_approach_doc_example():
    # "Are you taking your pills?" / "I skip them..." / complex reflection; plus the CT+ST ratio example
    labels = [
        T(main_behaviour="question", question="closed", adherence="neutral"),
        C("sustain"),
        T(main_behaviour="reflection", reflection="complex", adherence="adherent"),
        C("change"),
    ]
    r = score(labels)
    assert _m(r, "reflection_to_question").value == 1.0 and _m(r, "reflection_to_question").level == "basic"
    assert _m(r, "pct_complex_reflections").value == 1.0 and _m(r, "pct_complex_reflections").level == "advanced"
    assert _m(r, "pct_open_questions").level == "below"
    assert _m(r, "pct_mi_adherent").level == "advanced"
    assert r.change_talk_ratio == 0.5
    assert _m(r, "empathy").level == "pending" and not r.complete


def test_full_score_and_bands():
    labels = [
        T(main_behaviour="reflection", reflection="complex", adherence="adherent"),
        T(main_behaviour="reflection", reflection="complex", adherence="adherent"),
        T(main_behaviour="question", question="open", adherence="adherent"),
    ]
    r = score(labels, empathy=4.5, collaboration=4.0)
    assert r.complete and r.proficiency_points == 12 and r.proficiency_band == "Advanced proficiency"
    assert [band(p) for p in (0, 6, 7, 9, 10, 12)] == ["Developing"] * 2 + ["Basic proficiency"] * 2 + ["Advanced proficiency"] * 2


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("empathy", 3.0, "below"), ("empathy", 3.5, "basic"), ("empathy", 4.0, "advanced"),
        ("collaboration", 3.5, "basic"),
    ],
)
def test_global_threshold_edges(key, value, expected):
    r = score([T(main_behaviour="other")], **{key: value})
    assert _m(r, key).level == expected


def test_strict_percent_thresholds():
    # 2 of 5 open = 40% -> not > 40% -> below; 3 of 5 = 60% -> advanced
    qs = [T(main_behaviour="question", question="open")] * 2 + [T(main_behaviour="question", question="closed")] * 3
    assert _m(score(qs), "pct_open_questions").level == "below"
    qs = [T(main_behaviour="question", question="open")] * 3 + [T(main_behaviour="question", question="closed")] * 2
    assert _m(score(qs), "pct_open_questions").level == "advanced"


def test_mi_adherent_thresholds():
    nine_of_ten = [T(main_behaviour="reflection", reflection="simple", adherence="adherent")] * 9 + [T(main_behaviour="therapist_input", therapist_input="advice", adherence="non_adherent")]
    assert _m(score(nine_of_ten), "pct_mi_adherent").level == "basic"
    neutral_only = [T(main_behaviour="other", adherence="neutral")]
    assert _m(score(neutral_only), "pct_mi_adherent").level == "insufficient_data"


def test_edge_cases_no_questions_or_reflections():
    only_reflections = [T(main_behaviour="reflection", reflection="simple")] * 3
    m = _m(score(only_reflections), "reflection_to_question")
    assert m.value == 3.0 and m.level == "advanced" and m.note
    nothing = score([T(main_behaviour="other"), C("neutral")])
    assert _m(nothing, "reflection_to_question").level == "insufficient_data"
    assert _m(nothing, "pct_open_questions").points == 0
    assert nothing.change_talk_ratio is None


def test_matches_annomi_gold_metrics():
    gm = gold_metrics()
    for tid in (0, 27, 60, 131):
        r = score(labels_from_gold(load_transcript(tid).turns))
        values = {m.key: m.value for m in r.metrics}
        for key in ("reflection_to_question", "pct_open_questions", "pct_complex_reflections"):
            expected = gm.loc[tid, key]
            assert (values[key] is None and expected != expected) or values[key] == pytest.approx(expected), (tid, key)
        expected_ct = gm.loc[tid, "change_talk_ratio"]
        assert (r.change_talk_ratio is None and expected_ct != expected_ct) or r.change_talk_ratio == pytest.approx(expected_ct)
