import re
import base64
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent
LOGO_PATH    = Path(__file__).parent.parent / "Siluseg - Logo TARJETA OK.jpg"

ASEGURADORAS = ['Sancor', 'Federación', 'Meridional']
COLORES = {
    'Sancor':     {'header': '#c0392b', 'light': '#fff5f5', 'text': '#922b21'},
    'Federación': {'header': '#1a7a3c', 'light': '#f0fff4', 'text': '#145a2c'},
    'Meridional': {'header': '#1a4b8c', 'light': '#ebf8ff', 'text': '#154360'},
}


def parse_precio(texto):
    """'$ 321.543,37 x mes' → 321543.37"""
    if not texto:
        return None
    limpio = texto.replace('\xa0', '').replace(' ', '')
    match = re.search(r'\$([\d.]+),(\d+)', limpio)
    if match:
        entero = match.group(1).replace('.', '')
        return float(f"{entero}.{match.group(2)}")
    return None


def fmt(valor):
    """321543.37 → '$321.543'"""
    if valor is None:
        return None
    return f"${int(round(valor)):,}".replace(',', '.')


def _logo_b64():
    if LOGO_PATH.exists():
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return None


def generar_pdf(resultados_por_aseguradora, info, output_path):
    # Solo aseguradoras con datos reales
    aseguradoras_activas = [
        a for a in ASEGURADORAS
        if resultados_por_aseguradora.get(a, {}).get('ok') and
           resultados_por_aseguradora[a].get('coberturas')
    ]

    # Unificar coberturas en orden de aparición
    coberturas_vistas = []
    seen = set()
    for a in aseguradoras_activas:
        for c in resultados_por_aseguradora[a]['coberturas']:
            if c['nombre'] not in seen:
                coberturas_vistas.append(c['nombre'])
                seen.add(c['nombre'])

    # Filas de comparación
    rows = []
    for nombre in coberturas_vistas:
        precios_raw = {}
        deducible = ''
        for a in aseguradoras_activas:
            for c in resultados_por_aseguradora[a]['coberturas']:
                if c['nombre'] == nombre:
                    precios_raw[a] = c['precio']
                    if not deducible and c.get('deducible'):
                        deducible = c['deducible']

        precios_validos = {a: v for a, v in precios_raw.items() if v}
        mejor = min(precios_validos, key=precios_validos.get) if precios_validos else None

        rows.append({
            'cobertura': nombre,
            'deducible': deducible,
            'precios':   {a: fmt(precios_raw.get(a)) for a in aseguradoras_activas},
            'mejor':     mejor,
        })

    # Ganador general
    wins = {a: 0 for a in aseguradoras_activas}
    for row in rows:
        if row['mejor']:
            wins[row['mejor']] += 1
    mejor_general = max(wins, key=wins.get) if wins else None
    mejor_wins    = wins.get(mejor_general, 0) if mejor_general else 0

    # Renderizar template
    env      = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template('template.html')
    html = template.render(
        logo_b64      = _logo_b64(),
        fecha         = datetime.now().strftime('%d/%m/%Y'),
        aseguradoras  = aseguradoras_activas,
        colores       = COLORES,
        rows          = rows,
        vehiculo      = info.get('vehiculo', ''),
        anio          = info.get('anio', ''),
        capital       = info.get('capital', ''),
        cliente       = info.get('cliente', ''),
        dni           = info.get('dni', ''),
        mejor_general = mejor_general,
        mejor_wins    = mejor_wins,
        total         = len(rows),
    )

    # Intentar xhtml2pdf (puro Python, sin browser, sin asyncio)
    try:
        from xhtml2pdf import pisa
        with open(str(output_path), 'wb') as f:
            result = pisa.CreatePDF(html_string=html, dest=f)
        if not result.err:
            return
    except Exception:
        pass

    # Intentar weasyprint (requiere GTK instalado en Windows)
    try:
        from weasyprint import HTML as WeasyHTML
        WeasyHTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(output_path))
        return
    except Exception:
        pass

    raise RuntimeError(
        "No se pudo generar el PDF. Instalá xhtml2pdf:\n"
        "    pip install xhtml2pdf\n"
        "O weasyprint (requiere GTK en Windows):\n"
        "    pip install weasyprint"
    )
