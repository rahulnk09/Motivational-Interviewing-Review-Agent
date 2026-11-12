# MIRA — Speaker Notes (15 min · 25 slides)

**Rule of thumb:** say the slide title first, then point at the visual. Don't read the slide.
**Running time:** cumulative time is shown in brackets after each act.

---

## Act 1 · Why it matters (S1–S4) · 1:50 [1:50]

**S1 · Title (0:10)**
"We built MIRA, an AI reviewer for Motivational Interviewing conversations. Let me start with two clips."

**S2 · Same goal, opposite outcomes (0:40)**
"Two clinicians, same goal: a healthier client. On the left, the clinician argues: 'Do you put your dog above your baby?' The client digs in: 'You don't get my situation.' On the right: 'What would you like to do?' And the client herself says, 'Maybe I could try to cut back.' Zero percent versus 83 percent change talk. The difference isn't knowledge. It's a conversational skill that can be learned."

**S3 · The feedback gap (0:30)**
"Clinicians learn MI from feedback. But feedback means a trained coder reviewing a recording turn by turn, which takes hours. So it rarely happens, and research shows skills fade within months without it. Most sessions are never reviewed."
→ *Transition:* "So who needs this?"

**S4 · Users and promises (0:30)**
"Three users: the clinician who wants to know what to say next time, the supervisor who can only review a handful of sessions, and the programme lead who needs proof that training works. We made five promises. Hold us to them; we'll check them off at the end."

---

## Act 2 · What good MI looks like (S5–S7) · 1:30 [3:20]

**S5 · Spirit and four steps (0:35)**
"MI is a stance: partnership, acceptance, compassion, evocation. The client is the expert. A good session moves through four steps, and Mia's clinician hits all four: welcome her, focus on vaping, evoke her own pros and cons, and let her choose the next step."

**S6 · OARS (0:25)**
"Four micro-skills: open questions, affirmations, reflections and summaries. Reflections are the core. A simple reflection repeats; a complex one adds meaning. Experts want more reflections than questions."

**S7 · Change talk and traps (0:30)**
"Listen to the client. 'I felt out of breath' is change talk, and people believe what they hear themselves say. 'It helps me relax' is sustain talk. Clinicians create sustain talk by falling into traps: lecturing, interrogating, arguing. Sal's clinician fell into the confrontation trap."
→ *Transition:* "So how do experts turn this into a score?"

---

## Act 3 · How MI is measured (S8–S9) · 1:05 [4:25]

**S8 · Six metrics (0:40)**
"We use MITI 4.2.1, the standard MI coding manual. It has two lenses: code every turn, and rate the whole session. That gives six metrics, each with a basic and an advanced bar. Four are plain arithmetic on turn codes. Two, empathy and collaboration, are expert-style ratings. Mia's clinician is excellent on open questions, but she asks twice as many questions as she reflects."

**S9 · Score and client impact (0:25)**
"Each metric is worth up to 2 points, 12 in total. Mia's clinician scores 8, Basic proficiency; Sal's scores 0. Separately, the change talk ratio tells us whether it worked for the client: 83% versus 0%."
→ *Transition:* "Now, how does MIRA do this automatically?"

---

## Act 4 · Meet MIRA (S10–S11) · 1:20 [5:45]

**S10 · Pipeline (0:45)**
"Five stages. Azure Content Understanding listens: transcript, who's the clinician, millisecond timestamps. The Coder agent labels every turn. Plain Python does all the math, so scores are reproducible. The Supervisor agent rates empathy and collaboration and writes feedback. The app shows it all. Three trust rules: the LLM never does arithmetic; it cites turn numbers and our code inserts the exact quote and timestamp, so nothing can be made up; and every output is strictly typed and validated."

**S11 · AnnoMI (0:35)**
"Our answer key is AnnoMI: 133 real MI demonstrations, every turn coded by experts, and seven of them coded independently by ten experts. It does four jobs: it teaches the Coder with examples, calibrates the Supervisor, benchmarks the clinician, and grades MIRA itself. Only two transcripts ever go into prompts; the rest are kept strictly for testing."

---

## Act 5 · Inside the agents (S12–S13) · 1:20 [7:05]

**S12 · Coder (0:40)**
"Few-shot learning means showing the model solved examples instead of retraining it. It's like handing a new coder a marked-up page. We pick 22 examples by algorithm so every label is covered. The fixed part of the prompt goes first so Azure can cache it, which cuts cost. Here's a real turn: the model explains its reasoning first, then labels it 'open question, seeking collaboration'."

**S13 · Supervisor (0:40)**
"The Supervisor reads like an MI trainer: it gets the metrics as facts, the rating anchors and a catalogue of traps. It cites turn numbers; our code turns them into a quote and a clickable timestamp, and 100% of citations were valid. And it doesn't just criticise: here it tells the clinician exactly what she could have said instead."
→ *Transition:* "Let me show you."

---

## Act 6 · Live demo (S14) · 2:45 [9:50]

