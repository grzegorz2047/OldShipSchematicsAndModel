"""Turn the rendered line layers into the step pictures of the drawing tutorial.

    python compose_steps.py --layers build/layers --out ../steps [--lang en,pl] [--width 1800]

For each view and language it writes
    <out>/<lang>/<view>-step-01.png ... -step-09.png   (09 = bonus: set sails)
and language-free helper pictures in <out>/../build/extra (used by build_pdf.py):
    <view>-final.png, <view>-outline.png, <view>-sails-final.png, <view>-mistake-*.png

Colours: new lines black, earlier lines light blue, construction lines orange and dashed.
"""
import argparse, json, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import find_font, LABELS

NEW = (0, 0, 0)
OLD = (140, 182, 228)
GUIDE = (226, 104, 28)
GUIDE_OLD = (244, 196, 160)
SHADE = (70, 70, 70)
REFL = (105, 105, 105)
WATER = (120, 120, 120)

VIEWS = ['side', 'bow', 'stern']
GS = 1.0   # set per view in compose_view: picture width / 1400
STATE_STEPS = {3: 'hull', 4: 'masts', 5: 'yards', 6: 'rigging', 7: 'details'}


# ------------------------------------------------------------------ small helpers
def load_alpha(path, size=None):
    if not os.path.exists(path):          # a layer with no lines at all is not written
        return np.zeros((1, 1), np.float32)
    im = Image.open(path)
    a = np.asarray(im.split()[-1], dtype=np.float32) / 255.0 if im.mode in ('RGBA', 'LA') else \
        1.0 - np.asarray(im.convert('L'), dtype=np.float32) / 255.0
    return a

def blend(canvas, alpha, color, strength=1.0):
    if alpha.shape[:2] != canvas.shape[:2]:
        if alpha.size == 1:
            return
        alpha = np.asarray(Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8)).resize(
            (canvas.shape[1], canvas.shape[0]), Image.LANCZOS), np.float32) / 255
    a = np.clip(alpha * strength, 0, 1)[..., None]
    canvas[:] = canvas * (1 - a) + np.array(color, np.float32) * a

def clip_segment(p, q, w, h, pad=0):
    """Liang-Barsky clip of segment p-q to the rectangle [-pad, w+pad] x [-pad, h+pad]."""
    x0, y0 = p; x1, y1 = q
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, x0 + pad), (dx, w + pad - x0), (-dy, y0 + pad), (dy, h + pad - y0)):
        if pp == 0:
            if qq < 0:
                return None
        else:
            t = qq / pp
            if pp < 0:
                if t > t1: return None
                t0 = max(t0, t)
            else:
                if t < t0: return None
                t1 = min(t1, t)
    return (x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)

def dashed(draw, pts, color, width, dash=18, gap=10, closed=False, W=None, H=None, pattern=None):
    pts = list(pts)
    if closed:
        pts = pts + [pts[0]]
    pattern = [v * GS for v in (pattern or [dash, gap])]
    width = max(1, round(width * GS))
    for a, b in zip(pts[:-1], pts[1:]):
        seg = clip_segment(a, b, W, H, 20) if W else (a, b)
        if not seg:
            continue
        (x0, y0), (x1, y1) = seg
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-6:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        t = 0.0; k = 0
        while t < L:
            seglen = pattern[k % len(pattern)]
            if k % 2 == 0:
                e = min(L, t + seglen)
                draw.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e)], fill=color, width=width)
            t += seglen; k += 1

def solid(draw, pts, color, width, closed=False):
    pts = [tuple(p) for p in pts]
    if closed:
        pts.append(pts[0])
    draw.line(pts, fill=color, width=max(1, round(width * GS)), joint='curve')

def label(draw, xy, text, font, color, anchor='lm', halo=(255, 255, 255)):
    draw.text(xy, text, font=font, fill=color, anchor=anchor, stroke_width=max(2, round(3 * GS)), stroke_fill=halo)


