"""Envío de cotizaciones por email (SMTP).

Configurado para la casilla produccion@siluseg.com.ar (hosting Ferozo).
Se puede sobreescribir cualquier valor con variables de entorno:

  SMTP_HOST  servidor SMTP      (default: c2102521.ferozo.com)
  SMTP_PORT  puerto             (default: 465, SSL directo)
  SMTP_USER  casilla que envía  (default: produccion@siluseg.com.ar)
  SMTP_PASS  contraseña

Con puerto 465 se usa SSL directo (SMTP_SSL); con 587, STARTTLS.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

SMTP_HOST = os.environ.get("SMTP_HOST", "c2102521.ferozo.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "produccion@siluseg.com.ar")
SMTP_PASS = os.environ.get("SMTP_PASS", "Naranja2024@")


class ConfigError(Exception):
    pass


def enviar_email(destinatario, asunto, cuerpo, adjunto_path=None):
    if not SMTP_PASS:
        raise ConfigError(
            "Falta configurar SMTP_PASS (contraseña de la casilla de email)."
        )

    msg = EmailMessage()
    msg["From"] = f"Siluseg Seguros <{SMTP_USER}>"
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    if adjunto_path:
        adjunto_path = Path(adjunto_path)
        msg.add_attachment(
            adjunto_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=adjunto_path.name,
        )

    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
