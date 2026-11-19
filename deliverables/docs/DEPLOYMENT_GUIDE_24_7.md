# Guía de Despliegue y Operación 24/7 — NequiPay POS

## 1. Empaquetado a Ejecutables (`.exe`) con PyInstaller

### A. Servidor Central (Windows 10 / 11 — Python 3.11+)
```powershell
cd deliverables\server
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --console ^
  --name "NequiPayPOS_Server" ^
  --hidden-import="uvicorn.logging" ^
  --hidden-import="uvicorn.loops.auto" ^
  --hidden-import="uvicorn.protocols.http.auto" ^
  --hidden-import="engineio.async_drivers.asgi" ^
  --hidden-import="pyttsx3.drivers.sapi5" ^
  --add-data "..\client_win7\web_pos;client_win7\web_pos" ^
  app\main.py
```

### B. Agente Cliente Windows 7 SP1 (Python 3.8.10)
> **Nota:** Python 3.8.10 es la última versión oficial compatible con Windows 7 SP1.
```cmd
cd deliverables\client_win7
py -3.8 -m venv .venv38
.venv38\Scripts\activate
pip install -r requirements_win7.txt pyinstaller==5.13.2

pyinstaller --noconfirm --onefile --windowed ^
  --name "NequiPayPOS_Client_Win7" ^
  agent_tray.py
```
Para iniciar apuntando al servidor desde acceso directo en carpeta `shell:startup`:
`NequiPayPOS_Client_Win7.exe --server http://192.168.1.50:8000`

---

## 2. Configuración de Red y Firewall en Windows 10/11 (Servidor)

### A. Regla de Firewall (PowerShell como Administrador)
```powershell
New-NetFirewallRule -DisplayName "NequiPay POS LAN Server (TCP 8000)" `
  -Direction Inbound -Protocol TCP -LocalPort 8000 `
  -Action Allow -Profile Private,Domain
```
*(Asegúrate de que el perfil de red Wi-Fi/Ethernet esté marcado como **Red Privada**, no Pública).*

### B. Asignación de IP Estática (Reserva DHCP o IP Fija)
1. En el router del local, asigna una **Reserva DHCP por dirección MAC** al PC Servidor (ej. `192.168.1.50`).
2. Opcionalmente fija en Windows (`Adaptador Ethernet -> IPv4`):
   - IP: `192.168.1.50` | Máscara: `255.255.255.0` | Puerta de enlace: `192.168.1.1`

---

## 3. Operación como Servicio 24/7 en Windows

- Instala **NSSM (Non-Sucking Service Manager)** en el Servidor Central:
```powershell
nssm install NequiPayPOS_Server "C:\NequiPayPOS\NequiPayPOS_Server.exe"
nssm set NequiPayPOS_Server AppDirectory "C:\NequiPayPOS"
nssm set NequiPayPOS_Server Start SERVICE_AUTO_START
nssm start NequiPayPOS_Server
```

---

## 4. Lista de Verificación Pre-Producción (24/7)

1. [ ] **Primer Arranque:** Abrir `http://192.168.1.50:8000` y crear el usuario **Administrador** inicial.
2. [ ] **Cuentas Nequi:** Registrar cada alias (ej. `Caja Principal`, `Caja Express`) en el panel Admin.
3. [ ] **Cajeros (Invitados):** Crear credenciales independientes para cada cajero (sin acceso a totales ni históricos).
4. [ ] **Android sin Ahorro de Batería:** En cada celular receptor, ir a *Ajustes -> Aplicaciones -> NequiPay POS Agente -> Batería -> Sin restricciones* y habilitar *Acceso a Notificaciones*.
5. [ ] **Escaneo QR:** En la App Android, desbloquear con el PIN local, escanear el QR del panel Admin y presionar **"Enviar pago de prueba"**.
6. [ ] **Audio en Cajas Win7:** Confirmar que los parlantes reproducen `"Pago por el valor de quince mil pesos"` y que el icono de bandeja está en verde.
7. [ ] **Prueba de Corte LAN:** Desconectar cable/Wi-Fi en Android, simular un depósito, reconectar Wi-Fi y confirmar sincronización automática desde Room/WorkManager sin duplicados.
