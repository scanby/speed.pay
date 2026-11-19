# Guía de Despliegue y Operación 24/7 — NequiPay POS

## 1. Generación Automática de `.exe` y `.apk` vía Git Release (CI/CD)

El repositorio incluye el workflow `.github/workflows/release.yml` para compilar automáticamente los ejecutables de Windows y el APK de Android cada vez que publiques un release en Git:

```bash
git add .
git commit -m "chore: preparar release v0.1.3"
git tag v0.1.3
git push origin main --tags
```

Al detectar el tag `v*`, GitHub Actions ejecuta en paralelo:
1. **`NequiPayPOS_Server_Win10_11.exe`** (en `windows-latest` con Python 3.11 + `pytest` + PyInstaller).
2. **`NequiPayPOS_Client_Win7.exe`** (en `windows-latest` con Python 3.8 x86 + PyInstaller 5.13.2, compatible con Windows 7 SP1 de 32 y 64 bits).
3. **`NequiPayPOS_Agent_Android.apk`** (en `ubuntu-latest` con JDK 17 + Gradle 8.7 + pruebas unitarias JUnit + firma APK lista para instalar en Android 8.0+).
   - *Firma persistente opcional:* Configura en GitHub Secrets `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` y `ANDROID_KEY_PASSWORD` para conservar la misma firma entre actualizaciones. Si no existen, el workflow genera automáticamente un keystore PKCS12 válido para que el APK sea instalable de inmediato.
4. Publica los binarios y el archivo `SHA256SUMS.txt` directamente en la sección **Releases** de GitHub.

---

## 2. Panel de Configuración del Cliente (IP Estática del Servidor)

El ejecutable `NequiPayPOS_Client_Win7.exe` incluye un **Panel de Configuración nativo** (`config_window.py`) persistido en `%USERPROFILE%\.nequipos_client\config.json`:

- **Primer arranque:** Si no existe `config.json`, el panel se abre automáticamente antes de conectar.
- **Reconfiguración en caliente:** Clic derecho sobre el icono de la bandeja del sistema → **"Configurar Servidor (IP / Puerto)"**.
- **Campos configurables:**
  - **IP Estática del PC Servidor** (ej. `192.168.1.50`)
  - **Puerto TCP** (por defecto `8000`)
  - **Nombre de esta Caja** (ej. `Caja Principal`)
  - **Volumen de Voz POS** (`0%` a `100%`)
  - **Modo Kiosco** (ventana limpia sin barras del navegador)
  - Botón **"Probar Conexión"** que valida `GET http://<ip>:<puerto>/api/health` mostrando latencia en ms antes de guardar.

---

## 3. Empaquetado Manual Local con PyInstaller (Opcional)

### A. Servidor Central (Windows 10 / 11 — Python 3.11+)
```powershell
cd deliverables\server
python -m venv .venv
.\.venv\Scripts\activate
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
  --add-data "..\client_win7\web_pos;client_win7\web_pos" ^
  app\main.py
```

### B. Agente Cliente Windows 7 SP1 (Python 3.8.10 x86)
```cmd
cd deliverables\client_win7
py -3.8 -m venv .venv38
.venv38\Scripts\activate
pip install "pip<25" "setuptools<70" wheel
pip install -r requirements_win7.txt pyinstaller==5.13.2

pyinstaller --noconfirm --onefile --windowed ^
  --name "NequiPayPOS_Client_Win7" ^
  --paths "." ^
  --hidden-import="tkinter" ^
  --hidden-import="engineio.async_drivers.threading" ^
  agent_tray.py
```

---

## 4. Red, Firewall y Servicio 24/7 en Windows

```powershell
# Regla Firewall TCP 8000 en Red Privada
New-NetFirewallRule -DisplayName "NequiPay POS LAN Server (TCP 8000)" `
  -Direction Inbound -Protocol TCP -LocalPort 8000 `
  -Action Allow -Profile Private,Domain

# Servicio persistente 24/7 con NSSM
nssm install NequiPayPOS_Server "C:\NequiPayPOS\NequiPayPOS_Server_Win10_11.exe"
nssm set NequiPayPOS_Server AppDirectory "C:\NequiPayPOS"
nssm set NequiPayPOS_Server Start SERVICE_AUTO_START
nssm start NequiPayPOS_Server
```
