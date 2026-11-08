# MIRA hackathon deck

A 25-slide, 15-minute deck built with reveal.js and Chart.js. All libraries and fonts are stored in `vendor/`, so it runs **offline**, with no CDN.

## Present

```powershell
cd presentation
npm install      # first time only (also copies libraries into vendor/)
npm start        # → http://127.0.0.1:8642/
```

| Key | Action |
|---|---|
| → / Space / clicker | Next step (some slides reveal in steps: 2, 10, 24) |
| S | Speaker view with notes and a timer (allow pop-ups) |
| F | Full screen |
| Esc | Slide overview |

The PDF backup (`export/MIRA_deck.pdf`) has one slide per page with every step revealed. Use it if a browser isn't available.

## Edit

| What | Where |
|---|---|
| Slide text and layout | `index.html` (one `<section>` per slide, speaker notes in `<aside class="notes">`) |
| Colours, fonts, shared components | `css/deck.css` |
| Per-slide layout | `css/slides.css` (grouped by slide number) |
| Chart data (slides 9, 16, 17, 19), footer, motif | `js/deck.js` |
| Demo screenshots (slide 14) | `assets/img/` |

## Test and export

```powershell
npm test         # headless Edge/Chrome: screenshots of every slide in test-output/ + layout checks
npm run pdf      # export/MIRA_deck.pdf (25 pages)
```

`npm test` fails if any of these happen:
- the deck doesn't have 25 slides
- content runs off a slide or into the footer, or escapes its card
- text overlaps, or is smaller than 16 px
- an icon name doesn't render, or a font isn't loaded
- a chart or image doesn't render
- the browser logs a console error or a request fails
