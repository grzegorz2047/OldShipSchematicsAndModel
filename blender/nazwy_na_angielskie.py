"""Zamiana polskich nazw w gotowym pliku GLB na angielskie (zwykły Python 3, bez Blendera, bez dodatkowych pakietów).

    python blender/nazwy_na_angielskie.py WEJŚCIE.glb WYJŚCIE.glb [--mapa data/names-map.csv] [--raport PLIK.json]
    python blender/nazwy_na_angielskie.py --sprawdz PLIK.glb [--mapa data/names-map.csv]

Zmienia tylko część JSON pliku GLB: nazwy węzłów (nodes), siatek (meshes), materiałów (materials) i obrazów
(images), klucze w polach extras oraz znane wartości tekstowe w extras (opisy osi ruchu, nazwy czynności, nazwy
obiektów, listy węzłów). Blok binarny (geometria, obrazy) przechodzi bez zmian, bajt w bajt.

Skąd tłumaczenia (w tej kolejności):
1. data/names-map.csv (kolumny category, polish, english) – kategoria zależy od miejsca w pliku, np. węzeł:
   glb_node, collision_node, object…; klucz extras: glb_extras_key, json_key; opis osi ruchu: text;
2. reguły z nazwy_publiczne.py (słowa, wzorce nazw z burtą i numerem, np. lina_dyn_<grupa>_<nr> →
   rope_dynamic_<group>_<nr>, opisy osi ruchu, klucze);
3. słownik DODATKI niżej – nazwy, których nie ma w danych publicznych (siatki wspólne kilku węzłów, materiały
   scalonych siatek <materiał>__<grupa>, obrazy tekstur, trzy opisy tekstowe węzłów pomocniczych).
Narzędzie jest ścisłe: gdy jakaś nazwa, klucz albo tekst nie ma odpowiednika, nie zapisuje pliku i kończy się
kodem 1 z listą braków. Na końcu sprawdza wynik: brak polskich liter i polskich słów (słowa z kolumny polish mapy,
których nie ma w kolumnie english) w nazwach, kluczach i tekstach, różne nazwy angielskie dla różnych węzłów.
"""
import csv
import hashlib
import json
import os
import re
import struct
import sys

# wyjście na konsolę w UTF-8 także na Windows (strona kodowa konsoli nie zna wszystkich znaków komunikatów)
for _strumien in (sys.stdout, sys.stderr):
    try:
        _strumien.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))

import nazwy_publiczne as NP  # noqa: E402

POLSKIE_ZNAKI = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
# skróty i słowa wspólne obu języków (jak NEUTRALNE w kontrola_publiczna.py)
NEUTRALNE = {"glb", "snow", "log", "tex", "nrm"}

# kategorie mapy według miejsca w pliku (kolejność = pierwszeństwo)
KAT_WEZEL = ("glb_node", "collision_node", "object", "belaying_point", "obstacle", "spar", "station", "sail")
KAT_MATERIAL = ("material", "key")
KAT_KLUCZ = ("glb_extras_key", "json_key")
KAT_TEKST = ("text",)
KAT_CZYNNOSC = ("activity",)

