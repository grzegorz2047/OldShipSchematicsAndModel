"""Kadłub: poszycie z tabeli rzędnych, berghołty, nadburcia z grubością, pokłady, grodzie, furty, stępka,
dziobnica, tylnica, ster.

Poszycie to siatka rzędów × kolumn na funkcji y = H(s, z) (rzedne.Kadlub):
- rzędy to krzywe z(s): dno (od wrębu stępki do linii farby dna, zagęszczone przy stępce), burta, berghołty (rzędy
  w stałych odległościach pod linią pokładu – wypychane na zewnątrz po normalnej), linia pokładu, rzędy nadburcia
  (próg i nadproże furt, pas furt, poziom półpokładu, reling),
- kolumny to położenia s z listy odniesienia (rząd pokładu): w środku statku pionowe (krawędzie furt są proste),
  przy końcach ściskane liniowo do końców danego rzędu (dziobnica, pawęż), więc każdy rząd kończy się dokładnie
  na profilu,
- powłoka jest zamknięta: obie burty, pas stępki i dziobnicy (schowany w stępce), płaska pawęż dolna i pawęż
  z nawisem, nadburcia od środka, pokład główny, gródź progu półpokładu, półpokład, gródź pawęży od środka,
  wierzch nadburć, otwory furt z podszyciem.
"""
import math

import numpy as np
from mathutils import Matrix, Vector

import narzedzia as N
from narzedzia import P
from materialy import region as R
import rzedne


class Poszycie:
    def __init__(self, kd, K):
        self.kd = kd
        self.K = K
        # tablice pomocnicze (gęste) dla Zd(s) i R(s)
        ss = np.arange(-15.5, 15.5001, 0.05)
        self._ss = ss
        self._zd = kd.Zd(ss)
        self._rr = kd.rail_r(ss)
        self.Zb = K["LINIA_WODNA_FARBA"]
        self._rows()
        self._ends()
        self._columns()
        self._grid()

    # ------------------------------------------------------------ rzędy
    def Zd(self, s):
        return np.interp(s, self._ss, self._zd)

    def Rr(self, s):
        return np.interp(s, self._ss, self._rr)

    def _rows(self):
        kd, K = self.kd, self.K
        rows = []          # (funkcja z(s), wypchnięcie, znacznik)
        Zb = self.Zb
        strakes = K["BERGHOLTY"]                 # (od, do, wystawanie) pod linią pokładu
        base_bot = strakes[-1][1] + 0.006
        for phi in rzedne.resize_rows(24)[:-1]:
            rows.append((lambda s, p=phi: kd.zk(s) + p * (Zb - kd.zk(s)), 0.0, "dno"))
        rows.append((lambda s: np.full_like(np.asarray(s, float), Zb), 0.0, "farba_dna"))
        for p in (0.3, 0.6, 0.85):
            rows.append((lambda s, p=p: Zb + p * (self.Zd(s) - base_bot - Zb), 0.0, "burta"))
        # berghołty: rzędy (d pod linią pokładu, wystawanie) od dołu; krawędzie wystających pasów poziome
        wl = [(base_bot, 0.0)]
        for (d0, d1, pr) in reversed(strakes):
            wl += [(d1 - 0.004, pr), (d0 + 0.004, pr)]
        # rząd kończący się dokładnie na pawęży skrzydłowej (narożnik płaskiej pawęży i kontry)
        zwt = K["Z_PAWEZ_DOLNA"]
        lo, hi = 0.004, strakes[-1][1]
        for _ in range(40):
            m = (lo + hi) / 2
            fn = (lambda s, d=m: self.Zd(s) - d)
            sa = self._end_aft(fn)
            if fn(sa) < zwt:
                hi = m
            else:
                lo = m
        d_wt = (lo + hi) / 2
        pr_wt = [pr for (d0, d1, pr) in strakes if d0 <= d_wt <= d1][0]
        wl = [w for w in wl if abs(w[0] - d_wt) > 0.012]
        wl.append((d_wt, pr_wt, "wt"))
        wl.sort(key=lambda w: -w[0])
        for w in wl:
            d, f = w[0], w[1]
            tag = "pawez_skrzydlowa" if len(w) > 2 else "bergholt"
            rows.append((lambda s, d=d: self.Zd(s) - d, f, tag))
        self.r_deck = len(rows)
        rows.append((lambda s: self.Zd(s), 0.0, "poklad"))
        lf0, lf1 = K["LISTWA_FURT"]
        for dl, tag in [(0.10, "nadburcie"), (lf0, "pas0"), (K["FURTA_PROG"], "prog"),
                        (K["FURTA_NADPROZE"], "nadproze"), (lf1, "pas1")]:
            rows.append((lambda s, dl=dl: self.Zd(s) + dl, 0.0, tag))
        r_top0 = lf1
        rmax = float(self.Rr(-10.0))
        g_qd = (K["POLPOKLAD_H"] - r_top0) / (rmax - r_top0)
        for g, tag in [(g_qd, "polpoklad"), (0.6, "nadburcie"), (0.85, "nadburcie"), (1.0, "reling")]:
            rows.append((lambda s, g=g: self.Zd(s) + r_top0 + g * (self.Rr(s) - r_top0), 0.0, tag))
        self.rows = rows
        self.tags = [r[2] for r in rows]
        self.r_sill = self.tags.index("prog")
        self.r_lintel = self.tags.index("nadproze")
        self.r_qd = self.tags.index("polpoklad")
        self.r_top = len(rows) - 1
        self.r_wt = self.tags.index("pawez_skrzydlowa")

    def _end_aft(self, fn):
        kd = self.kd
        lo, hi = -16.0, 0.0
        for _ in range(48):
            m = (lo + hi) / 2
            h = float(fn(m)) - float(kd.zk(m))
            if m - kd.a_of_h(h) < 0:
                lo = m
            else:
                hi = m
        return (lo + hi) / 2

    def _end_fore(self, fn):
        kd = self.kd
        lo, hi = 0.0, 16.0
        for _ in range(48):
            m = (lo + hi) / 2
            h = float(fn(m)) - float(kd.zk(m))
            if m - kd.f_of_h(h) < 0:
                lo = m
            else:
                hi = m
        return (lo + hi) / 2

    def _ends(self):
        self.ra = [self._end_aft(r[0]) for r in self.rows]
        self.rf = [self._end_fore(r[0]) for r in self.rows]

    # ------------------------------------------------------------ kolumny
    def _columns(self):
        K = self.K
        A, F = self.ra[self.r_deck], self.rf[self.r_deck]
        self.A, self.F = A, F
        D = 2.5
        self.D = D
        forced = []
        hw = K["FURTA_SZER"] / 2
        for s in K["FURTY_S"]:
            forced += [s - hw, s + hw]
        forced.append(K["POLPOKLAD_S"])
        cols = [A]
        # rufa: od 0,07 do 0,22 m na odcinku D, środek co 0,25 m, dziób od 0,22 do 0,05 m
        s = A
        while s < A + D:
            t = (s - A) / D
            s += 0.07 + 0.15 * t
            cols.append(s)
        while s < F - D:
            s += 0.25
            cols.append(s)
        while True:
            t = max(0.0, (F - s) / D)
            s += 0.045 + 0.17 * t
            if s >= F - 0.03:
                break
            cols.append(s)
        cols.append(F)
        cols = np.array(cols)
        hw2 = hw + 0.06
        keep = []
        for c in cols:
            if any(abs(c - f) < 0.06 for f in forced):
                continue
            if any(s0 - hw2 < c < s0 + hw2 for s0 in K["FURTY_S"]):
                continue
            keep.append(c)
        self.S = np.array(sorted(keep + forced))
        self.c_qd = int(np.argmin(np.abs(self.S - K["POLPOKLAD_S"])))
        self.port_cols = []
        for s0 in K["FURTY_S"]:
            c0 = int(np.argmin(np.abs(self.S - (s0 - hw))))
            self.port_cols.append((c0, c0 + 1))

    def col_s(self, r, S):
        a, f = self.ra[r], self.rf[r]
        A, F, D = self.A, self.F, self.D
        lo = max(A, a) + D
        hi = min(F, f) - D
        S = np.asarray(S, float)
        out = S.copy()
        m0 = S <= lo
        out[m0] = a + (S[m0] - A) * (lo - a) / (lo - A)
        m1 = S >= hi
        out[m1] = hi + (S[m1] - hi) * (f - hi) / (F - hi)
        return out

    # ------------------------------------------------------------ siatka
    def _grid(self):
        kd, K = self.kd, self.K
        nr, nc = len(self.rows), len(self.S)
        X = np.zeros((nr, nc))
        Ss = np.zeros((nr, nc))
        Z = np.zeros((nr, nc))
        for r in range(nr):
            s = self.col_s(r, self.S)
            z = self.rows[r][0](s)
            Ss[r] = s
            Z[r] = z
            X[r] = kd.H(s, z)
        X[:, -1] = kd.half_siding          # dziobnica
        self.X0, self.S0, self.Z0 = X.copy(), Ss, Z
        # normalne (różnice skończone) i wypchnięcie berghołtów
        Pp = np.stack([X, Ss, Z], -1)
        tu = np.gradient(Pp, axis=1)
        tv = np.gradient(Pp, axis=0)
        n = np.cross(tv, tu)                 # w układzie (x, s, z): na zewnątrz lewej burty dla x > 0
        n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
        n[n[..., 0] < 0] *= -1
        self.N = n
        disp = np.array([r[1] for r in self.rows])[:, None] * np.ones((1, nc))
        # zanik na końcach: dziób 1,6 m, rufa 0,25 m
        for r in range(nr):
            if self.rows[r][1] == 0:
                continue
            s = Ss[r]
            tf = np.clip((self.rf[r] - s) / 1.6, 0, 1)
            ta = np.clip((s - self.ra[r]) / 0.25, 0, 1)
            disp[r] *= np.minimum(tf * tf * (3 - 2 * tf), 0.35 + 0.65 * ta)
        Pd = Pp + n * disp[..., None]
        self.X, self.Ss, self.Z = Pd[..., 0], Pd[..., 1], Pd[..., 2]
        # UV: u – długość łuku wzdłuż rzędu od s = 0, v – pasy poszycia
        U = np.zeros((nr, nc))
        for r in range(nr):
            # długość łuku w rzucie poziomym (x, s): rzędy różnią się głównie wzniosem, a łuk 3D liczony od s = 0
            # rozjeżdżał się między sąsiednimi rzędami (ścinanie UV, anizotropia do 2 przy rufie)
            d = np.sqrt(np.diff(Pd[r, :, 0]) ** 2 + np.diff(Pd[r, :, 1]) ** 2)
            L = np.concatenate([[0], np.cumsum(d)])
            c0 = int(np.argmin(np.abs(self.S)))
            U[r] = L - L[c0]
        G = np.zeros((nr, nc))
        G[1:] = np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=-1), axis=0)
        r_wb = self.tags.index("bergholt")          # dolna krawędź berghołtu (pierwszy rząd z tym znacznikiem)
        cmid = int(np.argmin(np.abs(self.S - 0.5)))
        nb = max(4, int(round(G[r_wb, cmid] / 0.25)))
        self.n_pasow = nb
        self.G = G                                  # obwód od stępki wzdłuż kolumn (m) – v desek poszycia (deski.py)
        V = np.where(np.arange(nr)[:, None] <= r_wb, G / np.maximum(G[r_wb][None, :], 1e-6) * nb * 0.25,
                     nb * 0.25 + (G - G[r_wb][None, :]))
        self.U, self.V = U, V

    # ------------------------------------------------------------ zapytania dla innych modułów
    def outer(self, s, z):
        """Punkt poszycia lewej burty (x, s, z) i poziomy wektor normalny (nx, ns)."""
        x = float(self.kd.H(s, z)[0])
        x2 = float(self.kd.H(s + 0.05, z)[0])
        x1 = float(self.kd.H(s - 0.05, z)[0])
        dxds = (x2 - x1) / 0.1
        nn = math.hypot(1, dxds)
        return x, (1 / nn, -dxds / nn)

    def inner(self, s, z):
        """Wewnętrzna powierzchnia nadburcia (lewa burta)."""
        x, (nx, ns) = self.outer(s, z)
        t = self.K["NADBURCIE_GR"]
        return x - t * nx, s - t * ns

    def rail_top(self, s):
        return float(self.Zd(s) + self.Rr(s))


