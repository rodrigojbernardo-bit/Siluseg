# scrapers/fedpat.py - Federacion Patronal para app
# Logica identica a fedpat_funkaba.py

from playwright.sync_api import sync_playwright
from pathlib import Path
import time
import re
import json

from scrapers.common import (
    HEADLESS, mensaje_error, abrir_fedpat, esperar_verificacion,
    marcar_check_cloudflare, encontrar_pagina_con, encontrar_ui_con,
    guardar_diagnostico,
)

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
    cerrar_nav = None

    try:
        log('Iniciando navegador...')
        pw = sync_playwright().start()
        page, cerrar_nav, chrome_real = abrir_fedpat(pw, log)
        if chrome_real:
            log('Conectado a tu Chrome (pasa la verificación de seguridad).')
        else:
            log('No encontré un Chrome abierto; usando navegador propio '
                '(puede frenarse en la verificación de seguridad).')

        log('Abriendo portal...')
        # El portal tiene una "verificación de seguridad" (Cloudflare) que
        # puede aparecer en cualquier momento. Si sale, esperamos a que la
        # resuelvas a mano en la ventana de Chrome y recién ahí seguimos.
        page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=45000)
        esperar_verificacion(page, log)
        # Tras pasar Cloudflare, la página redirige y se reacomoda: darle
        # unos segundos antes de tocar nada, o el login sale en falso.
        log('Dejando que la página termine de cargar...')
        time.sleep(5)

        # Puede que ya estés logueado (tu Chrome mantiene la sesión). Solo
        # iniciamos sesión si aparece el formulario de login.
        ya_logueado = True
        try:
            page.wait_for_selector('input#usuario', timeout=12000)
            ya_logueado = False
        except Exception:
            ya_logueado = True

        if not ya_logueado:
            page.wait_for_selector('input#usuario', timeout=12000)

            log('Ingresando credenciales...')
            page.fill('input#usuario', USUARIO)
            time.sleep(1)
            page.fill('input#password', PASSWORD)

            # Secuencia simple: esperar 6s, clic en el check de Cloudflare,
            # esperar 6s a que se verifique, y recién ahí Ingresar.
            log('Espero 6s a que aparezca la verificación...')
            time.sleep(6)
            marcar_check_cloudflare(page, log)
            log('Espero 6s a que se verifique...')
            time.sleep(6)

            log('Clic en Ingresar...')
            page.click('input[name="Aceptar"]', timeout=10000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            time.sleep(3)
            esperar_verificacion(page, log)
        else:
            log('Ya había una sesión abierta, no hace falta loguear.')

        log(f'URL actual: {page.url}')

        # Cerrar un posible aviso de sesión previa.
        for sel in ('input[value="Continuar"]', 'a:has-text("Continuar")',
                    'input[value="Aceptar"]', 'button:has-text("Aceptar")'):
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log('Cerrando aviso de sesión previa...')
                    el.click()
                    time.sleep(2)
                    break
            except Exception:
                pass

        # Ir a Nueva Cotización POR EL MENÚ. El acceso directo por URL no
        # sirve: el portal lo rebota a la página de inicio (homeWin32.do).
        log('Abriendo Nueva Cotización Automotor (por el menú)...')
        if 'homeWin32' not in page.url:
            page.goto(URL_LOGIN, wait_until='domcontentloaded', timeout=30000)
            esperar_verificacion(page, log)
            time.sleep(3)

        # El menú puede estar en otra ventana o dentro de un marco.
        menu = encontrar_ui_con(page.context, 'a.MsM_dropdownToggle', log, timeout=20)
        if menu is None:
            guardar_diagnostico(page, 'fedpat_sinmenu', log)
            raise Exception('No encontré el menú principal de Federación '
                            '(guardé diagnóstico en el Escritorio).')
        menu.click('a.MsM_dropdownToggle')
        time.sleep(1.5)
        menu.click('a[href="/self/newCotizacion.do"]')
        time.sleep(3)
        esperar_verificacion(page, log)

        # Buscar el formulario de cotización en cualquier ventana o marco.
        form_ui = encontrar_ui_con(page.context, 'input#documentoAsegurado', log, timeout=30)
        if form_ui is None:
            guardar_diagnostico(page, 'fedpat_nuevacotizacion', log)
            raise Exception('No apareció el formulario de Nueva Cotización '
                            '(guardé diagnóstico en el Escritorio).')
        # Page y Frame comparten fill/click/evaluate/etc.: seguimos sobre
        # donde realmente está el formulario.
        page = form_ui
        log('Formulario de cotización encontrado.')
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
        time.sleep(5)

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

        cuota_cf_raw = page.evaluate("""
            () => {
                // Recolectar TODOS los pares label→valor de 'Cuota'
                const titulos = document.querySelectorAll('div.title__filter.marginpixeles-top-10px');
                const pares = [];
                for (const t of titulos) {
                    const sib = t.nextElementSibling;
                    pares.push({ label: t.innerText.trim(), valor: sib ? sib.innerText.trim() : '' });
                }
                // Separar las cuotas numéricas
                const cuotas = pares
                    .filter(p => p.label === 'Cuota' && /[\\d.,]/.test(p.valor))
                    .map(p => {
                        const clean = p.valor.replace(/[^\\d,]/g, '').replace(',', '.');
                        return { texto: p.valor, num: parseFloat(clean) || 0 };
                    });
                if (cuotas.length === 0) return JSON.stringify({ cuotas: pares, resultado: 'NO ENCONTRADO' });
                // Si hay una sola, devolverla directo
                if (cuotas.length === 1) return JSON.stringify({ cuotas: pares, resultado: cuotas[0].texto });
                // Si hay varias, sumar (CF base + addons)
                const total = cuotas.reduce((s, c) => s + c.num, 0);
                const formatted = total.toFixed(2).replace('.', ',');
                return JSON.stringify({ cuotas: pares, resultado: formatted });
            }
        """)
        cf_data = json.loads(cuota_cf_raw)
        log(f'[FedPat CF] Elementos en página: {cf_data["cuotas"]}')
        cuota_cf = cf_data['resultado']
        log(f'CF resultado: {cuota_cf}')

        # Extraer suma asegurada — buscando en TODOS los marcos de la página,
        # porque el portal viejo reparte el contenido entre varios frames.
        _patron_capital = r"""
            () => {
                const txt = (document.body && document.body.innerText) || '';
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
                // El valor puede estar dentro de un campo de formulario
                // (input), que no aparece en el texto de la página.
                for (const inp of document.querySelectorAll('input')) {
                    const idn = ((inp.id || '') + ' ' + (inp.name || '')).toLowerCase();
                    if (/suma|capital|valorveh|valoraseg/.test(idn)) {
                        const v = (inp.value || '').replace(/[^\d.,]/g, '');
                        if (v.replace(/[.,]/g, '').length >= 4) return '$' + v;
                    }
                }
                return '';
            }
        """

        def _extraer_capital():
            # Página/Frame actual + todos los demás marcos de la ventana.
            destinos = [page]
            try:
                pg = getattr(page, 'page', None) or page
                destinos += [f for f in pg.frames if f is not page]
            except Exception:
                pass
            for d in destinos:
                try:
                    val = d.evaluate(_patron_capital)
                    if val:
                        return val
                except Exception:
                    continue
            return ''

        capital_text = _extraer_capital()
        if not capital_text:
            guardar_diagnostico(page, 'fedpat_sumaasegurada', log)
        log(f'Capital FedPat: {capital_text or "(no encontrado, guardé diagnóstico)"}')

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

        # Fallback capital desde la última página (todos los marcos) si no
        # se encontró en CF.
        if not capital_text:
            capital_text = _extraer_capital()
            if capital_text:
                log(f'Capital FedPat (fallback TD3 2%): {capital_text}')

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
        # Diagnóstico completo al Escritorio para ver dónde se trabó.
        try:
            guardar_diagnostico(page, 'fedpat_error', log)
        except Exception:
            pass
        sessions[session_id]['resultados']['Federación'] = {
            'aseguradora': 'Federacion Patronal',
            'ok': False,
            'error': mensaje_error(e),
            'coberturas': [],
        }
    finally:
        try:
            if cerrar_nav: cerrar_nav()
        except Exception:
            pass
        try:
            if pw: pw.stop()
        except Exception:
            pass
