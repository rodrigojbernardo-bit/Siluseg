"""Traduce el nombre visible de un perfil de Chrome (ej: "Siluseg BOOT")
al nombre de su carpeta interna (ej: "Profile 3").

Chrome muestra "Siluseg BOOT" pero en disco la carpeta se llama
"Profile N". El flag --profile-directory necesita el nombre de la
CARPETA, no el visible. Este script lee el archivo "Local State" de
Chrome y devuelve la carpeta correspondiente.

Imprime el nombre de carpeta por salida estándar para que lo use
chrome_cotizador.bat. Si no lo encuentra, imprime el nombre visible tal
cual (último recurso).

Configurable con variables de entorno:
  COTI_CHROME_PROFILE    nombre visible del perfil (default: "Siluseg BOOT")
  COTI_CHROME_USERDATA   carpeta "User Data" de Chrome (default: la real)
"""

import json
import os
import sys
from pathlib import Path


def _user_data_dir():
    env = os.environ.get("COTI_CHROME_USERDATA")
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    return Path(base) / "Google" / "Chrome" / "User Data"


def resolver(display, user_data):
    ls = Path(user_data) / "Local State"
    try:
        data = json.loads(ls.read_text(encoding="utf-8"))
        cache = data.get("profile", {}).get("info_cache", {})
        objetivo = display.strip().lower()
        for carpeta, info in cache.items():
            if (info.get("name", "") or "").strip().lower() == objetivo:
                return carpeta
    except Exception:
        pass
    return display  # último recurso: tal vez ya es el nombre de carpeta


if __name__ == "__main__":
    display = os.environ.get("COTI_CHROME_PROFILE", "Siluseg BOOT")
    sys.stdout.write(resolver(display, _user_data_dir()))
