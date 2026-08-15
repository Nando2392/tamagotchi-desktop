# tamagotchi_art.py — Arte del Tamagotchi DINO de escritorio (PIL puro, sin tkinter)
# Todo se dibuja por código: caparazón tipo dispositivo, sprite dinosaurio por
# etapa, partículas e iconos. Renderiza sobre fondo MAGENTA que la ventana
# transparente de tkinter convierte en "nada" (-transparentcolor).
import math
from PIL import Image, ImageDraw, ImageFont

W, H = 380, 470
MAGENTA = (255, 0, 255)
SCREEN = (48, 68, 332, 352)          # área de pantalla (bezel interior)
STATUS_POS = (58, 84)                # fila de barras de estado
PET_ANCHOR = (190, 232)              # centro del sprite
PET_BOTTOM = 308                     # línea de apoyo (pies/huevo)
BUTTONS = {                          # nombre -> (x, y, radio)
    "feed": (120, 428, 25),
    "play": (190, 428, 25),
    "bathe": (260, 428, 25),
    "sleep": (318, 428, 14),
}
CLOSE_RECT = (238, 14, 268, 40)
POOP_SLOTS = [(74, 302), (98, 308), (86, 320)]
TEXT_AGE = (58, 330)
TEXT_HINT = (190, 330)
SHOWER_RECT = (150, 195, 262, 305)   # mampara de ducha (en pantalla)

OUTLINE = (46, 34, 22)          # contorno casi negro (estilo Agumon)

PALETTES = {
    "egg":        {"body": (255, 250, 238, 255), "spot": (150, 214, 180, 255),
                   "crack": (120, 100, 90, 255)},
    "baby":       {"body": (255, 205, 90, 255), "belly": (255, 236, 190, 255),
                   "cheek": (255, 170, 150, 255), "spike": (250, 210, 110, 255)},
    "child":      {"body": (251, 177, 2, 255), "belly": (255, 224, 130, 255),
                   "cheek": (255, 160, 130, 255), "spike": (250, 210, 110, 255)},
    "teen":       {"body": (238, 152, 2, 255), "belly": (255, 210, 120, 255),
                   "cheek": (255, 155, 125, 255), "spike": (250, 210, 110, 255)},
    "adult_good": {"body": (224, 128, 0, 255), "belly": (255, 198, 108, 255),
                   "cheek": (255, 150, 120, 255), "spike": (250, 210, 110, 255)},
    "adult_bad":  {"body": (150, 160, 168, 255), "belly": (208, 216, 222, 255),
                   "cheek": (130, 142, 152, 255), "spike": (110, 120, 130, 255)},
    "sick":       {"body": (196, 206, 96, 255), "belly": (225, 232, 160, 255),
                   "cheek": (190, 200, 130, 255), "spike": (150, 180, 110, 255)},
    "ghost":      {"body": (244, 246, 248, 255), "cheek": (224, 230, 236, 255)},
}

STAGE_SIZES = {  # (ancho cuerpo, alto cuerpo) por etapa — Agumon compacto
    "egg": (64, 78), "baby": (58, 54), "child": (70, 66),
    "teen": (82, 78), "adult": (92, 88),
}


def _font(size, bold=False):
    names = ["arialbd.ttf" if bold else "arial.ttf", "segoeui.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{n}", size)
        except Exception:
            pass
    return ImageFont.load_default()


# ---------------------------------------------------------------- caparazón
def _shell_poly(pad=18):
    """Polígono de la silueta del dispositivo (óvalo ergonómico tipo Digivice).
    Ancho en toda la altura para albergar pantalla y botones; se afina solo
    en las puntas superior e inferior."""
    cx = W / 2
    ctl = [(0.0, 56), (0.08, 150), (0.22, 162), (0.42, 168), (0.60, 165),
           (0.76, 158), (0.90, 150), (1.0, 138)]
    pts = []
    def hw_at(t):
        for j in range(len(ctl) - 1):
            if t <= ctl[j + 1][0]:
                t0, w0 = ctl[j]
                t1, w1 = ctl[j + 1]
                f = (t - t0) / (t1 - t0)
                f = f * f * (3 - 2 * f)          # smoothstep
                return w0 + (w1 - w0) * f
        return ctl[-1][1]
    n = 40
    for i in range(n + 1):
        t = i / n
        y = pad + t * (H - 2 * pad)
        pts.append((cx - hw_at(t), y))
    for i in range(n, -1, -1):
        t = i / n
        y = pad + t * (H - 2 * pad)
        pts.append((cx + hw_at(t), y))
    return pts


