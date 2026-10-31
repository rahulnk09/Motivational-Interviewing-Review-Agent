# Chapter: Multi-Agent LLM Pipeline Architecture
 
This section details the backend processing pipeline, assuming Azure Content Understanding (ACU) has successfully extracted the WEBVTT transcript (with precise timestamps and speaker diarization) from the uploaded video.
 
To manage the cognitive load and ensure high fidelity in clinical evaluation, the system breaks the evaluation process into three distinct functional nodes.
 
## Node 1: The Parsing Agent
**Core Responsibility:** To read the raw WEBVTT transcript line-by-line and semantically tag every single utterance using the AnnoMI dataset schema.
 
*   **Execution Strategy (100% LLM):** This node requires deep semantic reasoning. Distinguishing between a "Simple Reflection" (parroting) and a "Complex Reflection" (adding meaning/emotion), or detecting client ambivalence, cannot be done via regex or standard code. It requires an LLM with a strong context window and reasoning capabilities.
*   **System Prompt Boilerplate (Few-Shot):**
 
```text
You are an expert Motivational Interviewing (MI) fidelity coder evaluating a transcript based on the AnnoMI coding schema. Your task is to classify each utterance.
 
For Clinician (C1) utterances, classify the `main_therapist_behaviour` as one of: [question, reflection, therapist_input, other].
- If a question, classify `question_subtype` as [open, closed].
- If a reflection, classify `reflection_subtype` as [simple, complex].
- Assess `mi_adherence` as [adherent, non_adherent, neutral].
 
For Client (C2) utterances, classify `client_talk_type` as [change, sustain, neutral].
 
Few-Shot Examples:
Clinician: "What brings you in today?"
-> behaviour: question, subtype: open, adherence: adherent
 
Client: "I know I should quit smoking, but it helps my stress."
-> talk_type: sustain
 
Clinician: "You feel torn because the thing harming your lungs is the only thing keeping you calm."
-> behaviour: reflection, subtype: complex, adherence: adherent
 
Clinician: "You just need to try harder to quit."
-> behaviour: therapist_input, subtype: advice, adherence: non_adherent
```
 
*   **Expected Handover:** A rigidly formatted JSON array of objects, where each object contains: `timestamp`, `speaker_id`, `text`, and the applied AnnoMI tags.
 
---
 
## Node 2: The Evaluator Agent
**Core Responsibility:** To calculate the required clinical metrics (the 6 Lyssn.io metrics and the Client Impact Metric) based on the parsed data.
 
*   **Execution Strategy (Hybrid: Deterministic + LLM):**
    *   **Deterministic (Python):** Do **not** use the LLM to calculate ratios (e.g., Reflection-to-Question Ratio, % Open Questions, % Complex Reflections, Change Talk Ratio). LLMs are prone to arithmetic hallucinations. Instead, use simple Python functions to aggregate the tags provided by Node 1 and calculate the percentages deterministically.
    *   **LLM:** Use an LLM *only* to evaluate the holistic Global Scores (Empathy and Collaboration) on a 1-5 Likert scale, as this requires assessing the overall "MI Spirit" of the session.
*   **System Prompt Boilerplate (Global Scoring):**
 
```text
You are an expert clinical supervisor evaluating a Motivational Interviewing session. You will be provided with a tagged transcript of a clinical encounter.
 
Based on the entire interaction, assign a score from 1 to 5 for the following global dimensions based on MITI 4.2.1 guidelines:
1. Empathy:
   - 1 = Indifference or active dismissal of client's perspective.
   - 3 = Sporadic efforts to explore perspective, but remains superficial.
   - 5 = Deep understanding and active interest in implicit/explicit meaning.
2. Collaboration (Partnership):
   - 1 = Actively assumes expert/authoritarian role; ignores client input.
   - 3 = Solicits client views perfunctorily.
   - 5 = Actively fosters power-sharing; cooperative partnership.
 
Provide a 1-2 sentence justification for each rating, citing specific conversational dynamics.
```
 
*   **Expected Handover:** A combined data dictionary containing the mathematically derived ratios (from Python) and the qualitative Global Scores and justifications (from the LLM).
 
---
 
## Node 3: The Synthesis Agent
**Core Responsibility:** To marry the qualitative insights with exact video timestamps to generate actionable, traceable feedback for the frontend dashboard.
 
*   **Execution Strategy (LLM-Light / Formatting):** This node acts as a formatter. It requires an LLM adept at instruction following and strict JSON schema generation. It scans the outputs of Nodes 1 and 2 to identify key learning moments.
*   **System Prompt Boilerplate:**
 
```text
You are an API data formatting agent. You will receive an evaluated MI transcript where utterances are tagged with behaviors and metrics.
 
Your task is to identify the 2 most significant "Strengths" (e.g., highly effective open questions or complex reflections that successfully elicited 'change talk') and the 2 most significant "Traps" (e.g., closed questions, expert traps, or unsolicited advice that caused 'sustain talk' or defensiveness).
 
You must strictly output this as a JSON object matching the provided JSON schema.
CRITICAL: You MUST include the exact `timestamp` (e.g., "01:23") and the exact `quote` from the transcript so the frontend video player can link directly to it for the clinical review.
```
 
*   **Expected Handover:** The final, highly structured JSON payload. This payload encompasses the total MI Proficiency Score, the statistical metric charts data, and the `what_went_good` / `what_went_bad` arrays with their respective WEBVTT timestamps, sent directly to the Streamlit UI.
 