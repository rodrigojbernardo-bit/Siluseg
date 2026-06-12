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
    """Abre Federación reutilizando TU Chrome (el que ya pasa Cloudflare).

    Si hay un Chrome escuchando en el puerto de depuración (lo abre el
    archivo chrome_cotizador.bat), se conecta a ÉL y le abre una PESTAÑA
    NUEVA solo para Federación, sin tocar las pestañas en las que estás
    trabajando. Al terminar, cierra únicamente esa pestaña; tu Chrome
    sigue abierto.

    Si no hay ninguno, cae al navegador propio con perfil persistente.
    Devuelve (page, cerrar, chrome_real).
    """
    port = os.environ.get("COTI_CHROME_PORT", "9222")
    try:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        # Pestaña nueva, dedicada a Federación (no robamos la pestaña activa).
        page = ctx.new_page()

        def cerrar():
            # Cerramos SOLO la pestaña de Federación; tu Chrome sigue intacto.
            try:
                page.close()
            except Exception:
                pass

        return page, cerrar, True  # conectado a tu Chrome real
    except Exception:
        pass

    context, page = lanzar_navegador(pw, perfil='fedpat')

    def cerrar():
        try:
            context.close()
        except Exception:
            pass

    return page, cerrar, False


def esperar_verificacion(page, log=None, timeout=180):
    """Si Cloudflare muestra la verificación, espera a que la resuelvas a mano.

    Cloudflare puede pedir la verificación en cualquier momento. Como la
    ventana de Chrome está a la vista, este helper detecta la pantalla de
    'verificación de seguridad' y espera (hasta `timeout` segundos) a que
    desaparezca, dándote tiempo a resolverla manualmente. No la 'saltea':
    simplemente no avanza hasta que vos pasaste.

    Devuelve True si está despejado para seguir.
    """
    import time as _t

    # Frases/elementos típicos de la pantalla antibot de Cloudflare.
    señales = [
        "verificación de seguridad",
        "verificacion de seguridad",
        "verificando que usted",
        "checking your browser",
        "just a moment",
        "un servicio de seguridad",
        "no es un bot",
    ]

    def _hay_desafio():
        try:
            cuerpo = (page.inner_text("body", timeout=2000) or "").lower()
        except Exception:
            return False
        return any(s in cuerpo for s in señales)

    if not _hay_desafio():
        # El desafío puede tardar un instante en aparecer; mirar de nuevo
        # antes de dar el OK.
        _t.sleep(2)
        if not _hay_desafio():
            return True

    if log:
        log("Cloudflare pidió verificación. Resolvela en la ventana de Chrome; "
            "te espero...")

    inicio = _t.time()
    while _t.time() - inicio < timeout:
        _t.sleep(3)
        if not _hay_desafio():
            if log:
                log("Verificación superada. Espero unos segundos a que "
                    "termine de procesar...")
            # Cloudflare redirige y recarga después de verificar: darle
            # tiempo a que termine antes de tocar la página.
            _t.sleep(5)
            return True
    if log:
        log("Pasaron los minutos de espera y la verificación sigue. "
            "Volvé a intentar la cotización.")
    return False


def encontrar_pagina_con(context, selector, log=None, timeout=30):
    """Busca, entre todas las ventanas abiertas, la que tenga `selector`.

    Portales viejos (como el de Federación) abren la aplicación en una
    ventana nueva tras el login; el programa se quedaría mirando la
    ventana vieja. Esto recorre todas las ventanas (y sus marcos internos)
    y devuelve la que realmente tiene el menú/elemento buscado.
    """
    import time as _t
    inicio = _t.time()
    while _t.time() - inicio < timeout:
        for p in list(context.pages):
            try:
                if p.query_selector(selector):
                    return p
            except Exception:
                pass
            # buscar también dentro de marcos (frames) de la página
            try:
                for fr in p.frames:
                    if fr.query_selector(selector):
                        if log:
                            log('El menú está dentro de un marco de la página.')
                        return p
            except Exception:
                pass
        _t.sleep(1)
    return None


def guardar_diagnostico(page, nombre='diagnostico', log=None):
    """Guarda en el Escritorio una foto + el HTML + las URLs de las ventanas.

    Sirve para ver exactamente en qué pantalla se trabó la automatización
    sin tener que estar mirando en vivo.
    """
    try:
        from pathlib import Path
        escritorio = Path.home() / 'Desktop'
        if not escritorio.exists():
            escritorio = Path.home()
        base = escritorio / nombre
        try:
            page.screenshot(path=str(base.with_suffix('.png')), full_page=True)
        except Exception:
            pass
        try:
            html = page.content()
            base.with_suffix('.html').write_text(html, encoding='utf-8')
        except Exception:
            pass
        try:
            ctx = page.context
            urls = []
            for p in ctx.pages:
                try:
                    urls.append(f'{p.title()}  ->  {p.url}')
                except Exception:
                    urls.append(p.url)
            base.with_suffix('.txt').write_text(
                'Ventanas abiertas:\n' + '\n'.join(urls), encoding='utf-8')
        except Exception:
            pass
        if log:
            log(f'Guardé diagnóstico en el Escritorio: {nombre}.png / .html / .txt')
    except Exception:
        pass


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
