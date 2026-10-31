"""AnnoMI-full: gold labels, transcript loader, and prompt/eval assets (few-shot, anchors, eval split, benchmarks)."""

import itertools
import json
import random
from functools import lru_cache

import pandas as pd

from .config import ANNOMI_FULL_CSV, ASSETS_DIR, get_settings
from .schemas import GoldCodes, Transcript, Turn

LABEL_COLS = [
    "main_therapist_behaviour", "reflection_exists", "reflection_subtype", "question_exists", "question_subtype",
    "therapist_input_exists", "therapist_input_subtype", "client_talk_type",
]
# Label classes the few-shot examples must cover: (column, value)
CLASSES = [
    ("main_therapist_behaviour", "reflection"), ("main_therapist_behaviour", "question"),
    ("main_therapist_behaviour", "therapist_input"), ("main_therapist_behaviour", "other"),
    ("reflection_subtype", "simple"), ("reflection_subtype", "complex"),
    ("question_subtype", "open"), ("question_subtype", "closed"),
    ("therapist_input_subtype", "information"), ("therapist_input_subtype", "advice"),
    ("therapist_input_subtype", "negotiation"), ("therapist_input_subtype", "options"),
    ("client_talk_type", "change"), ("client_talk_type", "neutral"), ("client_talk_type", "sustain"),
]
FEWSHOT_PER_CLASS = 2
ANCHOR_TURNS = 12


def _ts_to_ms(ts: str) -> int:
    h, m, s = (int(x) for x in ts.split(":"))
    return (h * 3600 + m * 60 + s) * 1000


@lru_cache
def load_full() -> pd.DataFrame:
    # keep_default_na=False: "n/a" is a real label value
    return pd.read_csv(ANNOMI_FULL_CSV, keep_default_na=False)


@lru_cache
def gold_utterances() -> pd.DataFrame:
    """One row per utterance; labels are the majority vote when several annotators labelled it."""
    df = load_full()
    keys = ["transcript_id", "utterance_id"]
    n = df.groupby(keys)["annotator_id"].transform("nunique")
    single = df[n == 1].assign(n_annotators=1)
    multi = df[n > 1]
    meta = multi.groupby(keys).first()[["mi_quality", "topic", "interlocutor", "timestamp", "utterance_text", "video_url"]]
    votes = multi.groupby(keys)[LABEL_COLS].agg(lambda s: s.value_counts().index[0])
    # Independent column votes can say "exists" with subtype "n/a"; vote the subtype among annotators who gave one
    for exists, subtype in [("reflection_exists", "reflection_subtype"), ("question_exists", "question_subtype"),
                            ("therapist_input_exists", "therapist_input_subtype")]:
        sub_votes = multi[multi[subtype] != "n/a"].groupby(keys)[subtype].agg(lambda s: s.value_counts().index[0])
        votes[subtype] = sub_votes.reindex(votes.index).where(votes[exists] == "True", "n/a").fillna("n/a")
    counts = multi.groupby(keys)["annotator_id"].nunique().rename("n_annotators")
    voted = meta.join(votes).join(counts).reset_index()
    out = pd.concat([single[voted.columns], voted]).sort_values(keys).reset_index(drop=True)
    out["topic"] = out["topic"].str.strip()
    out["words"] = out["utterance_text"].str.split().str.len()
    return out


def multi_annotator_ids() -> list[int]:
    g = gold_utterances()
    return sorted(g.loc[g["n_annotators"] > 1, "transcript_id"].unique().tolist())


def _flag(value: str) -> bool | None:
    return {"True": True, "False": False}.get(value)


def _na(value: str) -> str | None:
    return None if value == "n/a" else value


