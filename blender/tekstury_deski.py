"""Tekstury materiałów z fotografii CC0 (Poly Haven) i naszego układu desek (zwykły Python: numpy + PIL).

    python blender/tekstury_deski.py <katalog_tekstur_cc0> <build/tekstury_cc0>

Pobranych plików nie zmienia; wyniki (JPEG, prefiks td_) obok kopii roboczych tekstury_cc0.py, spis w _td.json.

Atlasy desek (deski.py tnie siatkę według tego samego układu – parametry.DESKI):
  td_burta_*      poszycie i nadburcie, dąb olejowany: R rzędów (deski) po szer m, długość L_tex (wielokrotność odstępu
                  wręgów); w każdym rzędzie pas jednej deski ze zdjęcia (wnętrze deski między jej szwami, bez styków,
                  bez własnych szwów zdjęcia), przeskalowany izotropowo do naszej szerokości i powtórzony wzdłuż tyle razy,
                  ile się mieści (dociągnięcie ≤ 15 %); szwy uszczelnione na granicach rzędów (dychtunek: ciemny, rowek
                  w mapie normalnych, zaokrąglone krawędzie desek), kołki parami na wręgach (u = j·krok + KOLEK_U)
  td_farba_<k>_*  farba na tych samych deskach: słoje i szwy widoczne pod farbą, przetarcia do drewna na krawędziach
                  desek i w plamach, chropowatość farby; kolory: czarna (smoła z sadzą), ochra, biała (white stuff), …
  td_poklad_*     pokład: wyszorowane deski (szaro-beżowe), ciemny dychtunek, kołki nad pokładnikami
Materiały elementów (kafelkowane, bez szwów):
  td_drewno_*     dąb olejowany wyposażenia (mnożnik koloru daje odmiany jaśniejsze i ciemniejsze)
  td_sosna_*      drzewca: sosna / jodła olejowana, ciepła, z pęknięciami wzdłużnymi
  td_laweta_*     laweta: czerwona ochra na dębie, przetarta do drewna
  td_zelazo_*     żelazo czernione: ciemny szary z rdzą tylko w zagłębieniach (mapa okluzji zdjęcia), chropowatość 0,5–0,7
  td_farba_gladka_*  farba bez desek (rzeźby, listwy): jasna, mnożona kolorem materiału; zagłębienia daje AO
  td_plotno_*     płótno: splot ze zdjęcia, fałdy wzdłuż wałka (u) w mapie normalnych, lekkie zabrudzenie
Każdy zestaw: _kolor (sRGB), _normalne (OpenGL), _orm (R – okluzja ze zdjęcia, G – chropowatość, B – metaliczność).
Bez wypalonego światła: kolor to albedo zdjęcia po wyrównaniu (zdjęcia Poly Haven są albedo), rzeźba tylko w normalnych.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametry as PR  # noqa: E402
from tekstury import fnoise, blur  # noqa: E402
from tekstury_cc0 import sloje_kierunek, wczytaj_spis  # noqa: E402

KOLEK_U = 0.07           # m za linią wręgu / pokładnika (styk klepek leży na linii, kołki obok)
Q_KOLOR, Q_NRM, Q_ORM = 84, 88, 84


def fnoise_r(H, W, sx, sy, seed):
    """Okresowy szum H×W (długość korelacji sx wzdłuż x, sy wzdłuż y, px); średnia 0, odchylenie 1."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((H, W)).astype(np.float32)
    kx = np.fft.rfftfreq(W)[None, :]
    ky = np.fft.fftfreq(H)[:, None]
    f = np.exp(-((kx * sx * np.pi) ** 2 + (ky * sy * np.pi) ** 2)).astype(np.float32)
    r = np.fft.irfft2(np.fft.rfft2(w) * f, s=(H, W))
    r -= r.mean()
    return r / (r.std() + 1e-9)


def blur_r(a, s):
    H, W = a.shape
    kx = np.fft.rfftfreq(W)[None, :]
    ky = np.fft.fftfreq(H)[:, None]
    f = np.exp(-2 * (np.pi * s) ** 2 * (kx ** 2 + ky ** 2))
    return np.fft.irfft2(np.fft.rfft2(a) * f, s=(H, W))


