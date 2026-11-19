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
  if (filePath.endsWith(".yml") || filePath.endsWith(".yaml")) return "yaml";
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

  // API: Lista completa de archivos fuente entregables (incluye .github/workflows/release.yml)
  app.get("/api/deliverables", (_req, res) => {
    const files = collectDeliverables(DELIVERABLES_DIR);
    const releaseWorkflowPath = path.resolve(__dirname, ".github", "workflows", "release.yml");
    if (fs.existsSync(releaseWorkflowPath)) {
      const wfContent = fs.readFileSync(releaseWorkflowPath, "utf-8");
      files.push({
        path: ".github/workflows/release.yml",
        name: "release.yml",
        module: "docs",
        language: "yaml",
        lines: wfContent.split("\n").length,
        content: wfContent,
      });
    }
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

  // API: Comparación de versión instalada vs repositorio GitHub Releases
  app.post("/api/pos/updates/check", async (req, res) => {
    const { installedVersion = "1.0.0", githubRepo = "", simulatedRemoteVersion } = req.body ?? {};
    const parseVer = (v: string): [number, number, number] => {
      const m = String(v).trim().replace(/^v/i, "").match(/^(\d+)\.(\d+)\.(\d+)/);
      return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : [0, 0, 0];
    };
    const isGreater = (a: string, b: string) => {
      const pa = parseVer(a);
      const pb = parseVer(b);
      for (let i = 0; i < 3; i++) {
        if (pa[i] !== pb[i]) return pa[i] > pb[i];
      }
      return false;
    };

    if (simulatedRemoteVersion) {
      const cleanInstalled = String(installedVersion).replace(/^v/i, "");
      const cleanRemote = String(simulatedRemoteVersion).replace(/^v/i, "");
      const updateAvailable = isGreater(cleanRemote, cleanInstalled);
      return res.json({
        status: updateAvailable ? "update_available" : "up_to_date",
        currentVersion: cleanInstalled,
        latestVersion: cleanRemote,
        updateAvailable,
        message: updateAvailable
          ? `Nueva versión v${cleanRemote} disponible en el repositorio (tienes v${cleanInstalled}). Se sugiere actualización desatendida.`
          : `Tienes la versión más reciente instalada (v${cleanInstalled}).`,
      });
    }

    const repo = String(githubRepo).trim().replace(/^\/|\/$/g, "");
    if (!repo || !repo.includes("/")) {
      return res.status(400).json({
        status: "error",
        message: "Ingresa un repositorio válido con formato usuario/repositorio.",
      });
    }

    try {
      const ghRes = await fetch(`https://api.github.com/repos/${repo}/releases/latest`, {
        headers: {
          Accept: "application/vnd.github+json",
          "User-Agent": "NequiPayPOS-Console",
        },
      });
      if (!ghRes.ok) {
        return res.json({
          status: "error",
          currentVersion: installedVersion,
          latestVersion: installedVersion,
          updateAvailable: false,
          message: `GitHub API respondió HTTP ${ghRes.status} para ${repo}.`,
        });
      }
      const data = (await ghRes.json()) as { tag_name?: string; body?: string };
      const remoteVer = String(data.tag_name || installedVersion).replace(/^v/i, "");
      const cleanInstalled = String(installedVersion).replace(/^v/i, "");
      const updateAvailable = isGreater(remoteVer, cleanInstalled);
      return res.json({
        status: updateAvailable ? "update_available" : "up_to_date",
        currentVersion: cleanInstalled,
        latestVersion: remoteVer,
        updateAvailable,
        releaseNotes: data.body || "",
        message: updateAvailable
          ? `Nueva versión v${remoteVer} disponible en el repositorio (tienes v${cleanInstalled}). Se sugiere actualización desatendida.`
          : `Tienes la versión más reciente instalada (v${cleanInstalled}).`,
      });
    } catch (err) {
      return res.json({
        status: "error",
        currentVersion: installedVersion,
        latestVersion: installedVersion,
        updateAvailable: false,
        message: `Error consultando GitHub: ${err instanceof Error ? err.message : "red"}`,
      });
    }
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
