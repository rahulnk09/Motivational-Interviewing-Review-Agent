// Captures fresh screenshots of the MIRA Streamlit app showing a saved report (no Azure calls).
// 1) uv run streamlit run mi_project/app/streamlit_app.py --server.headless true --server.port 8517
// 2) npm run shots            (APP_URL and REPORT can be overridden with environment variables)
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "../tests/check-deck.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "assets", "img");
mkdirSync(out, { recursive: true });
const APP = process.env.APP_URL || "http://localhost:8517/";
const REPORT = process.env.REPORT || "Motivational_Interviewing_in_Action__Rol-7e38dc72-39-223";

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.5 });
await page.goto(APP, { waitUntil: "domcontentloaded" });
await page.getByRole("heading", { name: /MIRA/ }).first().waitFor({ timeout: 90000 });
const group = (text) => page.locator('[data-testid="stButtonGroup"] button', { hasText: text }).first();

// Sidebar: Source = Saved report -> pick the report -> Open
await group("Saved report").click();
const openList = page.locator('[data-testid="stSelectbox"] button[aria-haspopup="listbox"]').first();
await openList.waitFor();
await page.waitForTimeout(2500); // let the rerun after switching source settle, or it closes the list again
await openList.click();
await page.waitForTimeout(1000);
await page.locator('[role="option"]', { hasText: REPORT }).first().click();
await page.waitForTimeout(800);
await page.getByRole("button", { name: /Open report/ }).click();
await page.getByText("MI proficiency score").waitFor({ timeout: 60000 });
await page.waitForTimeout(2500);

// Clean, wide shots: hide the sidebar and Streamlit's own header/toolbar
await page.addStyleTag({ content: '[data-testid="stSidebar"], header[data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; }' });
await page.waitForTimeout(1200);

const main = page.locator('[data-testid="stMain"]');
const shot = async (name) => {
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(out, name), fullPage: false });
  console.log("saved", name);
};

// Overview: wait until the video has a decoded frame (it opens at the clip start), then shoot from the title down
await page.waitForFunction(() => { const v = document.querySelector("video"); return v && v.readyState >= 2; }, null, { timeout: 30000 }).catch(() => console.log("video frame not ready"));
await page.waitForTimeout(1500);
await page.getByRole("heading", { name: /MIRA/ }).first().evaluate((el) => el.scrollIntoView({ block: "start" }));
await shot("app-overview.png");

const openTab = async (label, name, prepare) => {
  const tab = page.getByRole("tab", { name: new RegExp(label) });
  await tab.click();
  await page.waitForTimeout(1000);
  if (prepare) await prepare();
  await tab.evaluate((el) => el.scrollIntoView({ block: "start" }));
  await shot(name);
};

await openTab("Feedback", "app-feedback.png");
await openTab("Scorecard", "app-scorecard.png");
await openTab("Transcript", "app-transcript.png", async () => {
  await group("Change talk").click();
  await page.waitForTimeout(1500);
});
await openTab("Session dynamics", "app-dynamics.png");
await openTab("Run details", "app-run.png");

await browser.close();
