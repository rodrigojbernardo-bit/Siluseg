"""
Standalone PDF generator — reportlab only, no Playwright, no Flask.
Called as a subprocess: python pdf_worker_rl.py <output_path>
Data comes from stdin as JSON.
"""
import sys
import json
from pathlib import Path
from datetime import datetime


def main():
    data        = json.loads(sys.stdin.read())
    output_path = sys.argv[1]

    aseguradoras  = data['aseguradoras']
    rows          = data['rows']
    info          = data['info']
    capitales     = data.get('capitales', {})
    logo_path     = data.get('logo_path')

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
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
    DARK    = colors.HexColor('#1a1a2e')
    LIGHT   = colors.HexColor('#f5f5f5')
    BEST_BG = colors.HexColor('#c8f7c5')
    GRAY    = colors.HexColor('#555555')

    page   = landscape(A4)
    margin = 1.2 * cm
    usable = page[0] - 2 * margin

    doc = SimpleDocTemplate(
        output_path,
        pagesize=page,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )

    def ps(name, **kw):
        kw.setdefault('fontName', 'Helvetica')
        kw.setdefault('fontSize', 9)
        kw.setdefault('leading', 12)
        return ParagraphStyle(name, **kw)

    story = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    fecha = datetime.now().strftime('%d/%m/%Y')

    # Columna izquierda: logo + datos de contacto
    contacto = (
        '<font size="8"><b>www.siluseg.com.ar</b><br/>'
        'WhatsApp: +54 9 11 3450-1751</font>'
    )
    left_col = [Paragraph(contacto, ps('c', fontSize=8, textColor=GRAY))]

    # Columna central: datos del vehículo y cliente
    vehiculo_txt = (
        f'<font size="8">'
        f'<b>Vehículo:</b> {info.get("vehiculo","")} {info.get("anio","")}<br/>'
        f'<b>Cliente:</b> {info.get("cliente","")}&nbsp;&nbsp;'
        f'<b>DNI:</b> {info.get("dni","")}'
        f'</font>'
    )
    center_col = Paragraph(vehiculo_txt, ps('i', fontSize=8, textColor=GRAY))

    # Columna derecha: fecha
    right_col = Paragraph(
        f'<font size="8">{fecha}</font>',
        ps('d', fontSize=8, alignment=TA_RIGHT, textColor=GRAY)
    )

    logo_w = 3.5 * cm
    logo_shown = False

    if logo_path and Path(logo_path).exists():
        try:
            from reportlab.platypus import Image as RLImage
            logo = RLImage(logo_path, width=logo_w, height=2.0*cm, kind='proportional')
            hdr_row = [[logo, left_col], [center_col], [right_col]]
            hdr_cols = [logo_w + 0.2*cm, usable * 0.42, usable * 0.55 - logo_w - 0.2*cm, usable * 0.13]
            # Usar tabla 4 columnas: logo | contacto | vehiculo | fecha
            hdr_row = [[logo, left_col, center_col, right_col]]
            hdr_cols = [logo_w, usable*0.22, usable*0.50, usable*0.13]
            logo_shown = True
        except Exception:
            pass

    if not logo_shown:
        hdr_row = [[left_col, center_col, right_col]]
        hdr_cols = [usable*0.25, usable*0.62, usable*0.13]

    ht = Table(hdr_row, colWidths=hdr_cols)
    ht.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.2*cm))
    story.append(HRFlowable(width='100%', thickness=1.5,
                             color=colors.HexColor('#cccccc')))
    story.append(Spacer(1, 0.25*cm))

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    n     = len(aseguradoras)
    cov_w = usable * 0.30
    ded_w = usable * 0.10
    pr_w  = (usable - cov_w - ded_w) / max(n, 1)
    cols  = [cov_w, ded_w] + [pr_w] * n

    th     = ps('th', fontName='Helvetica-Bold', fontSize=9,
                textColor=colors.white, alignment=TA_CENTER)
    th_sa  = ps('ts', fontName='Helvetica', fontSize=7,
                textColor=colors.HexColor('#dddddd'), alignment=TA_CENTER, leading=9)
    td_cov = ps('tc', fontSize=8, leading=10)
    td_ded = ps('td', fontSize=8, alignment=TA_CENTER, leading=10)
    td_num = ps('tn', fontSize=9, alignment=TA_CENTER, leading=11)
    td_bst = ps('tb', fontSize=9, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#155724'),
                alignment=TA_CENTER, leading=11)

    # Encabezado con nombre aseguradora + suma asegurada debajo
    def make_header_cell(aseg):
        cap = capitales.get(aseg, '')
        if cap:
            return Paragraph(
                f'<b>{aseg.upper()}</b><br/>'
                f'<font size="7">SA: {cap}</font>',
                th
            )
        return Paragraph(f'<b>{aseg.upper()}</b>', th)

    header = (
        [Paragraph('<b>COBERTURA</b>', th), Paragraph('<b>DEDUCIBLE</b>', th)]
        + [make_header_cell(a) for a in aseguradoras]
    )
    tdata = [header]
    bests = []

    for i, row in enumerate(rows):
        cells = [
            Paragraph(row['cobertura'], td_cov),
            Paragraph(row['deducible'] or '—', td_ded),
        ]
        for j, a in enumerate(aseguradoras):
            price   = row['precios'].get(a)
            is_best = (row.get('mejor') == a) and bool(price)
            if is_best:
                bests.append((i + 1, j + 2))
            txt = f'<b>{price}</b>' if is_best and price else (price or '—')
            cells.append(Paragraph(txt, td_bst if is_best else td_num))
        tdata.append(cells)

    ct = Table(tdata, colWidths=cols, repeatRows=1)
    ts = [
        ('BACKGROUND',     (0, 0), (-1, 0), DARK),
        ('GRID',           (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',     (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 5),
        ('LEFTPADDING',    (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 6),
    ]
    for j, a in enumerate(aseguradoras):
        ts.append(('BACKGROUND', (j + 2, 0), (j + 2, 0), BRAND.get(a, DARK)))
    for (ri, ci) in bests:
        ts.append(('BACKGROUND', (ci, ri), (ci, ri), BEST_BG))
        ts.append(('FONTNAME',   (ci, ri), (ci, ri), 'Helvetica-Bold'))
    ct.setStyle(TableStyle(ts))
    story.append(ct)

    doc.build(story)
    print("OK")


if __name__ == '__main__':
    main()
