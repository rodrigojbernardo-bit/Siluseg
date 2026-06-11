"""Configuración del bot de Federación Patronal.

Los valores se toman de variables de entorno para no dejar credenciales ni
rutas absolutas hardcodeadas en el código. Podés definirlas en un archivo
`.env` (ver `.env.example`) o exportarlas en la terminal antes de ejecutar.
"""

import os
from pathlib import Path

try:
    # Carga opcional de un archivo .env si python-dotenv está instalado.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# Carpeta exclusiva del bot con el perfil de Chrome ya "calentado" (que pasó
# Cloudflare al menos una vez de forma manual). NO debe ser el perfil que usás
# en tu Chrome normal, porque no puede estar abierto en simultáneo.
CHROME_PERFIL = os.environ.get(
    "FP_CHROME_PERFIL",
    str(Path.home() / "Desktop" / "SVO AUTOMATICO" / "chrome_perfil_bot"),
)

# Portal de login de Federación Patronal.
URL_LOGIN = os.environ.get(
    "FP_URL_LOGIN",
    "https://www.fedpat.com.ar/",
)

# Credenciales del portal.
FP_USUARIO = os.environ.get("FP_USUARIO", "")
FP_PASSWORD = os.environ.get("FP_PASSWORD", "")

# Tiempo máximo (ms) de espera a que aparezca el formulario de login. Le da
# margen para resolver el desafío de Cloudflare de forma manual.
TIMEOUT_LOGIN_MS = int(os.environ.get("FP_TIMEOUT_LOGIN_MS", "60000"))

# Pausa extra (segundos) tras detectar el formulario, para que el portal
# termine de estabilizarse antes de completar credenciales.
PAUSA_ESTABILIZACION_S = float(os.environ.get("FP_PAUSA_ESTABILIZACION_S", "5"))

# slow_mo de Playwright (ms entre acciones). Útil para depurar y para que el
# comportamiento parezca menos robótico.
SLOW_MO_MS = int(os.environ.get("FP_SLOW_MO_MS", "500"))

# headless=False mantiene la ventana visible para poder interactuar con el
# Cloudflare manualmente. Ponelo en "1" solo si el perfil ya nunca pide desafío.
HEADLESS = os.environ.get("FP_HEADLESS", "0") == "1"
