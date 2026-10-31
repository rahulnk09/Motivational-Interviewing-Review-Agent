"""eval-ingest: audio pipeline (CU + agents) vs the AnnoMI expert transcript of the same video."""

import json
import re

import jiwer
from sklearn.metrics import accuracy_score, cohen_kappa_score

from ..annomi import load_transcript
from ..config import EVAL_DIR, REPORTS_DIR
from ..graph import run_pipeline, session_id_for
from ..ingest import transcribe
from ..metrics import labels_from_gold, score
from ..report import Report


def _norm(text: str) -> str:
    text = re.sub(r"\[[^\]]*\]", " ", text.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", text)).strip()


def _tokens(text: str) -> set[str]:
    return set(_norm(text).split())


def run(media: str, annomi_id: int, start_s: float = 0, end_s: float | None = None, reuse: bool = True) -> dict:
    gold = load_transcript(annomi_id)
    ingest = transcribe(media, start_s, end_s)
    session_id = session_id_for(media, start_s, end_s)
    path = REPORTS_DIR / f"{session_id}.json"
    report = Report.model_validate_json(path.read_text(encoding="utf-8")) if reuse and path.exists() else run_pipeline(media, start_s, end_s)
    roles = report.speaker_roles

    # 1) Transcription quality
    gold_text = _norm(" ".join(t.text for t in gold.turns))
    cu_text = _norm(" ".join(p.text for p in ingest.phrases))
    wer = jiwer.wer(gold_text, cu_text)

    # 2) Speaker attribution: map each CU phrase to the nearby gold utterance that contains most of its words
    gold_windows = [(t, t.start_ms - 3000, (t.end_ms or t.start_ms + 15000) + 3000) for t in gold.turns]
    role_words = role_ok = 0
    gold_hits: dict[int, dict[int, int]] = {}
    for p in ingest.phrases:
        words = _tokens(p.text)
        candidates = [g for g, lo, hi in gold_windows if lo <= p.start_ms <= hi]
        if not words or not candidates:
            continue
        best = max(candidates, key=lambda g: len(words & _tokens(g.text)))
        overlap = len(words & _tokens(best.text))
        if overlap / len(words) < 0.5:
            continue
        n = len(p.text.split())
        role_words += n
        role_ok += n * (roles.get(p.speaker) == best.role)
        turn = next((t for t in report.transcript if t.start_ms <= p.start_ms <= (t.end_ms or t.start_ms)), None)
        if turn is not None:
            gold_hits.setdefault(best.turn_id, {}).setdefault(turn.turn_id, 0)
            gold_hits[best.turn_id][turn.turn_id] += n

    # 3) Tag agreement for gold utterances matched to a CU turn of the same role
    turns = {t.turn_id: t for t in report.transcript}
    pairs = {"main_behaviour": [], "talk_type": []}
    for g in gold.turns:
        hits = gold_hits.get(g.turn_id)
        if not hits:
            continue
        cu_turn = turns[max(hits, key=hits.get)]
        if cu_turn.role != g.role:
            continue
        if g.role == "therapist":
            pairs["main_behaviour"].append((g.gold.main_therapist_behaviour, cu_turn.therapist_code.main_behaviour))
        else:
            pairs["talk_type"].append((g.gold.client_talk_type, cu_turn.client_code.talk_type))
    tags = {}
    for field, ps in pairs.items():
        if ps:
            gl, pr = zip(*ps)
            tags[field] = {"n": len(ps), "accuracy": round(float(accuracy_score(gl, pr)), 3),
                           "kappa": round(float(cohen_kappa_score(gl, pr)), 3) if len(set(gl) | set(pr)) > 1 else None}

    # 4) Session-level metrics: expert labels on the expert transcript vs the full audio pipeline
    gold_rubric = score(labels_from_gold(gold.turns))
    gold_vals = {m.key: m.display for m in gold_rubric.metrics} | {"change_talk_ratio": gold_rubric.change_talk_ratio}
    audio_vals = {m.key: m.display for m in report.rubric.metrics} | {"change_talk_ratio": report.rubric.change_talk_ratio}
    keys = ["reflection_to_question", "pct_open_questions", "pct_complex_reflections", "change_talk_ratio"]

    summary = {
        "media": media, "annomi_id": annomi_id, "mi_quality": gold.mi_quality,
        "wer": round(wer, 3),
        "turns": {"gold_utterances": len(gold.turns), "cu_turns": len(report.transcript), "cu_phrases": len(ingest.phrases)},
        "gold_utterances_matched": round(len(gold_hits) / len(gold.turns), 3),
        "speaker_role_accuracy_word_weighted": round(role_ok / role_words, 3) if role_words else None,
        "tag_agreement": tags,
        "session_metrics": {k: {"gold": gold_vals[k], "audio_pipeline": audio_vals[k]} for k in keys},
        "audio_pipeline_score": f"{report.rubric.proficiency_points}/12 ({report.rubric.proficiency_band})",
    }
    out = EVAL_DIR / "ingest" / f"annomi-{annomi_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print(f"Saved: {out}")
    return summary
