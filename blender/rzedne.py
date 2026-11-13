"""Matematyka kadłuba (bez bpy): profil, końce linii wodnych, interpolacja tabeli rzędnych, linia pokładu,
wysokość relingu, rzędy i kolumny siatki poszycia.

Powierzchnia kadłuba to funkcja y = H(s, h): półszerokość nad punktem (s, z) widoku z boku, gdzie h = z − z_k(s)
(wysokość nad wrębem stępki). Każdy wiersz tabeli (linia równoległa do stępki) jest interpolowany wzdłuż
znormalizowanej długości σ = (s − a(h)) / (f(h) − a(h)), gdzie a – koniec rufowy (płaszczyzna pawęży dolnej,
wyżej narożnik pawęży), f – wrąb dziobnicy; na końcach półszerokość jest dana profilem (y_a, y_f). Między wierszami
interpolacja monotoniczna (PCHIP) po h. Dzięki σ krawędzie siatki trafiają dokładnie w dziobnicę i pawęż.
"""
import math

import numpy as np

import narzedzia_math as nm


class Kadlub:
    def __init__(self, K, rzedne_h, rzedne_s, rzedne):
        self.K = K
        self.zk0, self.zks = K["ZK0"], K["ZK_SPADEK"]
        self.half_siding = K["STEPKA_SZER"] / 2
        # dziobnica: gęsta krzywa (s, z) → h
        st = np.array(nm.catmull(K["DZIOB"], 12))
        self.stem_s, self.stem_z = st[:, 0], st[:, 1]
        self.stem_h = self.stem_z - self.zk(self.stem_s)
        # rufa: płaszczyzna pawęży dolnej do Z_PAWEZ_DOLNA, wyżej narożnik pawęży (oś rufy + wygięcie)
        zwt = K["Z_PAWEZ_DOLNA"]
        rake = math.tan(math.radians(K["TUCK_RAKE"]))
        self.rake = rake
        z0 = self.zk(K["TUCK_S0"])
        self.tuck_z0 = z0
        zs = sorted(set(list(np.linspace(z0, zwt, 60)) + list(np.linspace(-0.45, 0.35, 41))))
        zs = [z for z in zs if z0 <= z <= zwt]
        ss = [self.tuck_s(z) for z in zs]
        rf = np.array(nm.catmull(K["RUFA"], 12))
        self.stern_cs, self.stern_cz = rf[:, 0], rf[:, 1]   # oś pawęży (środek)
        for s_, z_ in zip(rf[1:, 0], rf[1:, 1]):
            zs.append(z_)
            ss.append(s_ + self.bulge(z_))
        self.aft_z = np.array(zs)
        self.aft_s = np.array(ss)
        self.aft_h = self.aft_z - self.zk(self.aft_s)
        # półszerokość końca rufowego: poniżej pierwszego punktu RUFA_SZER sama tylnica (dejwud)
        rs = np.array(K["RUFA_SZER"])
        rsm = nm.pchip_slopes(rs[:, 0], rs[:, 1])
        self.aft_y = np.array([self.half_siding if z_ <= rs[0, 0] else float(nm.pchip(rs[:, 0], rs[:, 1], z_, rsm))
                               for z_ in self.aft_z])
        # tabela
        self.th = np.array(rzedne_h, float)
        self.ts = np.array(rzedne_s, float)
        self.rows = []
        for j, h in enumerate(self.th if len(rzedne_h) else []):
            a, f = self.a_of_h(h), self.f_of_h(h)
            sig = [0.0]
            ys_ = [self.ya_of_h(h)]
            for i, s_ in enumerate(self.ts):
                v = rzedne[j][i]
                if v is None:
                    continue
                sg = (s_ - a) / (f - a)
                if 0.002 < sg < 0.998:
                    sig.append(sg)
                    ys_.append(v)
            sig.append(1.0)
            ys_.append(self.half_siding)
            sig = np.array(sig)
            ys_ = np.array(ys_)
            o = np.argsort(sig)
            self.rows.append((sig[o], ys_[o], nm.pchip_slopes(sig[o], ys_[o])))
        # pokład: linia przy burcie z parametrów, oś wyżej o wypukłość belki na półszerokości burty
        po = np.array(K["POKLAD_BOK"])
        self.deck_s, self.deck_zb = po[:, 0], po[:, 1]
        self.deck_m = nm.pchip_slopes(self.deck_s, self.deck_zb)
        self._dc = None
        rl = np.array(K["RELING"])
        self.rail_s, self.rail_v = rl[:, 0], rl[:, 1]

    # -------------------------------------------------------- profil
    def zk(self, s):
        return self.zk0 + self.zks * np.asarray(s, float)

    def tuck_s(self, z):
        return self.K["TUCK_S0"] - (z - self.tuck_z0) * self.rake

    def bulge(self, z):
        K = self.K
        t = np.clip((z - K["Z_PAWEZ_DOLNA"]) / (K["Z_NAWIS"] - K["Z_PAWEZ_DOLNA"]), 0, 1)
        return K["RUFA_WYGIECIE"] * t * t * (3 - 2 * t)

    def stern_center_s(self, z):
        """Oś pawęży (środek) na wysokości z (nad pawężą skrzydłową)."""
        return float(np.interp(z, self.stern_cz, self.stern_cs))

    def f_of_h(self, h):
        return float(np.interp(h, self.stem_h, self.stem_s))

    def a_of_h(self, h):
        return float(np.interp(h, self.aft_h, self.aft_s))

    def ya_of_h(self, h):
        return float(np.interp(h, self.aft_h, self.aft_y))

    def a_of_z(self, z):
        return float(np.interp(z, self.aft_z, self.aft_s))

    def ya_of_z(self, z):
        return float(np.interp(z, self.aft_z, self.aft_y))

    # -------------------------------------------------------- powierzchnia
    def H(self, s, z):
        """Półszerokość poszycia (zewn.) w punkcie (s, z); skalary albo tablice tej samej długości."""
        s = np.atleast_1d(np.asarray(s, float))
        z = np.atleast_1d(np.asarray(z, float))
        h = np.clip(z - self.zk(s), self.th[0], self.th[-1])
        a = np.interp(h, self.aft_h, self.aft_s)
        f = np.interp(h, self.stem_h, self.stem_s)
        sg = np.clip((s - a) / (f - a), 0.0, 1.0)
        vals = np.array([nm.pchip(r[0], r[1], sg, r[2]) for r in self.rows])   # (wiersze, punkty)
        out = np.empty_like(s)
        for k in range(len(s)):
            if sg[k] <= 1e-6:
                out[k] = np.interp(h[k], self.aft_h, self.aft_y)
            elif sg[k] >= 1 - 1e-6:
                out[k] = self.half_siding
            else:
                out[k] = nm.pchip(self.th, vals[:, k], h[k])
        return out

    def Zd(self, s):
        """Linia pokładu przy burcie (po zewnętrznej stronie poszycia)."""
        return nm.pchip(self.deck_s, self.deck_zb, s, self.deck_m)

    def deck_c(self, s):
        """Pokład główny w osi: linia przy burcie + wypukłość belki (belki z jednej krzywej)."""
        if self._dc is None:
            ss = np.arange(-15.6, 15.01, 0.1)
            zb = self.Zd(ss)
            y = self.H(ss, zb)
            self._dc = (ss, zb + self.K["WYPUKLOSC"] * (y / self.K["POL_B"]) ** 2)
        return np.interp(s, self._dc[0], self._dc[1])

    def deck_z(self, s, x):
        """Wysokość pokładu w punkcie (s, x)."""
        K = self.K
        return self.deck_c(s) - K["WYPUKLOSC"] * (np.asarray(x) / K["POL_B"]) ** 2

    def rail_r(self, s):
        return nm.pchip(self.rail_s, self.rail_v, s)


def resize_rows(n_bottom=26):
    """Rozkład rzędów dna: zagęszczony przy stępce (φ ∈ [0, 1])."""
    t = np.linspace(0, 1, n_bottom + 1)
    return list(t ** 1.8)
