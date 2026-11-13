"""Dane do chodzenia i stanowiska czynności → <out>/bryg_poklad.json oraz puste obiekty stan_* (węzły GLB).

Osie jak w węzłach GLB (glTF, +Y w górę): x – w stronę lewej burty (bakburty, +), y – w górę od linii wody,
z – ku dziobowi; metry; środek długości pokładu z = 0. Z układu statku (x, s, z): GLB (x, z, s).

Zawartość: powierzchnie (pokład główny, pokład rufowy, marsy, ławy wantowe) jako wielokąty w rzucie + wzór
i siatka wysokości co 0,5 m; schody, wspinaczka (wanty z wyblinkami, podwantki), przejścia pod pokład; przeszkody
(okrąg/prostokąt z obrotem, wysokość, nazwa obiektu); krawędź burty i wysokość relingu; stanowiska (stopy, kierunek
patrzenia, obiekt ruchomy, oś, zakres, wysokość rąk); wynik testów ergonomii (postać r = 0,3 m, 1,75 m wzrostu).
Pusty obiekt stanowiska: lokalna −Y Blendera (w GLB: +Z węzła) = kierunek patrzenia postaci.
"""
import json
import math
import os
from collections import deque

import bpy
import numpy as np
from mathutils import Vector

import narzedzia as N
from narzedzia import P
from wyposazenie import stanowisko, deck, inner_x

R_POSTACI = 0.30
WZROST = 1.75
KROK_SIATKI = 0.10


def g(x, s, z):
    return [round(float(x), 3), round(float(z), 3), round(float(s), 3)]


# ---------------------------------------------------------------- powierzchnie
def obrys_pokladu(ctx):
    ps = ctx["poszycie"]
    kd = ctx["kd"]
    K = ctx["K"]
    # pokład główny: od progu półpokładu do grodzi dziobowej, krawędź = nadburcie od środka (przy ścieku)
    r = ps.r_deck
    cs = range(ps.c_qd, ps.c_in1 + 1)
    port = [(float(ps.xin[r, c]), float(ps.sin[r, c])) for c in cs]
    main = port + [(-x, s) for (x, s) in reversed(port)]
    r = ps.r_qd
    cs = range(0, ps.c_qd + 1)
    port = [(float(ps.xin[r, c]), float(ps.sin[r, c])) for c in cs]
    qd = port + [(-x, s) for (x, s) in reversed(port)]
    return main, qd


def inside(poly, x, s):
    n = len(poly)
    c = False
    j = n - 1
    for i in range(n):
        xi, si = poly[i]
        xj, sj = poly[j]
        if ((si > s) != (sj > s)) and (x < (xj - xi) * (s - si) / (sj - si + 1e-12) + xi):
            c = not c
        j = i
    return c


def dist_poly(poly, x, s):
    best = 1e9
    n = len(poly)
    for i in range(n):
        x0, s0 = poly[i]
        x1, s1 = poly[(i + 1) % n]
        dx, ds = x1 - x0, s1 - s0
        t = max(0, min(1, ((x - x0) * dx + (s - s0) * ds) / (dx * dx + ds * ds + 1e-12)))
        best = min(best, math.hypot(x - x0 - t * dx, s - s0 - t * ds))
    return best


def obst_dist(o, x, s):
    """Odległość punktu od przeszkody (0 wewnątrz)."""
    if o["typ"] == "kolo":
        return max(0.0, math.hypot(x - o["x"], s - o["s"]) - o["wym"])
    L, W = o["wym"]
    c, sn = math.cos(o["rot"]), math.sin(o["rot"])
    dx, ds = x - o["x"], s - o["s"]
    u = ds * c + dx * sn          # wzdłuż długości (L wzdłuż s przy rot = 0)
    v = -ds * sn + dx * c
    qu = max(abs(u) - L / 2, 0)
    qv = max(abs(v) - W / 2, 0)
    return math.hypot(qu, qv)


