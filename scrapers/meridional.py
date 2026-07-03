from playwright.sync_api import sync_playwright
import time
import json
import re
import unicodedata

URL_LOGIN = "https://ws8.meridionalnet.com.ar/Account/Login?ReturnUrl=%2F"
USUARIO   = "RJBERNARDO"
PASSWORD  = "AIU2024a"


EXCLUIR = {
    'C1 - INCENDIO, ROBO TOTAL Y PARCIAL',
    'C1 TOTAL - INCENDIO, ROBO TOTAL Y PARCIAL',
    'C - TERCEROS COMPLETOS',
}


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


def _normalizar(texto):
    """Mayúsculas, sin acentos y sin espacios repetidos, para comparar nombres."""
    t = unicodedata.normalize('NFD', texto)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', t).strip().upper()


# Nombres alternativos con los que las aseguradoras suelen listar cada provincia
_ALIAS_PROVINCIA = {
    'CAPITAL FEDERAL': [
        'CAPITAL FEDERAL',
        'CIUDAD AUTONOMA DE BUENOS AIRES',
        'CIUDAD DE BUENOS AIRES',
        'C.A.B.A.',
        'CABA',
    ],
    'BUENOS AIRES': [
        'BUENOS AIRES',
        'PROVINCIA DE BUENOS AIRES',
        'BS. AS.',
    ],
}


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


