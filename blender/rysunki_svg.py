"""Biblioteka rysunku technicznego w SVG (czysty Python): arkusz A3/A1 w milimetrach, widoki w skali (metry
modelu → mm papieru), linie wg ISO 128 (zarys 0,5, krawędzie niewidoczne kreskowe 0,25, osie punktowo-kreskowe
0,18, wymiarowe i konstrukcyjne 0,18), wymiary liniowe, promieniowe i kątowe z liczbami, podpisy z odnośnikami
i unikaniem nakładania, podziałka liniowa, tabelka rysunkowa. Jedna wersja kodu – dwa języki (słownik etykiet).

Atrybuty kresek zapisane wprost przy elementach (bez CSS) – lepszy import do programów CAD.
"""
import math
import os

import slownik_rysunkow as SL

FONT = "Arial, Helvetica, sans-serif"
PIORA = {
    "gruba": dict(w=0.50), "srednia": dict(w=0.35), "cienka": dict(w=0.25), "bcienka": dict(w=0.18),
    "ukryta": dict(w=0.25, dash="2.4,1.2"), "osiowa": dict(w=0.18, dash="7,1.2,1,1.2"),
    "wymiar": dict(w=0.18), "konstr": dict(w=0.13), "lina": dict(w=0.25), "punkt": dict(w=0.18, dash="0.6,0.8"),
}
FORMATY = {"A3": (420.0, 297.0), "A1": (841.0, 594.0)}

