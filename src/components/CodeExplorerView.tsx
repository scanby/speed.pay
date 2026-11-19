import React, { useEffect, useMemo, useState } from "react";
import JSZip from "jszip";
import { Check, Copy, Download, FileCode2, FolderTree, Search } from "lucide-react";

export interface DeliverableFile {
  path: string;
  name: string;
  module: "server" | "client_win7" | "android_app" | "docs";
  language: string;
  lines: number;
  content: string;
}

const MODULE_LABELS: Record<DeliverableFile["module"], string> = {
  server: "Servidor Central (Python 3.11)",
  client_win7: "Cliente Windows 7 (Python 3.8 + ES5)",
  android_app: "App Android (Kotlin)",
  docs: "Documentación y ERD",
};

export const CodeExplorerView: React.FC = () => {
  const [files, setFiles] = useState<DeliverableFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [moduleFilter, setModuleFilter] = useState<"all" | DeliverableFile["module"]>("all");
  const [search, setSearch] = useState("");
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [copied, setCopied] = useState(false);
  const [zipping, setZipping] = useState(false);

  useEffect(() => {
    let mounted = true;
    fetch("/api/deliverables")
      .then((res) => {
        if (!res.ok) throw new Error("No se pudo cargar el árbol de código fuente.");
        return res.json();
      })
      .then((data: { files: DeliverableFile[] }) => {
        if (!mounted) return;
        setFiles(data.files);
        if (data.files.length > 0) {
          setSelectedPath(data.files[0].path);
        }
        setLoading(false);
      })
      .catch((err: Error) => {
        if (!mounted) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const filteredFiles = useMemo(() => {
    const q = search.trim().toLowerCase();
    return files.filter((f) => {
      const matchModule = moduleFilter === "all" || f.module === moduleFilter;
      const matchSearch =
        !q || f.path.toLowerCase().includes(q) || f.content.toLowerCase().includes(q);
      return matchModule && matchSearch;
    });
  }, [files, moduleFilter, search]);

  const activeFile = useMemo(
    () => files.find((f) => f.path === selectedPath) || filteredFiles[0] || null,
    [files, filteredFiles, selectedPath]
  );

  async function handleCopy() {
    if (!activeFile) return;
    await navigator.clipboard.writeText(activeFile.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function handleDownloadZip() {
    if (files.length === 0) return;
    setZipping(true);
    try {
      const zip = new JSZip();
      for (const f of files) {
        zip.file(f.path, f.content);
      }
      const blob = await zip.generateAsync({ type: "blob" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "nequipos_sistema_completo.zip";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setZipping(false);
    }
  }

  if (loading) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-8 text-sm text-slate-500">
        Cargando estructura modular del proyecto (`server/`, `client_win7/`, `android_app/`, `docs/`)...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-sm text-red-800">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Barra superior de filtros y descarga ZIP */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-1 p-1 bg-slate-100 rounded-lg">
          <button
            type="button"
            onClick={() => setModuleFilter("all")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
              moduleFilter === "all" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
            }`}
          >
            Todos ({files.length})
          </button>
          {(["server", "client_win7", "android_app", "docs"] as const).map((mod) => (
            <button
              key={mod}
              type="button"
              onClick={() => setModuleFilter(mod)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                moduleFilter === mod ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
              }`}
            >
              {MODULE_LABELS[mod]}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Buscar archivo o símbolo..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-xs border border-slate-300 rounded-md w-56 focus:outline-none focus:ring-2 focus:ring-[#DA0081]"
            />
          </div>
          <button
            type="button"
            onClick={handleDownloadZip}
            disabled={zipping}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-md bg-[#DA0081] text-white hover:bg-[#b8006d] transition-colors whitespace-nowrap shrink-0 disabled:opacity-60"
          >
            <Download className="w-4 h-4" />
            <span>{zipping ? "Empaquetando..." : "Descargar Proyecto (.zip)"}</span>
          </button>
        </div>
      </div>

      {/* Explorador Maestro-Detalle */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        <aside className="lg:col-span-4 bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2 text-xs font-semibold text-slate-700">
            <FolderTree className="w-4 h-4 text-slate-500" />
            <span>Árbol de Directorios ({filteredFiles.length} archivos)</span>
          </div>
          <div className="max-h-[620px] overflow-y-auto divide-y divide-slate-100">
            {filteredFiles.map((file) => {
              const isSelected = activeFile?.path === file.path;
              return (
                <button
                  key={file.path}
                  type="button"
                  onClick={() => setSelectedPath(file.path)}
                  className={`w-full text-left px-4 py-2.5 transition-colors flex items-center justify-between gap-2 ${
                    isSelected
                      ? "bg-slate-900 text-white"
                      : "hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <div className="min-w-0">
                    <div className="text-xs font-mono truncate">{file.path}</div>
                  </div>
                  <span
                    className={`text-[11px] font-mono tabular-nums shrink-0 ${
                      isSelected ? "text-slate-300" : "text-slate-400"
                    }`}
                  >
                    {file.lines}L
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="lg:col-span-8 bg-white border border-slate-200 rounded-lg overflow-hidden">
          {activeFile ? (
            <>
              <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 min-w-0">
                  <FileCode2 className="w-4 h-4 text-[#DA0081] shrink-0" />
                  <span className="text-xs font-mono font-semibold text-slate-900 truncate">
                    {activeFile.path}
                  </span>
                  <span className="text-slate-400">·</span>
                  <span className="text-xs text-slate-500 whitespace-nowrap">
                    {activeFile.lines} líneas
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 transition-colors whitespace-nowrap shrink-0"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Copiado</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copiar código</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="p-4 text-xs font-mono leading-relaxed text-slate-800 bg-white overflow-x-auto max-h-[620px] overflow-y-auto">
                <code>{activeFile.content}</code>
              </pre>
            </>
          ) : (
            <div className="p-8 text-sm text-slate-500">
              Selecciona un archivo del árbol izquierdo para inspeccionar su código fuente.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