def render_shell():
    """Caparazón estilo Digivice (amarillo dorado → naranja, contorno negro,
    LCD oscuro). RGB sobre fondo MAGENTA. Estático."""
    img = Image.new("RGB", (W, H), MAGENTA)
    d = ImageDraw.Draw(img)
    poly = _shell_poly(14)

    # 1) contorno NEGRO grueso (escala desde el centro)
    cx, cy = W / 2, H / 2
    outer = [(cx + (x - cx) * 1.035, cy + (y - cy) * 1.035) for x, y in poly]
    d.polygon(outer, fill=(16, 14, 12))

    # 2) cuerpo: degradado amarillo dorado → naranja → marrón
    grad = Image.new("RGB", (W, H))
    gd = ImageDraw.Draw(grad)
    stops = [(0.0, (251, 183, 10)), (0.45, (238, 158, 6)),
             (0.78, (205, 118, 2)), (1.0, (150, 86, 0))]
    for y in range(H):
        f = y / H
        for k in range(len(stops) - 1):
            if f <= stops[k + 1][0]:
                f0, c0 = stops[k]
                f1, c1 = stops[k + 1]
                t = (f - f0) / (f1 - f0)
                col = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
                break
        else:
            col = stops[-1][1]
        gd.line((0, y, W - 1, y), fill=col)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    img.paste(grad, (0, 0), mask)

    # 3) línea de costura interior + brillo superior (lado izquierdo)
    inner = [(cx + (x - cx) * 0.972, cy + (y - cy) * 0.972) for x, y in poly]
    d.polygon(inner, outline=(120, 66, 0), width=2)
    d.arc((24, 16, 300, 220), 160, 300, fill=(255, 240, 190, 120), width=3)

    # 4) pantalla: bezel negro + marco metálico + LCD oscuro
    d.rounded_rectangle((40, 60, 340, 360), radius=30, fill=(12, 10, 8))
    d.rounded_rectangle((40, 60, 340, 360), radius=30, outline=(90, 90, 92), width=2)
    d.rounded_rectangle((44, 64, 336, 356), radius=26, fill=(70, 72, 76),
                        outline=(110, 112, 116), width=1)
    lcd = Image.new("RGB", (W, H))
    ld = ImageDraw.Draw(lcd)
    for y in range(68, 353):
        f = (y - 68) / 284
        c = int(26 + 22 * f)
        ld.line((49, y, 331, y), fill=(c, c + 2, c + 4))
    lm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(lm).rounded_rectangle((48, 68, 332, 352), radius=22, fill=255)
    img.paste(lcd, (0, 0), lm)
    d.rounded_rectangle((48, 68, 332, 352), radius=22, outline=(60, 62, 66), width=1)

    # 5) botones estilo Digivice (negros, iconos dorados)
    _button(img, *BUTTONS["feed"], fill=(30, 28, 26), icon="food")
    _button(img, *BUTTONS["play"], fill=(30, 28, 26), icon="star")
    _button(img, *BUTTONS["bathe"], fill=(30, 28, 26), icon="bubbles")
    _button(img, *BUTTONS["sleep"], fill=(30, 28, 26), icon="moon")

    # 6) altavoz (puntos oscuros)
    for i, x in enumerate((170, 190, 210)):
        d.ellipse((x - 2.5, 448, x + 2.5, 453), fill=(60, 40, 10))

    # 7) botón de cerrar (X) rojo coral
    x0, y0, x1, y1 = CLOSE_RECT
    d.rounded_rectangle((x0, y0, x1, y1), radius=9, fill=(240, 120, 110),
                        outline=(150, 60, 50), width=2)
    d.line((x0 + 6, y0 + 6, x1 - 6, y1 - 6), fill=(255, 255, 255), width=2)
    d.line((x1 - 6, y0 + 6, x0 + 6, y1 - 6), fill=(255, 255, 255), width=2)
    return img


