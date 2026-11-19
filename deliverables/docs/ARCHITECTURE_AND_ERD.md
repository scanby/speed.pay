# Arquitectura Distribuida LAN y Modelo Entidad-Relación (SQLite WAL)

## 1. Diagrama de Arquitectura Distribuida (Red Local)

```
+-------------------------------------------------------------------------+
|                    DISPOSITIVO ANDROID (Nequi Receptor)                 |
|  [com.nequi.MobileApp] -> NotificationListenerService (ForegroundSvc)   |
|        -> NequiNotificationParser (Regex) -> Room DB (Cola Offline)     |
|        -> WorkManager (Sync Cronológico Wi-Fi)                          |
+------------------------------------+------------------------------------+
                                     |
                                     | HTTP POST /api/deposits/ingest
                                     | Header: X-Api-Token + JSON Payload
                                     v
+-------------------------------------------------------------------------+
|              SERVIDOR CENTRAL WINDOWS 10/11 (Python 3.11+)              |
|                                                                         |
|  [Presentation] FastAPI REST + Socket.IO ASGI (/static/audio, /pos)     |
|        |                                                                |
|  [Application]  UseCases (Auth, Deposit, Admin, QR, CSV Export)         |
|        |                                                                |
|  [Domain]       SHA-256 Idempotency + monto_a_letras() + Entities       |
|        |                                                                |
|  [Infrastructure]                                                       |
|    |-- SQLAlchemy + SQLite (PRAGMA journal_mode=WAL)                    |
|    |-- HybridSpanishTtsService (edge-tts -> fallback SAPI5 pyttsx3)     |
|    |-- RotatingFileHandler (logs/nequipos_server.log, 5MB x 10)         |
+------------------------------------+------------------------------------+
                                     |
           Socket.IO (new_deposit + heartbeat_ping cada 5s)
           + HTTP GET /static/audio/pago_<hash>.mp3|.wav
                                     v
+-------------------------------------------------------------------------+
|                PUNTOS DE VENTA / CAJAS (Windows 7 a 11)                 |
|  1. Agente Python 3.8 (Tray Icon Verde/Rojo + pygame.mixer audio)       |
|  2. Frontend Web ES5/ES6 (Heartbeat 5s + Reconexión Exponencial)        |
|     - Rol Cajero (Invitado): Solo alertas en vivo y movimientos de hoy  |
|     - Rol Admin: Totales, Rango Fechas, CSV, Usuarios, Cuentas, QR      |
+-------------------------------------------------------------------------+
```

## 2. Modelo Entidad-Relación (SQLite Modo WAL)

```
+---------------------------+          +------------------------------------+
|       nequi_accounts      |          |        deposit_transactions        |
+---------------------------+          +------------------------------------+
| PK id (INTEGER)           |<----+    | PK id (INTEGER)                    |
| UQ alias (VARCHAR 80)     |     +----| FK account_id (INTEGER, RESTRICT)  |
|    phone_number (VARCHAR) |          | UQ idempotency_hash (CHAR 64)      |
|    device_label (VARCHAR) |          |    account_alias (VARCHAR 80)      |
|    is_active (BOOLEAN)    |          |    sender_name (VARCHAR 160)       |
|    created_at (DATETIME)  |          |    amount_cop (NUMERIC 14,2)       |
+---------------------------+          |    amount_words (VARCHAR 255)      |
                                       |    raw_notification (TEXT)         |
+---------------------------+          |    source (VARCHAR 32)             |
|           users           |          |    audio_filename (VARCHAR 128)    |
+---------------------------+          |    captured_at (DATETIME, IDX)     |
| PK id (INTEGER)           |          |    received_at (DATETIME)          |
| UQ username (VARCHAR 64)  |          +------------------------------------+
|    full_name (VARCHAR)    |
|    password_hash (bcrypt) |          +------------------------------------+
|    role (ADMIN | CAJERO)  |          |           system_config            |
|    is_active (BOOLEAN)    |          +------------------------------------+
|    created_at (DATETIME)  |          | PK id (INTEGER = 1)                |
+---------------------------+          |    api_token (VARCHAR 128)         |
                                       |    server_port (INTEGER)           |
+---------------------------+          |    tts_enabled (BOOLEAN)           |
|        audit_logs         |          |    tts_voice (VARCHAR 64)          |
+---------------------------+          |    updated_at (DATETIME)           |
| PK id (INTEGER)           |          +------------------------------------+
|    actor_username (IDX)   |
|    action (VARCHAR 80)    |
|    details (TEXT)         |
|    ip_address (VARCHAR)   |
|    created_at (DATETIME)  |
+---------------------------+
```
