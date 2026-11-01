"""MIFlow: Motivational Interviewing session review. Run: uv run streamlit run mi_project/app/streamlit_app.py"""

import hashlib

import pandas as pd
import streamlit as st

import ui
from mi_review.config import DATA_DIR, REPORTS_DIR, get_settings
from mi_review.graph import STAGES, run_pipeline
from mi_review.report import Report

# Known role-play clips inside sample videos (seconds); narrator intro/outro excluded
PRESETS = {
    "Motivational Interviewing in Action_ Role Play - (480p).mp4": (39.0, 223.0),
    "annomi_video_27.mp4": (0.0, None),
}

st.set_page_config(page_title="MIFlow · MI session review", page_icon=":material/psychology:", layout="wide")
st.session_state.setdefault("report", None)
st.session_state.setdefault("media", None)
st.session_state.setdefault("seek_s", None)


@st.cache_data(max_entries=50)
def load_report(path: str, mtime: float) -> Report:
    return Report.model_validate_json(open(path, encoding="utf-8").read())


def saved_reports() -> list:
    return sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if REPORTS_DIR.exists() else []


def save_upload(upload) -> str | None:
    suffix = "." + upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""
    if suffix not in ui.MEDIA_SUFFIXES:
        st.error(f"Unsupported file type {suffix!r}.")
        return None
    data = upload.getvalue()
    ui.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = ui.UPLOAD_DIR / f"{hashlib.sha256(data).hexdigest()[:16]}{suffix}"
    if not path.exists():
        path.write_bytes(data)
    return str(path)


# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Session")
    source = st.segmented_control("Source", ["Sample", "Upload", "Saved report"], default="Sample", key="source")
    media_path = None
    start_default, end_default = 0.0, None

    if source == "Sample":
        samples = sorted(p.name for p in DATA_DIR.glob("*") if p.suffix.lower() in ui.MEDIA_SUFFIXES)
        name = st.selectbox("Recording", samples) if samples else None
        if name:
            media_path = str(DATA_DIR / name)
            start_default, end_default = PRESETS.get(name, (0.0, None))
    elif source == "Upload":
        upload = st.file_uploader("Recording (video or audio)", type=[s.lstrip(".") for s in ui.MEDIA_SUFFIXES])
        if upload is not None:
            media_path = save_upload(upload)

    if source in ("Sample", "Upload"):
        with st.container(horizontal=True):
            start_s = st.number_input("Start (s)", min_value=0.0, value=start_default, step=1.0, key=f"start-{media_path}")
            end_s = st.number_input("End (s, 0 = to the end)", min_value=0.0, value=end_default or 0.0, step=1.0, key=f"end-{media_path}")
        st.caption("Skip intros or outros that are not part of the conversation.")
        analyze = st.button("Analyze session", type="primary", icon=":material/play_circle:", width="stretch", disabled=media_path is None)
    else:
        analyze = False
        reports = saved_reports()
        if reports:
            chosen = st.selectbox("Report", reports, format_func=lambda p: p.stem)
            if st.button("Open report", icon=":material/folder_open:", width="stretch"):
                report = load_report(str(chosen), chosen.stat().st_mtime)
                st.session_state.update(report=report, media=ui.find_media(report.source), seek_s=None)
        else:
            st.info("No saved reports yet.")

    s = get_settings()
    st.divider()
    st.caption(f"Coder: {s.coder_deployment}/{s.coder_effort} · Supervisor: {s.supervisor_deployment}/{s.supervisor_effort} · "
               f"Content Understanding analyzer: {s.cu_analyzer_id}")

# ---------------- Header ----------------
st.title("MIFlow", anchor=False)
st.caption("Motivational Interviewing review: Azure Content Understanding transcribes the session, a Coder agent tags every turn "
           "(AnnoMI / MITI 4.2.1), and a Supervisor agent rates empathy and collaboration with timestamped feedback.")

