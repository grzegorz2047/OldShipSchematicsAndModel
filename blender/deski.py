"""Deski poszycia, nadburcia i pokładu z układu pasów (nie ze zdjęcia): siatka (narzedzia.Siatka) cięta w przestrzeni
UV wzdłuż szwów między pasami (v = k·szerokość) i styków klepek (u = przesunięcie pasa + n·długość klepki), każda deska
dostaje własne UV w atlasie desek (jeden z R rzędów tekstury, przesunięcie wzdłuż o całkowitą liczbę wręgów /
pokładników – kołki zostają na wręgach) i własny odcień (kolor wierzchołków 'odcien'). Styk klepek to pasek ścian
szerokości szwu zmapowany na szew w atlasie (granica rzędów, v = 0) – ciemna kreska i rowek w mapie normalnych.

Atlas (tekstury_deski.py): R rzędów po 'szer' metrów, długość L_tex (wielokrotność odstępu wręgów), szwy na granicach
rzędów, kołki co 'krok' na u = j·krok + KOLEK_U. Kafel materiału (parametry.MATERIALY) = (L_tex, R·szer).

Cięcie dzieli wielokąty (zachowuje ściany sąsiednie: wierzchołek podziału wstawiany do sąsiednich ścian – siatka
zostaje zamknięta, bez połączeń T) i nie zmienia kształtu (nowe wierzchołki leżą na krawędziach).
"""
import math
import zlib

import numpy as np

EPS = 0.0025          # m w UV: wierzchołek bliżej linii cięcia leży na niej (bez okruchów < spaw 2 mm)


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def _tnij(sk, fis, os_, c, cache, splits, uv_of, rodz=None):
    """Tnie ściany fis linią uv[os_] = c (uv_of(fi) – UV narożników używane do cięcia). Zwraca nową listę ścian."""
    out = []
    for fi in fis:
        f = sk.f[fi]
        uv = uv_of[fi]
        d = [q[os_] - c for q in uv]
        s = [0 if abs(x) < EPS else (1 if x > 0 else -1) for x in d]
        if not (1 in s and -1 in s):
            out.append(fi)
            continue
        A, B, Auv, Buv, Asuv, Bsuv = [], [], [], [], [], []
        suv = sk.uv[fi]
        n = len(f)
        for i in range(n):
            j = (i + 1) % n
            if s[i] >= 0:
                A.append(f[i]); Auv.append(uv[i]); Asuv.append(suv[i])
            if s[i] <= 0:
                B.append(f[i]); Buv.append(uv[i]); Bsuv.append(suv[i])
            if s[i] * s[j] < 0:
                t = d[i] / (d[i] - d[j])
                a, b = f[i], f[j]
                key = (min(a, b), max(a, b), os_, round(c, 7))
                m = cache.get(key)
                if m is None:
                    m = sk.vert(_lerp(sk.v[a], sk.v[b], t))
                    cache[key] = m
                    splits.setdefault((min(a, b), max(a, b)), []).append(m)
                muv = _lerp(uv[i], uv[j], t)
                msuv = _lerp(suv[i], suv[j], t)
                A.append(m); Auv.append(muv); Asuv.append(msuv)
                B.append(m); Buv.append(muv); Bsuv.append(msuv)
        if len(A) >= 3 and len(B) >= 3:
            sk.f[fi] = tuple(A)
            uv_of[fi] = tuple(Auv)
            sk.uv[fi] = tuple(Asuv)
            sk.f.append(tuple(B))
            uv_of.append(tuple(Buv))
            sk.uv.append(tuple(Bsuv))
            sk.mat.append(sk.mat[fi])
            sk.flat.append(sk.flat[fi])
            sk.odcien.append(sk.odcien[fi])
            if rodz is not None:
                rodz[len(sk.f) - 1] = rodz.get(fi, fi)
            out += [fi, len(sk.f) - 1]
        else:
            out.append(fi)
    return out


def _napraw_t(sk, splits):
    """Wierzchołki podziału wstawione do ścian, które wciąż mają krawędź sprzed cięcia (połączenia T)."""
    V = sk.v

    def wnetrze(a, b, glebokosc=0):
        key = (min(a, b), max(a, b))
        ms = splits.get(key)
        if not ms or glebokosc > 30:
            return []
        pa, pb = np.array(V[a]), np.array(V[b])
        d = pb - pa
        L2 = float(d @ d) + 1e-18
        ms = sorted(ms, key=lambda m: float((np.array(V[m]) - pa) @ d) / L2)
        seq = [a] + ms + [b]
        full = []
        for x, y in zip(seq[:-1], seq[1:]):
            full.append(x)
            full += wnetrze(x, y, glebokosc + 1)
        return full[1:]

    n_fix = 0
    for fi in range(len(sk.f)):
        f = sk.f[fi]
        if not any((min(f[i], f[(i + 1) % len(f)]), max(f[i], f[(i + 1) % len(f)])) in splits for i in range(len(f))):
            continue
        uv = sk.uv[fi]
        nf, nuv = [], []
        zm = False
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            nf.append(a)
            nuv.append(uv[i])
            ins = wnetrze(a, b)
            if ins:
                zm = True
                pa, pb = np.array(V[a]), np.array(V[b])
                d = pb - pa
                L2 = float(d @ d) + 1e-18
                for m in ins:
                    t = float((np.array(V[m]) - pa) @ d) / L2
                    nf.append(m)
                    nuv.append(_lerp(uv[i], uv[(i + 1) % len(f)], t))
        if zm:
            sk.f[fi] = tuple(nf)
            sk.uv[fi] = tuple(nuv)
            n_fix += 1
    return n_fix


