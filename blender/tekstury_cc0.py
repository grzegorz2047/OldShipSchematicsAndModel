"""Kopie robocze tekstur fotograficznych CC0 (Poly Haven) dla zestawu 'polyhaven' (zwykły Python, PIL).

    python blender/tekstury_cc0.py <katalog_tekstur_cc0> <build/tekstury_cc0>

Wejście: katalog z podkatalogami <id>/ (diff, nor_gl, arm 2K). Spis zasobów (pliki, rozmiar kafla w metrach, strona,
licencja): <katalog>/_spis.json, a gdy go brak – tekstury_cc0_spis.json obok tego modułu. Pobranych plików nie
zmienia – w wyjściu powstają kopie (JPEG):
  <id>_kolor.jpg       kolor; tekstury z 'szarosc' odbarwione i rozjaśnione (kolor daje mnożnik materiału: farby, płótno)
  <id>_normalne.jpg    mapa normalnych OpenGL (jak w źródle; przy obrocie o 90° kanały R/G przestawione)
  <id>_szorstkosc.jpg  ARM: R = AO, G = chropowatość, B = metaliczność (glTF metallicRoughness), metal 0 dla drewna
Deski: kierunek słojów rozpoznawany z obrazu (profil jasności w poprzek desek ma okresowe ciemne spoiny); obraz
obracany tak, żeby słoje biegły wzdłuż u (jak UV generatora), a liczba desek na kafel trafia do _kafle.json –
generator dobiera z niej rozmiar kafla tak, by deska miała szerokość z parametru (20–28 cm).
"""
import json
import os
import shutil
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametry as PR  # noqa: E402


def okres(profil, lo=3, hi=30):
    """Liczba okresów (desek) na kafel z profilu jasności (FFT; profil kafla jest okresowy). Przy wyraźnej
    harmonicznej bierze podstawę (najniższe k, którego amplituda ≥ 0,45 maksimum i które dzieli k_max)."""
    p = profil - profil.mean()
    f = np.abs(np.fft.rfft(p))
    k = int(np.argmax(f[lo:hi + 1])) + lo
    for d in (4, 3, 2):
        if k % d == 0 and k // d >= lo and f[k // d] >= 0.45 * f[k]:
            k = k // d
            break
    sila = float(f[k] / (np.median(f[1:hi + 1]) + 1e-9))
    return k, sila


def sloje_kierunek(a):
    """True, gdy słoje biegną pionowo (gradient jasności w poprzek słojów, tj. wzdłuż x, jest silniejszy)."""
    gx = np.abs(np.diff(a, axis=1)).mean()
    gy = np.abs(np.diff(a, axis=0)).mean()
    return bool(gx > gy)


def analiza_desek(img):
    """(deski_na_kafel, słoje_pionowo, siła): kierunek z anizotropii gradientu (słoje i spoiny wzdłuż desek),
    liczba desek z okresowości profilu w poprzek."""
    a = np.asarray(img.convert("L"), dtype=np.float64)
    pion = sloje_kierunek(a)
    k, s = okres(a.mean(0) if pion else a.mean(1))
    return int(k), pion, s


def wczytaj_spis(src):
    """Spis zasobów CC0 {id: opis}: <src>/_spis.json (lista), a gdy go brak – tekstury_cc0_spis.json obok modułu
    (słownik z listą 'zasoby')."""
    p = os.path.join(src, "_spis.json")
    if not os.path.exists(p):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tekstury_cc0_spis.json")
    d = json.load(open(p, encoding="utf-8"))
    lista = d["zasoby"] if isinstance(d, dict) else d
    return {e["id"]: e for e in lista}


def main():
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    spis = wczytaj_spis(src)
    kafle = {}
    for mat, spec in PR.MATERIALY_CC0.items():
        tid = spec["id"]
        if tid in kafle:
            continue
        e = spis[tid]
        d = os.path.join(src, tid)
        col = Image.open(os.path.join(d, e["pliki"]["diff"])).convert("RGB")
        nor = Image.open(os.path.join(d, e["pliki"]["nor_gl"])).convert("RGB")
        arm = Image.open(os.path.join(d, e["pliki"]["arm"])).convert("RGB")
        info = dict(kafel_m=e["kafel_m"], deski=None, obrot=False)
        pion = None
        if spec.get("deski"):
            n, pion, sila = analiza_desek(col)
            info.update(deski=n, sloje_pionowo=pion, sila_okresu=round(sila, 1))
        elif spec.get("sloje"):
            pion = sloje_kierunek(np.asarray(col.convert("L"), dtype=np.float64))
            info.update(sloje_pionowo=pion)
        if pion:
            # obrót o 90° (słoje wzdłuż u); w mapie normalnych R i G zamieniają się (G odwrócone dla OpenGL)
            col = col.transpose(Image.Transpose.ROTATE_90)
            arm = arm.transpose(Image.Transpose.ROTATE_90)
            nr = np.asarray(nor.transpose(Image.Transpose.ROTATE_90)).astype(np.int16)
            r, g = nr[..., 0].copy(), nr[..., 1].copy()
            nr[..., 0] = 255 - g
            nr[..., 1] = r
            nor = Image.fromarray(nr.clip(0, 255).astype(np.uint8), "RGB")
            info["obrot"] = True
        if spec.get("szarosc"):
            a = np.asarray(col).astype(np.float64) / 255.0
            g = a.mean(-1)
            g = g / max(np.percentile(g, 75), 1e-3) * 0.82        # jasna szarość, kontrast słojów zachowany
            g = np.clip(0.5 + (g - 0.5) * spec.get("kontrast", 1.0), 0.03, 0.97)
            col = Image.fromarray((np.stack([g, g, g], -1) * 255 + 0.5).astype(np.uint8), "RGB")
        # boki potęgą dwójki (np. rough_linen 2048×2052 → 2048²)
        pot = lambda v: 1 << int(round(np.log2(v)))
        rozm = (pot(col.size[0]), pot(col.size[1]))
        if rozm != col.size:
            col, nor, arm = (im.resize(rozm, Image.Resampling.LANCZOS) for im in (col, nor, arm))
        col.save(os.path.join(dst, tid + "_kolor.jpg"), quality=90, subsampling=0)
        nor.save(os.path.join(dst, tid + "_normalne.jpg"), quality=92, subsampling=0)
        armn = np.asarray(arm).copy()
        if not spec.get("metal"):
            armn[..., 2] = 0
        Image.fromarray(armn, "RGB").save(os.path.join(dst, tid + "_szorstkosc.jpg"), quality=90, subsampling=0)
        kafle[tid] = info
    with open(os.path.join(dst, "_kafle.json"), "w", encoding="utf-8") as f:
        json.dump(kafle, f, ensure_ascii=False, indent=1)
    # licencje i autorzy obok kopii (CC0 nie wymaga, ale zostawiamy źródło)
    with open(os.path.join(dst, "_zrodla.json"), "w", encoding="utf-8") as f:
        json.dump({t: dict(nazwa=spis[t]["nazwa"], strona=spis[t]["strona"], licencja=spis[t]["licencja"],
                           autorzy=spis[t]["autorzy"]) for t in kafle}, f, ensure_ascii=False, indent=1)
    print("CC0 " + json.dumps(kafle, ensure_ascii=False))


if __name__ == "__main__":
    main()