# ---------------- Run the pipeline ----------------
if analyze and media_path:
    with st.status("Analyzing session...", expanded=True) as status:
        def on_event(event: dict) -> None:
            if event["status"] == "start":
                status.update(label=STAGES[event["stage"]] + "...")
                st.write(f":material/hourglass_top: {STAGES[event['stage']]}")
            else:
                st.write(f":material/check_circle: {event['message']} · {event['seconds']}s")

        try:
            report = run_pipeline(media_path, start_s, end_s or None, on_event=on_event)
        except Exception as exc:  # noqa: BLE001 - surface any Azure/LLM failure in the UI
            status.update(label="Analysis failed", state="error")
            st.error(f"{type(exc).__name__}: {exc}")
            st.stop()
        status.update(label=f"Analysis complete in {report.usage.total_seconds:.0f}s", state="complete", expanded=False)
    st.session_state.update(report=report, media=media_path, seek_s=None)

report: Report | None = st.session_state.report
if report is None:
    st.info("Pick a sample recording or upload one, set the clip range, and select **Analyze session**. "
            "You can also open a saved report without calling Azure.", icon=":material/info:")
    st.stop()

# ---------------- Overview ----------------
r = report.rubric
media = st.session_state.media
left, right = st.columns([3, 2], gap="large")
with left:
    if media:
        seek = st.session_state.seek_s
        show_captions = st.toggle("Captions", value=False)
        st.video(
            str(media),
            start_time=seek if seek is not None else report.clip_start_ms // 1000,
            autoplay=seek is not None,
            subtitles={"Transcript": ui.subtitles(report)} if show_captions else None,
            alt=f"Session recording: {report.target_behavior or 'MI session'}",
        )
    else:
        st.info("No recording available for this report (text-only analysis).", icon=":material/videocam_off:")
    st.markdown(f"**Target behaviour:** {report.target_behavior or 'unknown'}")
    if report.session_summary:
        st.caption(report.session_summary)

with right:
    with st.container(border=True):
        st.markdown("**MI proficiency score**")
        st.markdown(f"## {r.proficiency_points} / {r.proficiency_max}")
        st.progress(r.proficiency_points / r.proficiency_max)
        st.badge(r.proficiency_band, color=ui.BAND_BADGE[r.proficiency_band])
        st.caption("6 metrics × up to 2 points (basic = 1, advanced = 2). 7–9 basic, 10–12 advanced proficiency.")
    with st.container(horizontal=True):
        st.metric("Empathy", f"{report.empathy.score:.1f} / 5", border=True)
        st.metric("Collaboration", f"{report.collaboration.score:.1f} / 5", border=True)
        st.metric("Change talk ratio", "n/a" if r.change_talk_ratio is None else f"{r.change_talk_ratio:.0%}", border=True,
                  help="Change talk / (change + sustain talk) across client turns.")

# ---------------- Detail tabs ----------------
tab_feedback, tab_score, tab_transcript, tab_dynamics, tab_run = st.tabs(
    [":material/forum: Feedback", ":material/scoreboard: Scorecard", ":material/subject: Transcript",
     ":material/timeline: Session dynamics", ":material/monitoring: Run details"]
)

with tab_feedback:
    st.markdown(report.overall_summary)
    good, bad = st.columns(2, gap="large")
    with good:
        st.subheader(":material/thumb_up: What went well", anchor=False)
        for i, item in enumerate(report.what_went_well):
            ui.feedback_card(item, key=f"good-{i}")
    with bad:
        st.subheader(":material/build: What to improve", anchor=False)
        for i, item in enumerate(report.what_to_improve):
            ui.feedback_card(item, key=f"bad-{i}")
    with st.container(border=True):
        st.markdown("**Coaching tips for the next session**")
        for tip in report.coaching_tips:
            st.markdown(f"- {tip}")

