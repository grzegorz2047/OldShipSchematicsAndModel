"""Lay out the booklet pages and write the two PDFs.

    python build_pdf.py --steps ../steps --extra build/extra --out .. [--pages build/pages] [--lang en,pl]

Pages are drawn with Pillow at 240 dpi and stored in the PDF as Flate-compressed images
(no extra Python packages are needed: only Pillow and numpy).
"""
import argparse, json, os, zlib
import numpy as np
from PIL import Image, ImageDraw

from common import find_font
from texts import T, SOURCES, step_text

DPI = 240
PW, PH = round(210 / 25.4 * DPI), round(297 / 25.4 * DPI)
MM = DPI / 25.4
ML = MR = round(12 * MM)
MT = round(11 * MM)
CW = PW - ML - MR
FOOT_Y = PH - round(9 * MM)

INK = (20, 20, 20)
GREY = (110, 110, 110)
ACCENT = (226, 104, 28)
OLD = (140, 182, 228)
RULE = (200, 200, 200)
VIEWS = ['side', 'bow', 'stern']


def pt(p):
    return round(p / 72 * DPI)

class Fonts:
    def __init__(self):
        self.title = find_font(pt(30), style='title')
        self.h1 = find_font(pt(19), style='title')
        self.h2 = find_font(pt(12.5), bold=True)
        self.body = find_font(pt(10.5))
        self.bold = find_font(pt(10.5), bold=True)
        self.small = find_font(pt(8.5))
        self.smallb = find_font(pt(8.5), bold=True)
        self.tiny = find_font(pt(7.2))
        self.num = find_font(pt(8), bold=True)
F = None


# ------------------------------------------------------------------ text helpers
def wrap(draw, text, font, width):
    words = text.split()
    lines, cur = [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def para(draw, xy, text, font, width, fill=INK, lh=1.32, first_bold=None):
    """Draw wrapped text; optional bold lead-in. Returns the y below the paragraph."""
    x, y = xy
    size = font.size
    if first_bold:
        lead = first_bold + ' '
        lw = draw.textlength(lead, font=F.bold)
        lines = wrap(draw, text, font, width - lw)
        # first line next to the bold lead, the rest full width
        first = lines[0] if lines else ''
        rest = ' '.join(lines[1:])
        draw.text((x, y), lead, font=F.bold, fill=fill)
        draw.text((x + lw, y), first, font=font, fill=fill)
        y += round(size * lh)
        for ln in wrap(draw, rest, font, width):
            draw.text((x, y), ln, font=font, fill=fill); y += round(size * lh)
        return y
    for ln in wrap(draw, text, font, width):
        draw.text((x, y), ln, font=font, fill=fill)
        y += round(size * lh)
    return y

def para_height(draw, text, font, width, lh=1.32, first_bold=None):
    img = Image.new('RGB', (10, 10)); d = ImageDraw.Draw(img)
    if first_bold:
        lw = d.textlength(first_bold + ' ', font=F.bold)
        lines = wrap(d, text, font, width - lw)
        rest = ' '.join(lines[1:])
        return round(font.size * lh) * (1 + len(wrap(d, rest, font, width)))
    return round(font.size * lh) * len(wrap(d, text, font, width))

def bullets(draw, xy, items, font, width, gap=10, mark='•'):
    x, y = xy
    ind = round(draw.textlength(mark + '  ', font=font))
    for it in items:
        draw.text((x, y), mark, font=font, fill=ACCENT)
        y = para(draw, (x + ind, y), it, font, width - ind) + gap
    return y


# ------------------------------------------------------------------ images
def crop_content(im, pad=20, thr=245, min_col=None):
    """Crop to the drawing. Columns with only a few dark pixels (the horizon, water strokes) do not count."""
    g = np.asarray(im.convert('L')) < thr
    min_col = max(4, im.height // 150) if min_col is None else min_col
    cols = np.nonzero(g.sum(0) > min_col)[0]
    rows = np.nonzero(g.sum(1) > 0)[0]
    if not len(cols) or not len(rows):
        return im
    x0, x1, y0, y1 = cols[0], cols[-1], rows[0], rows[-1]
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))