BRAKUJACE = set()


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Arkusz:
    def __init__(self, nazwa, jezyk="en", format="A3", numer=1, z_ilu=19):
        self.nazwa = nazwa
        self.jezyk = jezyk
        self.W, self.H = FORMATY[format]
        self.format = format
        self.numer, self.z_ilu = numer, z_ilu
        self.el = []
        self.boxes = []
        self.margines = 10.0
        self.ramka_wew = (self.margines + 10.0, self.margines, self.W - self.margines, self.H - self.margines)
        self.tab_w, self.tab_h = 180.0, 34.0
        x1, y1 = self.ramka_wew[2], self.ramka_wew[3]
        self.tabelka = (x1 - self.tab_w, y1 - self.tab_h, x1, y1)
        self.boxes.append(self.tabelka)

    # ------------------------------------------------------------ język i liczby
    def t(self, en):
        if self.jezyk == "en":
            return en
        if en in SL.PL:
            return SL.PL[en]
        z = SL.zloz(en)
        if z:
            return z
        BRAKUJACE.add(en)
        return en

    def n(self, v, d=2):
        s = ("%." + str(d) + "f") % v
        if s.startswith("-"):
            s = "−" + s[1:]
        return s.replace(".", ",") if self.jezyk == "pl" else s

    # ------------------------------------------------------------ prymitywy (mm papieru)
    def _pen(self, pioro, kolor="#000", w=None, op=None):
        p = PIORA[pioro]
        a = 'stroke="%s" stroke-width="%.3f" fill="none" stroke-linecap="round" stroke-linejoin="round"' % (
            kolor, w if w is not None else p["w"])
        if "dash" in p:
            a += ' stroke-dasharray="%s"' % p["dash"]
        if op is not None:
            a += ' stroke-opacity="%.2f"' % op
        return a

    def path(self, pts, pioro="gruba", kolor="#000", zamknij=False, w=None, fill=None, op=None, fop=None, przytnij=False, obszar=None):
        if len(pts) < 2:
            return
        a = self._pen(pioro, kolor, w, op)
        if not fill and przytnij and not self._wewnatrz(pts, obszar):
            # linie przycięte do ramki i poza tabelką rysunkową
            if zamknij:
                pts = list(pts) + [pts[0]]
            czesci = self._przytnij(pts, obszar)
            if not czesci:
                return
            d = " ".join("M%.2f %.2f" % c[0] + "".join(" L%.2f %.2f" % p for p in c[1:]) for c in czesci)
            self.el.append('<path d="%s" %s/>' % (d, a))
            return
        d = "M%.2f %.2f" % pts[0] + "".join(" L%.2f %.2f" % p for p in pts[1:]) + (" Z" if zamknij else "")
        if fill:
            a = a.replace('fill="none"', 'fill="%s"' % fill) + (' fill-opacity="%.2f"' % fop if fop is not None else "")
        self.el.append('<path d="%s" %s/>' % (d, a))

    przycinaj = False

    def _wewnatrz(self, pts, obszar=None):
        x0, y0, x1, y1 = obszar or self.ramka_wew
        t0, u0, t1, u1 = self.tabelka
        for x, y in pts:
            if x < x0 or x > x1 or y < y0 or y > y1 or (t0 < x < t1 and u0 < y < u1):
                return False
        return True

    def _przytnij(self, pts, obszar=None):
        """Łamana → części wewnątrz ramki (albo obszaru widoku) i poza tabelką (próbkowanie odcinków)."""
        x0, y0, x1, y1 = obszar or self.ramka_wew
        t0, u0, t1, u1 = self.tabelka
        ok = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and not (t0 < p[0] < t1 and u0 < p[1] < u1)
        out, cur = [], []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(1, int(L / 0.5)) if not (ok(a) and ok(b)) else 1
            for k in range(n + 1):
                if k == 0 and i > 0:
                    continue
                p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                if ok(p):
                    cur.append(p)
                else:
                    if len(cur) > 1:
                        out.append(cur)
                    cur = []
        if len(cur) > 1:
            out.append(cur)
        return out

    def fill(self, pts, kolor="#000", op=1.0):
        d = "M%.2f %.2f" % pts[0] + "".join(" L%.2f %.2f" % p for p in pts[1:]) + " Z"
        self.el.append('<path d="%s" fill="%s" fill-opacity="%.2f" stroke="none"/>' % (d, kolor, op))

    def circle(self, c, r, pioro="gruba", kolor="#000", fill=None, w=None):
        a = self._pen(pioro, kolor, w)
        if fill:
            a = a.replace('fill="none"', 'fill="%s"' % fill)
        self.el.append('<circle cx="%.2f" cy="%.2f" r="%.2f" %s/>' % (c[0], c[1], r, a))

    def text(self, p, txt, h=2.5, anchor="middle", rot=0.0, bold=False, kolor="#000", italic=False, rejestr=True,
             tlo=False):
        txt = str(txt)
        w = self.szer_tekstu(txt, h)
        x, y = p
        if rejestr:
            x0 = x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
            if abs(rot) < 1e-6:
                self.boxes.append((x0 - 0.4, y - h * 0.85, x0 + w + 0.4, y + h * 0.25))
        if tlo and abs(rot) < 1e-6:
            x0 = x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
            self.el.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="#fff" stroke="none"/>' % (
                x0 - 0.5, y - h * 0.9, w + 1.0, h * 1.2))
        tr = ' transform="rotate(%.2f %.2f %.2f)"' % (rot, x, y) if abs(rot) > 1e-6 else ""
        st = ' font-weight="bold"' if bold else ""
        st += ' font-style="italic"' if italic else ""
        self.el.append('<text x="%.2f" y="%.2f" font-family="%s" font-size="%.2f" text-anchor="%s" fill="%s"%s%s>%s'
                       '</text>' % (x, y, FONT, h, anchor, kolor, st, tr, esc(txt)))

    @staticmethod
    def szer_tekstu(txt, h):
        w = 0.0
        for c in str(txt):
            w += 0.30 if c in "il.,:;|'!" else 0.85 if c in "mwMW" else 0.72 if c.isupper() else 0.55
        return w * h

    def kolizja(self, b, margines=0.6):
        x0, y0, x1, y1 = b
        if x0 < self.ramka_wew[0] + 1 or x1 > self.ramka_wew[2] - 1 or y0 < self.ramka_wew[1] + 1 or \
                y1 > self.ramka_wew[3] - 1:
            return True
        for (a0, b0, a1, b1) in self.boxes:
            if x0 < a1 + margines and x1 > a0 - margines and y0 < b1 + margines and y1 > b0 - margines:
                return True
        return False

    def zajmij(self, b):
        self.boxes.append(b)

    def strzalka(self, p, kier, dl=2.6, szer=0.9):
        """Grot strzałki wymiarowej w punkcie p, skierowany wzdłuż kier (wektor jednostkowy)."""
        dx, dy = kier
        nx, ny = -dy, dx
        a = (p[0] - dx * dl + nx * szer / 2, p[1] - dy * dl + ny * szer / 2)
        b = (p[0] - dx * dl - nx * szer / 2, p[1] - dy * dl - ny * szer / 2)
        self.fill([p, a, b])

    def etykieta(self, p, txt, pref=(1, -1), h=2.3, dmin=5.0, kolor="#000", dot=True, max_d=60.0, obszar=None):
        """Podpis z linią odniesienia: szuka miejsca bez kolizji wokół p (mm), zaczynając od kierunku pref."""
        txt = str(txt)
        w = self.szer_tekstu(txt, h)
        a0 = math.atan2(pref[1], pref[0])
        for d in [dmin + 3 * k for k in range(int((max_d - dmin) / 3) + 1)]:
            for da in (0, 20, -20, 40, -40, 60, -60, 90, -90, 120, -120, 150, -150, 180):
                a = a0 + math.radians(da)
                cx, cy = p[0] + d * math.cos(a), p[1] + d * math.sin(a)
                left = math.cos(a) < -0.2
                x0 = cx - w if left else cx
                if abs(math.cos(a)) <= 0.2:
                    x0 = cx - w / 2
                b = (x0 - 0.5, cy - h * 0.9, x0 + w + 0.5, cy + h * 0.3)
                if obszar and (b[0] < obszar[0] or b[2] > obszar[2] or b[1] < obszar[1] or b[3] > obszar[3]):
                    continue
                if not self.kolizja(b):
                    self.zajmij(b)
                    # linia odniesienia do najbliższego punktu ramki tekstu
                    ex = min(max(p[0], b[0]), b[2])
                    ey = cy - h * 0.3
                    if left:
                        ex = b[2]
                    elif math.cos(a) > 0.2:
                        ex = b[0]
                    self.path([p, (ex, ey)], "bcienka", kolor)
                    if dot:
                        self.circle(p, 0.45, "bcienka", kolor, fill=kolor)
                    self.text((x0, cy), txt, h, "start", kolor=kolor, rejestr=False)
                    return b
        # brak miejsca: tekst przy punkcie
        self.text((p[0] + 1, p[1] - 1), txt, h, "start", kolor=kolor)
        return None

    # ------------------------------------------------------------ elementy arkusza
    def ramka(self, tytul, skala_txt, podtytul="", uwagi=()):
        m = self.margines
        self.el.insert(0, '<rect x="0" y="0" width="%.1f" height="%.1f" fill="#fff" stroke="none"/>' % (self.W, self.H))
        x0, y0, x1, y1 = self.ramka_wew
        self.path([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "gruba", zamknij=True, w=0.7)
        self.path([(m, m), (self.W - m, m), (self.W - m, self.H - m), (m, self.H - m)], "bcienka", zamknij=True)
        # znaczniki środka
        for (a, b) in (((self.W / 2, m), (self.W / 2, y0 + 5)), ((self.W / 2, self.H - m), (self.W / 2, y1 - 5)),
                       ((m, self.H / 2), (x0 + 5, self.H / 2)), ((self.W - m, self.H / 2), (x1 - 5, self.H / 2))):
            self.path([a, b], "srednia")
        tx0, ty0, tx1, ty1 = self.tabelka
        self.path([(tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1)], "gruba", zamknij=True, w=0.7)
        self.path([(tx0, ty0 + 12), (tx1, ty0 + 12)], "cienka")
        self.path([(tx0, ty0 + 20), (tx1, ty0 + 20)], "cienka")
        self.path([(tx0, ty0 + 28.6), (tx1, ty0 + 28.6)], "cienka")
        self.path([(tx0 + 60, ty0 + 20), (tx0 + 60, ty0 + 28.6)], "cienka")
        self.path([(tx0 + 120, ty0 + 20), (tx0 + 120, ty0 + 28.6)], "cienka")
        self.text((tx0 + 3, ty0 + 7.8), self.t(tytul), 5.0, "start", bold=True, rejestr=False)
        if podtytul:
            self.text((tx0 + 3, ty0 + 17.2), self.t(podtytul), 2.6, "start", rejestr=False)
        lab = lambda x, y, a, b: (self.text((x, y), a, 1.8, "start", kolor="#444", rejestr=False),
                                  self.text((x, y + 4.1), b, 2.6, "start", rejestr=False))
        lab(tx0 + 3, ty0 + 22.2, self.t("Scale"), skala_txt)
        lab(tx0 + 63, ty0 + 22.2, self.t("Sheet"), "%d / %d" % (self.numer, self.z_ilu))
        lab(tx0 + 123, ty0 + 22.2, self.t("Format"), "%s, %s" % (self.format, self.t("dimensions in metres")))
        self.text((tx0 + 3, ty0 + 32.2), self.t("Reference model - snow, about 1710 - drawn by script from the model "
                                                "parameters"), 2.0, "start", rejestr=False)
        if uwagi:
            y = ty0 - 2.0
            for u in reversed(list(uwagi)):
                self.text((tx1 - 2, y), self.t(u), 2.1, "end", italic=True)
                y -= 3.2

    def podzialka(self, p, skala, dl_m=None, h=2.0, etykieta=True):
        """Podziałka liniowa w punkcie p (lewy dolny róg): długość dl_m metrów w skali 1:skala."""
        if dl_m is None:
            dl_m = 1.0
            for c in (1, 2, 5, 10, 20, 25, 50):
                if c * 1000 / skala <= 90:
                    dl_m = c
        n = int(dl_m) if dl_m >= 5 else 5
        krok = dl_m / n
        mm = 1000.0 / skala
        x, y = p
        for k in range(n):
            if k % 2 == 0:
                self.fill([(x + k * krok * mm, y - h), (x + (k + 1) * krok * mm, y - h), (x + (k + 1) * krok * mm, y),
                           (x + k * krok * mm, y)])
        self.path([(x, y - h), (x + dl_m * mm, y - h), (x + dl_m * mm, y), (x, y)], "cienka", zamknij=True)
        for k in range(n + 1):
            if k % (1 if n <= 10 else 2) == 0:
                v = k * krok
                self.text((x + k * krok * mm, y + 3.2), self.n(v, 0 if abs(v - round(v)) < 1e-6 else 1), 2.0)
        self.text((x + dl_m * mm + 2.5, y + 0.2), "m", 2.2, "start")
        if etykieta:
            self.text((x, y - h - 1.4), "1:%g" % skala, 2.2, "start", bold=True)

    def zapisz(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        s = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">' % (
                 self.W, self.H, self.W, self.H),
             '<title>%s</title>' % esc(self.nazwa)]
        s.extend(self.el)
        s.append("</svg>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(s))


class Widok:
    """Widok w skali: punkt modelu (u, v) w metrach → (X, Y) mm na arkuszu; v w górę."""

    def __init__(self, ark, x0, y0, skala, u0=0.0, v0=0.0, tytul=None, lustro=False):
        self.a = ark
        self.x0, self.y0, self.skala = x0, y0, skala
        self.u0, self.v0 = u0, v0
        self.k = 1000.0 / skala
        self.lustro = lustro
        self.bbox = None
        self.obszar = None          # (x0, y0, x1, y1) mm – przycinanie linii widoku
        if tytul:
            self.tytul = tytul

    def P(self, u, v):
        if self.lustro:
            u = 2 * self.u0 - u
        return (self.x0 + (u - self.u0) * self.k, self.y0 - (v - self.v0) * self.k)

    def mm(self, d):
        return d * self.k

    def linia(self, pts, pioro="gruba", kolor="#000", zamknij=False, w=None, fill=None, op=None, fop=None):
        self.a.path([self.P(*p) for p in pts], pioro, kolor, zamknij, w, fill, op, fop, przytnij=True, obszar=self.obszar)

    def odcinek(self, a, b, pioro="gruba", kolor="#000", w=None):
        self.a.path([self.P(*a), self.P(*b)], pioro, kolor, w=w, przytnij=True, obszar=self.obszar)

    def wypelnij(self, pts, kolor="#000", op=1.0):
        self.a.fill([self.P(*p) for p in pts], kolor, op)

    def okrag(self, c, r, pioro="gruba", kolor="#000", fill=None, w=None):
        self.a.circle(self.P(*c), r * self.k, pioro, kolor, fill, w)

    def luk(self, c, r, a0, a1, pioro="gruba", kolor="#000", n=48):
        pts = [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.linia(pts, pioro, kolor)

    def tekst(self, p, txt, h=2.5, anchor="middle", rot=0.0, dx=0.0, dy=0.0, **kw):
        X, Y = self.P(*p)
        self.a.text((X + dx, Y + dy), txt, h, anchor, rot, **kw)

    def etykieta(self, p, txt, pref=(1, -1), **kw):
        return self.a.etykieta(self.P(*p), txt, pref, **kw)

    def os(self, a, b, wydl=0.0):
        """Linia osiowa od a do b (z wydłużeniem w metrach na obu końcach)."""
        (ax, ay), (bx, by) = a, b
        L = math.hypot(bx - ax, by - ay) or 1.0
        ux, uy = (bx - ax) / L, (by - ay) / L
        self.odcinek((ax - ux * wydl, ay - uy * wydl), (bx + ux * wydl, by + uy * wydl), "osiowa")

    def wymiar(self, p1, p2, odst, txt=None, kier="a", h=2.3, d=2, tlo=False, przedluz=True):
        """Wymiar liniowy między punktami modelu p1, p2. kier: 'h' – poziomy, 'v' – pionowy, 'a' – równoległy.
        odst – odległość linii wymiarowej od p1–p2 w mm papieru (znak – strona)."""
        A, B = self.P(*p1), self.P(*p2)
        if kier == "h":
            dirv = (1.0, 0.0) if B[0] >= A[0] else (-1.0, 0.0)
            L = abs(p2[0] - p1[0]) if not self.lustro else abs(p2[0] - p1[0])
        elif kier == "v":
            dirv = (0.0, -1.0) if B[1] <= A[1] else (0.0, 1.0)
            L = abs(p2[1] - p1[1])
        else:
            dx, dy = B[0] - A[0], B[1] - A[1]
            Lm = math.hypot(dx, dy) or 1.0
            dirv = (dx / Lm, dy / Lm)
            L = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        nx, ny = -dirv[1], dirv[0]
        # położenie linii wymiarowej
        if kier == "h":
            yl = min(A[1], B[1]) - odst if odst > 0 else max(A[1], B[1]) - odst
            a2, b2 = (A[0], yl), (B[0], yl)
            ext = [(A, a2), (B, b2)]
        elif kier == "v":
            xl = max(A[0], B[0]) + odst if odst > 0 else min(A[0], B[0]) + odst
            a2, b2 = (xl, A[1]), (xl, B[1])
            ext = [(A, a2), (B, b2)]
        else:
            a2 = (A[0] + nx * odst, A[1] + ny * odst)
            b2 = (B[0] + nx * odst, B[1] + ny * odst)
            ext = [(A, a2), (B, b2)]
        if przedluz:
            for (p, q) in ext:
                vx, vy = q[0] - p[0], q[1] - p[1]
                Ln = math.hypot(vx, vy)
                if Ln > 0.5:
                    ux, uy = vx / Ln, vy / Ln
                    self.a.path([(p[0] + ux * 0.8, p[1] + uy * 0.8), (q[0] + ux * 1.5, q[1] + uy * 1.5)], "wymiar")
        self.a.path([a2, b2], "wymiar")
        Ld = math.hypot(b2[0] - a2[0], b2[1] - a2[1])
        if Ld > 0.2:
            u = ((b2[0] - a2[0]) / Ld, (b2[1] - a2[1]) / Ld)
            if Ld > 7:
                self.a.strzalka(b2, u)
                self.a.strzalka(a2, (-u[0], -u[1]))
            else:
                self.a.strzalka(a2, u)
                self.a.strzalka(b2, (-u[0], -u[1]))
                self.a.path([(a2[0] - u[0] * 4, a2[1] - u[1] * 4), (b2[0] + u[0] * 4, b2[1] + u[1] * 4)], "wymiar")
        t = txt if txt is not None else self.a.n(L, d)
        m = ((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2)
        ang = math.degrees(math.atan2(b2[1] - a2[1], b2[0] - a2[0]))
        if ang > 90:
            ang -= 180
        if ang < -90:
            ang += 180
        # tekst nad linią (po stronie odsunięcia)
        off = 1.0
        rad = math.radians(ang)
        px, py = m[0] + math.sin(rad) * off, m[1] - math.cos(rad) * off
        w = self.a.szer_tekstu(t, h)
        if Ld < w + 2 and kier != "v":
            px = max(a2[0], b2[0]) + 2 + w / 2 if abs(ang) < 45 else px
        self.a.text((px, py), t, h, "middle", ang, tlo=tlo)
        return L

    def wymiar_r(self, c, r, kat_deg, txt=None, h=2.3, prefix="R"):
        C = self.P(*c)
        a = math.radians(kat_deg)
        E = self.P(c[0] + r * math.cos(a), c[1] + r * math.sin(a))
        self.a.path([C, E], "wymiar")
        L = math.hypot(E[0] - C[0], E[1] - C[1]) or 1
        self.a.strzalka(E, ((E[0] - C[0]) / L, (E[1] - C[1]) / L))
        t = txt if txt is not None else "%s %s" % (prefix, self.a.n(r, 2))
        m = ((C[0] + E[0]) / 2, (C[1] + E[1]) / 2)
        ang = -kat_deg
        if ang > 90:
            ang -= 180
        if ang < -90:
            ang += 180
        rad = math.radians(ang)
        self.a.text((m[0] + math.sin(rad) * 1.0, m[1] - math.cos(rad) * 1.0), t, h, "middle", ang, tlo=True)

    def wymiar_kat(self, c, r, a0, a1, txt=None, h=2.3):
        """Wymiar kątowy: łuk o promieniu r (m) wokół c od kąta a0 do a1 (stopnie, przeciwnie do zegara w modelu)."""
        n = 32
        pts = [self.P(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                      c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.a.path(pts, "wymiar")
        for (p, q) in ((pts[0], pts[1]), (pts[-1], pts[-2])):
            L = math.hypot(p[0] - q[0], p[1] - q[1]) or 1
            self.a.strzalka(p, ((p[0] - q[0]) / L, (p[1] - q[1]) / L), dl=2.0, szer=0.8)
        am = math.radians((a0 + a1) / 2)
        t = txt if txt is not None else "%s°" % self.a.n(abs(a1 - a0), 1)
        X, Y = self.P(c[0] + (r + 0.0) * math.cos(am), c[1] + (r + 0.0) * math.sin(am))
        Cx, Cy = self.P(*c)
        dx, dy = X - Cx, Y - Cy
        L = math.hypot(dx, dy) or 1
        self.a.text((X + dx / L * 3.5, Y + dy / L * 3.5 + 0.8), t, h, "middle", tlo=True)

    def tytul_widoku(self, p_mm, txt, skala=True):
        t = self.a.t(txt) + ("  1:%g" % self.skala if skala else "")
        self.a.text(p_mm, t, 3.2, "start", bold=True)
        w = self.a.szer_tekstu(t, 3.2)
        self.a.path([(p_mm[0], p_mm[1] + 1.2), (p_mm[0] + w, p_mm[1] + 1.2)], "cienka")

    def odcinki_siatki(self, seg, du=0.0, dv=0.0, ukryte=True, pioro_w="srednia", lustro_u=False):
        """Odcinki z rzutu siatki [u0, v0, u1, v1, widoczny] (metry) przesunięte o (du, dv)."""
        vis, hid = [], []
        for u0, v0, u1, v1, w in seg:
            if lustro_u:
                u0, u1 = -u0, -u1
            A, B = self.P(u0 + du, v0 + dv), self.P(u1 + du, v1 + dv)
            ob = self.obszar or self.a.ramka_wew
            c = przytnij_odcinek(A, B, ob)
            if c is None:
                continue
            A, B = c
            t0, u0_, t1, u1_ = self.a.tabelka
            if t0 < A[0] < t1 and u0_ < A[1] < u1_ and t0 < B[0] < t1 and u0_ < B[1] < u1_:
                continue
            (vis if w else hid).append((A, B))
        # łączenie w ścieżki (mniej elementów)
        for lst, pioro in ((hid, "ukryta"), (vis, pioro_w)):
            if pioro == "ukryta" and not ukryte:
                continue
            if not lst:
                continue
            p = PIORA[pioro]
            d = " ".join("M%.2f %.2f L%.2f %.2f" % (a[0], a[1], b[0], b[1]) for a, b in lst
                         if abs(a[0] - b[0]) + abs(a[1] - b[1]) > 0.02)
            a = 'stroke="#000" stroke-width="%.3f" fill="none" stroke-linecap="round"' % (
                p["w"] * (0.8 if pioro == "ukryta" else 1.0))
            if "dash" in p:
                a += ' stroke-dasharray="1.2,0.8"'
            self.a.el.append('<path d="%s" %s/>' % (d, a))


def przytnij_odcinek(A, B, ob):
    """Liang–Barsky: odcinek A–B przycięty do prostokąta ob = (x0, y0, x1, y1); None, gdy poza."""
    x0, y0, x1, y1 = ob
    dx, dy = B[0] - A[0], B[1] - A[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, A[0] - x0), (dx, x1 - A[0]), (-dy, A[1] - y0), (dy, y1 - A[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return None
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return None
    return (A[0] + dx * t0, A[1] + dy * t0), (A[0] + dx * t1, A[1] + dy * t1)


def zakres_odcinkow(seg):
    us = [s[0] for s in seg] + [s[2] for s in seg]
    vs = [s[1] for s in seg] + [s[3] for s in seg]
    return (min(us), max(us), min(vs), max(vs)) if us else (0, 1, 0, 1)
