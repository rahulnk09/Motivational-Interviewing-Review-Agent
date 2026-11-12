"""Rendering helpers for the MIRA (MI Review App) Streamlit app."""

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from mi_review.config import ASSETS_DIR, DATA_DIR
from mi_review.report import FeedbackItem, Report
from mi_review.schemas import format_ms

ROLE_NAME = {"therapist": "Clinician", "client": "Client"}
LEVEL_BADGE = {"advanced": "green", "basic": "blue", "below": "red", "insufficient_data": "gray", "pending": "gray"}
BAND_BADGE = {"Advanced proficiency": "green", "Basic proficiency": "blue", "Developing": "orange"}
TALK_COLORS = {"change": "#16a34a", "neutral": "#94a3b8", "sustain": "#dc2626"}
BEHAVIOUR_COLORS = {"reflection": "#0d9488", "question": "#2563eb", "therapist_input": "#d97706", "other": "#94a3b8"}
MEDIA_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".m4a", ".mp3", ".wav"}
UPLOAD_DIR = DATA_DIR / "uploads"


def humanize(value: str) -> str:
    return value.replace("_", " ").capitalize()


@st.cache_data
def benchmarks() -> dict:
    return json.loads((ASSETS_DIR / "benchmarks.json").read_text(encoding="utf-8"))["metrics"]


def find_media(name: str | None) -> Path | None:
    if not name:
        return None
    for folder in (DATA_DIR, UPLOAD_DIR):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def subtitles(report: Report) -> str:
    """WebVTT track: one cue per turn, labelled with the speaker role."""
    def ts(ms: int) -> str:
        h, rem = divmod(ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    cues = ["WEBVTT", ""]
    turns = report.transcript
    for i, t in enumerate(turns):
        end = t.end_ms or (turns[i + 1].start_ms if i + 1 < len(turns) else t.start_ms + 5000)
        cues += [f"{ts(t.start_ms)} --> {ts(max(end, t.start_ms + 1000))}", f"{ROLE_NAME[t.role]}: {t.text}", ""]
    return "\n".join(cues)


def seek_button(start_ms: int, key: str, label: str | None = None) -> None:
    def _seek():
        st.session_state.seek_s = max(0, start_ms // 1000 - 1)

    st.button(label or format_ms(start_ms), icon=":material/play_arrow:", key=key, on_click=_seek, type="tertiary")


def metric_cards(report: Report) -> None:
    bench = benchmarks()
    metrics = report.rubric.metrics
    for row in range(0, len(metrics), 3):
        for col, m in zip(st.columns(3), metrics[row:row + 3]):
            with col.container(border=True, height="stretch"):
                _metric_card(m, bench)


def _metric_card(m, bench: dict) -> None:
    st.markdown(f"**{m.label}**")
    st.markdown(f"### {m.display}")
    with st.container(horizontal=True):
        st.badge(humanize(m.level), color=LEVEL_BADGE[m.level])
        st.badge(f"+{m.points} pts", color="gray")
    fmt = (lambda v: f"{v:.0%}") if m.key.startswith("pct_") else (lambda v: f"{v:g}")
    st.caption(f"Basic {m.comparison} {fmt(m.basic)} · Advanced {m.comparison} {fmt(m.advanced)}")
    if m.key in bench:
        b = bench[m.key]
        st.caption(f"AnnoMI medians: high-quality {fmt(b['high']['median'])} · low-quality {fmt(b['low']['median'])}")
    if m.note:
        st.caption(m.note)


def feedback_card(item: FeedbackItem, key: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{item.title}**")
        st.badge(humanize(item.category), color="green" if item.kind == "strength" else "orange")
        st.write(item.insight)
        for j, ev in enumerate(item.evidence):
            with st.container(horizontal=True, vertical_alignment="center"):
                seek_button(ev.start_ms, key=f"{key}-ev{j}")
                st.caption(f"{ROLE_NAME[ev.role]}: “{ev.quote[:220]}{'…' if len(ev.quote) > 220 else ''}”")
        if item.better_response:
            st.success(item.better_response, title="Try instead", icon=":material/lightbulb:")


def turn_tags(turn) -> list[tuple[str, str]]:
    if turn.client_code:
        return [(humanize(turn.client_code.talk_type) + " talk", {"change": "green", "sustain": "red"}.get(turn.client_code.talk_type, "gray"))]
    c = turn.therapist_code
    tags = []
    if c.reflection != "none":
        tags.append((f"{humanize(c.reflection)} reflection", "violet"))
    if c.question != "none":
        tags.append((f"{humanize(c.question)} question", "blue"))
    if c.therapist_input != "none":
        tags.append((f"Input: {c.therapist_input}", "orange"))
    if c.mi_behaviour != "none":
        tags.append((humanize(c.mi_behaviour), "primary"))
    if c.adherence == "non_adherent":
        tags.append(("MI non-adherent", "red"))
    return tags or [("Other", "gray")]


def dynamics_chart(report: Report) -> alt.Chart:
    rows = []
    for t in report.transcript:
        label = t.client_code.talk_type if t.client_code else t.therapist_code.main_behaviour
        rows.append({"minute": t.start_ms / 60000, "time": t.timestamp, "speaker": ROLE_NAME[t.role], "label": label, "text": t.text[:120]})
    df = pd.DataFrame(rows)
    domain = list(BEHAVIOUR_COLORS) + list(TALK_COLORS)
    colors = list(BEHAVIOUR_COLORS.values()) + list(TALK_COLORS.values())
    return (
        alt.Chart(df)
        .mark_circle(size=180, opacity=0.9)
        .encode(
            x=alt.X("minute:Q", title="Minute"),
            y=alt.Y("speaker:N", title=None, sort=["Clinician", "Client"]),
            color=alt.Color("label:N", scale=alt.Scale(domain=domain, range=colors), title="Code"),
            tooltip=["time", "speaker", "label", "text"],
        )
        .properties(height=180)
    )


def talk_trend_chart(report: Report) -> alt.Chart | None:
    rows, change, sustain = [], 0, 0
    for t in report.transcript:
        if t.client_code:
            change += t.client_code.talk_type == "change"
            sustain += t.client_code.talk_type == "sustain"
            rows += [{"minute": t.start_ms / 60000, "talk": "Change talk", "cumulative": change},
                     {"minute": t.start_ms / 60000, "talk": "Sustain talk", "cumulative": sustain}]
    if not rows:
        return None
    return (
        alt.Chart(pd.DataFrame(rows))
        .mark_line(point=True, interpolate="step-after")
        .encode(
            x=alt.X("minute:Q", title="Minute"),
            y=alt.Y("cumulative:Q", title="Cumulative client turns"),
            color=alt.Color("talk:N", scale=alt.Scale(domain=["Change talk", "Sustain talk"], range=[TALK_COLORS["change"], TALK_COLORS["sustain"]]), title=None),
        )
        .properties(height=240)
    )
