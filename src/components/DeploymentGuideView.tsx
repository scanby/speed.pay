import React, { useState } from "react";
import { Check, Copy, ShieldCheck, Terminal } from "lucide-react";

const SERVER_PYINSTALLER_CMD = `cd deliverables\\server
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --console ^
  --name "NequiPayPOS_Server" ^
  --hidden-import="uvicorn.logging" ^
  --hidden-import="uvicorn.loops.auto" ^
  --hidden-import="uvicorn.protocols.http.auto" ^
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
  agent_tray.py`;

const FIREWALL_POWERSHELL_CMD = `New-NetFirewallRule -DisplayName "NequiPay POS LAN Server (TCP 8000)" \`
  -Direction Inbound -Protocol TCP -LocalPort 8000 \`
  -Action Allow -Profile Private,Domain`;

const NSSM_SERVICE_CMD = `nssm install NequiPayPOS_Server "C:\\NequiPayPOS\\NequiPayPOS_Server.exe"
nssm set NequiPayPOS_Server AppDirectory "C:\\NequiPayPOS"
nssm set NequiPayPOS_Server Start SERVICE_AUTO_START
nssm start NequiPayPOS_Server`;

const CHECKLIST_ITEMS = [
  "Perfil de red en Windows Servidor configurado como Red Privada y regla TCP 8000 aplicada.",
  "IP estática o reserva DHCP por MAC asignada al PC Servidor (ej. 192.168.1.50).",
  "Primer inicio ejecutado para crear el usuario Administrador (bcrypt + JWT HttpOnly).",
  "Cuentas Nequi vinculadas por alias y usuarios Cajero creados con permisos restringidos al día.",
  "Teléfonos Android con Acceso a Notificaciones habilitado y Batería en Sin Restricciones.",
  "QR escaneado desde la App Android y prueba de sonido ($15.000) escuchada en cajas Windows 7.",
  "Prueba de corte Wi-Fi en Android verificada: encolado en Room DB y sincronización cronológica WorkManager sin duplicados.",
];

export const DeploymentGuideView: React.FC = () => {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<Record<number, boolean>>({});

  async function copyCommand(id: string, text: string) {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1600);
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bloque 1: PyInstaller Servidor */}
        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-[#DA0081]" />
              <span>01. Empaquetado Servidor (Windows 10/11 · Python 3.11)</span>
            </h2>
            <button
              type="button"
              onClick={() => copyCommand("srv", SERVER_PYINSTALLER_CMD)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 hover:bg-slate-50"
            >
              {copiedId === "srv" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedId === "srv" ? "Copiado" : "Copiar"}</span>
            </button>
          </div>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{SERVER_PYINSTALLER_CMD}</code>
          </pre>
        </section>

        {/* Bloque 2: PyInstaller Cliente Windows 7 */}
        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-[#DA0081]" />
              <span>02. Empaquetado Cliente Windows 7 SP1 (Python 3.8.10)</span>
            </h2>
            <button
              type="button"
              onClick={() => copyCommand("win7", WIN7_PYINSTALLER_CMD)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 hover:bg-slate-50"
            >
              {copiedId === "win7" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedId === "win7" ? "Copiado" : "Copiar"}</span>
            </button>
          </div>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{WIN7_PYINSTALLER_CMD}</code>
          </pre>
          <p className="text-xs text-slate-600">
            Acceso directo en <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">shell:startup</code>:{" "}
            <code className="font-mono bg-slate-100 px-1 py-0.5 rounded">
              NequiPayPOS_Client_Win7.exe --server http://192.168.1.50:8000
            </code>
          </p>
        </section>

        {/* Bloque 3: Firewall y Red Estática */}
        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              03. Firewall Windows 10/11 y Servicio 24/7 (NSSM)
            </h2>
            <button
              type="button"
              onClick={() => copyCommand("fw", `${FIREWALL_POWERSHELL_CMD}\n\n${NSSM_SERVICE_CMD}`)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded border border-slate-300 hover:bg-slate-50"
            >
              {copiedId === "fw" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedId === "fw" ? "Copiado" : "Copiar"}</span>
            </button>
          </div>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{FIREWALL_POWERSHELL_CMD}</code>
          </pre>
          <pre className="p-3 rounded-md bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto leading-relaxed">
            <code>{NSSM_SERVICE_CMD}</code>
          </pre>
        </section>

        {/* Bloque 4: Lista de verificación 24/7 */}
        <section className="bg-white border border-slate-200 rounded-lg p-5 space-y-3">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>04. Lista de Verificación Operación 24/7</span>
          </h2>
          <p className="text-xs text-slate-600">
            Marca cada punto antes de poner las cajas registradoras en producción continua.
          </p>
          <div className="divide-y divide-slate-100">
            {CHECKLIST_ITEMS.map((item, idx) => (
              <label
                key={idx}
                className="py-2.5 flex items-start gap-3 text-xs text-slate-700 cursor-pointer"
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
        </section>
      </div>
    </div>
  );
};