# ------------------------------------------------------------------ nazwy spoza danych publicznych
DODATKI = {
    # węzły (pliki LOD: jedna scalona siatka na plik)
    "wezel": {"bryg_lod1": "snow_lod1", "bryg_lod2": "snow_lod2"},
    # siatki wspólne kilku węzłów
    "siatka": {"dzialko_relingowe": "swivel_gun", "dzialo_laweta": "gun_carriage", "dzialo_lufa": "gun_barrel",
               "dzialo_laweta_polyhaven": "gun_carriage_polyhaven_cc0", "dzialo_lufa_polyhaven": "gun_barrel_polyhaven_cc0",
               "bryg_lod1": "snow_lod1", "bryg_lod2": "snow_lod2"},
    # materiały spoza mapy
    "material": {"maska_wody": "water_mask"},
    # słowa w nazwach obrazów (td_ – tekstury z fotografii CC0 i układu desek, tekstury_deski.py)
    "slowo_obrazu": {"td": "tex", "sosna": "pine", "kolor": "color", "normalne": "normal", "szorstkosc": "roughness",
                     "orm": "orm", "ao": "ao", "jpg": "jpg", "png": "png", "1k": "1k", "lina": "rope", "okno": "window",
                     "krata": "grating", "farba": "paint", "biala": "white", "czarna": "black", "gladka": "smooth",
                     "mat": "matte", "ochra": "ochre", "czerwona": "red", "niebieska": "blue", "laweta": "carriage",
                     "burta": "side", "poklad": "deck", "drewno": "wood", "zelazo": "iron", "lufa": "barrel",
                     "braz": "bronze", "plotno": "canvas", "dno": "bottom", "polyhaven": "polyhaven"},
    # teksty w extras węzłów pomocniczych (wyposazenie.py) i wzór przełożenia koła sterowego (sterowanie.py)
    "tekst": {
        "maska wody wewnątrz łodzi: obrys zewnętrznej strony poszycia na wodnicy łodzi (0.27 m nad spodem stępki, "
        "w świecie z = 0); gra nie rysuje wody wewnątrz obrysu (szablon/głębia), węzeł niewidoczny":
            "water mask inside the boat: outline of the outer face of the planking at the boat's waterline (0.27 m "
            "above the bottom of the keel, world z = 0); the game does not draw water inside the outline "
            "(stencil/depth); the node is invisible",
        "gra podmienia materiał na rysowany tylko do głębi albo szablonu":
            "the game replaces the material with one drawn only to depth or stencil",
        "n = L_rumpla·sin(35°) / (π·D_bębna) = 3.00·0.574 / (π·0.30)":
            "n = L_tiller·sin(35°) / (π·D_drum) = 3.00·0.574 / (π·0.30)",
    },
}
# wartości extras, które są nazwami węzłów albo listą nazw węzłów
KLUCZE_WEZLOW = {"obiekt", "od_obiekt", "do_obiekt", "wariant"}
KLUCZE_LISTY_WEZLOW = {"wezly"}
SUFIKS = re.compile(r"^(?P<b>.+?)\.(?P<n>\d{3})$")      # kopia Blendera: nazwa.001


def wczytaj_glb(path):
    with open(path, "rb") as f:
        d = f.read()
    magic, ver, length = struct.unpack("<III", d[:12])
    if magic != 0x46546C67 or ver != 2 or length != len(d):
        raise ValueError("to nie jest plik GLB 2.0: %s" % path)
    chunks, o = [], 12
    while o < len(d):
        n, typ = struct.unpack("<II", d[o:o + 8])
        chunks.append([typ, d[o + 8:o + 8 + n]])
        o += 8 + n
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise ValueError("brak bloku JSON: %s" % path)
    return json.loads(chunks[0][1].decode("utf-8")), chunks


def zapisz_glb(path, gltf, chunks):
    js = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    out = [struct.pack("<II", len(js), 0x4E4F534A) + js]
    for typ, data in chunks[1:]:
        out.append(struct.pack("<II", len(data), typ) + data)
    body = b"".join(out)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)


