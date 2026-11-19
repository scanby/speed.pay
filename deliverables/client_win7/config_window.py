# -*- coding: utf-8 -*-
"""
Panel de Configuración Nativo (Tkinter - Python 3.8 compatible con Windows 7).
Permite configurar la dirección IP estática del PC Servidor, puerto, nombre de caja,
volumen de voz y probar la conexión LAN antes de guardar.
"""
import tkinter as tk
from tkinter import messagebox

from client_config import (
    CONFIG_PATH,
    load_client_config,
    save_client_config,
    test_server_connection,
)


def open_config_dialog(on_save_callback=None):
    current = load_client_config()

    root = tk.Tk()
    root.title("NequiPay POS — Configuración del Cliente")
    root.geometry("460x420")
    root.resizable(False, False)
    root.configure(bg="#F8FAFC")

    frame = tk.Frame(root, bg="#FFFFFF", bd=1, relief="solid", padx=20, pady=18)
    frame.pack(fill="both", expand=True, padx=14, pady=14)

    tk.Label(
        frame,
        text="Conexión al Servidor Central (LAN)",
        font=("Segoe UI", 12, "bold"),
        bg="#FFFFFF",
        fg="#0F172A",
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

    tk.Label(
        frame,
        text="Ingresa la IP estática del PC Servidor Windows 10/11.",
        font=("Segoe UI", 9),
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
    port_entry = tk.Entry(frame, textvariable=port_var, width=28, font=("Consolas", 10))
    port_entry.grid(row=3, column=1, sticky="ew", pady=4)

    # Etiqueta de Caja
    tk.Label(frame, text="Nombre de esta Caja:", bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 9, "bold")).grid(
        row=4, column=0, sticky="w", pady=4
    )
    label_var = tk.StringVar(value=current["pos_label"])
    tk.Entry(frame, textvariable=label_var, width=28, font=("Segoe UI", 10)).grid(
        row=4, column=1, sticky="ew", pady=4
    )

    # Volumen de Audio
    tk.Label(frame, text="Volumen de Voz (%):", bg="#FFFFFF", fg="#0F172A", font=("Segoe UI", 9, "bold")).grid(
        row=5, column=0, sticky="w", pady=4
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
    ).grid(row=5, column=1, sticky="ew", pady=4)

    # Modo Kiosco
    kiosk_var = tk.BooleanVar(value=bool(current["kiosk_mode"]))
    tk.Checkbutton(
        frame,
        text="Abrir monitor web en modo ventana limpia (Kiosco)",
        variable=kiosk_var,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 9),
    ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 4))

    auto_open_var = tk.BooleanVar(value=bool(current["auto_open_browser"]))
    tk.Checkbutton(
        frame,
        text="Abrir monitor automáticamente al iniciar Windows",
        variable=auto_open_var,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 9),
    ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 8))

    status_var = tk.StringVar(value="Archivo local: " + CONFIG_PATH)
    status_label = tk.Label(
        frame,
        textvariable=status_var,
        bg="#F1F5F9",
        fg="#334155",
        font=("Segoe UI", 8),
        wraplength=390,
        justify="left",
        padx=8,
        pady=6,
    )
    status_label.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 12))

    def handle_test():
        try:
            port = int(port_var.get().strip())
        except ValueError:
            status_label.config(fg="#B91C1C", bg="#FEF2F2")
            status_var.set("Puerto inválido. Usa un número entre 1024 y 65535.")
            return
        ok, msg = test_server_connection(ip_var.get(), port)
        if ok:
            status_label.config(fg="#15803D", bg="#ECFDF5")
        else:
            status_label.config(fg="#B91C1C", bg="#FEF2F2")
        status_var.set(msg)

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
                "audio_volume": vol_var.get(),
                "kiosk_mode": kiosk_var.get(),
                "auto_open_browser": auto_open_var.get(),
            }
        )
        if on_save_callback is not None:
            on_save_callback(saved)
        root.destroy()

    btn_row = tk.Frame(frame, bg="#FFFFFF")
    btn_row.grid(row=9, column=0, columnspan=2, sticky="ew")

    tk.Button(
        btn_row,
        text="Probar Conexión",
        command=handle_test,
        bg="#FFFFFF",
        fg="#0F172A",
        font=("Segoe UI", 9, "bold"),
        padx=12,
        pady=6,
    ).pack(side="left")

    tk.Button(
        btn_row,
        text="Guardar y Conectar",
        command=handle_save,
        bg="#DA0081",
        fg="#FFFFFF",
        font=("Segoe UI", 9, "bold"),
        padx=14,
        pady=6,
    ).pack(side="right")

    frame.columnconfigure(1, weight=1)
    ip_entry.focus_set()
    root.mainloop()
