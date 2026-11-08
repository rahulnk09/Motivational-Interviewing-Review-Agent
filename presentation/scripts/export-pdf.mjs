// Exports the deck to a 25-page PDF (one slide per page, all fragments visible) via reveal.js print view.
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { startServer } from "./serve.mjs";
import { launchBrowser } from "../tests/check-deck.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "export", "MIRA_deck.pdf");
mkdirSync(dirname(out), { recursive: true });

const server = await startServer(0);
const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(`http://127.0.0.1:${server.address().port}/?print-pdf`, { waitUntil: "networkidle" });
await page.waitForFunction(() => document.body.dataset.ready === "1");
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(1500);
await page.pdf({ path: out, printBackground: true, preferCSSPageSize: true });
await browser.close();
server.close();

const pages = (readFileSync(out, "latin1").match(/\/Type\s*\/Page[^s]/g) || []).length;
console.log(`PDF written: export/MIRA_deck.pdf (${pages} pages)`);
if (pages !== 25) { console.error(`Expected 25 pages, got ${pages}`); process.exitCode = 1; }
