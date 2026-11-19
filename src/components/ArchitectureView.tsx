import React from "react";

export const ArchitectureView: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Diagrama 1: Arquitectura Distribuida LAN */}
      <section className="bg-white border border-slate-200 rounded-lg p-6">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            01. Arquitectura Distribuida en Red Local (LAN)
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            Flujo desacoplado desde la captura en Android (Kotlin) hacia el Servidor Central (FastAPI + Clean Architecture) y difusión en tiempo real a cajas Windows 7–11.
          </p>
        </div>

        <div className="overflow-x-auto">
          <svg
            viewBox="0 0 1080 340"
            className="w-full min-w-[820px] h-auto"
            role="img"
            aria-label="Diagrama de Arquitectura Distribuida LAN NequiPay POS"
          >
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569" />
              </marker>
            </defs>

            {/* Nodo 1: Android Kotlin */}
            <rect x="20" y="30" width="280" height="270" rx="8" fill="#F8FAFC" stroke="#CBD5E1" strokeWidth="1.5" />
            <text x="40" y="60" fontSize="14" fontWeight="700" fill="#0F172A">1. App Android (Kotlin)</text>
            <text x="40" y="80" fontSize="11" fill="#64748B">Dispositivos receptores Nequi</text>

            <rect x="40" y="100" width="240" height="44" rx="6" fill="#FFFFFF" stroke="#E2E8F0" />
            <text x="52" y="119" fontSize="12" fontWeight="600" fill="#0F172A">NotificationListenerService</text>
            <text x="52" y="135" fontSize="10" fill="#64748B">Filtro: com.nequi.MobileApp + Foreground</text>

            <rect x="40" y="156" width="240" height="44" rx="6" fill="#FFFFFF" stroke="#E2E8F0" />
            <text x="52" y="175" fontSize="12" fontWeight="600" fill="#0F172A">NequiNotificationParser</text>
            <text x="52" y="191" fontSize="10" fill="#64748B">Regex flexible + Normalización COP</text>

            <rect x="40" y="212" width="240" height="68" rx="6" fill="#FFFFFF" stroke="#E2E8F0" />
            <text x="52" y="232" fontSize="12" fontWeight="600" fill="#0F172A">Room DB + WorkManager</text>
            <text x="52" y="248" fontSize="10" fill="#64748B">Cola persistente offline (orden FIFO)</text>
            <text x="52" y="264" fontSize="10" fill="#DA0081">QR Config + PIN Local (EncryptedPrefs)</text>

            {/* Flecha Android -> Servidor */}
            <line x1="300" y1="165" x2="368" y2="165" stroke="#475569" strokeWidth="1.8" markerEnd="url(#arrow)" />
            <text x="306" y="152" fontSize="10" fontWeight="600" fill="#334155">POST /ingest</text>
            <text x="306" y="182" fontSize="10" fill="#64748B">X-Api-Token</text>

            {/* Nodo 2: Servidor Central */}
            <rect x="372" y="20" width="336" height="295" rx="8" fill="#FFFFFF" stroke="#0F172A" strokeWidth="1.5" />
            <text x="392" y="50" fontSize="14" fontWeight="700" fill="#0F172A">2. Servidor Central (Win 10/11 · Py 3.11)</text>
            <text x="392" y="68" fontSize="11" fill="#64748B">Clean Architecture: Presentation / App / Domain / Infra</text>

            <rect x="392" y="84" width="296" height="44" rx="6" fill="#F8FAFC" stroke="#E2E8F0" />
            <text x="404" y="103" fontSize="12" fontWeight="600" fill="#0F172A">Presentation · FastAPI + Socket.IO ASGI</text>
            <text x="404" y="119" fontSize="10" fill="#64748B">RBAC JWT HttpOnly + Pydantic v2 + /static/audio</text>

            <rect x="392" y="138" width="296" height="44" rx="6" fill="#F8FAFC" stroke="#E2E8F0" />
            <text x="404" y="157" fontSize="12" fontWeight="600" fill="#0F172A">Domain · SHA-256 + monto_a_letras()</text>
            <text x="404" y="173" fontSize="10" fill="#64748B">Idempotencia 120s + Conversión COP a palabras</text>

            <rect x="392" y="192" width="142" height="54" rx="6" fill="#F8FAFC" stroke="#E2E8F0" />
            <text x="402" y="211" fontSize="11" fontWeight="600" fill="#0F172A">SQLite Mode WAL</text>
            <text x="402" y="227" fontSize="10" fill="#64748B">SQLAlchemy +</text>
            <text x="402" y="239" fontSize="10" fill="#64748B">RotatingFileHandler</text>

            <rect x="546" y="192" width="142" height="54" rx="6" fill="#F8FAFC" stroke="#E2E8F0" />
            <text x="556" y="211" fontSize="11" fontWeight="600" fill="#0F172A">TTS Centralizado</text>
            <text x="556" y="227" fontSize="10" fill="#64748B">edge-tts neural +</text>
            <text x="556" y="239" fontSize="10" fill="#64748B">Fallback SAPI5 WAV</text>

            <rect x="392" y="256" width="296" height="42" rx="6" fill="#FDF2F8" stroke="#FBCFE8" />
            <text x="404" y="275" fontSize="11" fontWeight="600" fill="#9D174D">Broadcast Tiempo Real (new_deposit)</text>
            <text x="404" y="290" fontSize="10" fill="#831843">Heartbeat 5s + Distribución MP3/WAV por HTTP</text>

            {/* Flecha Servidor -> Win7 Clientes */}
            <line x1="708" y1="165" x2="776" y2="165" stroke="#475569" strokeWidth="1.8" markerEnd="url(#arrow)" />
            <text x="713" y="152" fontSize="10" fontWeight="600" fill="#334155">Socket.IO</text>
            <text x="713" y="182" fontSize="10" fill="#64748B">Audio HTTP</text>

            {/* Nodo 3: Clientes POS Win 7 - 11 */}
            <rect x="780" y="30" width="280" height="270" rx="8" fill="#F8FAFC" stroke="#CBD5E1" strokeWidth="1.5" />
            <text x="800" y="60" fontSize="14" fontWeight="700" fill="#0F172A">3. Clientes POS (Win 7 a 11)</text>
            <text x="800" y="80" fontSize="11" fill="#64748B">Múltiples puntos de venta / cajas</text>

            <rect x="800" y="100" width="240" height="72" rx="6" fill="#FFFFFF" stroke="#E2E8F0" />
            <text x="812" y="120" fontSize="12" fontWeight="600" fill="#0F172A">Agente Python 3.8 (Tray)</text>
            <text x="812" y="137" fontSize="10" fill="#64748B">Icono Verde/Rojo en bandeja</text>
            <text x="812" y="152" fontSize="10" fill="#64748B">pygame.mixer (sin bloqueo autoplay)</text>

            <rect x="800" y="186" width="240" height="94" rx="6" fill="#FFFFFF" stroke="#E2E8F0" />
            <text x="812" y="206" fontSize="12" fontWeight="600" fill="#0F172A">Frontend Web ES5 / ES6</text>
            <text x="812" y="223" fontSize="10" fill="#64748B">Heartbeat 5s + Backoff Exponencial</text>
            <text x="812" y="239" fontSize="10" fill="#15803D">Verde: En línea / Rojo: Desconectado</text>
            <text x="812" y="255" fontSize="10" fill="#64748B">RBAC: Cajero (Hoy) vs Admin (Total)</text>
          </svg>
        </div>
      </section>

      {/* Diagrama 2: Modelo Entidad-Relación SQLite WAL */}
      <section className="bg-white border border-slate-200 rounded-lg p-6">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            02. Modelo Entidad-Relación (SQLite WAL)
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            Esquema relacional con PRAGMA journal_mode=WAL y busy_timeout=5000 para concurrencia sin bloqueos entre ingestión Android y consultas de cajas.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 font-mono text-xs">
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="bg-slate-900 text-white px-4 py-2.5 font-semibold">
              deposit_transactions
            </div>
            <div className="p-4 space-y-1.5 text-slate-700">
              <div><span className="text-[#DA0081] font-semibold">PK</span> id INTEGER</div>
              <div><span className="text-emerald-700 font-semibold">UQ</span> idempotency_hash CHAR(64)</div>
              <div><span className="text-blue-700 font-semibold">FK</span> account_id → nequi_accounts.id</div>
              <div>account_alias VARCHAR(80)</div>
              <div>sender_name VARCHAR(160)</div>
              <div>amount_cop NUMERIC(14,2)</div>
              <div>amount_words VARCHAR(255)</div>
              <div>raw_notification TEXT</div>
              <div>source VARCHAR(32)</div>
              <div>audio_filename VARCHAR(128)</div>
              <div><span className="text-slate-500">IDX</span> captured_at DATETIME</div>
              <div>received_at DATETIME</div>
            </div>
          </div>

          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="bg-slate-900 text-white px-4 py-2.5 font-semibold">
              nequi_accounts
            </div>
            <div className="p-4 space-y-1.5 text-slate-700">
              <div><span className="text-[#DA0081] font-semibold">PK</span> id INTEGER</div>
              <div><span className="text-emerald-700 font-semibold">UQ</span> alias VARCHAR(80)</div>
              <div>phone_number VARCHAR(20)</div>
              <div>device_label VARCHAR(100)</div>
              <div>is_active BOOLEAN</div>
              <div>created_at DATETIME</div>
            </div>
            <div className="bg-slate-900 text-white px-4 py-2.5 font-semibold mt-2">
              users
            </div>
            <div className="p-4 space-y-1.5 text-slate-700">
              <div><span className="text-[#DA0081] font-semibold">PK</span> id INTEGER</div>
              <div><span className="text-emerald-700 font-semibold">UQ</span> username VARCHAR(64)</div>
              <div>full_name VARCHAR(128)</div>
              <div>password_hash VARCHAR(255) (bcrypt)</div>
              <div>role ENUM('ADMIN', 'CAJERO')</div>
              <div>is_active BOOLEAN</div>
              <div>created_at DATETIME</div>
            </div>
          </div>

          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="bg-slate-900 text-white px-4 py-2.5 font-semibold">
              audit_logs
            </div>
            <div className="p-4 space-y-1.5 text-slate-700">
              <div><span className="text-[#DA0081] font-semibold">PK</span> id INTEGER</div>
              <div><span className="text-slate-500">IDX</span> actor_username VARCHAR(64)</div>
              <div>action VARCHAR(80)</div>
              <div>details TEXT</div>
              <div>ip_address VARCHAR(45)</div>
              <div><span className="text-slate-500">IDX</span> created_at DATETIME</div>
            </div>
            <div className="bg-slate-900 text-white px-4 py-2.5 font-semibold mt-2">
              system_config
            </div>
            <div className="p-4 space-y-1.5 text-slate-700">
              <div><span className="text-[#DA0081] font-semibold">PK</span> id INTEGER (= 1)</div>
              <div>api_token VARCHAR(128)</div>
              <div>server_port INTEGER</div>
              <div>tts_enabled BOOLEAN</div>
              <div>tts_voice VARCHAR(64)</div>
              <div>updated_at DATETIME</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
