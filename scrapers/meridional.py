from playwright.sync_api import sync_playwright
import time
import json
import re

URL_LOGIN = "https://ws8.meridionalnet.com.ar/Account/Login?ReturnUrl=%2F"
USUARIO   = "RJBERNARDO"
PASSWORD  = "AIU2024a"


def _parse_precio(texto):
    """'501.359,29' → 501359.29"""
    if not texto:
        return None
    limpio = texto.strip().replace('.', '').replace(',', '.')
    try:
        v = float(limpio)
        return v if v > 0 else None
    except Exception:
        return None


def _select2_pick(page, search_text, option_text, timeout=15000):
    """Con el dropdown Select2 ya abierto: escribe para filtrar y hace click en la opción."""
    page.wait_for_selector('.select2-drop:not(.select2-display-none)', timeout=timeout)
    time.sleep(0.3)
    page.fill('.select2-input', '')
    page.type('.select2-input', search_text, delay=60)
    time.sleep(1.5)
    page.wait_for_selector(
        f'div.select2-result-label:has-text("{option_text}")',
        timeout=timeout
    )
    page.click(f'div.select2-result-label:has-text("{option_text}")')
    time.sleep(1)


def run(session_id, sessions, dni, anio, marca, modelo_busqueda, provincia, localidad):
    s = sessions[session_id]
    q = s['queue']

    def log(msg):
        q.put({'type': 'log', 'msg': f'[Meridional] {msg}'})

    pw      = None
    browser = None

    try:
        log('Iniciando navegador...')
        pw      = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page    = context.new_page()

        # ── LOGIN ─────────────────────────────────────────────────────────────
        log('Abriendo portal...')
        page.goto(URL_LOGIN, wait_until='load', timeout=30000)
        time.sleep(2)

        log('Ingresando credenciales...')
        page.fill('input#Usuario', USUARIO)
        time.sleep(0.3)
        page.fill('input#password', PASSWORD)
        time.sleep(0.5)
        page.click('input[type="submit"][value="Ingresar"]')
        try:
            page.wait_for_url(lambda url: 'Login' not in url, timeout=15000)
        except Exception:
            page.wait_for_load_state('load', timeout=15000)
        time.sleep(3)
        log('Sesión iniciada.')

        # ── CERRAR NOTIFICACIONES (aparece casi siempre) ──────────────────────
        try:
            notif = page.query_selector(
                'span.app-navbar__user-menu-name:has-text("Notificaciones")'
            )
            if notif and notif.is_visible():
                log('Cerrando panel de notificaciones...')
                notif.click()
                time.sleep(1.5)
        except Exception:
            pass

        # ── NAVEGAR A COTIZADORES → AUTOS ─────────────────────────────────────
        log('Abriendo Cotizadores...')
        page.click('span.app-sidebar__item-text:has-text("Cotizadores")')
        time.sleep(2)

        log('Abriendo Autos...')
        page.click('span.app-sidebar__item-text:has-text("Autos")')
        page.wait_for_load_state('load', timeout=30000)
        time.sleep(4)
        log(f'URL cotizador: {page.url}')

        # Esperar que aparezcan los Select2 del formulario
        page.wait_for_selector(
            '.select2-container:not(.select2-container-disabled)',
            timeout=20000
        )
        time.sleep(2)

        # ── UNIDAD DE NEGOCIO (1er Select2) ───────────────────────────────────
        log('Seleccionando Unidad de Negocio: PRODUCTORES MENSUAL...')
        page.locator(
            '.select2-container:not(.select2-container-disabled) .select2-choice'
        ).first.click()
        _select2_pick(page, 'PRODUCTORES MENSUAL', 'PRODUCTORES MENSUAL')
        log('Unidad de negocio OK.')
        time.sleep(1)

        # ── PROVINCIA (2do Select2) ────────────────────────────────────────────
        log(f'Seleccionando provincia: {provincia}...')
        page.locator(
            '.select2-container:not(.select2-container-disabled) .select2-choice'
        ).nth(1).click()
        _select2_pick(page, provincia, provincia)
        log(f'Provincia OK: {provincia}')
        time.sleep(2)  # esperar que carguen las localidades dependientes

        # ── LOCALIDAD (3er Select2 — búsqueda remota, mín 2 chars) ────────────
        log(f'Seleccionando localidad: {localidad}...')
        page.locator(
            '.select2-container:not(.select2-container-disabled) .select2-choice'
        ).nth(2).click()
        page.wait_for_selector('.select2-drop:not(.select2-display-none)', timeout=10000)
        time.sleep(0.3)
        page.fill('.select2-input', '')
        page.type('.select2-input', localidad, delay=80)
        time.sleep(2.5)  # esperar carga remota de opciones
        page.wait_for_selector(
            f'div.select2-result-label:has-text("{localidad}")',
            timeout=15000
        )
        page.click(f'div.select2-result-label:has-text("{localidad}")')
        time.sleep(1)
        log(f'Localidad OK: {localidad}')

        # ── CONTINÚA EN PRÓXIMOS PASOS ─────────────────────────────────────────
        log('TODO: datos del vehículo, asegurado, cotizar...')

    except Exception as e:
        import traceback
        log(f'Error: {traceback.format_exc()}')
        sessions[session_id]['resultados']['Meridional'] = {
            'aseguradora': 'Meridional',
            'ok':          False,
            'error':       str(e),
            'coberturas':  [],
        }
    finally:
        try:
            if browser: browser.close()
        except Exception:
            pass
        try:
            if pw: pw.stop()
        except Exception:
            pass
