"""Content Understanding ingestion: custom audio analyzer -> diarized, timestamped transcript phrases."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from azure.ai.contentunderstanding.models import (
    AnalysisResult,
    AudioVisualContent,
    ContentAnalyzer,
    ContentAnalyzerConfig,
    ContentFieldDefinition,
    ContentFieldSchema,
)
from azure.core.exceptions import ResourceNotFoundError

from .clients import cu_client
from .config import CU_CACHE_DIR, get_settings
from .schemas import CUUsage, Phrase

SPEAKER_LABELS = ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 4"]

FIELD_SCHEMA = ContentFieldSchema(
    name="MISession",
    description="Recorded motivational interviewing (MI) counselling session between a clinician and a client.",
    fields={
        "SessionSummary": ContentFieldDefinition(
            type="string",
            method="generate",
            description="Neutral 2-3 sentence summary of what the clinician and client discussed and where the conversation ended up.",
        ),
        "TargetBehavior": ContentFieldDefinition(
            type="string",
            method="generate",
            description=(
                "The target behaviour change the session is about, phrased as the desired NEW behaviour (the direction of "
                "change), never the current status-quo behaviour. Short phrase, e.g. 'reducing alcohol consumption', "
                "'quitting smoking', 'increasing physical activity', 'taking medication as prescribed'."
            ),
        ),
        "ClinicianSpeaker": ContentFieldDefinition(
            type="string",
            method="classify",
            enum=SPEAKER_LABELS,
            description=(
                "Transcript speaker label of the clinician (counsellor, doctor, nurse, pharmacist): the professional who "
                "guides the conversation by asking questions, reflecting, and offering information. Not the client/patient."
            ),
        ),
    },
)


def analyzer_definition() -> ContentAnalyzer:
    settings = get_settings()
    return ContentAnalyzer(
        base_analyzer_id=settings.cu_base_analyzer,
        description="MIFlow: diarized transcript plus session metadata for motivational interviewing review",
        config=ContentAnalyzerConfig(return_details=True, locales=list(settings.cu_locales)),
        field_schema=FIELD_SCHEMA,
        models={"completion": settings.cu_completion_model},
    )


def ensure_analyzer(replace: bool = False) -> str:
    """Create the custom analyzer if missing (or when replace=True). Returns 'exists' or 'created'."""
    analyzer_id = get_settings().cu_analyzer_id
    if not replace:
        try:
            cu_client().get_analyzer(analyzer_id)
            return "exists"
        except ResourceNotFoundError:
            pass
    cu_client().begin_create_analyzer(
        analyzer_id=analyzer_id, resource=analyzer_definition(), allow_replace=True
    ).result()
    return "created"


@dataclass
class IngestResult:
    phrases: list[Phrase]
    fields: dict
    clip_start_ms: int
    clip_end_ms: int | None
    duration_ms: int
    method: str
    usage: CUUsage
    cache_path: Path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _extract_audio(media_path: Path, start_s: float, end_s: float | None) -> bytes:
    """Cut [start, end) and convert to 16 kHz mono WAV; output times start at 0."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "clip.wav"
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(start_s)]
        if end_s is not None:
            cmd += ["-to", str(end_s)]
        cmd += ["-i", str(media_path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        return out.read_bytes()


def transcribe(media_path: str | Path, start_s: float = 0, end_s: float | None = None, use_cache: bool = True) -> IngestResult:
    """Transcribe [start_s, end_s) of the media. Returned phrase times are absolute (original media time)."""
    media_path = Path(media_path)
    settings = get_settings()
    clip_start_ms = int(start_s * 1000)
    clip_end_ms = None if end_s is None else int(end_s * 1000)
    # CU ignores content_range for binary uploads, so cut locally; video analyzers need the original file
    local_cut = shutil.which("ffmpeg") is not None and settings.cu_base_analyzer == "prebuilt-audio"
    method = "ffmpeg-wav" if local_cut else "full-file"
    tag = f"{clip_start_ms}_{clip_end_ms or 'end'}"
    cache_path = CU_CACHE_DIR / f"{file_hash(media_path)}.{settings.cu_analyzer_id}.{method}.{tag}.json"

    if use_cache and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        usage = CUUsage(**{**cached["usage"], "from_cache": True})
        result = AnalysisResult(cached["result"])
    else:
        payload = _extract_audio(media_path, start_s, end_s) if local_cut else media_path.read_bytes()
        started = time.perf_counter()
        poller = cu_client().begin_analyze_binary(analyzer_id=settings.cu_analyzer_id, binary_input=payload)
        result = poller.result()
        details = poller.usage
        usage = CUUsage(
            analyzer_id=settings.cu_analyzer_id,
            seconds=round(time.perf_counter() - started, 2),
            from_cache=False,
            audio_hours=getattr(details, "audio_hours", None),
            video_hours=getattr(details, "video_hours", None),
            tokens=dict(getattr(details, "tokens", None) or {}),
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"media": media_path.name, "method": method, "clip": tag, "usage": usage.model_dump(), "result": result.as_dict()}, indent=1),
            encoding="utf-8",
        )

    phrases, fields, duration_ms = _parse(result)
    if local_cut:
        phrases = [p.model_copy(update={"start_ms": p.start_ms + clip_start_ms, "end_ms": p.end_ms + clip_start_ms}) for p in phrases]
    else:
        phrases = [p for p in phrases if p.start_ms >= clip_start_ms and (clip_end_ms is None or p.start_ms < clip_end_ms)]
    return IngestResult(phrases, fields, clip_start_ms, clip_end_ms, duration_ms, method, usage, cache_path)


def _to_plain(field):
    if field is None:
        return None
    if field.type == "array":
        return [_to_plain(item) for item in field.value_array or []]
    if field.type == "object":
        return {key: _to_plain(value) for key, value in (field.value_object or {}).items()}
    return field.value


def _parse(result: AnalysisResult) -> tuple[list[Phrase], dict, int]:
    content = result.contents[0]
    if not isinstance(content, AudioVisualContent):
        raise ValueError(f"expected audioVisual content, got {type(content).__name__}")
    phrases = [
        Phrase(
            speaker=p.speaker or "Unknown",
            start_ms=p.start_time_ms,
            end_ms=p.end_time_ms,
            text=p.text.strip(),
            confidence=p.confidence,
        )
        for p in content.transcript_phrases or []
        if p.text and p.text.strip()
    ]
    fields = {name: _to_plain(value) for name, value in (content.fields or {}).items()}
    return phrases, fields, (content.end_time_ms or 0) - (content.start_time_ms or 0)
