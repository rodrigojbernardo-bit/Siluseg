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
    fecha    = datetime.now().strftime('%d/%m/%Y')
    HDR_BG   = colors.HexColor('#f0f4f8')
    ACCENT   = colors.HexColor('#1a4b8c')

    def lbl(t):
        return f'<font name="Helvetica-Bold" size="7" color="#1a4b8c">{t}  </font>'
    def val(t):
        return f'<font name="Helvetica" size="8.5" color="#1a1a2e">{t}</font>'

    # Bloque de info: vehículo, cliente, DNI
    veh_str = f'{info.get("vehiculo","")} {info.get("anio","")}'.strip()
    info_lines = []
    if veh_str:
        info_lines.append(Paragraph(lbl('VEHÍCULO') + val(veh_str),
                                    ps('iv', leading=13)))
    if info.get('cliente'):
        info_lines.append(Paragraph(lbl('CLIENTE') + val(info['cliente']),
                                    ps('ic', leading=13)))
    if info.get('dni'):
        info_lines.append(Paragraph(lbl('DNI') + val(info['dni']),
                                    ps('id', leading=13)))

    # Fecha
    fecha_para = Paragraph(
        f'<font name="Helvetica" size="8" color="#555555">{fecha}</font>',
        ps('fd', alignment=TA_RIGHT, leading=12)
    )

    # Fila principal: [logo] | [info vehículo/cliente] | [fecha]
    logo_w    = 4.0 * cm
    logo_h    = 2.2 * cm
    logo_shown = False

    if logo_path and Path(logo_path).exists():
        try:
            from reportlab.platypus import Image as RLImage
            logo_img   = RLImage(logo_path, width=logo_w, height=logo_h, kind='proportional')
            main_row   = [[logo_img, info_lines, fecha_para]]
            main_cols  = [logo_w + 0.4*cm, usable * 0.60, usable - logo_w - 0.4*cm - usable * 0.60]
            logo_shown = True
        except Exception:
            pass

    if not logo_shown:
        main_row  = [[info_lines, fecha_para]]
        main_cols = [usable * 0.80, usable * 0.20]

    mt = Table(main_row, colWidths=main_cols)
    mt.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), HDR_BG),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW',     (0, 0), (-1, 0),  0, HDR_BG),
    ]))
    story.append(mt)

    # Barra de contacto oscura
    contact_para = Paragraph(
        '<font name="Helvetica-Bold" size="8" color="#ffffff">www.siluseg.com.ar'
        '</font>'
        '<font name="Helvetica" size="8" color="#aaccee">'
        '&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;'
        '</font>'
        '<font name="Helvetica" size="8" color="#ffffff">'
        'WhatsApp: +54 9 11 3450-1751'
        '</font>',
        ps('ct', alignment=TA_CENTER, leading=12)
    )
    cb = Table([[contact_para]], colWidths=[usable])
    cb.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), DARK),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
    ]))
    story.append(cb)
    story.append(Spacer(1, 0.3*cm))

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
