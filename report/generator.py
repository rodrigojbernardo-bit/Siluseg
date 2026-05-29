import re
import os
import sys
import json
import subprocess
from pathlib import Path

LOGO_PATH = Path(__file__).parent.parent / "Siluseg - Logo TARJETA OK.jpg"
WORKER    = Path(__file__).parent / 'pdf_worker_rl.py'

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


def generar_pdf(resultados_por_aseguradora, info, output_path):
    aseguradoras_activas = [
        a for a in ASEGURADORAS
        if resultados_por_aseguradora.get(a, {}).get('ok') and
           resultados_por_aseguradora[a].get('coberturas')
    ]

    coberturas_vistas = []
    seen = set()
    for a in aseguradoras_activas:
        for c in resultados_por_aseguradora[a]['coberturas']:
            if c['nombre'] not in seen:
                coberturas_vistas.append(c['nombre'])
                seen.add(c['nombre'])

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

    wins = {a: 0 for a in aseguradoras_activas}
    for row in rows:
        if row['mejor']:
            wins[row['mejor']] += 1
    mejor_general = max(wins, key=wins.get) if wins else None
    mejor_wins    = wins.get(mejor_general, 0) if mejor_general else 0

    data = {
        'aseguradoras': aseguradoras_activas,
        'rows':         rows,
        'info':         info,
        'mejor_general': mejor_general,
        'mejor_wins':    mejor_wins,
        'logo_path':     str(LOGO_PATH) if LOGO_PATH.exists() else None,
    }

    result = subprocess.run(
        [sys.executable, str(WORKER), str(output_path)],
        input=json.dumps(data, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=60,
        env=os.environ.copy(),
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Error generando PDF (código {result.returncode}):\n{result.stderr}"
        )
