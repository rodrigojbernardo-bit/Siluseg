from flask import Flask, request, jsonify, send_file, render_template, Response
from playwright.sync_api import sync_playwright
import threading
import multiprocessing
import uuid
import time
import queue
import json
import re
from pathlib import Path
from report.generator import generar_pdf, parse_precio
from scrapers import meridional, fedpat


def _generar_pdf_proceso(resultados, info, output_path_str):
    """Corre generar_pdf en un proceso separado para evitar conflicto con asyncio."""
    from report.generator import generar_pdf
    from pathlib import Path
    generar_pdf(resultados, info, Path(output_path_str))

app = Flask(__name__)

DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

USUARIO = "pbernardo30334"
PASSWORD = "Termo2025"
URL_LOGIN = (
    "https://login.gruposancorseguros.com.ar/u/login/identifier"
    "?state=hKFo2SBaSnJKSDk5M0owM25WOTZybmxQN0g3N0xXb1BoQm0xeKFur3VuaXZlcnNhbC1sb2dpbq"
    "N0aWTZIE9XMUtXUHo1ZmZBS1kwWTlESURXNEZZNXcyYnBJWTlOo2NpZNkgU0dKam9aaUJOY2t1Qjg0"
    "RzQzbEFmdmlLYmxOYVVOZkw"
)

# {session_id: {status, queue, model_event, modelo_index, modelo_index_fedpat,
#               tipo_index_fedpat, pdf_filename, resultados}}
sessions = {}


