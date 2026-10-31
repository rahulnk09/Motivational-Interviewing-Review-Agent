"""eval-coder: Coder agent vs AnnoMI expert labels (turn-level agreement, transcript-level metrics, human ceiling)."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score

from ..annomi import auc, load_full, load_transcript
from ..coder import CoderResult, code_transcript, labels_from_codes, system_prompt
from ..config import ASSETS_DIR, EVAL_DIR, get_settings
from ..metrics import labels_from_gold, score

FIELDS = {
    "main_behaviour": ["reflection", "question", "therapist_input", "other"],
    "reflection": ["none", "simple", "complex"],
    "question": ["none", "open", "closed"],
    "therapist_input": ["none", "information", "advice", "negotiation", "options"],
    "talk_type": ["change", "neutral", "sustain"],
}
TRANSCRIPT_METRICS = ["reflection_to_question", "pct_open_questions", "pct_complex_reflections", "change_talk_ratio"]


def _tag(model: str, effort: str) -> str:
    prompt_hash = hashlib.sha256(system_prompt().encode()).hexdigest()[:8]
    return f"{model}_{effort}_{prompt_hash}"


def _coded(tid: int, model: str, effort: str, tag: str) -> CoderResult:
    path = EVAL_DIR / "coder" / tag / f"{tid}.json"
    if path.exists():
        return CoderResult.model_validate_json(path.read_text(encoding="utf-8"))
    result = code_transcript(load_transcript(tid), model=model, effort=effort)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=1), encoding="utf-8")
    return result


def _agreement(gold: pd.Series, pred: pd.Series, labels: list[str]) -> dict:
    return {
        "n": int(len(gold)),
        "accuracy": round(float(accuracy_score(gold, pred)), 3),
        "macro_f1": round(float(f1_score(gold, pred, labels=labels, average="macro", zero_division=0)), 3),
        "kappa": round(float(cohen_kappa_score(gold, pred, labels=labels)), 3),
        "labels": labels,
        "confusion": confusion_matrix(gold, pred, labels=labels).tolist(),
    }


def _turn_rows(tid: int, result: CoderResult) -> list[dict]:
    transcript = load_transcript(tid)
    gold = labels_from_gold(transcript.turns)
    pred = labels_from_codes(transcript.turns, result)
    rows = []
    for g, p in zip(gold, pred):
        row = {"transcript_id": tid, "mi_quality": transcript.mi_quality, "role": g.role, "multi": transcript.turns[0].gold.n_annotators > 1}
        if g.role == "client":
            row |= {"gold_talk_type": g.talk_type, "pred_talk_type": p.talk_type}
        else:
            for f in ("main_behaviour", "reflection", "question", "therapist_input"):
                row |= {f"gold_{f}": getattr(g, f), f"pred_{f}": getattr(p, f)}
        rows.append(row)
    return rows


def _transcript_row(tid: int, result: CoderResult) -> dict:
    transcript = load_transcript(tid)
    gold = score(labels_from_gold(transcript.turns))
    pred = score(labels_from_codes(transcript.turns, result))
    gv = {m.key: m.value for m in gold.metrics} | {"change_talk_ratio": gold.change_talk_ratio}
    pv = {m.key: m.value for m in pred.metrics} | {"change_talk_ratio": pred.change_talk_ratio}
    row = {"transcript_id": tid, "mi_quality": transcript.mi_quality}
    for k in TRANSCRIPT_METRICS:
        row[f"gold_{k}"], row[f"pred_{k}"] = gv[k], pv[k]
    row["seconds"] = sum(u.seconds for u in result.usage)
    row["input_tokens"] = sum(u.input_tokens for u in result.usage)
    row["output_tokens"] = sum(u.output_tokens for u in result.usage)
    row["warnings"] = len(result.warnings)
    return row


def _field_agreement(turns: pd.DataFrame) -> dict:
    out = {}
    for field, labels in FIELDS.items():
        sub = turns.dropna(subset=[f"gold_{field}", f"pred_{field}"])
        sub = sub[sub[f"gold_{field}"].isin(labels)]
        if len(sub):
            out[field] = _agreement(sub[f"gold_{field}"], sub[f"pred_{field}"], labels)
    return out


def human_ceiling(transcript_ids: list[int]) -> dict:
    """Mean kappa of each annotator vs the majority of the other annotators (leave-one-out)."""
    raw = load_full()
    raw = raw[raw["transcript_id"].isin(transcript_ids)].copy()
    raw["reflection"] = raw["reflection_subtype"].where(raw["reflection_exists"] == "True", "none")
    raw["question"] = raw["question_subtype"].where(raw["question_exists"] == "True", "none")
    raw["therapist_input"] = raw["therapist_input_subtype"].where(raw["therapist_input_exists"] == "True", "none")
    raw = raw.rename(columns={"main_therapist_behaviour": "main_behaviour", "client_talk_type": "talk_type"})
    out = {}
    for field, labels in FIELDS.items():
        role = "client" if field == "talk_type" else "therapist"
        sub = raw[(raw["interlocutor"] == role) & raw[field].isin(labels)]
        wide = sub.pivot_table(index=["transcript_id", "utterance_id"], columns="annotator_id", values=field, aggfunc="first")
        kappas = []
        for a in wide.columns:
            others = wide.drop(columns=a).apply(lambda r: r.dropna().value_counts().index[0] if r.notna().any() else None, axis=1)
            mask = wide[a].notna() & others.notna()
            if mask.sum() > 10:
                kappas.append(cohen_kappa_score(wide.loc[mask, a], others[mask], labels=labels))
        out[field] = round(float(pd.Series(kappas).mean()), 3) if kappas else None
    return out


def run(ids: list[int] | None = None, include_multi: bool = True, model: str | None = None, effort: str | None = None, workers: int = 6) -> dict:
    settings = get_settings()
    model = model or settings.coder_deployment
    effort = effort or settings.coder_effort
    split = json.loads((ASSETS_DIR / "eval_split.json").read_text(encoding="utf-8"))
    multi = split["multi_annotator"]
    if ids is None:
        ids = split["sample"] + (multi if include_multi else [])
    tag = _tag(model, effort)
    print(f"eval-coder: {len(ids)} transcripts | model={model} effort={effort} | cache tag={tag}")

    results: dict[int, CoderResult] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_coded, tid, model, effort, tag): tid for tid in ids}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

    turns = pd.DataFrame([r for tid in ids for r in _turn_rows(tid, results[tid])])
    per_t = pd.DataFrame([_transcript_row(tid, results[tid]) for tid in ids]).set_index("transcript_id")

    summary = {"model": model, "effort": effort, "tag": tag, "transcripts": ids, "agreement": {}, "transcript_metrics": {}}
    summary["agreement"]["all"] = _field_agreement(turns)
    multi_in = [t for t in ids if t in multi]
    if multi_in:
        summary["agreement"]["multi_annotator"] = _field_agreement(turns[turns["transcript_id"].isin(multi_in)])
        summary["human_ceiling_kappa"] = human_ceiling(multi_in)
    for k in TRANSCRIPT_METRICS:
        pair = per_t[[f"gold_{k}", f"pred_{k}"]].dropna()
        rho = spearmanr(pair[f"gold_{k}"], pair[f"pred_{k}"]).statistic if len(pair) > 2 else None
        pred_auc = auc(per_t.rename(columns={f"pred_{k}": k}), k) if per_t["mi_quality"].nunique() == 2 else None
        gold_auc = auc(per_t.rename(columns={f"gold_{k}": k}), k) if per_t["mi_quality"].nunique() == 2 else None
        summary["transcript_metrics"][k] = {
            "mae": round(float((pair[f"gold_{k}"] - pair[f"pred_{k}"]).abs().mean()), 3),
            "spearman": None if rho is None else round(float(rho), 3),
            "auc_pred": None if pred_auc is None else round(pred_auc, 3),
            "auc_gold": None if gold_auc is None else round(gold_auc, 3),
        }
    summary["cost"] = {
        "mean_seconds_per_transcript": round(float(per_t["seconds"].mean()), 1),
        "mean_input_tokens": round(float(per_t["input_tokens"].mean())),
        "mean_output_tokens": round(float(per_t["output_tokens"].mean())),
        "transcripts_with_warnings": int((per_t["warnings"] > 0).sum()),
    }

    out_dir = EVAL_DIR / "coder" / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    turns.to_csv(out_dir / "turns.csv", index=False)
    per_t.to_csv(out_dir / "transcripts.csv")
    _print(summary)
    print(f"Saved: {out_dir}")
    return summary


def _print(s: dict) -> None:
    ceiling = s.get("human_ceiling_kappa", {})
    print("\nTurn-level agreement (all | multi-annotator subset | human ceiling kappa):")
    print(f"  {'field':<16}{'n':>5}{'acc':>7}{'macroF1':>9}{'kappa':>7}   | {'kappa':>6} | {'human':>6}")
    for field, a in s["agreement"]["all"].items():
        m = s["agreement"].get("multi_annotator", {}).get(field, {})
        print(f"  {field:<16}{a['n']:>5}{a['accuracy']:>7}{a['macro_f1']:>9}{a['kappa']:>7}   | {m.get('kappa', '-'):>6} | {ceiling.get(field) or '-':>6}")
    for field in ("main_behaviour", "talk_type"):
        a = s["agreement"]["all"][field]
        print(f"\nConfusion {field} (rows=gold, cols=pred) {a['labels']}:")
        for label, row in zip(a["labels"], a["confusion"]):
            print(f"  {label:<16}{row}")
    print("\nTranscript-level metrics (pred vs gold):")
    for k, v in s["transcript_metrics"].items():
        print(f"  {k:<26} MAE={v['mae']:<7} spearman={v['spearman']}  AUC pred={v['auc_pred']} gold={v['auc_gold']}")
    print(f"\nCost: {s['cost']}")