def potnij(sk, strefy, seed=7):
    """strefy: lista słowników
        twarze  – indeksy ścian strefy (UV narożników w metrach: u wzdłuż desek, v w poprzek)
        uklad   – dict(szer, krok, dl (w krokach), przes (krokach na pas), okres (pasów), rzedy, L_tex, szew,
                       odcien=(jasność ±, ciepło ±))
        pasy    – None (cięcie co szer od v0) albo {indeks_ściany: (k, szerokość pasa)} – pasy z siatki (berghołty;
                  v narożników = odległość od dolnej krawędzi pasa)
        v0      – położenie szwu zerowego (m)
        nazwa   – do ziarna losowania
    Zwraca statystykę. UV wynikowe (metry atlasu) w sk.uv; odcienie w sk.odcien."""
    stat = dict(deski=0, styki=0, sciany_przed=len(sk.f))
    cache, splits = {}, {}
    uv_of = list(sk.uv)          # UV do cięcia (metryczne, przed przemapowaniem)
    for st in strefy:
        U = st["uklad"]
        w, krok, L = U["szer"], U["krok"], U["dl"] * U["krok"]
        fis = list(st["twarze"])
        v0 = st.get("v0", 0.0)
        pasy = st.get("pasy")
        # 1. szwy wzdłużne (strefy cięte)
        if pasy is None:
            vs = [q[1] for fi in fis for q in uv_of[fi]]
            if not vs:
                continue
            k0, k1 = int(math.floor((min(vs) - v0) / w)), int(math.ceil((max(vs) - v0) / w))
            for k in range(k0 + 1, k1):
                fis = _tnij(sk, fis, 1, v0 + k * w, cache, splits, uv_of)

        rodz = {}

        def pas(fi):
            if pasy is not None:
                k, bw = pasy[rodz.get(fi, fi)]
                return (k, 0.0, bw)
            vc = sum(q[1] for q in uv_of[fi]) / len(uv_of[fi])
            k = int(math.floor((vc - v0) / w))
            return (k, v0 + k * w, v0 + (k + 1) * w)
        # 2. styki klepek: na każdym pasie osobno (przesunięcie schodkowe)
        po_pasie = {}
        for fi in fis:
            po_pasie.setdefault(pas(fi)[0], []).append(fi)
        nowe = []
        styki_pasa = {}
        for k, lst in po_pasie.items():
            us = [q[0] for fi in lst for q in uv_of[fi]]
            off = ((k * U["przes"]) % U["okres"]) * krok
            n0, n1 = int(math.floor((min(us) - off) / L)), int(math.ceil((max(us) - off) / L))
            sty = [off + n * L for n in range(n0, n1 + 1) if min(us) + 0.05 < off + n * L < max(us) - 0.05]
            styki_pasa[k] = sty
            for ub in sty:
                lst = _tnij(sk, lst, 0, ub - U["szew"] / 2, cache, splits, uv_of, rodz)
                lst = _tnij(sk, lst, 0, ub + U["szew"] / 2, cache, splits, uv_of, rodz)
            stat["styki"] += len(sty)
            nowe += [(fi, k) for fi in lst]
        # 3. przemapowanie UV na atlas, odcień deski
        R, Lt = U["rzedy"], U["L_tex"]
        oj, oc = U.get("odcien", (0.07, 0.04))
        deski = {}
        for fi, k in nowe:
            _, vlo, vhi = pas(fi)
            q = uv_of[fi]
            uc = sum(p[0] for p in q) / len(q)
            sty = styki_pasa.get(k, [])
            szew = [ub for ub in sty if abs(uc - ub) < U["szew"] / 2]
            off = ((k * U["przes"]) % U["okres"]) * krok
            n = int(math.floor((uc - off) / L))
            klucz = (st["nazwa"], k, n)
            if klucz not in deski:
                rng = np.random.default_rng(zlib.crc32(repr((seed,) + klucz).encode()))
                deski[klucz] = (int(rng.integers(0, R)), int(rng.integers(0, max(1, round(Lt / krok)))),
                                1.0 + rng.uniform(-oj, oj), rng.uniform(-oc, oc), rng.uniform(0, Lt))
            r, m, jas, cie, useed = deski[klucz]
            bw = vhi - vlo
            if pasy is None or 0.82 * w <= bw <= 1.22 * w:
                sv, cv = w / max(bw, 1e-6), 0.0
            else:
                sv, cv = 1.0, max(0.0, (w - bw) / 2)
            if szew:
                ub = szew[0]
                sk.uv[fi] = tuple((useed + (p[1] - vlo) * sv, (p[0] - ub)) for p in q)
            else:
                sk.uv[fi] = tuple((p[0] + m * krok, r * w + cv + (p[1] - vlo) * sv) for p in q)
            sk.odcien[fi] = (jas * (1 + cie), jas, jas * (1 - 1.5 * cie))
        stat["deski"] += len(deski)
    stat["naprawione_T"] = _napraw_t(sk, splits)
    stat["sciany_po"] = len(sk.f)
    return stat
