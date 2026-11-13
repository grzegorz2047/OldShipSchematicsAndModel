"""Tabela rzędnych po wręgach (rozdział 02) → tabela generatora (wiersze równoległe do stępki) w parametry.py.

    python blender/projekt_rzednych.py [--zapisz]

Dla każdego wręgu z LINIE_WREGI składam przekrój (wysokość → półszerokość): dejwud (0,13) od wrębu do linii
brodaty, punkty na wodnicach −2,5 … +0,5, największa szerokość, pokład, nadburcie; nad nadburciem (pokład rufowy,
głowica dziobu) przedłużam zawał połową nachylenia między pokładem a nadburciem. Do półszerokości dodaję
poszycie (0,065 m, malejące do zera przy dejwudzie). Potem próbkuję przekrój na wysokościach h nad wrębem
(wiersze RZEDNE_H) – generator interpoluje te wiersze wzdłuż znormalizowanej długości (rzedne.py).
Bez --zapisz drukuje tabelę; z --zapisz przepisuje blok RZEDNE w parametry.py.
"""
import os
import re
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narzedzia_math as nm  # noqa: E402
import parametry as PR  # noqa: E402
from rzedne import Kadlub  # noqa: E402

K = PR.KADLUB
kd = Kadlub(K, [], [], [])
PL = K["POSZYCIE_GR"]
KH = K["STEPKA_SZER"] / 2
WL = [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5]


def przekroj(st):
    z, keel, rab, beard, wl, deck, deckhb, b, hb, rail, top = st
    pts = [(rab, 0.13)]
    if beard > rab + 0.05:
        pts.append((beard, 0.13))
    for y, v in zip(WL, wl):
        if v is None or y <= beard + 0.02:
            continue
        pts.append((y, v))
    pts += [(hb, b), (deck, deckhb), (rail, top)]
    slope = (top - deckhb) / (rail - deck)
    for dz in (0.8, 1.6, 2.4):
        pts.append((rail + dz, top + 0.5 * slope * dz))
    pts = sorted(pts)
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 0.03:
            continue
        out.append(p)
    a = np.array(out)
    # poszycie
    y = a[:, 1] + PL * np.clip((a[:, 1] - 0.13) / 0.15, 0, 1)
    y[a[:, 1] <= 0.131] = KH
    return a[:, 0], y


WIERSZE = [0.0, 0.03, 0.08, 0.15, 0.25, 0.38, 0.55, 0.75, 1.0, 1.3, 1.65, 2.05, 2.5, 2.8, 3.0, 3.15, 3.3, 3.45,
           3.6, 3.8, 4.05, 4.35, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5]
STACJE = [round(st[0] + PR.LINIE_PRZESUNIECIE, 3) for st in PR.LINIE_WREGI]
tab = []
secs = [przekroj(st) for st in PR.LINIE_WREGI]
for h in WIERSZE:
    row = []
    for s, (zz, yy) in zip(STACJE, secs):
        z = float(kd.zk(s)) + h
        a, f = kd.a_of_h(h), kd.f_of_h(h)
        if not (a < s < f) or z < zz[0] - 1e-6:
            row.append(None)
            continue
        if z > zz[-1]:
            row.append(round(float(yy[-1]), 3))
            continue
        row.append(round(float(nm.pchip(zz, yy, z)), 3))
    tab.append(row)


def fmt():
    out = ["# >>> RZEDNE (blok przepisywany przez projekt_rzednych.py)",
           "RZEDNE_H = %r" % WIERSZE, "RZEDNE_S = %r" % STACJE, "RZEDNE = ["]
    for h, row in zip(WIERSZE, tab):
        cells = ", ".join("None" if v is None else ("%.3f" % v) for v in row)
        out.append("    [%s],  # h = %.2f" % (cells, h))
    out.append("]")
    out.append("# <<< RZEDNE")
    return "\n".join(out)


txt = fmt()
print(txt)
for z in (0.0, 0.9):
    print("z=%.2f: koniec rufowy s=%.2f, dziobnica s=%.2f" % (z, kd.a_of_z(z), float(np.interp(z, kd.stem_z, kd.stem_s))))
if "--zapisz" in sys.argv:
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parametry.py")
    src = open(p, encoding="utf-8").read()
    src = re.sub(r"# >>> RZEDNE.*?# <<< RZEDNE", lambda m: txt, src, flags=re.S)
    open(p, "w", encoding="utf-8").write(src)
    print("zapisano", p)
