"""Proceduralne, kafelkujące tekstury statku (numpy + PIL, zwykły Python, nie Blender).

    python blender/tekstury.py <katalog_wyjściowy> [--size 2048] [--only poklad,burta,...] [--force]

Każdy zestaw: <nazwa>_kolor.jpg (sRGB), <nazwa>_normalne.jpg (OpenGL, zielony w górę, jakość 92),
<nazwa>_szorstkosc.jpg (glTF metallicRoughness: G – chropowatość, B – metaliczność, R = 1).
Szum powstaje przez filtrowanie białego szumu w dziedzinie częstotliwości (FFT), więc każda tekstura jest okresowa:
kafelkuje bez szwu z definicji. Rozmiar kafla w metrach (do UV) jest w parametry.py (MATERIALY), tu tylko układ
desek / pasów w obrębie kafla – oba miejsca muszą się zgadzać (tabela KAFEL niżej). Bez wypalonego światła i cieni:
kolor to albedo, rzeźba jest tylko w mapie normalnych.
"""
import json
import os
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass

import numpy as np
from PIL import Image

# metry na kafel (musi się zgadzać z parametry.MATERIALY[...]['kafel'])
KAFEL = {"poklad": 6.4, "burta": 8.0, "drewno": 2.0, "zelazo": 1.0, "lina": 1.0, "plotno": 2.4, "okno": 1.0}


def fnoise(n, sx, sy, seed, kind="gauss"):
    """Okresowy szum n×n o długości korelacji sx (wzdłuż osi x obrazu) i sy (px); średnia 0, odchylenie 1."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n))
    kx = np.fft.fftfreq(n)[None, :]
    ky = np.fft.fftfreq(n)[:, None]
    if kind == "gauss":
        f = np.exp(-((kx * sx * np.pi) ** 2 + (ky * sy * np.pi) ** 2))
    else:  # widmo potęgowe (fraktalne), sx – skala odcięcia
        k = np.sqrt((kx * sx) ** 2 + (ky * sy) ** 2) + 1e-6
        f = k ** -1.4 * np.exp(-(k * 0.02) ** 2)
        f[0, 0] = 0
    r = np.real(np.fft.ifft2(np.fft.fft2(w) * f))
    r -= r.mean()
    return r / (r.std() + 1e-9)


def blur(a, s):
    """Okresowe rozmycie gaussowskie (px)."""
    n0, n1 = a.shape[:2]
    kx = np.fft.fftfreq(n1)[None, :]
    ky = np.fft.fftfreq(n0)[:, None]
    f = np.exp(-2 * (np.pi * s) ** 2 * (kx ** 2 + ky ** 2))
    if a.ndim == 2:
        return np.real(np.fft.ifft2(np.fft.fft2(a) * f))
    return np.stack([np.real(np.fft.ifft2(np.fft.fft2(a[..., c]) * f)) for c in range(a.shape[2])], -1)


def normal_from_height(h, strength):
    """Wysokość (w px, dodatnia = wypukło) → mapa normalnych OpenGL (zielony = +V, czyli w górę obrazu)."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dr = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5   # wiersze rosną w dół obrazu
    nx = -dx * strength
    ny = dr * strength                                  # dh/d(góra) = −dh/dr → ny = −dh/d(góra) = dr
    nz = np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], -1)
    return np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)