# ---------------------------------------------------------------- stanowiska dodatkowe
def stanowiska_takielunku(ctx):
    rig = ctx["rig"]
    ps = ctx["poszycie"]
    O = ctx["PR"].OLINOWANIE
    # kołkownice i nagielbanki: po stanowisku na grupę lin
    groups = {}
    for b in ctx.get("belay", []):
        groups.setdefault((b["pool"], b["grupa"]), []).append(b)
    for (pool, grupa), lst in sorted(groups.items()):
        xs = np.mean([b["p"][0] for b in lst])
        ss = np.mean([b["p"][1] for b in lst])
        if pool.startswith("nagielbank"):
            # stań z boku nagielbanku (od strony burty, z której schodzą liny)
            sgn = 1 if xs >= 0 else -1
            ph = ctx["PR"].UKLAD["NAGIELBANK"]["pol"]
            s_c = np.mean([b["p"][1] for b in ctx["belay"] if b["pool"] == pool])
            x = sgn * (ph + 0.6)
            s = float(min(max(ss, s_c - ph * 0.6), s_c + ph * 0.6))
            fx, fs = -sgn, 0
            qd = False
        else:
            sgn = 1 if xs > 0 else -1
            qd = pool == "knagi_rufowe"
            x = xs - sgn * 0.55
            s = ss
            fx, fs = sgn, 0
        stanowisko(ctx, "liny_" + grupa, s, x, deck(ctx, s, x, qd=qd), fs, fx, obiekt=pool,
                   liny=sorted(b["lina"] for b in lst), h_rak=1.0)
    for (nazwa, grupa, pool) in ctx.get("liny_stanowisk", []):
        if pool.startswith("lawa_"):
            key = pool[5:]
            de = rig["lawy"][key]["dead"][rig["lawy"][key]["n_sh"]]
            side = -1 if key == "fok" else 1
            x = side * (inner_x(ctx, de["s"]) - 0.5)
            stanowisko(ctx, "liny_faly", de["s"], x, deck(ctx, de["s"], x), 0, side, obiekt="lawy_wantowe",
                       liny=[nazwa], h_rak=1.1)
    # wanty: wejście na maszt, marsy, noki rej
    clim = []
    for key in ("fok", "grot"):
        R_ = rig["maszty"][key]
        m, top = R_["m"], R_["top"]
        for side in (1, -1):
            shr = R_["shrouds"][side]
            k = len(shr) // 2
            a, b = shr[k]
            s_f = -a.y
            x_in = side * (inner_x(ctx, s_f) - 0.45)
            stanowisko(ctx, "wanty", s_f, x_in, deck(ctx, s_f, x_in), 0, side, obiekt="lina_wanty_" + key,
                       h_rak=1.4, opis="wejście na reling i wanty %s" % key)
            st0, st1 = R_["stave"][side]
            stave = st0.lerp(st1, 0.5)
            rim = P(side * top["W"] / 2 * 0.9, top["c_s"], top["z"])
            pts = [P(x_in, s_f, deck(ctx, s_f, x_in))]
            zr = ps.rail_top(s_f)
            pts.append(P(side * (inner_x(ctx, s_f) + 0.15), s_f, zr + 0.08))
            low = a + (b - a).normalized() * 0.3
            pts += [low]
            t = (stave.z - a.z) / (b.z - a.z)
            pts.append(a.lerp(b, t))
            pts += [rim, P(side * top["W"] * 0.25, top["c_s"], top["z"])]
            clim.append(dict(nazwa="wanty_%s_%s" % (key, "L" if side > 0 else "P"), typ="wspinaczka",
                             punkty=[g(p.x, -p.y, p.z) for p in pts], szczeble_co=O["WYBLINKI_ROZSTAW"],
                             uwagi="wyblinki od %.2f m; ostatni odcinek po podwantkach na krawędź marsa" % a.z))
        # mars
        zt = top["z"]
        stanowisko(ctx, "mars", top["c_s"] - top["Lb"] * 0.55, 0.0, zt, 1, 0, obiekt="drzewca", h_rak=1.0,
                   opis="pomost marsa %s" % key)
        # noki rej (perty): dolna reja i marsreja
        for nm in (key, key + "mars"):
            Y = rig["reje"][nm]
            c = Vector(Y["c"])
            h = Y["L"] / 2
            drop = O["PERTA_ZWIS"] if nm == key else 0.6
            for side in (1, -1):
                x = side * (h - 1.0)
                foot = c + Vector((x, Y["sr"] * 0.6 + 0.35, -drop * 0.75))
                stanowisko(ctx, "nok_rei", -foot.y, foot.x, foot.z, 1, 0, obiekt="reja_" + nm,
                           os="reja obraca się wokół osi masztu (lokalna Z)", h_rak=1.05,
                           opis="na percie, przy noku %s" % nm)
    ctx["wspinaczka"] = clim
    # dziób: sonda ręczna (stojąc przy przednich wantach foka, od środka nadburcia), rufa: log
    lw = rig["lawy"]["fok"]["dead"][0]
    s0 = lw["s"]
    x = inner_x(ctx, s0) - 0.45
    stanowisko(ctx, "sonda", s0, x, deck(ctx, s0, x), 0.3, 1, obiekt=None, h_rak=1.3,
               opis="rzut sondy przez reling przy wantach foka")
    zq = deck(ctx, -13.9, 1.0, qd=True)
    stanowisko(ctx, "log", -13.9, 1.0, zq, -1, 0, obiekt=None, h_rak=1.1, opis="log z relingu rufowego")