with tab_score:
    ui.metric_cards(report)
    for name, g in (("Empathy", report.empathy), ("Collaboration", report.collaboration)):
        with st.expander(f"Why {name.lower()} = {g.score:.1f}", icon=":material/psychology:"):
            st.write(g.justification)
            for j, ev in enumerate(g.evidence):
                with st.container(horizontal=True, vertical_alignment="center"):
                    ui.seek_button(ev.start_ms, key=f"glob-{name}-{j}")
                    st.caption(f"{ui.ROLE_NAME[ev.role]}: “{ev.quote[:200]}”")
    c = r.counts
    st.dataframe(
        pd.DataFrame([
            {"Code": "Questions (open / closed)", "Count": f"{c.questions} ({c.open_questions} / {c.closed_questions})"},
            {"Code": "Reflections (simple / complex)", "Count": f"{c.reflections} ({c.simple_reflections} / {c.complex_reflections})"},
            {"Code": "Turns with therapist input", "Count": str(c.therapist_inputs)},
            {"Code": "MI-adherent / non-adherent turns", "Count": f"{c.adherent} / {c.non_adherent}"},
            {"Code": "Client change / sustain / neutral", "Count": f"{c.change_talk} / {c.sustain_talk} / {c.neutral_talk}"},
            {"Code": "Clinician share of words", "Count": "n/a" if r.therapist_word_share is None else f"{r.therapist_word_share:.0%}"},
        ]),
        hide_index=True, alt="Code counts behind the metrics",
    )

with tab_transcript:
    with st.container(horizontal=True, vertical_alignment="bottom"):
        who = st.segmented_control("Speaker", ["All", "Clinician", "Client"], default="All", key="who")
        focus = st.pills("Highlight", ["Reflections", "Questions", "Input", "Change talk", "Sustain talk", "Non-adherent"],
                         selection_mode="multi", key="focus")

    def keep(turn) -> bool:
        if who and who != "All" and ui.ROLE_NAME[turn.role] != who:
            return False
        if not focus:
            return True
        tc, cc = turn.therapist_code, turn.client_code
        checks = {
            "Reflections": tc is not None and tc.reflection != "none",
            "Questions": tc is not None and tc.question != "none",
            "Input": tc is not None and tc.therapist_input != "none",
            "Non-adherent": tc is not None and tc.adherence == "non_adherent",
            "Change talk": cc is not None and cc.talk_type == "change",
            "Sustain talk": cc is not None and cc.talk_type == "sustain",
        }
        return any(checks[f] for f in focus)

    for turn in filter(keep, report.transcript):
        avatar = ":material/medical_services:" if turn.role == "therapist" else ":material/person:"
        with st.chat_message(ui.ROLE_NAME[turn.role], avatar=avatar):
            with st.container(horizontal=True, vertical_alignment="center"):
                ui.seek_button(turn.start_ms, key=f"turn-{turn.turn_id}")
                for label, color in ui.turn_tags(turn):
                    st.badge(label, color=color)
            st.write(turn.text)
            code = turn.therapist_code or turn.client_code
            st.caption(f"Coder: {code.rationale}")

with tab_dynamics:
    st.markdown("**Who did what, when**")
    st.altair_chart(ui.dynamics_chart(report), alt="Timeline of clinician behaviours and client talk types")
    trend = ui.talk_trend_chart(report)
    if trend is not None:
        st.markdown("**Change vs sustain talk over the session**")
        st.altair_chart(trend, alt="Cumulative change and sustain talk over time")

with tab_run:
    u = report.usage
    with st.container(horizontal=True):
        st.metric("Total time", f"{u.total_seconds:.0f}s", border=True)
        st.metric("LLM input tokens", f"{u.input_tokens:,}", border=True, help=f"{u.cached_tokens:,} served from prompt cache")
        st.metric("LLM output tokens", f"{u.output_tokens:,}", border=True, help=f"{u.reasoning_tokens:,} reasoning tokens")
        st.metric("Audio analyzed", "n/a" if not u.cu else f"{(u.cu.audio_hours or 0) * 60:.1f} min", border=True,
                  help="Content Understanding (cached)" if u.cu and u.cu.from_cache else "Content Understanding")
    if u.stage_seconds:
        st.bar_chart(pd.DataFrame({"stage": list(u.stage_seconds), "seconds": list(u.stage_seconds.values())}),
                     x="stage", y="seconds", horizontal=True, alt="Seconds per pipeline stage", height=220)
    st.dataframe(pd.DataFrame([x.model_dump() for x in u.llm]), hide_index=True, alt="LLM calls")
    st.caption(f"Session {report.session_id} · created {report.created_at} · models {report.models}")
    for w in report.warnings:
        st.warning(w, icon=":material/warning:")
    st.download_button("Download report JSON", report.model_dump_json(indent=1), file_name=f"{report.session_id}.json",
                       mime="application/json", icon=":material/download:")