def save(out, name, col, nrm, rough, metal=None, q=90):
    os.makedirs(out, exist_ok=True)
    c = np.clip(col * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(c, "RGB").save(os.path.join(out, name + "_kolor.jpg"), quality=q, subsampling=0)
    Image.fromarray(nrm, "RGB").save(os.path.join(out, name + "_normalne.jpg"), quality=92, subsampling=0)
    n = rough.shape[0]
    m = np.zeros((n, n)) if metal is None else metal
    rm = np.stack([np.ones((n, n)), np.clip(rough, 0, 1), np.clip(m, 0, 1)], -1)
    Image.fromarray((rm * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(out, name + "_szorstkosc.jpg"),
                                                                   quality=q, subsampling=0)


def srgb(*c):
    return np.array(c, dtype=np.float64) / 255.0


def disc_field(n, centers, radius):
    """Pole odległości do najbliższego środka (okresowe, px) – do kołków i łbów sworzni."""
    yy, xx = np.mgrid[0:n, 0:n]
    d = np.full((n, n), 1e9)
    r = int(radius * 3) + 2
    for (cy, cx) in centers:
        y0, x0 = int(cy), int(cx)
        ys = (np.arange(y0 - r, y0 + r + 1)) % n
        xs = (np.arange(x0 - r, x0 + r + 1)) % n
        sub_y = (np.arange(y0 - r, y0 + r + 1) - cy)[:, None]
        sub_x = (np.arange(x0 - r, x0 + r + 1) - cx)[None, :]
        dd = np.sqrt(sub_y ** 2 + sub_x ** 2)
        blk = d[np.ix_(ys, xs)]
        d[np.ix_(ys, xs)] = np.minimum(blk, dd)
    return d


def planks(n, rows, butts_per_row, shift, frames, seed, seam_px, tn_rows=2, tn_r=4.0, tn_every=1, jitter=0.0):
    """Wspólny układ klepek: wiersze = klepki (oś v), wzdłuż u styki co 1/butts_per_row kafla przesunięte o shift
    pozycji ramy na wiersz. Zwraca słownik pól: id klepki, odległość do szczeliny wzdłużnej i do styku, kołki."""
    rng = np.random.default_rng(seed)
    h = n / rows
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    row = np.floor(yy / h).astype(int)
    fy = yy - row * h                      # px od górnej krawędzi klepki
    d_seam = np.minimum(fy, h - fy)        # odległość do szczeliny wzdłużnej
    fw = n / frames                        # odstęp wręgów / pokładników (px)
    seg = n / butts_per_row
    # pozycja styku w wierszu: na linii wręgu, przesunięta o shift wręgów na wiersz (układ styków)
    butt0 = np.array([((r * shift) % frames) * fw + rng.uniform(-jitter, jitter) * fw for r in range(rows)])
    bx = (xx - butt0[row]) % seg
    d_butt = np.minimum(bx, seg - bx)
    plank_id = row * butts_per_row + np.floor(((xx - butt0[row]) % n) / seg).astype(int)
    # kołki: na każdej linii wręgu, tn_rows w klepce; przy stykach po obu stronach
    centers = []
    for r in range(rows):
        for f in range(frames):
            if f % tn_every:
                continue
            x = f * fw + fw * 0.5 * 0 + rng.normal(0, 0.6)
            for k in range(tn_rows):
                y = r * h + h * (k + 1) / (tn_rows + 1) + rng.normal(0, 0.5)
                bxr = (x - butt0[r]) % seg
                if min(bxr, seg - bxr) < tn_r * 3:
                    for sgn in (-1, 1):
                        centers.append((y, (butt0[r] + (bxr // seg) * seg + sgn * tn_r * 3.2) % n))
                else:
                    centers.append((y, x % n))
    d_tn = disc_field(n, centers, tn_r)
    return dict(row=row, fy=fy, h=h, d_seam=d_seam, d_butt=d_butt, plank_id=plank_id, d_tn=d_tn, rng=rng)


def per_plank(ids, seed, scale):
    rng = np.random.default_rng(seed)
    vals = rng.normal(0, scale, ids.max() + 1)
    return vals[ids]


def grain(n, seed, along=400.0, across=1.2, rings=0.11, warp=40.0):
    """Usłojenie wzdłuż osi u (x obrazu): drobne słoje + długie włókna."""
    w = fnoise(n, along * 0.6, 18, seed) * warp
    yy = np.mgrid[0:n, 0:n][0].astype(np.float64)
    ring = np.sin(2 * np.pi * (yy + w) * rings)
    ring = np.sign(ring) * np.abs(ring) ** 0.35
    fib = fnoise(n, along, across, seed + 1)
    return ring, fib


def tex_poklad(n, out, seed=11):
    # kafel 6,4 m: 32 klepki po 0,2 m (64 px), pokładniki co 0,8 m (8 na kafel), jeden styk w wierszu na kafel,
    # przesunięcie 3 pokładniki na wiersz (sąsiednie styki 2,4 m od siebie, ten sam pokładnik co 8 klepek)
    P = planks(n, rows=32, butts_per_row=1, shift=3, frames=8, seed=seed, seam_px=3, tn_rows=2, tn_r=3.6)
    ring, fib = grain(n, seed + 5, along=500, rings=0.09)
    base = srgb(178, 154, 118)
    pv = per_plank(P["plank_id"], seed + 7, 0.07)
    tone = 1 + pv + 0.035 * fib + 0.03 * ring
    dirt = fnoise(n, 160, 160, seed + 9) * 0.04 + fnoise(n, 30, 30, seed + 10) * 0.02
    col = base[None, None, :] * (tone + dirt)[..., None]
    # cieplejsze / szarsze klepki
    hue = per_plank(P["plank_id"], seed + 8, 0.04)
    col[..., 0] *= 1 + hue
    col[..., 2] *= 1 - hue
    # szczeliny (dychtunek ze smołą) 3 px, ciemniejszy brud przy nich
    seam = np.clip(1.6 - np.minimum(P["d_seam"], P["d_butt"]), 0, 1)
    near = np.exp(-np.minimum(P["d_seam"], P["d_butt"]) / 5.0)
    col *= (1 - 0.12 * near)[..., None]
    pitch = srgb(30, 25, 20)
    col = col * (1 - seam[..., None]) + pitch * seam[..., None]
    # kołki (jaśniejsze, z ciemną obwódką)
    tn = np.clip(3.6 - P["d_tn"], 0, 1)
    rim = np.exp(-((P["d_tn"] - 3.8) ** 2) / 1.2)
    col = col * (1 - 0.25 * rim[..., None])
    col = col * (1 - tn[..., None]) + (srgb(196, 172, 132) * (1 + 0.05 * fib[..., None])) * tn[..., None]
    # przetarcia (jaśniej, szarzej) w plamach
    wear = np.clip(fnoise(n, 220, 120, seed + 12) * 0.5 + 0.2, 0, 1) * 0.12
    col = col * (1 - wear[..., None]) + srgb(190, 182, 165) * wear[..., None]
    # sęki
    rng = np.random.default_rng(seed + 13)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    for _ in range(14):
        cy, cx = rng.uniform(0, n, 2)
        dy = (yy - cy + n / 2) % n - n / 2
        dx = ((xx - cx + n / 2) % n - n / 2) / 2.2
        r = np.sqrt(dx * dx + dy * dy)
        k = np.exp(-(r / rng.uniform(4, 7)) ** 2)
        col *= (1 - 0.45 * k)[..., None]
    # wysokość: lekkie wypuklenie klepki, szczelina wklęsła, włókna
    cup = np.sin(np.pi * np.clip(P["fy"] / P["h"], 0, 1)) * 0.8
    hgt = cup + 0.25 * fib + 0.15 * ring - 2.2 * seam - 0.6 * np.clip(2.5 - P["d_butt"], 0, 1) + 0.4 * tn
    nrm = normal_from_height(blur(hgt, 0.7), 1.2)
    rough = 0.78 + 0.06 * fib + 0.05 * dirt * 10 * 0.2 - 0.18 * seam + 0.04 * per_plank(P["plank_id"], seed + 3, 1)
    save(out, "poklad", np.clip(col, 0, 1), nrm, rough)


def tex_burta(n, out, seed=21):
    # kafel 8 m: 32 pasy po 0,25 m (64 px), wręgi co 0,5 m (16 na kafel), styki co pół kafla (klepki 4 m... 8 m),
    # przesunięcie 5 wręgów na pas (sąsiednie styki 2,5 m od siebie)
    P = planks(n, rows=32, butts_per_row=1, shift=5, frames=16, seed=seed, seam_px=2, tn_rows=2, tn_r=2.6)
    ring, fib = grain(n, seed + 5, along=700, rings=0.07, warp=60)
    pv = per_plank(P["plank_id"], seed + 7, 0.06)
    streak = fnoise(n, 30, 500, seed + 15)   # zacieki pionowe (w poprzek klepek)
    big = fnoise(n, 300, 300, seed + 16)
    tone = 1 + pv + 0.04 * fib + 0.025 * ring + 0.035 * streak + 0.03 * big
    seamd = np.minimum(P["d_seam"], P["d_butt"])
    seam = np.clip(1.3 - seamd, 0, 1)
    tn = np.clip(2.6 - P["d_tn"], 0, 1)
    rim = np.exp(-((P["d_tn"] - 2.8) ** 2) / 0.9)
    # naturalne: olejowany dąb
    base = srgb(146, 104, 64)
    col = base[None, None, :] * tone[..., None]
    hue = per_plank(P["plank_id"], seed + 8, 0.035)
    col[..., 0] *= 1 + hue
    col[..., 2] *= 1 - 1.5 * hue
    col = col * (1 - 0.1 * np.exp(-seamd / 4.0))[..., None]
    col = col * (1 - seam[..., None]) + srgb(34, 26, 18) * seam[..., None]
    col = col * (1 - 0.2 * rim[..., None])
    col = col * (1 - tn[..., None]) + srgb(120, 84, 50) * tn[..., None]
    hgt = 0.5 * np.sin(np.pi * np.clip(P["fy"] / P["h"], 0, 1)) + 0.25 * fib + 0.1 * ring - 1.6 * seam \
        - 0.5 * np.clip(2.0 - P["d_butt"], 0, 1) + 0.25 * tn - 0.3 * rim
    nrm = normal_from_height(blur(hgt, 0.7), 1.1)
    rough = 0.62 + 0.05 * fib + 0.04 * streak + 0.03 * pv * 10 * 0.3 - 0.1 * seam
    save(out, "burta", np.clip(col, 0, 1), nrm, rough)
    # farba na deskach: prawie biała (mnożona przez kolor materiału), szczeliny i kołki prześwitują lekko
    pcol = 0.9 + 0.025 * big + 0.02 * streak + 0.012 * fib + 0.02 * pv
    pcol = pcol - 0.25 * seam - 0.05 * rim
    chips = np.clip((fnoise(n, 6, 6, seed + 30) + 0.25 * fnoise(n, 60, 60, seed + 31)) - 2.6, 0, 1)
    pc = np.stack([pcol, pcol, pcol], -1)
    pc = pc * (1 - chips[..., None]) + (base * 0.9)[None, None, :] * chips[..., None]
    prough = 0.64 + 0.05 * big + 0.05 * streak + 0.25 * chips + 0.08 * seam
    Image.fromarray(np.clip(pc * 255 + 0.5, 0, 255).astype(np.uint8), "RGB").save(
        os.path.join(out, "farba_kolor.jpg"), quality=90, subsampling=0)
    rm = np.stack([np.ones((n, n)), np.clip(prough, 0, 1), np.zeros((n, n))], -1)
    Image.fromarray((rm * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(out, "farba_szorstkosc.jpg"),
                                                                   quality=90, subsampling=0)


def tex_drewno(n, out, seed=31):
    # drzewca i sprzęty: sosna pokostowana, kafel 2 m wzdłuż (u) × 2 m w obwodzie (v), bez szczelin
    ring, fib = grain(n, seed, along=900, rings=0.045, warp=90)
    fine = fnoise(n, 400, 0.8, seed + 2)
    big = fnoise(n, 400, 200, seed + 3)
    tone = 1 + 0.06 * fib + 0.06 * ring + 0.02 * fine + 0.05 * big
    base = srgb(160, 116, 72)
    col = base[None, None, :] * tone[..., None]
    # pęknięcia wzdłużne (checks)
    rng = np.random.default_rng(seed + 5)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    crack = np.zeros((n, n))
    for _ in range(9):
        cy, cx, L = rng.uniform(0, n), rng.uniform(0, n), rng.uniform(150, 600)
        dx = (xx - cx + n / 2) % n - n / 2
        dy = (yy - cy + n / 2) % n - n / 2 + 3 * np.sin(dx / 40)
        w = np.clip(1 - np.abs(dx) / (L / 2), 0, 1) * 1.6
        crack = np.maximum(crack, np.clip(w - np.abs(dy), 0, 1))
    col = col * (1 - 0.55 * crack[..., None])
    hgt = 0.35 * fib + 0.2 * ring + 0.15 * fine - 1.5 * crack
    nrm = normal_from_height(blur(hgt, 0.6), 1.0)
    rough = 0.55 + 0.05 * fib + 0.05 * big + 0.2 * crack
    save(out, "drewno", np.clip(col, 0, 1), nrm, rough)


def tex_zelazo(n, out, seed=41):
    # żelazo czernione, kafel 1 m: wżery, rdza w plamach
    a = fnoise(n, 80, 80, seed, "pow")
    b = fnoise(n, 6, 6, seed + 1)
    c = fnoise(n, 25, 25, seed + 2)
    rust = np.clip((0.6 * a + 0.4 * c) - 1.45, 0, 1)
    rust = np.clip(rust * 2.5, 0, 1)
    base = srgb(46, 44, 42) * (1 + 0.08 * b[..., None] + 0.06 * c[..., None])
    rc = srgb(112, 58, 30) * (1 + 0.15 * b[..., None])
    col = base * (1 - rust[..., None]) + rc * rust[..., None]
    pits = np.clip(-b - 1.8, 0, 1)
    hgt = 0.3 * c + 0.4 * rust + 0.2 * b - 1.0 * pits
    nrm = normal_from_height(blur(hgt, 1.0), 1.2)
    rough = 0.55 + 0.08 * c + 0.35 * rust
    metal = np.clip(0.75 - rust * 0.8, 0, 1)
    save(out, "zelazo", np.clip(col, 0, 1), nrm, rough, metal)


def tex_lina(n, out, seed=51):
    # lina 3-splotkowa: u wzdłuż (kafel = 2 skoki splotu), v w obwodzie (kafel = pełny obwód)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    U, V = xx / n, yy / n
    ph = (3 * V + 6 * U) % 1.0            # 3 splotki, 2 skoki na kafel
    s = np.abs(ph - 0.5) * 2               # 0 w środku splotki, 1 na rowku
    strand = np.sqrt(np.clip(1 - s ** 2, 0, 1))
    fph = (40 * V - 70 * U) % 1.0          # włókna w splotce (skręt przeciwny)
    fib = 0.5 + 0.5 * np.cos(2 * np.pi * fph)
    nz = fnoise(n, 12, 12, seed)
    hgt = 3.0 * strand + 0.35 * fib + 0.2 * nz
    nrm = normal_from_height(blur(hgt, 0.8), 2.0)
    tone = 0.78 + 0.18 * strand + 0.06 * fib + 0.04 * nz
    col = srgb(214, 200, 170)[None, None, :] * tone[..., None]
    col *= (1 - 0.35 * np.clip(s - 0.75, 0, 1) * 4)[..., None]
    rough = 0.82 + 0.06 * nz - 0.05 * strand
    save(out, "lina", np.clip(col, 0, 1), nrm, rough)


def tex_plotno(n, out, seed=61):
    # płótno żaglowe, kafel 2,4 m: 4 brytyki po 0,6 m (szwy wzdłuż v, czyli pionowo na żaglu), splot, plamy
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    cw = n / 4
    dseam = np.abs(((xx + cw / 2) % cw) - cw / 2)
    seam = np.exp(-((dseam - 0.0) ** 2) / 6) + 0.6 * np.exp(-((dseam - 12) ** 2) / 2) + 0.6 * np.exp(-((dseam + 12 - cw) ** 2) / 2)
    weave = 0.5 + 0.25 * np.sin(2 * np.pi * xx / 2.0) * np.sin(2 * np.pi * yy / 2.0)
    nz = fnoise(n, 3, 3, seed)
    big = fnoise(n, 200, 200, seed + 1)
    stain = np.clip(fnoise(n, 90, 140, seed + 2) - 1.2, 0, 1)
    tone = 0.92 + 0.03 * nz + 0.04 * big - 0.12 * stain - 0.06 * seam
    col = srgb(226, 214, 186)[None, None, :] * tone[..., None]
    hgt = 0.4 * nz + 0.3 * weave + 1.2 * seam + 0.4 * fnoise(n, 40, 40, seed + 3)
    nrm = normal_from_height(blur(hgt, 0.7), 1.0)
    rough = 0.88 + 0.04 * nz
    save(out, "plotno", np.clip(col, 0, 1), nrm, rough)


def tex_okno(n, out, seed=71):
    # okno skrzynkowe: 4 × 6 szybek w szprosach (kafel = całe okno), szkło lekko nierówne
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    U, V = xx / n, yy / n
    cu, cv = (U * 4) % 1.0, (V * 6) % 1.0
    du = np.minimum(cu, 1 - cu) * n / 4
    dv = np.minimum(cv, 1 - cv) * n / 6
    bar = np.clip(6 - np.minimum(du, dv), 0, 1)
    frame = np.clip(14 - np.minimum(np.minimum(xx, n - 1 - xx), np.minimum(yy, n - 1 - yy)), 0, 1)
    bar = np.maximum(bar, frame)
    ripple = fnoise(n, 30, 30, seed)
    glass = srgb(38, 48, 52)[None, None, :] * (1 + 0.15 * ripple[..., None])
    wood = srgb(52, 40, 30)[None, None, :]
    col = glass * (1 - bar[..., None]) + wood * bar[..., None]
    hgt = 2.5 * blur(bar, 2) + 0.3 * ripple * (1 - bar)
    nrm = normal_from_height(hgt, 1.5)
    rough = 0.08 + 0.02 * ripple + 0.6 * bar
    save(out, "okno", np.clip(col, 0, 1), nrm, rough)


ALL = {"poklad": tex_poklad, "burta": tex_burta, "drewno": tex_drewno, "zelazo": tex_zelazo, "lina": tex_lina,
       "plotno": tex_plotno, "okno": tex_okno}

if __name__ == "__main__":
    a = sys.argv[1:]
    out = a[0]
    size = int(a[a.index("--size") + 1]) if "--size" in a else 2048
    only = a[a.index("--only") + 1].split(",") if "--only" in a else list(ALL)
    force = "--force" in a
    done = {}
    for k in only:
        nsz = 512 if k == "okno" else size
        if not force and os.path.exists(os.path.join(out, k + "_kolor.jpg")):
            continue
        ALL[k](nsz, out)
        done[k] = nsz
    print("TEKSTURY " + json.dumps({"zrobione": done, "kafel_m": KAFEL}))