def _button(img, cx, cy, r, fill, icon):
    d = ImageDraw.Draw(img)
    # sombra
    d.ellipse((cx - r + 2, cy - r + 4, cx + r + 2, cy + r + 4), fill=(110, 62, 0))
    # cuerpo negro con bisel
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=(130, 120, 96), width=2)
    d.ellipse((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), outline=(72, 68, 60), width=1)
    GOLD = (250, 210, 110)
    if icon == "food":
        _icon_onigiri(d, cx, cy, 11, GOLD)
    elif icon == "star":
        _icon_star(d, cx, cy, 9, GOLD)
    elif icon == "bubbles":
        d.ellipse((cx - 7, cy - 4, cx - 1, cy + 2), outline=GOLD, width=2)
        d.ellipse((cx + 1, cy - 6, cx + 7, cy), outline=GOLD, width=2)
        d.line((cx - 4, cy + 3, cx - 2, cy + 3), fill=GOLD, width=2)
    elif icon == "moon":
        d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=GOLD)
        d.ellipse((cx + 2, cy - 6, cx + 8, cy + 4), fill=fill)


def _icon_onigiri(d, cx, cy, s, ink):
    pts = [(cx, cy - s), (cx - s, cy + s * 0.8), (cx + s, cy + s * 0.8)]
    d.polygon(pts, fill=(248, 240, 224), outline=(20, 20, 20))
    d.rounded_rectangle((cx - s + 1, cy - s + 1, cx + s - 1, cy - s + 4), radius=2,
                        fill=(52, 44, 38))
    d.ellipse((cx - 1.5, cy + 1, cx + 1.5, cy + 4), fill=(255, 138, 128))


def _icon_star(d, cx, cy, r, ink):
    pts = []
    for i in range(10):
        ang = math.pi / 5 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    ImageDraw.Draw(d._image if hasattr(d, "_image") else d.img).polygon(
        pts, fill=ink, outline=(20, 20, 20))