class Tlumacz:
    def __init__(self, mapa):
        self.mapa = {}                      # (kategoria, polska) → angielska
        self.wiersze = []
        with open(mapa, encoding="utf-8") as f:
            for r in csv.DictReader(l for l in f if not l.startswith("#")):
                self.mapa.setdefault((r["category"], r["polish"]), r["english"])
                self.wiersze.append(r)
        self.braki = []                     # (rodzaj, nazwa, gdzie)
        self.zrodla = {"mapa": 0, "reguly": 0, "dodatki": 0}
        self.slowa_pl = self._slowa_polskie()

    def _slowa_polskie(self):
        pl, en = set(), set()
        for r in self.wiersze:
            pl |= {t for t in re.split(r"[^0-9a-ząćęłńóśźż]+", r["polish"].lower()) if len(t) > 2 and not t.isdigit()}
            en |= set(re.split(r"[^0-9a-z]+", r["english"].lower()))
        return pl - en - NEUTRALNE

    def _z_mapy(self, nazwa, kategorie):
        for k in kategorie:
            e = self.mapa.get((k, nazwa))
            if e is not None:
                self.zrodla["mapa"] += 1
                return e
        return None

    def _brak(self, rodzaj, nazwa, gdzie):
        self.braki.append((rodzaj, nazwa, gdzie))
        return nazwa

    # ---- nazwy
    def wezel(self, nazwa, gdzie="węzeł"):
        if nazwa is None or nazwa == "":
            return nazwa
        e = self._z_mapy(nazwa, KAT_WEZEL)
        if e is not None:
            return e
        e = NP.en(nazwa)
        if e is not None:
            self.zrodla["reguly"] += 1
            return e
        e = DODATKI["wezel"].get(nazwa)
        if e is not None:
            self.zrodla["dodatki"] += 1
            return e
        return self._brak("węzeł", nazwa, gdzie)

    def siatka(self, nazwa, wezly_siatki):
        e = DODATKI["siatka"].get(nazwa)
        if e is not None:
            self.zrodla["dodatki"] += 1
            return e
        m = SUFIKS.match(nazwa)
        if m and wezly_siatki:
            # kopia Blendera (np. 'kadlub.001' w pliku kolizji): nazwa jak węzeł, który jej używa
            return self.wezel(wezly_siatki[0], "siatka %s (nazwa węzła)" % nazwa)
        e = self._z_mapy(nazwa, KAT_WEZEL)
        if e is not None:
            return e
        e = NP.en(nazwa)
        if e is not None:
            self.zrodla["reguly"] += 1
            return e
        return self._brak("siatka", nazwa, "meshes")

    def material(self, nazwa):
        if "__" in nazwa:                    # materiał scalonej siatki: <materiał>__<grupa>
            a, b = nazwa.split("__", 1)
            return self.material(a) + "__" + self.wezel(b, "materiał %s" % nazwa)
        e = self._z_mapy(nazwa, KAT_MATERIAL)
        if e is not None:
            return e
        e = DODATKI["material"].get(nazwa) or NP.SLOWA.get(nazwa)
        if e is not None:
            self.zrodla["dodatki" if nazwa in DODATKI["material"] else "reguly"] += 1
            return e
        return self._brak("materiał", nazwa, "materials")

    def obraz(self, nazwa):
        """Nazwa obrazu z części rozdzielonych '-' (AO połączone z ORM), każda ze słów '_': najdłuższe dopasowanie
        do słownika słów obrazów, mapy materiałów i słów nazwy_publiczne; liczby bez zmian."""
        czesci = []
        for cz in nazwa.split("-"):
            t = cz.split("_")
            i, out = 0, []
            while i < len(t):
                for L in range(len(t) - i, 0, -1):
                    k = "_".join(t[i:i + L])
                    e = (DODATKI["slowo_obrazu"].get(k) if L == 1 else None) or \
                        self.mapa.get(("material", k)) or self.mapa.get(("key", k)) or NP.SLOWA.get(k)
                    if e is None and L == 1 and (k.isdigit() or k == ""):
                        e = k
                    if e is not None:
                        out.append(e)
                        i += L
                        break
                else:
                    return self._brak("obraz", nazwa, "images (słowo %r)" % t[i])
            czesci.append("_".join(out))
        self.zrodla["reguly"] += 1
        return "-".join(czesci)

    # ---- extras
    def klucz(self, k, gdzie):
        e = self._z_mapy(k, KAT_KLUCZ)
        if e is not None:
            return e
        e = NP.KLUCZE.get(k)
        if e is not None:
            self.zrodla["reguly"] += 1
            return e
        return self._brak("klucz extras", k, gdzie)

    def tekst(self, klucz, v, gdzie):
        if klucz in KLUCZE_WEZLOW:
            return self.wezel(v, gdzie)
        if klucz in KLUCZE_LISTY_WEZLOW:
            return ",".join(self.wezel(x.strip(), gdzie) for x in v.split(","))
        if klucz == "czynnosc":
            e = self._z_mapy(v, KAT_CZYNNOSC) or NP.en(v)
            return e if e is not None else self._brak("czynność", v, gdzie)
        e = self._z_mapy(v, KAT_TEKST)
        if e is not None:
            return e
        e = NP.OPISY.get(v)
        if e is not None:
            self.zrodla["reguly"] += 1
            return e
        e = DODATKI["tekst"].get(v)
        if e is not None:
            self.zrodla["dodatki"] += 1
            return e
        if re.fullmatch(r"[0-9.,+\- ]*", v):
            return v                          # pusty tekst albo liczba zapisana tekstem
        return self._brak("tekst extras", v, gdzie)

    def extras(self, o, gdzie, klucz=None):
        if isinstance(o, dict):
            return {self.klucz(k, gdzie): self.extras(v, gdzie + "/" + k, k) for k, v in o.items()}
        if isinstance(o, list):
            return [self.extras(v, gdzie, klucz) for v in o]
        if isinstance(o, str):
            return self.tekst(klucz, o, gdzie)
        return o

    # ---- kontrola wyniku
    def polskie_slowa(self, t):
        return [w for w in re.split(r"[^0-9a-ząćęłńóśźż]+", t.lower()) if w in self.slowa_pl]


