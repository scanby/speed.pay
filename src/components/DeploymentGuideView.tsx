import React, { useState } from "react";
import { Check, Copy, GitBranch, MonitorCog, ShieldCheck, Terminal, Wifi } from "lucide-react";

const GIT_RELEASE_CMD = `git add .
git commit -m "chore: preparar release v1.0.0"
git tag v1.0.0
git push origin main --tags`;

const SERVER_PYINSTALLER_CMD = `cd deliverables\\server
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --console ^
  --name "NequiPayPOS_Server_Win10_11" ^
  --paths "." ^
  --hidden-import="uvicorn.logging" ^
  --hidden-import="uvicorn.loops.auto" ^
  --hidden-import="uvicorn.protocols.http.auto" ^
  --hidden-import="uvicorn.lifespan.on" ^
  --hidden-import="engineio.async_drivers.asgi" ^
  --hidden-import="pyttsx3.drivers.sapi5" ^
  --add-data "..\\client_win7\\web_pos;client_win7\\web_pos" ^
  app\\main.py`;

const WIN7_PYINSTALLER_CMD = `cd deliverables\\client_win7
py -3.8 -m venv .venv38
.venv38\\Scripts\\activate
pip install -r requirements_win7.txt pyinstaller==5.13.2

pyinstaller --noconfirm --onefile --windowed ^
  --name "NequiPayPOS_Client_Win7" ^
  --paths "." ^
  --hidden-import="tkinter" ^
  --hidden-import="engineio.async_drivers.threading" ^
  agent_tray.py`;

const FIREWALL_AND_NSSM_CMD = `New-NetFirewallRule -DisplayName "NequiPay POS LAN Server (TCP 8000)" \`
  -Direction Inbound -Protocol TCP -LocalPort 8000 \`
  -Action Allow -Profile Private,Domain

nssm install NequiPayPOS_Server "C:\\NequiPayPOS\\NequiPayPOS_Server_Win10_11.exe"
nssm set NequiPayPOS_Server AppDirectory "C:\\NequiPayPOS"
nssm set NequiPayPOS_Server Start SERVICE_AUTO_START
nssm start NequiPayPOS_Server`;

const CHECKLIST_ITEMS = [
  "Tag v* publicado en Git y ejecutables .exe descargados desde GitHub Releases.",
  "Perfil de red en Windows Servidor configurado como Red Privada y regla TCP 8000 aplicada.",
  "IP estática o reserva DHCP por MAC asignada al PC Servidor (ej. 192.168.1.50).",
  "IP estática ingresada en el Panel de Configuración de cada Cliente Win7 (config.json).",
  "Primer inicio ejecutado para crear el usuario Administrador (bcrypt + JWT HttpOnly).",
  "Teléfonos Android con Acceso a Notificaciones habilitado y Batería en Sin Restricciones.",
  "QR escaneado desde Android y prueba de sonido ($15.000) verificada en cajas Windows 7.",
];