def load_transcript(transcript_id: int) -> Transcript:
    rows = gold_utterances().query("transcript_id == @transcript_id").sort_values("utterance_id")
    if rows.empty:
        raise KeyError(f"AnnoMI transcript {transcript_id} not found")
    starts = [_ts_to_ms(t) for t in rows["timestamp"]]
    turns = []
    for i, r in enumerate(rows.itertuples()):
        gold = GoldCodes(
            main_therapist_behaviour=_na(r.main_therapist_behaviour),
            reflection_exists=_flag(r.reflection_exists),
            reflection_subtype=_na(r.reflection_subtype),
            question_exists=_flag(r.question_exists),
            question_subtype=_na(r.question_subtype),
            therapist_input_exists=_flag(r.therapist_input_exists),
            therapist_input_subtype=_na(r.therapist_input_subtype),
            client_talk_type=_na(r.client_talk_type),
            n_annotators=r.n_annotators,
        )
        turns.append(Turn(
            turn_id=i, role=r.interlocutor, speaker=r.interlocutor, start_ms=starts[i],
            end_ms=starts[i + 1] if i + 1 < len(starts) else None, text=r.utterance_text, gold=gold,
        ))
    first = rows.iloc[0]
    return Transcript(
        source=f"annomi:{transcript_id}", turns=turns, target_behavior=first["topic"],
        speaker_roles={"therapist": "therapist", "client": "client"}, mi_quality=first["mi_quality"],
    )