def fit(im, w=None, h=None):
    s = min((w / im.width) if w else 1e9, (h / im.height) if h else 1e9)
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)

def framed(page, im, xy, outline=RULE):
    page.paste(im.convert('RGB'), xy)
    d = ImageDraw.Draw(page)
    d.rectangle([xy[0], xy[1], xy[0] + im.width - 1, xy[1] + im.height - 1], outline=outline, width=2)


# ------------------------------------------------------------------ page furniture
def new_page():
    return Image.new('RGB', (PW, PH), 'white')

def footer(page, lang, n):
    d = ImageDraw.Draw(page)
    d.line([(ML, FOOT_Y - round(2.5 * MM)), (PW - MR, FOOT_Y - round(2.5 * MM))], fill=RULE, width=2)
    d.text((ML, FOOT_Y), T[lang]['footer'], font=F.tiny, fill=GREY, anchor='lm')
    d.text((PW - MR, FOOT_Y), str(n), font=F.smallb, fill=GREY, anchor='rm')

def difficulty_dots(d, x, y, level, r=None):
    r = r or round(1.6 * MM)
    for i in range(3):
        cx = x + r + i * (2 * r + round(1.2 * MM))
        box = [cx - r, y - r, cx + r, y + r]
        if i < level:
            d.ellipse(box, fill=INK)
        else:
            d.ellipse(box, outline=INK, width=3)
    return x + 3 * (2 * r) + 2 * round(1.2 * MM)

LEVEL = {'side': 1, 'bow': 2, 'stern': 3}


