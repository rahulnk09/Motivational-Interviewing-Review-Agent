## Cost estimate per review (USD, Global Standard, pay-as-you-go)

Prices come from the official Azure pricing pages for Content Understanding and Azure OpenAI. Token counts come from your two saved reports in `reports`.

### Unit prices used

| Resource | Meter | Price |
|---|---|---|
| Content Understanding | Audio content extraction | $0.36 per hour of audio |
| Content Understanding | Standard contextualization (audio = 100k tokens per hour) | $1 per 1M tokens |
| Content Understanding | Field extraction (the 3 analyzer fields) | Billed as gpt-5.4-mini tokens, see below |
| gpt-5.4-mini (CU fields) | Input / cached input / output | $0.75 / $0.08 / $4.50 per 1M |
| gpt-5.4 (Coder and Supervisor) | Input / cached input / output | $2.50 / $0.25 / $15 per 1M |
| ffmpeg, LangGraph, Streamlit, Python metrics | Run locally | $0 |

Reasoning tokens are billed as output tokens, and the output counts in the reports already include them.

### Measured: the two sample runs (about 3 minutes of audio each)

| Component | Role-play (0.052 h, no cache) | AnnoMI 27 (0.059 h, cached prompt) |
|---|---|---|
| CU audio extraction | $0.0187 | $0.0212 |
| CU contextualization (5.2k / 5.9k tokens) | $0.0052 | $0.0059 |
| CU field extraction (gpt-5.4-mini, ~2.6k in, ~0.1k out) | $0.0024 | $0.0026 |
| **Content Understanding subtotal** | **$0.026** | **$0.030** |
| Coder (gpt-5.4: 4.2k in, 0.6–1.1k out) | $0.0266 | $0.0107 |
| Supervisor (gpt-5.4: 3.6k in, 1.9–2.4k out) | $0.0379 | $0.0396 |
| **LLM subtotal** | **$0.065** | **$0.050** |
| **Total per run** | **≈ $0.09** | **≈ $0.08** |

About 70% of the cost is output tokens from gpt-5.4, mostly reasoning and JSON. Audio transcription is about 30%.

### Extrapolated: a realistic session length

These figures are my own scaling, not measurements. I assumed roughly 300–400 transcript tokens per minute. I assumed a fixed prompt of about 3k tokens. I assumed Coder output grows with the number of turns, and Supervisor output stays near 3k.

| Component | 30 min | 60 min |
|---|---|---|
| CU audio extraction | $0.18 | $0.36 |
| CU contextualization | $0.05 | $0.10 |
| CU field extraction (mini) | ~$0.01 | ~$0.02 |
| Coder (windowed above 120 turns, ~10k output) | ~$0.20 | ~$0.40 |
| Supervisor (~18k in, ~3.5k out) | ~$0.09 | ~$0.12 |
| **Total** | **≈ $0.50 (range $0.40–0.70)** | **≈ $1.00 (range $0.80–1.30)** |

### Factors that change the number

- **CU cache:** a re-run on the same clip skips CU. You then pay only the LLM part, about $0.05–0.07 for a short clip and about $0.30 for 30 minutes.
- **Prompt caching:** this saves about 10% on the Coder when the cache hits. The first run, as in the role-play report, gets no cache.
- **Deployment type:** Data Zone is about 10% higher. Batch is 50% lower but doesn't suit interactive use.
- **Reasoning effort:** the Supervisor on `medium` produced 0.9–1.5k reasoning tokens. Setting `low` would save about $0.01–0.02 per run, but the evaluation scores would need re-checking.
- **Coder on gpt-5.4-mini:** this cuts Coder cost by about 70%, but agreement with experts drops (see §10 of the README).
- **Planned 3× majority-vote Coder (Phase 8):** this triples Coder cost, which is about $0.60 for a 30-minute session.
- **Not included:** evaluation runs (`eval-coder` over 27 transcripts is roughly $1–2 each), Azure hosting, storage, and tax or agreement discounts.

**Rule of thumb:** about $0.015 per audio minute, or roughly 1–2 cents per minute of recording.

I haven't verified the 30- and 60-minute rows against a real long recording. Running one through `uv run mi-review run` would give real token counts to replace them.