def _face_quad(sk, a, b, c, d, uvs, mat, flip):
    if flip:
        sk.face([d, c, b, a], list(reversed(uvs)), mat)
    else:
        sk.face([a, b, c, d], uvs, mat)


def region_for_row(tag_lo, K):
    return {"dno": "dno", "farba_dna": "burta", "burta": "burta", "pawez_skrzydlowa": "burta", "bergholt": "bergholt",
            "poklad": "burta_gorna", "nadburcie": "burta_gorna", "pas0": "pas_furt", "prog": "pas_furt", "nadproze": "pas_furt",
            "pas1": "burta_gorna", "polpoklad": "burta_gorna", "reling": "burta_gorna"}[tag_lo]


def zbuduj(ctx):
    """Buduje powłokę kadłuba i części konstrukcyjne. ctx: słownik (kd, K, kolekcje, ...)."""
    kd, K = ctx["kd"], ctx["K"]
    ps = Poszycie(kd, K)
    ctx["poszycie"] = ps
    sk = N.Siatka("kadlub")
    nr, nc = len(ps.rows), len(ps.S)
    X, Ss, Z = ps.X, ps.Ss, ps.Z
    t_b = K["NADBURCIE_GR"]
    holes = set()
    for (c0, c1) in ps.port_cols:
        holes.add((ps.r_sill, c0))
    # wierzchołki obu burt
    idx = {}
    for side in (1, -1):
        g = np.zeros((nr, nc), int)
        for r in range(nr):
            for c in range(nc):
                g[r, c] = sk.vert(P(side * X[r, c], Ss[r, c], Z[r, c]))
        idx[side] = g
    # ściany poszycia; UV deskowe (deski.py): u – długość wzdłuż rzędu, v – obwód od dolnej krawędzi berghołtów
    # w dół (strefa dolna) albo od linii pokładu w górę (strefa górna); między nimi pasy siatki (berghołty)
    rowreg = [region_for_row(ps.tags[r], K) for r in range(nr)]
    G = ps.G
    r_wb, r_dk = ps.tags.index("bergholt"), ps.r_deck
    strefy = dict(dolna=[], gorna=[], pasy=[], wnetrze=[], poklad=[])
    pasy = {}
    for side in (1, -1):
        g = idx[side]
        for r in range(nr - 1):
            reg = R(rowreg[r])
            if r < r_wb:
                vv, zona = G - G[r_wb][None, :], "dolna"
            elif r >= r_dk:
                vv, zona = G - G[r_dk][None, :], "gorna"
            else:
                vv, zona = G - G[r][None, :], "pasy"
            for c in range(nc - 1):
                if (r, c) in holes:
                    continue
                uv = [(ps.U[r, c], vv[r, c]), (ps.U[r + 1, c], vv[r + 1, c]),
                      (ps.U[r + 1, c + 1], vv[r + 1, c + 1]), (ps.U[r, c + 1], vv[r, c + 1])]
                _face_quad(sk, g[r, c], g[r + 1, c], g[r + 1, c + 1], g[r, c + 1], uv, reg, side < 0)
                strefy[zona].append(len(sk.f) - 1)
                if zona == "pasy":
                    pasy[len(sk.f) - 1] = (r, float(np.mean(G[r + 1] - G[r])))
    # pas stępki (wrąb, od spodu) i dziobnicy – zamknięcie między burtami (schowane w stępce / dziobnicy)
    for c in range(1, nc - 1):          # c = 0 domyka się niżej, razem z dolnym rzędem pawęży
        a, b = idx[1][0, c], idx[1][0, c + 1]
        d, e = idx[-1][0, c], idx[-1][0, c + 1]
        sk.face([a, d, e, b], [(ps.U[0, c], 0), (ps.U[0, c], 0.32), (ps.U[0, c + 1], 0.32), (ps.U[0, c + 1], 0)],
                R("dno"))
    for r in range(nr - 1):
        a, b = idx[1][r, -1], idx[1][r + 1, -1]
        d, e = idx[-1][r, -1], idx[-1][r + 1, -1]
        sk.face([a, b, e, d], [(0, ps.V[r, -1]), (0, ps.V[r + 1, -1]), (0.32, ps.V[r + 1, -1]), (0.32, ps.V[r, -1])],
                R(rowreg[r]))
    # rufa: płaska pawęż dolna (tuck) do rzędu pawęży skrzydłowej, wyżej nawis i pawęż z wygięciem w rzucie
    NX = 16
    stern_rows = []
    for r in range(nr):
        z_end = Z[r, 0]
        s_end = Ss[r, 0]
        x_end = X[r, 0]
        bul = float(kd.bulge(z_end)) if r > ps.r_wt else 0.0
        row = []
        for k in range(NX + 1):
            t = 1 - 2 * k / NX                 # +1 lewa … −1 prawa
            if k == 0:
                row.append(idx[1][r, 0])
                continue
            if k == NX:
                row.append(idx[-1][r, 0])
                continue
            xx = x_end * t
            sss = s_end - bul * (1 - t * t)
            row.append(sk.vert(P(xx, sss, z_end)))
        stern_rows.append(row)
    # pas stępki przy tylnicy: n-kąt z wierzchołkami dolnego rzędu pawęży (bez szczeliny T)
    row0 = stern_rows[0]
    poly = [idx[1][0, 0]] + row0[1:-1] + [idx[-1][0, 0], idx[-1][0, 1], idx[1][0, 1]]
    sk.face_proj(poly, R("dno"))
    ctx["rufa_rzedy"] = [(float(Z[r, 0]), float(Ss[r, 0]), float(X[r, 0]),
                          float(kd.bulge(Z[r, 0])) if r > ps.r_wt else 0.0) for r in range(nr)]
    for r in range(nr - 1):
        zc = (Z[r, 0] + Z[r + 1, 0]) / 2
        if r < ps.r_wt:
            reg = R("dno") if zc < ps.Zb else R("burta")
        elif zc < K["Z_NAWIS"]:
            reg = R("burta")
        else:
            reg = R("pawez")
        for k in range(NX):
            a, b = stern_rows[r][k], stern_rows[r][k + 1]
            c, d = stern_rows[r + 1][k + 1], stern_rows[r + 1][k]
            pa, pb, pc, pd = (Vector(sk.v[i]) for i in (a, b, c, d))
            uv = [(pa.x, pa.z), (pb.x, pb.z), (pc.x, pc.z), (pd.x, pd.z)]
            sk.face([a, b, c, d], uv, reg)
    # ---------------------------------------------------- nadburcie od środka
    # wewnętrzne wierzchołki dla rzędów od pokładu w górę (offset w rzucie o grubość ścianki)
    rr = list(range(ps.r_deck, nr))
    inner = {}
    xin = np.zeros((nr, nc))
    sin_ = np.zeros((nr, nc))
    for r in rr:
        px, pss = X[r], Ss[r]
        dx = np.gradient(px)
        ds = np.gradient(pss)
        l = np.sqrt(dx * dx + ds * ds) + 1e-12
        nx, ns = ds / l, -dx / l              # normalna w rzucie (na zewnątrz dla lewej burty)
        flip = nx < 0
        nx[flip] *= -1
        ns[flip] *= -1
        xin[r] = px - t_b * nx
        sin_[r] = pss - t_b * ns
    for r in rr:                              # narożnik pawęży: odsunięty od burty i od pawęży
        xin[r, 0] = X[r, 0] - t_b
        sin_[r, 0] = Ss[r, 0] + t_b
    # koniec dziobowy nadburcia od środka: ostatnia kolumna z x ≥ 0,32 m we wszystkich rzędach
    c_in1 = nc - 1
    while c_in1 > 0 and (xin[rr, c_in1].min() < 0.32 or np.any(np.diff(sin_[rr, nc // 2:c_in1 + 1], axis=1) <= 0.005)):
        c_in1 -= 1
    ps.c_in1 = c_in1
    zin = np.zeros((nr, nc))
    for r in rr:
        zin[r] = Z[r]
    zin[ps.r_deck] = np.array([float(kd.deck_z(sin_[ps.r_deck, c], xin[ps.r_deck, c])) for c in range(nc)])
    zin[ps.r_qd] = np.array([float(kd.deck_z(sin_[ps.r_qd, c], xin[ps.r_qd, c])) + K["POLPOKLAD_H"] if c <= ps.c_qd
                             else Z[ps.r_qd, c] for c in range(nc)])
    ps.xin, ps.sin, ps.zin = xin, sin_, zin
    for side in (1, -1):
        g = np.full((nr, nc), -1, int)
        for r in rr:
            for c in range(c_in1 + 1):
                g[r, c] = sk.vert(P(side * xin[r, c], sin_[r, c], zin[r, c]))
        inner[side] = g
    for side in (1, -1):
        g = inner[side]
        for r in rr[:-1]:
            for c in range(c_in1):
                if (r, c) in holes:
                    continue
                if c + 1 <= ps.c_qd and r < ps.r_qd:
                    continue                    # pod półpokładem – wnętrze zamknięte
                # v – wysokość nad pokładem w tej kolumnie (deski nadburcia od środka idą ze wzniosem pokładu)
                zc0, zc1 = zin[ps.r_deck, c], zin[ps.r_deck, c + 1]
                uv = [(sin_[r, c], zin[r, c] - zc0), (sin_[r, c + 1], zin[r, c + 1] - zc1),
                      (sin_[r + 1, c + 1], zin[r + 1, c + 1] - zc1), (sin_[r + 1, c], zin[r + 1, c] - zc0)]
                _face_quad(sk, g[r, c], g[r, c + 1], g[r + 1, c + 1], g[r + 1, c], uv, R("wnetrze"), side < 0)
                strefy["wnetrze"].append(len(sk.f) - 1)
    # podszycie furt (tunele przez nadburcie)
    for (c0, c1) in ps.port_cols:
        r0, r1 = ps.r_sill, ps.r_lintel
        for side in (1, -1):
            o, i_ = idx[side], inner[side]
            quads = [(o[r0, c0], o[r0, c1], i_[r0, c1], i_[r0, c0]),     # próg
                     (o[r1, c1], o[r1, c0], i_[r1, c0], i_[r1, c1]),     # nadproże
                     (o[r1, c0], o[r0, c0], i_[r0, c0], i_[r1, c0]),     # bok rufowy
                     (o[r0, c1], o[r1, c1], i_[r1, c1], i_[r0, c1])]     # bok dziobowy
            for q in quads:
                q2 = q if side > 0 else tuple(reversed(q))
                sk.face_proj(list(q2), R("wnetrze"))
    # wierzch nadburcia (pod pokrywą relingu): pas między rzędem relingu zewn. i wewn.
    rt = ps.r_top
    for side in (1, -1):
        for c in range(c_in1):
            a, b = idx[side][rt, c], idx[side][rt, c + 1]
            d, e = inner[side][rt, c], inner[side][rt, c + 1]
            q = [a, b, e, d]
            if side < 0:
                q = q[::-1]
            sk.face_proj(q, R("reling"))
    # dziób: gródź (od pokładu do relingu) w kolumnie c_in1 i pokrywa nad dziobem do dziobnicy
    NXD = 16
    cb = c_in1
    deck_front = []
    for k in range(NXD + 1):
        t = 1 - 2 * k / NXD
        if k == 0:
            deck_front.append(inner[1][ps.r_deck, cb])
        elif k == NXD:
            deck_front.append(inner[-1][ps.r_deck, cb])
        else:
            xx = xin[ps.r_deck, cb] * t
            deck_front.append(sk.vert(P(xx, sin_[ps.r_deck, cb], float(kd.deck_z(sin_[ps.r_deck, cb], xx)))))
    prev = deck_front
    zside0 = zin[ps.r_deck, cb]
    for r in rr[1:]:
        cur = []
        for k in range(NXD + 1):
            t = 1 - 2 * k / NXD
            if k == 0:
                cur.append(inner[1][r, cb])
            elif k == NXD:
                cur.append(inner[-1][r, cb])
            else:
                xx = xin[r, cb] * t
                zd = float(kd.deck_z(sin_[ps.r_deck, cb], xin[ps.r_deck, cb] * t))
                ztop = zin[ps.r_top, cb]
                f = (zin[r, cb] - zside0) / (ztop - zside0)
                cur.append(sk.vert(P(xx, sin_[r, cb], zd + f * (ztop - zd))))
        for k in range(NXD):
            a, b, c, d = prev[k], prev[k + 1], cur[k + 1], cur[k]
            sk.face_proj([a, d, c, b][::-1] if True else [a, b, c, d], R("wnetrze"))
        prev = cur
    bow_top_inner = prev
    # pokrywa dziobu: od c_in1 do dziobnicy między górnymi rzędami obu burt
    for c in range(cb, nc - 1):
        a, b = idx[1][rt, c], idx[1][rt, c + 1]
        d, e = idx[-1][rt, c], idx[-1][rt, c + 1]
        sk.face_proj([a, d, e, b], R("reling"))
    # wąski pas między zewn. górną krawędzią w c_in1 a górą grodzi dziobowej
    poly = [idx[1][rt, cb]] + [idx[-1][rt, cb]] + [bow_top_inner[NXD - k] for k in range(NXD + 1)][1:-1][::1]
    poly = [idx[1][rt, cb], idx[-1][rt, cb]] + bow_top_inner[::-1][1:-1]
    # kolejność: lewa zewn. → prawa zewn. → prawa wewn. → … → lewa wewn.
    poly = [idx[1][rt, cb], idx[-1][rt, cb], inner[-1][rt, cb]] + bow_top_inner[::-1][1:-1] + [inner[1][rt, cb]]
    sk.face_proj(poly[::-1], R("reling"))
    # ---------------------------------------------------- pokład główny (od progu półpokładu do grodzi dziobowej)
    def deck_strip(c_from, c_to, r_edge, lift, mat):
        rows_ = []
        for c in range(c_from, c_to + 1):
            row = []
            for k in range(NXD + 1):
                t = 1 - 2 * k / NXD
                if k == 0:
                    row.append(inner[1][r_edge, c])
                elif k == NXD:
                    row.append(inner[-1][r_edge, c])
                else:
                    xx = xin[r_edge, c] * t
                    row.append(sk.vert(P(xx, sin_[r_edge, c], float(kd.deck_z(sin_[r_edge, c], xx)) + lift)))
            rows_.append(row)
        for i in range(len(rows_) - 1):
            for k in range(NXD):
                a, b = rows_[i][k], rows_[i][k + 1]
                c_, d = rows_[i + 1][k + 1], rows_[i + 1][k]
                pa, pb, pc, pd = (Vector(sk.v[j]) for j in (a, b, c_, d))
                uv = [(-pa.y, pa.x), (-pb.y, pb.x), (-pc.y, pc.x), (-pd.y, pd.x)]
                sk.face([a, d, c_, b], [uv[0], uv[3], uv[2], uv[1]], mat)
                strefy["poklad"].append(len(sk.f) - 1)
        return rows_
    main_rows = deck_strip(ps.c_qd, cb, ps.r_deck, 0.0, "poklad")
    # łączenie pokładu z grodzią dziobową: pierwszy rząd grodzi to deck_front (inne wierzchołki niż ostatni rząd
    # pokładu w środku) – scal przez wspólne położenia (remove doubles na końcu)
    qd_rows = deck_strip(0, ps.c_qd, ps.r_qd, K["POLPOKLAD_H"], "poklad")
    # gródź progu półpokładu: od rzędu pokładu w c_qd do rzędu półpokładu
    cq = ps.c_qd
    prev = main_rows[0]
    zs0 = zin[ps.r_deck, cq]
    zs1 = zin[ps.r_qd, cq]
    for r in range(ps.r_deck + 1, ps.r_qd + 1):
        if r == ps.r_qd:
            cur = qd_rows[-1]
        else:
            cur = []
            f = (zin[r, cq] - zs0) / (zs1 - zs0)
            for k in range(NXD + 1):
                t = 1 - 2 * k / NXD
                if k == 0:
                    cur.append(inner[1][r, cq])
                elif k == NXD:
                    cur.append(inner[-1][r, cq])
                else:
                    xx = xin[r, cq] * t
                    zd = float(kd.deck_z(sin_[ps.r_deck, cq], xx))
                    cur.append(sk.vert(P(xx, sin_[r, cq], zd + f * K["POLPOKLAD_H"])))
        for k in range(NXD):
            a, b, c_, d = prev[k], prev[k + 1], cur[k + 1], cur[k]
            sk.face_proj([a, b, c_, d], R("wnetrze"))
        prev = cur
    # gródź pawęży od środka: od półpokładu do relingu, między kolumnami 0 obu burt
    prev = qd_rows[0]
    zq = zin[ps.r_qd, 0]
    ztop = zin[ps.r_top, 0]
    for r in range(ps.r_qd + 1, nr):
        cur = []
        f = (zin[r, 0] - zq) / (ztop - zq)
        for k in range(NXD + 1):
            t = 1 - 2 * k / NXD
            if k == 0:
                cur.append(inner[1][r, 0])
            elif k == NXD:
                cur.append(inner[-1][r, 0])
            else:
                xx = xin[r, 0] * t
                bul = float(kd.bulge(Z[r, 0]))
                zd = float(kd.deck_z(sin_[ps.r_qd, 0], xx)) + K["POLPOKLAD_H"]
                cur.append(sk.vert(P(xx, sin_[r, 0] - bul * (1 - t * t), zd + f * (ztop - zd))))
        for k in range(NXD):
            a, b, c_, d = prev[k], prev[k + 1], cur[k + 1], cur[k]
            sk.face_proj([a, d, c_, b], R("wnetrze"))
        prev = cur
    transom_top_inner = prev
    # wierzch pawęży: między górnym rzędem rufy (zewn.) a górą grodzi pawęży (NX vs NXD – oba 16)
    st = stern_rows[rt]
    for k in range(NX):
        a, b = st[k], st[k + 1]
        c_, d = transom_top_inner[k + 1], transom_top_inner[k]
        sk.face_proj([a, d, c_, b], R("reling"))
    # deski: cięcie wzdłuż szwów i styków, UV i odcień na deskę (atlas desek, deski.py)
    import deski
    D = ctx["PR"].DESKI
    n_sc, nowe = N.scal_wierzcholki(sk, 0.002)
    strefy = {k: [nowe[f] for f in v if f in nowe] for k, v in strefy.items()}
    pasy = {nowe[f]: v for f, v in pasy.items() if f in nowe}
    ctx["deski"] = deski.potnij(sk, [
        dict(nazwa="dolna", twarze=strefy["dolna"], uklad=D["burta"]),
        dict(nazwa="gorna", twarze=strefy["gorna"], uklad=D["burta"]),
        dict(nazwa="pasy", twarze=strefy["pasy"], uklad=D["burta"], pasy=pasy),
        dict(nazwa="wnetrze", twarze=strefy["wnetrze"], uklad=D["burta"]),
        dict(nazwa="poklad", twarze=strefy["poklad"], uklad=D["poklad"]),
    ])
    sk.bez_slojow = True
    ctx["kadlub_siatka"] = sk
    ob = N.to_object(sk, ctx["kol"]["kadlub"], weld=0.002)
    ob.name = "kadlub"
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    brzeg = [e for e in bm.edges if e.is_boundary]
    ctx["deski"]["krawedzie_brzegowe"] = len(brzeg)
    ctx["deski"]["brzeg_przyklady"] = [[round(c, 3) for c in (e.verts[0].co + e.verts[1].co) / 2] for e in brzeg[:8]]
    print("DESKI " + str(ctx["deski"]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    ctx["obj"]["kadlub"] = ob
    return ps


# ======================================================================== oś kadłuba i ster

def os_kadluba(ctx):
    """Stępka z dziobnicą (jedna bryła wzdłuż wrębu), tylnica, okucia steru na tylnicy."""
    kd, K = ctx["kd"], ctx["K"]
    sk = N.Siatka("kadlub_stepka")
    # ścieżka wrębu: stępka od tylnicy do początku łuku, potem dziobnica
    s0 = K["TUCK_S0"]
    ff = K["DZIOB"][0][0]
    pts = [(s, float(kd.zk(s))) for s in np.linspace(s0, ff, 24)[:-1]]
    pts += [tuple(p) for p in N.catmull(K["DZIOB"], 10)]
    pts = np.array(pts)
    n = len(pts)
    inner, outer, hw, mats = [], [], [], []
    w0, w1 = K["DZIOBNICA_SZER"]
    for i in range(n):
        s, z = pts[i]
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        t = t / np.linalg.norm(t)
        nrm = np.array([t[1], -t[0]])          # na zewnątrz: w dół (stępka), w przód (dziobnica)
        on_stem = s > ff - 1e-6
        frac = 0.0 if not on_stem else min(1.0, max(0.0, (z - pts[23][1]) / (pts[-1][1] - pts[23][1])))
        d = K["STEPKA_WYS"] if not on_stem else K["STEPKA_WYS"] + (K["DZIOBNICA_GR"] - K["STEPKA_WYS"]) * min(1, frac * 3)
        inner.append(P(0, s - nrm[0] * 0.06, z - nrm[1] * 0.06))
        outer.append(P(0, s + nrm[0] * d, z + nrm[1] * d))
        hw.append((w0 + (w1 - w0) * frac ** 1.5) / 2 if on_stem else K["STEPKA_SZER"] / 2)
    for i in range(n - 1):
        mats.append(R("dno") if (pts[i][1] + pts[i + 1][1]) / 2 < K["LINIA_WODNA_FARBA"] else R("burta"))
    N.solid_strip(sk, inner, outer, hw, mats)
    # tylnica: od pięty pod stępką do pawęży skrzydłowej (głowica tylnicy pod kontrą, nad nią tylko trzon steru
    # w otworze kontry); krawędź tylna równoległa do osi zawiasów steru (prostej)
    zb = float(kd.zk(s0)) - K["STEPKA_WYS"]
    zos = K["Z_PAWEZ_DOLNA"] + 0.25
    ztop = K["Z_PAWEZ_DOLNA"]
    d0, d1 = K["TYLNICA_GR"]
    a0 = (kd.tuck_s(zb) - d0, zb)
    a1 = (kd.tuck_s(zos) - d1, zos)
    ctx["ster_os"] = (a0, a1)
    ctx["tylnica_gora"] = ztop
    zs = np.linspace(zb, ztop, 16)
    inner, outer, hw, mats = [], [], [], []
    for z in zs:
        t_ = (z - zb) / (zos - zb)
        sa = a0[0] + (a1[0] - a0[0]) * t_
        inner.append(P(0, kd.tuck_s(z) + 0.08, z))
        outer.append(P(0, sa + K["STER_LUZ_TYLNICA"], z))   # lico tylnicy przed osią zawiasów: płetwa ±35° bez styku
        hw.append(K["STEPKA_SZER"] / 2)
    for i in range(len(zs) - 1):
        mats.append(R("dno") if (zs[i] + zs[i + 1]) / 2 < K["LINIA_WODNA_FARBA"] else R("burta"))
    N.solid_strip(sk, inner, outer, hw, mats)
    ob = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    ctx["obj"]["stepka"] = ob
    return ob


def _kontra_w_osi(ctx, on_axis):
    """Lico kontry w osi statku (siatka: środkowa kolumna rzędów rufy): zc(d) – wysokość, na której kontra leży
    d metrów za osią zawiasów steru (rośnie ku rufie)."""
    K = ctx["K"]
    rr = [r for r in ctx["rufa_rzedy"] if r[0] >= K["Z_PAWEZ_DOLNA"] - 1e-6]
    zz = np.array([r[0] for r in rr])
    sc = np.array([r[1] - r[3] for r in rr])

    def zc(d):
        lo, hi = float(zz[0]), float(zz[-1])
        for _ in range(50):
            m = 0.5 * (lo + hi)
            if float(np.interp(m, zz, sc)) - (on_axis(m) - d) > 0:
                lo = m
            else:
                hi = m
        return 0.5 * (lo + hi)
    return zc


STER_KAT = 35.0          # stopnie, wychylenie steru na burtę (rozdziały 04 i 09)
STER_CZOPY = (-2.9, -1.9, -0.9, 0.1, 0.95)   # m, wysokości taśm czopów (5 par, rozdział 04: 4–5 par)
TRZON_R = (0.17, 0.16)   # m, promień trzonu u dołu / u góry


def ster(ctx):
    """Ster na czopach jak w okręcie z płaską pawężą (rozdział 04 przewodnika):
    - płetwa wzdłuż osi zawiasów (prosta za licem tylnicy), u dołu 0,95 m, zwężająca się ku górze; górna krawędź
      ścięta równolegle do kontry tak, że przy każdym wychyleniu do ±35° zostaje luz STER_LUZ_KONTRA,
    - przednia krawędź płetwy wycięta przy każdym okuciu (gniazdo na oko okucia), czop schodzi z taśmy w dół przez
      oko okucia; taśmy czopów leżą na klinowych bokach płetwy,
    - trzon od głowicy tylnicy w górę przez otwór w kontrze (helm port, luz STER_OTWOR_LUZ) do kabiny pod
      pokładem rufowym; w wariancie z rumplem na pokładzie głowica wychodzi przez otwór w pokładzie rufowym.
    Obiekt 'ster' ma oś w linii zawiasów (lokalna Z = oś obrotu)."""
    kd, K = ctx["kd"], ctx["K"]
    (sa0, za0), (sa1, za1) = ctx["ster_os"]
    ax = np.array([sa1 - sa0, za1 - za0])
    ax /= np.linalg.norm(ax)

    def on_axis(z):
        t = (z - za0) / ax[1]
        return sa0 + ax[0] * t

    zc = _kontra_w_osi(ctx, on_axis)
    r_otw = TRZON_R[0] + K["STER_OTWOR_LUZ"]
    luz_k = K["STER_LUZ_KONTRA"]
    kmax = math.radians(STER_KAT)
    sk = N.Siatka("ster")
    zbot = za0 + 0.04
    zqd = float(kd.deck_c(on_axis(3.0))) + K["POLPOKLAD_H"]
    ztop = zqd + 0.62
    ctx["ster_glowica"] = (on_axis(zqd + 0.45), zqd + 0.45)
    z_front = zc(0.0) - luz_k                 # górna krawędź płetwy przy osi
    z_flat = z_front - 0.30                   # do tej wysokości pierścienie poziome, wyżej ścięte pod kontrą
    widths = [(zbot, 0.95), (-2.0, 0.92), (-0.5, 0.82), (0.5, 0.66), (1.1, 0.45), (2.0, 0.36)]
    wz = np.array(widths)

    def szer(z):
        return float(np.interp(z, wz[:, 0], wz[:, 1]))

    def bok(u, w):
        """Półgrubość płetwy u metrów za osią: bark 0,13 przy u = 0,078, klin do 0,065 i spływ 0,052."""
        tail = max(w - 0.08, 0.1)
        if u <= 0.078:
            return 0.13 * math.sqrt(max(0.0, 1 - ((0.078 - u) / 0.078) ** 2))
        if u <= tail:
            return 0.13 - 0.065 * (u - 0.078) / (tail - 0.078)
        return 0.065 - 0.013 * (u - tail) / max(w - tail, 1e-6)

    def profil(w, u0=0.0):
        """Przekrój płetwy (u – w tył od osi, v – w poprzek), 15 punktów; u0 > 0 – wycięcie przedniej krawędzi."""
        tail = max(w - 0.08, 0.1)
        pts = []
        for k in range(7):
            a = math.pi / 2 + math.pi * k / 6
            pts.append((0.078 * (1 + math.cos(a)), 0.13 * math.sin(a)))
        sides = [(0.078 + (tail - 0.078) * f, -(0.13 - 0.065 * f)) for f in (1 / 3, 2 / 3, 1.0)]
        pts += sides + [(w, -0.052), (w, 0.052)] + [(u, -v) for (u, v) in reversed(sides)]
        if u0 > 0:
            vb = bok(u0, w)
            pts = [(u0, v * vb / 0.13) if u < u0 else (u, v) for (u, v) in pts]
        return pts

    def z_gora(u, v):
        """Najwyższe dopuszczalne z punktu płetwy: pod kontrą w najgorszym położeniu (obrót od osi statku o 35°
        zbliża punkt do osi zawiasów, gdzie kontra jest niżej); punkty bliżej osi niż otwór kontry – bez ograniczeń
        od kontry (pod otworem), wyrównane do z_front."""
        r = math.hypot(u, v)
        phi = math.atan2(abs(v), u)
        d = r * math.cos(min(phi + kmax, math.pi))
        z = zc(max(d, 0.0)) - luz_k
        if r < r_otw - 0.02:
            z = max(z, z_front)
        return z

    # pierścienie poziome z wycięciami na oka okuć (zp − 0,19 … zp − 0,055, przejścia 1 cm)
    U0 = 0.115
    wyc = [(zp - 0.19, zp - 0.055) for zp in STER_CZOPY]
    ztab = set(float(z) for z in np.linspace(zbot, z_flat, 20))
    for (a, b) in wyc:
        ztab = set(z for z in ztab if min(abs(z - a), abs(z - b), abs(z - a + 0.01), abs(z - b - 0.01)) > 0.03)
        ztab |= {a - 0.01, a, b, b + 0.01}
    ztab = sorted(ztab)

    def u0_of(z):
        return U0 if any(a - 1e-6 <= z <= b + 1e-6 for (a, b) in wyc) else 0.0
    rings, zring = [], []
    for z in ztab:
        w = szer(z)
        rings.append(sk.verts([P(v, on_axis(z) - u, z) for (u, v) in profil(w, u0_of(z))]))
        zring.append(z)
    for tau in (0.25, 0.5, 0.75, 1.0):
        zm = z_flat + tau * (z_front - z_flat)
        w = szer(zm)
        ring = []
        for (u, v) in profil(w):
            z = z_flat + tau * (z_gora(u, v) - z_flat)
            ring.append(P(v, on_axis(z) - u, z))
        rings.append(sk.verts(ring))
        zring.append(zm)
    m = len(rings[0])
    for i in range(len(rings) - 1):
        mat = R("dno") if zring[i] < K["LINIA_WODNA_FARBA"] else R("burta")
        for j in range(m):
            j2 = (j + 1) % m
            sk.face_proj([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], mat, axis=0)
    sk.face_proj(list(reversed(rings[0])), R("dno"), flat=True)
    # górna krawędź (nieplaska): pasy między punktami symetrycznymi, od nosa do spływu
    t_ = rings[-1]
    sk.face_proj([t_[3], t_[4], t_[2]], R("burta"))
    for (a, b, c, d) in ((2, 4, 5, 1), (1, 5, 6, 0), (0, 6, 7, 14), (14, 7, 8, 13), (13, 8, 9, 12), (12, 9, 10, 11)):
        sk.face_proj([t_[a], t_[b], t_[c], t_[d]], R("burta"))
    # trzon: od głowicy tylnicy przez otwór w kontrze do kabiny pod pokładem rufowym; głowica nad pokładem rufowym
    # tylko w wariancie z rumplem na pokładzie (osobny obiekt 'ster_glowica', dziecko steru)
    z_pod = zqd - 0.12
    ctx["ster_trzon_gora"] = z_pod
    z_s0 = ctx["tylnica_gora"] + 0.02
    p0 = P(0, on_axis(z_s0), z_s0)
    p1 = P(0, on_axis(z_pod), z_pod)
    N.cylinder(sk, p0, p1, TRZON_R[0], TRZON_R[1], "drewno", sides=12, segs=3)
    pc = P(0, on_axis(z_pod - 0.3), z_pod - 0.3)
    N.cylinder(sk, pc + Vector((0, 0, -0.04)), pc + Vector((0, 0, 0.04)), TRZON_R[1] + 0.012, TRZON_R[1] + 0.008,
               "zelazo", sides=12)
    skg = N.Siatka("ster_glowica")
    N.cylinder(skg, P(0, on_axis(z_pod - 0.02), z_pod - 0.02), P(0, on_axis(ztop), ztop),
               0.159, 0.15, "drewno", sides=12, segs=2)
    for zz in (ztop - 0.08, zqd + 0.05):
        pc = P(0, on_axis(zz), zz)
        N.cylinder(skg, pc + Vector((0, 0, -0.04)), pc + Vector((0, 0, 0.04)), 0.165, 0.155, "zelazo", sides=12)
    # czopy: taśma owinięta wokół przedniej krawędzi płetwy (na bokach klina), nasada na osi, czop w dół
    for zp in STER_CZOPY:
        w = szer(zp)
        Lt = 0.6 * w
        sx = on_axis(zp)
        half = []
        for f in np.linspace(1.0, 0.0, 6):
            u = 0.078 + (Lt - 0.078) * f
            half.append((u, bok(u, w)))
        for k in range(1, 6):
            a = math.pi / 2 + math.pi / 2 * k / 6
            half.append((0.078 * (1 + math.cos(a)), 0.13 * math.sin(a)))
        cur = [(u, -v) for (u, v) in half] + [(0.0, 0.0)] + [(u, v) for (u, v) in reversed(half)]
        path = []
        for i, (u, v) in enumerate(cur):
            ua, va = cur[max(i - 1, 0)]
            ub, vb = cur[min(i + 1, len(cur) - 1)]
            tu, tv = ub - ua, vb - va
            ln = math.hypot(tu, tv) or 1.0
            nu, nv = tv / ln, -tu / ln            # normalna na zewnątrz przekroju
            if nu * (u - 0.2) + nv * v < 0:
                nu, nv = -nu, -nv
            path.append(P(v + nv * 0.011, sx - (u + nu * 0.011), zp))
        N.sweep(sk, path, N.rect_prof(0.02, 0.075), "zelazo", up=Vector((0, 0, 1)))
        N.cylinder(sk, P(0, on_axis(zp - 0.04), zp - 0.04), P(0, on_axis(zp + 0.04), zp + 0.04), 0.04, 0.04,
                   "zelazo", sides=10)
        N.cylinder(sk, P(0, on_axis(zp - 0.18), zp - 0.18), P(0, on_axis(zp - 0.035), zp - 0.035), 0.028, 0.028,
                   "zelazo", sides=10)
    ob = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    pivot = P(0, on_axis(0.0), 0.0)
    zdir = P(0, ax[0], ax[1]) - P(0, 0, 0)
    N.ustaw_os(ob, pivot, zdir, Vector((0, 1, 0)))
    ob["os_ruchu"] = "obrót wokół lokalnej Z (oś zawiasów = oś trzonu), ±35°"
    ctx["obj"]["ster"] = ob
    og = N.to_object(skg, ctx["kol"]["kadlub"], recalc=True)
    og.parent = ob
    og.matrix_parent_inverse = ob.matrix_world.inverted()
    og["wariant"] = "naped_rumpel"
    ctx["obj"]["ster_glowica"] = og
    # okucia (gudgeons) na tylnicy – statyczne: oko wokół czopu w wycięciu płetwy, ramiona po bokach tylnicy
    # i dalej po poszyciu dejwudu (punkty rzutowane promieniem na siatkę tylnicy i kadłuba); nad tuckiem ramiona
    # kończą się na licu płaskiej pawęży
    from mathutils.bvhtree import BVHTree
    vs, fs = [], []
    for o in (ctx["obj"]["kadlub"], ctx["obj"]["stepka"]):
        off = len(vs)
        vs += [o.matrix_world @ v.co for v in o.data.vertices]
        fs += [[off + i for i in p.vertices] for p in o.data.polygons]
    tree = BVHTree.FromPolygons(vs, fs)
    sk2 = N.Siatka("kadlub_okucia_steru")
    for zp in STER_CZOPY:
        zg = zp - 0.12
        sx = on_axis(zg)
        N.cylinder(sk2, P(0, on_axis(zg - 0.035), zg - 0.035), P(0, on_axis(zg + 0.035), zg + 0.035), 0.07, 0.07,
                   "zelazo", sides=12)
        for sgn in (1, -1):
            path = [P(sgn * 0.05, sx + 0.02, zg), P(sgn * (K["STEPKA_SZER"] / 2 + 0.012), sx + K["STER_LUZ_TYLNICA"] - 0.006, zg)]
            prev = K["STEPKA_SZER"] / 2
            hits = []
            ups = [Vector((0, 0, 1)), Vector((0, 0, 1))]
            for s_ in np.linspace(sx + K["STER_LUZ_TYLNICA"] + 0.012, sx + 0.75, 15):
                o_ = P(sgn * 4.0, s_, zg)
                loc, nrm, idx, dist = tree.ray_cast(o_, Vector((-sgn, 0, 0)), 8.0)
                # koniec ramienia: lico płaskiej pawęży (skok szerokości) albo poszycie zbyt pochyłe dla płaskownika
                if loc is None or abs(loc.x) - prev > 0.08:
                    break
                if nrm.x * sgn < 0:
                    nrm = -nrm
                if abs(nrm.z) > 0.35:
                    break
                prev = abs(loc.x)
                hits.append((loc, nrm))
                path.append(loc + nrm * 0.012)
                ups.append((Vector((0, 0, 1)) - nrm * nrm.z).normalized())
            n_ = len(path)
            N.sweep(sk2, path, N.rect_prof(0.022, 0.07), "zelazo", up=ups,
                    scale_b=[1.0, 1.0] + list(np.linspace(1.0, 0.62, n_ - 2)))
            for (loc, nrm) in hits[1::2]:
                N.cylinder(sk2, loc + nrm * 0.020, loc + nrm * 0.030, 0.012, 0.010, "zelazo", sides=6)
    o2 = N.to_object(sk2, ctx["kol"]["kadlub"])
    ctx["obj"]["okucia_steru"] = o2
    ctx["ster_otwor"] = dict(r=r_otw, z0=K["Z_PAWEZ_DOLNA"] - 0.05, z1=zqd + 0.40, os=on_axis, zqd=zqd)
    if not ctx.get("bez_otworu_steru"):
        otwor_steru(ctx)
    return ob


def otwor_steru(ctx):
    """Otwór steru (helm port) w kontrze i dalej szyb trzonu do pokładu rufowego: walec wzdłuż osi zawiasów
    (promień trzonu + luz) odjęty od kadłuba (Boolean, solver Manifold). W wariancie z kołem otwór w pokładzie rufowym
    zamyka pokrywa z desek (obiekt 'pokrywa_trzonu', wariant naped_kolo) – rumpel pracuje pod pokładem."""
    import bpy
    from mathutils.bvhtree import BVHTree
    O = ctx["ster_otwor"]
    on_axis = O["os"]
    hull = ctx["obj"]["kadlub"]
    import bmesh
    # nóż: walec z bmesh (zamknięty, normalne na zewnątrz – EXACT liczy po liczbie nawinięć)
    p0, p1 = P(0, on_axis(O["z0"]), O["z0"]), P(0, on_axis(O["z1"]), O["z1"])
    bmc = bmesh.new()
    bmesh.ops.create_cone(bmc, cap_ends=True, cap_tris=False, segments=24, radius1=O["r"], radius2=O["r"],
                          depth=(p1 - p0).length)
    # obrót o pół kroku podziału: krawędzie noża nie pokrywają się z krawędziami desek pokładu
    rot = (Vector((0, 0, 1)).rotation_difference((p1 - p0).normalized()).to_matrix().to_4x4()
           @ Matrix.Rotation(math.radians(7.5), 4, "Z"))
    bmc.transform(Matrix.Translation((p0 + p1) / 2) @ rot)
    bmesh.ops.recalc_face_normals(bmc, faces=bmc.faces)
    me_c = bpy.data.meshes.new("_otwor_steru")
    bmc.to_mesh(me_c)
    bmc.free()
    cut = bpy.data.objects.new("_otwor_steru", me_c)
    ctx["kol"]["kadlub"].objects.link(cut)

    def niemanifold(me):
        import bmesh
        bm_ = bmesh.new()
        bm_.from_mesh(me)
        n_ = sum(1 for e in bm_.edges if not e.is_manifold)
        bm_.free()
        return n_
    nm0 = niemanifold(hull.data)
    # ścianki szybu w materiale wnętrza kadłuba: ta sama lista materiałów w nożu co w kadłubie (tryb INDEX)
    m_w = N.MATERIALY_REJESTR.get(R("wnetrze"))
    if m_w is not None and m_w.name not in [m.name for m in hull.data.materials if m]:
        hull.data.materials.append(m_w)
    cut.data.materials.clear()
    for m in hull.data.materials:
        cut.data.materials.append(m)
    iw = [m.name if m else "" for m in hull.data.materials].index(m_w.name) if m_w is not None else 0
    for p in cut.data.polygons:
        p.material_index = iw
    mod = hull.modifiers.new("otwor_steru", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "MANIFOLD"          # Manifold (Blender 4.5+): EXACT gubi tu klasyfikację wnętrza kadłuba
    mod.object = cut
    mod.material_mode = "INDEX"
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = hull
    hull.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    hull.select_set(False)
    bpy.data.objects.remove(cut, do_unlink=True)
    ctx["otwor_steru_niemanifold"] = (nm0, niemanifold(hull.data))
    # pokrywa otworu w pokładzie rufowym (wariant z kołem): pryzmat w otworze, luz 4 mm od ścianki, wierzch
    # 4 mm pod deskami pokładu wokół otworu (wysokość z promienia w dół na siatkę kadłuba)
    vs = [hull.matrix_world @ v.co for v in hull.data.vertices]
    tree = BVHTree.FromPolygons(vs, [list(p.vertices) for p in hull.data.polygons])
    z_ = O["zqd"]
    c = P(0, on_axis(z_), z_)
    d_ax = (P(0, on_axis(z_ + 1.0), z_ + 1.0) - c).normalized()
    ex = Vector((1, 0, 0))
    ey = d_ax.cross(ex).normalized()
    sk = N.Siatka("pokrywa_trzonu")
    top, bot = [], []
    n = 24
    for k in range(n):
        a = 2 * math.pi * k / n
        rad = ex * math.cos(a) + ey * math.sin(a)
        q = c + rad * (O["r"] + 0.03)
        loc = tree.ray_cast(Vector((q.x, q.y, z_ + 1.0)), Vector((0, 0, -1)), 2.0)[0]
        zt = (loc.z if loc is not None else z_) - 0.004
        p = c + rad * (O["r"] - 0.004)
        # punkt na tworzącej walca (równoległej do osi) na wysokości zt
        t = (zt - p.z) / d_ax.z
        top.append(p + d_ax * t)
        bot.append(p + d_ax * (t - 0.08 / d_ax.z))
    it = sk.verts(top)
    ib = sk.verts(bot)
    sk.face_proj(it, "poklad")
    sk.face_proj(list(reversed(ib)), "poklad")
    for k in range(n):
        k2 = (k + 1) % n
        sk.face_proj([ib[k], ib[k2], it[k2], it[k]], "poklad")
    pk = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    pk["wariant"] = "naped_kolo"
    ctx["obj"]["pokrywa_trzonu"] = pk


def zabrudzenia(ctx):
    """Zabrudzenia w kolorach wierzchołków kadłuba (atrybut 'zabrudzenia', mnożony przez kolor materiału; w GLB
    COLOR_0): ciemniejszy pas przy wodnicy (glony, osad), zacieki pod furtami i szpigatami, rdzawe zacieki pod
    puttingami. Wartości przyjęte (zlecenie A2); brud w narożnikach daje mapa AO (eksport)."""
    ob = ctx["obj"]["kadlub"]
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    x, s, z = co[:, 0], -co[:, 1], co[:, 2]
    K = ctx["K"]
    c = np.ones((n, 3))
    # pas przy wodnicy: od 0,2 m pod do 0,40 m nad wodą, najciemniej tuż nad wodą (zielonkawo-brązowy); runda 2e:
    # mocniejszy (0,42 → 0,58) i szerszy (±0,24 → ±0,30 m), bo na renderach z wody był ledwie widoczny
    w = np.clip(1.0 - np.abs(z - 0.10) / 0.30, 0.0, 1.0)
    c *= (1.0 - 0.58 * w)[:, None] * np.array([1.0, 1.0, 0.90])[None, :] + (0.58 * w)[:, None] * np.array([0.02, 0.05, 0.0])
    # smugi w dół pod wodnicą (spływ, osad): amplituda losowa co 0,3 m wzdłuż, zanik w głąb (0,7 m)
    rng = np.random.default_rng(17)
    ks = np.arange(-17.0, 17.0, 0.3)
    a_s = np.interp(s, ks, np.clip(rng.normal(0.5, 0.35, len(ks)), 0, 1))
    pod = np.clip((0.15 - z) / 0.15, 0, 1) * np.exp(-np.clip(0.1 - z, 0, None) / 0.7) * (np.abs(x) > 0.3)
    f = 0.22 * a_s * pod
    c *= (1.0 - f)[:, None] + (f[:, None] * np.array([0.80, 0.84, 0.70])[None, :])
    zd = np.array([float(ctx["kd"].deck_c(si)) for si in s]) - 0.12
    burta = np.abs(x) > 0.3

    def zaciek(s0, hw, z_top, kolor, sila):
        d = np.abs(s - s0)
        m = burta & (d < hw) & (z < z_top) & (z > 0.0)
        f = np.zeros(n)
        f[m] = sila * (1.0 - d[m] / hw) * np.clip(1.0 - (z_top - z[m]) / 1.4, 0.15, 1.0)
        c[:] = c * (1.0 - f[:, None]) + np.array(kolor)[None, :] * c * f[:, None]
    for p0 in K["FURTY_S"] + K.get("FURTY_ZAMKNIETE_S", []):
        zt = float(ctx["kd"].deck_c(p0)) + K["FURTA_PROG"] - 0.15
        zaciek(p0, 0.22, zt, (0.62, 0.58, 0.52), 0.55)
    for p0 in ctx.get("szpigaty_s", []):
        zaciek(p0, 0.12, float(ctx["kd"].deck_c(p0)) - 0.15, (0.55, 0.52, 0.47), 0.6)
    for key, lw in ctx.get("rig", {}).get("lawy", {}).items():
        for de in lw["dead"]:
            zaciek(de["s"], 0.07, float(ctx["kd"].deck_c(de["s"])) - 0.18, (0.62, 0.42, 0.30), 0.5)
    import bpy
    pl = pokladowe(ctx, co)
    if pl is not None:
        c *= pl
    # atrybut w rogach ścian: zabrudzenia (wierzchołki) × odcień deski / elementu ('odcien', narzedzia / deski.py)
    zapisz_kolory(me, c)
    # pozostałe siatki: odcień elementu albo biel (materiały mnożą kolor przez ten atrybut; brak atrybutu = czerń)
    for o in bpy.data.objects:
        if o.type == "MESH" and o is not ob and "zabrudzenia" not in o.data.color_attributes:
            zapisz_kolory(o.data, None)
    return me.color_attributes.get("zabrudzenia")


def zapisz_kolory(me, c_wierzcholki):
    """'zabrudzenia' (BYTE_COLOR, rogi ścian) = c_wierzcholki[v] (albo 1) × 'odcien' (jeśli jest); 'odcien' usuwany."""
    nl = len(me.loops)
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    col = np.ones((nl, 4), np.float32)
    if c_wierzcholki is not None:
        col[:, :3] = np.clip(c_wierzcholki, 0, 1)[vi]
    od = me.color_attributes.get("odcien")
    if od is not None and od.domain == "CORNER":
        o = np.empty(nl * 4, np.float32)
        od.data.foreach_get("color", o)
        col[:, :3] *= o.reshape(-1, 4)[:, :3]
    if od is not None:
        me.color_attributes.remove(od)
    old = me.color_attributes.get("zabrudzenia")
    if old is not None:
        me.color_attributes.remove(old)
    at = me.color_attributes.new("zabrudzenia", "BYTE_COLOR", "CORNER")
    at.data.foreach_set("color", np.clip(col, 0, 1).ravel())
    me.color_attributes.active_color = at
    return at


def pokladowe(ctx, co):
    """Zużycie pokładu (mnożnik na wierzchołek kadłuba, tylko wierzchołki pokładu): ciemniej przy ścieku i wokół
    dział (brud, smoła, proch), jaśniej na wydeptanych ścieżkach (środek pokładu, wokół kabestanu, przy kole)."""
    import bpy
    x, s, z = co[:, 0], -co[:, 1], co[:, 2]
    kd = ctx["kd"]
    n = len(co)
    zd = np.array([float(kd.deck_c(si)) for si in s])
    pok = (np.abs(z - zd) < 0.02) | (np.abs(z - zd - ctx["K"]["POLPOKLAD_H"]) < 0.03)
    if not pok.any():
        return None
    m = np.ones((n, 3))
    # szerokość pokładu w tym przekroju (wewnętrzna krawędź nadburcia) – tablica co 5 cm, interpolacja
    ps = ctx["poszycie"]
    ss = np.arange(-15.0, 15.0, 0.05)
    xs = np.array([abs(float(ps.inner(si, float(kd.deck_c(si)) + 0.3)[0])) for si in ss])
    xr = np.interp(s, ss, xs)
    d_burta = np.clip(xr - np.abs(x), 0, None)
    ciemno = 0.16 * np.exp(-d_burta / 0.25) + 0.05 * np.exp(-d_burta / 0.8)
    for o in bpy.data.objects:
        if o.name.startswith("dzialo_") and o.type == "MESH" and "_" not in o.name[7:]:
            p = o.matrix_world.translation
            d = np.hypot(x - p.x, -s - p.y)
            ciemno += 0.10 * np.exp(-(d / 0.9) ** 2)
    jasno = 0.06 * np.exp(-(x / 1.1) ** 2)
    for nm in ("kabestan_podstawa", "kolo_sterowe"):
        o = bpy.data.objects.get(nm)
        if o is not None:
            p = o.matrix_world.translation
            d = np.hypot(x - p.x, -s - p.y)
            jasno += 0.07 * np.exp(-((d - 1.4) / 0.5) ** 2) if nm.startswith("kab") else 0.05 * np.exp(-(d / 1.0) ** 2)
    f = np.clip(0.9 - ciemno + jasno, 0.55, 1.0)        # 0,9 – zwykły pokład; do 1,0 na ścieżkach
    m[pok] = np.stack([f[pok], f[pok] * 0.995, f[pok] * 0.985], -1)
    return m


def zbuduj_all(ctx):
    zbuduj(ctx)
    os_kadluba(ctx)
    ster(ctx)