# ---------------------------------------------------------------- sprite DINO
def render_pet(stage, quality, state, phase=0.0, scale=1.0):
    """Sprite RGBA del dinosaurio chibi FRONTAL estilo Agumon (referencia del
    usuario): cabeza grande redonda con DOS ojos, hocico claro con boca,
    bracitos T-rex a los lados, patas con tres dedos, cola gruesa. Sin espinas.
    stage: egg|baby|child|teen|adult|ghost. state: idle|blink|happy|sleep|sick|eat."""
    if stage == "egg":
        return _render_egg(phase, state == "peck")
    if stage == "ghost":
        return _render_ghost(phase)
    if state == "sick":
        pal = PALETTES["sick"]
    elif stage == "adult":
        pal = PALETTES["adult_good" if quality == "good" else "adult_bad"]
    else:
        pal = PALETTES[stage]
    w, h = STAGE_SIZES[stage]
    lw = int(w * 2.3) + 16
    lh = h + 44
    img = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = lw * 0.5
    base = 10 + h
    bob = math.sin(phase * math.tau) * 1.5
    body_c, belly_c = pal["body"], pal["belly"]
    baby = stage == "baby"

    head_r = w * (0.34 if baby else 0.30)   # cabeza grande chibi
    body_rx = w * 0.26
    body_ry = w * 0.21
    head_cy = base - h * 0.66
    body_cy = base - h * 0.24

    def _ell_out(bb, k=1.10):
        x0, y0, x1, y1 = bb
        cxm, cym = (x0 + x1) / 2, (y0 + y1) / 2
        ww, hh = (x1 - x0) * k, (y1 - y0) * k
        return (cxm - ww / 2, cym - hh / 2, cxm + ww / 2, cym + hh / 2)

    def _pol_out(pts, k=1.10):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cxm, cym = sum(xs) / len(xs), sum(ys) / len(ys)
        return [(cxm + (x - cxm) * k, cym + (y - cym) * k) for x, y in pts]

    def _bezier(p0, p1, p2, n=28):
        pts = []
        for i in range(n + 1):
            t = i / n
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
            pts.append((x, y))
        return pts

    def _tapered(pts, w0, w1):
        """Poligono de espesor variable a lo largo de una curva (cola afilada)."""
        poly = []
        n = len(pts)
        for i in range(n):
            x, y = pts[i]
            dx = pts[min(i + 1, n - 1)][0] - pts[max(i - 1, 0)][0]
            dy = pts[min(i + 1, n - 1)][1] - pts[max(i - 1, 0)][1]
            L = math.hypot(dx, dy) or 1e-6
            nx, ny = -dy / L, dx / L
            wr = w0 + (w1 - w0) * (i / (n - 1))
            poly.append((x + nx * wr, y + ny * wr))
        for i in range(n - 1, -1, -1):
            x, y = pts[i]
            dx = pts[min(i + 1, n - 1)][0] - pts[max(i - 1, 0)][0]
            dy = pts[min(i + 1, n - 1)][1] - pts[max(i - 1, 0)][1]
            L = math.hypot(dx, dy) or 1e-6
            nx, ny = -dy / L, dx / L
            wr = w0 + (w1 - w0) * (i / (n - 1))
            poly.append((x - nx * wr, y - ny * wr))
        return poly

    # ---- 1) cola: gruesa, curvada hacia arriba-izquierda, afilada (sin espinas) ----
    t_len = 0.50 if baby else 0.72
    t_hi = 0.40 if baby else 0.52
    spine = _bezier(
        (cx - body_rx * 0.7, body_cy + body_ry * 0.2),
        (cx - w * 0.52, body_cy + body_ry * 0.55),
        (cx - w * t_len, base - h * t_hi), 28)
    tail_poly = _tapered(spine, w * 0.11, w * 0.018)
    d.polygon(_pol_out(tail_poly, 1.08), fill=OUTLINE)
    d.polygon(tail_poly, fill=body_c)

    # ---- 2) cuerpo (torax ancho y bajo) ----
    bb = (cx - body_rx, body_cy - body_ry, cx + body_rx, body_cy + body_ry)
    d.ellipse(_ell_out(bb, 1.10), fill=OUTLINE)
    d.ellipse(bb, fill=body_c)
    # barriga clara
    d.ellipse((cx - body_rx * 0.42, body_cy + body_ry * 0.05,
               cx + body_rx * 0.42, body_cy + body_ry * 0.95), fill=belly_c)

    # ---- 3) bracitos T-rex (cortos, a los lados, apuntando abajo) ----
    for s in (-1, 1):
        ax = cx + s * (body_rx + w * 0.06)
        ay = body_cy + body_ry * 0.10 + bob
        ab = (min(ax, ax + s * w * 0.10), ay,
              max(ax, ax + s * w * 0.10), ay + 11)
        d.ellipse(_ell_out(ab, 1.20), fill=OUTLINE)
        d.ellipse(ab, fill=body_c)
        # garra (una linea)
        d.line((ax + s * w * 0.05, ay + 12, ax + s * w * 0.05, ay + 16),
               fill=OUTLINE, width=2)

    # ---- 4) patas (dos, con tres dedos) ----
    for fx in (cx - w * 0.14, cx + w * 0.14):
        fb = (fx - w * 0.09, base - h * 0.10, fx + w * 0.09, base + 2)
        d.rounded_rectangle(_ell_out(fb, 1.16), radius=6, fill=OUTLINE)
        d.rounded_rectangle(fb, radius=6, fill=body_c)
        # tres dedos
        for dxo in (-w * 0.05, 0, w * 0.05):
            d.line((fx + dxo - 1, base - 1, fx + dxo - 1, base + 4),
                   fill=OUTLINE, width=2)

    # ---- 5) cabeza (circulo grande frontal) ----
    hb = (cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r)
    d.ellipse(_ell_out(hb, 1.08), fill=OUTLINE)
    d.ellipse(hb, fill=body_c)

    # ---- 6) hocico claro (sobresale de la cabeza, mandíbula Agumon) ----
    sn_x0 = cx - head_r * 0.72
    sn_x1 = cx + head_r * 0.72
    sn_y0 = head_cy + head_r * 0.22
    sn_y1 = head_cy + head_r * 1.22
    sbb = (sn_x0, sn_y0 + bob, sn_x1, sn_y1 + bob)
    d.rounded_rectangle(_ell_out(sbb, 1.10), radius=10, fill=OUTLINE)
    d.rounded_rectangle(sbb, radius=10, fill=belly_c)
    # fosas nasales (dos puntitos)
    d.ellipse((sn_x0 + 6, sn_y0 + 5 + bob, sn_x0 + 10, sn_y0 + 9 + bob),
              fill=(120, 110, 90))
    d.ellipse((sn_x1 - 10, sn_y0 + 5 + bob, sn_x1 - 6, sn_y0 + 9 + bob),
              fill=(120, 110, 90))

    # ---- boca (línea ancha con dientes, en la mandíbula) ----
    my = sn_y0 + (sn_y1 - sn_y0) * 0.40
    mx0, mx1 = sn_x0 + 7, sn_x1 - 7
    chew = state == "eat" and math.sin(phase * math.tau * 2) > 0
    if state == "sick":
        d.line((mx0 + 2, my + bob, mx1 - 2, my + bob), fill=OUTLINE, width=2)
    elif state in ("happy",) or chew:
        # boca abierta con dientecitos
        d.arc((mx0, my - 2 + bob, mx1, my + 9 + bob), 0, 180, fill=OUTLINE, width=2)
        d.polygon([(mx0 + 6, my + 1 + bob), (mx0 + 11, my + 1 + bob),
                   (mx0 + 8, my + 7 + bob)], fill=(255, 255, 255), outline=OUTLINE, width=1)
        d.polygon([(mx1 - 11, my + 1 + bob), (mx1 - 6, my + 1 + bob),
                   (mx1 - 8, my + 7 + bob)], fill=(255, 255, 255), outline=OUTLINE, width=1)
        d.polygon([(cx - 3, my + 1 + bob), (cx + 2, my + 1 + bob),
                   (cx - 1, my + 7 + bob)], fill=(255, 255, 255), outline=OUTLINE, width=1)
    elif state == "sleep":
        d.ellipse((cx - 3, my - 1 + bob, cx + 3, my + 2 + bob), fill=(130, 70, 60))
    elif stage == "adult" and quality == "bad":
        d.arc((mx0, my - 2 + bob, mx1, my + 6 + bob), 20, 160, fill=OUTLINE, width=2)
        d.polygon([(cx - 4, my + 2 + bob), (cx + 1, my + 2 + bob),
                   (cx - 2, my + 8 + bob)], fill=(255, 255, 255), outline=OUTLINE, width=1)
    else:
        # línea de boca cerrada
        d.line((mx0 + 3, my + bob, mx1 - 3, my + bob), fill=OUTLINE, width=2)

    # ---- ojos (dos, simétricos, arriba en la cabeza) ----
    er = head_r * 0.30
    for s in (-1, 1):
        ex = cx + s * head_r * 0.42
        ey = head_cy - head_r * 0.20
        if state == "blink":
            d.line((ex - er, ey + bob, ex + er, ey + bob), fill=OUTLINE, width=3)
        elif state in ("happy", "eat"):
            d.arc((ex - er, ey - er + bob, ex + er, ey + er + bob), 200, 340,
                  fill=OUTLINE, width=3)
        elif state == "sleep":
            d.arc((ex - er, ey - er + bob, ex + er, ey + er + bob), 20, 160,
                  fill=OUTLINE, width=3)
        elif state == "sick":
            d.line((ex - er, ey - er + bob, ex + er, ey + er + bob), fill=OUTLINE, width=3)
            d.line((ex - er, ey + er + bob, ex + er, ey - er + bob), fill=OUTLINE, width=3)
        else:  # idle
            d.ellipse((ex - er, ey - er + bob, ex + er, ey + er + bob),
                      fill=(255, 255, 255, 255), outline=OUTLINE, width=2)
            pup = er * 0.5
            d.ellipse((ex - pup * 0.2, ey - pup * 0.2 + bob, ex + pup * 0.8,
                       ey + pup * 0.8 + bob), fill=(42, 66, 70, 255))
            d.ellipse((ex - pup * 0.55, ey - pup * 0.55 + bob, ex - pup * 0.05,
                       ey - pup * 0.05 + bob), fill=(255, 255, 255, 255))
    # ceja fruncida (adulto malo)
    if stage == "adult" and quality == "bad" and state not in ("sleep", "sick"):
        for s in (-1, 1):
            ex = cx + s * head_r * 0.42
            ey = head_cy - head_r * 0.20
            d.line((ex - er - 2, ey - er - 4 + bob, ex + er * 0.4, ey - er + 2 + bob),
                   fill=OUTLINE, width=3)
    # mejillas
    ck = pal["cheek"]
    for s in (-1, 1):
        d.ellipse((cx + s * head_r * 0.80 - 3, head_cy + head_r * 0.34 + bob,
                   cx + s * head_r * 0.80 + 6, head_cy + head_r * 0.34 + 7 + bob),
                  fill=ck)

    # gota de sudor si esta enfermo
    if state == "sick":
        d.ellipse((cx + head_r * 0.55, head_cy - head_r * 1.05 + bob,
                   cx + head_r * 0.55 + 6, head_cy - head_r * 1.05 + 6 + bob),
                  fill=(150, 200, 240, 255), outline=OUTLINE, width=1)
    return img


