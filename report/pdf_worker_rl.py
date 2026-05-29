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
    mejor_general = data.get('mejor_general')
    mejor_wins    = data.get('mejor_wins', 0)
    logo_path     = data.get('logo_path')

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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
    DARK     = colors.HexColor('#1a1a2e')
    LIGHT    = colors.HexColor('#f5f5f5')
    BEST_BG  = colors.HexColor('#c8f7c5')

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
        kw.setdefault('leading', 11)
        return ParagraphStyle(name, **kw)

    story = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    fecha   = datetime.now().strftime('%d/%m/%Y')
    hdr_row = [[
        Paragraph('<b>COTIZACIÓN COMPARATIVA DE SEGUROS</b>',
                  ps('t', fontSize=13, fontName='Helvetica-Bold', textColor=DARK)),
        Paragraph(
            f'<font size="8"><b>Vehículo:</b> {info.get("vehiculo","")} {info.get("anio","")}<br/>'
            f'<b>Suma asegurada:</b> {info.get("capital","")}<br/>'
            f'<b>Cliente:</b> {info.get("cliente","")}&nbsp;&nbsp;<b>DNI:</b> {info.get("dni","")}</font>',
            ps('i', fontSize=8, textColor=colors.HexColor('#555555'))),
        Paragraph(f'<font size="8">{fecha}</font>',
                  ps('d', fontSize=8, alignment=TA_RIGHT,
                     textColor=colors.HexColor('#777777'))),
    ]]
    logo_widths = [usable * 0.40, usable * 0.45, usable * 0.15]

    if logo_path and Path(logo_path).exists():
        try:
            from reportlab.platypus import Image as RLImage
            logo = RLImage(logo_path, width=2.4*cm, height=1.4*cm, kind='proportional')
            hdr_row[0].insert(0, logo)
            logo_widths = [2.6*cm, usable * 0.35, usable * 0.45, usable * 0.15]
        except Exception:
            pass

    ht = Table(hdr_row, colWidths=logo_widths)
    ht.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.25*cm))
    story.append(HRFlowable(width='100%', thickness=1.5,
                             color=colors.HexColor('#cccccc')))
    story.append(Spacer(1, 0.25*cm))

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    n       = len(aseguradoras)
    cov_w   = usable * 0.30
    ded_w   = usable * 0.10
    pr_w    = (usable - cov_w - ded_w) / max(n, 1)
    cols    = [cov_w, ded_w] + [pr_w] * n

    th     = ps('th', fontName='Helvetica-Bold', fontSize=9,
                textColor=colors.white, alignment=TA_CENTER)
    td_cov = ps('tc', fontSize=8, leading=10)
    td_ded = ps('td', fontSize=8, alignment=TA_CENTER, leading=10)
    td_num = ps('tn', fontSize=9, alignment=TA_CENTER, leading=11)
    td_bst = ps('tb', fontSize=9, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#155724'),
                alignment=TA_CENTER, leading=11)

    header = (
        [Paragraph('<b>COBERTURA</b>', th), Paragraph('<b>DEDUCIBLE</b>', th)]
        + [Paragraph(f'<b>{a.upper()}</b>', th) for a in aseguradoras]
    )
    tdata  = [header]
    bests  = []

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
        ('BACKGROUND',    (0, 0), (-1, 0), DARK),
        ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, LIGHT]),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]
    for j, a in enumerate(aseguradoras):
        ts.append(('BACKGROUND', (j + 2, 0), (j + 2, 0),
                   BRAND.get(a, DARK)))
    for (ri, ci) in bests:
        ts.append(('BACKGROUND', (ci, ri), (ci, ri), BEST_BG))
        ts.append(('FONTNAME',   (ci, ri), (ci, ri), 'Helvetica-Bold'))
    ct.setStyle(TableStyle(ts))
    story.append(ct)
    story.append(Spacer(1, 0.4*cm))

    # ── Ganador ───────────────────────────────────────────────────────────────
    if mejor_general:
        wc = BRAND.get(mejor_general, DARK)
        story.append(Paragraph(
            f'<b>MEJOR PRECIO GENERAL: {mejor_general.upper()}</b>'
            f'  —  ganó {mejor_wins} de {len(rows)} coberturas',
            ps('w', fontSize=11, fontName='Helvetica-Bold',
               textColor=wc, alignment=TA_CENTER),
        ))

    doc.build(story)
    print("OK")


if __name__ == '__main__':
    main()
