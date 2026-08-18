"""Envío de alertas cuando el detector marca anomalías.

Soporta dos canales, seleccionables en config.yaml (`notification.channel`):
Telegram (bot de BotFather) y email (SMTP simple). Si faltan credenciales,
no lanza excepción: avisa por consola y no envía nada, para que `run.py`
siga funcionando sin credenciales configuradas.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import requests


def format_message(metric_name: str, date: str, value: float, expected: float) -> str:
    """Mensaje tipo: "⚠️ Métrica cayó un 24% respecto a la media ..."."""
    if expected is None or expected != expected:  # NaN: sin ventana previa completa
        return (
            f"⚠️ {metric_name} — anomalía detectada el {date}: "
            f"valor {value:.2f} (sin línea base completa todavía)"
        )

    diff_pct = ((value - expected) / expected * 100) if expected else 0.0
    direction = "subió" if diff_pct >= 0 else "cayó"
    return (
        f"⚠️ {metric_name} {direction} un {abs(diff_pct):.0f}% respecto a la media "
        f"esperada — valor: {value:.2f}, esperado: {expected:.2f} (fecha: {date})"
    )


def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        print("[notify] Telegram no configurado (falta bot_token o chat_id); alerta no enviada.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
    if resp.status_code != 200:
        print(f"[notify] Error enviando a Telegram ({resp.status_code}): {resp.text}")
        return False
    return True


def send_email(message: str, subject: str, cfg: dict[str, Any]) -> bool:
    required = ["smtp_host", "smtp_port", "username", "password", "from_addr", "to_addr"]
    if not all(cfg.get(k) for k in required):
        print("[notify] Email no configurado (faltan credenciales SMTP); alerta no enviada.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = cfg["to_addr"]
    msg.set_content(message)

    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"])) as server:
        server.starttls(context=context)
        server.login(cfg["username"], cfg["password"])
        server.send_message(msg)
    return True


def notify(messages: list[str], config: dict[str, Any]) -> None:
    """Despacha `messages` por el canal configurado en config['notification']."""
    if not messages:
        return

    notif_cfg = config.get("notification", {})
    channel = notif_cfg.get("channel", "none")
    body = "\n\n".join(messages)

    if channel == "telegram":
        tg = notif_cfg.get("telegram", {})
        send_telegram(body, tg.get("bot_token", ""), tg.get("chat_id", ""))
    elif channel == "email":
        email_cfg = notif_cfg.get("email", {})
        subject = f"[anomaly-alerts] {len(messages)} anomalía(s) detectada(s)"
        try:
            send_email(body, subject, email_cfg)
        except Exception as exc:  # No cortar run.py por un fallo de envío
            print(f"[notify] Error enviando email: {exc}")
    elif channel == "none":
        print("[notify] Canal de notificación desactivado (channel: none). Alertas solo por consola:")
        print(body)
    else:
        print(f"[notify] Canal de notificación desconocido: {channel!r}")