# ---------------------------------------------------------------- testy ergonomii
def testy(ctx, main, qd, przeszkody, extra_obst):
    out = {}
    U = ctx["PR"].UKLAD
    res = {}
    for poziom, poly in (("glowny", main), ("rufowy", qd)):
        xs = [p[0] for p in poly]
        ss = [p[1] for p in poly]
        x0, x1, s0, s1 = min(xs), max(xs), min(ss), max(ss)
        nx = int((x1 - x0) / KROK_SIATKI) + 1
        ns = int((s1 - s0) / KROK_SIATKI) + 1
        obs = [o for o in przeszkody + extra_obst if o["poziom"] == poziom and not o.get("chodzic")]
        S, X = np.meshgrid(s0 + np.arange(ns) * KROK_SIATKI, x0 + np.arange(nx) * KROK_SIATKI, indexing="ij")
        free = inside_v(poly, X, S) & (dist_poly_v(poly, X, S) >= R_POSTACI)
        for o in obs:
            free &= obst_dist_v(o, X, S) >= R_POSTACI
        res[poziom] = dict(free=free, x0=x0, s0=s0, nx=nx, ns=ns, poly=poly, obs=obs)
    return res


def inside_v(poly, X, S):
    c = np.zeros(X.shape, bool)
    n = len(poly)
    for i in range(n):
        xi, si = poly[i]
        xj, sj = poly[i - 1]
        cond = ((si > S) != (sj > S)) & (X < (xj - xi) * (S - si) / (sj - si + 1e-12) + xi)
        c ^= cond
    return c


def dist_poly_v(poly, X, S):
    best = np.full(X.shape, 1e9)
    n = len(poly)
    for i in range(n):
        x0, s0 = poly[i]
        x1, s1 = poly[(i + 1) % n]
        dx, ds = x1 - x0, s1 - s0
        tt = np.clip(((X - x0) * dx + (S - s0) * ds) / (dx * dx + ds * ds + 1e-12), 0, 1)
        best = np.minimum(best, np.hypot(X - x0 - tt * dx, S - s0 - tt * ds))
    return best


def obst_dist_v(o, X, S):
    if o["typ"] == "kolo":
        return np.maximum(0.0, np.hypot(X - o["x"], S - o["s"]) - o["wym"])
    L, W = o["wym"]
    c, sn = math.cos(o["rot"]), math.sin(o["rot"])
    dx, ds = X - o["x"], S - o["s"]
    u = ds * c + dx * sn
    v = -ds * sn + dx * c
    return np.hypot(np.maximum(np.abs(u) - L / 2, 0), np.maximum(np.abs(v) - W / 2, 0))


def bfs(grid, starts):
    ns, nx = grid.shape
    lab = -np.ones_like(grid, int)
    q = deque()
    for (i, j) in starts:
        if 0 <= i < ns and 0 <= j < nx and grid[i, j] and lab[i, j] < 0:
            lab[i, j] = 0
            q.append((i, j))
    while q:
        i, j = q.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            a, b = i + di, j + dj
            if 0 <= a < ns and 0 <= b < nx and grid[a, b] and lab[a, b] < 0:
                lab[a, b] = lab[i, j] + 1
                q.append((a, b))
    return lab


def cell(R, x, s):
    return int(round((s - R["s0"]) / KROK_SIATKI)), int(round((x - R["x0"]) / KROK_SIATKI))


def nearest_free(R, x, s, maxr=5):
    i0, j0 = cell(R, x, s)
    best = None
    for di in range(-maxr, maxr + 1):
        for dj in range(-maxr, maxr + 1):
            i, j = i0 + di, j0 + dj
            if 0 <= i < R["ns"] and 0 <= j < R["nx"] and R["free"][i, j]:
                d = di * di + dj * dj
                if best is None or d < best[0]:
                    best = (d, i, j)
    return None if best is None else (best[1], best[2])


