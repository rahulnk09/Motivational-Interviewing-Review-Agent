## Plan: MIFlow, the Motivational Interviewing Review prototype

The plan builds a `mi_review` Python package in `mi_project/src`. The flow is:

1. A Content Understanding (CU) custom audio analyzer transcribes the video and separates the two speakers.
2. A Coder agent tags every turn using AnnoMI-style labels.
3. Plain Python calculates your exact rubric (6 metrics, a 0–12 proficiency score, and the change talk ratio).
4. A Supervisor agent rates Empathy and Collaboration and writes the strengths and traps.
5. Each piece of feedback carries a timestamp, which Python fills in so the LLM never invents one.

LangGraph runs the steps and streams progress to a local Streamlit app. Each component gets a command-line smoke test, and the agents also get an evaluation script that compares them against held-out AnnoMI transcripts.

**On your few-shot question:** I agree with your limit of 2 transcripts (1 high, 1 low), but I wouldn't paste them in whole. Two full transcripts are mostly filler turns ("Okay", "Mm-hmm") and may contain no sustain talk or advice at all. Instead:
- **Coder prompt:** about 25 short labelled excerpts taken from those 2 transcripts, chosen to cover every label (roughly 2k tokens).
- **Supervisor prompt:** one short excerpt from each transcript as a high/low reference point.
- **The rest of AnnoMI:** never goes into a prompt. The evaluation scripts feed held-out transcripts through the pipeline one at a time, as test inputs.

**Changes to your draft pipeline (where it was over-engineered)**
1. **Two LLM calls instead of three.** Your Evaluator call and Synthesis call become one Supervisor call using structured outputs. The LLM only cites turn IDs; Python looks up the quote and timestamp, so citations can't be made up.
2. **The Coder's output matches AnnoMI-full's columns:** main behaviour, the reflection/question/input flags, and their subtypes, plus an MI-adherence field. That lets us score it directly against the gold labels.
3. **The CU analyzer does more than transcribe.** In the same pass it returns a session summary, the target behaviour, and which speaker is the clinician. That solves the Speaker 1/Speaker 2 → clinician/client mapping, and gives the context needed to judge change talk.
4. **Tagging is per turn, not per sentence.** Consecutive sentences from the same speaker are merged into one turn. This matches AnnoMI and MITI's "count one question per turn" rule.
5. **Empathy and Collaboration use half-points (1.0–5.0).** With whole numbers, your 3.5 Basic threshold can never be hit, so Basic and Advanced would collapse into one level.

**Steps**

*Phase 0 – Foundation*
1. Make `mi_project` a uv workspace member: a new `mi_project/pyproject.toml` (hatchling build, src layout), plus a workspace entry and source in the root pyproject. New dependencies: langgraph, streamlit, plotly, scikit-learn, jiwer, and pytest (dev only). Then run `uv sync` so the root `.venv` and its kernel can import the package.
2. `config.py`: loads the root `.env` and defines settings:
   - `MI_CU_ANALYZER_ID` (default `miSessionAudio`) and `MI_CU_BASE_ANALYZER` (prebuilt-audio or prebuilt-video).
   - `MI_CODER_DEPLOYMENT` (default gpt-5.4-mini) and `MI_SUPERVISOR_DEPLOYMENT` (default gpt-5.4), plus a reasoning-effort setting for each.
   - Folder paths and the rubric thresholds.
3. `clients.py`: reuses the auth from notebook 02 (`DefaultAzureCredential` with a bearer-token provider, and `OpenAI(base_url=…/openai/v1/)`). It includes an optional TLS workaround for the Netskope proxy: a requests transport for CU and an httpx client for OpenAI. Switch it on only if certificate errors appear.
4. `llm.py`: one helper that calls the Responses API's `parse` with a Pydantic output schema, with retries, and records token usage and latency.
5. `cli.py doctor` checks the env vars, the CU connection, and a tiny structured-output call to both model deployments.
   - **Verify:** `uv run python -m mi_review.cli doctor` reports everything OK.

*Phase 1 – Ingestion with Content Understanding (needs Phase 0)*

6. `ingest.py` defines and creates (or replaces) the analyzer:
   - Base `prebuilt-audio`, with `return_details=True` and `locales=["en-US"]`.
   - Fields: `SessionSummary` (generate), `TargetBehavior` (generate), `ClinicianSpeaker` (classify, choices "Speaker 1" to "Speaker 4").
   - `transcribe(path, start_s, end_s)` uses `begin_analyze_binary(content_range="39000-")` and caches the raw result in `data/output/cu/` by file hash and time range.
   - If the time range isn't honoured, the fallback is to trim the file with ffmpeg first.