def normal_r(h, strength):
    """Wysokość → wektory normalnych OpenGL (prostokątne, okresowe)."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    dr = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    v = np.stack([-dx * strength, dr * strength, np.ones_like(h)], -1)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


# ---------------------------------------------------------------- wejście
def wczytaj(src, spis, tid):
    """(kolor, normalne, arm) jako float 0..1, obrócone tak, by słoje szły wzdłuż x (u); px/m."""
    e = spis[tid]
    d = os.path.join(src, tid)
    col = np.asarray(Image.open(os.path.join(d, e["pliki"]["diff"])).convert("RGB"), np.float64) / 255
    nor = np.asarray(Image.open(os.path.join(d, e["pliki"]["nor_gl"])).convert("RGB"), np.float64) / 255
    arm = np.asarray(Image.open(os.path.join(d, e["pliki"]["arm"])).convert("RGB"), np.float64) / 255
    n = min(col.shape[0], col.shape[1])
    col, nor, arm = col[:n, :n], nor[:n, :n], arm[:n, :n]
    if sloje_kierunek(col.mean(-1) * 255):
        col, arm = np.rot90(col), np.rot90(arm)
        nr = np.rot90(nor).copy()
        r, g = nr[..., 0].copy(), nr[..., 1].copy()
        nr[..., 0] = 1 - g
        nr[..., 1] = r
        nor = nr
    return col, nor, arm, n / e["kafel_m"][0]


def _medfilt1(p, w):
    """Mediana ruchoma okresowa (1D)."""
    h = w // 2
    q = np.concatenate([p[-h:], p, p[:h]])
    win = np.lib.stride_tricks.sliding_window_view(q, w)
    return np.median(win, axis=1)


def pasy_desek(col, pxm, min_szer=0.12):
    """Wnętrza desek ze zdjęcia: [(y0, y1)] (px, bez szwów i krawędzi), tylko deski bez styków w obrębie kafla."""
    L = col.mean(-1)
    p = L.mean(1)
    d = p - _medfilt1(p, int(0.06 * pxm) | 1)
    thr = -2.0 * d.std()
    H = len(p)
    sep = int(0.07 * pxm)
    mins = []
    for y in np.argsort(d):
        if d[y] > thr:
            break
        if all(min(abs(y - m), H - abs(y - m)) > sep for m in mins):
            mins.append(int(y))
    mins.sort()
    out = []
    marg = int(0.012 * pxm) + 2
    for i, a in enumerate(mins):
        b = mins[(i + 1) % len(mins)] + (H if i + 1 == len(mins) else 0)
        y0, y1 = a + marg, b - marg
        if (y1 - y0) / pxm < min_szer:
            continue
        rows = np.arange(y0, y1) % H
        q = np.median(L[rows], 0)        # mediana: łby gwoździ (kilka wierszy) nie udają styku
        dq = q - _medfilt1(q, int(0.05 * pxm) | 1)
        if dq.min() < -5.0 * dq.std():       # ciemna pionowa kreska = styk w obrębie kafla
            continue
        out.append((y0, y1))
    return out


def _resize(a, w, h):
    """Zmiana rozmiaru tablicy float (H, W, C) przez PIL (LANCZOS) na kanał."""
    out = []
    for c in range(a.shape[2]):
        im = Image.fromarray(a[..., c].astype(np.float32), "F")
        out.append(np.asarray(im.resize((w, h), Image.Resampling.LANCZOS), np.float64))
    return np.stack(out, -1)


def wiersz(col, nor, arm, pxm, pas, L_tex, szer, W, Hrow):
    """Rząd atlasu (Hrow × W px) z jednej deski zdjęcia: skala izotropowa do naszej szerokości, powtórzenia wzdłuż."""
    y0, y1 = pas
    H = col.shape[0]
    rows = np.arange(y0, y1) % H
    strip = [a[rows] for a in (col, nor, arm)]
    hs = (y1 - y0) / pxm
    Ls = col.shape[1] / pxm
    f = szer / hs
    n_rep = max(1, int(round(L_tex / (Ls * f))))
    Wr = int(round(W / n_rep))
    anizo = (L_tex / n_rep) / (Ls * f)
    out = []
    for a in strip:
        r = _resize(a, Wr, Hrow)
        r = np.concatenate([r] * n_rep, 1)
        if r.shape[1] != W:
            r = _resize(r, W, Hrow)
        out.append(r)
    return out, dict(powtorzenia=n_rep, dociagniecie=round(anizo, 3), px_m_zrodla=round(pxm / f, 0))


def nrm_dec(n):
    v = n * 2 - 1
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def nrm_enc(v):
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return np.clip((v * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)


def nrm_mix(a, b):
    """Połączenie map normalnych (whiteout): a, b – wektory."""
    return np.stack([a[..., 0] + b[..., 0], a[..., 1] + b[..., 1], a[..., 2] * b[..., 2]], -1)


def nrm_sila(v, s):
    return np.stack([v[..., 0] * s, v[..., 1] * s, v[..., 2]], -1)


def grade(col, cel, kontrast=1.0, nasycenie=0.5):
    """Wyrównanie zdjęcia do docelowego średniego koloru (sRGB 0..1): odchyłki jasności zachowane (× kontrast),
    barwa zdjęcia przemieszana z neutralną (nasycenie 0 – tylko jasność zdjęcia)."""
    m = col.reshape(-1, 3).mean(0)
    c = col / np.maximum(m, 1e-4)
    Lr = c.mean(-1, keepdims=True)
    c = Lr * (1 - nasycenie) + c * nasycenie
    c = 1 + (c - 1) * kontrast
    c = np.where(c > 1, 1 + (1 - np.exp(-(c - 1) * 2.5)) / 2.5, c)     # miękkie światła (bez jaskrawych plam)
    return np.clip(np.array(cel)[None, None, :] * c, 0, 1)


def zapisz(dst, nazwa, kol, nrm_v, orm, info):
    Image.fromarray(np.clip(kol * 255 + 0.5, 0, 255).astype(np.uint8), "RGB").save(
        os.path.join(dst, nazwa + "_kolor.jpg"), quality=Q_KOLOR, subsampling=0)
    if nrm_v is not None:
        Image.fromarray(nrm_enc(nrm_v), "RGB").save(os.path.join(dst, nazwa + "_normalne.jpg"), quality=Q_NRM,
                                                    subsampling=0)
    if orm is not None:
        Image.fromarray(np.clip(orm * 255 + 0.5, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(dst, nazwa + "_orm.jpg"), quality=Q_ORM, subsampling=0)
    info["pliki"] = [nazwa + s for s in ("_kolor.jpg", "_normalne.jpg", "_orm.jpg")]
    return info


# ---------------------------------------------------------------- atlas desek
def atlas(src, spis, tid, U, W=4096, H=1024, pomin=0, seed=1):
    """Surowy atlas desek (kolor, normalne – wektory, arm) + pola układu (odległość do szwu, kołki)."""
    col, nor, arm, pxm = wczytaj(src, spis, tid)
    pasy = pasy_desek(col, pxm)
    if not pasy:
        raise RuntimeError("brak desek w " + tid)
    pasy = sorted(pasy, key=lambda p: -(p[1] - p[0]))
    R = U["rzedy"]
    Hrow = H // R
    kol, nr, ar, opis = [], [], [], []
    for r in range(R):
        p = pasy[(r + pomin) % len(pasy)]
        (c, n, a), inf = wiersz(col, nor, arm, pxm, p, U["L_tex"], U["szer"], W, Hrow)
        # przesunięcie wzdłuż (inne miejsce deski w każdym rzędzie)
        sh = int((r * 0.37 + seed * 0.19) % 1.0 * W)
        kol.append(np.roll(c, sh, 1)); nr.append(np.roll(n, sh, 1)); ar.append(np.roll(a, sh, 1))
        opis.append(inf)
    kol, nr, ar = np.concatenate(kol, 0), np.concatenate(nr, 0), np.concatenate(ar, 0)
    pxm_t = W / U["L_tex"]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    fy = yy % Hrow
    d_szew = np.minimum(fy + 0.5, Hrow - fy - 0.5) / pxm_t          # m do najbliższego szwu wzdłużnego
    # kołki: parami na każdym wręgu / pokładniku
    kr = U["krok"] * pxm_t
    cen = []
    rng = np.random.default_rng(seed)
    nk = int(round(U["L_tex"] / U["krok"]))
    for r in range(R):
        for j in range(nk):
            for t in (0.3, 0.7):
                cen.append((r * Hrow + t * Hrow + rng.normal(0, 0.6), (j * kr + KOLEK_U * pxm_t + rng.normal(0, 0.8)) % W))
    rk = 0.019 * pxm_t
    # pole odległości do kołków (okresowe; disc_field liczy w kwadracie n×n – tu prostokąt, więc ręcznie)
    d_k = np.full((H, W), 1e9)
    ri = int(rk * 3) + 2
    for (cy, cx) in cen:
        ys = np.arange(int(cy) - ri, int(cy) + ri + 1)
        xs = np.arange(int(cx) - ri, int(cx) + ri + 1)
        dd = np.sqrt((ys[:, None] - cy) ** 2 + (xs[None, :] - cx) ** 2)
        blk = np.ix_(ys % H, xs % W)
        d_k[blk] = np.minimum(d_k[blk], dd)
    return dict(kol=kol, nrm=nrm_dec(nr), arm=ar, d_szew=d_szew, d_kolek=d_k / pxm_t, rk=0.019, pxm=pxm_t,
                zrodlo=tid, rzedy=opis, H=H, W=W)


def struktura(A, U, glebokosc=1.0):
    """Wysokość (m·1000 ≈ mm) i maski: rowek szwu (dychtunek), zaokrąglenie krawędzi, kołki."""
    hw = U["szew"] / 2
    ds = A["d_szew"]
    rowek = np.clip(1 - ds / hw, 0, 1)                          # 1 w osi szwu
    krawedz = np.clip(1 - (ds - hw) / 0.006, 0, 1) * (ds > hw)  # 6 mm zaokrąglenia przy szwie
    kolek = np.clip((A["rk"] - A["d_kolek"]) / 0.002, 0, 1)
    obw = np.exp(-((A["d_kolek"] - A["rk"]) / 0.0025) ** 2)
    h = -2.5 * rowek ** 0.7 - 1.2 * krawedz ** 2 - 0.25 * obw + 0.15 * kolek
    return h * glebokosc, rowek, krawedz, kolek, obw


def nrm_ze_struktury(h, pxm, sila=1.0):
    """Wysokość w mm → wektory normalnych (nachylenie na px)."""
    return normal_r(blur_r(h, 0.6), sila * 1000.0 / pxm)


def deski_drewno(A, U, cel, kontrast, nasycenie, szew_kol, kolek_kol, chrop, seed):
    """Drewno desek (bez farby) z układu A."""
    h, rowek, kraw, kolek, obw = struktura(A, U)
    kol = grade(A["kol"], cel, kontrast, nasycenie)
    H, W = A["H"], A["W"]
    # duża skala: plamy wilgoci / przebarwień (okresowe), lekko
    big = fnoise_r(H, W, 400, 160, seed)
    kol = kol * (1 + 0.05 * big[..., None])
    kol = kol * (1 - 0.18 * kraw[..., None])                     # brud przy szwach
    kol = kol * (1 - rowek[..., None]) + np.array(szew_kol)[None, None, :] * rowek[..., None]
    # kołek: czoło drewna – gładszy, jaśniejszy krążek o średnim kolorze deski, cienka ciemna obwódka
    sr = kol.reshape(-1, 3).mean(0)
    czolo = (sr * np.array(kolek_kol))[None, None, :] * (1 + 0.06 * fnoise_r(H, W, 3, 3, seed + 5))[..., None]
    kol = kol * (1 - 0.10 * obw[..., None])
    kol = kol * (1 - 0.5 * kolek[..., None]) + czolo * 0.5 * kolek[..., None]
    n = nrm_mix(A["nrm"], nrm_ze_struktury(h, A["pxm"]))
    g = A["arm"][..., 1]
    g = chrop[0] + (g - g.mean()) * chrop[1]
    g = g * (1 - rowek) + chrop[2] * rowek
    orm = np.stack([np.ones_like(g), np.clip(g, 0.05, 1), np.zeros_like(g)], -1)
    return kol, n, orm


def deski_farba(A, U, drewno_kol, farba, chrop_farby, seed, przetarcie=1.0):
    """Farba na deskach: kolor farby z lekkim prześwitem słojów, przetarcia do drewna (krawędzie desek, plamy),
    rowek szwu z ciemną farbą i brudem; normalne słojów osłabione (farba je wypełnia)."""
    h, rowek, kraw, kolek, obw = struktura(A, U)
    H, W = A["H"], A["W"]
    Lw = A["kol"].mean(-1)
    Lw = (Lw - Lw.mean()) / (Lw.std() + 1e-6)
    pedzel = fnoise_r(H, W, 260, 6, seed + 1)                     # pociągnięcia pędzla wzdłuż desek
    plamy = fnoise_r(H, W, 90, 60, seed + 2)
    drob = fnoise_r(H, W, 5, 5, seed + 3)
    F = np.array(farba)[None, None, :]
    jas = 1 + 0.035 * Lw + 0.03 * pedzel + 0.025 * plamy
    kol = F * jas[..., None]
    # przetarcia: przy krawędziach desek i w plamach (próg na szumie), drobne odpryski
    m = np.clip((0.55 * plamy + 0.45 * drob + 1.6 * kraw ** 0.5 - 1.75) * 3.0, 0, 1) * przetarcie
    m = np.maximum(m, np.clip((drob - 2.6) * 2, 0, 1) * przetarcie)
    kol = kol * (1 - m[..., None]) + drewno_kol * m[..., None]
    kol = kol * (1 - 0.12 * kraw[..., None])
    szew = F * 0.35 + 0.02
    kol = kol * (1 - rowek[..., None]) + szew * rowek[..., None]
    kol = kol * (1 - 0.03 * obw[..., None])
    hp = h * np.where(rowek > 0, 1.0, 1.0) - 0.15 * obw + 0.25 * (1 - m)                                        # warstwa farby (krawędź odprysku)
    n = nrm_mix(nrm_sila(A["nrm"], 0.45), nrm_ze_struktury(hp, A["pxm"]))
    g = chrop_farby + 0.04 * pedzel + 0.03 * plamy
    g = g * (1 - m) + 0.78 * m
    g = g * (1 - rowek) + (chrop_farby + 0.1) * rowek
    orm = np.stack([np.ones_like(g), np.clip(g, 0.05, 1), np.zeros_like(g)], -1)
    return kol, n, orm, float(m.mean())


# ---------------------------------------------------------------- kafle bez szwów (elementy)
def kafel(src, spis, tid, L, N=2048, obrot=False):
    """Kafel N×N obejmujący L m ze zdjęcia (słoje wzdłuż u), z powtórzeniem całkowitym (L / kafel zdjęcia)."""
    col, nor, arm, pxm = wczytaj(src, spis, tid)
    Ls = col.shape[0] / pxm
    n_rep = max(1, int(round(L / Ls)))
    out = []
    for a in (col, nor, arm):
        t = np.concatenate([np.concatenate([a] * n_rep, 1)] * n_rep, 0)
        out.append(_resize(t, N, N))
    return out[0], nrm_dec(out[1]), out[2], dict(zrodlo=tid, powtorzenia=n_rep, dociagniecie=round(L / (n_rep * Ls), 3))


def kafel_z_desek(src, spis, tid, L=2.0, N=2048, h=0.25, min_szer=0.06, ov=24, pomin=0):
    """Kafel bez szwów z wnętrz desek zdjęcia: pasy o wysokości h m ułożone jeden nad drugim (L/h pasów), każdy
    powtórzony wzdłuż (bez styków), przejścia między pasami miękkie (ov px) – prawdziwe słoje bez szwów zdjęcia."""
    col, nor, arm, pxm = wczytaj(src, spis, tid)
    pasy = pasy_desek(col, pxm, min_szer)
    n_p = int(round(L / h))
    Hrow = N // n_p
    acc = [np.zeros((N, N, 3)) for _ in range(3)]
    wsum = np.zeros((N, 1))
    info = []
    for k in range(n_p):
        p = pasy[(k * 3 + pomin) % len(pasy)]
        Hr = Hrow + 2 * ov
        (c, n, a), inf = wiersz(col, nor, arm, pxm, p, L, h * Hr / Hrow, N, Hr)
        sh = int((k * 0.41 + 0.13) % 1.0 * N)
        rows = (np.arange(Hr) + k * Hrow - ov) % N
        t = np.arange(Hr)
        w = np.clip(np.minimum(t + 1, Hr - t) / (2 * ov), 0, 1)
        w = (w * w * (3 - 2 * w))[:, None]
        for i, arr in enumerate((c, n, a)):
            np.add.at(acc[i], rows, np.roll(arr, sh, 1) * w[..., None])
        np.add.at(wsum, rows, w)
        info.append(inf)
    c, n, a = (x / np.maximum(wsum[..., None], 1e-6) for x in acc)
    return c, nrm_dec(n), a, dict(zrodlo=tid, pasy=len(pasy), dociagniecie=[i["dociagniecie"] for i in info])


def peknięcia(N, seed, ile=10, dl=(200, 700)):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float64)
    cr = np.zeros((N, N))
    for _ in range(ile):
        cy, cx, L = rng.uniform(0, N), rng.uniform(0, N), rng.uniform(*dl)
        dx = (xx - cx + N / 2) % N - N / 2
        dy = (yy - cy + N / 2) % N - N / 2 + 2.5 * np.sin(dx / 50)
        w = np.clip(1 - np.abs(dx) / (L / 2), 0, 1) * 1.3
        cr = np.maximum(cr, np.clip(w - np.abs(dy), 0, 1))
    return cr


def main():
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    spis = wczytaj_spis(src)
    T = PR.TEKSTURY_TD
    info = {}
    D = PR.DESKI
    # --- poszycie: dąb olejowany
    Ub = D["burta"]
    A = atlas(src, spis, T["burta"]["zrodlo"], Ub, pomin=0, seed=3)
    kb, nb, ob = deski_drewno(A, Ub, T["burta"]["kolor"], 1.25, 0.25, (0.05, 0.035, 0.025), (1.12, 1.08, 1.0),
                              (0.62, 0.9, 0.5), 11)
    info["td_burta"] = zapisz(dst, "td_burta", kb, nb, ob, dict(zrodlo=A["zrodlo"], rzedy=A["rzedy"], px_m=A["pxm"]))
    # --- farby na deskach (ten sam układ i te same deski co poszycie)
    for nazwa, f in T["farby"].items():
        kf, nf, of, mm = deski_farba(A, Ub, kb, f["kolor"], f["chrop"], 21, f.get("przetarcie", 1.0))
        info["td_farba_" + nazwa] = zapisz(dst, "td_farba_" + nazwa, kf, nf, of,
                                           dict(zrodlo=A["zrodlo"], przetarte=round(mm, 3), px_m=A["pxm"]))
    # --- pokład: wyszorowane deski
    Up = D["poklad"]
    A2 = atlas(src, spis, T["poklad"]["zrodlo"], Up, pomin=2, seed=5)
    kp, np_, op = deski_drewno(A2, Up, T["poklad"]["kolor"], 1.15, 0.2, (0.06, 0.05, 0.045), (1.08, 1.06, 1.02),
                               (0.80, 0.6, 0.55), 13)
    info["td_poklad"] = zapisz(dst, "td_poklad", kp, np_, op, dict(zrodlo=A2["zrodlo"], rzedy=A2["rzedy"],
                                                                     px_m=A2["pxm"]))
    # --- dąb wyposażenia
    t = T["drewno"]
    c, n, a, inf = kafel_z_desek(src, spis, t["zrodlo"], t["kafel"], h=t["pas"], min_szer=t["min_szer"])
    N_ = c.shape[0]
    big = fnoise(N_, 500, 200, 31)
    zab = fnoise(N_, 40, 25, 32)
    k = grade(c, t["kolor"], 0.95, 0.3) * (1 + 0.06 * big[..., None] - 0.04 * np.clip(zab, 0, None)[..., None])
    cr = peknięcia(N_, 33, 8, (120, 420))
    k = k * (1 - 0.5 * cr[..., None])
    nn = nrm_mix(n, nrm_ze_struktury(-1.2 * cr + 0.08 * fnoise(N_, 300, 1.2, 34), N_ / t["kafel"]))
    g = np.clip(0.58 + (a[..., 1] - a[..., 1].mean()) * 0.8 + 0.05 * big + 0.15 * cr, 0.05, 1)
    info["td_drewno"] = zapisz(dst, "td_drewno", k, nn, np.stack([1 + 0 * g, blur(g, 1.0), 0 * g], -1), dict(inf, px_m=N_ / t["kafel"]))
    # --- laweta: czerwona ochra na dębie, przetarta
    plamy = fnoise(N_, 70, 50, 41)
    drob = fnoise(N_, 4, 4, 42)
    m = np.clip((0.6 * plamy + 0.4 * drob - 1.05) * 2.5, 0, 1)
    F = np.array(T["laweta"]["kolor"])[None, None, :]
    Lw = k.mean(-1)
    kl = F * (1 + 0.45 * (Lw / Lw.mean() - 1))[..., None] * (1 + 0.04 * fnoise(N_, 200, 5, 43))[..., None]
    kl = kl * (1 - m[..., None]) + k * m[..., None]
    nl = nrm_mix(nrm_sila(nn, 0.5), nrm_ze_struktury(0.3 * (1 - m), N_ / t["kafel"]))
    gl = np.clip(0.6 * (1 - m) + g * m, 0.05, 1)
    info["td_laweta"] = zapisz(dst, "td_laweta", kl, nl, np.stack([1 + 0 * gl, blur(gl, 1.0), 0 * gl], -1),
                               dict(inf, przetarte=round(float(m.mean()), 3)))
    # --- sosna drzewc
    t = T["sosna"]
    c, n, a, inf = kafel_z_desek(src, spis, t["zrodlo"], t["kafel"], h=t["pas"], min_szer=t["min_szer"], pomin=1)
    big = fnoise(N_, 600, 150, 51)
    zab = fnoise(N_, 60, 8, 52)
    k = grade(c, t["kolor"], 0.9, 0.3) * (1 + 0.07 * big[..., None] - 0.05 * np.clip(zab, 0, None)[..., None])
    cr = peknięcia(N_, 53, 12, (250, 900))
    k = k * (1 - 0.55 * cr[..., None])
    nn = nrm_mix(n, nrm_ze_struktury(-1.5 * cr + 0.1 * fnoise(N_, 400, 1.0, 54), N_ / t["kafel"]))
    g = np.clip(0.55 + (a[..., 1] - a[..., 1].mean()) * 0.8 + 0.06 * big + 0.15 * cr, 0.05, 1)
    info["td_sosna"] = zapisz(dst, "td_sosna", k, nn, np.stack([1 + 0 * g, blur(g, 1.0), 0 * g], -1), dict(inf, px_m=N_ / t["kafel"]))
    # --- żelazo czernione
    t = T["zelazo"]
    c, n, a, inf = kafel(src, spis, t["zrodlo"], t["kafel"], N=t.get("N", 2048))
    N_ = c.shape[0]
    L = c.mean(-1)
    Ln = (L - L.mean()) / (L.std() + 1e-6)
    ao = a[..., 0]
    p15 = np.percentile(ao, 15)
    rdza = np.clip((p15 - ao) / max(p15 - np.percentile(ao, 2), 1e-3), 0, 1) * np.clip(0.6 + 0.5 * fnoise(N_, 30, 30, 61), 0, 1)
    baza = np.array(t["kolor"])[None, None, :] * (1 + 0.10 * Ln + 0.06 * fnoise(N_, 120, 120, 62))[..., None]
    rdza = blur(rdza, 1.5) * 0.6
    kz = baza * (1 - rdza[..., None]) + np.array(t["rdza"])[None, None, :] * (1 + 0.2 * Ln)[..., None] * rdza[..., None]
    nz = nrm_sila(n, 0.6)
    gz = np.clip(0.58 + 0.06 * Ln + 0.15 * rdza, 0.3, 0.9)
    mz = np.clip(t["metal"] * (1 - rdza), 0, 1)
    info["td_zelazo"] = zapisz(dst, "td_zelazo", np.clip(kz, 0, 1), nz, np.stack([ao, gz, mz], -1),
                               dict(inf, rdza=round(float(rdza.mean()), 3)))
    # lufy: ta sama powierzchnia, gładsza (lekki połysk)
    Image.fromarray(np.clip(np.stack([ao, gz * 0.78, mz], -1) * 255 + 0.5, 0, 255).astype(np.uint8), "RGB").save(
        os.path.join(dst, "td_zelazo_lufa_orm.jpg"), quality=Q_ORM, subsampling=0)
    # --- farba gładka (rzeźby, listwy): jasna, mnożona kolorem materiału
    N_ = 1024
    pedzel = fnoise(N_, 160, 4, 71)
    plamy = fnoise(N_, 60, 60, 72)
    kg = np.clip(0.88 + 0.03 * pedzel + 0.03 * plamy, 0, 1)
    ng = nrm_ze_struktury(0.15 * pedzel + 0.1 * fnoise(N_, 3, 3, 73), N_ / 1.0)
    gg = np.clip(0.5 + 0.05 * plamy + 0.03 * pedzel, 0.05, 1)
    info["td_farba_gladka"] = zapisz(dst, "td_farba_gladka", np.stack([kg] * 3, -1), ng,
                                     np.stack([np.ones_like(gg), gg, 0 * gg], -1), dict(px_m=N_))
    # farba czarna (reling, listwy): matowsza – smoła z sadzą, chropowatość ok. 0,68
    Image.fromarray(np.clip(np.stack([np.ones_like(gg), gg + 0.18, 0 * gg], -1) * 255 + 0.5, 0, 255).astype(np.uint8),
                    "RGB").save(os.path.join(dst, "td_farba_gladka_mat_orm.jpg"), quality=Q_ORM, subsampling=0)
    # brąz (piasta koła, okucia): ta sama powierzchnia, metal, chropowatość 0,3–0,4
    Image.fromarray(np.clip(np.stack([np.ones_like(gg), 0.36 + 0.05 * plamy, 0.95 + 0 * gg], -1) * 255 + 0.5, 0, 255)
                    .astype(np.uint8), "RGB").save(os.path.join(dst, "td_braz_orm.jpg"), quality=Q_ORM, subsampling=0)
    # --- płótno: splot ze zdjęcia, fałdy wzdłuż u
    t = T["plotno"]
    c, n, a, inf = kafel(src, spis, t["zrodlo"], t["kafel"], N=1024)
    N_ = c.shape[0]
    Lc = c.mean(-1)
    Lc = (Lc - Lc.mean()) / (Lc.std() + 1e-6)
    # fałdy wzdłuż u: krótsze i słabsze niż w rundzie tekstur (380 px / normalne × 6 dawały na zwiniętych żaglach
    # miękkie, smugowate pasy jak rozmazana farba) – splot ze zdjęcia zostaje widoczny
    fald = fnoise(N_, 150, 30, 81) + 0.5 * fnoise(N_, 60, 18, 82)
    brud = np.clip(fnoise(N_, 160, 90, 83) - 0.6, 0, None)
    kp = np.array(t["kolor"])[None, None, :] * (1 + 0.05 * Lc - 0.10 * brud + 0.015 * fald)[..., None]
    npl = nrm_mix(nrm_sila(n, 0.9), nrm_ze_struktury(1.8 * fald, N_ / t["kafel"], 1.0))
    gp = np.clip(0.85 + 0.03 * Lc, 0.05, 1)
    info["td_plotno"] = zapisz(dst, "td_plotno", np.clip(kp, 0, 1), npl, np.stack([1 + 0 * gp, gp, 0 * gp], -1), inf)
    with open(os.path.join(dst, "_td.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1, default=float)
    print("TD " + json.dumps({k: v.get("zrodlo") for k, v in info.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
