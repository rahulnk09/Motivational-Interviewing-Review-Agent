"""Command-line entry point: python -m mi_review.cli <command>."""

import argparse
import sys
import time
from pathlib import Path

from pydantic import BaseModel

from .config import get_settings


class _Ping(BaseModel):
    ok: bool
    echo: str


def _check(label: str, fn) -> bool:
    start = time.perf_counter()
    try:
        detail = fn()
        print(f"  OK   {label} ({time.perf_counter() - start:.1f}s){f' - {detail}' if detail else ''}")
        return True
    except Exception as exc:  # noqa: BLE001 - doctor reports every failure
        print(f"  FAIL {label}: {type(exc).__name__}: {str(exc).splitlines()[0][:300]}")
        return False


def cmd_doctor(_args) -> int:
    from .clients import COGNITIVE_SCOPE, credential, cu_client
    from .llm import structured_call

    s = get_settings()
    print("Settings:")
    print(f"  CU analyzer={s.cu_analyzer_id} base={s.cu_base_analyzer} completion_model={s.cu_completion_model} locales={s.cu_locales}")
    print(f"  coder={s.coder_deployment}/{s.coder_effort} supervisor={s.supervisor_deployment}/{s.supervisor_effort}")
    print(f"  relax_x509_strict={s.relax_x509_strict} reserved_annomi_ids={s.reserved_annomi_ids}")
    if s.missing():
        print(f"  FAIL missing env vars: {', '.join(s.missing())}")
        return 1

    def cu_defaults():
        mapping = cu_client().get_defaults().model_deployments or {}
        if s.cu_completion_model not in mapping:
            raise RuntimeError(f"{s.cu_completion_model} not mapped in CU defaults: {mapping}")
        return f"{s.cu_completion_model} -> {mapping[s.cu_completion_model]}"

    def custom_analyzer():
        try:
            return f"{s.cu_analyzer_id} base={cu_client().get_analyzer(s.cu_analyzer_id).base_analyzer_id}"
        except Exception:  # noqa: BLE001
            return f"{s.cu_analyzer_id} not created yet (run setup-analyzer)"

    def ping(model: str, effort: str):
        def _run():
            out, usage = structured_call(
                step="doctor", model=model, instructions="Return the requested JSON.",
                input="Set ok=true and echo='pong'.", schema=_Ping, effort=effort,
            )
            assert out.ok and out.echo == "pong", out
            return f"in={usage.input_tokens} out={usage.output_tokens} reasoning={usage.reasoning_tokens}"
        return _run

    print("Checks:")
    results = [
        _check("Entra ID token (az login)", lambda: credential().get_token(COGNITIVE_SCOPE) and None),
        _check("CU prebuilt-audio analyzer", lambda: cu_client().get_analyzer("prebuilt-audio").analyzer_id),
        _check("CU model deployment defaults", cu_defaults),
        _check("CU custom analyzer", custom_analyzer),
        _check(f"Structured output: {s.coder_deployment}", ping(s.coder_deployment, s.coder_effort)),
        _check(f"Structured output: {s.supervisor_deployment}", ping(s.supervisor_deployment, s.supervisor_effort)),
    ]
    return 0 if all(results) else 1


def cmd_setup_analyzer(args) -> int:
    from .ingest import ensure_analyzer

    status = ensure_analyzer(replace=args.replace)
    print(f"Analyzer {get_settings().cu_analyzer_id}: {status}")
    return 0


def cmd_transcribe(args) -> int:
    from .ingest import transcribe
    from .transcript import speaker_stats, transcript_from_ingest

    ingest = transcribe(args.media, args.start, args.end, use_cache=not args.no_cache)
    transcript = transcript_from_ingest(ingest, source=str(args.media))
    u = ingest.usage
    print(f"CU: method={ingest.method} cached={u.from_cache} seconds={u.seconds} audio_hours={u.audio_hours} tokens={u.tokens}")
    print(f"Clip: {ingest.clip_start_ms}-{ingest.clip_end_ms} ms (analyzed {ingest.duration_ms} ms) | phrases={len(ingest.phrases)} | cache={ingest.cache_path.name}")
    print(f"Fields: {ingest.fields}")
    print(f"Speaker stats: {speaker_stats(ingest.phrases)}")
    print(f"Roles: {transcript.speaker_roles}")
    for w in transcript.warnings:
        print(f"WARNING: {w}")
    starts = [t.start_ms for t in transcript.turns]
    print(f"Turns: {len(transcript.turns)} | first at {transcript.turns[0].timestamp if transcript.turns else '-'} | "
          f"monotonic={all(a <= b for a, b in zip(starts, starts[1:]))}")
    for t in transcript.turns[: args.show]:
        print(f"  [{t.turn_id:>3}] {t.timestamp} {t.role[:3].upper()} ({t.speaker}): {t.text[:160]}")
    return 0


