"""Kontrola danych publicznych (czysty Python): zgodność data/ z modelem (liczba lin, stanowisk, części ruchomych,
sumy długości, wymiary główne, drzewca) i brak polskich nazw spoza names-map.csv (klucze i wartości tekstowe
we wszystkich plikach danych i rysunkach SVG). Wynik: słownik + wydruk; kod wyjścia 1 przy błędach.

    python blender/kontrola_publiczna.py [katalog_publiczny] [katalog_modelu]

Domyślnie: katalog główny repozytorium (data/, plans/) i build/ (wyniki budowy). Dodatkowe słowa niedozwolone
w danych (np. nazwy prywatnych katalogów) można podać w pliku tekstowym (jedno na wiersz) wskazanym zmienną
środowiska KONTROLA_ZAKAZANE.
"""
import csv
import json
import math
import os
import re
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))     # katalog główny repozytorium

import nazwy_publiczne as NP  # noqa: E402

# słowa angielskie albo neutralne, które przypadkiem są też fragmentami polskich nazw
NEUTRALNE = {"a", "b", "l", "p", "glb", "snow", "log", "id", "s", "x", "z", "h", "r", "d", "n", "rm", "nrm", "tex",
             "kafel_m", "dno", "stan"} - {"dno", "stan"}
# ścieżki lokalne (litera dysku z dwukropkiem – SCIEZKA_DYSKU) i nazwy plików roboczych generatora; dalsze słowa
# – z pliku wskazanego przez KONTROLA_ZAKAZANE
ZAKAZANE_W_TEKSCIE = ("Users", "/home/", "bryg_poklad", "rysunki_robocze")
SCIEZKA_DYSKU = re.compile(r"\b[A-Za-z]:[\\/]")
if os.environ.get("KONTROLA_ZAKAZANE") and os.path.exists(os.environ["KONTROLA_ZAKAZANE"]):
    with open(os.environ["KONTROLA_ZAKAZANE"], encoding="utf-8") as _f:
        ZAKAZANE_W_TEKSCIE += tuple(w.strip() for w in _f if w.strip() and not w.startswith("#"))


def _csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


def slowa_polskie(nm_rows):
    """Zbiór polskich słów (tokenów) z kolumny polish mapy nazw, bez tokenów, które są też angielskie."""
    pl, en_ = set(), set()
    for r in nm_rows:
        for t in re.split(r"[^0-9A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", r["polish"].lower()):
            if len(t) > 2 and not t.isdigit():
                pl.add(t)
        for t in re.split(r"[^0-9A-Za-z]+", r["english"].lower()):
            en_.add(t)
    return pl - en_ - NEUTRALNE