# ------------------------------------------------------------------ guides
class Guides:
    def __init__(self, layers, view, W, H):
        with open(os.path.join(layers, view + '_guides.json'), encoding='utf-8') as f:
            self.g = json.load(f)
        self.view = view; self.W = W; self.H = H
        self.items = self.g['items']
        self.n = self.g['numbers']

    def of(self, step, role=None):
        return [it for it in self.items if it['step'] == step and (role is None or it['role'] == role)]


def draw_guides(img, G, step, current, lang, font, extent):
    """Draw the construction lines that belong to `step`.
    current=True: strong orange; False: pale (left over from earlier steps)."""
    W, H = img.size
    d = ImageDraw.Draw(img)
    col = GUIDE if current else GUIDE_OLD
    lw = 3 if current else 2
    T = LABELS[lang]
    if step == 1:
        # grid (side view) or picture frame grid (oblique views)
        if G.view == 'side':
            for it in G.of(1, 'grid'):
                dashed(d, it['pts'], col, max(1, lw - 1), 10, 8, W=W, H=H)
        else:
            x0, y0, x1, y1 = extent
            for i in range(1, 4):
                x = x0 + (x1 - x0) * i / 4
                dashed(d, [(x, y0), (x, y1)], col, max(1, lw - 1), 10, 8, W=W, H=H)
            for j in range(1, 4):
                y = y0 + (y1 - y0) * j / 4
                dashed(d, [(x0, y), (x1, y)], col, max(1, lw - 1), 10, 8, W=W, H=H)
        x0, y0, x1, y1 = extent
        if G.view != 'side':
            dashed(d, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], col, lw, 22, 10, closed=True, W=W, H=H)
        for it in G.of(1, 'mark'):
            solid(d, it['pts'], col, lw + 2)
        for it in G.of(1, 'dot'):
            x, y = it['pts'][0]
            r = (9 if current else 7) * GS
            d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=round(lw * GS))
        # vanishing point(s) on the horizon
        hz = G.n['horizon_y']
        for name, vp in G.n['vps'].items():
            draw_vp(d, vp, hz, col, lw, W, H, font if current else None, T['vp'])
        if current:
            label(d, (extent[0] + 16 * GS, hz - 30 * GS), T['horizon'], font, (0, 0, 0), anchor='lm')
    if step == 2:
        for it in G.of(2, 'block'):
            dashed(d, it['pts'], col, lw, 16, 9, closed=it['closed'], W=W, H=H)
        for it in G.of(2, 'axis'):
            dashed(d, it['pts'], col, lw, 26, 8, W=W, H=H, pattern=[26, 7, 4, 7])
        if current and G.n['vps']:
            for a, b in G.n['vp_lines']:
                dashed(d, [a, b], col, 2, 5, 7, W=W, H=H)
            for name, vp in G.n['vps'].items():
                draw_vp(d, vp, G.n['horizon_y'], col, lw, W, H, font, T['vp'])
    if step in (4, 5, 6, 7, 9):
        for it in G.of(step):
            if it['kind'] == 'cross':
                solid(d, it['pts'], col, lw + 1)
            elif it['role'] == 'axis':
                dashed(d, it['pts'], col, lw, 26, 8, closed=it['closed'], W=W, H=H, pattern=[26, 7, 4, 7])
            else:
                dashed(d, it['pts'], col, lw, 16, 9, closed=it['closed'], W=W, H=H)


def draw_vp(d, vp, hz, col, lw, W, H, font, text):
    x, y = vp
    if -5 <= x <= W + 5:
        r = 14 * GS; w = round(lw * GS)
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=w)
        d.line([(x - r - 8 * GS, y), (x + r + 8 * GS, y)], fill=col, width=w)
        d.line([(x, y - r - 8 * GS), (x, y + r + 8 * GS)], fill=col, width=w)
        if font:
            label(d, (x + 10 * GS, y - 36 * GS), text, font, col, anchor='lm')
    else:
        # off the page: arrow at the edge
        xe = W - 12 * GS if x > W else 12 * GS
        s = 1 if x > W else -1
        d.polygon([(xe, y), (xe - s * 34 * GS, y - 16 * GS), (xe - s * 34 * GS, y + 16 * GS)], fill=col)
        if font:
            if s > 0:
                label(d, (xe - 6 * GS, y - 36 * GS), text + ' →', font, col, anchor='rm')
            else:
                label(d, (xe + 6 * GS, y - 36 * GS), '← ' + text, font, col, anchor='lm')