def _render_egg(phase, peck):
    w, h = 64, 78
    pad = 16
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = (w + pad * 2) / 2, pad + h
    top = pad + 4
    pal = PALETTES["egg"]
    d.ellipse((pad, top, pad + w, top + h), fill=pal["body"], outline=OUTLINE, width=3)
    # moteado
    for sx, sy, sr in ((0.30, 0.35, 3), (0.68, 0.30, 2.5), (0.55, 0.62, 3.5),
                       (0.38, 0.75, 2), (0.72, 0.72, 2.5)):
        d.ellipse((cx + (sx - 0.5) * w - sr, top + sy * h - sr,
                   cx + (sx - 0.5) * w + sr, top + sy * h + sr), fill=pal["spot"])
    if peck or phase > 0.3:  # grietas al empollar
        cr = pal["crack"]
        d.line((cx - 8, top + h * 0.55, cx + 2, top + h * 0.62), fill=cr, width=2)
        d.line((cx + 2, top + h * 0.62, cx - 2, top + h * 0.72), fill=cr, width=2)
        d.line((cx + 6, top + h * 0.48, cx - 1, top + h * 0.56), fill=cr, width=2)
    if peck:
        d.polygon([(cx - 5, top + h * 0.55), (cx + 5, top + h * 0.55),
                   (cx, top + h * 0.55 + 8)], fill=(255, 190, 60, 255),
                  outline=OUTLINE, width=1)
    return img


