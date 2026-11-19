import express from "express";
import fs from "fs";
import path from "path";
import crypto from "crypto";
import { fileURLToPath } from "url";
import { createServer as createViteServer } from "vite";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DELIVERABLES_DIR = path.resolve(__dirname, "deliverables");

interface DeliverableFile {
  path: string;
  name: string;
  module: "server" | "client_win7" | "android_app" | "docs";
  language: string;
  lines: number;
  content: string;
}

function detectLanguage(filePath: string): string {
  if (filePath.endsWith(".py")) return "python";
  if (filePath.endsWith(".kt") || filePath.endsWith(".kts")) return "kotlin";
  if (filePath.endsWith(".xml")) return "xml";
  if (filePath.endsWith(".html")) return "html";
  if (filePath.endsWith(".css")) return "css";
  if (filePath.endsWith(".js")) return "javascript";
  if (filePath.endsWith(".md")) return "markdown";
  return "text";
}

function collectDeliverables(dir: string, baseDir: string = dir): DeliverableFile[] {
  if (!fs.existsSync(dir)) return [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: DeliverableFile[] = [];

  for (const entry of entries) {
    if (entry.name === "__pycache__" || entry.name.endsWith(".pyc")) {
      continue;
    }
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectDeliverables(fullPath, baseDir));
    } else if (entry.isFile()) {
      const relPath = path.relative(baseDir, fullPath).replace(/\\/g, "/");
      const topFolder = relPath.split("/")[0] as DeliverableFile["module"];
      const content = fs.readFileSync(fullPath, "utf-8");
      files.push({
        path: relPath,
        name: entry.name,
        module: ["server", "client_win7", "android_app", "docs"].includes(topFolder)
          ? topFolder
          : "docs",
        language: detectLanguage(relPath),
        lines: content.split("\n").length,
        content,
      });
    }
  }
  return files.sort((a, b) => a.path.localeCompare(b.path));
}

async function startServer() {
  const app = express();
  app.use(express.json());

  // API: Lista completa de archivos fuente entregables
  app.get("/api/deliverables", (_req, res) => {
    const files = collectDeliverables(DELIVERABLES_DIR);
    res.json({
      totalFiles: files.length,
      files,
    });
  });

  // API: Hash SHA-256 idempotente real en servidor Node para pruebas del simulador
  app.post("/api/pos/hash", (req, res) => {
    const { accountId, senderName, amountCop, capturedAtIso, windowSeconds = 120 } = req.body ?? {};
    const epochSeconds = Math.floor(new Date(capturedAtIso || Date.now()).getTime() / 1000);
    const timeBucket = Math.floor(epochSeconds / Math.max(1, Number(windowSeconds)));
    const normalizedSender = String(senderName || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
    const normalizedAmount = Number(amountCop || 0).toFixed(2);
    const payload = `${accountId}|${normalizedSender}|${normalizedAmount}|${timeBucket}`;
    const hash = crypto.createHash("sha256").update(payload, "utf8").digest("hex");
    res.json({ hash, timeBucket, payload });
  });

  // API: Heartbeat LAN para el monitor POS en tiempo real
  app.get("/api/pos/heartbeat", (_req, res) => {
    res.json({
      status: "online",
      serverTime: new Date().toISOString(),
      walMode: true,
    });
  });

  const isProd = process.env.NODE_ENV === "production";
  if (!isProd) {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distDir = path.resolve(__dirname, "dist");
    app.use(express.static(distDir));
    app.get("/{*splat}", (_req, res) => {
      res.sendFile(path.join(distDir, "index.html"));
    });
  }

  const PORT = Number(process.env.PORT) || 3000;
  app.listen(PORT, "0.0.0.0", () => {
    console.log(`NequiPay POS Console & Deliverables server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