# ------------------------------------------------------------------ pages
def page_cover(lang, extra):
    p = new_page(); d = ImageDraw.Draw(p)
    t = T[lang]
    y = MT + round(8 * MM)
    d.text((PW // 2, y), t['title'], font=F.title, fill=INK, anchor='mt')
    y += F.title.size + round(4 * MM)
    d.text((PW // 2, y), t['subtitle'], font=F.h1, fill=ACCENT, anchor='mt')
    y += F.h1.size + round(10 * MM)
    im = crop_content(Image.open(os.path.join(extra, 'bow-sails-final.png')).convert('RGB'), 30)
    im = fit(im, CW, round(185 * MM))
    p.paste(im, ((PW - im.width) // 2, y))
    y += im.height + round(8 * MM)
    d.text((PW // 2, y), t['cover_ship'], font=F.h2, fill=INK, anchor='mt')
    y += F.h2.size + round(4 * MM)
    d.text((PW // 2, y), t['cover_ages'], font=F.body, fill=GREY, anchor='mt')
    y += F.body.size + round(10 * MM)
    # small strip with the three views
    thumbs = [crop_content(Image.open(os.path.join(extra, v + '-final.png')).convert('RGB'), 10) for v in VIEWS]
    th = round(34 * MM)
    thumbs = [fit(im, h=th) for im in thumbs]
    total = sum(im.width for im in thumbs) + 2 * round(8 * MM)
    x = (PW - total) // 2
    for v, im in zip(VIEWS, thumbs):
        p.paste(im, (x, y))
        name = t['views'][v][0].split(':')[-1].strip()
        d.text((x + im.width // 2, y + th + round(2 * MM)), name, font=F.small, fill=GREY, anchor='mt')
        x += im.width + round(8 * MM)
    y += th + round(10 * MM)
    box_h = para_height(d, t['cover_note'], F.small, CW - round(16 * MM)) + round(8 * MM)
    d.rounded_rectangle([ML, y, PW - MR, y + box_h], radius=round(3 * MM), outline=RULE, width=3)
    para(d, (ML + round(8 * MM), y + round(4 * MM)), t['cover_note'], F.small, CW - round(16 * MM), fill=GREY)
    footer(p, lang, 1)
    return p

def legend_sample(d, x, y, kind, w):
    if kind == 'new':
        d.line([(x, y), (x + w, y)], fill=INK, width=6)
    elif kind == 'old':
        d.line([(x, y), (x + w, y)], fill=OLD, width=6)
    else:
        xx = x
        while xx < x + w:
            d.line([(xx, y), (min(x + w, xx + 22), y)], fill=ACCENT, width=4); xx += 34

def page_intro(lang, extra):
    p = new_page(); d = ImageDraw.Draw(p)
    t = T[lang]
    y = MT
    d.text((ML, y), t['start_title'], font=F.h1, fill=INK)
    y += F.h1.size + round(5 * MM)
    colw = (CW - round(8 * MM)) // 2
    d.text((ML, y), t['need_title'], font=F.h2, fill=ACCENT)
    d.text((ML + colw + round(8 * MM), y), t['how_title'], font=F.h2, fill=ACCENT)
    y0 = y + F.h2.size + round(3 * MM)
    y1 = bullets(d, (ML, y0), t['need'], F.body, colw, gap=6)
    y2 = bullets(d, (ML + colw + round(8 * MM), y0), t['how'], F.body, colw, gap=6)
    y = max(y1, y2) + round(3 * MM)
    # legend
    d.text((ML, y), t['legend_title'], font=F.h2, fill=ACCENT)
    y += F.h2.size + round(3 * MM)
    for kind, txt in t['legend']:
        legend_sample(d, ML, y + F.body.size // 2 + 2, kind, round(16 * MM))
        d.text((ML + round(20 * MM), y), txt, font=F.body, fill=INK)
        y += round(F.body.size * 1.45)
    y += round(4 * MM)
    d.line([(ML, y), (PW - MR, y)], fill=RULE, width=2)
    y += round(4 * MM)
    # meet the ship
    d.text((ML, y), t['meet_title'], font=F.h1, fill=INK)
    y += F.h1.size + round(2 * MM)
    y = para(d, (ML, y), t['meet_intro'], F.body, CW, fill=GREY) + round(2 * MM)
    info = json.load(open(os.path.join(extra, 'side-info.json'), encoding='utf-8'))
    im = Image.open(os.path.join(extra, 'side-final.png')).convert('RGB')
    W, H = info['size']
    s_in = im.width / W
    # legend size first, so the picture can take the rest of the page
    order = ['foremast', 'mainmast', 'snowmast', 'topmast', 'top', 'bowsprit', 'yard', 'furled_sail', 'gaff',
             'shrouds', 'ratlines', 'stay', 'backstay', 'quarterdeck', 'lantern', 'wheel', 'stern',
             'boat', 'rudder', 'waterline', 'wale', 'gunport', 'anchor', 'head']
    order = [k for k in order if info['anchors'].get(k)]
    r = round(2.3 * MM)
    cols = 3
    per = (len(order) + cols - 1) // cols
    row_h = round(F.small.size * 1.42)
    legend_h = per * row_h + round(3 * MM)
    # crop the picture: ship plus room for the label columns and the row under the water
    ext = info['extent']
    pad_x = int(0.06 * W)
    x0 = max(0, int((ext[0] - pad_x) * s_in)); x1 = min(im.width, int((ext[2] + pad_x) * s_in))
    top = max(0, int((ext[1] - 30) * s_in))
    bot = min(im.height, int((info['water_y'] + 0.10 * H) * s_in))
    im = im.crop((x0, top, x1, bot))
    img_y = y + round(1 * MM)
    im = fit(im, CW, FOOT_Y - round(7 * MM) - legend_h - img_y)
    sc = im.width / ((x1 - x0) / s_in)          # render px -> page px
    img_x = ML + (CW - im.width) // 2
    p.paste(im, (img_x, img_y))
    P = lambda a: (img_x + (a[0] - x0 / s_in) * sc, img_y + (a[1] - top / s_in) * sc)
    ship_l = P((ext[0], 0))[0]; ship_r = P((ext[2], 0))[0]
    water = P((0, info['water_y']))[1]
    cxm = (ship_l + ship_r) / 2
    low = {'gunport', 'wale', 'rudder', 'anchor', 'head', 'boat', 'waterline', 'stern'}
    deck = set()   # deck items join the sky column on their side
    place = {}
    # sky labels: two columns, kept apart vertically
    for side in (-1, 1):
        ks = [k for k in order if k not in low and k not in deck and (P(info['anchors'][k])[0] - cxm) * side > 0]
        ks.sort(key=lambda k: P(info['anchors'][k])[1])
        col_x = (ship_l + 1.6 * r) if side < 0 else (ship_r - 1.6 * r)
        last = -1e9; ys_ = []
        for k in ks:
            ay = P(info['anchors'][k])[1]
            cy = max(ay, last + 2.6 * r)
            ys_.append(cy); last = cy
        if ks:
            over = ys_[-1] - P(info['anchors'][ks[-1]])[1]
            shift = min(over / 2, ys_[0] - (img_y + 2 * r))
            for k, cy in zip(ks, ys_):
                place[k] = (col_x, cy - max(0, shift))
    # deck labels: a row above the quarterdeck; low labels: a row in the water
    for group, row_y in ((deck, P(info['anchors']['quarterdeck'])[1] - 9 * r), (low, water + 4.2 * r)):
        ks = sorted([k for k in order if k in group], key=lambda k: P(info['anchors'][k])[0])
        last = -1e9
        for k in ks:
            ax = P(info['anchors'][k])[0]
            cx = max(ax, last + 2.6 * r)
            place[k] = (cx, row_y); last = cx
    nums = []
    for i, k in enumerate(order, 1):
        ax, ay = P(info['anchors'][k])
        cx, cy = place[k]
        d.line([(ax, ay), (cx, cy)], fill=ACCENT, width=3)
        d.ellipse([ax - 6, ay - 6, ax + 6, ay + 6], fill=ACCENT)
        nums.append((i, t['parts'][k], cx, cy))
    for i, name, cx, cy in nums:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill='white', outline=ACCENT, width=4)
        d.text((cx, cy + 1), str(i), font=F.num, fill=INK, anchor='mm')
    y = img_y + im.height + round(3 * MM)
    cw = CW // cols
    for c in range(cols):
        yy = y
        for i, name, _, _ in nums[c * per:(c + 1) * per]:
            x = ML + c * cw
            d.ellipse([x, yy + 2, x + 2 * r, yy + 2 + 2 * r], outline=ACCENT, width=3)
            d.text((x + r, yy + 2 + r + 1), str(i), font=F.num, fill=INK, anchor='mm')
            d.text((x + 2 * r + round(2 * MM), yy), name, font=F.small, fill=INK)
            yy += row_h
    footer(p, lang, 2)
    return p

def view_header(p, lang, view, extra, y):
    d = ImageDraw.Draw(p)
    t = T[lang]
    name, level_name, desc = t['views'][view]
    th = round(24 * MM)
    im = crop_content(Image.open(os.path.join(extra, view + '-final.png')).convert('RGB'), 8)
    im = fit(im, h=th)
    framed(p, im, (ML, y))
    x = ML + im.width + round(6 * MM)
    d.text((x, y + round(1 * MM)), name, font=F.h1, fill=INK)
    yy = y + F.h1.size + round(3.5 * MM)
    d.text((x, yy), t['difficulty'] + ':', font=F.bold, fill=INK)
    xx = x + d.textlength(t['difficulty'] + ': ', font=F.bold) + round(1 * MM)
    xx = difficulty_dots(d, xx, yy + F.bold.size // 2 + 4, LEVEL[view])
    d.text((xx + round(3 * MM), yy), level_name, font=F.bold, fill=ACCENT)
    yy += round(F.body.size * 1.5)
    para(d, (x, yy), desc, F.body, PW - MR - x, fill=GREY)
    return y + th + round(5 * MM)

def running_header(p, lang, view, a, b, y):
    d = ImageDraw.Draw(p)
    t = T[lang]
    name = t['views'][view][0]
    d.text((ML, y), name, font=F.smallb, fill=GREY)
    d.text((PW - MR, y), '%s %d–%d' % (t['steps_plural'], a, b), font=F.smallb, fill=GREY, anchor='ra')
    d.line([(ML, y + F.smallb.size + 12), (PW - MR, y + F.smallb.size + 12)], fill=RULE, width=2)
    return y + F.smallb.size + round(4 * MM)

def step_block(p, lang, view, k, steps, nums, y, max_img_h):
    d = ImageDraw.Draw(p)
    t = T[lang]
    im = Image.open(os.path.join(steps, lang, '%s-step-%02d.png' % (view, k))).convert('RGB')
    im = fit(im, CW, max_img_h)
    x = ML + (CW - im.width) // 2
    framed(p, im, (x, y))
    # step number badge
    r = round(5 * MM)
    d.ellipse([x + 18, y + 18, x + 18 + 2 * r, y + 18 + 2 * r], fill=INK)
    d.text((x + 18 + r, y + 18 + r), str(k), font=F.h2, fill='white', anchor='mm')
    y += im.height + round(2.5 * MM)
    title, body = step_text(lang, view, k, nums)
    lead = '%s %d. %s.' % (t['steps_word'], k, title)
    y = para(d, (ML, y), body, F.body, CW, first_bold=lead)
    return y

def text_height(lang, view, k, nums):
    title, body = step_text(lang, view, k, nums)
    lead = '%s %d. %s.' % (T[lang]['steps_word'], k, title)
    return para_height(None, body, F.body, CW, first_bold=lead)

def frac(x):
    """4.33 -> '4¼' style, to the nearest quarter."""
    q = round(x * 4) / 4
    whole = int(q); part = q - whole
    sym = {0.25: '¼', 0.5: '½', 0.75: '¾'}.get(round(part, 2), '')
    return (str(whole) if whole or not sym else '') + sym

def view_numbers(extra, view):
    info = json.load(open(os.path.join(extra, 'side-info.json'), encoding='utf-8'))
    n = info['numbers']
    return {
        'cols': n['grid_cols'], 'rows': frac(n['grid_rows']),
        'fore_pos': frac(n['mast_pos_units']['fore']), 'main_pos': frac(n['mast_pos_units']['main']),
        'fore_top': frac(n['mast_top_units']['fore']), 'main_top': frac(n['mast_top_units']['main']),
        'bsp': frac(n['bowsprit_units']),
    }

def pages_view(lang, view, steps, extra, first_no):
    nums = view_numbers(extra, view)
    out = []
    for i, (a, b) in enumerate(((1, 2), (3, 4), (5, 6), (7, 8))):
        p = new_page()
        y = MT
        if i == 0:
            y = view_header(p, lang, view, extra, y)
        else:
            y = running_header(p, lang, view, a, b, y)
        avail = FOOT_Y - round(5 * MM) - y
        th = text_height(lang, view, a, nums) + text_height(lang, view, b, nums)
        gaps = 2 * round(2.5 * MM) + round(5 * MM)
        img_h = min(round(CW / 1.8), (avail - th - gaps) // 2)
        y = step_block(p, lang, view, a, steps, nums, y, img_h) + round(5 * MM)
        step_block(p, lang, view, b, steps, nums, y, img_h)
        footer(p, lang, first_no + i)
        out.append(p)
    return out

def page_bonus(lang, steps, extra, n):
    p = new_page(); d = ImageDraw.Draw(p); t = T[lang]
    y = MT
    d.text((ML, y), t['bonus_title'], font=F.h1, fill=INK); y += F.h1.size + round(3 * MM)
    y = para(d, (ML, y), t['bonus_intro'], F.body, CW) + round(3 * MM)
    im = Image.open(os.path.join(steps, lang, 'side-step-09.png')).convert('RGB')
    im = fit(crop_content(im, 30), CW, round(124 * MM))
    framed(p, im, (ML + (CW - im.width) // 2, y))
    d.text((ML + (CW - im.width) // 2 + 20, y + 16), '%s 9 · %s' % (t['steps_word'], t['bonus_caption']['side']), font=F.smallb, fill=GREY)
    y += im.height + round(4 * MM)
    half = (CW - round(5 * MM)) // 2
    hs = []
    for j, v in enumerate(('bow', 'stern')):
        im = Image.open(os.path.join(steps, lang, '%s-step-09.png' % v)).convert('RGB')
        im = fit(crop_content(im, 30), half, round(100 * MM))
        x = ML + j * (half + round(5 * MM)) + (half - im.width) // 2
        framed(p, im, (x, y))
        d.text((x + 16, y + 14), '%s 9 · %s' % (t['steps_word'], t['bonus_caption'][v]), font=F.smallb, fill=GREY)
        hs.append(im.height)
    y += max(hs) + round(5 * MM)
    y = bullets(d, (ML, y), t['bonus_tips'], F.body, CW, gap=6)
    footer(p, lang, n)
    return p

def mark(d, x, y, ok, r=None):
    r = r or round(4.2 * MM)
    if ok:
        d.ellipse([x - r, y - r, x + r, y + r], fill='white', outline=INK, width=5)
        d.line([(x - r * 0.45, y + r * 0.02), (x - r * 0.1, y + r * 0.4), (x + r * 0.5, y - r * 0.4)], fill=INK, width=8)
    else:
        d.ellipse([x - r, y - r, x + r, y + r], fill='white', outline=ACCENT, width=5)
        k = r * 0.42
        d.line([(x - k, y - k), (x + k, y + k)], fill=ACCENT, width=8)
        d.line([(x - k, y + k), (x + k, y - k)], fill=ACCENT, width=8)

def page_mistakes(lang, extra, n):
    p = new_page(); d = ImageDraw.Draw(p); t = T[lang]
    y = MT
    d.text((ML, y), t['mist_title'], font=F.h1, fill=INK); y += F.h1.size + round(5 * MM)
    half = (CW - round(6 * MM)) // 2
    # reference picture
    ok = fit(Image.open(os.path.join(extra, 'mistake-ok.png')).convert('RGB'), half, round(66 * MM))
    x = ML + (CW - ok.width) // 2
    framed(p, ok, (x, y))
    mark(d, x + ok.width - round(6 * MM), y + round(6 * MM), True)
    d.text((x + 16, y + 14), t['mist_ok'], font=F.smallb, fill=INK)
    y += ok.height + round(6 * MM)
    row_y = y
    for i, (fname, title, txt) in enumerate(t['mistakes']):
        col = i % 2
        if i == 2:
            row_y = y2
        x = ML + col * (half + round(6 * MM))
        im = fit(Image.open(os.path.join(extra, fname + '.png')).convert('RGB'), half, round(66 * MM))
        yy = row_y
        framed(p, im, (x + (half - im.width) // 2, yy))
        mark(d, x + (half + im.width) // 2 - round(6 * MM), yy + round(6 * MM), False)
        yy += im.height + round(2.5 * MM)
        d.text((x, yy), title, font=F.h2, fill=INK)
        yy += F.h2.size + round(2 * MM)
        yy = para(d, (x, yy), txt, F.body, half)
        if col == 0:
            y_left = yy
        else:
            y2 = max(y_left, yy) + round(6 * MM)
    footer(p, lang, n)
    return p

def page_facts(lang, n, extra):
    p = new_page(); d = ImageDraw.Draw(p); t = T[lang]
    y = MT
    d.text((ML, y), t['facts_title'], font=F.h1, fill=INK); y += F.h1.size + round(5 * MM)
    colw = (CW - round(8 * MM)) // 2
    cols_y = [y, y]
    for i, (head, txt) in enumerate(t['facts']):
        c = 0 if cols_y[0] <= cols_y[1] else 1
        x = ML + c * (colw + round(8 * MM))
        yy = cols_y[c]
        d.rectangle([x, yy + 6, x + 10, yy + F.h2.size + 2], fill=ACCENT)
        d.text((x + 24, yy), head, font=F.h2, fill=INK)
        yy += F.h2.size + round(2 * MM)
        yy = para(d, (x, yy), txt, F.body, colw)
        cols_y[c] = yy + round(5 * MM)
    y = max(cols_y) + round(2 * MM)
    d.line([(ML, y), (PW - MR, y)], fill=RULE, width=2); y += round(4 * MM)
    y = para(d, (ML, y), t['facts_note'], F.small, CW, fill=GREY) + round(2 * MM)
    d.text((ML, y), t['sources_title'], font=F.smallb, fill=INK); y += F.smallb.size + round(2 * MM)
    for s in SOURCES:
        y = para(d, (ML, y), s, F.tiny, CW, fill=GREY, lh=1.3) + 4
    snow_mast_figure(p, lang, extra, y + round(5 * MM))
    footer(p, lang, n)
    return p

def snow_mast_figure(p, lang, extra, y):
    """Close-up of the mainmast and the snow mast, cut from the finished side view."""
    d = ImageDraw.Draw(p); t = T[lang]
    info = json.load(open(os.path.join(extra, 'side-info.json'), encoding='utf-8'))
    im = Image.open(os.path.join(extra, 'side-final.png')).convert('RGB')
    W, H = info['size']; s_in = im.width / W
    A = info['anchors']; ext = info['extent']
    x0 = (min(A['gaff'][0], A['snowmast'][0]) - 0.11 * W); x1 = A['mainmast'][0] + 0.11 * W
    y0 = ext[1] - 0.01 * H; y1 = info['water_y'] + 0.02 * H
    crop = im.crop((int(x0 * s_in), int(y0 * s_in), int(x1 * s_in), int(y1 * s_in)))
    avail = FOOT_Y - round(8 * MM) - y
    if avail < 40 * MM:
        return
    fig = fit(crop, round(CW * 0.42), avail)
    framed(p, fig, (ML, y))
    sc = fig.width / ((x1 - x0))
    def P(a):
        return (ML + (a[0] - x0) * sc, y + (a[1] - y0) * sc)
    tx = ML + fig.width + round(8 * MM)
    labels = [('snowmast', t['parts']['snowmast']), ('mainmast', t['parts']['mainmast']), ('gaff', t['parts']['gaff'])]
    labels.sort(key=lambda kv: A[kv[0]][1])
    ty = y + round(fig.height * 0.25)
    for k, name in labels:
        ax, ay = P(A[k])
        d.line([(ax, ay), (tx - round(2 * MM), ty + F.bold.size // 2)], fill=ACCENT, width=3)
        d.ellipse([ax - 6, ay - 6, ax + 6, ay + 6], fill=ACCENT)
        d.text((tx, ty), name, font=F.bold, fill=INK)
        ty += round(F.bold.size * 2.2)
    para(d, (tx, ty + round(2 * MM)), t['snow_caption'], F.body, PW - MR - tx, fill=GREY)

def page_trace(lang, extra, n):
    p = new_page(); d = ImageDraw.Draw(p); t = T[lang]
    y = MT
    d.text((ML, y), t['trace_title'], font=F.h1, fill=INK); y += F.h1.size + round(3 * MM)
    y = para(d, (ML, y), t['trace_intro'], F.body, CW, fill=GREY) + round(4 * MM)
    about_h = para_height(d, t['about'], F.tiny, CW)
    about_y = FOOT_Y - round(6 * MM) - about_h
    half = (CW - round(6 * MM)) // 2
    pair = [fit(crop_content(Image.open(os.path.join(extra, v + '-outline.png')).convert('RGB'), 30), half, round(120 * MM))
            for v in ('bow', 'stern')]
    pair_h = max(im.height for im in pair)
    side_h = about_y - round(10 * MM) - pair_h - y
    side = fit(crop_content(Image.open(os.path.join(extra, 'side-outline.png')).convert('RGB'), 30), CW, side_h)
    p.paste(side, (ML + (CW - side.width) // 2, y)); y += side.height + round(5 * MM)
    for j, im in enumerate(pair):
        p.paste(im, (ML + j * (half + round(6 * MM)) + (half - im.width) // 2, y + (pair_h - im.height)))
    para(d, (ML, about_y), t['about'], F.tiny, CW, fill=GREY)
    footer(p, lang, n)
    return p


# ------------------------------------------------------------------ PDF writer (images only)
def write_pdf(pages, path, title):
    objs = []
    def add(b):
        objs.append(b); return len(objs)
    catalog = add(None); pages_id = add(None)
    kids = []
    for im in pages:
        q = im.convert('RGB').quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pal = q.getpalette()[:96 * 3]
        pal += [255] * (96 * 3 - len(pal))
        data = zlib.compress(q.tobytes(), 9)
        img_id = add(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace [/Indexed /DeviceRGB 95 <%s>] '
                     b'/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n' % (
                         im.width, im.height, bytes(pal).hex().encode(), len(data)) + data + b'\nendstream')
        w_pt, h_pt = 595.276, 841.89
        content = b'q %.3f 0 0 %.3f 0 0 cm /Im0 Do Q' % (w_pt, h_pt)
        c_id = add(b'<< /Length %d >>\nstream\n' % len(content) + content + b'\nendstream')
        pg = add(b'<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.3f %.3f] /Resources << /XObject << /Im0 %d 0 R >> >> /Contents %d 0 R >>'
                 % (pages_id, w_pt, h_pt, img_id, c_id))
        kids.append(pg)
    objs[catalog - 1] = b'<< /Type /Catalog /Pages %d 0 R >>' % pages_id
    objs[pages_id - 1] = b'<< /Type /Pages /Kids [%s] /Count %d >>' % (b' '.join(b'%d 0 R' % k for k in kids), len(kids))
    t16 = title.encode('utf-16-be')
    info = add(b'<< /Title <feff%s> /Producer (drawing-tutorial build_pdf.py) >>' % t16.hex().encode())
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b'%d 0 obj\n' % i + o + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for o in offs:
        out += b'%010d 00000 n \n' % o
    out += b'trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, catalog, info, xref)
    with open(path, 'wb') as f:
        f.write(out)


def build(lang, steps, extra, out, pages_dir):
    pages = [page_cover(lang, extra), page_intro(lang, extra)]
    n = 3
    for v in VIEWS:
        pages += pages_view(lang, v, steps, extra, n); n += 4
    pages.append(page_bonus(lang, steps, extra, n)); n += 1
    pages.append(page_mistakes(lang, extra, n)); n += 1
    pages.append(page_facts(lang, n, extra)); n += 1
    pages.append(page_trace(lang, extra, n)); n += 1
    if pages_dir:
        os.makedirs(pages_dir, exist_ok=True)
        for i, pg in enumerate(pages, 1):
            pg.save(os.path.join(pages_dir, '%s-page-%02d.png' % (lang, i)))
    name = 'how-to-draw-the-ship-%s.pdf' % lang
    write_pdf(pages, os.path.join(out, name), T[lang]['title'])
    print('wrote', name, len(pages), 'pages', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', required=True)
    ap.add_argument('--extra', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pages', default=None, help='also save every page as PNG here (for checking)')
    ap.add_argument('--lang', default='en,pl')
    a = ap.parse_args()
    F = Fonts()
    for lang in a.lang.split(','):
        build(lang, a.steps, a.extra, a.out, a.pages)