def _render_ghost(phase):
    w, h = 84, 96
    pad = 14
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, top = (w + pad * 2) / 2, pad
    body = PALETTES["ghost"]["body"]
    bob = math.sin(phase * math.tau) * 3
    top += bob
    # halo
    d.ellipse((cx - 8, top - 12, cx + 8, top + 4), fill=(255, 224, 130, 255),
              outline=OUTLINE, width=1)
    d.rounded_rectangle((pad, top, pad + w, top + h - 6), radius=22, fill=body,
                        outline=OUTLINE, width=3)
    n = 4
    seg = w / n
    yb = top + h - 6
    for i in range(n):
        x0 = pad + seg * i + 1
        x1 = pad + seg * (i + 1) - 1
        d.ellipse((x0, yb - 4, x1, yb + 12), fill=body, outline=OUTLINE, width=2)
    for side in (-1, 1):
        ex = cx + side * 16
        d.ellipse((ex - 6, top + 30, ex + 6, top + 42), fill=(60, 56, 60, 255))
    d.ellipse((cx - 5, top + 48, cx + 5, top + 56), fill=(60, 56, 60, 255))
    return img


# ---------------------------------------------------------------- ducha
def render_mampara():
    """Panel de ducha translúcido (RGBA) para el estado 'bathing'."""
    x0, y0, x1, y1 = 0, 0, 112, 110
    img = Image.new("RGBA", (x1, y1), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # cristal
    d.rounded_rectangle((6, 10, x1 - 6, y1 - 4), radius=10,
                        fill=(175, 215, 240, 55), outline=(215, 240, 255, 170), width=2)
    # brillo diagonal
    d.line((20, 14, 60, 100), fill=(255, 255, 255, 70), width=3)
    # barra de ducha + cabezal
    d.line((14, 6, x1 - 14, 6), fill=(190, 210, 225, 200), width=2)
    d.ellipse((x1 // 2 - 9, 0, x1 // 2 + 9, 12), fill=(210, 228, 240, 230),
              outline=(150, 175, 195, 255), width=2)
    # chorritos del cabezal
    d.line((x1 // 2 - 4, 12, x1 // 2 - 4, 22), fill=(170, 210, 235, 200), width=2)
    d.line((x1 // 2 + 4, 12, x1 // 2 + 4, 22), fill=(170, 210, 235, 200), width=2)
    return img


# ---------------------------------------------------------------- extras
def render_status_row(hunger, happiness, hygiene, energy):
    """Tira RGBA con 4 iconos + barra de 5 segmentos (para pegar en la pantalla)."""
    items = [("heart", hunger), ("smiley", happiness), ("drop", hygiene), ("moon", energy)]
    strip = Image.new("RGBA", (268, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    x = 0
    for icon, val in items:
        _status_icon(d, x + 7, 8, icon)
        segs = max(0, min(5, int(round(val / 20))))
        col = (232, 90, 90) if val < 30 else ((240, 190, 70) if val < 60 else (110, 190, 120))
        for s in range(5):
            sx = x + 18 + s * 9
            filled = s < segs
            d.rounded_rectangle((sx, 3, sx + 6, 13), radius=2,
                                fill=col if filled else (72, 70, 64),
                                outline=(52, 50, 46) if not filled else None)
        x += 67
    return strip


def _status_icon(d, cx, cy, kind):
    if kind == "heart":
        d.ellipse((cx - 5, cy - 5, cx - 1, cy - 1), fill=(235, 90, 110))
        d.ellipse((cx + 1, cy - 5, cx + 5, cy - 1), fill=(235, 90, 110))
        d.polygon([(cx - 5, cy - 2), (cx + 5, cy - 2), (cx, cy + 5)],
                  fill=(235, 90, 110))
    elif kind == "smiley":
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(255, 190, 60),
                  outline=(150, 110, 30), width=1)
        d.ellipse((cx - 3, cy - 3, cx - 1, cy - 1), fill=(90, 70, 60))
        d.ellipse((cx + 1, cy - 3, cx + 3, cy - 1), fill=(90, 70, 60))
        d.arc((cx - 3, cy - 1, cx + 3, cy + 3), 20, 160, fill=(90, 70, 60), width=1)
    elif kind == "drop":
        d.ellipse((cx - 4, cy - 2, cx + 4, cy + 5), fill=(110, 170, 235))
        d.polygon([(cx - 4, cy - 1), (cx + 4, cy - 1), (cx, cy - 7)],
                  fill=(110, 170, 235))
    elif kind == "moon":
        d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(120, 140, 200))
        d.ellipse((cx + 2, cy - 6, cx + 7, cy + 4), fill=(255, 248, 230, 255))


def render_particle(kind, frame):
    """Partículas pequeñas RGBA: heart, bubble, zzz, sweat, sparkle, food, poo,
    fly (mosca), stink (olor), drop (gota)."""
    img = Image.new("RGBA", (26, 26), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = 13, 13
    if kind == "heart":
        s = 8
        d.ellipse((cx - s / 2, cy - s / 2, cx - 1, cy - 1), fill=(240, 100, 120, 255))
        d.ellipse((cx + 1, cy - s / 2, cx + s / 2, cy - 1), fill=(240, 100, 120, 255))
        d.polygon([(cx - s / 2, cy - 2), (cx + s / 2, cy - 2), (cx, cy + s * 0.62)],
                  fill=(240, 100, 120, 255))
    elif kind == "bubble":
        r = 6 + (frame % 3)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(150, 200, 240, 255), width=2)
        d.ellipse((cx - r + 2, cy - r + 2, cx - r + 4, cy - r + 4),
                  fill=(255, 255, 255, 220))
    elif kind == "zzz":
        f = _font(12, True)
        d.text((cx - 4, cy - 8), "Z", font=f, fill=(120, 140, 200, 255))
        d.text((cx + 4, cy - 1), "z", font=_font(9, True), fill=(150, 165, 215, 255))
    elif kind == "sweat":
        d.ellipse((cx - 4, cy - 1, cx + 4, cy + 6), fill=(150, 200, 240, 255))
        d.polygon([(cx - 4, cy), (cx + 4, cy), (cx, cy - 8)], fill=(150, 200, 240, 255))
    elif kind == "drop":
        d.ellipse((cx - 3, cy - 1, cx + 3, cy + 6), fill=(120, 185, 240, 255))
        d.polygon([(cx - 3, cy), (cx + 3, cy), (cx, cy - 7)], fill=(120, 185, 240, 255))
    elif kind == "fly":
        # mosca: cuerpo + alas
        wob = math.sin(frame * 1.8) * 1.5
        d.ellipse((cx - 3, cy - 2 + wob, cx + 3, cy + 2 + wob), fill=(70, 62, 66, 255))
        d.ellipse((cx - 6, cy - 4 + wob, cx - 2, cy - 1 + wob), fill=(215, 225, 235, 210))
        d.ellipse((cx + 2, cy - 4 + wob, cx + 6, cy - 1 + wob), fill=(215, 225, 235, 210))
    elif kind == "stink":
        # nube de olor verdosa
        off = frame % 4
        for ox, oy, r in ((cx - 4 + off, cy - 2, 6), (cx + 3 - off, cy + 1, 5),
                          (cx, cy - 6, 4)):
            d.ellipse((ox - r, oy - r, ox + r, oy + r), fill=(168, 196, 148, 130))
        d.ellipse((cx - 2, cy - 1, cx + 5, cy + 4), fill=(150, 180, 132, 150))
    elif kind == "sparkle":
        for ang in (0, math.pi / 2):
            pts = []
            for i in range(4):
                a = ang + math.pi / 2 * i
                pts.append((cx + 8 * math.cos(a), cy + 8 * math.sin(a)))
                pts.append((cx + 2.5 * math.cos(a + math.pi / 4),
                            cy + 2.5 * math.sin(a + math.pi / 4)))
            d.polygon(pts, fill=(255, 213, 79, 255))
    elif kind == "food":
        s = 9
        pts = [(cx, cy - s), (cx - s, cy + s * 0.8), (cx + s, cy + s * 0.8)]
        d.polygon(pts, fill=(255, 255, 255, 255), outline=(52, 84, 92, 255))
        d.rounded_rectangle((cx - s + 1, cy - s + 1, cx + s - 1, cy - s + 4), radius=2,
                            fill=(58, 52, 46, 255))
    elif kind == "poo":
        d.ellipse((cx - 8, cy + 2, cx + 8, cy + 10), fill=(141, 110, 99, 255),
                  outline=(52, 84, 92, 255), width=1)
        d.ellipse((cx - 6, cy - 3, cx + 6, cy + 5), fill=(141, 110, 99, 255),
                  outline=(52, 84, 92, 255), width=1)
        d.ellipse((cx - 4, cy - 8, cx + 4, cy), fill=(141, 110, 99, 255),
                  outline=(52, 84, 92, 255), width=1)
    return img


def render_hint(text, dark=False):
    """Texto RGBA para la pantalla (pista de botón / mensaje). LCD oscuro."""
    f = _font(13, True)
    img = Image.new("RGBA", (260, 18), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((130, 0), text, font=f,
           fill=(235, 224, 200, 255) if not dark else (255, 255, 255, 255),
           anchor="ma")
    return img


def render_age_text(text):
    f = _font(11, True)
    img = Image.new("RGBA", (200, 14), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((0, 0), text, font=f, fill=(205, 195, 175, 255))
    return img


def render_glow(cx, cy, r, pressed=False):
    """Overlay de hover/press para botones (RGBA)."""
    img = Image.new("RGBA", (r * 2 + 10, r * 2 + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = (255, 255, 255, 70) if not pressed else (60, 40, 40, 60)
    d.ellipse((4, 4, r * 2 + 6, r * 2 + 6), outline=col, width=3 if not pressed else 2)
    if pressed:
        d.ellipse((7, 7, r * 2 + 3, r * 2 + 3), fill=(60, 40, 40, 40))
    return img


def format_age(minutes):
    if minutes < 1:
        return f"{int(minutes * 60)}s"
    if minutes < 1440:
        return f"{int(minutes // 60)}m {int(minutes % 60):02d}s"
    return f"{int(minutes // 1440)}d {int((minutes % 1440) // 60):02d}h"


def render_preview(stage="baby", state="idle", quality="good", out="preview.png"):
    """Vista estática completa del dispositivo (para iterar el diseño)."""
    img = render_shell()
    pet = render_pet(stage, quality, state, phase=0.0)
    px, py = PET_ANCHOR[0] - pet.width // 2, PET_BOTTOM - pet.height
    img.paste(pet, (px, py), pet)
    strip = render_status_row(62, 74, 88, 55)
    img.paste(strip, STATUS_POS, strip)
    age = render_age_text(f"{'Huevo' if stage=='egg' else 'Bebé'} · 0m 12s")
    img.paste(age, TEXT_AGE, age)
    img.save(out)
    return out


def preview_with_background(stage="baby", state="idle", quality="good", out="preview.png"):
    """Igual que render_preview pero sustituye el magenta por gris (para revisar)."""
    p = render_preview(stage, state, quality, out)
    img = Image.open(p).convert("RGB")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            if px[x, y] == MAGENTA:
                px[x, y] = (70, 78, 92)
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    img.save(out)
    return out


if __name__ == "__main__":
    import sys
    stage = sys.argv[1] if len(sys.argv) > 1 else "baby"
    state = sys.argv[2] if len(sys.argv) > 2 else "idle"
    quality = sys.argv[3] if len(sys.argv) > 3 else "good"
    out = sys.argv[4] if len(sys.argv) > 4 else "preview.png"
    print(preview_with_background(stage, state, quality, out))
