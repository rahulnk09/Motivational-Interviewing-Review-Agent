import json

from mi_review.annomi import gold_metrics, load_transcript, multi_annotator_ids
from mi_review.config import ASSETS_DIR


def test_reserved_gold_transcript_loads_with_majority_labels():
    t = load_transcript(27)
    assert t.mi_quality == "low" and len(t.turns) == 23
    assert {turn.gold.n_annotators for turn in t.turns} == {10}
    assert all(turn.role in ("therapist", "client") for turn in t.turns)
    assert t.turns[0].start_ms == 8000
    assert all(a.start_ms <= b.start_ms for a, b in zip(t.turns, t.turns[1:]))


def test_role_label_consistency():
    t = load_transcript(60)
    for turn in t.turns:
        if turn.role == "client":
            assert turn.gold.main_therapist_behaviour is None and turn.gold.client_talk_type
        else:
            assert turn.gold.client_talk_type is None and turn.gold.main_therapist_behaviour


def test_multi_annotator_set():
    assert multi_annotator_ids() == [7, 27, 55, 56, 66, 109, 130]


def test_gold_metrics_shape():
    m = gold_metrics()
    assert len(m) == 133
    assert m["reflection_to_question"].notna().all()


def test_assets_have_no_leakage():
    split = json.loads((ASSETS_DIR / "eval_split.json").read_text(encoding="utf-8"))
    fewshot = json.loads((ASSETS_DIR / "fewshot_coder.json").read_text(encoding="utf-8"))
    pair = set(fewshot["source_transcripts"])
    assert not pair & (set(split["sample"]) | set(split["multi_annotator"]))
    assert not pair & set(split["reserved_gold_videos"])
    assert all(v >= 2 for v in fewshot["class_counts"].values())