def run_automation(session_id, dni, anio, marca, modelo_busqueda, localidad, sexo):
    s = sessions[session_id]
    q = s["queue"]
    model_event = s["model_event"]
    pw = None
    browser = None
    meridional_thread = None
    fedpat_thread = None

    s["resultados"] = {}

    def log(msg):
        q.put({"type": "log", "msg": msg})

    try:
        # ── Arrancar scrapers paralelos ──────────────────────────────────────
        meridional_thread = threading.Thread(
            target=meridional.run,
            args=(session_id, sessions, dni, anio, marca, modelo_busqueda),
            daemon=True,
        )
        meridional_thread.start()

        fedpat_thread = threading.Thread(
            target=fedpat.run,
            args=(session_id, sessions, dni, anio, marca, modelo_busqueda, localidad, sexo),
            daemon=True,
        )
        fedpat_thread.start()

        # ── Sancor ───────────────────────────────────────────────────────────
        log("Iniciando navegador Sancor...")
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        log("Abriendo portal Sancor...")
        page.goto(URL_LOGIN, wait_until="load", timeout=30000)
        time.sleep(2)

        log("Iniciando sesión...")
        page.fill('input[name="username"]', USUARIO)
        time.sleep(1)
        page.press('input[name="username"]', "Enter")
        time.sleep(2)
        page.wait_for_selector('input[type="password"]', timeout=10000)
        time.sleep(1)
        page.fill('input[type="password"]', PASSWORD)
        time.sleep(1)
        page.press('input[type="password"]', "Enter")
        page.wait_for_load_state("load", timeout=15000)
        time.sleep(3)
        log("Sesión iniciada.")

        log("Accediendo al cotizador...")
        with context.expect_page() as nueva_pagina_info:
            page.click("a#item_15")
        cotizador = nueva_pagina_info.value
        cotizador.wait_for_load_state("load", timeout=30000)
        time.sleep(3)

        cotizador.click("strong.text-brand-primary-darker")
        cotizador.wait_for_load_state("load", timeout=15000)
        time.sleep(3)

        log("Seleccionando organizador...")
        cotizador.click("#select2-sourceOrganizers-container")
        time.sleep(1)
        cotizador.wait_for_selector(".select2-results__option", timeout=5000)
        cotizador.click(".select2-results__option")
        time.sleep(1)

        log("Seleccionando productor...")
        cotizador.click("#select2-sourceProducers-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            'input[aria-controls="select2-sourceProducers-results"]', timeout=5000
        )
        cotizador.fill('input[aria-controls="select2-sourceProducers-results"]', "230334")
        time.sleep(2)
        cotizador.wait_for_selector(
            "#select2-sourceProducers-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=5000,
        )
        cotizador.click(
            "#select2-sourceProducers-results .select2-results__option:not(.select2-results__option--disabled)"
        )
        # El portal puede redirigir o recargar tras elegir el productor
        time.sleep(3)
        try:
            cotizador.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # Si la página se cerró, intentar recuperarla del contexto
        if cotizador.is_closed():
            paginas = context.pages
            cotizador = paginas[-1] if paginas else cotizador
            cotizador.wait_for_load_state("load", timeout=15000)
            time.sleep(2)

        log("Seleccionando ramo Automotores...")
        cotizador.wait_for_selector("#select2-sourceBranches-container", timeout=10000)
        cotizador.click("#select2-sourceBranches-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            "#select2-sourceBranches-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=5000,
        )
        for opcion in cotizador.query_selector_all(
            "#select2-sourceBranches-results .select2-results__option:not(.select2-results__option--disabled)"
        ):
            if "automotor" in opcion.inner_text().lower():
                opcion.click()
                break
        time.sleep(3)

        cotizador.click("#select2-sourceOperatories-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            "#select2-sourceOperatories-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=10000,
        )
        cotizador.click(
            "#select2-sourceOperatories-results .select2-results__option:not(.select2-results__option--disabled)"
        )
        time.sleep(1)

        cotizador.click("button.bg-primary.btn.btn-primary")
        cotizador.wait_for_load_state("load", timeout=15000)
        time.sleep(3)

        log(f"Buscando cliente DNI {dni}...")
        cotizador.click("#select2-sourceClients-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            'input[aria-controls="select2-sourceClients-results"]', timeout=5000
        )
        cotizador.fill('input[aria-controls="select2-sourceClients-results"]', dni)
        time.sleep(2)
        cotizador.wait_for_selector(
            "#select2-sourceClients-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=5000,
        )
        opciones_cliente = cotizador.query_selector_all(
            "#select2-sourceClients-results .select2-results__option:not(.select2-results__option--disabled)"
        )
        nombre_cliente = opciones_cliente[0].inner_text().strip()
        log(f"Cliente: {nombre_cliente}")
        opciones_cliente[0].click()
        time.sleep(1)

        cotizador.click("button.btn.btn-primary.margin-top.pull-right.margin-right-half")
        cotizador.wait_for_load_state("load", timeout=15000)
        time.sleep(3)

        cotizador.click('button[data-wizard="next"].btn.btn-next.btn-primary')
        cotizador.wait_for_load_state("load", timeout=15000)
        time.sleep(3)

        log(f"Seleccionando año {anio}...")
        time.sleep(3)
        cotizador.click("#select2-yearPat-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            "#select2-yearPat-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=15000,
        )
        for opcion in cotizador.query_selector_all(
            "#select2-yearPat-results .select2-results__option:not(.select2-results__option--disabled)"
        ):
            if opcion.inner_text().strip() == anio:
                opcion.click()
                break
        time.sleep(2)

        log(f"Seleccionando marca {marca}...")
        cotizador.click("#select2-brand-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            'input[aria-controls="select2-brand-results"]', timeout=5000
        )
        cotizador.fill('input[aria-controls="select2-brand-results"]', marca[:6])
        time.sleep(2)
        cotizador.wait_for_selector(
            "#select2-brand-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=5000,
        )
        for opcion in cotizador.query_selector_all(
            "#select2-brand-results .select2-results__option:not(.select2-results__option--disabled)"
        ):
            if marca.lower() in opcion.inner_text().lower():
                opcion.click()
                break
        time.sleep(3)

        log(f'Buscando modelos "{modelo_busqueda}"...')
        cotizador.click("#select2-model-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            'input[aria-controls="select2-model-results"]', timeout=5000
        )
        cotizador.fill('input[aria-controls="select2-model-results"]', modelo_busqueda)
        time.sleep(2)
        cotizador.wait_for_selector(
            "#select2-model-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=5000,
        )
        opciones_modelo = cotizador.query_selector_all(
            "#select2-model-results .select2-results__option:not(.select2-results__option--disabled)"
        )
        modelos = [op.inner_text().strip() for op in opciones_modelo]
        log(f"Se encontraron {len(modelos)} modelos. Esperando selección...")

        q.put({"type": "modelos", "modelos": modelos})
        s["status"] = "esperando_modelo"
        model_event.clear()
        log("Esperando selección de modelo Sancor (máx 5 min)...")
        resultado_evento = model_event.wait(timeout=300)
        log(f"[DEBUG] evento={resultado_evento} | modelo_index={s.get('modelo_index')} | status={s.get('status')}")

        if s.get("modelo_index") is None:
            raise Exception("Tiempo de espera agotado para selección de modelo Sancor.")

        modelo_index = s["modelo_index"]
        modelo_elegido = modelos[modelo_index]
        log(f"Modelo seleccionado: {modelo_elegido}")

        cotizador.keyboard.press("Escape")
        time.sleep(0.5)
        cotizador.click("#select2-model-container")
        time.sleep(1)
        cotizador.wait_for_selector(
            'input[aria-controls="select2-model-results"]', timeout=5000
        )
        cotizador.fill('input[aria-controls="select2-model-results"]', modelo_busqueda)
        time.sleep(2)
        cotizador.wait_for_selector(
            "#select2-model-results .select2-results__option:not(.select2-results__option--disabled)",
            timeout=5000,
        )
        opciones_new = cotizador.query_selector_all(
            "#select2-model-results .select2-results__option:not(.select2-results__option--disabled)"
        )
        opciones_new[modelo_index].click()
        time.sleep(3)

        log("Configurando opciones adicionales...")
        cotizador.evaluate(
            "document.querySelector('input#driver ~ span.switch-background').click()"
        )
        time.sleep(1)
        cotizador.evaluate("""
            const sel = document.getElementById('promotionalDiscount');
            if (sel && sel.options.length > 0) {
                sel.value = sel.options[0].value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
            }
        """)
        time.sleep(1)

        log("Cotizando Sancor...")
        cotizador.evaluate(
            'document.querySelector(\'button[data-wizard="finish"]\').scrollIntoView()'
        )
        time.sleep(1)
        cotizador.click('button[data-wizard="finish"]', force=True)
        cotizador.wait_for_load_state("load", timeout=30000)
        time.sleep(5)

        log("Obteniendo coberturas Sancor...")
        # Esperar que carguen las tarjetas de cobertura (más robusto que buscar un nombre específico)
        cotizador.wait_for_selector('div[data-name="nf-check"]', timeout=60000)
        cotizador.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(3)

        coberturas_json = cotizador.evaluate("""
            () => {
                const resultado = [];
                const seen = new Set();
                const checks = document.querySelectorAll('div[data-name="nf-check"]');
                for (const check of checks) {
                    const card = check.closest('div.nf-card')
                               || check.closest('div.margin-bottom-half')
                               || check.parentElement.parentElement.parentElement;
                    if (!card || seen.has(card)) continue;
                    seen.add(card);
                    let nombre = '';
                    for (const el of card.querySelectorAll('h1,h2,h3,h4,strong')) {
                        const t = el.innerText.trim();
                        if (t && t.length > 1 && t.length < 80) { nombre = t; break; }
                    }
                    let precio_texto = '';
                    const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
                    let node;
                    while ((node = walker.nextNode())) {
                        if (/\\$[\\s\\d.,]+x\\s*mes/i.test(node.nodeValue)) {
                            precio_texto = node.nodeValue.trim();
                            break;
                        }
                    }
                    if (!precio_texto) {
                        for (const el of card.querySelectorAll('*')) {
                            if (el.children.length === 0) {
                                const t = (el.innerText||'').trim();
                                if (/\\$.*x\\s*mes/i.test(t)) { precio_texto = t; break; }
                            }
                        }
                    }
                    let deducible_texto = '';
                    for (const el of card.querySelectorAll('*')) {
                        const t = (el.innerText||'').trim();
                        if (t.toLowerCase().includes('deducible') && t.length < 120) {
                            deducible_texto = t; break;
                        }
                    }
                    if (nombre && precio_texto) {
                        resultado.push({ nombre, precio_texto, deducible_texto });
                    }
                }
                return JSON.stringify(resultado);
            }
        """)
        coberturas_raw = json.loads(coberturas_json)
        log(f"Se extrajeron {len(coberturas_raw)} coberturas Sancor.")

        info_json = cotizador.evaluate("""
            () => {
                const body = document.body.innerText;
                const capitalMatch = body.match(/Capital asegurable[:\\s]+([\\$\\d.,]+)/i);
                const cotizMatch   = body.match(/N[°º]\\s*de cotizaci[oó]n[:\\s]+(\\S+)/i);
                const clienteMatch = body.match(/Cliente[:\\s]+([A-ZÁÉÍÓÚ ]+?)(?:\\s*\\(|\\s*\\n)/i);
                return JSON.stringify({
                    capital:    capitalMatch ? capitalMatch[1].trim() : '',
                    cotizacion: cotizMatch   ? cotizMatch[1].trim()   : '',
                    cliente:    clienteMatch ? clienteMatch[1].trim() : '',
                });
            }
        """)
        info_pagina = json.loads(info_json)

        coberturas = [
            {
                "nombre":    c["nombre"],
                "precio":    parse_precio(c["precio_texto"]),
                "deducible": c["deducible_texto"],
            }
            for c in coberturas_raw
        ]

        s["resultados"]["Sancor"] = {
            "aseguradora": "Sancor",
            "ok": True,
            "coberturas": coberturas,
        }
        log("Sancor completado.")

        # ── Esperar scrapers paralelos ────────────────────────────────────────
        if meridional_thread and meridional_thread.is_alive():
            log("Esperando cotización de Meridional...")
            meridional_thread.join(timeout=180)
        if meridional_thread and meridional_thread.is_alive():
            log("ADVERTENCIA: Meridional no terminó a tiempo, se omite del PDF.")

        if fedpat_thread and fedpat_thread.is_alive():
            log("Esperando cotización de Federación Patronal...")
            fedpat_thread.join(timeout=300)
        if fedpat_thread and fedpat_thread.is_alive():
            log("ADVERTENCIA: Federación Patronal no terminó a tiempo, se omite del PDF.")

        # Cerrar browser Sancor antes del PDF para evitar conflicto asyncio/sync playwright
        try:
            if browser:
                browser.close()
                browser = None
            if pw:
                pw.stop()
                pw = None
        except Exception:
            pass

        # ── Generar PDF ───────────────────────────────────────────────────────
        info = {
            "vehiculo": f"{marca} {modelo_elegido}",
            "anio":     anio,
            "capital":  info_pagina.get("capital", ""),
            "cliente":  info_pagina.get("cliente", ""),
            "dni":      dni,
        }

        # Mostrar estado de cada aseguradora para facilitar el debug
        for aseg, datos in s["resultados"].items():
            ok  = datos.get("ok", False)
            err = datos.get("error", "")
            ncob = len(datos.get("coberturas", []))
            if ok:
                log(f"  ✓ {aseg}: {ncob} coberturas")
            else:
                log(f"  ✗ {aseg}: ERROR - {err}")

        log("Generando PDF comparativo...")
        filename = f"Cotizacion_Siluseg_{uuid.uuid4().hex[:8].upper()}.pdf"
        destino = DOWNLOADS_DIR / filename

        pdf_error = []
        def _run_pdf():
            try:
                generar_pdf(s["resultados"], info, destino)
            except Exception as e:
                import traceback
                pdf_error.append(traceback.format_exc())
        t = threading.Thread(target=_run_pdf)
        t.start()
        t.join(timeout=90)
        if t.is_alive():
            raise Exception("Error PDF: tiempo de espera agotado (90s)")
        if pdf_error:
            raise Exception(f"Error PDF: {pdf_error[0]}")

        s["pdf_filename"] = filename
        s["status"] = "completado"
        log("¡Listo! PDF comparativo generado.")
        q.put({"type": "done", "pdf_filename": filename})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log(f"ERROR: {tb}")
        # Guardar en archivo para debug
        with open("C:/Users/User/Desktop/Cotizador Siluseg/error_log.txt", "a") as f:
            f.write(f"\n{'='*50}\n{tb}\n")
        q.put({"type": "error", "msg": str(e)})
        s["status"] = "error"
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


