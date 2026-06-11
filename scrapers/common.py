"""Configuración y helpers compartidos por los scrapers."""

import os
from pathlib import Path

# Con COTI_HEADLESS=1 los navegadores corren ocultos (sin ventanas).
# Recomendado cuando se usa el cotizador a distancia, para que nadie
# pueda cerrar las ventanas por accidente mientras cotiza.
HEADLESS = os.environ.get("COTI_HEADLESS", "").strip().lower() in ("1", "true", "si", "sí")

# Carpeta donde se guardan los perfiles persistentes de cada navegador.
# Mantener el perfil permite conservar la cookie que entrega la
# "verificación de seguridad" antibot, así no aparece en cada cotización.
_PROFILES_DIR = Path(__file__).resolve().parent.parent / ".browser_profiles"

# Banderas que evitan que el sitio detecte que es un navegador automatizado.
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]

_STEALTH_JS = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)


def lanzar_navegador(pw, perfil, headless=None):
    """Abre un navegador resistente a verificaciones antibot.

    Usa el Chrome real instalado (channel='chrome') con un perfil
    persistente. Si Chrome no está instalado, cae al Chromium de Playwright.
    Devuelve (context, page); cerrar con context.close().
    """
    if headless is None:
        headless = HEADLESS

    user_data_dir = _PROFILES_DIR / perfil
    user_data_dir.mkdir(parents=True, exist_ok=True)

    kwargs = dict(
        user_data_dir=str(user_data_dir),
        headless=headless,
        args=_STEALTH_ARGS,
        accept_downloads=True,
        viewport={"width": 1366, "height": 768},
        locale="es-AR",
    )

    try:
        context = pw.chromium.launch_persistent_context(channel="chrome", **kwargs)
    except Exception:
        # Chrome no instalado: usar el Chromium que trae Playwright.
        context = pw.chromium.launch_persistent_context(**kwargs)

    try:
        context.add_init_script(_STEALTH_JS)
    except Exception:
        pass

    page = context.pages[0] if context.pages else context.new_page()
    return context, page


def abrir_fedpat(pw):
    """Abre Federación reutilizando un Chrome real ya abierto por el usuario.

    Si hay un Chrome escuchando en el puerto de depuración (lo abre el
    archivo chrome_cotizador.bat), se conecta a ÉL: es un navegador de
    verdad, con la confianza de Cloudflare, así pasa la verificación de
    seguridad igual que cuando navegás a mano.

    Si no hay ninguno, cae al navegador propio con perfil persistente.
    Devuelve (page, cerrar) — llamar cerrar() al terminar.
    """
    port = os.environ.get("COTI_CHROME_PORT", "9222")
    try:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def cerrar():
            # No cerramos el Chrome del usuario: solo soltamos la conexión.
            pass

        return page, cerrar, True  # conectado a Chrome real
    except Exception:
        pass

    context, page = lanzar_navegador(pw, perfil='fedpat')

    def cerrar():
        try:
            context.close()
        except Exception:
            pass

    return page, cerrar, False


def mensaje_error(e):
    """Traduce errores técnicos de Playwright a mensajes entendibles."""
    s = str(e)
    if type(e).__name__ == "TargetClosedError" or "has been closed" in s:
        return (
            "La ventana del navegador se cerró antes de terminar la cotización. "
            "No cierres las ventanas de Chromium mientras se cotiza: se cierran "
            "solas al finalizar. Volvé a intentar."
        )
    if type(e).__name__ == "TimeoutError":
        return (
            "El portal tardó demasiado en responder o no se encontró el dato "
            f"esperado. Detalle: {s}"
        )
    return s
