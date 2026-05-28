from playwright.sync_api import sync_playwright
import time
import json
import re

URL_LOGIN     = "https://ws8.meridionalnet.com.ar/Account/Login?ReturnUrl=%2F"
URL_COTIZADOR = "https://ws2.meridionalseguros.com.ar/WSCARFrontend/index.aspx#html/cotizar.html"
USUARIO       = "RJBERNARDO"
PASSWORD      = "AIU2024a"

# Ubicación por defecto (ajustar si el cliente es de otra provincia)
PROVINCIA_DEFAULT = "BUENOS AIRES"


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


def run(session_id, sessions, dni, anio, marca, modelo_busqueda):
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

        # ── LOGIN EN WS8 ─────────────────────────────────────────────────────
        log('Iniciando sesión en portal Meridional...')
        page.goto(URL_LOGIN, wait_until='load', timeout=30000)
        time.sleep(2)

        # Debug: ver qué inputs hay en la página de login
        inputs_info = page.evaluate("""
            () => Array.from(document.querySelectorAll('input')).map(i => ({
                type: i.type, placeholder: i.placeholder, id: i.id, name: i.name
            }))
        """)
        log(f'Inputs en login: {inputs_info}')
        page.screenshot(path='C:/Users/User/Desktop/Cotizador Siluseg/meridional_login_debug.png')

        page.fill('input#Usuario', USUARIO)
        time.sleep(0.3)
        page.fill('input#password', PASSWORD)
        time.sleep(0.5)
        page.press('input#password', "Enter")
        try:
            page.wait_for_url(lambda url: 'Login' not in url, timeout=15000)
        except Exception:
            page.wait_for_load_state('load', timeout=15000)
        time.sleep(3)
        log('Sesión iniciada.')

        # ── NAVEGAR AL COTIZADOR ─────────────────────────────────────────────
        log('Navegando al cotizador de Autos...')
        time.sleep(2)

        # Click en Cotizadores en el sidebar
        page.click('span.app-sidebar__item-text:has-text("Cotizadores")')
        time.sleep(2)

        # Click en Autos
        page.click('span.app-sidebar__item-text:has-text("Autos")')
        page.wait_for_load_state('load', timeout=30000)
        time.sleep(3)

        # Esperar que el SPA renderice el formulario
        time.sleep(5)
        page.wait_for_selector('#coUnidadNegocio, select[id*="Negocio"], .panel-body', timeout=30000)
        time.sleep(2)
        log('Cotizador cargado.')

        # Debug: capturar URL actual
        log(f'URL cotizador: {page.url}')

        # ── UNIDAD DE NEGOCIO ────────────────────────────────────────────────
        log('Seleccionando unidad de negocio: PRODUCTORES MENSUAL...')
        # Clickear el elemento visual (la flecha del select2)
        page.click('.select2-container:not(.select2-container-disabled) .select2-choice')
        time.sleep(2)
        # Esperar que aparezca el dropdown
        page.wait_for_selector('.select2-drop:not(.select2-display-none)', timeout=10000)
        # Filtrar escribiendo MENSUAL
        page.type('.select2-input', 'MENSUAL')
        time.sleep(1)
        page.press('.select2-input', 'Enter')
        time.sleep(2)
        log('Unidad de negocio seleccionada.')

        # ── DATOS DE UBICACIÓN ───────────────────────────────────────────────
        log('Seleccionando provincia...')
        prov_sel = page.query_selector('select[id*="Provincia"], select[name*="Provincia"]')
        if prov_sel:
            options = prov_sel.query_selector_all('option')
            for opt in options:
                if PROVINCIA_DEFAULT.lower() in opt.inner_text().lower():
                    prov_sel.select_option(value=opt.get_attribute('value'))
                    break
        time.sleep(2)

        log('Seleccionando localidad...')
        loc_sel = page.query_selector('select[id*="Localidad"], select[name*="Localidad"]')
        if loc_sel:
            options = loc_sel.query_selector_all('option')
            for opt in options:
                if opt.get_attribute('value') and opt.get_attribute('value') != '':
                    loc_sel.select_option(value=opt.get_attribute('value'))
                    break
        time.sleep(1)

        # ── DATOS DEL VEHÍCULO (Ingreso Manual) ──────────────────────────────
        log('Usando ingreso manual de vehículo...')
        # Click en "Ingreso Manual" del bloque Datos del Vehículo
        ingreso_links = page.query_selector_all('text=Ingreso Manual')
        if ingreso_links:
            ingreso_links[0].click()   # primer link = vehículo
        time.sleep(2)

        # Año
        log(f'Seleccionando año {anio}...')
        anio_sel = page.query_selector(
            'select[id*="Anio"], select[name*="Anio"], '
            'select[id*="Year"], select[name*="Year"], '
            'select[id*="AnioVehiculo"], select[name*="AnioVehiculo"]'
        )
        if anio_sel:
            anio_sel.select_option(label=str(anio))
        time.sleep(2)

        # Marca
        log(f'Seleccionando marca {marca}...')
        marca_sel = page.query_selector(
            'select[id*="Marca"], select[name*="Marca"]'
        )
        if marca_sel:
            options = marca_sel.query_selector_all('option')
            for opt in options:
                if marca.lower() in opt.inner_text().lower():
                    marca_sel.select_option(value=opt.get_attribute('value'))
                    break
        time.sleep(2)

        # Modelo
        log(f'Buscando modelo "{modelo_busqueda}"...')
        modelo_sel = page.query_selector(
            'select[id*="Modelo"], select[name*="Modelo"]'
        )
        modelo_elegido = ''
        if modelo_sel:
            options = modelo_sel.query_selector_all('option')
            modelos_disponibles = [
                o for o in options
                if o.get_attribute('value') and o.get_attribute('value') != ''
            ]
            # Buscar coincidencia
            match = next(
                (o for o in modelos_disponibles
                 if modelo_busqueda.lower() in o.inner_text().lower()),
                modelos_disponibles[0] if modelos_disponibles else None
            )
            if match:
                modelo_elegido = match.inner_text().strip()
                modelo_sel.select_option(value=match.get_attribute('value'))
                log(f'Modelo: {modelo_elegido}')
        time.sleep(2)

        # ── DATOS DEL ASEGURADO ───────────────────────────────────────────────
        log(f'Buscando asegurado DNI {dni}...')
        # Campo de DNI — es el input de texto antes del botón Buscar
        dni_input = page.query_selector(
            'input[placeholder*="DNI"], input[placeholder*="Documento"], '
            'section:has-text("Asegurado") input[type="text"], '
            '.datos-asegurado input[type="text"]'
        )
        if dni_input:
            dni_input.fill(dni)
        else:
            # fallback: último input de texto visible antes del botón Buscar
            page.evaluate(f"""
                const btns = Array.from(document.querySelectorAll('button'));
                const buscarBtn = btns.find(b => b.innerText.includes('Buscar por DNI'));
                if (buscarBtn) {{
                    const inputs = document.querySelectorAll('input[type="text"]');
                    inputs[inputs.length - 1].value = '{dni}';
                    inputs[inputs.length - 1].dispatchEvent(new Event('input', {{bubbles: true}}));
                    inputs[inputs.length - 1].dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            """)
        time.sleep(1)

        # Debug: ver botones disponibles
        botones = page.evaluate("""
            () => Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t)
        """)
        log(f'Botones disponibles: {botones}')

        # Intentar click en botón de búsqueda por DNI
        buscar_btn = page.query_selector('button:has-text("Buscar"), button:has-text("DNI"), input[type="button"][value*="Buscar"]')
        if buscar_btn:
            buscar_btn.click()
        else:
            # Fallback: buscar por texto parcial
            page.click('button', timeout=5000)
        time.sleep(3)

        # ── DATOS DE LA OPERACIÓN ─────────────────────────────────────────────
        log('Configurando operación...')

        def select_first(selector):
            sel = page.query_selector(selector)
            if sel:
                opts = sel.query_selector_all('option')
                for o in opts:
                    if o.get_attribute('value') and o.get_attribute('value') not in ('', '...'):
                        sel.select_option(value=o.get_attribute('value'))
                        return True
            return False

        select_first('select[id*="Periodicidad"], select[name*="Periodicidad"]')
        time.sleep(0.5)
        select_first('select[id*="MedioPago"], select[name*="MedioPago"]')
        time.sleep(0.5)
        select_first('select[id*="Cuotas"], select[name*="Cuotas"]')
        time.sleep(0.5)

        # ── COTIZAR ───────────────────────────────────────────────────────────
        log('Cotizando...')
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        page.click('#btnCotizar, button:has-text("COTIZAR"), button:has-text("Cotizar")',
                   force=True)
        page.wait_for_load_state('load', timeout=30000)
        time.sleep(4)

        # ── EXTRAER COBERTURAS ────────────────────────────────────────────────
        log('Extrayendo coberturas y precios...')

        coberturas_json = page.evaluate("""
            () => {
                const resultado = [];

                // Buscar encabezados de sección (FULL CAR, TERCEROS, BASICAS)
                // y las filas de sus tablas
                const tables = document.querySelectorAll('table');

                for (const table of tables) {
                    const rows = table.querySelectorAll('tbody tr');
                    for (const row of rows) {
                        const cells = Array.from(row.querySelectorAll('td'));
                        if (cells.length < 4) continue;

                        // Encontrar columna Cobertura (la más larga con texto descriptivo)
                        // y columna Premio/Importe (números grandes)
                        let nombre = '';
                        let precio_texto = '';

                        // La cobertura suele estar en la celda 1 o 2
                        // El precio en la celda con el importe mayor
                        for (let i = 0; i < cells.length; i++) {
                            const txt = cells[i].innerText.trim();
                            // Detectar celda de cobertura: texto largo sin números solos
                            if (txt.length > 10 && !/^\\d+[,.]/.test(txt) && !nombre) {
                                nombre = txt;
                            }
                            // Detectar celda de precio: número con formato 000.000,00
                            // Priorizar la columna "Premio" o "Importe" (la más grande)
                            if (/^\\d{1,3}(\\.\\d{3})+,\\d{2}$/.test(txt)) {
                                precio_texto = txt; // toma el último match (Importe)
                            }
                        }

                        if (nombre && precio_texto &&
                            !nombre.toLowerCase().includes('no se encontraron')) {
                            resultado.push({ nombre, precio_texto });
                        }
                    }
                }

                return JSON.stringify(resultado);
            }
        """)

        coberturas_raw = json.loads(coberturas_json)

        coberturas = []
        for c in coberturas_raw:
            precio = _parse_precio(c['precio_texto'])
            if precio:
                coberturas.append({
                    'nombre':    c['nombre'],
                    'precio':    precio,
                    'deducible': '',
                })

        log(f'Se extrajeron {len(coberturas)} coberturas.')

        sessions[session_id]['resultados']['Meridional'] = {
            'aseguradora': 'Meridional',
            'ok':          True,
            'coberturas':  coberturas,
        }
        log('¡Cotización completada!')

    except Exception as e:
        import traceback
        log(f'Error: {e}')
        sessions[session_id]['resultados']['Meridional'] = {
            'aseguradora': 'Meridional',
            'ok':          False,
            'error':       str(e),
            'coberturas':  [],
        }
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if pw:
                pw.stop()
        except Exception:
            pass
