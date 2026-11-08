// Minimal static server for the deck (the speaker-notes window and fonts behave better over http than file://).
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { dirname, extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const TYPES = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".pdf": "application/pdf",
};

export function startServer(port = Number(process.env.PORT) || 8642) {
  const server = createServer(async (req, res) => {
    try {
      const path = decodeURIComponent(new URL(req.url, "http://x").pathname);
      let file = normalize(join(root, path === "/" ? "index.html" : path));
      if (!file.startsWith(root + sep) && file !== root) throw Object.assign(new Error("forbidden"), { code: 403 });
      if ((await stat(file)).isDirectory()) file = join(file, "index.html");
      const body = await readFile(file);
      res.writeHead(200, { "Content-Type": TYPES[extname(file).toLowerCase()] || "application/octet-stream", "Cache-Control": "no-cache" });
      res.end(body);
    } catch (err) {
      res.writeHead(err.code === 403 ? 403 : 404);
      res.end(err.code === 403 ? "Forbidden" : "Not found");
    }
  });
  return new Promise((resolve) => server.listen(port, "127.0.0.1", () => resolve(server)));
}

if (process.argv[1] && fileURLToPath(import.meta.url).toLowerCase() === normalize(process.argv[1]).toLowerCase()) {
  const server = await startServer();
  const { port } = server.address();
  console.log(`MIRA deck: http://127.0.0.1:${port}/   (S = speaker notes, F = fullscreen, Esc = overview)`);
}