# ── Rutas Flask ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cotizar", methods=["POST"])
def iniciar_cotizacion():
    data = request.json or {}
    dni      = data.get("dni", "").strip()
    anio     = data.get("anio", "").strip()
    marca    = data.get("marca", "").strip().upper()
    modelo   = data.get("modelo", "").strip().upper()
    localidad = data.get("localidad", "").strip().upper()
    sexo     = data.get("sexo", "M").strip().upper()

    if not all([dni, anio, marca, modelo, localidad]):
        return jsonify({"error": "Todos los campos son requeridos"}), 400

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "status":               "iniciando",
        "queue":                queue.Queue(),
        "model_event":          threading.Event(),
        "model_event_fedpat":   threading.Event(),
        "modelo_index":         None,
        "modelo_index_fedpat":  None,
        "tipo_index_fedpat":    None,
        "pdf_filename":         None,
        "resultados":           {},
    }

    threading.Thread(
        target=run_automation,
        args=(session_id, dni, anio, marca, modelo, localidad, sexo),
        daemon=True,
    ).start()

    return jsonify({"session_id": session_id})


@app.route("/api/eventos/<session_id>")
def eventos(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Sesión no encontrada"}), 404

    def generate():
        s = sessions[session_id]
        q = s["queue"]
        while True:
            try:
                msg = q.get(timeout=20)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg["type"] in ("done", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/seleccionar-modelo", methods=["POST"])
def seleccionar_modelo():
    data = request.json or {}
    session_id  = data.get("session_id")
    modelo_index = data.get("modelo_index")

    if session_id not in sessions:
        return jsonify({"error": "Sesión no encontrada"}), 404

    s = sessions[session_id]
    s["modelo_index"] = int(modelo_index)
    s["status"] = "procesando"
    s["model_event"].set()
    return jsonify({"ok": True})


@app.route("/api/seleccionar-modelo-fedpat", methods=["POST"])
def seleccionar_modelo_fedpat():
    data = request.json or {}
    session_id   = data.get("session_id")
    modelo_index = data.get("modelo_index")

    if session_id not in sessions:
        return jsonify({"error": "Sesión no encontrada"}), 404

    s = sessions[session_id]
    s["modelo_index_fedpat"] = int(modelo_index)
    s["model_event_fedpat"].set()
    return jsonify({"ok": True})


@app.route("/api/seleccionar-tipo-fedpat", methods=["POST"])
def seleccionar_tipo_fedpat():
    data = request.json or {}
    session_id = data.get("session_id")
    tipo_index = data.get("tipo_index")

    if session_id not in sessions:
        return jsonify({"error": "Sesión no encontrada"}), 404

    s = sessions[session_id]
    s["tipo_index_fedpat"] = int(tipo_index)
    s["model_event_fedpat"].set()
    return jsonify({"ok": True})


@app.route("/api/pdf/<path:filename>")
def descargar_pdf(filename):
    pdf_path = DOWNLOADS_DIR / filename
    if not pdf_path.exists():
        return jsonify({"error": "PDF no encontrado"}), 404
    return send_file(str(pdf_path), as_attachment=True, download_name=filename)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    import webbrowser
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    print("\n  Cotizador Siluseg - Sancor - Meridional - Federacion Patronal")
    print("  http://127.0.0.1:5000\n")
    app.run(debug=False, host="127.0.0.1", port=5001, threaded=True)
