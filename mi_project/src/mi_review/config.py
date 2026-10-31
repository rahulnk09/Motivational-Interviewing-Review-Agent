"""Paths and environment-driven settings."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parents[1]
REPO_ROOT = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"
CU_CACHE_DIR = OUTPUT_DIR / "cu"
REPORTS_DIR = OUTPUT_DIR / "reports"
EVAL_DIR = OUTPUT_DIR / "eval"
ASSETS_DIR = PACKAGE_DIR / "assets"
PROMPTS_DIR = PACKAGE_DIR / "prompts"
ANNOMI_DIR = REPO_ROOT / "AnnoMI"
ANNOMI_FULL_CSV = ANNOMI_DIR / "AnnoMI-full.csv"

load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _ids(raw: str | None) -> tuple[int, ...]:
    return tuple(int(x) for x in (raw or "").split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    cu_endpoint: str | None
    aoai_endpoint: str | None
    cu_analyzer_id: str
    cu_base_analyzer: str
    cu_completion_model: str
    cu_locales: tuple[str, ...]
    coder_deployment: str
    coder_effort: str
    supervisor_deployment: str
    supervisor_effort: str
    relax_x509_strict: bool
    reserved_annomi_ids: tuple[int, ...]

    def missing(self) -> list[str]:
        required = {"CONTENTUNDERSTANDING_ENDPOINT": self.cu_endpoint, "AZURE_OPENAI_ENDPOINT": self.aoai_endpoint}
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        cu_endpoint=_env("CONTENTUNDERSTANDING_ENDPOINT"),
        aoai_endpoint=_env("AZURE_OPENAI_ENDPOINT"),
        cu_analyzer_id=_env("MI_CU_ANALYZER_ID", "miSessionAudio"),
        cu_base_analyzer=_env("MI_CU_BASE_ANALYZER", "prebuilt-audio"),
        cu_completion_model=_env("CU_COMPLETION_MODEL", "gpt-5.4-mini"),
        cu_locales=tuple(_env("MI_CU_LOCALES", "en-US").split(",")),
        # eval-coder: gpt-5.4/low beat gpt-5.4-mini/low on therapist codes (kappa 0.86 vs 0.76)
        coder_deployment=_env("MI_CODER_DEPLOYMENT") or _env("AZURE_OPENAI_PREMIUM_DEPLOYMENT", "gpt-5.4"),
        coder_effort=_env("MI_CODER_EFFORT", "low"),
        supervisor_deployment=_env("MI_SUPERVISOR_DEPLOYMENT") or _env("AZURE_OPENAI_PREMIUM_DEPLOYMENT", "gpt-5.4"),
        supervisor_effort=_env("MI_SUPERVISOR_EFFORT", "medium"),
        relax_x509_strict=_env("MI_RELAX_X509_STRICT", "0") == "1",
        # AnnoMI transcripts whose videos are used for end-to-end tests; never used as few-shot examples
        reserved_annomi_ids=_ids(_env("MI_RESERVED_ANNOMI_IDS", "27")),
    )
