import React, { useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  KeyRound,
  Plus,
  RefreshCw,
  Send,
  Smartphone,
  Volume2,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  buildTtsPhrase,
  formatCop,
  montoALetras,
  parseNequiNotification,
  speakSpanishPosPhrase,
} from "../utils/posDomain";

export type UserRole = "ADMIN" | "CAJERO";

export interface PosAccount {
  id: number;
  alias: string;
  phoneNumber: string;
  deviceLabel: string;
  isActive: boolean;
}

export interface PosUser {
  id: number;
  username: string;
  fullName: string;
  role: UserRole;
  isActive: boolean;
}

export interface DepositRecord {
  id: number;
  idempotencyHash: string;
  accountId: number;
  accountAlias: string;
  senderName: string;
  amountCop: number;
  amountWords: string;
  ttsPhrase: string;
  rawNotification: string;
  source: "ANDROID_NOTIFICATION" | "MANUAL_TEST";
  capturedAt: string;
}

interface OfflineQueuedItem {
  localId: number;
  accountId: number;
  accountAlias: string;
  senderName: string;
  amountCop: number;
  rawNotification: string;
  capturedAt: string;
}

const INITIAL_ACCOUNTS: PosAccount[] = [
  { id: 1, alias: "Caja Principal", phoneNumber: "300 412 8890", deviceLabel: "Samsung A14 - Mostrador 1", isActive: true },
  { id: 2, alias: "Caja Express", phoneNumber: "311 890 2234", deviceLabel: "Motorola G23 - Barra", isActive: true },
];

const INITIAL_USERS: PosUser[] = [
  { id: 1, username: "admin", fullName: "Administrador General", role: "ADMIN", isActive: true },
  { id: 2, username: "cajero_turno1", fullName: "Laura Martínez", role: "CAJERO", isActive: true },
];

function buildInitialDeposits(): DepositRecord[] {
  const now = new Date();
  const todayBase = now.toISOString().slice(0, 10);
  const yesterdayDate = new Date(now.getTime() - 86400000).toISOString().slice(0, 10);

  return [
    {
      id: 104,
      idempotencyHash: "8f3c91a4b2d0e719c34a1109a56b8e02f4d198c2e6b7012a4f5e9c1b2d3a4f01",
      accountId: 1,
      accountAlias: "Caja Principal",
      senderName: "Carlos Mendoza",
      amountCop: 45000,
      amountWords: montoALetras(45000),
      ttsPhrase: buildTtsPhrase(45000),
      rawNotification: "Recibiste $45.000 de Carlos Mendoza en tu Nequi",
      source: "ANDROID_NOTIFICATION",
      capturedAt: `${todayBase}T10:14:22`,
    },
    {
      id: 103,
      idempotencyHash: "4a9e12b7c0d3f582a19b4402c87d1e35b2a094f6c1e8032b7d9a1c4e6f8b0a12",
      accountId: 2,
      accountAlias: "Caja Express",
      senderName: "María Fernanda Gómez",
      amountCop: 120500,
      amountWords: montoALetras(120500),
      ttsPhrase: buildTtsPhrase(120500),
      rawNotification: "Te enviaron $ 120.500 de María Fernanda Gómez.",
      source: "ANDROID_NOTIFICATION",
      capturedAt: `${todayBase}T09:42:08`,
    },
    {
      id: 102,
      idempotencyHash: "c21d45e8a7b9f013d45e6789a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9",
      accountId: 1,
      accountAlias: "Caja Principal",
      senderName: "Andrés Felipe Rojas",
      amountCop: 8000,
      amountWords: montoALetras(8000),
      ttsPhrase: buildTtsPhrase(8000),
      rawNotification: "Pago recibido por $8.000 de Andrés Felipe Rojas",
      source: "ANDROID_NOTIFICATION",
      capturedAt: `${yesterdayDate}T17:50:12`,
    },
  ];
}

const PRESET_NOTIFICATIONS = [
  "Recibiste $45.000 de Carlos Mendoza en tu Nequi",
  "Te enviaron $ 128.500 de Sofía Valentina Ortiz.",
  "Pago recibido por $15.000 de Distribuidora El Sol",
  "Enviaste $50.000 a Pedro Gómez (Debe ignorarse)",
];