def teksty(o, sciezka=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield sciezka + "/" + str(k), str(k)
            yield from teksty(v, sciezka + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from teksty(v, sciezka + "[%d]" % i)
    elif isinstance(o, str):
        yield sciezka, o


def sprawdz_tekst(t, pl, gdzie, bledy):
    if any(c in NP.POLSKIE_ZNAKI for c in t):
        bledy.append("polski znak: %s: %r" % (gdzie, t[:80]))
        return
    for z in ZAKAZANE_W_TEKSCIE:
        if z in t:
            bledy.append("niedozwolony tekst %r: %s" % (z, gdzie))
    if SCIEZKA_DYSKU.search(t):
        bledy.append("ścieżka dysku: %s" % gdzie)
    for tok in re.split(r"[^0-9A-Za-z]+", t.lower()):
        if tok in pl:
            bledy.append("polskie słowo %r: %s: %r" % (tok, gdzie, t[:80]))
            return


def kontrola(pub, model_dir):
    data = os.path.join(pub, "data")
    bledy, wyniki = [], {}
    nm = _csv(os.path.join(data, "names-map.csv"))
    pl = slowa_polskie(nm)
    wyniki["names_map_rows"] = len(nm)
    # jedna polska – jedna angielska
    seen = {}
    for r in nm:
        k = (r["category"], r["polish"])
        if k in seen and seen[k] != r["english"]:
            bledy.append("names-map: dwie nazwy dla %s" % (k,))
        seen[k] = r["english"]
    dup = {}
    for r in nm:
        dup.setdefault(r["english"], set()).add(r["polish"])
    wyniki["english_names_shared_by_several_polish"] = sorted(e for e, p in dup.items() if len(p) > 1)[:40]
    # 1. polskie nazwy w plikach danych (bez names-map) i w SVG
    pliki = [f for f in os.listdir(data) if f != "names-map.csv" and f != "SCHEMA.pl.md"]
    for f in pliki:
        p = os.path.join(data, f)
        if f.endswith(".json"):
            for gdzie, t in teksty(json.load(open(p, encoding="utf-8"))):
                sprawdz_tekst(t, pl, f + gdzie, bledy)
        else:
            for i, line in enumerate(open(p, encoding="utf-8")):
                if f.endswith(".md") and line.startswith("|"):
                    pass
                sprawdz_tekst(line, pl, "%s:%d" % (f, i + 1), bledy)
    plans = os.path.join(pub, "plans")
    if os.path.isdir(plans):
        for f in sorted(os.listdir(plans)):
            if f.endswith(".svg"):
                txt = open(os.path.join(plans, f), encoding="utf-8").read()
                for m in re.finditer(r">([^<>]+)<", txt):
                    sprawdz_tekst(m.group(1), pl, "plans/" + f, bledy)
        pld = os.path.join(plans, "pl")
        if os.path.isdir(pld):
            for f in sorted(os.listdir(pld)):
                txt = open(os.path.join(pld, f), encoding="utf-8").read()
                for z in ZAKAZANE_W_TEKSCIE:
                    if z in txt:
                        bledy.append("niedozwolony tekst %r: plans/pl/%s" % (z, f))
                if SCIEZKA_DYSKU.search(txt):
                    bledy.append("ścieżka dysku: plans/pl/%s" % f)
    # 2. zgodność z modelem
    LJ = json.load(open(os.path.join(model_dir, "liny.json"), encoding="utf-8"))
    RJ = json.load(open(os.path.join(data, "rigging-lines.json"), encoding="utf-8"))
    wyniki["lines_model"] = len(LJ)
    wyniki["lines_public"] = len(RJ["lines"])
    if len(LJ) != len(RJ["lines"]):
        bledy.append("liczba lin: model %d, dane %d" % (len(LJ), len(RJ["lines"])))
    sm, sp = sum(l["dlugosc_m"] for l in LJ), sum(l["length_m"] for l in RJ["lines"])
    wyniki["length_model_m"], wyniki["length_public_m"] = round(sm, 2), round(sp, 2)
    if abs(sm - sp) > 0.01 * len(LJ) * 0.001 + 0.5:
        bledy.append("suma długości lin: model %.2f, dane %.2f" % (sm, sp))
    for a, b in zip(LJ, RJ["lines"]):
        if abs(a["srednica_m"] - b["diameter_m"]) > 1e-4 or max(abs(x - y) for x, y in zip(a["od"], b["from"])) > 2e-3:
            bledy.append("lina %d różni się od modelu" % b["id"])
            break
    dyn_m = sum(1 for l in LJ if l["od_obiekt"] or l["do_obiekt"])
    wyniki["dynamic_model"], wyniki["dynamic_public"] = dyn_m, RJ["counts"]["dynamic"]
    if dyn_m != RJ["counts"]["dynamic"]:
        bledy.append("liny dynamiczne: model %d, dane %d" % (dyn_m, RJ["counts"]["dynamic"]))
    P = json.load(open(os.path.join(model_dir, "bryg_poklad.json"), encoding="utf-8"))
    st = _csv(os.path.join(data, "stations.csv"))
    wyniki["stations_model"], wyniki["stations_public"] = len(P["stanowiska"]), len(st)
    if len(st) != len(P["stanowiska"]):
        bledy.append("stanowiska: model %d, dane %d" % (len(P["stanowiska"]), len(st)))
    mp = _csv(os.path.join(data, "moving-parts.csv"))
    # części ruchome modelu: lista z etapu chodzenia (bryg_poklad.json) i węzły GLB z opisem osi ruchu (extras
    # os_ruchu) – pokrywy furt i głowica steru są opisywane dopiero po etapie chodzenia, więc są tylko w GLB
    ruchome = {o["obiekt"] for o in P["obiekty_ruchome"]}
    glb = os.path.join(model_dir, "bryg.glb")
    if os.path.exists(glb):
        import struct
        with open(glb, "rb") as f:
            head = f.read(20)
            gj = json.loads(f.read(struct.unpack("<I", head[12:16])[0]))
        ruchome |= {n.get("name") for n in gj.get("nodes", []) if (n.get("extras") or {}).get("os_ruchu")
                    and not (n.get("name") or "").startswith("lina_")}
    wyniki["moving_model"], wyniki["moving_public"] = len(ruchome), len(mp)
    if len(mp) != len(ruchome):
        bledy.append("części ruchome: model %d, dane %d" % (len(ruchome), len(mp)))
    DL = json.load(open(os.path.join(data, "deck-layout.json"), encoding="utf-8"))
    if len(DL["obstacles"]) != len(P["przeszkody"]):
        bledy.append("przeszkody: model %d, dane %d" % (len(P["przeszkody"]), len(DL["obstacles"])))
    # wymiary główne i drzewca
    K = json.load(open(os.path.join(model_dir, "kontrola.json"), encoding="utf-8"))
    W = K.get("wymiary", {})
    PJ = json.load(open(os.path.join(data, "parameters.json"), encoding="utf-8"))
    sp_rows = {r["spar"]: r for r in _csv(os.path.join(data, "spars.csv"))}
    porown = []

    def por(nazwa, a, b, tol=0.02):
        ok = a is not None and b is not None and abs(float(a) - float(b)) <= tol
        porown.append(dict(item=nazwa, model=a, public=b, ok=ok))
        if not ok:
            bledy.append("wymiar %s: model %s, dane %s" % (nazwa, a, b))
    por("main_topgallant_truck_z", W.get("top_grotbramstengi_m", W.get("top_grotbramstengi")),
        sp_rows["main_topgallant_mast"]["truck_z_m"], 0.02)
    por("fore_topgallant_truck_z", W.get("top_fokbramstengi_m", W.get("top_fokbramstengi")),
        sp_rows["fore_topgallant_mast"]["truck_z_m"], 0.02)
    for k, nmk in (("fok", "fore"), ("grot", "main")):
        por(nmk + "_top_z", K["maszty"][k]["mars_z"], sp_rows[nmk + "_mast"]["top_platform_z_m"])
        por(nmk + "_mast_deck_s", K["maszty"][k]["s_pokladu"], sp_rows[nmk + "_mast"]["deck_s_m"])
        por(nmk + "_mast_d", K["maszty"][k]["sr_przy_pokladzie"], sp_rows[nmk + "_mast"]["d_max_m"], 0.002)
    for k, v in K["reje"].items():
        nm_en = NP.SLOWA["reja_" + k] if k != "gafel" else "gaff"
        por(nm_en + "_length", v["dl"], sp_rows[nm_en]["length_m"])
        por(nm_en + "_diameter", v["sr"], sp_rows[nm_en]["d_max_m"], 0.002)
    G = PJ["groups"]
    por("main_mast_length", 17.8, G["spars"]["values"]["main_mast_length_m"]["value"])
    por("breadth_constructional", W.get("szerokosc_konstrukcyjna_m"), 7.6)
    wyniki["porownania"] = porown
    wyniki["bledy"] = bledy
    return wyniki


def main():
    a = sys.argv[1:]
    pub = os.path.abspath(a[0]) if a else ROOT
    model = os.path.abspath(a[1]) if len(a) > 1 else os.path.join(ROOT, "build")
    w = kontrola(pub, model)
    for k, v in w.items():
        if k not in ("porownania", "bledy"):
            print("%-45s %s" % (k, v))
    print("porównania wymiarów: %d, zgodne %d" % (len(w["porownania"]), sum(p["ok"] for p in w["porownania"])))
    print("BŁĘDY: %d" % len(w["bledy"]))
    for b in w["bledy"][:60]:
        print("  " + b)
    return 1 if w["bledy"] else 0


if __name__ == "__main__":
    sys.exit(main())
