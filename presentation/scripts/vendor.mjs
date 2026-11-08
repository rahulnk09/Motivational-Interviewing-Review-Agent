// Copies the runtime libraries and fonts from node_modules into vendor/ so the deck runs offline.
import { cpSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const nm = join(root, "node_modules");
const out = join(root, "vendor");

const files = [
  ["reveal.js/dist/reset.css", "reveal/reset.css"],
  ["reveal.js/dist/reveal.css", "reveal/reveal.css"],
  ["reveal.js/dist/reveal.js", "reveal/reveal.js"],
  ["reveal.js/plugin/notes/notes.js", "reveal/notes.js"],
  ["chart.js/dist/chart.umd.min.js", "chart/chart.umd.min.js"],
  ["material-symbols/material-symbols-rounded.woff2", "fonts/material-symbols-rounded.woff2"],
  ["@fontsource/inter/files/inter-latin-400-normal.woff2", "fonts/inter-400.woff2"],
  ["@fontsource/inter/files/inter-latin-500-normal.woff2", "fonts/inter-500.woff2"],
  ["@fontsource/inter/files/inter-latin-700-normal.woff2", "fonts/inter-700.woff2"],
  ["@fontsource/fraunces/files/fraunces-latin-600-normal.woff2", "fonts/fraunces-600.woff2"],
  ["@fontsource/fraunces/files/fraunces-latin-600-italic.woff2", "fonts/fraunces-600-italic.woff2"],
  ["@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2", "fonts/jetbrains-mono-400.woff2"],
  ["@fontsource/jetbrains-mono/files/jetbrains-mono-latin-500-normal.woff2", "fonts/jetbrains-mono-500.woff2"],
];

rmSync(out, { recursive: true, force: true });
for (const [src, dest] of files) {
  const target = join(out, dest);
  mkdirSync(dirname(target), { recursive: true });
  cpSync(join(nm, src), target);
}
console.log(`Vendored ${files.length} files into vendor/`);
