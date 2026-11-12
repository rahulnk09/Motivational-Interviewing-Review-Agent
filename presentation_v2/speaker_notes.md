# MIRA v2 · Speaker notes (≈ 11½ min: 8:40 slides + 2:45 demo)

Team **PhoenixAI**: Rahul Nakka, Deependra Shekhawat.
Say the slide title first, then point at the visual. Times in brackets are cumulative.

| # | Slide | Time | Cumulative |
|---|---|---|---|
| 1 | MIRA + team | 0:15 | 0:15 |
| 2 | The feedback gap | 0:40 | 0:55 |
| 3 | MI in one minute | 0:45 | 1:40 |
| 4 | From skills to a score | 0:35 | 2:15 |
| 5 | How MIRA works | 0:40 | 2:55 |
| 6 | One moment, end to end | 0:45 | 3:40 |
| 7 | **Demo (saved report)** | **2:45** | 6:25 |
| 8 | Who it helps | 0:40 | 7:05 |
| 9 | AnnoMI | 0:35 | 7:40 |
| 10 | Check 1 · Listen | 0:25 | 8:05 |
| 11 | Check 2 · confusion matrices | 0:40 | 8:45 |
| 12 | Check 2 · κ vs experts | 0:45 | 9:30 |
| 13 | Check 3 · good vs poor | 0:35 | 10:05 |
| 14 | Cost + privacy | 0:50 | 10:55 |
| 15 | Proven / next / thanks | 0:30 | 11:25 |

---

**1 · Title (0:15)**
"We're Team PhoenixAI: Rahul Nakka and Deependra Shekhawat. We built MIRA, the MI Review App. You upload a recorded counselling session, and in a minute or two you get a transcript, an MI scorecard and coaching linked to the exact moments in the video."

**2 · The feedback gap (0:40)**
"Clinicians get better at Motivational Interviewing through feedback on their real sessions. Today that means a trained coder going through the recording turn by turn against the MITI manual, which takes hours per session. It's slow and expensive, so most sessions never get reviewed. It isn't perfectly consistent either: on AnnoMI, two experts coding the same client statements agree only kappa 0.47. Clinicians need feedback on every session that is fast, consistent and points to the exact moment."

**3 · MI in one minute (0:45)**
"MI is a way of talking that helps people find their own reasons to change. Two real sessions from our data: Sal's clinician argues, 'Do you put Oscar higher than your baby?' Sal digs in: zero change talk. Mia's clinician asks about the pros and cons, and Mia says herself she worries about getting addicted: 67% change talk. A good session moves through four steps (engage, focus, evoke, plan), shown here with Mia's clinician."

**4 · From skills to a score (0:35)**
"MITI, the standard coding manual, has two lenses: label every turn (open questions, affirmations, reflections, and whether the client talks toward or away from change) and rate the whole session on empathy and collaboration. Six metrics, up to two points each, 0 to 12. Mia's clinician scores 8, Basic. Great open questions, but twice as many questions as reflections. The change talk ratio shows whether it worked for the client."

**5 · How MIRA works (0:40)**
"ffmpeg cuts the clip locally and keeps only the audio. Azure Content Understanding transcribes it, separates the speakers with millisecond timestamps, and generates the clinician speaker, target behaviour and a summary. The Coder agent (gpt-5.4 with 22 expert-labelled examples) labels every turn. Plain Python computes the metrics. The Supervisor agent rates empathy and collaboration and writes the coaching. Trust rules: no LLM arithmetic; the LLM cites turn numbers and our code inserts quotes and timestamps; every output is strictly typed and validated."

**6 · One moment, end to end (0:45)** *(click through 7 build steps)*
"At 2:29, Content Understanding returns Speaker 1 with a timestamp, and the clinician field says Speaker 1 is the clinician. The Coder labels it an open question with an affirmation and gives a reason. Mia's reply is change talk. Python turns codes into metrics. The Supervisor calls it a strength and cites turns 8 and 9 by number only. Our code inserts the quote and the clickable timestamp, so feedback can't misquote the session. It also coaches: at 3:18 the clinician offered advice without asking, and MIRA suggests what to say instead."

**7 · Demo (2:45)**: *switch to the app; the saved report needs no Azure call*
1. Sidebar → **Saved report** → `Motivational_Interviewing_in_Action__Rol-7e38dc72-39-223` → **Open report**.
2. **Overview:** "8 out of 12, Basic; empathy and collaboration 3.5; change talk 67%."
3. **Feedback:** under "Evoked discrepancy with her future goals", click ▶ **02:29** and let it play ~5 s. Then "Ask before offering strategies" → read the *Try instead*.
4. **Scorecard:** "R:Q 0.50 is below Basic: exactly the coaching point. Each metric shows AnnoMI medians for expert-rated good and poor sessions."
5. **Transcript:** filter **Change talk**: "every code comes with a one-line reason."
6. **Session dynamics:** "change talk overtakes sustain talk."
- Close with: "A new analysis takes about one to one and a half minutes for a three-minute clip."
- **Fallback:** if the app is unavailable, talk through the screenshots on slide 7.

