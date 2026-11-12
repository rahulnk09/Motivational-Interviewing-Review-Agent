# MIRA screening deck (v2)

A 15-slide deck for the hackathon screening (≈ 8:40 of slides + a 2:45 walkthrough of the saved report). It's built with reveal.js and Chart.js, and every library and font lives in `vendor/`, so it runs **fully offline**.

- Plan and evidence for every slide: [`plan.md`](plan.md)
- What to say, timings, demo script and Q&A: [`speaker_notes.md`](speaker_notes.md) (also in the speaker view, key **S**)
- PDF backup: `export/MIRA_deck_v2.pdf`

## Present

```powershell
cd presentation_v2
npm install      # first time only: installs playwright-core for tests / PDF (the deck itself needs nothing)
npm start        # → http://127.0.0.1:8643/
```

| Key | Action |
|---|---|
| → / Space / clicker | Next (slide 6 builds in 7 steps) |
| S | Speaker view with notes and timer (allow pop-ups) |
| F | Full screen |
| Esc | Slide overview |

You can also open `index.html` directly in a browser, but the speaker view works best over `npm start`.

## Test and export

```powershell
npm test         # headless Edge/Chrome: screenshots of every slide in test-output/ + layout checks
npm run pdf      # export/MIRA_deck_v2.pdf (15 pages, all build steps shown)
```

`npm test` fails if the deck doesn't have 15 slides, if content leaves the canvas, runs into the footer or escapes its card, if text overlaps or is smaller than 16 px, if an icon, font, chart or image doesn't render, if the browser logs an error, or if the print/PDF view is broken.

## Refresh the app screenshots (slide 7)

The screenshots show the **saved** Mia report, which is exactly what the demo opens. No Azure calls are needed.

```powershell
# from the repository root
uv run streamlit run mi_project/app/streamlit_app.py --server.headless true --server.port 8517
# in another terminal
cd presentation_v2; npm run shots
```

## Edit

| What | Where |
|---|---|
| Slide text, layout, speaker notes | `index.html` (one `<section>` per slide, notes in `<aside class="notes">`) |
| Colours, fonts, shared components | `css/deck.css` (same design system as v1) |
| Per-slide layout | `css/slides.css` |
| Heatmaps (slide 11), κ dumbbells (slide 12), score chart (slide 13) | data attributes in `index.html`, rendering in `js/deck.js` |

## Where the numbers come from

| Slide | Source |
|---|---|
| 3, 4, 6, 7 | Saved reports in `mi_project/data/output/reports/` (Mia: `Motivational_Interviewing_in_Action__Rol-7e38dc72-39-223.json`, Sal: `annomi_video_27-d2518c2b-0-end.json`) |
| 2, 12 | `mi_project/data/output/eval/coder/pairwise_kappa.json`, coder `summary.json` (`human_ceiling_kappa`, `agreement.multi_annotator`) |
| 9 | `mi_project/docs/evaluation_explained.md` §1, `AnnoMI/AnnoMI-full.csv` |
| 10 | `mi_project/data/output/eval/ingest/annomi-27.json`, `annomi-23.json` |
| 11 | `mi_project/data/output/eval/coder/gpt-5.4_low_36aca3fa/summary.json` → `agreement.all` |
| 13 | `mi_project/data/output/eval/supervisor/gpt-5.4_medium_1d9518c3/transcripts.csv`, `summary.json` |
| 14 | `cost_estimation.md` (measured rows only); code: `ingest._extract_audio`, `clients.py`, `llm.py` (`store=False`) |
