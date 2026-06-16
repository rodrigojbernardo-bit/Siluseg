"""Configuración y helpers compartidos por los scrapers."""

import os
import socket
import subprocess
import time
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


# Carpeta de datos propia del Chrome del cotizador (independiente del
# Chrome personal del usuario). chrome_cotizador.bat la siembra una vez
# copiando el perfil de confianza; si no existe, se crea limpia.
_BOOT_DIR = Path(__file__).resolve().parent.parent / ".chrome_boot"


def _puerto_abierto(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        s.connect(("127.0.0.1", int(port)))
        return True
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _buscar_chrome():
    for var, sub in (
        ("PROGRAMFILES", r"Google\Chrome\Application\chrome.exe"),
        ("PROGRAMFILES(X86)", r"Google\Chrome\Application\chrome.exe"),
        ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"),
    ):
        base = os.environ.get(var)
        if base:
            p = Path(base) / sub
            if p.exists():
                return str(p)
    # Linux/otros (por si se prueba fuera de Windows)
    for cand in ("/usr/bin/google-chrome", "/usr/bin/chromium-browser",
                 "/usr/bin/chromium"):
        if Path(cand).exists():
            return cand
    return None


def _lanzar_chrome_real(port):
    """Lanza un Chrome REAL como proceso aparte (no por Playwright) con el
    puerto de depuración. Al ser un Chrome normal, pasa Cloudflare como el
    navegador del usuario. Devuelve True si quedó el puerto escuchando."""
    exe = _buscar_chrome()
    if not exe:
        return False
    _BOOT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.Popen(
            [
                exe,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={_BOOT_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                "https://online.fedpat.com.ar/self/homeWin32.do",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False
    # Esperar a que abra el puerto (hasta ~25s)
    for _ in range(50):
        if _puerto_abierto(port):
            return True
        time.sleep(0.5)
    return _puerto_abierto(port)


def abrir_fedpat(pw, log=None):
    """Abre Federación en un Chrome REAL con carpeta propia, vía CDP.

    1. Si ya hay un Chrome con el puerto de depuración abierto, se conecta.
    2. Si no, lanza un Chrome real (proceso aparte, no Playwright) con su
       carpeta de datos propia .chrome_boot y se conecta a él. Al ser un
       Chrome normal, pasa la verificación de Cloudflare como tu navegador.
    3. Solo si todo falla, cae al navegador interno de Playwright.

    Devuelve (page, cerrar, chrome_real).
    """
    port = os.environ.get("COTI_CHROME_PORT", "9222")

    if not _puerto_abierto(port):
        if log:
            log("Abriendo Chrome del cotizador (carpeta propia)...")
        _lanzar_chrome_real(port)

    if _puerto_abierto(port):
        try:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            # Usar la pestaña que ya abrió el Chrome (la que se ve en pantalla,
            # donde Turnstile se dibuja). Si no hay, abrir una.
            paginas = [p for p in ctx.pages if not p.is_closed()] if ctx.pages else []
            page = paginas[0] if paginas else ctx.new_page()
            try:
                page.bring_to_front()
            except Exception:
                pass

            def cerrar():
                # No cerramos la pestaña: es el Chrome propio del cotizador.
                pass

            return page, cerrar, True
        except Exception:
            pass

    if log:
        log("No pude usar el Chrome real; uso el navegador interno "
            "(puede pedir verificación de Cloudflare).")
    context, page = lanzar_navegador(pw, perfil='fedpat')

    def cerrar():
        try:
            context.close()
        except Exception:
            pass

    return page, cerrar, False


def _token_turnstile(pg):
    """Lee el token que Cloudflare Turnstile completa al verificarse."""
    try:
        return pg.evaluate(
            "() => { const e = document.querySelector('[name=\"cf-turnstile-response\"]')"
            " || document.querySelector('#turnstileToken'); return e ? (e.value || '') : ''; }"
        ) or ""
    except Exception:
        return ""


def pasar_turnstile(page, log=None, timeout=60):
    """Pasa el Cloudflare Turnstile del login de Federación.

    Lo que importa no es el clic en sí, sino que Turnstile complete su
    TOKEN (input cf-turnstile-response). En un navegador de confianza el
    token se completa solo; si aparece el recuadro con la casilla, lo
    clickeamos. Esperamos hasta `timeout` a que el token esté listo.

    Devuelve True si el token quedó completo.
    """
    import time as _t
    pg = getattr(page, 'page', None) or page

    if log:
        log("Esperando la verificación de Cloudflare (Turnstile)...")

    _t.sleep(6)   # darle tiempo a que el recuadro se dibuje, como pediste

    inicio = _t.time()
    aviso_manual = False
    while _t.time() - inicio < timeout:
        tok = _token_turnstile(pg)
        if tok:
            if log:
                log("Verificación de Cloudflare completa. Espero unos segundos...")
            _t.sleep(3)
            return True
        # Si el recuadro ya se dibujó, intentar clickearlo
        _click_turnstile(pg, log)
        # A partir de cierto tiempo, avisar para que lo resuelvas a mano
        if not aviso_manual and _t.time() - inicio > 20:
            aviso_manual = True
            if log:
                log("Si ves el recuadro de Cloudflare en la ventana de Chrome, "
                    "marcalo a mano; sigo esperando.")
        _t.sleep(2)

    if log:
        log("Cloudflare no se verificó a tiempo; guardo la página para revisar.")
    _dump_login(pg, log)
    return False


def _click_turnstile(pg, log=None):
    """Hace clic en la casilla (<input type=checkbox>) de Cloudflare.

    Recorre TODOS los marcos (incluido el de Cloudflare) y clickea el
    checkbox como elemento; si no, clickea dentro del iframe del widget por
    posición. Devuelve True si clickeó algo.
    """
    try:
        pg.bring_to_front()
    except Exception:
        pass

    # 1) Buscar el checkbox como elemento, marco por marco. Priorizamos los
    #    marcos de Cloudflare.
    try:
        marcos = list(pg.frames)
    except Exception:
        marcos = []
    def _es_cf(fr):
        try:
            u = (fr.url or '').lower()
        except Exception:
            u = ''
        return ('challenges.cloudflare' in u or 'turnstile' in u or 'cloudflare' in u)
    marcos.sort(key=lambda f: 0 if _es_cf(f) else 1)

    for fr in marcos:
        for sel in ('input[type="checkbox"]', 'label', 'body'):
            try:
                el = fr.query_selector(sel)
                if not el:
                    continue
                if sel == 'body':
                    # solo clickear body si el marco es de Cloudflare (el check)
                    if not _es_cf(fr):
                        continue
                    el.click(position={'x': 30, 'y': 30}, force=True, timeout=2500)
                else:
                    el.click(force=True, timeout=2500)
                if log:
                    log(f"Clic en la casilla de Cloudflare ({sel}).")
                return True
            except Exception:
                continue

    # 2) Clic dentro del iframe del widget por posición relativa
    listas = []
    for sel in ('div.cf-turnstile iframe',
                'iframe[src*="challenges.cloudflare.com"]',
                'iframe[title*="Cloudflare"]',
                'iframe[title*="challenge"]',
                'iframe[title*="seguridad"]',
                'iframe[title*="human"]'):
        try:
            listas += (pg.query_selector_all(sel) or [])
        except Exception:
            pass
    try:
        for el in (pg.query_selector_all('iframe') or []):
            b = el.bounding_box()
            if b and b['width'] < 450 and b['height'] < 120:
                listas.append(el)
    except Exception:
        pass

    for el in listas:
        try:
            try:
                el.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass
            box = el.bounding_box()
            if not box:
                continue
            px = min(30, box['width'] / 2)
            py = box['height'] / 2
            try:
                el.click(position={'x': px, 'y': py}, force=True, timeout=3000)
            except Exception:
                pg.mouse.click(box['x'] + px, box['y'] + py)
            if log:
                log("Clic en la casilla de Cloudflare (iframe).")
            return True
        except Exception:
            continue
    return False


def _dump_login(pg, log=None):
    """Guarda en el Escritorio la página de login (foto + HTML + lista de
    marcos) para poder ver cómo es la casilla de Cloudflare."""
    try:
        from pathlib import Path
        d = Path.home() / 'Desktop'
        if not d.exists():
            d = Path.home()
        base = d / 'fedpat_login'
        try:
            pg.screenshot(path=str(base.with_suffix('.png')), full_page=True)
        except Exception:
            pass
        try:
            partes = [f'URL: {pg.url}', '', 'MARCOS (frames):']
            for fr in pg.frames:
                partes.append(f'  - {fr.url}')
                try:
                    n_cb = len(fr.query_selector_all('input[type="checkbox"]'))
                    n_if = len(fr.query_selector_all('iframe'))
                    partes.append(f'      checkboxes={n_cb}  iframes={n_if}')
                except Exception:
                    pass
            base.with_suffix('.txt').write_text('\n'.join(partes), encoding='utf-8')
        except Exception:
            pass
        try:
            base.with_suffix('.html').write_text(pg.content(), encoding='utf-8')
        except Exception:
            pass
        if log:
            log('Guardé la página de login en el Escritorio (fedpat_login.*).')
    except Exception:
        pass


def clic_checkbox_cloudflare(page, log=None, antes=5, despues=6):
    """Secuencia para la casilla de Cloudflare que aparece en el login:

    1) espera `antes` segundos a que la casilla se habilite,
    2) hace clic en el <input type="checkbox">,
    3) espera `despues` segundos a que se ponga en verde (verificada).

    Se usa SIEMPRE en la página de login (la casilla puede estar sin el
    cartel de 'verificación de seguridad'). Devuelve True si clickeó.
    """
    import time as _t
    pg = getattr(page, 'page', None) or page
    if log:
        log('Esperando la casilla de verificación...')
    _t.sleep(antes)
    # Reintentar el clic por si la casilla tarda en habilitarse
    clickeo = False
    for _ in range(3):
        if _click_turnstile(pg, log):
            clickeo = True
            break
        _t.sleep(2)
    if clickeo:
        if log:
            log(f'Casilla marcada; espero {despues}s a que se verifique...')
        _t.sleep(despues)
    else:
        if log:
            log('No encontré la casilla automáticamente. Guardo la página '
                'para revisar y, si aparece, marcala en la ventana de Chrome.')
        _dump_login(pg, log)        # capturar la estructura real
        _t.sleep(despues)
    return clickeo


def esperar_verificacion(page, log=None, timeout=180):
    """Si Cloudflare muestra la verificación, hace clic en la casilla y espera.

    Detecta la pantalla antibot de Cloudflare, hace clic automáticamente en
    la casilla "no soy un robot" y le da unos segundos a que procese y
    redirija. Si el clic automático no encuentra la casilla, igual espera a
    que la resuelvas a mano en la ventana (que está a la vista).

    Devuelve True si está despejado para seguir.
    """
    import time as _t

    pg = getattr(page, 'page', None) or page   # si es Frame, usar su Page

    # Frases/elementos típicos de la pantalla antibot de Cloudflare.
    señales = [
        "verificación de seguridad",
        "verificacion de seguridad",
        "verificando que usted",
        "checking your browser",
        "just a moment",
        "un servicio de seguridad",
        "no es un bot",
        "needs to review the security",
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
        log("Cloudflare pidió verificación; intento pasarla...")

    inicio = _t.time()
    while _t.time() - inicio < timeout:
        # Intentar clic en la casilla; si la encuentra, esperar 6s a que
        # Cloudflare procese y deje continuar.
        clickeo = _click_turnstile(pg, log)
        _t.sleep(6 if clickeo else 3)
        if not _hay_desafio():
            if log:
                log("Verificación superada. Espero unos segundos a que "
                    "termine de procesar...")
            _t.sleep(5)
            return True
    if log:
        log("La verificación sigue. Hacé clic en la casilla de la ventana "
            "de Chrome y volvé a intentar.")
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


def encontrar_ui_con(context, selector, log=None, timeout=30):
    """Busca `selector` en todas las ventanas Y sus marcos internos.

    Devuelve la Page o el Frame donde está el elemento (ambos soportan
    fill/click/evaluate/wait_for_selector), o None si no aparece.
    Necesario porque el portal de Federación es viejo: puede abrir el
    contenido en otra ventana o dentro de un marco (frame).
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
            try:
                for fr in p.frames:
                    try:
                        if fr != p.main_frame and fr.query_selector(selector):
                            if log:
                                log('(el contenido está dentro de un marco de la página)')
                            return fr
                    except Exception:
                        pass
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
        # Si llega un Frame, trabajar con su Page contenedora.
        page = getattr(page, 'page', page)
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
