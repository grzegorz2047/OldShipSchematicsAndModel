"""Geometria do rysunków i danych publicznych (czysty Python + numpy, bez bpy): kadłub z rzedne.Kadlub
(przekroje, wodnice, przekroje wzdłużne, pokład, reling, stępka, dziobnica, tylnica, pawęż), drzewca z model.json
(osie masztów, wysokości, reje opuszczone i robocze), wręg wykreślony łukami, żagle postawione wyliczone z drzewc.

Układ: statek (x, s, z), metry – x + ku lewej burcie, s + ku dziobowi (s = 0 w środku 28 m pokładu), z + w górę od
wodnicy konstrukcyjnej.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import parametry as PR  # noqa: E402
import rzedne  # noqa: E402


class Statek:
    """Wszystko, co rysunki i dane wiedzą o modelu: parametry, powierzchnia kadłuba, dane z model.json."""

    def __init__(self, cache, out_model):
        self.PR = PR
        self.K = PR.KADLUB
        self.D = PR.DRZEWCA
        self.O = PR.OLINOWANIE
        self.U = PR.UKLAD
        self.kd = rzedne.Kadlub(self.K, PR.RZEDNE_H, PR.RZEDNE_S, PR.RZEDNE)
        with open(os.path.join(cache, "model.json"), encoding="utf-8") as f:
            self.M = json.load(f)
        self.out_model = out_model
        self._json = {}
        self.ob = {o["nazwa"]: o for o in self.M["obiekty"]}

    def plik(self, nazwa):
        if nazwa not in self._json:
            p = os.path.join(self.out_model, nazwa)
            self._json[nazwa] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
        return self._json[nazwa]

    # ------------------------------------------------------------ kadłub
    def H(self, s, z):
        return self.kd.H(s, z)

    def deck_side(self, s):
        return float(self.kd.Zd(s))

    def deck_c(self, s):
        return float(self.kd.deck_c(s))

    def rail(self, s):
        """Górna krawędź relingu (pokrywa) nad wodnicą: linia pokładu przy burcie + RELING."""
        return float(self.kd.Zd(s)) + float(self.kd.rail_r(s))

    def zk(self, s):
        return float(self.kd.zk(s))

    def stem_s(self, z):
        """Wrąb dziobnicy: s na wysokości z."""
        kd = self.kd
        return float(np.interp(z, kd.stem_z, kd.stem_s))

    def aft_s(self, z):
        return float(self.kd.a_of_z(z))

    def s_range(self):
        return float(self.kd.aft_s.min()), float(self.kd.stem_s.max())

    def przekroj(self, s, z_top=None, n=160):
        """Wręg (półszerokość po poszyciu) na stacji s: lista (y, z) od stępki do relingu."""
        z0 = self.zk(s)
        zt = z_top if z_top is not None else self.rail(s)
        zs = z0 + (zt - z0) * (np.linspace(0, 1, n) ** 1.6)
        ys = self.H(np.full_like(zs, s), zs)
        a, f = self._konce(zs)
        ok = [(s >= a_ - 1e-6 and s <= f_ + 1e-6) for a_, f_ in zip(a, f)]
        return [(float(y), float(z)) for y, z, k in zip(ys, zs, ok) if k]

    def _konce(self, zs):
        kd = self.kd
        h = np.asarray(zs) - 0.0
        a = [kd.a_of_z(z) for z in zs]
        f = [self.stem_s(z) for z in zs]
        return a, f

    def wodnica(self, z, n=240):
        """Wodnica z: lista (s, y) od końca rufowego do dziobnicy."""
        a, f = self.aft_s(z), self.stem_s(z)
        if z > self.K["Z_PAWEZ_DOLNA"]:
            a = self.kd.stern_center_s(z)
        ss = np.linspace(a, f, n)
        ys = self.H(ss, np.full_like(ss, z))
        return [(float(s), float(y)) for s, y in zip(ss, ys)]

    def wzdluzny(self, x, n=300):
        """Przekrój wzdłużny x: lista odcinków (s, z) – dno od stępki ku górze, gdzie H(s, z) = x."""
        s0, s1 = self.s_range()
        out = []
        for s in np.linspace(s0 + 0.02, s1 - 0.02, n):
            z0 = self.zk(s)
            zs = np.linspace(z0, min(self.deck_side(s), z0 + 6.5), 120)
            ys = self.H(np.full_like(zs, s), zs)
            a = np.array([self.kd.a_of_z(z) for z in zs])
            f = np.array([self.stem_s(z) for z in zs])
            ok = (s >= a) & (s <= f)
            ys = np.where(ok, ys, 0.0)
            idx = np.where((ys[:-1] < x) & (ys[1:] >= x))[0]
            if len(idx):
                i = idx[0]
                t = (x - ys[i]) / (ys[i + 1] - ys[i])
                out.append((float(s), float(zs[i] + t * (zs[i + 1] - zs[i]))))
        return out

    def najwieksza_szerokosc(self):
        best = (0, 0, 0)
        for s in np.linspace(-6, 8, 57):
            for z in np.linspace(-0.5, 1.5, 41):
                y = float(self.H(s, z)[0])
                if y > best[0]:
                    best = (y, s, z)
        return best

    def tylnica(self):
        """Lico tylnicy (oś zawiasów steru): od pięty do pawęży skrzydłowej (s, z)."""
        z0 = self.kd.tuck_z0
        z1 = self.K["Z_PAWEZ_DOLNA"]
        return [(self.kd.tuck_s(z), z) for z in (z0, z1)]

    def profil(self):
        """Linie profilu w płaszczyźnie symetrii (s, z): wrąb, spód stępki, lico dziobnicy, tylnica, rufa, reling,
        pokład przy burcie i pokład rufowy, kolano galionu. Każda pozycja – lista punktów."""
        K, kd = self.K, self.kd
        dz = np.array(K["DZIOB"])
        st = np.array(_catmull([tuple(p) for p in K["DZIOB"]], 10))
        # lico dziobnicy: odsunięcie łuku wrębu na zewnątrz o grubość (0,31 przy stopie → 0,35 przy pokładzie)
        out = []
        for i in range(len(st)):
            a = st[max(i - 1, 0)]
            b = st[min(i + 1, len(st) - 1)]
            t = b - a
            n = np.array([t[1], -t[0]]) / (np.hypot(*t) or 1)
            g = K["STEPKA_WYS"] + (K["DZIOBNICA_GR"] - K["STEPKA_WYS"]) * i / (len(st) - 1)
            out.append(st[i] + n * g)
        lico = [tuple(map(float, p)) for p in out]
        z0 = kd.tuck_z0
        zw = K["Z_PAWEZ_DOLNA"]
        tyl_wreb = [(kd.tuck_s(z0), z0), (kd.tuck_s(zw), zw)]
        g0, g1 = K["TYLNICA_GR"]
        tyl_lico = [(kd.tuck_s(z0) - g0, z0 - K["STEPKA_WYS"]), (kd.tuck_s(zw) - g1, zw)]
        s_keel0 = tyl_lico[0][0]
        s_f0 = float(dz[0, 0])
        ss = np.linspace(s_keel0, s_f0, 40)
        stepka = [(float(s), self.zk(s) - K["STEPKA_WYS"]) for s in ss]
        wreb = [(float(s), self.zk(s)) for s in np.linspace(tyl_wreb[0][0], s_f0, 40)] + \
            [tuple(map(float, p)) for p in st]
        rufa = [tuple(p) for p in K["RUFA"]]
        s_rail = np.linspace(rufa[-1][0] + 0.05, 14.6, 120)
        reling = [(float(s), self.rail(s)) for s in s_rail]
        poklad = [(float(s), self.deck_side(s)) for s in np.linspace(-15.0, 14.3, 160)]
        poklad = [(s, z) for s, z in poklad if s >= self.aft_s(z) and s <= self.stem_s(z) + 0.36]
        rufowy = [(float(s), self.deck_side(s) + K["POLPOKLAD_H"]) for s in np.linspace(-15.0, K["POLPOKLAD_S"], 40)]
        rufowy = [(s, z) for s, z in rufowy if s >= self.aft_s(z)]
        # kolano galionu: (z, wysunięcie przed lico dziobnicy)
        gal = (self.M.get("stale", {}).get("rufa_dziob", {}).get("GALION") or {}).get("KOLANO") or []
        lz = np.array(lico)
        galion = []
        for z, o in gal:
            s_face = float(np.interp(z, lz[:, 1], lz[:, 0]))
            galion.append((s_face + o, z))
        glowica = (float(dz[-1, 0]) + K["DZIOBNICA_GR"], float(dz[-1, 1]))
        return dict(lico=lico, wreb=wreb, stepka=stepka, tyl_wreb=tyl_wreb, tyl_lico=tyl_lico, rufa=rufa,
                    reling=reling, poklad=poklad, rufowy=rufowy, galion=galion, glowica=glowica)

    def sylwetka(self):
        """Zarys kadłuba z boku (zamknięty wielokąt s, z) – do sylwetek i planów drzewc."""
        p = self.profil()
        pts = [p["tyl_lico"][0]] + p["stepka"] + p["lico"] + [p["glowica"]]
        pts += [(14.6, self.rail(14.6))] + p["reling"][::-1] + p["rufa"][::-1][:1]
        pts += p["rufa"][::-1] + [p["tyl_lico"][1]]
        return pts

    # ------------------------------------------------------------ drzewca
    def maszt(self, k):
        return self.M["maszty"][k]

    def ms(self, k, z, czesc=None):
        """s osi masztu k (fok/grot) na wysokości z; czesc: None (kolumna), 'st' (stenga), 'br' (bramstenga)."""
        o = self.M["maszty"][k]["osie"]
        s = o["s_d"] - (z - o["z_d"]) * o["tan_rake"]
        if czesc:
            s += o[czesc]["s_off"]
        return s

    def reja(self, nm):
        return self.M["reje"][nm]

    def reja_c(self, nm, robocza=False):
        Y = self.M["reje"][nm]
        c = list(Y["c"])
        if robocza:
            c[2] += Y.get("dz_robocza", 0.0)
            # przesunięcie wzdłuż osi masztu (prawie pion): s zmienia się o −dz·tan
            mk = Y.get("mast")
            if mk in ("fok", "grot"):
                c[1] -= Y.get("dz_robocza", 0.0) * self.M["maszty"][mk]["osie"]["tan_rake"]
        return c

    # ------------------------------------------------------------ żagle postawione (rozdział 08, „Worked example:
    # sails of the reference model” – our inference)
    def zagle(self):
        """Zarysy żagli postawionych (rzut boczny s, z) z drzewc: reje w pozycji roboczej, głowica 0,9 × reja,
        stopa = głowica żagla niżej (marsel, bramsel) albo 0,95 × reja (żagiel dolny), żagle dolne do relingu.
        Zwraca dict nazwa → dict(kontur=[(s, z)], glowica, stopa, wysokosc, pole, typ, reje, szwy=[...])."""
        out = {}
        szew = 0.57
        for mk in ("fok", "grot"):
            lo, ts, tg = mk, mk + "mars", mk + "bram"
            c_lo, c_ts, c_tg = (self.reja_c(n, True) for n in (lo, ts, tg))
            L = {n: self.M["reje"][n]["L"] for n in (lo, ts, tg)}
            s_m = c_lo[1]
            z_foot_course = self.rail(s_m) + 0.3
            spec = [
                (lo, c_lo, 0.9 * L[lo], 0.95 * L[lo], z_foot_course, 0),
                (ts, c_ts, 0.9 * L[ts], 0.9 * L[lo], c_lo[2], 2),
                (tg, c_tg, 0.9 * L[tg], 0.9 * L[ts], c_ts[2], 0),
            ]
            for nm, c, head, foot, z_foot, reefs in spec:
                z_head = c[2]
                out[nm] = dict(typ="square", maszt=mk, glowica=head, stopa=foot, z_glowicy=z_head, z_stopy=z_foot,
                               wysokosc=z_head - z_foot, s=c[1], pole=(head + foot) / 2 * (z_head - z_foot),
                               szwy_glowica=int(round(head / szew)), szwy_stopa=int(round(foot / szew)), refy=reefs)
        # blinda pod bukszprytem
        cb = self.reja_c("blinda")
        Lb = self.M["reje"]["blinda"]["L"]
        zb_foot = max(0.6, cb[2] - 3.6)
        out["blinda"] = dict(typ="square", maszt="bukszpryt", glowica=0.9 * Lb, stopa=0.95 * Lb, z_glowicy=cb[2],
                             z_stopy=zb_foot, wysokosc=cb[2] - zb_foot, s=cb[1],
                             pole=(0.9 * Lb + 0.95 * Lb) / 2 * (cb[2] - zb_foot), szwy_glowica=int(round(0.9 * Lb / szew)),
                             szwy_stopa=int(round(0.95 * Lb / szew)), refy=0)
        # żagiel gaflowy na maszcie snow, bez bomu: róg halsowy przy maszcie, szotowy nad relingiem rufy
        g = self.M["reje"]["gafel"]
        jaw, peak = g["c"], g["end"]
        sn = self.M.get("snow") or {}
        s_sn = sn.get("s", self.ms("grot", 2.0) - 0.45)
        z_tack = self.deck_c(s_sn) + 1.4
        s_clew = -13.6
        z_clew = self.rail(s_clew) + 0.6
        kont = [(s_sn - 0.1, z_tack), (jaw[1], jaw[2] - 0.15), (peak[1], peak[2]), (s_clew, z_clew)]
        out["gaflowy"] = dict(typ="gaff", kontur=kont, pole=_pole(kont), maszt="snow")
        # sztaksle i kliwer: trójkąty na sztagach (our inference)
        liny = self.M["liny"]

        def sztag(fragment):
            for Ln in liny:
                if Ln["g"] == "sztagi" and Ln["opis"] and fragment in Ln["opis"][0]["kod"]:
                    p = Ln["p"]
                    return (p[0][1], p[0][2]), (p[-1][1], p[-1][2])
            return None
        for nm, frag, f0, f1, wys in (("kliwer", "D_SZTAG_KLIWRA", 0.06, 0.90, 0.50),
                                      ("sztaksel_fokstengi", "st_f.p(st_f.z_head + 0.1", 0.10, 0.92, 0.55),
                                      ("sztaksel_grotstengi", "st_g.p(st_g.z_head + 0.1", 0.12, 0.90, 0.50),
                                      ("sztaksel_grota", "D_GROTSZTAG", 0.30, 0.92, 0.55)):
            st = sztag(frag)
            if not st:
                continue
            (sa, za), (sb, zb) = st      # a – góra, b – dół
            head = (sa + (sb - sa) * f0, za + (zb - za) * f0)
            tack = (sa + (sb - sa) * f1, za + (zb - za) * f1)
            # róg szotowy: od halsu w tył (ku −s) poziomo, długość wys × lik przedni
            luff = math.hypot(head[0] - tack[0], head[1] - tack[1])
            zc = max(tack[1] - 0.1 * luff, self.rail(tack[0] - wys * luff) + 1.0)
            clew = (tack[0] - wys * luff, zc)
            kont = [head, tack, clew]
            out[nm] = dict(typ="stay", kontur=kont, pole=_pole(kont), maszt=None)
        for nm, z in out.items():
            if z["typ"] == "square":
                hh, ff = z["glowica"] / 2, z["stopa"] / 2
                s = z["s"]
                # rzut boczny żagla rejowego: odcinek (żagiel prostopadły do płaszczyzny rysunku); w rzucie z boku
                # rysujemy go jak w planie ożaglowania – rozłożony w płaszczyźnie rysunku (szerokość wzdłuż s)
                z["kontur"] = [(s - hh, z["z_glowicy"]), (s + hh, z["z_glowicy"]), (s + ff, z["z_stopy"]),
                               (s - ff, z["z_stopy"])]
        return out


def _catmull(pts, n):
    import narzedzia_math as nm
    return nm.catmull(pts, n)


def _pole(k):
    a = 0.0
    for i in range(len(k)):
        x0, y0 = k[i]
        x1, y1 = k[(i + 1) % len(k)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


# ------------------------------------------------------------------ wręg wykreślony łukami (rozdział 02)
def wreg_lukami(b, h_b, rail_y, rail_t, alpha_deg, r0=(0.13, -2.85), kf=0.38, kb=1.05):
    """Metoda z rozdziału 02 (kroki 1–7): linia wzniosu dna pod kątem α od R0, łuk obła (R_f = kf·b) styczny do
    niej w głowicy dennika, łuk szerokości (R_b = kb·b, środek (b − R_b, h_b)) styczny wewnętrznie do łuku obła,
    łuk nadburcia od (b, h_b) do relingu (t, y_n). Zwraca słownik z punktami, środkami, promieniami."""
    a = math.radians(alpha_deg)
    Rf, Rb = kf * b, kb * b
    Cb = (b - Rb, h_b)
    d = (math.cos(a), math.sin(a))
    nrm = (-math.sin(a), math.cos(a))        # normalna do wnętrza (w górę i do osi)
    # szukamy t: |C_f(t) − C_b| = R_b − R_f, C_f = R0 + t·d + R_f·n
    def f(t):
        cx = r0[0] + t * d[0] + Rf * nrm[0]
        cy = r0[1] + t * d[1] + Rf * nrm[1]
        return math.hypot(cx - Cb[0], cy - Cb[1]) - (Rb - Rf)
    lo, hi = 0.0, 6.0
    ts = np.linspace(lo, hi, 601)
    vals = [f(t) for t in ts]
    t_sol = None
    for i in range(len(ts) - 1):
        if vals[i] == 0 or vals[i] * vals[i + 1] < 0:
            a_, b_ = ts[i], ts[i + 1]
            for _ in range(60):
                m = (a_ + b_) / 2
                if f(a_) * f(m) <= 0:
                    b_ = m
                else:
                    a_ = m
            t_sol = (a_ + b_) / 2
            break
    if t_sol is None:
        t_sol = float(ts[int(np.argmin(np.abs(vals)))])
    F = (r0[0] + t_sol * d[0], r0[1] + t_sol * d[1])
    Cf = (F[0] + Rf * nrm[0], F[1] + Rf * nrm[1])
    # punkt styku łuków: na prostej przez środki, po stronie C_f dalej od C_b
    ux, uy = Cf[0] - Cb[0], Cf[1] - Cb[1]
    L = math.hypot(ux, uy)
    T = (Cb[0] + ux / L * Rb, Cb[1] + uy / L * Rb)
    delta = b - rail_t
    Ru = ((rail_y - h_b) ** 2 + delta ** 2) / (2 * delta) if delta > 1e-6 else 1e6
    Cu = (b - Ru, h_b)
    return dict(R0=r0, alpha=alpha_deg, F=F, Rf=Rf, Cf=Cf, Rb=Rb, Cb=Cb, T=T, B=(b, h_b), Ru=Ru, Cu=Cu,
                N=(rail_t, rail_y), delta=delta)


def luk_punkty(C, R, p0, p1, n=48, krotszy=True):
    """Punkty łuku okręgu (C, R) od p0 do p1."""
    a0 = math.atan2(p0[1] - C[1], p0[0] - C[0])
    a1 = math.atan2(p1[1] - C[1], p1[0] - C[0])
    da = a1 - a0
    while da > math.pi:
        da -= 2 * math.pi
    while da < -math.pi:
        da += 2 * math.pi
    if not krotszy:
        da = da - 2 * math.pi if da > 0 else da + 2 * math.pi
    return [(C[0] + R * math.cos(a0 + da * k / n), C[1] + R * math.sin(a0 + da * k / n)) for k in range(n + 1)]
