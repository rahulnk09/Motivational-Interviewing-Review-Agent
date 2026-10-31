"""LangGraph pipeline: transcribe -> code -> metrics -> supervise -> assemble, with streamed progress events."""

import hashlib
import operator
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from .coder import CoderResult, code_transcript, labels_from_codes
from .config import REPORTS_DIR, get_settings
from .ingest import file_hash, transcribe
from .metrics import RubricResult, score
from .report import Report, build_report, summarize_usage
from .schemas import CUUsage, LLMUsage, Transcript
from .supervisor import CitationCheck, SupervisorOutput, supervise
from .transcript import transcript_from_ingest

STAGES = {
    "transcribe": "Transcribing and separating speakers (Content Understanding)",
    "code": "Coding every turn (Coder agent)",
    "metrics": "Computing MI metrics",
    "supervise": "Rating empathy and collaboration, finding strengths and traps (Supervisor agent)",
    "assemble": "Assembling the report",
}


def _merge(a: dict, b: dict) -> dict:
    return {**a, **b}


class PipelineState(TypedDict, total=False):
    media_path: str | None
    start_s: float
    end_s: float | None
    session_id: str
    transcript: Transcript
    cu_usage: CUUsage | None
    coded: CoderResult
    rubric: RubricResult
    supervision: SupervisorOutput
    supervisor_usage: LLMUsage
    citations: CitationCheck
    report: Report
    warnings: Annotated[list[str], operator.add]
    stage_seconds: Annotated[dict[str, float], _merge]


def _stage(name: str):
    """Wrap a node: emit start/done progress events and record its duration."""
    def decorator(fn: Callable[[PipelineState], dict]):
        def node(state: PipelineState) -> dict:
            write = get_stream_writer()
            write({"stage": name, "status": "start", "message": STAGES[name]})
            started = time.perf_counter()
            update = fn(state)
            seconds = round(time.perf_counter() - started, 2)
            write({"stage": name, "status": "done", "message": update.pop("_message", ""), "seconds": seconds})
            return update | {"stage_seconds": {name: seconds}}
        node.__name__ = name
        return node
    return decorator


@_stage("transcribe")
def transcribe_node(state: PipelineState) -> dict:
    media = Path(state["media_path"])
    ingest = transcribe(media, state.get("start_s", 0), state.get("end_s"))
    transcript = transcript_from_ingest(ingest, source=media.name)
    cached = " (cached)" if ingest.usage.from_cache else ""
    return {
        "transcript": transcript,
        "cu_usage": ingest.usage,
        "warnings": transcript.warnings,
        "_message": f"{len(transcript.turns)} turns, {len(transcript.speaker_roles)} speakers, target: {transcript.target_behavior}{cached}",
    }


@_stage("code")
def code_node(state: PipelineState) -> dict:
    coded = code_transcript(state["transcript"])
    return {"coded": coded, "warnings": coded.warnings, "_message": f"{len(coded.therapist)} therapist and {len(coded.client)} client turns coded"}


@_stage("metrics")
def metrics_node(state: PipelineState) -> dict:
    rubric = score(labels_from_codes(state["transcript"].turns, state["coded"]))
    m = {x.key: x.display for x in rubric.metrics}
    return {"rubric": rubric, "_message": f"R:Q {m['reflection_to_question']}, open Q {m['pct_open_questions']}, complex R {m['pct_complex_reflections']}"}


@_stage("supervise")
def supervise_node(state: PipelineState) -> dict:
    out, usage, check, warnings = supervise(state["transcript"], state["coded"], state["rubric"])
    return {
        "supervision": out, "supervisor_usage": usage, "citations": check, "warnings": warnings,
        "_message": f"empathy {out.empathy.score}, collaboration {out.collaboration.score}, "
                    f"{len(out.strengths)} strengths, {len(out.improvements)} improvements",
    }


@_stage("assemble")
def assemble_node(state: PipelineState) -> dict:
    s = get_settings()
    sup = state["supervision"]
    labels = labels_from_codes(state["transcript"].turns, state["coded"])
    rubric = score(labels, empathy=sup.empathy.score, collaboration=sup.collaboration.score)
    usage = summarize_usage(state.get("cu_usage"), state["coded"].usage + [state["supervisor_usage"]], state.get("stage_seconds", {}))
    start_s, end_s = state.get("start_s", 0), state.get("end_s")
    report = build_report(
        session_id=state["session_id"], transcript=state["transcript"], coded=state["coded"], rubric=rubric, supervision=sup,
        models={"coder": f"{s.coder_deployment}/{s.coder_effort}", "supervisor": f"{s.supervisor_deployment}/{s.supervisor_effort}",
                "cu_analyzer": s.cu_analyzer_id if state.get("media_path") else "n/a (text input)"},
        usage=usage, warnings=state.get("warnings", []),
        clip_start_ms=int(start_s * 1000), clip_end_ms=None if end_s is None else int(end_s * 1000),
    )
    return {"report": report, "_message": f"{rubric.proficiency_points}/12 ({rubric.proficiency_band})"}


def _entry(state: PipelineState) -> str:
    return "code" if state.get("transcript") is not None else "transcribe"


def build_graph():
    g = StateGraph(PipelineState)
    for node in (transcribe_node, code_node, metrics_node, supervise_node, assemble_node):
        g.add_node(node.__name__, node)
    g.add_conditional_edges(START, _entry, ["transcribe", "code"])
    g.add_edge("transcribe", "code")
    g.add_edge("code", "metrics")
    g.add_edge("metrics", "supervise")
    g.add_edge("supervise", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


GRAPH = build_graph()


def session_id_for(media_path: str | Path | None = None, start_s: float = 0, end_s: float | None = None, transcript: Transcript | None = None) -> str:
    if media_path is not None:
        return f"{Path(media_path).stem[:40].replace(' ', '_')}-{file_hash(Path(media_path))[:8]}-{int(start_s)}-{'end' if end_s is None else int(end_s)}"
    return transcript.source.replace(":", "-") if transcript else hashlib.sha256(str(time.time()).encode()).hexdigest()[:10]


def run_pipeline(
    media_path: str | Path | None = None,
    start_s: float = 0,
    end_s: float | None = None,
    transcript: Transcript | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    save: bool = True,
) -> Report:
    """Run the graph from a media file (CU) or a ready transcript (skips CU). Progress events go to on_event."""
    started = time.perf_counter()
    state: PipelineState = {
        "media_path": None if media_path is None else str(media_path),
        "start_s": start_s,
        "end_s": end_s,
        "session_id": session_id_for(media_path, start_s, end_s, transcript),
        "warnings": [],
        "stage_seconds": {},
    }
    if transcript is not None:
        state["transcript"] = transcript
    report: Report | None = None
    stage_seconds: dict[str, float] = {}
    for chunk in GRAPH.stream(state, stream_mode=["updates", "custom"], version="v2"):
        if chunk["type"] == "custom" and on_event:
            on_event(chunk["data"])
        elif chunk["type"] == "updates":
            for node, update in chunk["data"].items():
                stage_seconds |= update.get("stage_seconds", {})
                if node == "assemble":
                    report = update["report"]
    report.usage.stage_seconds = stage_seconds
    report.usage.total_seconds = round(time.perf_counter() - started, 2)
    if save:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / f"{report.session_id}.json").write_text(report.model_dump_json(indent=1), encoding="utf-8")
    return report
