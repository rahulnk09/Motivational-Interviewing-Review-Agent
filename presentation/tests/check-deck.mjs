// Automated visual + structural checks for the MIRA deck (headless Edge/Chrome via playwright-core).
// Usage: npm test            -> screenshots in test-output/, report in test-output/report.json, exit 1 on issues
import { chromium } from "playwright-core";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "../scripts/serve.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = join(root, "test-output");
mkdirSync(outDir, { recursive: true });
const EXPECTED_SLIDES = 25;

export async function launchBrowser() {
  for (const channel of ["msedge", "chrome"]) {
    try { return await chromium.launch({ channel, headless: true }); } catch { /* try next */ }
  }
  throw new Error("Neither Microsoft Edge nor Google Chrome is installed.");
}

// Runs inside the page for the current slide; returns a list of human-readable issues.
function inspectSlide() {
  const W = 1920, H = 1080, BODY_BOTTOM = 1080 - 96, TOL = 2;
  const slide = Reveal.getCurrentSlide();
  const issues = [];
  const name = (el) => {
    const cls = typeof el.className === "string" && el.className ? "." + el.className.trim().split(/\s+/).join(".") : "";
    const txt = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
    return `<${el.tagName.toLowerCase()}${cls}> "${txt}"`;
  };
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const els = [...slide.querySelectorAll("*")].filter((el) => !el.closest("aside.notes") && !el.ownerSVGElement && visible(el));
  const footer = slide.querySelector(".deck-footer");

  // 1) nothing outside the 1920x1080 canvas; body content must stay above the footer
  for (const el of els) {
    if (el.closest(".ribbon, .motif")) continue;
    const r = el.getBoundingClientRect();
    if (r.left < -TOL || r.top < -TOL || r.right > W + TOL || r.bottom > H + TOL) issues.push(`outside canvas: ${name(el)} [${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)}]`);
    if (footer && !footer.contains(el) && r.bottom > BODY_BOTTOM + TOL && !el.classList.contains("frame")) issues.push(`runs into footer: ${name(el)} bottom=${Math.round(r.bottom)}`);
  }

  // 2) children escaping their boxed parents (cards, bubbles, nodes...)
  const BOX = ".card,.bubble,.pn,.tier,.sw,.dd,.kp,.promise,.pt,.cv,.c5,.rr,.ba-r,.io-card,.ch,.fs-row,.pb,.price,.sp,.stop,.node,.callout,.fix,.better,.chip,.ts,.json,.sig4 > div,.step,.io,.shot,.hook-stat";
  const IGNORE = ".pick-badge,.ribbon,.art,.tick";
  for (const box of slide.querySelectorAll(BOX)) {
    if (!visible(box)) continue;
    const b = box.getBoundingClientRect();
    for (const d of box.querySelectorAll("*")) {
      if (!visible(d) || d.ownerSVGElement || d.closest(IGNORE)) continue;
      const r = d.getBoundingClientRect();
      if (r.left < b.left - TOL || r.right > b.right + TOL || r.top < b.top - TOL || r.bottom > b.bottom + TOL) {
        issues.push(`escapes box: ${name(d)} from ${name(box)}`);
        break;
      }
    }
    const cs = getComputedStyle(box);
    if (box.scrollHeight > box.clientHeight + TOL && cs.overflow !== "visible" && !box.matches(".shot")) issues.push(`clipped content: ${name(box)}`);
  }

  // 3) text: minimum size and overlapping text leaves
  const leaves = els.filter((el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && !el.classList.contains("ms"));
  for (const el of leaves) {
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 16 - 0.01) issues.push(`font < 16px (${fs}px): ${name(el)}`);
  }
  const textRects = leaves.map((el) => {
    const range = document.createRange();
    const rects = [];
    for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) { range.selectNodeContents(n); rects.push(...range.getClientRects()); }
    return { el, rects };
  });
  for (let i = 0; i < textRects.length; i++) for (let j = i + 1; j < textRects.length; j++) {
    const A = textRects[i], B = textRects[j];
    if (A.el.contains(B.el) || B.el.contains(A.el)) continue;
    const hit = A.rects.some((a) => B.rects.some((b) => {
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      return w > 4 && h > 4 && w * h > 0.15 * Math.min(a.width * a.height, b.width * b.height);
    }));
    if (hit) issues.push(`text overlap: ${name(A.el)} × ${name(B.el)}`);
  }

  // 4) icons resolved (an unknown ligature renders as a wide word)
  for (const ic of slide.querySelectorAll(".ms")) {
    if (!visible(ic)) continue;
    const range = document.createRange();
    range.selectNodeContents(ic);
    const fs = parseFloat(getComputedStyle(ic).fontSize), w = range.getBoundingClientRect().width;
    if (w > fs * 1.35) issues.push(`icon not rendered: "${ic.textContent.trim()}" (width ${Math.round(w)} vs ${fs}px)`);
  }

  // 5) charts and images
  for (const cv of slide.querySelectorAll("canvas")) {
    const ch = Chart.getChart(cv);
    if (!ch) issues.push(`chart not created: #${cv.id}`);
    else if (cv.width < 50 || cv.height < 50) issues.push(`chart too small: #${cv.id} ${cv.width}x${cv.height}`);
  }
  for (const img of slide.querySelectorAll("img")) if (!img.complete || img.naturalWidth === 0) issues.push(`image not loaded: ${img.getAttribute("src")}`);
  return issues;
}