def _load_transcript(args):
    if args.annomi is not None:
        from .annomi import load_transcript

        return load_transcript(args.annomi)
    from .ingest import transcribe
    from .transcript import transcript_from_ingest

    return transcript_from_ingest(transcribe(args.media, args.start, args.end), source=str(args.media))


def cmd_code(args) -> int:
    from .coder import code_transcript, labels_from_codes
    from .metrics import score

    transcript = _load_transcript(args)
    result = code_transcript(transcript, model=args.model, effort=args.effort)
    for t in transcript.turns:
        if t.role == "therapist":
            c = result.therapist[t.turn_id]
            tag = f"{c.main_behaviour}|R={c.reflection}|Q={c.question}|I={c.therapist_input}|{c.mi_behaviour}|{c.adherence}"
        else:
            c = result.client[t.turn_id]
            tag = c.talk_type
        gold = ""
        if t.gold:
            g = t.gold
            gold = f"  [gold: {g.client_talk_type if t.role == 'client' else f'{g.main_therapist_behaviour}|R={g.reflection_subtype}|Q={g.question_subtype}|I={g.therapist_input_subtype}'}]"
        print(f"[T{t.turn_id:>3}] {t.timestamp} {t.role[:3].upper()} <{tag}>{gold} {t.text[:args.width]}")
        print(f"        why: {c.rationale}")
    for w in result.warnings:
        print(f"WARNING: {w}")
    for u in result.usage:
        print(f"Usage {u.step}: {u.model} {u.seconds}s in={u.input_tokens} cached={u.cached_tokens} out={u.output_tokens} reasoning={u.reasoning_tokens}")
    rubric = score(labels_from_codes(transcript.turns, result))
    print(f"Counts: {rubric.counts.model_dump()}")
    for m in rubric.metrics:
        print(f"  {m.label:<30} {m.display:>6}  {m.level}")
    print(f"  Change talk ratio: {rubric.change_talk_ratio}")
    return 0


def cmd_eval_coder(args) -> int:
    from .evals.eval_coder import run

    run(ids=args.ids, include_multi=not args.no_multi, model=args.model, effort=args.effort, workers=args.workers)
    return 0


def print_report(report) -> None:
    r = report.rubric
    print(f"\n=== {report.session_id} | target: {report.target_behavior} ===")
    print(f"MI proficiency: {r.proficiency_points}/12 ({r.proficiency_band}) | change talk ratio: "
          f"{'n/a' if r.change_talk_ratio is None else f'{r.change_talk_ratio:.0%}'}")
    for m in r.metrics:
        print(f"  {m.label:<30} {m.display:>6}  {m.level:<18} +{m.points}")
    for name, g in (("Empathy", report.empathy), ("Collaboration", report.collaboration)):
        print(f"{name} {g.score}: {g.justification} [{', '.join(e.timestamp for e in g.evidence)}]")
    print("\nWhat went well:")
    for f in report.what_went_well:
        print(f"  [{f.evidence[0].timestamp}] {f.title} ({f.category}): {f.insight}")
    print("What to improve:")
    for f in report.what_to_improve:
        print(f"  [{f.evidence[0].timestamp}] {f.title} ({f.category}): {f.insight}\n      -> try: {f.better_response}")
    print(f"\nSummary: {report.overall_summary}")
    print("Tips: " + " | ".join(report.coaching_tips))
    for w in report.warnings:
        print(f"WARNING: {w}")
    u = report.usage
    print(f"\nUsage: LLM in={u.input_tokens} (cached {u.cached_tokens}) out={u.output_tokens} (reasoning {u.reasoning_tokens}) "
          f"llm_seconds={u.llm_seconds} | CU={u.cu.seconds if u.cu else '-'}s audio_hours={u.cu.audio_hours if u.cu else '-'} "
          f"| stages={u.stage_seconds} total={u.total_seconds}s")