def ergonomia(ctx, main, qd):
    przes = ctx["przeszkody"]
    rig = ctx["rig"]
    D = ctx["PR"].DRZEWCA
    U = ctx["PR"].UKLAD
    K = ctx["K"]
    extra = []
    for key in ("fok", "grot"):
        m = rig["maszty"][key]["m"]
        extra.append(dict(nazwa="maszt_" + key, obiekt="drzewca", typ="kolo", s=m.s_d, x=0.0, wym=m.r(m.z_d) + 0.12,
                          h=10, poziom="glowny", rot=0.0))
    if ctx["snow"]:
        sn = rig["snow"]
        extra.append(dict(nazwa="maszt_snow", obiekt="drzewca", typ="kolo", s=sn["s"], x=0.0, wym=sn["r"] + 0.05,
                          h=10, poziom="glowny", rot=0.0))
    bs = rig["bukszpryt"]
    h_s = bs["heel"][0]
    # pod bukszprytem nisko (do ok. 2 m nad pokładem): przeszkoda wzdłuż osi
    s2 = h_s + (2.0 - 0.3) / math.tan(math.radians(D["BUKSZPRYT_WZNIOS"]))
    extra.append(dict(nazwa="bukszpryt", obiekt="bukszpryt", typ="prostokat", s=(h_s - 0.4 + s2) / 2, x=0.0,
                      wym=(s2 - h_s + 0.4, 0.8), h=2.0, poziom="glowny", rot=0.0))
    sch = ctx["schody"]
    extra.append(dict(nazwa="schody_rufowe", obiekt="schody_rufowe", typ="prostokat",
                      s=(sch["s_gora"] + sch["s_dol"]) / 2, x=0.0, wym=(sch["s_dol"] - sch["s_gora"], sch["x1"] - sch["x0"] + 0.1),
                      h=K["POLPOKLAD_H"], poziom="glowny", rot=0.0))
    R = testy(ctx, main, qd, przes, extra)
    wynik = {}
    # dopasowanie stanowisk: wolne koło 0,45 m (bez własnego obiektu); przy relingu nadburcie nie liczy się
    PRZY_BURCIE = ("furta", "wanty", "sonda", "lodz", "kotbelka", "kotwica", "log", "dzialo_", "liny_")
    przes_all = przes + extra

    def kolidujace(t, x, s, Rl):
        bad = []
        for o in Rl["obs"]:
            if o["obiekt"] == t["obiekt"] or o["nazwa"] == t["obiekt"]:
                continue
            if t["czynnosc"] == "furta" and o["nazwa"].startswith("dzialo_") and abs(o["s"] - s) < 1.2:
                continue
            if t["czynnosc"].startswith("liny_") and o["nazwa"] in ("kolkownica",) and abs(o["x"] - x) < 0.8:
                continue
            if obst_dist(o, x, s) < 0.45:
                bad.append(o["nazwa"])
        dmin = 0.30 if t["czynnosc"].startswith(PRZY_BURCIE) else 0.45
        if not inside(Rl["poly"], x, s) or dist_poly(Rl["poly"], x, s) < dmin:
            bad.append("nadburcie")
        return bad
    przesuniete = []
    # 1) stanowiska: wolne koło 0,45 m (poza własnym obiektem), dojście z dowolnego innego
    st_deck = [t for t in ctx["stanowiska"] if t["czynnosc"] not in ("mars", "nok_rei")]
    braki_kola, nie_dojdzie = [], []
    starts = {}
    for t in st_deck:
        poziom = "rufowy" if t["s"] < K["POLPOKLAD_S"] else "glowny"
        t["poziom"] = poziom
        Rl = R[poziom]
        bad = kolidujace(t, t["x"], t["s"], Rl)
        if bad:
            best = None
            for rr in np.arange(0.05, 0.86, 0.05):
                for a in np.linspace(0, 2 * math.pi, 24, endpoint=False):
                    x2, s2 = t["x"] + rr * math.sin(a), t["s"] + rr * math.cos(a)
                    if not kolidujace(t, x2, s2, Rl):
                        best = (x2, s2)
                        break
                if best:
                    break
            if best:
                przesuniete.append(dict(stanowisko=t["nazwa"], o_m=round(math.hypot(best[0] - t["x"], best[1] - t["s"]), 2),
                                        bylo=bad))
                t["x"], t["s"] = best
                t["z"] = deck(ctx, t["s"], t["x"], qd=(poziom == "rufowy"))
                bad = []
        if bad:
            braki_kola.append(dict(stanowisko=t["nazwa"], przeszkody=bad))
        c = nearest_free(Rl, t["x"], t["s"])
        if c is None:
            nie_dojdzie.append(t["nazwa"])
        else:
            starts[t["nazwa"]] = (poziom, c)
    # spójność: pokład główny i rufowy łączą schody (dolny i górny koniec)
    cm = nearest_free(R["glowny"], 0.0, sch["s_dol"] + 0.4, maxr=8)
    cq = nearest_free(R["rufowy"], 0.0, sch["s_gora"] - 0.35)
    labs = {"glowny": bfs(R["glowny"]["free"], [cm] if cm else []),
            "rufowy": bfs(R["rufowy"]["free"], [cq] if cq else [])}
    wynik["_siatka"] = dict(start_glowny=cm, start_rufowy=cq,
                            wolne=dict((k, int(v["free"].sum())) for k, v in R.items()),
                            osiagalne=dict((k, int((v >= 0).sum())) for k, v in labs.items()))
    for nm, (poz, c) in starts.items():
        if labs[poz][c] < 0:
            nie_dojdzie.append(nm)
    wynik["stanowiska_na_pokladach"] = len(st_deck)
    wynik["dojscie_wszystkie"] = len(nie_dojdzie) == 0
    wynik["nie_dojdzie"] = sorted(set(nie_dojdzie))
    wynik["wolne_kolo_045_braki"] = braki_kola
    wynik["stanowiska_przesuniete_przez_test"] = przesuniete
    # 2) szerokość przejść: na każdym przekroju s największy wolny odcinek w poprzek (bez promienia postaci)
    waskie = []
    for poziom, poly in (("glowny", main), ("rufowy", qd)):
        obs = R[poziom]["obs"]
        ss = [p[1] for p in poly]
        for s in np.arange(min(ss) + 0.4, max(ss) - (1.5 if poziom == "glowny" else 0.4), 0.25):
            xs = [x for (x, s_) in poly]
            xmax = max(abs(x) for x in xs)
            line = np.arange(-xmax, xmax, 0.02)
            ok = np.array([inside(poly, x, s) and all(obst_dist(o, x, s) > 0.0 for o in obs) for x in line])
            best = 0
            run = 0
            for v in ok:
                run = run + 1 if v else 0
                best = max(best, run)
            w = best * 0.02
            if w < 0.8:
                waskie.append(dict(poziom=poziom, z=round(float(s), 2), szer=round(w, 2)))
    wynik["przejscia_ponizej_08"] = waskie
    # 3) kabestan: koło drągów a maszty i luki
    kk = ctx["kabestan_kolo"]
    kol = []
    for o in przes + extra:
        if o["nazwa"] in ("kabestan",) or o["poziom"] != "glowny":
            continue
        if not (o["nazwa"].startswith("maszt") or o["nazwa"].startswith("luk") or o["nazwa"].startswith("nagielbank")
                or o["nazwa"].startswith("pompa")):
            continue
        # najmniejsza odległość od środka kabestanu do przeszkody
        best = 1e9
        for t in np.linspace(0, 2 * math.pi, 72):
            for rr in np.linspace(0.3, kk["r"], 8):
                best = min(best, obst_dist(o, kk["x"] + rr * math.sin(t), kk["s"] + rr * math.cos(t)))
        kol.append(dict(przeszkoda=o["nazwa"], odstep=round(best, 3)))
    wynik["kabestan_drag_r"] = kk["r"]
    wynik["kabestan_odstepy"] = kol
    wynik["kabestan_kolizja"] = any(k["odstep"] <= 0.0 for k in kol)
    # 4) działa po odrzucie: przeszkody działa przesunięte o odrzut w głąb – czy wszystkie stanowiska nadal
    #    osiągalne (z wyjątkiem obsady działa, która wtedy stoi z boku)
    odr = U["DZIALA"]["odrzut"]
    stale = [o for o in przes + extra if o["poziom"] == "glowny" and not o.get("chodzic")
             and not o["nazwa"].startswith("dzialo_")]
    odrzuty = {}
    przes2 = []
    for o in przes:
        if not o["nazwa"].startswith("dzialo_"):
            przes2.append(o)
            continue
        W_s, L_x = o["wym"]
        r_ok = 0.0
        # przeszkody, których działo dotyka już w położeniu wytoczonym (kołkownica przy burcie), nie hamują odrzutu
        def styk(q, xc):
            return any(obst_dist(q, xx, ss) <= 0.02 for xx in np.linspace(xc - L_x / 2, xc + L_x / 2, 7)
                       for ss in (o["s"] - W_s / 2, o["s"], o["s"] + W_s / 2))
        stale_o = [q for q in stale if not styk(q, o["x"])]
        ob_g = bpy.data.objects.get(o["nazwa"])
        odr_g = min(odr, float(ob_g.get("odrzut_m", odr))) if ob_g is not None else odr   # z przenikanie.zbuduj
        for r in np.arange(0.05, odr_g + 1e-6, 0.05):
            xc = o["x"] - math.copysign(r, o["x"])
            o2 = dict(o, x=xc)
            inner_end = abs(xc) - L_x / 2
            if inner_end < 0.03:
                break
            if any(styk(q, xc) for q in stale_o):
                break
            r_ok = r
        odrzuty[o["nazwa"]] = round(float(r_ok), 2)
        przes2.append(dict(o, x=o["x"] - math.copysign(r_ok, o["x"])))
    wynik["odrzut_dzial_m"] = odrzuty
    for nm, r in odrzuty.items():
        ob = bpy.data.objects.get(nm)
        if ob is not None:
            ob["odrzut_m"] = r
    R2 = testy(ctx, main, qd, przes2, extra)
    cm2 = nearest_free(R2["glowny"], 0.0, sch["s_dol"] + 0.4, maxr=8)
    lab2 = bfs(R2["glowny"]["free"], [cm2] if cm2 else [])
    cut, zajete = [], []
    for t in st_deck:
        if t.get("poziom") != "glowny" or t["czynnosc"].startswith("dzialo") or t["czynnosc"] == "furta":
            continue
        c = nearest_free(R2["glowny"], t["x"], t["s"])
        if c is None or lab2[c] < 0:
            if t["czynnosc"] in ("wanty", "kotbelka", "sonda", "kotwica", "pompa", "liny_brasy", "liny_faly"):
                cut.append(t["nazwa"])
            else:
                zajete.append(t["nazwa"])
    # punkty kontrolne przejścia: dziób przy nagielbanku foka, oba boki przy wantach grota i foka
    for (nm, x, s) in (("dziob_lewa", 1.3, D["FOK_S"] + 0.9), ("dziob_prawa", -1.3, D["FOK_S"] + 0.9),
                       ("srodek_lewa", 2.6, 2.3), ("srodek_prawa", -2.6, 2.3)):
        c = nearest_free(R2["glowny"], x, s, maxr=8)
        if c is None or lab2[c] < 0:
            cut.append(nm)
    wynik["po_odrzucie_odciete"] = cut
    wynik["po_odrzucie_stanowiska_w_strefie_odrzutu"] = zajete
    dbg = dict(x0=R["glowny"]["x0"], s0=R["glowny"]["s0"],
               normal=["".join("2" if labs["glowny"][i, j] >= 0 else ("1" if R["glowny"]["free"][i, j] else "0")
                               for j in range(R["glowny"]["nx"])) for i in range(R["glowny"]["ns"])],
               odrzut=["".join("2" if lab2[i, j] >= 0 else ("1" if R2["glowny"]["free"][i, j] else "0")
                               for j in range(R2["glowny"]["nx"])) for i in range(R2["glowny"]["ns"])],
               stan=[(t["nazwa"], t["x"], t["s"]) for t in st_deck])
    with open(os.path.join(ctx["out"], "_chodzenie_debug.json"), "w") as f:
        json.dump(dbg, f)
    # 5) schody
    wynik["schody"] = dict(stopnie=sch["stopnie"], wznios_m=round(sch["wznios"], 3), glebokosc_m=sch["glebokosc"],
                           szerokosc_m=round(sch["x1"] - sch["x0"], 2))
    # 6) nad głową: promienie w górę z wolnych komórek na wysokości 1,45 → 2,0 m nad pokładem (bez lin)
    dg = bpy.context.evaluated_depsgraph_get()
    hits = {}
    hits_pos = []
    for poziom in ("glowny", "rufowy"):
        Rl = R[poziom]
        for i in range(0, Rl["ns"], 2):
            for j in range(0, Rl["nx"], 2):
                if not Rl["free"][i, j]:
                    continue
                s = Rl["s0"] + i * KROK_SIATKI
                x = Rl["x0"] + j * KROK_SIATKI
                z0 = deck(ctx, s, x, qd=(poziom == "rufowy"))
                o = P(x, s, z0 + 1.45)
                dist = 2.0 - 1.45
                while dist > 0:
                    ok, loc, nrm, idx, ob, mat = bpy.context.scene.ray_cast(dg, o, Vector((0, 0, 1)), distance=dist)
                    if not ok:
                        break
                    if ob.name.startswith("lina_") or ob.name.startswith("##"):
                        step = (loc - o).length + 0.01
                        o = loc + Vector((0, 0, 0.01))
                        dist -= step
                        continue
                    hits[ob.name] = hits.get(ob.name, 0) + 1
                    hits_pos.append([ob.name, round(x, 2), round(s, 2), round(loc.z - z0, 2)])
                    break
    wynik["nad_glowa_trafienia"] = hits
    wynik["nad_glowa_miejsca"] = hits_pos[:20]
    ctx["siatki_chodzenia"] = R
    return wynik, extra