def gold_metrics(utts: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-transcript MI metrics computed from gold labels."""
    g = gold_utterances() if utts is None else utts
    ther = g[g["interlocutor"] == "therapist"]
    cli = g[g["interlocutor"] == "client"]
    by_t = ther.groupby("transcript_id")
    q = by_t["question_exists"].apply(lambda s: (s == "True").sum())
    r = by_t["reflection_exists"].apply(lambda s: (s == "True").sum())
    oq = by_t["question_subtype"].apply(lambda s: (s == "open").sum())
    cr = by_t["reflection_subtype"].apply(lambda s: (s == "complex").sum())
    inp = by_t["main_therapist_behaviour"].apply(lambda s: (s == "therapist_input").mean())
    talk = pd.crosstab(cli["transcript_id"], cli["client_talk_type"])
    words = g.pivot_table(index="transcript_id", columns="interlocutor", values="words", aggfunc="sum")
    m = pd.DataFrame({
        "mi_quality": g.groupby("transcript_id")["mi_quality"].first(),
        "reflection_to_question": r / q.where(q > 0, 1),
        "pct_open_questions": oq / q.where(q > 0),
        "pct_complex_reflections": cr / r.where(r > 0),
        "change_talk_ratio": talk.get("change", 0) / (talk.get("change", 0) + talk.get("sustain", 0)).where(lambda s: s > 0),
        "pct_therapist_input": inp,
        "therapist_word_share": words["therapist"] / (words["therapist"] + words["client"]),
    })
    return m


def auc(m: pd.DataFrame, metric: str) -> float:
    """P(random high-quality transcript scores above a random low-quality one)."""
    hi = m.loc[m["mi_quality"] == "high", metric].dropna().values
    lo = m.loc[m["mi_quality"] == "low", metric].dropna().values
    return float(((hi[:, None] > lo[None, :]).mean() + 0.5 * (hi[:, None] == lo[None, :]).mean()))


def _class_counts(utts: pd.DataFrame) -> dict[tuple[str, str], int]:
    return {(col, val): int((utts[col] == val).sum()) for col, val in CLASSES}


def select_fewshot_pair(exclude: set[int]) -> tuple[int, int]:
    """High/low single-annotator transcripts (20-120 utterances) whose union best covers every label class."""
    g = gold_utterances()
    multi = set(multi_annotator_ids())
    sizes = g.groupby("transcript_id").agg(q=("mi_quality", "first"), n=("utterance_id", "count"))
    pool = sizes[(sizes["n"].between(20, 120)) & (~sizes.index.isin(multi | exclude))]
    counts = {tid: _class_counts(g[g["transcript_id"] == tid]) for tid in pool.index}

    def score(h: int, lo: int):
        total = {c: counts[h][c] + counts[lo][c] for c in CLASSES}
        return (sum(v >= FEWSHOT_PER_CLASS for v in total.values()), sum(v >= 1 for v in total.values()),
                sum(min(v, 4) for v in total.values()), -(pool.loc[h, "n"] + pool.loc[lo, "n"]))

    highs = pool.index[pool["q"] == "high"]
    lows = pool.index[pool["q"] == "low"]
    return max(itertools.product(highs, lows), key=lambda p: score(*p))


def _labels(row) -> dict:
    if row.interlocutor == "client":
        return {"client_talk_type": row.client_talk_type}
    return {
        "main_therapist_behaviour": row.main_therapist_behaviour,
        "reflection": row.reflection_subtype if row.reflection_exists == "True" else "none",
        "question": row.question_subtype if row.question_exists == "True" else "none",
        "therapist_input": row.therapist_input_subtype if row.therapist_input_exists == "True" else "none",
    }


def _context(text: str, max_words: int = 40) -> str:
    words = text.split()
    return text if len(words) <= max_words else "... " + " ".join(words[-max_words:])


def build_fewshot(pair: tuple[int, int]) -> dict:
    """Greedy pick of short, clear turns until each label class has FEWSHOT_PER_CLASS examples."""
    g = gold_utterances()
    utts = g[g["transcript_id"].isin(pair)].sort_values(["transcript_id", "utterance_id"]).reset_index(drop=True)
    candidates = utts[utts["words"].between(4, 45)].copy()
    candidates["clarity"] = (candidates["words"] - 18).abs()
    # Prefer unambiguous turns: at most one behaviour flag, and it matches the main behaviour
    flags = candidates[["reflection_exists", "question_exists", "therapist_input_exists"]].eq("True")
    main_matches = (
        (flags.sum(axis=1) == 0) & candidates["main_therapist_behaviour"].isin(["other", "n/a"])
        | flags["reflection_exists"] & (candidates["main_therapist_behaviour"] == "reflection")
        | flags["question_exists"] & (candidates["main_therapist_behaviour"] == "question")
        | flags["therapist_input_exists"] & (candidates["main_therapist_behaviour"] == "therapist_input")
    )
    candidates["ambiguous"] = ~((flags.sum(axis=1) <= 1) & main_matches)
    covered = dict.fromkeys(CLASSES, 0)
    chosen: list[int] = []
    rarest_first = sorted(CLASSES, key=lambda c: (candidates[c[0]] == c[1]).sum())
    for col, val in rarest_first:
        pool = candidates[(candidates[col] == val) & (~candidates.index.isin(chosen))].sort_values(["ambiguous", "clarity"])
        for idx in pool.index[: max(0, FEWSHOT_PER_CLASS - covered[(col, val)])]:
            chosen.append(idx)
            for c in CLASSES:
                covered[c] += int(candidates.loc[idx, c[0]] == c[1])

    examples = []
    for idx in sorted(chosen):
        row = utts.loc[idx]
        prev = utts.loc[idx - 1] if idx > 0 and utts.loc[idx - 1, "transcript_id"] == row["transcript_id"] else None
        examples.append({
            "transcript_id": int(row["transcript_id"]),
            "topic": row["topic"],
            "context": None if prev is None else {"role": prev["interlocutor"], "text": _context(prev["utterance_text"])},
            "turn": {"role": row["interlocutor"], "text": row["utterance_text"], "labels": _labels(row)},
        })
    words = sum(len(e["turn"]["text"].split()) + len((e["context"] or {"text": ""})["text"].split()) for e in examples)
    return {
        "source_transcripts": [int(t) for t in pair],
        "class_counts": {f"{c}={v}": n for (c, v), n in covered.items()},
        "approx_tokens": round(words * 1.35 + 30 * len(examples)),
        "examples": examples,
    }


def build_anchors(pair: tuple[int, int], metrics: pd.DataFrame) -> list[dict]:
    """One representative excerpt per quality level for supervisor calibration."""
    g = gold_utterances()
    anchors = []
    for tid in pair:
        utts = g[g["transcript_id"] == tid].sort_values("utterance_id").reset_index(drop=True)
        quality = utts["mi_quality"].iloc[0]
        if quality == "high":
            signal = (utts["reflection_exists"] == "True").astype(int) + (utts["reflection_subtype"] == "complex") + (utts["client_talk_type"] == "change")
        else:
            signal = (utts["main_therapist_behaviour"] == "therapist_input").astype(int) + (utts["client_talk_type"] == "sustain") + (utts["question_subtype"] == "closed")
        window = min(ANCHOR_TURNS, len(utts))
        sums = signal.rolling(window).sum().shift(-(window - 1)).fillna(-1)
        start = int(sums.idxmax())
        excerpt = utts.iloc[start:start + window]
        row = metrics.loc[tid]
        anchors.append({
            "transcript_id": int(tid),
            "mi_quality": quality,
            "topic": utts["topic"].iloc[0],
            "transcript_metrics": {k: (None if pd.isna(row[k]) else round(float(row[k]), 3)) for k in metrics.columns if k != "mi_quality"},
            "turns": [{"role": r.interlocutor, "text": r.utterance_text, "labels": _labels(r)} for r in excerpt.itertuples()],
        })
    return anchors


def build_eval_split(exclude: set[int], n_high: int, n_low: int, seed: int) -> dict:
    g = gold_utterances()
    multi = multi_annotator_ids()
    quality = g.groupby("transcript_id")["mi_quality"].first()
    pool = quality[~quality.index.isin(set(multi) | exclude)]
    rng = random.Random(seed)
    sample = sorted(rng.sample(sorted(pool[pool == "high"].index), n_high) + rng.sample(sorted(pool[pool == "low"].index), n_low))
    return {
        "seed": seed,
        "sample": [int(t) for t in sample],
        "multi_annotator": multi,
        "excluded_fewshot": sorted(int(t) for t in exclude),
    }


def build_benchmarks(metrics: pd.DataFrame) -> dict:
    out = {"n_transcripts": metrics["mi_quality"].value_counts().to_dict(), "metrics": {}}
    for col in metrics.columns.drop("mi_quality"):
        stats = {}
        for q in ("high", "low"):
            s = metrics.loc[metrics["mi_quality"] == q, col].dropna()
            stats[q] = {"median": round(float(s.median()), 3), "q1": round(float(s.quantile(0.25)), 3), "q3": round(float(s.quantile(0.75)), 3)}
        stats["auc_high_vs_low"] = round(auc(metrics, col), 3)
        out["metrics"][col] = stats
    return out


def build_assets(n_high: int = 12, n_low: int = 8, seed: int = 42) -> None:
    reserved = set(get_settings().reserved_annomi_ids)
    metrics = gold_metrics()
    pair = select_fewshot_pair(exclude=reserved)
    fewshot = build_fewshot(pair)
    anchors = build_anchors(pair, metrics)
    split = build_eval_split(exclude=set(pair), n_high=n_high, n_low=n_low, seed=seed)
    split["reserved_gold_videos"] = sorted(reserved)
    benchmarks = build_benchmarks(metrics)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for name, payload in [("fewshot_coder", fewshot), ("supervisor_anchors", anchors), ("eval_split", split), ("benchmarks", benchmarks)]:
        (ASSETS_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    sizes = gold_utterances().groupby("transcript_id").agg(q=("mi_quality", "first"), n=("utterance_id", "count"), topic=("topic", "first"))
    print("Few-shot pair:")
    for tid in pair:
        print(f"  {tid}: {sizes.loc[tid, 'q']}, {sizes.loc[tid, 'n']} utterances, topic={sizes.loc[tid, 'topic']}")
    print(f"Few-shot examples: {len(fewshot['examples'])}, approx tokens: {fewshot['approx_tokens']}")
    print("Class coverage:", ", ".join(f"{k.split('=')[1]}={v}" for k, v in fewshot["class_counts"].items()))
    print(f"Anchors: " + ", ".join(f"{a['transcript_id']} ({a['mi_quality']}, {len(a['turns'])} turns)" for a in anchors))
    print(f"Eval sample: {len(split['sample'])} ({n_high} high / {n_low} low) + multi-annotator {split['multi_annotator']}")
    overlap = set(pair) & (set(split["sample"]) | set(split["multi_annotator"]))
    print(f"Leakage check (few-shot vs eval overlap): {sorted(overlap) or 'none'}; reserved {sorted(reserved)} in few-shot: {bool(reserved & set(pair))}")
    print("Gold benchmarks (median high | low | AUC):")
    for k, v in benchmarks["metrics"].items():
        print(f"  {k:<24} {v['high']['median']:>6} | {v['low']['median']:>6} | {v['auc_high_vs_low']}")
