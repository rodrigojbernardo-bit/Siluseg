"""
Standalone PDF generator — reportlab only, no Playwright, no Flask.
Called as a subprocess: python pdf_worker_rl.py <output_path>
Data comes from stdin as JSON.
"""
import sys
import json
from pathlib import Path
from datetime import datetime


MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
         'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']


def main():
    data           = json.loads(sys.stdin.read())
    output_path    = sys.argv[1]

    aseguradoras   = data['aseguradoras']
    rows           = data['rows']
    info           = data['info']
    capitales      = data.get('capitales', {})
    logo_path      = data.get('logo_path')
    nro_cotizacion = data.get('nro_cotizacion', '')

    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer,
    )

    # ── Paleta ───────────────────────────────────────────────────────────────
    BLUE    = colors.HexColor('#222f5b')   # azul principal (logo)
    LIGHT   = colors.HexColor('#f5f5f5')
    BEST_BG = colors.HexColor('#c8f7c5')
    HDR_BG  = colors.HexColor('#f0f4f8')

    BRAND = {
        'Sancor':     colors.HexColor('#c0392b'),
        'Federación': colors.HexColor('#1a7a3c'),
        'Meridional': colors.HexColor('#222f5b'),
    }

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

    # ── Fecha larga ───────────────────────────────────────────────────────────
    now = datetime.now()
    fecha_larga = f"Buenos Aires, {now.day:02d} de {MESES[now.month - 1]} de {now.year}"

    # ── Encabezado ────────────────────────────────────────────────────────────
    # Columna izquierda: título + N° de cotización + datos del vehículo/cliente
    def lbl(t):
        return f'<font name="Helvetica-Bold" size="7" color="#222f5b">{t}  </font>'
    def val(t):
        return f'<font name="Helvetica" size="8.5" color="#1a1a2e">{t}</font>'

    left_lines = [
        Paragraph(
            '<font name="Helvetica-Bold" size="15" color="#222f5b">COTIZACIÓN AUTOMOTORES</font>',
            ps('ht', leading=20)
        ),
        Spacer(1, 0.12 * cm),
        Paragraph(
            f'<font name="Helvetica" size="10" color="#555555">N° {nro_cotizacion}</font>',
            ps('hn', leading=14)
        ),
        Spacer(1, 0.18 * cm),
    ]
    veh_str = f'{info.get("vehiculo", "")} {info.get("anio", "")}'.strip()
    if veh_str:
        left_lines.append(Paragraph(lbl('VEHÍCULO') + val(veh_str), ps('iv', leading=13)))
    if info.get('cliente'):
        left_lines.append(Paragraph(lbl('CLIENTE') + val(info['cliente']), ps('ic', leading=13)))
    if info.get('dni'):
        left_lines.append(Paragraph(lbl('DNI') + val(info['dni']), ps('id', leading=13)))

    # Columna derecha: logo arriba + fecha abajo
    logo_w = 4.2 * cm
    logo_h = 2.0 * cm
    hdr_right_w = usable * 0.30
    hdr_left_w  = usable - hdr_right_w

    fecha_para = Paragraph(
        f'<font name="Helvetica" size="8" color="#555555">{fecha_larga}</font>',
        ps('fd', alignment=TA_RIGHT, leading=12)
    )

    logo_shown = False
    if logo_path and Path(logo_path).exists():
        try:
            from reportlab.platypus import Image as RLImage
            logo_img = RLImage(logo_path, width=logo_w, height=logo_h, kind='proportional')
            right_inner = Table([[logo_img], [fecha_para]],
                                colWidths=[hdr_right_w - 0.6 * cm])
            right_inner.setStyle(TableStyle([
                ('ALIGN',         (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING',   (0, 0), (-1, -1), 0),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
                ('TOPPADDING',    (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            right_cell = right_inner
            logo_shown = True
        except Exception:
            pass

    if not logo_shown:
        right_cell = fecha_para

    ht = Table([[left_lines, right_cell]], colWidths=[hdr_left_w, hdr_right_w])
    ht.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), HDR_BG),
        ('VALIGN',        (0, 0), (0, 0),   'MIDDLE'),
        ('VALIGN',        (1, 0), (1, 0),   'MIDDLE'),
        ('ALIGN',         (1, 0), (1, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(ht)

    # ── Barra azul superior (contacto) ────────────────────────────────────────
    def _barra_azul(texto):
        t = Table(
            [[Paragraph(texto, ps('br', alignment=TA_CENTER, leading=12))]],
            colWidths=[usable]
        )
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), BLUE),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ]))
        return t

    story.append(_barra_azul(
        '<font name="Helvetica-Bold" size="8" color="#ffffff">www.siluseg.com.ar</font>'
        '<font name="Helvetica" size="8" color="#aaccee">&nbsp;&nbsp;|&nbsp;&nbsp;</font>'
        '<font name="Helvetica" size="8" color="#ffffff">WhatsApp: +54 9 11 3450-1751</font>'
    ))
    story.append(Spacer(1, 0.35 * cm))

    # ── Saludo ────────────────────────────────────────────────────────────────
    cliente = info.get('cliente', '').strip()
    saludo = (
        f'<font name="Helvetica-Bold" size="10" color="#222f5b">GRACIAS, {cliente}</font><br/>'
        '<font name="Helvetica" size="9" color="#444444">'
        'Abajo te detallamos las opciones de coberturas y precios que te podemos ofrecer '
        'para que puedas elegir la que más te convenga.'
        '</font>'
    )
    story.append(Paragraph(saludo, ps('sal', leading=15)))
    story.append(Spacer(1, 0.35 * cm))

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    n     = len(aseguradoras)
    cov_w = usable * 0.38
    pr_w  = (usable - cov_w) / max(n, 1)
    cols  = [cov_w] + [pr_w] * n

    th    = ps('th', fontName='Helvetica-Bold', fontSize=9,
               textColor=colors.white, alignment=TA_CENTER)
    td_cov = ps('tc', fontSize=8, leading=11)
    td_num = ps('tn', fontSize=9, alignment=TA_CENTER, leading=11)
    td_bst = ps('tb', fontSize=9, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#155724'),
                alignment=TA_CENTER, leading=11)

    def make_header_cell(aseg):
        cap = capitales.get(aseg, '')
        if cap:
            return Paragraph(
                f'<b>{aseg.upper()}</b><br/><font size="7">SA: {cap}</font>', th
            )
        return Paragraph(f'<b>{aseg.upper()}</b>', th)

    header = [Paragraph('<b>COBERTURA</b>', th)] + [make_header_cell(a) for a in aseguradoras]
    tdata  = [header]
    bests  = []

    for i, row in enumerate(rows):
        cells = [Paragraph(row['cobertura'], td_cov)]
        for j, a in enumerate(aseguradoras):
            price   = row['precios'].get(a)
            is_best = (row.get('mejor') == a) and bool(price)
            if is_best:
                bests.append((i + 1, j + 1))
            txt = f'<b>{price}</b>' if is_best and price else (price or '—')
            cells.append(Paragraph(txt, td_bst if is_best else td_num))
        tdata.append(cells)

    ct = Table(tdata, colWidths=cols, repeatRows=1)
    ts = [
        ('BACKGROUND',     (0, 0), (-1, 0), BLUE),
        ('GRID',           (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',     (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 5),
        ('LEFTPADDING',    (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 6),
    ]
    for j, a in enumerate(aseguradoras):
        ts.append(('BACKGROUND', (j + 1, 0), (j + 1, 0), BRAND.get(a, BLUE)))
    for (ri, ci) in bests:
        ts.append(('BACKGROUND', (ci, ri), (ci, ri), BEST_BG))
        ts.append(('FONTNAME',   (ci, ri), (ci, ri), 'Helvetica-Bold'))
    ct.setStyle(TableStyle(ts))
    story.append(ct)

    # ── Barra azul inferior (pie) ─────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(_barra_azul(
        '<font name="Helvetica" size="7.5" color="#ffffff">'
        'Esta cotización es orientativa y está sujeta a las condiciones de cada aseguradora. '
        'Validez: 30 días desde la fecha de emisión.'
        '&nbsp;&nbsp;|&nbsp;&nbsp;'
        'www.siluseg.com.ar'
        '&nbsp;&nbsp;|&nbsp;&nbsp;'
        'WhatsApp: +54 9 11 3450-1751'
        '</font>'
    ))

    doc.build(story)
    print("OK")


if __name__ == '__main__':
    main()