# ---------------------------------------------------------------- wyjście
def zbuduj(ctx):
    kd, K = ctx["kd"], ctx["K"]
    stanowiska_takielunku(ctx)
    main, qd = obrys_pokladu(ctx)
    # test ergonomii osobno dla każdego wariantu napędu steru (przeszkody i stanowiska z 'wariant'); domyślny na końcu
    dom = ctx.get("naped_domyslny")
    all_p, all_s = ctx["przeszkody"], ctx["stanowiska"]
    warianty = sorted({o.get("wariant") for o in all_p + all_s if o.get("wariant")}, key=lambda w: w == dom)
    wyniki_w = {}
    for w in warianty or [None]:
        ctx["przeszkody"] = [o for o in all_p if o.get("wariant") in (None, w)]
        ctx["stanowiska"] = [t for t in all_s if t.get("wariant") in (None, w)]
        wynik, extra = ergonomia(ctx, main, qd)
        wyniki_w[w] = {k: v for k, v in wynik.items() if k in (
            "dojscie_wszystkie", "nie_dojdzie", "wolne_kolo_045_braki", "przejscia_ponizej_08", "kabestan_kolizja",
            "po_odrzucie_odciete", "nad_glowa_trafienia", "stanowiska_przesuniete_przez_test")}
    ctx["przeszkody"], ctx["stanowiska"] = all_p, all_s
    if warianty:
        wynik["warianty_napedu_steru"] = wyniki_w
    rig = ctx["rig"]
    # puste obiekty stanowisk
    kol = ctx["kol"]["stanowiska"]
    for t in ctx["stanowiska"]:
        e = N.empty(t["nazwa"], P(t["x"], t["s"], t["z"]), kol, rot=(0, 0, t["yaw"]), size=0.35, typ="SINGLE_ARROW")
        e.rotation_euler = (math.pi / 2, 0, t["yaw"] + math.pi)
        e.rotation_euler = (0, 0, t["yaw"])
        e["czynnosc"] = t["czynnosc"]
        if t["obiekt"]:
            e["obiekt"] = t["obiekt"]
        e["wysokosc_rak"] = t["h_rak"]
        if t.get("wariant"):
            e["wariant"] = t["wariant"]
    # wysokości: siatka co 0,5 m
    def siatka(poly, lift):
        xs = [p[0] for p in poly]
        ss = [p[1] for p in poly]
        x0, x1 = math.floor(min(xs) * 2) / 2, math.ceil(max(xs) * 2) / 2
        s0, s1 = math.floor(min(ss) * 2) / 2, math.ceil(max(ss) * 2) / 2
        rows = []
        for s in np.arange(s0, s1 + 1e-6, 0.5):
            rows.append([round(float(kd.deck_z(s, x)) + lift, 3) if inside(poly, x, s) else None
                         for x in np.arange(x0, x1 + 1e-6, 0.5)])
        return dict(x0=x0, z0=s0, krok=0.5, nx=len(rows[0]), nz=len(rows), y=rows)
    oscd = [[round(float(s), 2), round(float(kd.deck_c(s)), 3)] for s in np.arange(-15.0, 14.01, 0.5)]
    pow_ = [
        dict(nazwa="poklad_glowny", poziom="glowny", wielokat=[[round(x, 3), round(s, 3)] for (x, s) in main],
             wysokosc=dict(wzor="y = os(z) − %.3f·(x / %.2f)²" % (K["WYPUKLOSC"], K["POL_B"]), os_z_y=oscd),
             siatka=siatka(main, 0.0)),
        dict(nazwa="poklad_rufowy", poziom="rufowy", wielokat=[[round(x, 3), round(s, 3)] for (x, s) in qd],
             wysokosc=dict(wzor="y = os(z) + %.2f − %.3f·(x / %.2f)²" % (K["POLPOKLAD_H"], K["WYPUKLOSC"], K["POL_B"]),
                           os_z_y=oscd), siatka=siatka(qd, K["POLPOKLAD_H"])),
    ]
    for key in ("fok", "grot"):
        top = rig["maszty"][key]["top"]
        outer = [[round(x, 3), round(top["c_s"] + y, 3)] for (x, y) in top["outer"]]
        pow_.append(dict(nazwa="mars_" + key, poziom="mars_" + key, wielokat=outer, wysokosc=dict(stala=round(top["z"], 3)),
                         otwor="prostokąt wokół masztu (lubber's hole): x ±%.2f, z %.2f…%.2f" %
                         (top["W"] * 0.20, top["c_s"] - top["Lt"] * 0.30, top["c_s"] + top["Lt"] * 0.20)))
    for key, lw in rig["lawy"].items():
        pow_.append(dict(nazwa="lawy_wantowe_" + key, poziom="lawa", z0=round(lw["s0"], 3), z1=round(lw["s1"], 3),
                         szerokosc=ctx["PR"].OLINOWANIE["LAWA_SZER"], uwagi="ława wantowa po obu burtach za nadburciem"))
    sch = ctx["schody"]
    schody = [dict(nazwa="schody_rufowe", typ="schody", poczatek=g(0, sch["s_dol"], sch["z0"]),
                   koniec=g(0, sch["s_gora"], sch["z1"]), szerokosc=round(sch["x1"] - sch["x0"], 2),
                   stopnie=sch["stopnie"], wznios=round(sch["wznios"], 3), glebokosc_stopnia=sch["glebokosc"])]
    przejscia = []
    for p in ctx.get("przejscia", []):
        przejscia.append(dict(nazwa=p["nazwa"], typ=p["typ"], poczatek=g(0, p["s0"], p["z0"]), koniec=g(0, p["s1"], p["z1"]),
                              szerokosc=round(p["x1"] - p["x0"], 2), stopnie=p["stopnie"], uwagi=p["uwagi"]))
    przeszkody = []
    for o in ctx["przeszkody"] + extra:
        d = dict(nazwa=o["nazwa"], obiekt=o["obiekt"], poziom=o["poziom"], wysokosc=round(o["h"], 3), wariant=o.get("wariant"),
                 chodzic=bool(o.get("chodzic")), prog=o.get("prog"))
        if o["typ"] == "kolo":
            d.update(typ="kolo", srodek=[round(o["x"], 3), round(o["s"], 3)], r=round(o["wym"], 3))
        else:
            d.update(typ="prostokat", srodek=[round(o["x"], 3), round(o["s"], 3)],
                     dl_z=round(o["wym"][0], 3), szer_x=round(o["wym"][1], 3), obrot=round(o["rot"], 4))
        przeszkody.append(d)
    ps = ctx["poszycie"]
    rail = [[round(float(s), 2), round(ps.rail_top(s) + ctx["K"]["RELING_GR"] - 0.005, 3)]
            for s in np.arange(ps.ra[ps.r_top] + 0.2, ps.rf[ps.r_top] - 0.6, 0.5)]
    stan = []
    for t in ctx["stanowiska"]:
        stan.append(dict(nazwa=t["nazwa"], czynnosc=t["czynnosc"], stopy=g(t["x"], t["s"], t["z"]),
                         patrzy=[round(math.sin(t["yaw"]), 3), 0.0, round(math.cos(t["yaw"]), 3)],
                         yaw_rad=round(t["yaw"], 4), obiekt=t["obiekt"], os=t["os"], zakres=t["zakres"],
                         wysokosc_rak=round(t["h_rak"], 2), liny=t["liny"], opis=t.get("opis"),
                         poziom=t.get("poziom"), wariant=t.get("wariant")))
    licz = {}
    for t in ctx["stanowiska"]:
        licz[t["czynnosc"]] = licz.get(t["czynnosc"], 0) + 1
    # obiekty ruchome
    ruch = []
    for ob in bpy.data.objects:
        if "os_ruchu" in ob.keys():
            ruch.append(dict(obiekt=ob.name, os=ob["os_ruchu"], pivot=g(ob.matrix_world.translation.x,
                                                                        -ob.matrix_world.translation.y,
                                                                        ob.matrix_world.translation.z)))
    for nm, Y in rig["reje"].items():
        ob = Y["obj"]
        ruch.append(dict(obiekt=ob.name, os="obrót wokół lokalnej Z (oś masztu) – brasowanie",
                         pivot=g(ob.matrix_world.translation.x, -ob.matrix_world.translation.y,
                                 ob.matrix_world.translation.z)))
    J = dict(
        uklad=dict(osie="(x, y, z), metry, prawoskrętny jak glTF: x – w poprzek, + ku lewej burcie (bakburta); y – "
                        "w górę, y = 0 na wodnicy konstrukcyjnej; z – wzdłuż, + ku dziobowi, z = 0 w środku długości "
                        "pokładu między wrębami (jak węzły GLB). Odpowiada układowi parametry.json "
                        "(s, x, z) jako (x, z, s); w Blenderze (x, −z, y)",
                   postac=dict(promien=R_POSTACI, wzrost=WZROST), krok_siatki_testu=KROK_SIATKI,
                   uwagi="punkty [x, y, z]; wielokąty w rzucie [x, z]; pokład rufowy zaczyna się w z = %.2f" %
                         K["POLPOKLAD_S"]),
        powierzchnie=pow_, schody=schody, wspinaczka=ctx.get("wspinaczka", []), przejscia=przejscia,
        przeszkody=przeszkody,
        burta=dict(krawedz_pokladu_glownego="= wielokąt poklad_glowny (wewnętrzna strona nadburcia)",
                   krawedz_pokladu_rufowego="= wielokąt poklad_rufowy", reling_y=rail,
                   uwagi="poza wielokątem pokładu (|x| większe) – za burtą; reling = górna krawędź pokrywy relingu"),
        stanowiska=stan, stanowiska_liczba=licz, obiekty_ruchome=ruch, kontrola=wynik,
        siatka_chodzenia={k: dict(x0=round(float(v["x0"]), 3), z0=round(float(v["s0"]), 3), krok=KROK_SIATKI,
                                  nx=int(v["nx"]), nz=int(v["ns"]),
                                  wiersze=["".join("1" if c else "0" for c in row) for row in v["free"]],
                                  opis="1 – środek postaci (r 0,3 m) może tu stanąć; wiersze po z od z0, kolumny po x od x0")
                          for k, v in ctx["siatki_chodzenia"].items()},
    )
    p = os.path.join(ctx["out"], "bryg_poklad.json")
    os.makedirs(ctx["out"], exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(J, f, ensure_ascii=False, indent=1)
    print("CHODZENIE " + json.dumps(dict(stanowiska=len(stan), liczba=licz, kontrola=wynik), ensure_ascii=False))
    ctx["chodzenie_json"] = J
    return J