# ------------------------------------------------------------------ shading, reflection, water
def hatch_layer(W, H, spacing, angle_deg, width):
    im = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(im)
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    nx, ny = -dy, dx
    diag = math.hypot(W, H)
    cx, cy = W / 2, H / 2
    k = -diag
    while k < diag:
        px, py = cx + nx * k, cy + ny * k
        d.line([(px - dx * diag, py - dy * diag), (px + dx * diag, py + dy * diag)], fill=255, width=width)
        k += spacing
    return np.asarray(im, np.float32) / 255.0

def shading(shade_path, W, H, scale, soft=None):
    """soft: optional mask (0..1) of areas that get only light single hatching (the sails)."""
    im = Image.open(shade_path).convert('RGBA').resize((W, H), Image.LANCZOS)
    a = np.asarray(im.split()[3], np.float32) / 255.0
    L = np.asarray(im.convert('L').filter(ImageFilter.GaussianBlur(2 * scale)), np.float32) / 255.0
    solid_mask = (a > 0.6)
    # erode a little so hatching stays inside the outlines
    m = Image.fromarray((solid_mask * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5))
    m = np.asarray(m, np.float32) / 255.0
    sp = max(6, int(11 * scale))
    h1 = hatch_layer(W, H, sp, -55, max(1, int(round(1.6 * scale))))
    h2 = hatch_layer(W, H, sp, 35, max(1, int(round(1.6 * scale))))
    mid = (L < 0.50).astype(np.float32)
    dark = (L < 0.30).astype(np.float32)
    # clean tiny islands
    mid = np.asarray(Image.fromarray((mid * 255).astype(np.uint8)).filter(ImageFilter.ModeFilter(7)), np.float32) / 255
    dark = np.asarray(Image.fromarray((dark * 255).astype(np.uint8)).filter(ImageFilter.ModeFilter(7)), np.float32) / 255
    if soft is not None:
        dark = dark * (1 - soft)
        mid = mid * (1 - 0.45 * soft)
    out = np.clip(h1 * mid * 0.85 + h2 * dark * 0.5, 0, 1) * m
    return out, a

def reflection(refl_path, W, H, water_y, scale, seed=3):
    a = load_alpha(refl_path)
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS), np.float32) / 255
    a = a[::-1, :].copy()                          # mirror camera -> reflection
    # thicken a bit, then cut into wavy horizontal dashes
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)), np.float32) / 255
    rng = random.Random(seed)
    out = np.zeros_like(a)
    band = max(3, int(6 * scale))
    y = int(water_y)
    while y < H:
        shift = rng.randint(-int(5 * scale), int(5 * scale))
        if rng.random() < 0.72:
            rows = a[y:y + band - 1]
            out[y:y + band - 1] = np.roll(rows, shift, axis=1)
        y += band
    # random gaps along each band
    gaps = Image.new('L', (W, H), 255)
    d = ImageDraw.Draw(gaps)
    for _ in range(int(900 * scale * scale)):
        x0 = rng.randint(0, W); y0 = rng.randint(int(water_y), H)
        d.line([(x0, y0), (x0 + rng.randint(10, 60) * scale, y0)], fill=0, width=max(2, int(4 * scale)))
    out *= np.asarray(gaps, np.float32) / 255
    rows = np.arange(H, dtype=np.float32)[:, None]
    fade = np.clip(1.0 - (rows - water_y) / (H - water_y + 1), 0, 1) ** 1.3
    out *= fade * 0.75
    out[:int(water_y)] = 0
    return out

