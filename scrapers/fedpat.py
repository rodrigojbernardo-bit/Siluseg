# scrapers/fedpat.py - Federacion Patronal para app
# Logica identica a fedpat_funkaba.py

from playwright.sync_api import sync_playwright
from pathlib import Path
import time
import re

USUARIO   = "30658"
PASSWORD  = "Termo2025"
URL_LOGIN = "https://online.fedpat.com.ar/self/homeWin32.do"
BASE_DIR  = Path("C:/Users/User/Desktop/Cotizador Siluseg")


def _parse_precio(texto):
    if not texto or texto == 'NO ENCONTRADO':
        return None
    limpio = re.sub(r'[^\d,]', '', texto).replace(',', '.')
    try:
        v = float(limpio)
        return v if v > 0 else None
    except Exception:
        return None


def run(session_id, sessions, dni, anio, marca, modelo_busqueda, localidad, sexo):
    s = sessions[session_id]
    q = s['queue']
    model_event = s['model_event_fedpat']

    def log(msg):
        q.put({'type': 'log', 'msg': f'[FedPat] {msg}'})

    pw = None
    browser = None

    try:
        log('Iniciando navegador...')
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        log('Abriendo portal...')
        page.goto(URL_LOGIN, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        log('Ingresando credenciales...')
        page.fill('input#usuario', USUARIO)
        time.sleep(1)
        page.fill('input#password', PASSWORD)
        time.sleep(1)
        page.click('input[name="Aceptar"]')
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        log(f'URL tras login: {page.url}')

        log('Abriendo Favoritos...')
        page.click('a.MsM_dropdownToggle')
        time.sleep(1)

        log('Clickeando Nueva Cotizacion Automotor...')
        page.click('a[href="/self/newCotizacion.do"]')
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)

        log(f'Ingresando DNI {dni}...')
        page.fill('input#documentoAsegurado', dni)
        time.sleep(1)
        page.press('input#documentoAsegurado', "Tab")
        time.sleep(2)

        log(f'Seleccionando sexo {sexo}...')
        if sexo.upper() == "M":
            page.click('input#sexoM')
        else:
            page.click('input#sexoF')
        time.sleep(1)

        log(f'Ingresando localidad {localidad}...')
        page.fill('input#nombreLocalidad', localidad)
        time.sleep(2)

        log('Abriendo menu Riesgo...')
        page.click('span.nombreParaItemNavigato:has-text("Riesgo")')
        time.sleep(2)

        log(f'Ingresando marca {marca}...')
        page.fill('input#descripcionMarca', marca[:5])
        time.sleep(2)

        log(f'Ingresando año {anio}...')
        page.fill('input#anio', anio)
        time.sleep(1)
        page.press('input#anio', "Tab")
        time.sleep(2)

        log(f'Buscando modelo {modelo_busqueda}...')
        page.fill('input#descripcionModelo', modelo_busqueda)
        time.sleep(1)
        page.type('input#descripcionModelo', " ")
        time.sleep(2)

        opciones_raw = page.evaluate("""
            () => {
                const todos = document.querySelectorAll('*');
                for (let el of todos) {
                    if (el.offsetParent !== null && el.tagName === 'UL' && el.children.length > 1) {
                        const input = document.getElementById('descripcionModelo');
                        const inputRect = input.getBoundingClientRect();
                        const rect = el.getBoundingClientRect();
                        if (Math.abs(rect.left - inputRect.left) < 200 && rect.top > inputRect.top) {
                            return Array.from(el.querySelectorAll('li')).map(li => ({
                                id: li.id,
                                texto: li.innerText.trim()
                            }));
                        }
                    }
                }
                return [];
            }
        """)

        if not opciones_raw:
            raise Exception('No se encontraron modelos')

        # Enviar modelos a la app
        q.put({'type': 'modelos_fedpat', 'modelos': opciones_raw})
        s['status'] = 'esperando_modelo_fedpat'
        model_event.clear()
        model_event.wait(timeout=120)

        modelo_index = s.get('modelo_index_fedpat', 0)
        modelo_elegido = opciones_raw[modelo_index]
        log(f'Seleccionando: {modelo_elegido["texto"]}...')
        page.click(f'li[id="{modelo_elegido["id"]}"]')
        time.sleep(2)

        log('Seleccionando tipo de vehiculo...')
        page.wait_for_selector('select#tipo', timeout=5000)
        opciones_tipo = page.evaluate("""
            () => Array.from(document.querySelectorAll('select#tipo option'))
                .filter(o => o.value !== '0')
                .map(o => ({ value: o.value, texto: o.text.trim() }))
        """)

        # Enviar tipos a la app
        q.put({'type': 'tipos_fedpat', 'tipos': opciones_tipo})
        s['status'] = 'esperando_tipo_fedpat'
        model_event.clear()
        model_event.wait(timeout=120)

        tipo_index = s.get('tipo_index_fedpat', 0)
        tipo_elegido = opciones_tipo[tipo_index]
        page.select_option('select#tipo', value=tipo_elegido['value'])
        time.sleep(2)
        log(f'Tipo seleccionado: {tipo_elegido["texto"]}')

        log('Abriendo Plan de cobertura...')
        page.click('span.nombreParaItemNavigato:has-text("Plan de cobertura")')
        time.sleep(2)

        log('Seleccionando plan CF...')
        page.wait_for_selector('select#planCobertura', timeout=5000)
        page.select_option('select#planCobertura', value='CF')
        time.sleep(2)

        log('Marcando Interasegurados...')
        page.click('label[for="interasegurado"]')
        time.sleep(1)

        log('Abriendo Adicionales...')
        page.click('span.nombreParaItemNavigato:has-text("Adicionales")')
        time.sleep(2)

        log('Marcando ASEGURA2...')
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        page.click('input#asegura2')
        time.sleep(1)

        log('Clickeando Agregar Producto...')
        page.click('input#agregarAsegura2')
        time.sleep(2)

        log('Seleccionando AP Familiares Transportados...')
        page.wait_for_selector('select#codigoProductoAsegura2', timeout=5000)
        page.select_option('select#codigoProductoAsegura2', value='350001')
        time.sleep(1)

        log('Clickeando Aceptar...')
        page.click('input[name="action"][value="Aceptar"]')
        time.sleep(4)

        log('Abriendo Facturacion...')
        page.click('span.nombreParaItemNavigato:has-text("Facturación")')
        time.sleep(2)

        log('Seleccionando Refacturacion Mensual...')
        page.wait_for_selector('select#cantidadPeriodos', timeout=5000)
        page.select_option('select#cantidadPeriodos', value='12')
        time.sleep(1)

        log('Seleccionando Debito/Tarjeta...')
        page.select_option('select#formaPago', value='2')
        time.sleep(1)

        log('Cotizando CF...')
        page.click('input#cotizar_')
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        cuota_cf = page.evaluate("""
            () => {
                const titulos = document.querySelectorAll('div.title__filter.marginpixeles-top-10px');
                for (let titulo of titulos) {
                    if (titulo.innerText.trim() === 'Cuota') {
                        const valor = titulo.nextElementSibling;
                        return valor ? valor.innerText.trim() : 'NO ENCONTRADO';
                    }
                }
                return 'NO ENCONTRADO';
            }
        """)
        log(f'CF: ${cuota_cf}')

        # Extraer suma asegurada en la página de resultados CF (antes de cambiar plan)
        capital_text = page.evaluate(r"""
            () => {
                const txt = document.body.innerText;
                // Patrones con saltos de línea permitidos entre label y valor
                const pats = [
                    /(?:suma|capital|valor)\s+asegur(?:ada|able|ado)[\s\S]{0,80}\$([\d.,]+)/i,
                    /valor\s+(?:del\s+)?veh[ií]culo[\s\S]{0,80}\$([\d.,]+)/i,
                    /valor\s+a\s+nuevo[\s\S]{0,80}\$([\d.,]+)/i,
                ];
                for (const p of pats) {
                    const m = txt.match(p);
                    if (m && m[1] && m[1].replace(/[.,]/g,'').length >= 4)
                        return '$' + m[1].trim();
                }
                // Buscar celdas/spans etiquetados "Suma asegurada" y tomar el siguiente valor
                for (const el of document.querySelectorAll('td,th,div,span,label,p')) {
                    const t = (el.innerText || '').trim().toLowerCase();
                    if (t === 'suma asegurada' || t === 'valor asegurado' || t === 'capital asegurado') {
                        const sib = el.nextElementSibling;
                        if (sib) {
                            const m = (sib.innerText || '').match(/([\d.,]+)/);
                            if (m) return '$' + m[1];
                        }
                    }
                }
                return '';
            }
        """)
        log(f'Capital FedPat: {capital_text or "(no encontrado)"}')

        # TD3 6%
        log('Cotizando TD3 6%...')
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        page.select_option('select#planCobertura', value='TD3')
        time.sleep(2)
        page.wait_for_selector('select#franquicia', timeout=5000)
        page.select_option('select#franquicia', value='106')
        time.sleep(1)
        page.click('label[for="tallerExclusivo"]')
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        page.select_option('select#cantidadPeriodos', value='12')
        time.sleep(1)
        page.select_option('select#formaPago', value='2')
        time.sleep(1)
        page.click('input#cotizar_')
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        cuota_td3_6 = page.evaluate("""
            () => {
                const titulos = document.querySelectorAll('div.title__filter.marginpixeles-top-10px');
                for (let titulo of titulos) {
                    if (titulo.innerText.trim() === 'Cuota') {
                        const valor = titulo.nextElementSibling;
                        return valor ? valor.innerText.trim() : 'NO ENCONTRADO';
                    }
                }
                return 'NO ENCONTRADO';
            }
        """)
        log(f'TD3 6%: ${cuota_td3_6}')

        # TD3 4%
        log('Cotizando TD3 4%...')
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        page.select_option('select#planCobertura', value='TD3')
        time.sleep(2)
        page.wait_for_selector('select#franquicia', timeout=5000)
        page.select_option('select#franquicia', value='104')
        time.sleep(1)
        page.click('label[for="tallerExclusivo"]')
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        page.select_option('select#cantidadPeriodos', value='12')
        time.sleep(1)
        page.select_option('select#formaPago', value='2')
        time.sleep(1)
        page.click('input#cotizar_')
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        cuota_td3_4 = page.evaluate("""
            () => {
                const titulos = document.querySelectorAll('div.title__filter.marginpixeles-top-10px');
                for (let titulo of titulos) {
                    if (titulo.innerText.trim() === 'Cuota') {
                        const valor = titulo.nextElementSibling;
                        return valor ? valor.innerText.trim() : 'NO ENCONTRADO';
                    }
                }
                return 'NO ENCONTRADO';
            }
        """)
        log(f'TD3 4%: ${cuota_td3_4}')

        # TD3 2%
        log('Cotizando TD3 2%...')
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        page.select_option('select#planCobertura', value='TD3')
        time.sleep(2)
        page.wait_for_selector('select#franquicia', timeout=5000)
        page.select_option('select#franquicia', value='102')
        time.sleep(1)
        page.click('label[for="tallerExclusivo"]')
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        page.select_option('select#cantidadPeriodos', value='12')
        time.sleep(1)
        page.select_option('select#formaPago', value='2')
        time.sleep(1)
        page.click('input#cotizar_')
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        cuota_td3_2 = page.evaluate("""
            () => {
                const titulos = document.querySelectorAll('div.title__filter.marginpixeles-top-10px');
                for (let titulo of titulos) {
                    if (titulo.innerText.trim() === 'Cuota') {
                        const valor = titulo.nextElementSibling;
                        return valor ? valor.innerText.trim() : 'NO ENCONTRADO';
                    }
                }
                return 'NO ENCONTRADO';
            }
        """)
        log(f'TD3 2%: ${cuota_td3_2}')

        log('Guardando cotizacion...')
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        page.click('input#buttonGuardar')
        page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)
        log('Cotizacion guardada.')

        sessions[session_id]['resultados']['Federación'] = {
            'aseguradora': 'Federacion Patronal',
            'ok': True,
            'coberturas': [
                {'nombre': 'CF - Full',           'precio': _parse_precio(cuota_cf),    'deducible': ''},
                {'nombre': 'TD3 - 6% Franquicia', 'precio': _parse_precio(cuota_td3_6), 'deducible': 'Franquicia 6%'},
                {'nombre': 'TD3 - 4% Franquicia', 'precio': _parse_precio(cuota_td3_4), 'deducible': 'Franquicia 4%'},
                {'nombre': 'TD3 - 2% Franquicia', 'precio': _parse_precio(cuota_td3_2), 'deducible': 'Franquicia 2%'},
            ],
            'capital': capital_text or '',
        }
        log('Cotizacion completada!')

    except Exception as e:
        import traceback
        log(f'Error: {traceback.format_exc()}')
        sessions[session_id]['resultados']['Federación'] = {
            'aseguradora': 'Federacion Patronal',
            'ok': False,
            'error': str(e),
            'coberturas': [],
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