1. **Start the analysis first** (the transcript is cached, so it takes ~50 s). "While it runs, you can see each stage live: transcribe, code, measure, supervise."
2. **Overview:** "About 8 out of 12, Basic; empathy 3.5; change talk 83%." *(LLM runs vary between 6 and 8; say "about 8".)*
3. **Feedback tab:** click ▶ on "Reflect the change talk…" and let the video play for 5 s. "Every point jumps to the moment."
4. **Scorecard:** "R:Q is below Basic. And every metric shows how expert-rated good and poor sessions score."
5. **Transcript:** filter "Change talk". "You can watch Mia move toward change; every code has a one-line reason."
6. **Dynamics / Run details:** "Change talk overtakes sustain talk. The whole review took about 50 seconds."
- **If anything fails:** open the saved report (instant, no Azure call) or click through the screenshots on this slide.

---

## Act 7 · Proof (S15–S18) · 1:55 [11:45]

**S15 · How to read the results (0:30)**
"Four yardsticks. Kappa is agreement beyond chance: a lazy coder that says 'neutral' every time gets 64% accuracy but zero kappa. The human ceiling is how well experts agree with each other. AUC: pick a good and a poor session; how often do we score the good one higher? WER is transcription errors."

**S16 · Coder vs experts (0:25)**
"On the seven sessions that ten experts coded independently, the Coder agrees with the expert consensus better than a typical expert does, on all five code families. Across all 1,276 held-out turns it reaches kappa 0.85 on main behaviour. Data picked our model and tuned our prompt: one rule lifted client-talk agreement by 14 points."

**S17 · Good vs poor sessions (0:30)**
"Never seeing the expert's quality label, MIRA scores the good session higher in 164 of 170 good-versus-poor pairs: AUC 0.98, with 4 ties and only 2 reversed. Empathy and collaboration together separate every pair. Citations are 100% valid, the Supervisor gives the same points when re-run, and on our held-out video the audio stage got speakers 100% right."

**S18 · Honest gaps (0:30)**
"We ran our own playbook on ourselves. Simple versus complex reflections wobble, though experts disagree there even more: kappa 0.22 among themselves. Our bands are strict. Audio merges very short turns. And some metrics aren't validated yet. Each has a concrete fix, starting with a three-run majority vote."
→ *Transition:* "Is it affordable?"

---

## Act 8 · Cost & feasibility (S19–S21) · 1:20 [13:05]

**S19 · Cost (0:30)**
"Measured, not estimated: about 9 cents for a 3-minute review. Most of it is the model thinking and writing feedback. That scales to about 50 cents for a 30-minute session, roughly 1–2 cents per minute. A hundred clinicians reviewing four sessions a month is about $200." *(If you have it: "compared with $__ for a human review.")*

**S20 · Feasibility (0:30)**
"No GPUs and no training pipeline: just managed Azure services. Models and settings are configuration, and 31 tests plus three evaluation suites catch regressions. Going to a pilot is integration work: hosting, sign-in, storage, and a validation study on real, consented sessions."

**S21 · Risks (0:20)**
"The key risks: wrong scores, privacy and surveillance fears. Evidence on every claim, data in the organisation's tenant, consent, and feedback that goes to the clinician first."

---

## Act 9 · Impact (S22) · 0:30 [13:35]

**S22 · Impact (0:30)**
"Feedback on every session is the lever. It builds skill, which means more reflecting and less pushing, more client change talk, and ultimately behaviour change. MIRA measures the first four links today; a pilot proves the last. Operationally, expert time moves from scoring to coaching."

---

## Act 10 · Next & close (S23–S25) · 1:05 [14:40]

**S23 · Beyond words (0:35)**
"'I suppose I could try' can be real commitment or a polite no; text can't tell. Next, we add voice: talk time, pauses and interruptions from timestamps we already have, then an audio model for tone, then video for gaze and nodding. And we'll measure behaviour, not emotion, in line with Microsoft's own Responsible AI decisions."

**S24 · Promises kept (0:25)**
"Five promises, five receipts: standards-based, grounded, actionable, fast and affordable, and measured. And remember Mia's words: 'maybe I could try to cut back.' Every clinician deserves to know which words got them there."

**S25 · Thank you (0:05)**
"Thank you. Happy to take questions."

---

## Q&A prep (one-liners)

| Likely question | Answer |
|---|---|
| Why not fine-tune a model? | Few-shot plus evals reaches expert-level agreement with no training pipeline; changes are a text edit, re-measured automatically. |
| How do you stop hallucinations? | The model only cites turn ids; code inserts quotes and timestamps; invalid ids are dropped (479/479 valid). |
| Is AnnoMI realistic? | They're demonstration videos, so the pilot validates on real, consented sessions coded by certified MITI coders. |
| Why gpt-5.4, not the mini model? | Measured on the same 27 sessions: κ 0.85 vs 0.78 on main behaviour, 0.70 vs 0.57 on reflections; mini is about 4× faster (9 s vs 38 s), so it remains a cost lever. |
| Why does the demo score vary (6–8)? | Simple vs complex reflection judgements vary between runs; the 3× majority-vote Coder is the planned fix. |
| Data privacy? | Runs in your Azure tenant, requires consent, has a retention/deletion policy; it is a coaching aid, not certification. |
| What about long sessions? | Over 120 turns, the Coder works in 80-turn windows; cost is about $0.50 for 30 minutes (extrapolated). |
 