def teksty_wyniku(g):
    """Wszystkie nazwy, klucze extras i teksty extras po zamianie: (gdzie, tekst)."""
    def ex(o, gdzie):
        if isinstance(o, dict):
            for k, v in o.items():
                yield gdzie + "/klucz", k
                yield from ex(v, gdzie + "/" + k)
        elif isinstance(o, list):
            for v in o:
                yield from ex(v, gdzie)
        elif isinstance(o, str):
            yield gdzie, o
    for sek in ("nodes", "meshes", "materials", "images", "textures", "scenes", "samplers", "animations", "skins",
                "cameras"):
        for i, it in enumerate(g.get(sek, [])):
            if "name" in it:
                yield "%s[%d].name" % (sek, i), it["name"]
            if "extras" in it:
                yield from ex(it["extras"], "%s[%d].extras" % (sek, i))
    if "extras" in g:
        yield from ex(g["extras"], "extras")


def sprawdz(g, T):
    """Błędy wyniku: polskie litery, polskie słowa, dwa różne węzły o tej samej nazwie angielskiej."""
    bledy = []
    for gdzie, t in teksty_wyniku(g):
        if any(c in POLSKIE_ZNAKI for c in t):
            bledy.append("polska litera: %s: %r" % (gdzie, t[:80]))
        elif T.polskie_slowa(t):
            bledy.append("polskie słowo %s: %s: %r" % (T.polskie_slowa(t)[:3], gdzie, t[:80]))
    return bledy


