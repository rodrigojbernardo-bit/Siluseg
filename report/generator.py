import re
import base64
from pathlib import Path
from datetime import datetime

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

    _pdf_reportlab(aseguradoras_activas, rows, info, mejor_general, mejor_wins, output_path)


def _pdf_reportlab(aseguradoras, rows, info, mejor_general, mejor_wins, output_path):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )

    BRAND = {
        'Sancor':     colors.HexColor('#c0392b'),
        'Federación': colors.HexColor('#1a7a3c'),
        'Meridional': colors.HexColor('#1a4b8c'),
    }
    BRAND_LIGHT = {
        'Sancor':     colors.HexColor('#fdecea'),
        'Federación': colors.HexColor('#e8f5e9'),
        'Meridional': colors.HexColor('#e3f2fd'),
    }
    DARK      = colors.HexColor('#1a1a2e')
    LIGHT_ROW = colors.HexColor('#f5f5f5')
    BEST_BG   = colors.HexColor('#c8f7c5')

    page    = landscape(A4)
    W       = page[0]
    margin  = 1.2 * cm
    usable  = W - 2 * margin

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )

    def style(name, **kw):
        defaults = dict(fontName='Helvetica', fontSize=9, leading=11)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    story = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    fecha    = datetime.now().strftime('%d/%m/%Y')
    vehiculo = f"{info.get('vehiculo', '')} {info.get('anio', '')}".strip()
    cliente  = info.get('cliente', '')
    dni      = info.get('dni', '')
    capital  = info.get('capital', '')

    title_p = Paragraph(
        '<b>COTIZACIÓN COMPARATIVA DE SEGUROS</b>',
        style('title', fontSize=14, fontName='Helvetica-Bold', textColor=DARK),
    )
    info_p = Paragraph(
        f'<font size="8"><b>Vehículo:</b> {vehiculo}&nbsp;&nbsp;'
        f'<b>Suma asegurada:</b> {capital}<br/>'
        f'<b>Cliente:</b> {cliente}&nbsp;&nbsp;<b>DNI:</b> {dni}</font>',
        style('info', fontSize=8, textColor=colors.HexColor('#555555')),
    )
    date_p = Paragraph(
        f'<font size="8">{fecha}</font>',
        style('date', fontSize=8, alignment=TA_RIGHT, textColor=colors.HexColor('#777777')),
    )

    logo_cell = ''
    logo_widths = [usable * 0.45, usable * 0.40, usable * 0.15]
    if LOGO_PATH.exists():
        try:
            from reportlab.platypus import Image as RLImage
            logo_cell = RLImage(str(LOGO_PATH), width=2.4*cm, height=1.4*cm, kind='proportional')
            logo_widths = [2.6*cm, usable * 0.40, usable * 0.35, usable * 0.15]
            hdr_row = [[logo_cell, title_p, info_p, date_p]]
        except Exception:
            hdr_row = [[title_p, info_p, date_p]]
    else:
        hdr_row = [[title_p, info_p, date_p]]

    hdr_table = Table(hdr_row, colWidths=logo_widths)
    hdr_table.setStyle(TableStyle([
        ('VALIGN',  (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 0.25*cm))
    story.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#cccccc')))
    story.append(Spacer(1, 0.25*cm))

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    n           = len(aseguradoras)
    cov_w       = usable * 0.30
    ded_w       = usable * 0.10
    price_w     = (usable - cov_w - ded_w) / max(n, 1)
    col_widths  = [cov_w, ded_w] + [price_w] * n

    th = style('th', fontName='Helvetica-Bold', fontSize=9,
               textColor=colors.white, alignment=TA_CENTER)
    td_cov = style('tdcov', fontSize=8, leading=10)
    td_ded = style('tdded', fontSize=8, alignment=TA_CENTER, leading=10)
    td_num = style('tdnum', fontSize=9, alignment=TA_CENTER, leading=11)
    td_best = style('tdbest', fontSize=9, fontName='Helvetica-Bold',
                    textColor=colors.HexColor('#155724'), alignment=TA_CENTER, leading=11)

    header_row = [
        Paragraph('<b>COBERTURA</b>', th),
        Paragraph('<b>DEDUCIBLE</b>', th),
    ] + [Paragraph(f'<b>{a.upper()}</b>', th) for a in aseguradoras]

    table_data = [header_row]
    best_cells = []

    for i, row in enumerate(rows):
        cells = [
            Paragraph(row['cobertura'], td_cov),
            Paragraph(row['deducible'] or '—', td_ded),
        ]
        for j, a in enumerate(aseguradoras):
            price = row['precios'].get(a)
            is_best = (row.get('mejor') == a) and price
            if is_best:
                best_cells.append((i + 1, j + 2))
            text = f'<b>{price}</b>' if is_best and price else (price or '—')
            cells.append(Paragraph(text, td_best if is_best else td_num))
        table_data.append(cells)

    comp = Table(table_data, colWidths=col_widths, repeatRows=1)

    ts = [
        ('BACKGROUND',    (0, 0), (-1, 0), DARK),
        ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, LIGHT_ROW]),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]
    for j, a in enumerate(aseguradoras):
        ts.append(('BACKGROUND', (j + 2, 0), (j + 2, 0), BRAND.get(a, DARK)))

    for (ri, ci) in best_cells:
        a = aseguradoras[ci - 2]
        ts.append(('BACKGROUND', (ci, ri), (ci, ri), BEST_BG))
        ts.append(('FONTNAME',   (ci, ri), (ci, ri), 'Helvetica-Bold'))

    comp.setStyle(TableStyle(ts))
    story.append(comp)
    story.append(Spacer(1, 0.4*cm))

    # ── Ganador ───────────────────────────────────────────────────────────────
    if mejor_general:
        win_color = BRAND.get(mejor_general, DARK)
        story.append(Paragraph(
            f'<b>MEJOR PRECIO GENERAL: {mejor_general.upper()}</b>'
            f'  —  ganó {mejor_wins} de {len(rows)} coberturas',
            style('winner', fontSize=11, fontName='Helvetica-Bold', textColor=win_color, alignment=TA_CENTER),
        ))

    doc.build(story)
