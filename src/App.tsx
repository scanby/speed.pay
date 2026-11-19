import React, { useState } from "react";
import { Code2, FileCheck2, Layers, MonitorPlay } from "lucide-react";
import { PosMonitorView } from "./components/PosMonitorView";
import { ArchitectureView } from "./components/ArchitectureView";
import { CodeExplorerView } from "./components/CodeExplorerView";
import { DeploymentGuideView } from "./components/DeploymentGuideView";

type SectionKey = "monitor" | "architecture" | "code" | "deploy";

const NAV_ITEMS: { key: SectionKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "monitor", label: "Consola POS en Vivo", icon: MonitorPlay },
  { key: "architecture", label: "Arquitectura y ERD", icon: Layers },
  { key: "code", label: "Código Fuente Completo", icon: Code2 },
  { key: "deploy", label: "Despliegue 24/7", icon: FileCheck2 },
];

export default function App() {
  const [activeSection, setActiveSection] = useState<SectionKey>("monitor");

  const activeTitle = NAV_ITEMS.find((n) => n.key === activeSection)?.label || "NequiPay POS";

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-slate-50 text-slate-900">
      {/* Sidebar fijo 260px en escritorio */}
      <aside className="w-full lg:w-64 bg-white border-b lg:border-b-0 lg:border-r border-slate-200 shrink-0 flex flex-col">
        <div className="px-6 py-5 border-b border-slate-200">
          <div className="text-lg font-bold tracking-tight font-display text-slate-900 whitespace-nowrap">
            NequiPay POS
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            Auditoría LAN y Notificación por Voz
          </div>
        </div>

        <nav className="p-3 flex lg:flex-col gap-1 overflow-x-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setActiveSection(item.key)}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-md text-sm font-medium transition-colors whitespace-nowrap shrink-0 ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto p-5 border-t border-slate-200 hidden lg:block text-xs text-slate-500 space-y-1.5">
          <div className="font-semibold text-slate-700">Stack de Producción</div>
          <div>Servidor · Python 3.11 FastAPI + SQLite WAL</div>
          <div>Cliente · Python 3.8 Win7 + ES5</div>
          <div>Móvil · Kotlin Room + WorkManager</div>
        </div>
      </aside>

      {/* Contenido Principal */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between gap-8">
          <div className="flex items-center gap-2 text-sm text-slate-600 whitespace-nowrap">
            <span className="text-slate-400">NequiPay POS</span>
            <span aria-hidden="true">/</span>
            <h1 className="font-semibold text-slate-900">{activeTitle}</h1>
          </div>
          <button
            type="button"
            onClick={() => setActiveSection("code")}
            className="px-4 py-2 text-xs font-semibold rounded-md bg-[#DA0081] text-white hover:bg-[#b8006d] transition-colors whitespace-nowrap shrink-0"
          >
            Explorar y Descargar Código
          </button>
        </header>

        <main className="flex-1 p-6 max-w-[1320px] w-full mx-auto">
          {activeSection === "monitor" && <PosMonitorView />}
          {activeSection === "architecture" && <ArchitectureView />}
          {activeSection === "code" && <CodeExplorerView />}
          {activeSection === "deploy" && <DeploymentGuideView />}
        </main>
      </div>
    </div>
  );
}