export const PosMonitorView: React.FC = () => {
  const [activeRole, setActiveRole] = useState<UserRole>("ADMIN");
  const [activeSubTab, setActiveSubTab] = useState<"monitor" | "history" | "config">("monitor");

  const [accounts, setAccounts] = useState<PosAccount[]>(INITIAL_ACCOUNTS);
  const [users, setUsers] = useState<PosUser[]>(INITIAL_USERS);
  const [deposits, setDeposits] = useState<DepositRecord[]>(buildInitialDeposits);
  const [lastAlert, setLastAlert] = useState<DepositRecord | null>(null);

  // Estado Heartbeat LAN (5 segundos)
  const [simulateLanOutage, setSimulateLanOutage] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [lastHeartbeatAt, setLastHeartbeatAt] = useState<string>(new Date().toLocaleTimeString("es-CO"));
  const [reconnectDelaySec, setReconnectDelaySec] = useState(1);

  // Simulador Android + Cola Room Offline
  const [selectedAccountId, setSelectedAccountId] = useState<number>(1);
  const [rawNotification, setRawNotification] = useState(PRESET_NOTIFICATIONS[0]);
  const [androidOfflineMode, setAndroidOfflineMode] = useState(false);
  const [offlineQueue, setOfflineQueue] = useState<OfflineQueuedItem[]>([]);
  const [simulatorFeedback, setSimulatorFeedback] = useState<{
    type: "success" | "warning" | "error";
    message: string;
  } | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  // Configuración LAN & QR
  const [lanIp, setLanIp] = useState("192.168.1.50");
  const [serverPort, setServerPort] = useState(8000);
  const [apiToken, setApiToken] = useState("nqp_8f9a2c4b7e1d603a9c5b2f8e1d4a7c09");
  const [qrDataUrl, setQrDataUrl] = useState("");

  // Filtros Históricos Admin
  const todayStr = new Date().toISOString().slice(0, 10);
  const weekAgoStr = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState(weekAgoStr);
  const [endDate, setEndDate] = useState(todayStr);

  // Formularios Admin
  const [newCashierUser, setNewCashierUser] = useState("");
  const [newCashierName, setNewCashierName] = useState("");
  const [newCashierPass, setNewCashierPass] = useState("");
  const [newAccAlias, setNewAccAlias] = useState("");
  const [newAccPhone, setNewAccPhone] = useState("");
  const [newAccDevice, setNewAccDevice] = useState("");

  // Forzar retorno a monitor si cambia a Cajero
  useEffect(() => {
    if (activeRole === "CAJERO" && activeSubTab !== "monitor") {
      setActiveSubTab("monitor");
    }
  }, [activeRole, activeSubTab]);

  // Heartbeat real cada 5s contra /api/pos/heartbeat
  useEffect(() => {
    let active = true;
    const checkHeartbeat = async () => {
      if (simulateLanOutage) {
        if (active) {
          setIsOnline(false);
          setReconnectDelaySec((prev) => Math.min(prev * 2, 30));
        }
        return;
      }
      try {
        const res = await fetch("/api/pos/heartbeat");
        if (res.ok && active) {
          setIsOnline(true);
          setReconnectDelaySec(1);
          setLastHeartbeatAt(new Date().toLocaleTimeString("es-CO"));
        }
      } catch {
        if (active) {
          setIsOnline(false);
        }
      }
    };

    checkHeartbeat();
    const timer = setInterval(checkHeartbeat, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [simulateLanOutage]);

  // Generar Código QR dinámico real con IP + Puerto + Token
  useEffect(() => {
    const payload = JSON.stringify({
      server_ip: lanIp,
      server_port: serverPort,
      api_token: apiToken,
      protocol: "http",
    });
    QRCode.toDataURL(payload, { width: 196, margin: 2 }).then(setQrDataUrl).catch(() => {});
  }, [lanIp, serverPort, apiToken]);

  const todayDeposits = useMemo(
    () => deposits.filter((d) => d.capturedAt.slice(0, 10) === todayStr),
    [deposits, todayStr]
  );

  const todayTotalCop = useMemo(
    () => todayDeposits.reduce((acc, item) => acc + item.amountCop, 0),
    [todayDeposits]
  );

  const filteredHistory = useMemo(
    () =>
      deposits.filter((d) => {
        const day = d.capturedAt.slice(0, 10);
        return day >= startDate && day <= endDate;
      }),
    [deposits, startDate, endDate]
  );

  async function processSingleDeposit(item: {
    accountId: number;
    accountAlias: string;
    senderName: string;
    amountCop: number;
    rawNotification: string;
    capturedAt: string;
    source: "ANDROID_NOTIFICATION" | "MANUAL_TEST";
  }): Promise<"ok" | "duplicate"> {
    const res = await fetch("/api/pos/hash", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        accountId: item.accountId,
        senderName: item.senderName,
        amountCop: item.amountCop,
        capturedAtIso: item.capturedAt,
        windowSeconds: 120,
      }),
    });
    const { hash } = (await res.json()) as { hash: string };

    if (deposits.some((d) => d.idempotencyHash === hash)) {
      return "duplicate";
    }

    const record: DepositRecord = {
      id: Math.floor(200 + Math.random() * 8000),
      idempotencyHash: hash,
      accountId: item.accountId,
      accountAlias: item.accountAlias,
      senderName: item.senderName,
      amountCop: item.amountCop,
      amountWords: montoALetras(item.amountCop),
      ttsPhrase: buildTtsPhrase(item.amountCop),
      rawNotification: item.rawNotification,
      source: item.source,
      capturedAt: item.capturedAt,
    };

    setDeposits((prev) => [record, ...prev]);
    setLastAlert(record);
    if (voiceEnabled) {
      speakSpanishPosPhrase(record.ttsPhrase);
    }
    return "ok";
  }

  async function handleSimulateAndroidNotification(e: React.FormEvent) {
    e.preventDefault();
    const parsed = parseNequiNotification(rawNotification);
    if (!parsed) {
      setSimulatorFeedback({
        type: "warning",
        message:
          "El parser Regex ignoró la notificación (no corresponde a un ingreso válido de Nequi o es una transferencia saliente).",
      });
      return;
    }

    const account = accounts.find((a) => a.id === selectedAccountId) || accounts[0];
    const nowIso = new Date().toISOString().slice(0, 19);

    if (androidOfflineMode) {
      const queued: OfflineQueuedItem = {
        localId: Date.now(),
        accountId: account.id,
        accountAlias: account.alias,
        senderName: parsed.senderName,
        amountCop: parsed.amountCop,
        rawNotification: parsed.rawNotification,
        capturedAt: nowIso,
      };
      setOfflineQueue((prev) => [...prev, queued]);
      setSimulatorFeedback({
        type: "warning",
        message: `Sin Wi-Fi: Depósito de ${formatCop(parsed.amountCop)} guardado en cola Room DB (${offlineQueue.length + 1} pendientes).`,
      });
      return;
    }

    const outcome = await processSingleDeposit({
      accountId: account.id,
      accountAlias: account.alias,
      senderName: parsed.senderName,
      amountCop: parsed.amountCop,
      rawNotification: parsed.rawNotification,
      capturedAt: nowIso,
      source: "ANDROID_NOTIFICATION",
    });

    if (outcome === "duplicate") {
      setSimulatorFeedback({
        type: "error",
        message:
          "409 Conflict · Idempotencia SHA-256: Depósito duplicado dentro de la ventana de 120s. Bloqueado sin repetir voz.",
      });
    } else {
      setSimulatorFeedback({
        type: "success",
        message: `Depósito procesado en ${account.alias}: "${buildTtsPhrase(parsed.amountCop)}".`,
      });
    }
  }

  async function handleFlushOfflineQueue() {
    if (offlineQueue.length === 0) return;
    setAndroidOfflineMode(false);
    let synced = 0;
    let skipped = 0;

    // Drenaje estricto cronológico (FIFO)
    for (const item of offlineQueue) {
      const outcome = await processSingleDeposit({
        accountId: item.accountId,
        accountAlias: item.accountAlias,
        senderName: item.senderName,
        amountCop: item.amountCop,
        rawNotification: item.rawNotification,
        capturedAt: item.capturedAt,
        source: "ANDROID_NOTIFICATION",
      });
      if (outcome === "ok") synced += 1;
      else skipped += 1;
    }
    setOfflineQueue([]);
    setSimulatorFeedback({
      type: "success",
      message: `WorkManager sincronizó ${synced} transacciones en orden cronológico (${skipped} duplicadas ignoradas).`,
    });
  }

  function handleExportCsv() {
    const header = [
      "ID",
      "Fecha Captura",
      "Cuenta Nequi",
      "Remitente",
      "Monto COP",
      "Monto en Letras",
      "Hash SHA-256",
    ];
    const rows = filteredHistory.map((d) => [
      d.id,
      d.capturedAt,
      `"${d.accountAlias}"`,
      `"${d.senderName}"`,
      d.amountCop.toFixed(2),
      `"${d.amountWords}"`,
      d.idempotencyHash,
    ]);
    const csv = "\ufeff" + [header.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `nequipos_auditoria_${startDate}_${endDate}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function handleRotateToken() {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    setApiToken(`nqp_${hex}`);
  }

  async function handleTestSound() {
    const account = accounts[0];
    await processSingleDeposit({
      accountId: account.id,
      accountAlias: "PRUEBA DE AUDIO",
      senderName: "Panel Administrador",
      amountCop: 50000,
      rawNotification: "Prueba manual de sonido POS ($50.000)",
      capturedAt: new Date().toISOString().slice(0, 19),
      source: "MANUAL_TEST",
    });
  }

  return (
    <div className="space-y-6">
      {/* Barra de Control de Simulación RBAC + Heartbeat LAN */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <span
              className={`w-3 h-3 rounded-full shrink-0 ${
                isOnline ? "bg-emerald-600" : "bg-red-600 animate-heartbeat-offline"
              }`}
              aria-hidden="true"
            />
            {isOnline ? (
              <div className="flex items-center gap-1.5 text-sm font-semibold text-emerald-700">
                <Wifi className="w-4 h-4" />
                <span>En línea</span>
                <span className="text-slate-400 font-normal">·</span>
                <span className="text-xs font-mono text-slate-600 tabular-nums">
                  Heartbeat 5s ({lastHeartbeatAt})
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-sm font-semibold text-red-700">
                <WifiOff className="w-4 h-4" />
                <span>Desconectado del servidor</span>
                <span className="text-slate-400 font-normal">·</span>
                <span className="text-xs font-mono text-red-600 tabular-nums">
                  Backoff {reconnectDelaySec}s
                </span>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setSimulateLanOutage((v) => !v)}
            className="px-3 py-1.5 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors whitespace-nowrap shrink-0"
          >
            {simulateLanOutage ? "Restaurar Red LAN" : "Simular Corte LAN"}
          </button>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 whitespace-nowrap">Vista de Rol:</span>
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-lg">
            <button
              type="button"
              onClick={() => setActiveRole("ADMIN")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                activeRole === "ADMIN"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Administrador
            </button>
            <button
              type="button"
              onClick={() => setActiveRole("CAJERO")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                activeRole === "CAJERO"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Invitado (Cajero)
            </button>
          </div>
          <button
            type="button"
            onClick={() => setVoiceEnabled((v) => !v)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-colors whitespace-nowrap shrink-0 ${
              voiceEnabled
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-700"
            }`}
          >
            <Volume2 className="w-3.5 h-3.5" />
            <span>{voiceEnabled ? "Voz TTS Activa" : "Voz Silenciada"}</span>
          </button>
        </div>
      </div>

      {/* Sub-navegación RBAC */}
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveSubTab("monitor")}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
              activeSubTab === "monitor"
                ? "bg-[#DA0081] text-white"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            Monitor en Vivo (Hoy)
          </button>
          {activeRole === "ADMIN" && (
            <>
              <button
                type="button"
                onClick={() => setActiveSubTab("history")}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                  activeSubTab === "history"
                    ? "bg-[#DA0081] text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Auditoría Histórica y CSV
              </button>
              <button
                type="button"
                onClick={() => setActiveSubTab("config")}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                  activeSubTab === "config"
                    ? "bg-[#DA0081] text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Configuración, QR y Usuarios
              </button>
            </>
          )}
        </div>
        <div className="text-xs text-slate-500">
          {activeRole === "CAJERO"
            ? "Acceso Cajero: Solo movimientos de hoy · Totales históricos restringidos"
            : "Acceso Administrador: Control total · Auditoría y configuración LAN"}
        </div>
      </div>

      {/* TAB 1: MONITOR EN VIVO */}
      {activeSubTab === "monitor" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Columna Principal: Alerta de Voz + KPIs Admin + Tabla del Día */}
          <div className="lg:col-span-8 space-y-6">
            {lastAlert && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-5 flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold text-emerald-800">
                    Última notificación emitida por voz · {lastAlert.accountAlias}
                  </div>
                  <div className="text-3xl font-bold font-mono tabular-nums text-slate-900 mt-1">
                    {formatCop(lastAlert.amountCop)}
                  </div>
                  <div className="text-sm text-slate-700 mt-1">
                    Remitente: <span className="font-semibold">{lastAlert.senderName}</span>
                    <span className="mx-2 text-slate-400">·</span>
                    <span className="italic">"{lastAlert.ttsPhrase}"</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => speakSpanishPosPhrase(lastAlert.ttsPhrase)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-md bg-emerald-700 text-white hover:bg-emerald-800 transition-colors whitespace-nowrap shrink-0"
                >
                  <Volume2 className="w-4 h-4" />
                  <span>Repetir Voz</span>
                </button>
              </div>
            )}

            {activeRole === "ADMIN" && (
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="text-xs text-slate-500">Depósitos de hoy</div>
                  <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
                    {todayDeposits.length}
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="text-xs text-slate-500">Total recaudado hoy</div>
                  <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
                    {formatCop(todayTotalCop)}
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-4">
                  <div className="text-xs text-slate-500">Cuentas Nequi activas</div>
                  <div className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
                    {accounts.filter((a) => a.isActive).length}
                  </div>
                </div>
              </div>
            )}

            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-900">
                  Depósitos recibidos hoy
                </h2>
                <span className="text-xs font-mono text-slate-500 tabular-nums">{todayStr}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600">
                      <th className="py-2.5 px-4">Hora</th>
                      <th className="py-2.5 px-4">Cuenta Nequi</th>
                      <th className="py-2.5 px-4">Remitente</th>
                      <th className="py-2.5 px-4">Frase TTS</th>
                      <th className="py-2.5 px-4 text-right">Monto COP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {todayDeposits.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-500">
                          No se han registrado depósitos en la jornada de hoy.
                        </td>
                      </tr>
                    ) : (
                      todayDeposits.map((tx) => (
                        <tr key={tx.idempotencyHash} className="hover:bg-slate-50 transition-colors">
                          <td className="py-2.5 px-4 font-mono text-xs text-slate-600 tabular-nums whitespace-nowrap">
                            {tx.capturedAt.slice(11, 19)}
                          </td>
                          <td className="py-2.5 px-4 text-slate-800 font-medium whitespace-nowrap">
                            {tx.accountAlias}
                          </td>
                          <td className="py-2.5 px-4 text-slate-700">{tx.senderName}</td>
                          <td className="py-2.5 px-4 text-xs text-slate-500 max-w-xs truncate">
                            {tx.ttsPhrase}
                          </td>
                          <td className="py-2.5 px-4 text-right font-mono font-semibold text-slate-900 tabular-nums whitespace-nowrap">
                            {formatCop(tx.amountCop)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Columna Lateral: Simulador Android Listener + Room Offline Queue */}
          <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-[#DA0081]" />
                <span>Simulador Agente Android</span>
              </h3>
              <span className="text-xs font-mono text-slate-500">com.nequi.MobileApp</span>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Prueba el parser Regex en Kotlin, la idempotencia SHA-256 ante reintentos y la cola persistente Room + WorkManager ante cortes de Wi-Fi.
            </p>

            <form onSubmit={handleSimulateAndroidNotification} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Cuenta Nequi receptora
                </label>
                <select
                  value={selectedAccountId}
                  onChange={(e) => setSelectedAccountId(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-[#DA0081]"
                >
                  {accounts.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.alias} ({acc.phoneNumber})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Plantillas rápidas de notificación
                </label>
                <div className="grid grid-cols-1 gap-1.5">
                  {PRESET_NOTIFICATIONS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setRawNotification(preset)}
                      className="text-left px-2.5 py-1.5 text-xs rounded border border-slate-200 hover:bg-slate-50 text-slate-700 truncate"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Texto crudo de notificación Android
                </label>
                <textarea
                  rows={2}
                  value={rawNotification}
                  onChange={(e) => setRawNotification(e.target.value)}
                  className="w-full px-3 py-2 text-xs font-mono border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-[#DA0081]"
                />
              </div>

              <div className="flex items-center justify-between pt-1">
                <label className="inline-flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={androidOfflineMode}
                    onChange={(e) => setAndroidOfflineMode(e.target.checked)}
                    className="rounded border-slate-300 text-[#DA0081]"
                  />
                  <span>Simular teléfono sin Wi-Fi (Room)</span>
                </label>
              </div>

              <button
                type="submit"
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-md bg-[#DA0081] text-white hover:bg-[#b8006d] transition-colors"
              >
                <Send className="w-4 h-4" />
                <span>Capturar Notificación</span>
              </button>
            </form>

            {offlineQueue.length > 0 && (
              <div className="pt-3 border-t border-slate-200 space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-amber-800">
                  <span>Cola Room DB pendiente ({offlineQueue.length})</span>
                  <button
                    type="button"
                    onClick={handleFlushOfflineQueue}
                    className="px-2.5 py-1 rounded bg-amber-600 text-white hover:bg-amber-700 transition-colors"
                  >
                    Reconectar Wi-Fi y Sincronizar
                  </button>
                </div>
                <ul className="space-y-1 text-xs font-mono text-slate-600">
                  {offlineQueue.map((q) => (
                    <li key={q.localId} className="truncate">
                      {q.capturedAt.slice(11, 19)} · {formatCop(q.amountCop)} · {q.senderName}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {simulatorFeedback && (
              <div
                className={`p-3 rounded-md border text-xs flex items-start gap-2 ${
                  simulatorFeedback.type === "success"
                    ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                    : simulatorFeedback.type === "warning"
                    ? "bg-amber-50 border-amber-200 text-amber-900"
                    : "bg-red-50 border-red-200 text-red-900"
                }`}
              >
                {simulatorFeedback.type === "success" ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                )}
                <span>{simulatorFeedback.message}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: AUDITORÍA HISTÓRICA (SOLO ADMIN) */}
      {activeSubTab === "history" && activeRole === "ADMIN" && (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="p-5 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Auditoría Histórica por Rango de Fechas
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Total en rango: {filteredHistory.length} depósitos ·{" "}
                <span className="font-mono font-semibold text-slate-900 tabular-nums">
                  {formatCop(filteredHistory.reduce((s, d) => s + d.amountCop, 0))}
                </span>
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-md font-mono"
              />
              <span className="text-xs text-slate-400">a</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-md font-mono"
              />
              <button
                type="button"
                onClick={handleExportCsv}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-md bg-slate-900 text-white hover:bg-slate-800 transition-colors whitespace-nowrap shrink-0"
              >
                <Download className="w-4 h-4" />
                <span>Exportar CSV / Excel</span>
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-600">
                  <th className="py-2.5 px-4">Fecha / Hora</th>
                  <th className="py-2.5 px-4">Cuenta</th>
                  <th className="py-2.5 px-4">Remitente</th>
                  <th className="py-2.5 px-4">Idempotencia SHA-256</th>
                  <th className="py-2.5 px-4 text-right">Monto COP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredHistory.map((tx) => (
                  <tr key={tx.idempotencyHash} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-600 tabular-nums">
                      {tx.capturedAt.replace("T", " ")}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-800">{tx.accountAlias}</td>
                    <td className="py-2.5 px-4 text-slate-700">{tx.senderName}</td>
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-500">
                      {tx.idempotencyHash.slice(0, 16)}...
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono font-semibold text-slate-900 tabular-nums">
                      {formatCop(tx.amountCop)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: CONFIGURACIÓN, QR, USUARIOS Y CUENTAS (SOLO ADMIN) */}
      {activeSubTab === "config" && activeRole === "ADMIN" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Panel QR y Red LAN */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
            <h2 className="text-base font-semibold text-slate-900">
              Configuración de Red LAN y Código QR Android
            </h2>
            <p className="text-xs text-slate-600">
              Escanea este código desde la pantalla protegida con PIN de la App Android para vincular múltiples celulares sin hardcodear IPs.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-6 py-2">
              {qrDataUrl && (
                <img
                  src={qrDataUrl}
                  alt="Código QR de configuración LAN"
                  className="w-44 h-44 border border-slate-200 rounded-md p-2 bg-white shrink-0"
                />
              )}
              <div className="flex-1 w-full space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">IP Local</label>
                    <input
                      type="text"
                      value={lanIp}
                      onChange={(e) => setLanIp(e.target.value)}
                      className="w-full px-3 py-1.5 text-sm font-mono border border-slate-300 rounded-md"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Puerto</label>
                    <input
                      type="number"
                      value={serverPort}
                      onChange={(e) => setServerPort(Number(e.target.value))}
                      className="w-full px-3 py-1.5 text-sm font-mono border border-slate-300 rounded-md"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Token API</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={apiToken}
                      className="w-full px-3 py-1.5 text-xs font-mono bg-slate-50 border border-slate-200 rounded-md text-slate-700"
                    />
                    <button
                      type="button"
                      onClick={handleRotateToken}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-slate-300 hover:bg-slate-50 whitespace-nowrap shrink-0"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Rotar</span>
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleTestSound}
                  className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-md bg-[#DA0081] text-white hover:bg-[#b8006d] transition-colors"
                >
                  <Volume2 className="w-4 h-4" />
                  <span>Probar Sonido ($50.000)</span>
                </button>
              </div>
            </div>
          </div>

          {/* Gestión de Cajeros y Cuentas Nequi */}
          <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-6">
            <div>
              <h2 className="text-base font-semibold text-slate-900 mb-3 flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-slate-600" />
                <span>Usuarios y Cajeros (RBAC)</span>
              </h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!newCashierUser || !newCashierName || !newCashierPass) return;
                  setUsers((prev) => [
                    ...prev,
                    {
                      id: Date.now(),
                      username: newCashierUser.trim(),
                      fullName: newCashierName.trim(),
                      role: "CAJERO",
                      isActive: true,
                    },
                  ]);
                  setNewCashierUser("");
                  setNewCashierName("");
                  setNewCashierPass("");
                }}
                className="grid grid-cols-1 sm:grid-cols-4 gap-2 mb-3"
              >
                <input
                  type="text"
                  placeholder="Usuario"
                  value={newCashierUser}
                  onChange={(e) => setNewCashierUser(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-md"
                />
                <input
                  type="text"
                  placeholder="Nombre"
                  value={newCashierName}
                  onChange={(e) => setNewCashierName(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-md"
                />
                <input
                  type="password"
                  placeholder="Contraseña"
                  value={newCashierPass}
                  onChange={(e) => setNewCashierPass(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-md"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-900 text-white hover:bg-slate-800"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Cajero</span>
                </button>
              </form>
              <div className="divide-y divide-slate-100 text-xs">
                {users.map((u) => (
                  <div key={u.id} className="py-2 flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-slate-900">{u.fullName}</span>
                      <span className="mx-1.5 text-slate-400">·</span>
                      <span className="font-mono text-slate-600">{u.username}</span>
                      <span className="mx-1.5 text-slate-400">·</span>
                      <span className="text-slate-600">{u.role}</span>
                    </div>
                    <span className={u.isActive ? "text-emerald-700 font-medium" : "text-slate-400"}>
                      {u.isActive ? "Activo" : "Inactivo"}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200">
              <h2 className="text-base font-semibold text-slate-900 mb-3">
                Cuentas Nequi Vinculadas
              </h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!newAccAlias || !newAccPhone) return;
                  setAccounts((prev) => [
                    ...prev,
                    {
                      id: Date.now(),
                      alias: newAccAlias.trim(),
                      phoneNumber: newAccPhone.trim(),
                      deviceLabel: newAccDevice.trim() || "Android LAN",
                      isActive: true,
                    },
                  ]);
                  setNewAccAlias("");
                  setNewAccPhone("");
                  setNewAccDevice("");
                }}
                className="grid grid-cols-1 sm:grid-cols-4 gap-2 mb-3"
              >
                <input
                  type="text"
                  placeholder="Alias (Caja 3)"
                  value={newAccAlias}
                  onChange={(e) => setNewAccAlias(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-md"
                />
                <input
                  type="text"
                  placeholder="Celular Nequi"
                  value={newAccPhone}
                  onChange={(e) => setNewAccPhone(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-md"
                />
                <input
                  type="text"
                  placeholder="Teléfono"
                  value={newAccDevice}
                  onChange={(e) => setNewAccDevice(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-md"
                />
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-900 text-white hover:bg-slate-800"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Cuenta</span>
                </button>
              </form>
              <div className="divide-y divide-slate-100 text-xs">
                {accounts.map((a) => (
                  <div key={a.id} className="py-2 flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-slate-900">{a.alias}</span>
                      <span className="mx-1.5 text-slate-400">·</span>
                      <span className="font-mono text-slate-600">{a.phoneNumber}</span>
                    </div>
                    <span className="text-slate-500">{a.deviceLabel}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
