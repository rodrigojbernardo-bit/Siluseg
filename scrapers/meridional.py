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


def _select2_open(page, field_id):
    """Abre el dropdown Select2 de un campo usando la API JS de Select2."""
    page.evaluate(f"$('#{field_id}').select2('open')")
    time.sleep(0.8)


def _select2_pick(page, search_text, option_text, timeout=15000):
    """Con el dropdown Select2 ya abierto: escribe para filtrar y hace click en la opción."""
    page.wait_for_selector('#select2-drop', state='visible', timeout=timeout)
    time.sleep(0.5)
    page.keyboard.type(search_text, delay=80)
    time.sleep(2)
    page.wait_for_selector(
        f'#select2-drop div.select2-result-label:has-text("{option_text}")',
        state='visible', timeout=timeout
    )
    page.click(f'#select2-drop div.select2-result-label:has-text("{option_text}")')
    time.sleep(1)


def run(session_id, sessions, dni, anio, marca, modelo_busqueda, provincia, localidad, sexo='M'):
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

        log('Abriendo Autos (nueva pestaña)...')
        with context.expect_page() as nueva_pestaña:
            page.click('span.app-sidebar__item-text:has-text("Autos")')
        cotizador = nueva_pestaña.value
        cotizador.wait_for_load_state('load', timeout=30000)
        time.sleep(4)
        log(f'URL cotizador: {cotizador.url}')

        # Esperar que el formulario cargue
        cotizador.wait_for_selector('#s2id_coUnidadNegocio', timeout=20000)
        time.sleep(2)

        # ── UNIDAD DE NEGOCIO ─────────────────────────────────────────────────
        log('Seleccionando Unidad de Negocio: PRODUCTORES MENSUAL...')
        _select2_open(cotizador, 'coUnidadNegocio')
        _select2_pick(cotizador, 'PRODUCTORES MENSUAL', 'PRODUCTORES MENSUAL')
        log('Unidad de negocio OK.')
        time.sleep(1)

        # ── PROVINCIA ─────────────────────────────────────────────────────────
        log(f'Seleccionando provincia: {provincia}...')
        _select2_open(cotizador, 'coProvincia')
        _select2_pick(cotizador, provincia, provincia)
        log(f'Provincia OK: {provincia}')
        time.sleep(2)  # esperar que carguen las localidades dependientes

        # ── LOCALIDAD (búsqueda remota — mín 2 chars) ─────────────────────────
        log(f'Seleccionando localidad: {localidad}...')
        _select2_open(cotizador, 'coLocalidad')
        cotizador.wait_for_selector('#select2-drop', state='visible', timeout=10000)
        time.sleep(0.5)
        cotizador.keyboard.type(localidad, delay=80)
        time.sleep(3)  # esperar carga remota
        cotizador.wait_for_selector(
            f'#select2-drop div.select2-result-label:has-text("{localidad}")',
            state='visible', timeout=15000
        )
        cotizador.click(f'#select2-drop div.select2-result-label:has-text("{localidad}")')
        time.sleep(1)
        log(f'Localidad OK: {localidad}')

        # ── CONTINÚA EN PRÓXIMOS PASOS ─────────────────────────────────────────
        # ── DATOS DEL VEHÍCULO ────────────────────────────────────────────────
        log('Desplazando a Datos del Vehículo...')
        cotizador.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1)

        log('Clickeando Ingreso Manual...')
        cotizador.click('i.fa-keyboard-o')
        time.sleep(2)

        # ── MARCA ─────────────────────────────────────────────────────────────
        log(f'Seleccionando marca: {marca}...')
        _select2_open(cotizador, 'coMarca')
        _select2_pick(cotizador, marca, marca)
        log(f'Marca OK: {marca}')
        time.sleep(1)

        # ── AÑO ───────────────────────────────────────────────────────────────
        log(f'Seleccionando año: {anio}...')
        _select2_open(cotizador, 'coAnnoFabricacion')
        _select2_pick(cotizador, anio, anio)
        log(f'Año OK: {anio}')
        time.sleep(1)

        # ── MODELO ────────────────────────────────────────────────────────────
        log(f'Buscando modelos para: {modelo_busqueda}...')
        _select2_open(cotizador, 'coModelo')
        cotizador.wait_for_selector('#select2-drop', state='visible', timeout=15000)
        time.sleep(0.5)
        cotizador.keyboard.type(modelo_busqueda, delay=80)
        time.sleep(3)

        modelos_raw = cotizador.evaluate("""
            () => Array.from(document.querySelectorAll('#select2-drop div.select2-result-label'))
                 .map((el, i) => ({ index: i, texto: el.innerText.trim() }))
                 .filter(o => o.texto)
        """)

        log(f'Modelos encontrados ({len(modelos_raw)}):')
        for m in modelos_raw:
            log(f'  [{m["index"]}] {m["texto"]}')

        # Seleccionar el primero por defecto (luego se implementará selección por usuario)
        if modelos_raw:
            cotizador.click(
                f'#select2-drop div.select2-result-label:has-text("{modelos_raw[0]["texto"][:30]}")'
            )
            log(f'Modelo seleccionado: {modelos_raw[0]["texto"]}')
        time.sleep(1)

        # ── USO DEL VEHÍCULO ──────────────────────────────────────────────────
        log('Seleccionando uso: PARTICULAR...')
        _select2_open(cotizador, 'coUsoVehiculo')
        _select2_pick(cotizador, 'PARTICULAR', 'PARTICULAR')
        log('Uso OK.')
        time.sleep(1)

        # ── RASTREADOR ────────────────────────────────────────────────────────
        log('Seleccionando rastreador: NO POSEE/NO INFORMA...')
        _select2_open(cotizador, 'coRastreador')
        _select2_pick(cotizador, 'NO POSEE', 'NO POSEE/NO INFORMA')
        log('Rastreador OK.')
        time.sleep(1)

        # ── DATOS DEL ASEGURADO ───────────────────────────────────────────────
        log('Desplazando a Datos del Asegurado...')
        cotizador.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        log('Clickeando Ingreso Manual (asegurado)...')
        cotizador.locator('i.fa-keyboard-o').nth(1).click()
        time.sleep(2)

        log('Ingresando email...')
        cotizador.fill('input#coEMail', 'info@siluseg.com.ar')
        time.sleep(0.5)

        log(f'Ingresando DNI: {dni}...')
        cotizador.fill('input#coNroDocumento', dni)
        time.sleep(0.5)

        log('Seleccionando estado civil: SOLTERO...')
        _select2_open(cotizador, 'coEstadoCivil')
        _select2_pick(cotizador, 'SOLTERO', 'SOLTERO')
        log('Estado civil OK.')
        time.sleep(1)

        sexo_meridional = 'Masculino' if sexo.upper() == 'M' else 'Femenino'
        log(f'Seleccionando género: {sexo_meridional}...')
        _select2_open(cotizador, 'coSexo')
        _select2_pick(cotizador, sexo_meridional, sexo_meridional)
        log(f'Género OK.')
        time.sleep(1)

        log('TODO: periodicidad, medio de pago, cuotas, cotizar...')

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