async function main() {
  const server = await startServer(0);
  const base = `http://127.0.0.1:${server.address().port}/`;
  const browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const runtime = [];
  page.on("console", (m) => m.type() === "error" && runtime.push(`console: ${m.text()}`));
  page.on("pageerror", (e) => runtime.push(`page error: ${e.message}`));
  page.on("response", (r) => r.status() >= 400 && runtime.push(`HTTP ${r.status()}: ${r.url()}`));

  await page.goto(base, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.dataset.ready === "1");
  await page.evaluate(() => document.fonts.ready);
  const fonts = await page.evaluate(() => ["Inter", "Fraunces", "JetBrains Mono", "Material Symbols Rounded"]
    .filter((f) => !document.fonts.check(`32px "${f}"`)));
  const total = await page.evaluate(() => Reveal.getTotalSlides());

  const report = { total, missingFonts: fonts, runtime, slides: [] };
  for (let i = 0; i < total; i++) {
    await page.evaluate((h) => Reveal.slide(h, 0, 99), i);
    await page.waitForTimeout(1300);
    const id = await page.evaluate(() => Reveal.getCurrentSlide().id);
    const issues = await page.evaluate(inspectSlide);
    const file = `slide-${String(i + 1).padStart(2, "0")}.png`;
    await page.screenshot({ path: join(outDir, file) });
    report.slides.push({ n: i + 1, id, issues, screenshot: file });
  }

  // Print view (used by the PDF export): every page must keep the full 1920x1080 layout.
  const pp = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await pp.goto(base + "?print-pdf", { waitUntil: "networkidle" });
  await pp.waitForFunction(() => document.body.dataset.ready === "1");
  await pp.waitForTimeout(1200);
  report.print = await pp.evaluate((expected) => {
    const out = [];
    const pages = [...document.querySelectorAll(".pdf-page")];
    if (pages.length !== expected) out.push(`print view: expected ${expected} pages, found ${pages.length}`);
    pages.forEach((pg, i) => {
      const s = pg.querySelector("section"), top = pg.getBoundingClientRect().top;
      if (Math.round(s.getBoundingClientRect().height) !== 1080) out.push(`print page ${i + 1}: section height ${Math.round(s.getBoundingClientRect().height)} (expected 1080)`);
      const f = s.querySelector(".deck-footer");
      if (f && f.getBoundingClientRect().top - top < 980) out.push(`print page ${i + 1}: footer not at bottom`);
      const t = s.querySelector(".title, .hook-title, .hero-mark, .thanks");
      if (t && t.getBoundingClientRect().top - top < 0) out.push(`print page ${i + 1}: content pushed above page`);
      for (const cv of s.querySelectorAll("canvas")) if (!Chart.getChart(cv)) out.push(`print page ${i + 1}: chart #${cv.id} missing`);
      for (const fr of s.querySelectorAll(".fragment")) if (getComputedStyle(fr).opacity !== "1") { out.push(`print page ${i + 1}: hidden fragment`); break; }
    });
    return out;
  }, EXPECTED_SLIDES);
  for (const n of [9, 17, 19, 24]) {
    const pg = (await pp.$$(".pdf-page"))[n - 1];
    if (pg) await pg.screenshot({ path: join(outDir, `print-${String(n).padStart(2, "0")}.png`) });
  }
  await browser.close();
  server.close();

  writeFileSync(join(outDir, "report.json"), JSON.stringify(report, null, 2));
  const problems = [];
  if (total !== EXPECTED_SLIDES) problems.push(`expected ${EXPECTED_SLIDES} slides, found ${total}`);
  if (fonts.length) problems.push(`fonts not loaded: ${fonts.join(", ")}`);
  problems.push(...runtime);
  for (const s of report.slides) for (const msg of s.issues) problems.push(`slide ${s.n} (${s.id}): ${msg}`);
  problems.push(...report.print);

  console.log(`Checked ${total} slides · screenshots in test-output/`);
  if (problems.length) {
    console.log(`\n${problems.length} issue(s):`);
    for (const p of problems) console.log("  ✗ " + p);
    process.exitCode = 1;
  } else {
    console.log("✓ All checks passed");
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url).toLowerCase() === resolve(process.argv[1]).toLowerCase()) await main();
