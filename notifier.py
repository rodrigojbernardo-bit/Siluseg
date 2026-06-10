"""Envío de cotizaciones por email (SMTP).

Configuración por variables de entorno (o editando los valores por defecto):

  SMTP_HOST  servidor SMTP            (default: smtp.gmail.com)
  SMTP_PORT  puerto con STARTTLS      (default: 587)
  SMTP_USER  casilla que envía        (default: rodrigojbernardo@gmail.com)
  SMTP_PASS  contraseña de aplicación (obligatoria; en Gmail se genera en
             https://myaccount.google.com/apppasswords)

Para Gmail NO sirve la contraseña normal de la cuenta: hay que activar la
verificación en dos pasos y generar una "contraseña de aplicación".
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "rodrigojbernardo@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "")


class ConfigError(Exception):
    pass


def enviar_email(destinatario, asunto, cuerpo, adjunto_path=None):
    if not SMTP_PASS:
        raise ConfigError(
            "Falta configurar SMTP_PASS (contraseña de aplicación del email). "
            "Ver instrucciones en notifier.py / DESPLIEGUE.md"
        )

    msg = EmailMessage()
    msg["From"] = SMTP_USER
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

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)
