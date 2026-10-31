"""eval-supervisor: do global ratings and the 0-12 proficiency score separate expert-rated high vs low MI sessions?"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from pydantic import BaseModel

from ..annomi import auc, load_transcript
from ..coder import labels_from_codes
from ..config import ASSETS_DIR, EVAL_DIR, get_settings
from ..metrics import score
from ..schemas import LLMUsage
from ..supervisor import CitationCheck, SupervisorOutput, supervise, system_prompt
from .eval_coder import _coded, _tag as coder_tag


class SupervisedRecord(BaseModel):
    output: SupervisorOutput
    usage: LLMUsage
    check: CitationCheck
    warnings: list[str]


def _tag(model: str, effort: str) -> str:
    return f"{model}_{effort}_{hashlib.sha256(system_prompt().encode()).hexdigest()[:8]}"


def _supervised(tid: int, coder_model: str, coder_effort: str, model: str, effort: str, tag: str, run: int) -> SupervisedRecord:
    path = EVAL_DIR / "supervisor" / tag / f"{tid}.run{run}.json"
    if path.exists():
        return SupervisedRecord.model_validate_json(path.read_text(encoding="utf-8"))
    transcript = load_transcript(tid)
    coded = _coded(tid, coder_model, coder_effort, coder_tag(coder_model, coder_effort))
    rubric = score(labels_from_codes(transcript.turns, coded))
    out, usage, check, warnings = supervise(transcript, coded, rubric, model=model, effort=effort)
    record = SupervisedRecord(output=out, usage=usage, check=check, warnings=warnings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=1), encoding="utf-8")
    return record


def _row(tid: int, rec: SupervisedRecord, coder_model: str, coder_effort: str) -> dict:
    transcript = load_transcript(tid)
    coded = _coded(tid, coder_model, coder_effort, coder_tag(coder_model, coder_effort))
    out = rec.output
    rubric = score(labels_from_codes(transcript.turns, coded), empathy=out.empathy.score, collaboration=out.collaboration.score)
    return {
        "transcript_id": tid,
        "mi_quality": transcript.mi_quality,
        "empathy": out.empathy.score,
        "collaboration": out.collaboration.score,
        "relational": (out.empathy.score + out.collaboration.score) / 2,
        "proficiency_points": rubric.proficiency_points,
        "band": rubric.proficiency_band,
        "n_strengths": len(out.strengths),
        "n_improvements": len(out.improvements),
        "traps": ",".join(i.trap for i in out.improvements),
        "cited": rec.check.cited,
        "valid": rec.check.valid,
        "dropped_items": rec.check.dropped_items,
        "seconds": rec.usage.seconds,
        "input_tokens": rec.usage.input_tokens,
        "output_tokens": rec.usage.output_tokens,
    }


def run(ids: list[int] | None = None, model: str | None = None, effort: str | None = None, repeat: int = 3, workers: int = 6) -> dict:
    settings = get_settings()
    model = model or settings.supervisor_deployment
    effort = effort or settings.supervisor_effort
    coder_model, coder_effort = settings.coder_deployment, settings.coder_effort
    split = json.loads((ASSETS_DIR / "eval_split.json").read_text(encoding="utf-8"))
    ids = ids or split["sample"] + split["multi_annotator"]
    tag = _tag(model, effort)
    # Stability check: re-run the first `repeat` transcripts of each quality once more
    by_quality = {q: [t for t in ids if load_transcript(t).mi_quality == q] for q in ("high", "low")}
    repeat_ids = by_quality["high"][: (repeat + 1) // 2] + by_quality["low"][: repeat // 2]
    print(f"eval-supervisor: {len(ids)} transcripts | supervisor={model}/{effort} coder={coder_model}/{coder_effort} | tag={tag} | repeats={repeat_ids}")

    jobs = [(tid, 1) for tid in ids] + [(tid, 2) for tid in repeat_ids]
    records: dict[tuple[int, int], SupervisedRecord] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_supervised, tid, coder_model, coder_effort, model, effort, tag, r): (tid, r) for tid, r in jobs}
        for fut in as_completed(futures):
            records[futures[fut]] = fut.result()

    df = pd.DataFrame([_row(tid, records[(tid, 1)], coder_model, coder_effort) for tid in ids]).set_index("transcript_id")
    stability = []
    for tid in repeat_ids:
        a, b = records[(tid, 1)].output, records[(tid, 2)].output
        pa = df.loc[tid, "proficiency_points"]
        pb = _row(tid, records[(tid, 2)], coder_model, coder_effort)["proficiency_points"]
        stability.append({"transcript_id": tid, "d_empathy": abs(a.empathy.score - b.empathy.score),
                          "d_collaboration": abs(a.collaboration.score - b.collaboration.score), "d_points": abs(int(pa) - int(pb))})

    summary = {
        "supervisor": f"{model}/{effort}",
        "coder": f"{coder_model}/{coder_effort}",
        "tag": tag,
        "n": df["mi_quality"].value_counts().to_dict(),
        "auc_high_vs_low": {k: round(auc(df, k), 3) for k in ("proficiency_points", "empathy", "collaboration", "relational")},
        "mean_by_quality": df.groupby("mi_quality")[["proficiency_points", "empathy", "collaboration"]].mean().round(2).to_dict(),
        "bands_by_quality": pd.crosstab(df["mi_quality"], df["band"]).to_dict(),
        "citation_validity": round(float(df["valid"].sum() / max(df["cited"].sum(), 1)), 3),
        "dropped_items": int(df["dropped_items"].sum()),
        "stability": stability,
        "traps_by_quality": {q: pd.Series(",".join(df.loc[df["mi_quality"] == q, "traps"]).split(",")).value_counts().to_dict() for q in ("high", "low")},
        "cost": {"mean_seconds": round(float(df["seconds"].mean()), 1), "mean_input_tokens": round(float(df["input_tokens"].mean())),
                 "mean_output_tokens": round(float(df["output_tokens"].mean()))},
    }
    out_dir = EVAL_DIR / "supervisor" / tag
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    df.to_csv(out_dir / "transcripts.csv")

    print(f"\nAUC high vs low: {summary['auc_high_vs_low']}")
    print(f"Mean by quality: {summary['mean_by_quality']}")
    print(f"Bands by quality: {summary['bands_by_quality']}")
    print(f"Citation validity: {summary['citation_validity']} | dropped items: {summary['dropped_items']}")
    print(f"Stability (run1 vs run2): {stability}")
    print(f"Traps by quality: {summary['traps_by_quality']}")
    print(f"Cost: {summary['cost']}")
    print(df[["mi_quality", "empathy", "collaboration", "proficiency_points", "band"]].sort_values("proficiency_points").to_string())
    print(f"Saved: {out_dir}")
    return summary