def run(session_id, sessions, dni, anio, marca, modelo_busqueda, provincia, localidad, sexo='M', email=''):
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
        cotizador.wait_for_selector('#select2-drop', state='visible', timeout=15000)
        time.sleep(1)

        # Leer todas las provincias que ofrece Meridional (sin filtrar)
        opciones_prov = cotizador.evaluate("""
            () => Array.from(document.querySelectorAll('#select2-drop div.select2-result-label'))
                .map(el => el.innerText.trim())
                .filter(t => t.length > 0)
        """)
        log(f'Provincias en Meridional: {opciones_prov}')

        objetivo    = _normalizar(provincia)
        candidatos  = [_normalizar(a) for a in _ALIAS_PROVINCIA.get(objetivo, [objetivo])]
        prov_elegida = None
        # 1) coincidencia exacta (normalizada) con el nombre o alguno de sus alias
        for op in opciones_prov:
            if _normalizar(op) in candidatos:
                prov_elegida = op
                break
        # 2) coincidencia parcial (uno contiene al otro)
        if prov_elegida is None:
            for op in opciones_prov:
                n = _normalizar(op)
                if any(c in n or n in c for c in candidatos):
                    prov_elegida = op
                    break
        if prov_elegida is None:
            raise Exception(
                f'Provincia "{provincia}" no encontrada en Meridional. '
                f'Opciones: {opciones_prov}'
            )

        idx_prov = opciones_prov.index(prov_elegida)
        cotizador.click(f'#select2-drop div.select2-result-label >> nth={idx_prov}')
        time.sleep(1)
        log(f'Provincia OK: {prov_elegida}')
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

        if not modelos_raw:
            raise Exception('No se encontraron modelos en Meridional.')

        # Enviar lista al front-end para que el usuario seleccione
        s['queue'].put({'type': 'modelos_meridional',
                        'modelos': [m['texto'] for m in modelos_raw]})
        s['status'] = 'esperando_modelo_meridional'
        model_event_mer = s['model_event_meridional']
        model_event_mer.clear()
        log('Esperando selección de modelo Meridional (máx 3 min)...')
        model_event_mer.wait(timeout=180)

        modelo_index = s.get('modelo_index_meridional', 0)
        modelo_elegido = modelos_raw[modelo_index]
        cotizador.click(
            f'#select2-drop div.select2-result-label:has-text("{modelo_elegido["texto"][:30]}")'
        )
        log(f'Modelo seleccionado: {modelo_elegido["texto"]}')
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
        cotizador.fill('input#coEMail', email or 'info@siluseg.com.ar')
        time.sleep(0.5)

        log(f'Ingresando DNI: {dni}...')
        cotizador.fill('input#coNroDocumento', dni)
        time.sleep(0.5)

        log('Ingresando apellido...')
        cotizador.fill('input#coApellidoRazonSocial', 'BERNARDO')
        time.sleep(0.3)

        log('Ingresando nombre...')
        cotizador.fill('input#coNombres', 'RODRIGO BERNARDO')
        time.sleep(0.3)

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

        # ── FECHA DE NACIMIENTO ───────────────────────────────────────────────
        log('Ingresando fecha de nacimiento...')
        cotizador.fill('input#coFechaNacimiento', '01/01/1980')
        cotizador.press('input#coFechaNacimiento', 'Tab')
        time.sleep(0.5)

        # ── DATOS DE LA OPERACIÓN ─────────────────────────────────────────────
        log('Desplazando a Datos de la Operación...')
        cotizador.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        log('Seleccionando medio de pago: TARJETA DE CREDITO...')
        _select2_open(cotizador, 'coMedioPago')
        _select2_pick(cotizador, 'TARJETA', 'TARJETA DE CREDITO')
        log('Medio de pago OK.')
        time.sleep(1)

        log('Seleccionando cuotas: 1...')
        _select2_open(cotizador, 'coCuotas')
        _select2_pick(cotizador, '1', '1')
        log('Cuotas OK.')
        time.sleep(1)

        log('Seleccionando comisión: 15...')
        _select2_open(cotizador, 'coComision')
        _select2_pick(cotizador, '15', '15')
        log('Comisión OK.')
        time.sleep(1)

        log('Seleccionando descuento/recargo: -10...')
        _select2_open(cotizador, 'coPorcDescuentoRecargoPrima')
        _select2_pick(cotizador, '-10', '-10')
        log('Descuento/recargo OK.')
        time.sleep(1)

        # ── COTIZAR ───────────────────────────────────────────────────────────
        log('Clickeando COTIZAR...')
        cotizador.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        cotizador.click('span:has-text("COTIZAR")')
        cotizador.wait_for_load_state('networkidle', timeout=30000)
        time.sleep(5)
        log('Página de resultados cargada.')

        # ── EXTRAER COBERTURAS ────────────────────────────────────────────────
        log('Extrayendo coberturas...')
        coberturas_raw = cotizador.evaluate("""
            () => {
                const resultado = [];

                // Recorrer todas las tablas buscando FULL CAR y TERCEROS
                for (const table of document.querySelectorAll('table')) {
                    const texto = table.innerText.toUpperCase();
                    if (!texto.includes('FULL CAR') && !texto.includes('TERCERO')) continue;

                    // Detectar índices de columnas por header
                    const ths = Array.from(table.querySelectorAll('th'))
                                     .map(th => th.innerText.trim().toLowerCase());
                    const iCob = ths.findIndex(h => h.includes('cobertura'));
                    const iPremio = ths.findIndex(h => h.includes('premio'));
                    const iImp = ths.findIndex(h => h.includes('importe'));

                    for (const row of table.querySelectorAll('tbody tr')) {
                        const cells = Array.from(row.querySelectorAll('td'))
                                           .map(td => td.innerText.trim());
                        if (cells.length < 2) continue;

                        // Cobertura: usar columna detectada o la primera celda con texto largo
                        const nombre = iCob >= 0 ? cells[iCob]
                            : cells.find(c => c.length > 5 && !/^[\d.,]+$/.test(c)) || '';

                        // Importe: última columna con formato número 000.000,00
                        const precio_texto = iImp >= 0 ? cells[iImp]
                            : [...cells].reverse().find(c => /\\d{1,3}(\\.\\d{3})+,\\d{2}/.test(c)) || '';

                        const premio_texto = iPremio >= 0 ? cells[iPremio] : '';

                        if (nombre && precio_texto) {
                            resultado.push({
                                nombre: nombre,
                                premio: premio_texto,
                                importe: precio_texto,
                            });
                        }
                    }
                }

                return resultado;
            }
        """)

        coberturas = []
        for c in coberturas_raw:
            if c['nombre'].strip() in EXCLUIR:
                log(f'  [omitida] {c["nombre"]}')
                continue
            precio = _parse_precio(c['importe'])
            if precio:
                coberturas.append({
                    'nombre':    c['nombre'],
                    'precio':    precio,
                    'deducible': '',
                })
                log(f'  Cobertura: {c["nombre"]} | Premio: {c["premio"]} | Importe: {c["importe"]}')

        log(f'Total coberturas extraídas: {len(coberturas)}')

        capital_text = cotizador.evaluate("""
            () => {
                const body = document.body.innerText;
                const m = body.match(
                    /(?:suma|capital)\\s+asegur(?:ada|able)[^\\$\\d\\n]{0,30}\\$?\\s*([\\d.,]+)/i
                );
                return m ? '$' + m[1].trim() : '';
            }
        """)

        sessions[session_id]['resultados']['Meridional'] = {
            'aseguradora': 'Meridional',
            'ok':          True,
            'coberturas':  coberturas,
            'capital':     capital_text or '',
        }
        log('¡Cotización completada!')

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
