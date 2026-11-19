# -*- coding: utf-8 -*-
"""
Panel de Configuración Nativo (Tkinter - Python 3.8 compatible con Windows 7).
Permite configurar la IP estática del PC Servidor, puerto, nombre de caja, volumen de voz,
repositorio GitHub y comprobar/aplicar actualizaciones desatendidas.
"""
import os
import threading
import tkinter as tk
from tkinter import messagebox

from client_config import (
    CONFIG_PATH,
    load_client_config,
    save_client_config,
    test_server_connection,
)
from client_updater import (
    apply_unattended_client_update,
    check_client_update,
    get_client_version,
)


def open_config_dialog(on_save_callback=None):
    current = load_client_config()
    installed_ver = get_client_version()
    pending_release = {"data": None}

    root = tk.Tk()
    root.title("NequiPay POS — Configuración del Cliente (v{0})".format(installed_ver))
    root.geometry("490x540")
    root.resizable(False, False)
    root.configure(bg="#F8FAFC")

    frame = tk.Frame(root, bg="#FFFFFF", bd=1, relief="solid", padx=20, pady=18)
    frame.pack(fill="both", expand=True, padx=14, pady=14)

    tk.Label(
        frame,
        text="Conexión al Servidor Central y Actualizaciones",
        font=("Segoe UI", 12, "bold"),
        bg="#FFFFFF",
        fg="#0F172A",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

    tk.Label(
        frame,
        text="Versión instalada: v{0} · Archivo: {1}".format(installed_ver, CONFIG_PATH),
        font=("Segoe UI", 8),
        bg="#FFFFFF",
        fg="#64748B",
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

    # IP Estática del Servidor
    tk.Label(frame, text="IP Estática del Servidor:", bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 9, "bold")).grid(
        row=2, column=0, sticky="w", pady=4
    )
    ip_var = tk.StringVar(value=current["server_ip"])
    ip_entry = tk.Entry(frame, textvariable=ip_var, width=28, font=("Consolas", 10))
    ip_entry.grid(row=2, column=1, sticky="ew", pady=4)

    # Puerto
    tk.Label(frame, text="Puerto TCP:", bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 9, "bold")).grid(
        row=3, column=0, sticky="w", pady=4
    )
    port_var = tk.StringVar(value=str(current["server_port"]))
    tk.Entry(frame, textvariable=port_var, width=28, font=("Consolas", 10)).grid(
        row=3, column=1, sticky="ew", pady=4
    )

    # Etiqueta de Caja
    tk.Label(frame, text="Nombre de esta Caja:", bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 9, "bold")).grid(
        row=4, column=0, sticky="w", pady=4
    )
    label_var = tk.StringVar(value=current["pos_label"])
    tk.Entry(frame, textvariable=label_var, width=28, font=("Segoe UI", 10)).grid(
        row=4, column=1, sticky="ew", pady=4
    )

    # Repositorio GitHub para actualizaciones
    tk.Label(frame, text="Repositorio GitHub:", bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 9, "bold")).grid(
        row=5, column=0, sticky="w", pady=4
    )
    repo_var = tk.StringVar(value=current["github_repo"])
    tk.Entry(frame, textvariable=repo_var, width=28, font=("Consolas", 9)).grid(
        row=5, column=1, sticky="ew", pady=4
    )

    # Volumen de Audio
    tk.Label(frame, text="Volumen de Voz (%):", bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 9, "bold")).grid(
        row=6, column=0, sticky="w", pady=4
    )
    vol_var = tk.IntVar(value=int(current["audio_volume"]))
    tk.Scale(
        frame,
        from_=0,
        to=100,
        orient="horizontal",
        variable=vol_var,
        bg="#FFFFFF",
        highlightthickness=0,
    ).grid(row=6, column=1, sticky="ew", pady=4)

    kiosk_var = tk.BooleanVar(value=bool(current["kiosk_mode"]))
    tk.Checkbutton(
        frame,
        text="Abrir monitor web en modo ventana limpia (Kiosco)",
        variable=kiosk_var,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 9),
    ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 2))

    auto_open_var = tk.BooleanVar(value=bool(current["auto_open_browser"]))
    tk.Checkbutton(
        frame,
        text="Abrir monitor automáticamente al iniciar Windows",
        variable=auto_open_var,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 9),
    ).grid(row=8, column=0, columnspan=2, sticky="w", pady=2)

    auto_update_var = tk.BooleanVar(value=bool(current["auto_update_enabled"]))
    tk.Checkbutton(
        frame,
        text="Instalar nuevas versiones automáticamente (Desatendida)",
        variable=auto_update_var,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 9),
    ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(2, 8))

    status_var = tk.StringVar(value="Listo para probar conexión o buscar actualizaciones.")
    status_label = tk.Label(
        frame,
        textvariable=status_var,
        bg="#F1F5F9",
        fg="#334155",
        font=("Segoe UI", 8),
        wraplength=415,
        justify="left",
        padx=8,
        pady=8,
    )
    status_label.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(4, 10))

    install_btn = tk.Button(
        frame,
        text="Actualizar Ahora (Desatendida)",
        bg="#16A34A",
        fg="#FFFFFF",
        font=("Segoe UI", 9, "bold"),
        padx=10,
        pady=5,
        state="disabled",
    )

    def handle_test():
        try:
            port = int(port_var.get().strip())
        except ValueError:
            status_label.config(fg="#B91C1C", bg="#FEF2F2")
            status_var.set("Puerto inválido. Usa un número entre 1024 y 65535.")
            return
        ok, msg = test_server_connection(ip_var.get(), port)
        status_label.config(fg="#15803D" if ok else "#B91C1C", bg="#ECFDF5" if ok else "#FEF2F2")
        status_var.set(msg)

    def handle_check_updates():
        status_label.config(fg="#334155", bg="#F1F5F9")
        status_var.set("Consultando último release en GitHub...")
        repo = repo_var.get().strip()

        def _worker():
            res = check_client_update(repo)

            def _ui_update():
                if res["status"] == "update_available":
                    pending_release["data"] = res
                    status_label.config(fg="#92400E", bg="#FFFBEB")
                    status_var.set(res["message"])
                    install_btn.config(state="normal")
                elif res["status"] == "up_to_date":
                    pending_release["data"] = None
                    status_label.config(fg="#15803D", bg="#ECFDF5")
                    status_var.set(res["message"])
                    install_btn.config(state="disabled")
                else:
                    pending_release["data"] = None
                    status_label.config(fg="#B91C1C", bg="#FEF2F2")
                    status_var.set(res["message"])
                    install_btn.config(state="disabled")

            root.after(0, _ui_update)

        threading.Thread(target=_worker, daemon=True).start()

    def handle_install_update():
        rel = pending_release.get("data")
        if not rel or not rel.get("download_url"):
            status_label.config(fg="#B91C1C", bg="#FEF2F2")
            status_var.set("El release no incluye el ejecutable NequiPayPOS_Client_Win7.exe.")
            return
        install_btn.config(state="disabled")
        status_label.config(fg="#1D4ED8", bg="#EFF6FF")
        status_var.set("Descargando y verificando firma SHA-256 sin intervención...")

        def _worker():
            ok, msg = apply_unattended_client_update(rel["download_url"], rel.get("sha256_sums_url"))

            def _finish():
                if ok:
                    os._exit(0)
                else:
                    status_label.config(fg="#B91C1C", bg="#FEF2F2")
                    status_var.set(msg)

            root.after(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()

    install_btn.config(command=handle_install_update)

    def handle_save():
        ip_text = ip_var.get().strip()
        if not ip_text:
            messagebox.showerror("Dato requerido", "Ingresa la dirección IP estática del servidor.")
            return
        try:
            port = int(port_var.get().strip())
            if port < 1024 or port > 65535:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Puerto inválido", "El puerto debe estar entre 1024 y 65535.")
            return

        saved = save_client_config(
            {
                "server_ip": ip_text,
                "server_port": port,
                "pos_label": label_var.get(),
                "github_repo": repo_var.get(),
                "audio_volume": vol_var.get(),
                "kiosk_mode": kiosk_var.get(),
                "auto_open_browser": auto_open_var.get(),
                "auto_update_enabled": auto_update_var.get(),
            }
        )
        if on_save_callback is not None:
            on_save_callback(saved)
        root.destroy()

    btn_row = tk.Frame(frame, bg="#FFFFFF")
    btn_row.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(0, 6))

    tk.Button(
        btn_row,
        text="Probar Conexión",
        command=handle_test,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 8, "bold"),
        padx=10,
        pady=5,
    ).pack(side="left", padx=(0, 6))

    tk.Button(
        btn_row,
        text="Buscar Actualizaciones",
        command=handle_check_updates,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 8, "bold"),
        padx=10,
        pady=5,
    ).pack(side="left")

    tk.Button(
        btn_row,
        text="Guardar y Conectar",
        command=handle_save,
        bg="#DA0081",
        fg="#FFFFFF",
        font=("Segoe UI", 8, "bold"),
        padx=12,
        pady=5,
    ).pack(side="right")

    install_btn.grid(row=12, column=0, columnspan=2, sticky="ew")

    frame.columnconfigure(1, weight=1)
    ip_entry.focus_set()
    root.mainloop()