def zamien(wej, wyj, mapa, raport=None):
    g, chunks = wczytaj_glb(wej)
    bin_przed = hashlib.sha256(b"".join(c[1] for c in chunks[1:])).hexdigest()
    T = Tlumacz(mapa)
    stare_wezly = [n.get("name") for n in g.get("nodes", [])]
    wezly_siatki = {}
    for n in g.get("nodes", []):
        if "mesh" in n:
            wezly_siatki.setdefault(n["mesh"], []).append(n.get("name"))
    pary = {}
    for i, n in enumerate(g.get("nodes", [])):
        if "name" in n:
            n["name"] = T.wezel(n["name"], "nodes[%d]" % i)
            pary.setdefault(n["name"], set()).add(stare_wezly[i])
        if "extras" in n:
            n["extras"] = T.extras(n["extras"], "nodes[%d].extras" % i)
    for i, m in enumerate(g.get("meshes", [])):
        if "name" in m:
            m["name"] = T.siatka(m["name"], wezly_siatki.get(i, []))
        if "extras" in m:
            m["extras"] = T.extras(m["extras"], "meshes[%d].extras" % i)
    for i, m in enumerate(g.get("materials", [])):
        if "name" in m:
            m["name"] = T.material(m["name"])
        if "extras" in m:
            m["extras"] = T.extras(m["extras"], "materials[%d].extras" % i)
    for im in g.get("images", []):
        if "name" in im:
            im["name"] = T.obraz(im["name"])
    for sek in ("scenes", "textures", "samplers"):
        for i, it in enumerate(g.get(sek, [])):
            if "extras" in it:
                it["extras"] = T.extras(it["extras"], "%s[%d].extras" % (sek, i))
            if "name" in it and (any(c in POLSKIE_ZNAKI for c in it["name"]) or T.polskie_slowa(it["name"])):
                T._brak(sek, it["name"], sek)
    if "extras" in g:
        g["extras"] = T.extras(g["extras"], "extras")
    bledy = ["brak odpowiednika (%s): %r w %s" % b for b in T.braki]
    bledy += ["dwa węzły o nazwie %r: %s" % (e, sorted(p)) for e, p in pary.items() if len(p) > 1]
    if not T.braki:
        bledy += sprawdz(g, T)
    wynik = dict(wejscie=os.path.basename(wej), wyjscie=os.path.basename(wyj),
                 wezly=len(g.get("nodes", [])), siatki=len(g.get("meshes", [])),
                 materialy=len(g.get("materials", [])), obrazy=len(g.get("images", [])),
                 zrodla=T.zrodla, bledy=bledy)
    if not bledy:
        zapisz_glb(wyj, g, chunks)
        g2, ch2 = wczytaj_glb(wyj)
        bin_po = hashlib.sha256(b"".join(c[1] for c in ch2[1:])).hexdigest()
        wynik.update(blok_binarny_bez_zmian=bin_po == bin_przed, bajty=os.path.getsize(wyj))
        if bin_po != bin_przed:
            bledy.append("blok binarny się zmienił")
    if raport:
        with open(raport, "w", encoding="utf-8", newline="\n") as f:
            json.dump(wynik, f, ensure_ascii=False, indent=1)
    return wynik


def main():
    a = sys.argv[1:]
    mapa = os.path.join(ROOT, "data", "names-map.csv")
    raport = None
    if "--mapa" in a:
        i = a.index("--mapa")
        mapa = a[i + 1]
        del a[i:i + 2]
    if "--raport" in a:
        i = a.index("--raport")
        raport = a[i + 1]
        del a[i:i + 2]
    if a and a[0] == "--sprawdz" and len(a) == 2:
        g, _ = wczytaj_glb(a[1])
        T = Tlumacz(mapa)
        bledy = sprawdz(g, T)
        print("SPRAWDZ %s: węzłów %d, siatek %d, materiałów %d, obrazów %d, błędów %d" % (
            os.path.basename(a[1]), len(g.get("nodes", [])), len(g.get("meshes", [])), len(g.get("materials", [])),
            len(g.get("images", [])), len(bledy)))
        for b in bledy[:50]:
            print("  " + b)
        return 1 if bledy else 0
    if len(a) != 2:
        print(__doc__)
        return 2
    w = zamien(a[0], a[1], mapa, raport)
    print("NAZWY %s → %s: węzłów %d, siatek %d, materiałów %d, obrazów %d; źródła: %s; błędów %d" % (
        w["wejscie"], w["wyjscie"], w["wezly"], w["siatki"], w["materialy"], w["obrazy"], w["zrodla"],
        len(w["bledy"])))
    for b in w["bledy"][:80]:
        print("  " + b)
    if len(w["bledy"]) > 80:
        print("  … i %d dalszych" % (len(w["bledy"]) - 80))
    return 1 if w["bledy"] else 0


if __name__ == "__main__":
    sys.exit(main())
