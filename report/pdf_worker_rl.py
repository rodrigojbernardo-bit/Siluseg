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
    data              = json.loads(sys.stdin.read())
    output_path       = sys.argv[1]

    aseguradoras      = data['aseguradoras']
    rows              = data['rows']
    info              = data['info']
    capitales         = data.get('capitales', {})
    logo_path         = data.get('logo_path')
    nro_cotizacion    = data.get('nro_cotizacion', '')
    logos_aseguradoras = data.get('logos_aseguradoras', {})

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, Image as RLImage, Flowable,
    )

    # ── Paleta ───────────────────────────────────────────────────────────────
    BLUE    = colors.HexColor('#222f5b')
    LIGHT   = colors.HexColor('#f5f5f5')
    BEST_BG = colors.HexColor('#c8f7c5')
    GRAY    = colors.HexColor('#555555')

    BRAND = {
        'Sancor':     colors.HexColor('#c0392b'),
        'Federación': colors.HexColor('#1a7a3c'),
        'Meridional': colors.HexColor('#222f5b'),
    }

    # ── Página vertical (A4 portrait) ────────────────────────────────────────
    page   = A4
    margin = 1.2 * cm
    usable = page[0] - 2 * margin   # ≈ 18.6 cm

    doc = SimpleDocTemplate(
        output_path,
        pagesize=page,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin,  bottomMargin=margin,
    )

    def ps(name, **kw):
        kw.setdefault('fontName', 'Helvetica')
        kw.setdefault('fontSize', 9)
        kw.setdefault('leading', 12)
        return ParagraphStyle(name, **kw)

    def _barra_azul(html_txt):
        t = Table(
            [[Paragraph(html_txt, ps('br', alignment=TA_CENTER, leading=13))]],
            colWidths=[usable]
        )
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), BLUE),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ]))
        return t

    story = []

    # ── Fecha larga ───────────────────────────────────────────────────────────
    now = datetime.now()
    fecha_larga = f"Buenos Aires, {now.day:02d} de {MESES[now.month - 1]} de {now.year}"

    # ── Encabezado: COTIZACIÓN centrada | logo + fecha a la derecha ──────────
    hdr_right_w = usable * 0.35
    hdr_left_w  = usable - hdr_right_w

    titulo_para = Paragraph(
        '<font name="Helvetica-Bold" size="17" color="#222f5b">COTIZACIÓN AUTOMOTORES</font>',
        ps('ht', alignment=TA_CENTER, leading=22)
    )

    fecha_para = Paragraph(
        f'<font name="Helvetica" size="8" color="#555555">{fecha_larga}</font>',
        ps('fd', alignment=TA_RIGHT, leading=12)
    )

    right_cell = fecha_para
    if logo_path and Path(logo_path).exists():
        try:
            logo_img = RLImage(logo_path, width=4.5*cm, height=2.0*cm, kind='proportional')
            right_tbl = Table([[logo_img], [fecha_para]],
                              colWidths=[hdr_right_w - 0.4*cm])
            right_tbl.setStyle(TableStyle([
                ('ALIGN',         (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING',   (0, 0), (-1, -1), 0),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
                ('TOPPADDING',    (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            right_cell = right_tbl
        except Exception:
            pass

    ht = Table([[titulo_para, right_cell]], colWidths=[hdr_left_w, hdr_right_w])
    ht.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (0, 0),   'CENTER'),
        ('ALIGN',         (1, 0), (1, 0),   'RIGHT'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        # Sin fondo — blanco puro
    ]))
    story.append(ht)

    # ── Barra azul: N° cotización + contacto ──────────────────────────────────
    story.append(_barra_azul(
        f'<font name="Helvetica-Bold" size="9" color="#ffffff">COTIZACIÓN N° {nro_cotizacion}</font>'
        '<font name="Helvetica" size="8" color="#7fa8d8">&nbsp;&nbsp;|&nbsp;&nbsp;</font>'
        '<font name="Helvetica" size="8" color="#ffffff">www.siluseg.com.ar</font>'
        '<font name="Helvetica" size="8" color="#7fa8d8">&nbsp;&nbsp;|&nbsp;&nbsp;</font>'
        '<font name="Helvetica" size="8" color="#ffffff">WhatsApp: +54 9 11 3450-1751</font>'
    ))
    story.append(Spacer(1, 0.3 * cm))

    # ── Saludo + datos del vehículo ───────────────────────────────────────────
    cliente = info.get('cliente', '').strip()
    story.append(Paragraph(
        f'<font name="Helvetica-Bold" size="11" color="#222f5b">GRACIAS, {cliente}</font>',
        ps('sal1', leading=16)
    ))
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph(
        'Abajo te detallamos las opciones de coberturas y precios que te podemos '
        'ofrecer para que puedas elegir la que más te convenga.',
        ps('sal2', fontSize=9, leading=13)
    ))
    story.append(Spacer(1, 0.15 * cm))

    veh_str = f'{info.get("vehiculo", "")} {info.get("anio", "")}'.strip()
    partes_info = []
    if veh_str:              partes_info.append(f'<b>Vehículo:</b> {veh_str}')
    if info.get('cliente'):  partes_info.append(f'<b>Cliente:</b> {info["cliente"]}')
    if info.get('dni'):      partes_info.append(f'<b>DNI:</b> {info["dni"]}')
    if partes_info:
        story.append(Paragraph(
            '&nbsp;&nbsp;&nbsp;'.join(partes_info),
            ps('veh', fontSize=8, leading=12, textColor=GRAY)
        ))
    story.append(Spacer(1, 0.3 * cm))

    # ── Tabla comparativa ─────────────────────────────────────────────────────
    n     = len(aseguradoras)
    cov_w = usable * 0.38
    pr_w  = (usable - cov_w) / max(n, 1)
    cols  = [cov_w] + [pr_w] * n

    th    = ps('th', fontName='Helvetica-Bold', fontSize=8,
               textColor=colors.white, alignment=TA_CENTER)
    th_sm = ps('thsm', fontName='Helvetica', fontSize=6.5,
               textColor=colors.HexColor('#dddddd'), alignment=TA_CENTER, leading=9)
    td_cov = ps('tc', fontSize=8, leading=11)
    td_num = ps('tn', fontSize=9, alignment=TA_CENTER, leading=11)
    td_bst = ps('tb', fontSize=9, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#155724'),
                alignment=TA_CENTER, leading=11)

    def make_header_cell(aseg):
        cap          = capitales.get(aseg, '')
        logo_aseg_path = logos_aseguradoras.get(aseg, '')
        items = []

        # Logo de la aseguradora (si existe)
        if logo_aseg_path and Path(logo_aseg_path).exists():
            try:
                aseg_logo = RLImage(logo_aseg_path,
                                    width=pr_w * 0.75, height=0.85*cm,
                                    kind='proportional')
                items.append(aseg_logo)
            except Exception:
                pass

        # Nombre
        txt = f'<b>{aseg.upper()}</b>'
        if cap:
            txt += f'<br/><font size="6.5">SA: {cap}</font>'
        items.append(Paragraph(txt, th))
        return items

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
        ('LEFTPADDING',    (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 5),
    ]
    for j, a in enumerate(aseguradoras):
        ts.append(('BACKGROUND', (j + 1, 0), (j + 1, 0), BRAND.get(a, BLUE)))
    for (ri, ci) in bests:
        ts.append(('BACKGROUND', (ci, ri), (ci, ri), BEST_BG))
        ts.append(('FONTNAME',   (ci, ri), (ci, ri), 'Helvetica-Bold'))
    ct.setStyle(TableStyle(ts))
    story.append(ct)

    # ── Leyenda (aclaración) + banner, anclados casi al pie de la página ─────
    RED = colors.HexColor('#bd222e')   # rojo de la paleta del logo

    leyenda_txt = (
        '<font name="Helvetica-Bold" size="8" color="#888888">Aclaración importante:</font><br/>'
        '<font name="Helvetica" size="7.5" color="#888888">'
        'Los valores son a título orientativo. Los mismos se encuentran sujetos a '
        'modificaciones hasta tanto no se efectivice la solicitud formal. La aceptación '
        'de la cobertura quedará sujeta al análisis previo del Área de Suscripción de '
        'cada Aseguradora. Ante cualquier consulta podés comunicarte con Nosotros por '
        'medio del WhatsApp +5491134501751 o llamando al +5491134501751 en el horario '
        'de Lunes a Viernes de 10 a 17 hs.'
        '</font>'
    )
    leyenda = Table(
        [['', Paragraph(leyenda_txt, ps('ley', leading=10))]],
        colWidths=[0.07 * cm, usable - 0.07 * cm],
    )
    leyenda.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, 0), BLUE),   # barrita azul a la altura del texto
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (0, 0), 0),
        ('RIGHTPADDING',  (0, 0), (0, 0), 0),
        ('LEFTPADDING',   (1, 0), (1, 0), 8),
        ('RIGHTPADDING',  (1, 0), (1, 0), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # Foto de la casa: Casa_Banner.jpg/png en la carpeta principal de la app
    banner_dir = Path(__file__).resolve().parent.parent
    foto_banner = None
    for nombre in ('Casa_Banner.jpg', 'Casa_Banner.png', 'Casa_Banner.jpeg'):
        p = banner_dir / nombre
        if p.exists():
            foto_banner = str(p)
            break

    banner_h = 2.7 * cm

    class Banner(Flowable):
        """Banner promocional: rectángulo azul redondeado, círculos rojos
        decorativos, foto a la izquierda y textos en blanco."""
        def __init__(self, width, height, foto):
            self.width = width
            self.height = height
            self.foto = foto

        def wrap(self, aw, ah):
            return (self.width, self.height)

        def _lineas(self, c, cx, lineas):
            total = sum(sz * 1.45 for _, _, sz in lineas)
            y = (self.height + total) / 2 - lineas[0][2]
            for txt, fnt, sz in lineas:
                c.setFont(fnt, sz)
                c.setFillColor(colors.white)
                c.drawCentredString(cx, y, txt)
                y -= sz * 1.55

        def draw(self):
            c = self.canv
            w, h = self.width, self.height
            rad = 0.4 * cm
            img_w = 4.8 * cm if self.foto else 0
            cta_w = 5.8 * cm
            mid_x = img_w + (w - img_w - cta_w) / 2
            cta_x = w - cta_w / 2

            # Fondo azul redondeado
            c.saveState()
            c.setFillColor(BLUE)
            c.roundRect(0, 0, w, h, rad, fill=1, stroke=0)

            # Recortar todo a las esquinas redondeadas
            path = c.beginPath()
            path.roundRect(0, 0, w, h, rad)
            c.clipPath(path, stroke=0, fill=0)

            # Círculos rojos decorativos
            c.setFillColor(RED)
            c.circle(w * 0.985, h * 0.30, h * 0.62, fill=1, stroke=0)
            c.circle(w * 0.50,  h * 1.02, h * 0.30, fill=1, stroke=0)
            c.circle(w * 0.70,  -h * 0.10, h * 0.26, fill=1, stroke=0)

            # Foto a la izquierda (dentro del recorte → esquinas redondeadas)
            if self.foto:
                try:
                    from reportlab.lib.utils import ImageReader
                    c.drawImage(ImageReader(self.foto), 0, 0, img_w, h,
                                preserveAspectRatio=False, mask='auto')
                except Exception:
                    pass
            c.restoreState()

            # Textos
            self._lineas(c, mid_x, [
                ('Asegurá tu Auto', 'Helvetica-Bold', 13),
                ('y Conseguí un 10% OFF', 'Helvetica-Bold', 10),
                ('en el Seguro de tu Hogar', 'Helvetica-Bold', 10),
            ])
            self._lineas(c, cta_x, [
                ('Cotizá todos tus seguros', 'Helvetica-Bold', 10.5),
                ('Escribinos al WhatsApp', 'Helvetica', 8.5),
                ('+54 9 11 3450-1751', 'Helvetica-Bold', 11),
            ])

    banner = Banner(usable, banner_h, foto_banner)

    # Empujar leyenda + banner hacia el fondo de la página
    class PushDown(Flowable):
        """Consume el espacio libre para que lo que sigue quede abajo."""
        def __init__(self, reservar):
            self.reservar = reservar
        def wrap(self, aw, ah):
            self.width = aw
            self.height = max(0, ah - self.reservar)
            return (aw, self.height)
        def draw(self):
            pass

    gap = 0.5 * cm
    ley_h = leyenda.wrap(usable, 10000)[1]
    reserva = ley_h + gap + banner_h
    story.append(PushDown(reserva))
    story.append(leyenda)
    story.append(Spacer(1, gap))
    story.append(banner)

    doc.build(story)
    print("OK")


if __name__ == '__main__':
    main()