export const DeploymentGuideView: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<Record<number, boolean>>({});

  // Simulador interactivo del Panel de Configuración del Cliente Win7
  const [clientIp, setClientIp] = useState("192.168.1.50");
  const [clientPort, setClientPort] = useState(8000);
  const [posLabel, setPosLabel] = useState("Caja Principal");
  const [audioVolume, setAudioVolume] = useState(100);
  const [kioskMode, setKioskMode] = useState(true);
  const [autoOpen, setAutoOpen] = useState(true);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);

  async function copyCommand(id: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1600);
  }

  async function handleTestClientConnection() {
    const start = performance.now();
    try {
      const res = await fetch("/api/pos/heartbeat");
      const latency = Math.round(performance.now() - start);
      if (res.ok) {
        setTestResult({
          ok: true,
          text: `Endpoint /api/health alcanzable (${latency} ms) · Configurado hacia http://${clientIp}:${clientPort}`,
        });
      } else {
        setTestResult({ ok: false, text: `Error HTTP ${res.status}` });
      }
    } catch {
      setTestResult({ ok: false, text: "Sin respuesta del servidor local." });
    }
  }

  const generatedConfigJson = JSON.stringify(
    {
      server_ip: clientIp,
      server_port: clientPort,
      pos_label: posLabel,
      audio_volume: audioVolume,
      kiosk_mode: kioskMode,
      auto_open_browser: autoOpen,
    },
    null,
    2
  );

  return (
    <div className="space-y-6">
      {/* Fila 1: Git Release CI/CD + Simulador Panel de Configuración Win7 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-[#DA0081]" />
              <span>01. Git Release Automático (.exe Servidor y Cliente)</span>
            </h2>
            <button
              type="button"
              onClick={() => copyCommand("git", GIT_RELEASE_CMD)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 hover:bg-slate-50"
            >
              {copiedId === "git" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedId === "git" ? "Copiado" : "Copiar"}</span>
            </button>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            El workflow <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">.github/workflows/release.yml</code> compila ambos ejecutables en GitHub Actions al subir un tag <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">v*</code>:
          </p>
          <ul className="text-xs text-slate-700 space-y-1.5 list-disc pl-4">
            <li>
              <span className="font-mono font-semibold">NequiPayPOS_Server_Win10_11.exe</span> · Python 3.11 + FastAPI + TTS + Web POS embebido (Windows 10/11).
            </li>
            <li>
              <span className="font-mono font-semibold">NequiPayPOS_Client_Win7.exe</span> · Python 3.8.10 x86 + PyInstaller 5.13.2 (compatible Windows 7 SP1 32/64 bits).
            </li>
            <li>
              <span className="font-mono font-semibold">SHA256SUMS.txt</span> · Firmas de verificación adjuntas al Release.
            </li>
          </ul>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{GIT_RELEASE_CMD}</code>
          </pre>
        </section>

        {/* Vista previa interactiva del Panel Tkinter del Cliente Windows 7 */}
        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <MonitorCog className="w-4 h-4 text-[#DA0081]" />
              <span>02. Panel de Configuración Local del Cliente (Win7)</span>
            </h2>
            <span className="text-xs font-mono text-slate-500">config_window.py</span>
          </div>
          <p className="text-xs text-slate-600">
            Al abrir <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">NequiPayPOS_Client_Win7.exe</code> por primera vez o desde el icono de bandeja, el cliente muestra este panel para fijar la IP estática del PC Servidor en <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">config.json</code>.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                IP Estática del Servidor
              </label>
              <input
                type="text"
                value={clientIp}
                onChange={(e) => setClientIp(e.target.value)}
                className="w-full px-3 py-1.5 text-xs font-mono border border-slate-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Puerto TCP</label>
              <input
                type="number"
                value={clientPort}
                onChange={(e) => setClientPort(Number(e.target.value))}
                className="w-full px-3 py-1.5 text-xs font-mono border border-slate-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Nombre de esta Caja
              </label>
              <input
                type="text"
                value={posLabel}
                onChange={(e) => setPosLabel(e.target.value)}
                className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Volumen de Voz ({audioVolume}%)
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={audioVolume}
                onChange={(e) => setAudioVolume(Number(e.target.value))}
                className="w-full mt-1.5 accent-[#DA0081]"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-700">
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={kioskMode}
                onChange={(e) => setKioskMode(e.target.checked)}
                className="rounded border-slate-300 text-[#DA0081]"
              />
              <span>Abrir en modo Kiosco</span>
            </label>
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoOpen}
                onChange={(e) => setAutoOpen(e.target.checked)}
                className="rounded border-slate-300 text-[#DA0081]"
              />
              <span>Abrir monitor al iniciar Windows</span>
            </label>
          </div>

          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleTestClientConnection}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md border border-slate-300 hover:bg-slate-50"
            >
              <Wifi className="w-3.5 h-3.5 text-emerald-600" />
              <span>Probar Conexión</span>
            </button>
            <span className="text-[11px] font-mono text-slate-500 truncate">
              ~/.nequipos_client/config.json
            </span>
          </div>

          {testResult && (
            <div
              className={`p-2.5 rounded text-xs border ${
                testResult.ok
                  ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                  : "bg-red-50 border-red-200 text-red-800"
              }`}
            >
              {testResult.text}
            </div>
          )}

          <pre className="p-2.5 rounded bg-slate-900 text-slate-100 text-[11px] font-mono overflow-x-auto">
            <code>{generatedConfigJson}</code>
          </pre>
        </section>
      </div>

      {/* Fila 2: PyInstaller Manual + Firewall/NSSM + Checklist */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-[#DA0081]" />
              <span>03. Compilación Manual PyInstaller (Servidor y Win7)</span>
            </h2>
            <button
              type="button"
              onClick={() => copyCommand("pyi", `${SERVER_PYINSTALLER_CMD}\n\n${WIN7_PYINSTALLER_CMD}`)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 hover:bg-slate-50"
            >
              {copiedId === "pyi" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedId === "pyi" ? "Copiado" : "Copiar"}</span>
            </button>
          </div>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{SERVER_PYINSTALLER_CMD}</code>
          </pre>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{WIN7_PYINSTALLER_CMD}</code>
          </pre>
        </section>

        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              04. Firewall TCP 8000, NSSM y Lista 24/7
            </h2>
            <button
              type="button"
              onClick={() => copyCommand("fw", FIREWALL_AND_NSSM_CMD)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 hover:bg-slate-50"
            >
              {copiedId === "fw" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedId === "fw" ? "Copiado" : "Copiar"}</span>
            </button>
          </div>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{FIREWALL_AND_NSSM_CMD}</code>
          </pre>

          <div className="pt-2 border-t border-slate-200">
            <h3 className="text-xs font-semibold text-slate-900 flex items-center gap-1.5 mb-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Lista de Verificación Pre-Producción</span>
            </h3>
            <div className="divide-y divide-slate-100">
              {CHECKLIST_ITEMS.map((item, idx) => (
                <label
                  key={idx}
                  className="py-2 flex items-start gap-2.5 text-xs text-slate-700 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={Boolean(checked[idx])}
                    onChange={() => setChecked((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                    className="mt-0.5 rounded border-slate-300 text-[#DA0081]"
                  />
                  <span className={checked[idx] ? "line-through text-slate-400" : ""}>{item}</span>
                </label>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