def cmd_run(args) -> int:
    from .config import REPORTS_DIR
    from .graph import run_pipeline

    def on_event(e: dict) -> None:
        if e["status"] == "start":
            print(f"> {e['message']} ...", flush=True)
        else:
            print(f"  done in {e['seconds']}s: {e['message']}", flush=True)

    if args.annomi is not None:
        from .annomi import load_transcript

        report = run_pipeline(transcript=load_transcript(args.annomi), on_event=on_event)
    else:
        report = run_pipeline(args.media, args.start, args.end, on_event=on_event)
    print_report(report)
    print(f"Saved {REPORTS_DIR / (report.session_id + '.json')}")
    return 0


def cmd_eval_supervisor(args) -> int:
    from .evals.eval_supervisor import run

    run(ids=args.ids, model=args.model, effort=args.effort, repeat=args.repeat, workers=args.workers)
    return 0


def cmd_eval_ingest(args) -> int:
    from .evals.eval_ingest import run

    run(args.media, args.annomi, args.start, args.end, reuse=not args.fresh)
    return 0


def cmd_build_assets(args) -> int:
    from .annomi import build_assets

    build_assets(n_high=args.n_high, n_low=args.n_low, seed=args.seed)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mi-review")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check env, Azure auth, CU and model deployments").set_defaults(fn=cmd_doctor)

    p = sub.add_parser("setup-analyzer", help="create the Content Understanding custom analyzer")
    p.add_argument("--replace", action="store_true", help="recreate even if it exists")
    p.set_defaults(fn=cmd_setup_analyzer)

    p = sub.add_parser("transcribe", help="run CU on a media file and print turns")
    p.add_argument("media")
    p.add_argument("--start", type=float, default=0, help="seconds to skip at the start")
    p.add_argument("--end", type=float, default=None, help="stop at this second")
    p.add_argument("--show", type=int, default=15)
    p.add_argument("--no-cache", action="store_true")
    p.set_defaults(fn=cmd_transcribe)

    p = sub.add_parser("build-assets", help="build few-shot, anchors, eval split and benchmarks from AnnoMI")
    p.add_argument("--n-high", type=int, default=12)
    p.add_argument("--n-low", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(fn=cmd_build_assets)

    p = sub.add_parser("code", help="run the Coder agent on an AnnoMI transcript or a media file")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--annomi", type=int, help="AnnoMI transcript id (gold roles and labels)")
    src.add_argument("--media", help="audio/video file (uses CU cache)")
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--effort", default=None)
    p.add_argument("--width", type=int, default=110)
    p.set_defaults(fn=cmd_code)

    p = sub.add_parser("eval-coder", help="evaluate the Coder agent against AnnoMI gold labels")
    p.add_argument("--ids", type=int, nargs="+", default=None, help="transcript ids (default: eval split)")
    p.add_argument("--no-multi", action="store_true", help="exclude the multi-annotator transcripts")
    p.add_argument("--model", default=None)
    p.add_argument("--effort", default=None)
    p.add_argument("--workers", type=int, default=6)
    p.set_defaults(fn=cmd_eval_coder)

    p = sub.add_parser("run", help="full LangGraph pipeline (CU -> Coder -> metrics -> Supervisor -> report JSON)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--annomi", type=int, help="AnnoMI transcript id (skips CU)")
    src.add_argument("--media")
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=None)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("eval-supervisor", help="evaluate global ratings / proficiency score on AnnoMI high vs low sessions")
    p.add_argument("--ids", type=int, nargs="+", default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--effort", default=None)
    p.add_argument("--repeat", type=int, default=3, help="transcripts re-run to measure stability")
    p.add_argument("--workers", type=int, default=6)
    p.set_defaults(fn=cmd_eval_supervisor)

    p = sub.add_parser("eval-ingest", help="audio pipeline vs the AnnoMI expert transcript of the same video")
    p.add_argument("--media", default="mi_project/data/annomi_video_27.mp4")
    p.add_argument("--annomi", type=int, default=27)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--fresh", action="store_true", help="re-run the pipeline instead of reusing the saved report")
    p.set_defaults(fn=cmd_eval_ingest)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