**8 · Who it helps (0:40)**
"Clinicians get specific, timestamped feedback minutes after the session. Supervisors can't listen to every recording; the evidence-linked scorecard helps them pick which sessions need a closer look, so their time goes into coaching, not counting. Team-level trends for programme leads are intended, not built yet. MI is used across behaviour-change care. MIRA is a coaching aid built on MITI 4.2.1. It rates the clinician, never the client, and it isn't a certification."

**9 · AnnoMI (0:35)**
"We grade MIRA against AnnoMI: 133 MI demonstration transcripts, 110 rated high and 23 low quality, every utterance coded by an expert, and 7 coded by all 10 experts, which tells us how much experts agree. Only two transcripts go into our prompts; 27 others, 1,276 turns, are held out for testing. Three checks, one per stage."

**10 · Check 1 · Listen (0:25)**
"On a held-out AnnoMI video, about 10% word error rate and 100% correct speaker roles; on a second, 12-minute video, 10.8% and 99.7%. In this real line half the words count as errors, but the meaning is identical: the human transcriber kept fillers. A sanity check on two videos, not a benchmark."

**11 · Check 2 · where it agrees (0:40)**
"On 27 unseen transcripts we compare MIRA's label with the expert's for every turn; the diagonal is agreement. Whether there's a reflection is easy; how deep it is is the hard call: 36 of 110 complex reflections were called simple. MIRA rarely misses sustain talk but is a little generous with change talk."

**12 · Check 2 · as consistent as experts (0:45)**
"Kappa is agreement after removing lucky guesses: a lazy coder saying 'neutral' every time gets 69% accuracy but kappa zero. On the 7 sessions all 10 experts coded: treat MIRA as an 11th coder and it agrees with any single expert more than experts agree with each other, on all five code families. Against the majority vote, the same picture. Compare within a panel, not across."

**13 · Check 3 · good vs poor (0:35)**
"MIRA never sees the expert's quality label. All 10 poor sessions score 3 or less; 15 of 17 good ones score 4 or more; in 164 of 170 good-vs-poor pairs the good session scores higher. In good sessions it flags missed opportunities; in poor ones, confrontation and persuasion. Our bands are strict, so some good demo sessions still land in Developing."

**14 · Cost + privacy (0:50)**
"Measured on two real runs: about 9 and 8 cents for a three-minute session; ~70% is the gpt-5.4 agents, ~30% audio. Today only the audio leaves the machine, all AI runs in our own Microsoft Foundry resource with Entra ID, LLM calls aren't stored, and quotes are inserted by code. Azure OpenAI and Content Understanding are HIPAA-eligible under Microsoft's BAA, and prompts aren't used for training. But eligible isn't compliant: before real patient data we'd add a hosted app with sign-in, private networking, Key Vault, retention and deletion, and consent."

**15 · Proven / next (0:30)**
"On AnnoMI, MIRA codes at or above the human level, ranks good above poor almost every time, and never invents evidence, for about nine cents per short review. Gaps: reflection depth is hard even for experts, so scores can move a point or two between runs; demonstration videos only; words only. Next: a three-run majority vote, a consented pilot on real sessions, and voice features. Thank you."

---

## Q&A one-liners

| Question | Answer |
|---|---|
| Why not fine-tune? | Few-shot prompting plus evaluations already reaches expert-level agreement; changing behaviour is a prompt edit, re-measured automatically. |
| How do you stop hallucinated evidence? | The LLM cites turn ids only; code inserts quote and timestamp and drops invalid ids. 479/479 cited ids were valid. |
| Is AnnoMI realistic? | It's demonstration videos. A pilot would validate on consented real sessions coded by MITI experts. |
| Why gpt-5.4 and not mini? | Measured on the same 27 sessions: κ 0.85 vs 0.78 (behaviour), 0.70 vs 0.57 (reflection). Mini is ~4× faster, so it's a cost lever. |
| Why might the score change between runs? | Simple vs complex reflection judgements vary (experts agree only κ 0.22 on that call). Planned fix: 3-run majority vote. |
| Is it HIPAA compliant? | The Azure services are HIPAA-eligible under Microsoft's BAA; compliance depends on our configuration (hosting, access control, storage, consent), which is pilot work. |
| Long sessions? | Above 120 turns the Coder works in 80-turn windows with 10 turns of context. |