7. `transcript.py`:
   - Turns CU sentences into numbered turns with start/end times. It checks whether CU's times count from the start of the file or from the clip start, and corrects if needed.
   - Maps speakers to roles: the CU `ClinicianSpeaker` field first, otherwise whichever speaker asks the most questions. It warns if more than 2 speakers are detected.
   - Includes an AnnoMI loader that returns the same turn format with the gold labels.
8. CLI commands: `setup-analyzer` and `transcribe <video> --start 39 [--end]`.
   - **Verify:**
     - On the demo video: 2 speakers, the first turn starts at 39 s or later, timestamps only go forward, and the CU speaker mapping agrees with the heuristic.
     - Spot-check the first 15 turns against the audio.
     - pytest `test_transcript.py` (merge rules, role heuristic, time offset).

*Phase 2 – AnnoMI assets (can run alongside Phase 1)*

9. `annomi.py` plus a `build-assets` command picks the high/low transcript pair that covers the most labels. It excludes the multi-annotator transcripts and your reserved gold-video transcript. It writes four files:
   - `assets/fewshot_coder.json`: the labelled excerpts.
   - `assets/supervisor_anchors.json`: one excerpt each from the high and low transcript.
   - `assets/eval_split.json`: about 20 stratified held-out transcripts plus the 7 multi-annotator ones.
   - `assets/benchmarks.json`: median gold R:Q, %OQ, %CR and change talk ratio for high vs low sessions, shown in the UI for comparison.
   - **Verify:** a label-coverage table prints, the few-shot block is under ~2.5k tokens, and the few-shot and evaluation transcripts don't overlap.

*Phase 3 – Coder agent (needs Phases 1 and 2)*

10. `prompts/coder_system.md`: MITI 4.2.1 / AnnoMI definitions and decision rules:
    - Open vs closed questions; count one question per turn.
    - Simple vs complex reflection; default to simple when unsure; summaries count as complex.
    - Input subtypes: information, advice, negotiation, options.
    - "Other" for fillers and back-channels.
    - Adherent / non-adherent / neutral, defined to match your %MIA wording.
    - Change / sustain / neutral talk, relative to the `TargetBehavior`.
    - Then the few-shot block, then the transcript last.
11. `coder.py` sends the whole transcript in one call, splitting into overlapping windows only above ~120 turns. It then:
    - checks every turn ID is coded exactly once;
    - checks the labels match the speaker's role;
    - makes the flags and subtypes consistent;
    - re-requests any turns that are missing.
12. The `eval-coder --n 20 --model --effort` command reports accuracy, macro-F1, Cohen's κ and confusion matrices for each label. On the 7 multi-annotator transcripts, it also measures how often human annotators agree with each other, which is the realistic ceiling. It compares mini vs full and allows up to 3 rounds of prompt tuning.
    - **Verify:** first a 3-transcript smoke run, then n=20.
    - Soft targets: κ ≥ 0.55 for therapist behaviour and macro-F1 ≥ 0.5 for client talk, read against the human ceiling.

*Phase 4 – Metrics (can run alongside Phase 3)*

13. `metrics.py`:
    - Computes the 6 metrics using your doc's thresholds.
    - Scores each metric 0, 1 (Basic) or 2 (Advanced), for a total of 0–12. Bands: 0–6 Developing, 7–9 Basic, 10–12 Advanced.
    - Change talk ratio = change / (change + sustain).
    - Also reports the therapist's share of words spoken.
    - Edge cases:
      - No questions: R:Q uses the number of reflections.
      - Any other undefined metric: scored "insufficient data" with 0 points.
    - **Verify:** pytest `test_metrics.py`, including your doc's worked example (R:Q 1.0 = Basic, %CR 100% = Advanced, change talk 50%). Also a sanity check that gold-label metrics still separate high from low quality as in your EDA (R:Q AUC ≈ 0.89).

*Phase 5 – Supervisor agent and report (needs Phases 3 and 4)*

14. `prompts/supervisor_system.md`:
    - MITI 4.2.1 score descriptions for Empathy and Partnership/Collaboration, on the half-point scale.
    - A catalogue of traps: Expert / righting reflex, Question–Answer, Confrontation–Denial, Premature Focus, Labeling, Blaming, Persuading without permission, and missed change talk.
    - A catalogue of OARS strengths.
    - The two reference excerpts.
    - Rules: cite turn IDs only, and suggest an MI-consistent alternative response for each trap.