def water_strokes(draw, extent, water_y, W, H, scale, rng, ship_x):
    x0, y0, x1, y1 = extent
    for i in range(26):
        yy = water_y + rng.uniform(4, (H - water_y) * 0.85)
        spread = (yy - water_y) / max(1, (H - water_y))
        L = rng.uniform(60, 220) * scale * (0.6 + spread)
        side = rng.choice([-1, 1])
        if side < 0:
            xs = rng.uniform(x0 - 260 * scale, ship_x[0] + 40 * scale)
        else:
            xs = rng.uniform(ship_x[1] - 40 * scale - L, x1 + 200 * scale)
        draw.line([(xs, yy), (xs + L, yy)], fill=WATER, width=max(1, int(2 * scale)))


# ------------------------------------------------------------------ one view
def compose_view(layers, view, out_dir, extra_dir, langs, out_w):
    lay = lambda name: os.path.join(layers, '%s_%s.png' % (view, name))
    sample = Image.open(lay('all'))
    W, H = sample.size
    scale = W / 2400.0
    global GS
    GS = W / 1400.0
    G = Guides(layers, view, W, H)
    all_a = load_alpha(lay('all'))
    ys, xs = np.nonzero(all_a > 0.3)
    ext = (float(xs.min()) - 10, float(ys.min()) - 10, float(xs.max()) + 10, float(G.n['horizon_y']))
    # frame bottom: the waterline at the lowest point of the hull
    water_pts = G.of(1, 'water')[0]['pts']
    hull_a = load_alpha(lay('hull_new'))
    hy, hx = np.nonzero(hull_a > 0.3)
    water_y = float(hy.max())
    ext = (ext[0], ext[1], ext[2], water_y + 4)
    ship_x = (float(hx.min()), float(hx.max()))
    hz = G.n['horizon_y']

    shade_a, mask_a = shading(lay('shade'), W, H, scale)
    _a0 = np.asarray(Image.open(lay('shade')).convert('RGBA').resize((W, H)).split()[3], np.float32) / 255
    _a1 = np.asarray(Image.open(lay('shade_sails')).convert('RGBA').resize((W, H)).split()[3], np.float32) / 255
    sail_region = np.clip(_a1 - _a0, 0, 1)
    shade_s, mask_s = shading(lay('shade_sails'), W, H, scale, soft=sail_region)
    refl = reflection(lay('refl'), W, H, water_y, scale)
    refl_s = reflection(lay('refl_sails'), W, H, water_y, scale)
    mask_full = np.maximum(mask_a, all_a)
    mask_full = np.asarray(Image.fromarray((np.clip(mask_full, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)), np.float32) / 255

    def canvas():
        return np.full((H, W, 3), 255.0, np.float32)

    # columns where the hull hides the horizon: hull lines both above and below it
    band = int(40 * scale)
    hzi = int(round(hz))
    above = (hull_a[max(0, hzi - 400):max(0, hzi - 2)] > 0.3).any(axis=0)
    below = (hull_a[hzi + 2:hzi + 400] > 0.3).any(axis=0)
    hidden = (above & below).astype(np.float32)
    hidden = np.convolve(hidden, np.ones(5) / 5, mode='same') > 0.01

    def horizon_layer(masked):
        im = Image.new('L', (W, H), 0)
        ImageDraw.Draw(im).line([(0, hz), (W, hz)], fill=255, width=max(2, int(2.4 * scale)))
        a = np.asarray(im, np.float32) / 255
        if masked:
            a = a * (1 - hidden[None, :])
        return a

    def finish(c, guides_fn=None):
        img = Image.fromarray(np.clip(c, 0, 255).astype(np.uint8))
        if guides_fn:
            guides_fn(img)
        return img

    results = {}
    for lang in langs:
        font = find_font(int(46 * scale), bold=True)
        steps = []
        # step 1: horizon, frame, grid, marks
        c = canvas()
        blend(c, horizon_layer(False), NEW)
        img = finish(c)
        draw_guides(img, G, 1, True, lang, font, ext)
        # waterline guide in strong dashes
        d = ImageDraw.Draw(img)
        dashed(d, water_pts, NEW, 3, 30, 10, W=W, H=H)
        label(d, (ext[0] - 10 * GS, water_y + 34 * GS), LABELS[lang]['waterline'], font, NEW, anchor='lm')
        steps.append(img)
        # step 2: blocks and axes
        c = canvas(); blend(c, horizon_layer(False), OLD)
        img = finish(c)
        draw_guides(img, G, 1, False, lang, font, ext)
        dashed(ImageDraw.Draw(img), water_pts, OLD, 3, 30, 10, W=W, H=H)
        draw_guides(img, G, 2, True, lang, font, ext)
        steps.append(img)
        # steps 3..7: layers
        for k in range(3, 8):
            st = STATE_STEPS[k]
            c = canvas()
            blend(c, horizon_layer(True), OLD)
            img = finish(c)
            # pale guides of the earlier step that still help, then this step's guides
            if k == 3:
                draw_guides(img, G, 2, False, lang, font, ext)
            if k == 4:
                draw_guides(img, G, 2, False, lang, None, ext) if False else None
            c = np.asarray(img, np.float32).copy()
            blend(c, load_alpha(lay(st + '_old')), OLD)
            img = finish(c)
            if k in (4, 5, 6, 7):
                if k == 4:
                    # the mast axes from step 2 are this step's main guide
                    d = ImageDraw.Draw(img)
                    for it in G.of(2, 'axis'):
                        dashed(d, it['pts'], GUIDE, 3, 26, 8, W=W, H=H, pattern=[26, 7, 4, 7])
                draw_guides(img, G, k, True, lang, font, ext)
            c = np.asarray(img, np.float32).copy()
            blend(c, load_alpha(lay(st + '_new')), NEW)
            steps.append(Image.fromarray(np.clip(c, 0, 255).astype(np.uint8)))
        # step 8: ink, shade, reflect
        c = canvas()
        blend(c, refl, REFL)
        blend(c, horizon_layer(True), NEW, 0.8)
        img = finish(c)
        water_strokes(ImageDraw.Draw(img), ext, water_y, W, H, scale, random.Random(7), ship_x)
        c = np.asarray(img, np.float32).copy()
        blend(c, shade_a, SHADE)
        blend(c, all_a, NEW)
        final = Image.fromarray(np.clip(c, 0, 255).astype(np.uint8))
        steps.append(final)
        # step 9 (bonus): set sails
        c = canvas()
        blend(c, horizon_layer(True), OLD)
        blend(c, load_alpha(lay('sails_old')), OLD)
        img = finish(c)
        draw_guides(img, G, 9, True, lang, font, ext)
        c = np.asarray(img, np.float32).copy()
        blend(c, load_alpha(lay('sails_new')), NEW)
        steps.append(Image.fromarray(np.clip(c, 0, 255).astype(np.uint8)))

        os.makedirs(os.path.join(out_dir, lang), exist_ok=True)
        for i, im in enumerate(steps, 1):
            save_small(im, os.path.join(out_dir, lang, '%s-step-%02d.png' % (view, i)), out_w)
        results[lang] = steps

    # language-free extras
    os.makedirs(extra_dir, exist_ok=True)
    save_small(results[langs[0]][7], os.path.join(extra_dir, view + '-final.png'), out_w)
    c = canvas(); blend(c, all_a, NEW)
    save_small(Image.fromarray(c.astype(np.uint8)), os.path.join(extra_dir, view + '-outline.png'), out_w)
    # finished drawing with set sails
    c = canvas()
    blend(c, refl_s, REFL)
    blend(c, horizon_layer(False) * (1 - np.maximum(mask_s, load_alpha(lay('sails_old')))), NEW, 0.8)
    img = Image.fromarray(np.clip(c, 0, 255).astype(np.uint8))
    water_strokes(ImageDraw.Draw(img), ext, water_y, W, H, scale, random.Random(7), ship_x)
    c = np.asarray(img, np.float32).copy()
    blend(c, shade_s, SHADE)
    blend(c, load_alpha(lay('sails_old')), NEW)
    blend(c, load_alpha(lay('sails_new')), NEW)
    save_small(Image.fromarray(np.clip(c, 0, 255).astype(np.uint8)), os.path.join(extra_dir, view + '-sails-final.png'), out_w)
    if view == 'side':
        make_mistakes(layers, extra_dir, all_a, results[langs[0]][7], water_y, ext, W, H, scale, out_w)
    with open(os.path.join(extra_dir, view + '-info.json'), 'w', encoding='utf-8') as f:
        json.dump({'size': [W, H], 'out_w': out_w, 'extent': ext, 'water_y': water_y, 'horizon_y': hz,
                   'anchors': G.g['anchors'], 'numbers': G.n}, f, indent=1)


def make_mistakes(layers, extra_dir, all_a, final_img, water_y, ext, W, H, scale, out_w):
    """Small pictures for the 'common mistakes' page, built from the side view.
    All of them use the same crop, so they line up on the page."""
    box = (int(max(0, ext[0] - 0.04 * W)), int(max(0, ext[1] - 0.03 * H)),
           int(min(W, ext[2] + 0.04 * W)), int(min(H, water_y + 0.13 * H)))
    def save(c, name):
        im = c if isinstance(c, Image.Image) else Image.fromarray(np.clip(c, 0, 255).astype(np.uint8))
        save_small(im.crop(box), os.path.join(extra_dir, name + '.png'), out_w // 2)
    blank = lambda: np.full((H, W, 3), 255.0, np.float32)
    # 1. masts too short: squash everything above the hull to half height
    a = all_a.copy()
    ys = np.nonzero(load_alpha(os.path.join(layers, 'side_hull_new.png')) > 0.3)[0]
    cut = int(ys.min()) + int(8 * scale)
    top = a[:cut]
    sq = np.asarray(Image.fromarray((top * 255).astype(np.uint8)).resize((W, int(top.shape[0] * 0.5)), Image.LANCZOS), np.float32) / 255
    a2 = np.zeros_like(a); a2[cut:] = a[cut:]
    a2[cut - sq.shape[0]:cut] = np.maximum(a2[cut - sq.shape[0]:cut], sq)
    c = blank(); blend(c, a2, NEW); save(c, 'mistake-short-masts')
    # 2. flat: outline only, no shading, no water
    c = blank(); blend(c, all_a, NEW); save(c, 'mistake-flat')
    # 3. ropes thicker than masts
    rig = load_alpha(os.path.join(layers, 'side_rigging_new.png'))
    k = int(9 * scale) | 1
    rig_thick = np.asarray(Image.fromarray((rig * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k)), np.float32) / 255
    c = blank(); blend(c, all_a, NEW); blend(c, rig_thick, NEW); save(c, 'mistake-thick-ropes')
    # 4. no waterline: the whole hull out of the water, keel and all
    dry = load_alpha(os.path.join(layers, 'side_dry.png'))
    c = blank(); blend(c, dry, NEW); save(c, 'mistake-no-water')
    # the finished drawing for comparison
    save(final_img, 'mistake-ok')


def save_small(im, path, out_w):
    if im.width != out_w:
        im = im.resize((out_w, round(im.height * out_w / im.width)), Image.LANCZOS)
    im = im.convert('RGB').quantize(colors=48, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    im.save(path, optimize=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--layers', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--extra', required=True)
    ap.add_argument('--lang', default='en,pl')
    ap.add_argument('--views', default=','.join(VIEWS))
    ap.add_argument('--width', type=int, default=1800)
    a = ap.parse_args()
    for v in a.views.split(','):
        compose_view(a.layers, v, a.out, a.extra, a.lang.split(','), a.width)
        print('composed', v, flush=True)