15. `supervisor.py` returns, as structured output: both global scores with justification and evidence, 2–3 strengths, 2–3 improvements, an overall narrative, and coaching tips. `report.py` fills in timestamps and verbatim quotes, and rejects citations that point to a missing turn or the wrong speaker.
16. The `eval-supervisor` command reports:
    - AUC (high vs low) for proficiency points, Empathy and Collaboration.
    - The share of citations that are valid.
    - How much scores vary between 2 runs on 3 transcripts.
    - **Verify:** targets are proficiency AUC ≥ 0.75 and 100% valid citations.

*Phase 6 – LangGraph pipeline and end-to-end run (needs Phase 5)*

17. `graph.py` defines a `StateGraph` with these steps:
    - **Steps:** transcribe → build turns → code turns → compute metrics → supervise → assemble report.
    - **Entry:** a branch at the start skips CU when turns are supplied (used by the evaluation scripts).
    - **Progress:** each step emits progress events that Streamlit can display.
    - **Logging:** timings and token usage are collected.
    - **Output:** the report is saved to `data/output/reports/{session_id}.json`.
18. Two more CLI commands:
    - `run <video> --start 39 [--end]`: runs the whole pipeline on a video.
    - `eval-ingest`: run on your AnnoMI gold video, it measures:
      - transcription word error rate;
      - speaker-role accuracy (CU turns lined up with gold utterances by time and text similarity);
      - tag agreement.
    - **Verify:**
      - End-to-end run on the demo video; the report matches the schema.
      - Watch the cited moments in the video to confirm each strength and trap.
      - A second run reuses the cached CU result.
      - Note latency and cost.

*Phase 7 – Streamlit app (UI work can start from a saved Phase 5 report)*

19. `app/streamlit_app.py`. Use the Streamlit skill's version-matched docs during implementation.
    - **Sidebar:** upload a file or pick a sample, start/end offset, Analyze button, and a list of previous reports.
    - **Main area:** video player next to a 0–12 proficiency gauge and the change talk ratio.
    - **Tabs:**
      - Scorecard: the 6 metrics with threshold markers, Basic/Advanced level, and AnnoMI benchmarks.
      - Feedback: what went well / what to improve, each with a quote, a timestamp button that jumps the video there, and a suggested better response.
      - Transcript: colour-coded turns and tags with a filter.
      - Dynamics: change vs sustain talk over time.
    - JSON download, and progress shown while the pipeline runs.
    - **Verify:** with `uv run streamlit run mi_project/app/streamlit_app.py`, check:
      - the analysis runs and progress stages show;
      - timestamp clicks jump the video;
      - a saved report loads with no Azure calls.

*Phase 8 – Demo hardening*

20. Pre-compute reports for the demo video and the gold video. Update `.env.sample` with the new variable names. Add `mi_project/data/output/` and `mi_project/data/*.mp4` to `.gitignore`.

**Relevant files**
- `e:\rnakka\POCs\ADI\pyproject.toml`, `.gitignore`, `.env.sample`: workspace member, ignore rules, variable names.
- `e:\rnakka\POCs\ADI\mi_project\pyproject.toml`: the new package.
- `e:\rnakka\POCs\ADI\mi_project\src\mi_review\`:
  - Python modules: `config`, `clients`, `llm`, `schemas`, `ingest`, `transcript`, `annomi`, `coder`, `metrics`, `supervisor`, `report`, `graph`, `cli`.
  - `prompts/`, generated `assets/`, and `evals/`.
- `e:\rnakka\POCs\ADI\mi_project\app\streamlit_app.py`
- `e:\rnakka\POCs\ADI\mi_project\tests\`: `test_transcript.py`, `test_metrics.py`, `test_report.py`.
- Reference only: `junk/Notebooks/02_structured_rag_mixed_content.ipynb` for the client setup, `begin_create_analyzer`, `begin_analyze_binary`, `to_plain`, the TLS adapter and `usage_of`.

**Decisions**
- **Rubric:** exactly as your approach document.
- **%MIA:** adherent / (adherent + non-adherent) at turn level. AnnoMI has no gold labels for this, so it is judged by the LLM only.
- **Models:** no fine-tuning and no new deployments; the existing gpt-5.4-mini and gpt-5.4 are enough.
- **Out of scope:** video frames / non-verbal cues, authentication, Azure hosting, real-time audio.

**Further considerations**
1. **Gold video:** I suggest AnnoMI transcript 27 ("How NOT to do Motivational Interviewing: … Sal … asthma", low quality, 00:00:08–00:03:23). It has 10 annotators, so we get a human-agreement ceiling, and it contrasts well with your high-quality demo. Please pick it before Phase 2 so it's excluded from the few-shot examples.
2. **Your `.env`:** it contains a plain-text Azure Search key. It's gitignored and this project doesn't use it, but rotate it if the file was ever shared.
