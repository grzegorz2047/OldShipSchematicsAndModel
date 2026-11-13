"""Dane publiczne modelu wzorcowego (czysty Python + numpy): parameters.json, offsets.csv/json, spars.csv,
rigging-lines.json, rigging-summary.csv, deck-layout.json, stations.csv, moving-parts.csv, names-map.csv, SCHEMA.md,
SCHEMA.pl.md – w katalogu data/ repozytorium publicznego.

Źródła: parametry.py (+ stałe modułów w model.json), model.json (model_rysunkowy.py: drzewca, rejestr lin z opisem
wywołań, kołki), wyniki pełnej budowy (bryg_poklad.json, kontrola.json, bryg.glb – extras węzłów).
Wszystkie klucze i teksty po angielsku; polskie nazwy tylko w names-map.csv.

Układ współrzędnych (wszystkie pliki): punkty [x, s, z] w metrach – x w poprzek (+ lewa burta), s wzdłuż
(+ ku dziobowi, s = 0 w środku 28,0 m pokładu między wrębami), z w górę (z = 0 na wodnicy konstrukcyjnej).
"""
import csv
import io
import json
import math
import os
import re
import struct
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import nazwy_publiczne as NP  # noqa: E402
from nazwy_publiczne import SLOWA, LINY, en  # noqa: E402

UKLAD = {
    "axes": "[x, s, z] in metres. x: athwartships, positive to port (larboard), 0 on the centreline. s: fore and aft, "
            "positive forward, s = 0 at the middle of the 28.0 m deck length between rabbets (stem rabbet at the deck "
            "s = +14.0, sternpost s = -14.0). z: up, z = 0 on the design waterline.",
    "handedness": "the triple (s, x, z) is right-handed; written as [x, s, z] in all files",
    "to_gltf": "glTF / game file (+Y up, metres): (X, Y, Z) = (x, z, s), bow towards +Z",
    "to_blender": "Blender (Z up): (X, Y, Z) = (x, -s, z), bow towards -Y",
    "research_stations": "research notes measure stations from the dead flat: s = z_df + 1.96",
}
UKLAD_CSV = ("# coordinates: metres; x athwartships (+ port), s fore and aft (+ forward, 0 at mid deck length), "
             "z up (0 at design waterline)",
             "# glTF (X, Y, Z) = (x, z, s); Blender (X, Y, Z) = (x, -s, z)")

STALE_GRUPY = {"talrepy", "wyblinki", "perty", "wanty_grot", "wanty_fok", "sztagi", "podwantki", "wanty_stengowe",
               "paduny", "wiazanie", "wanty_bramstengowe", "sciagacze"}
REJE = ("fok", "fokmars", "fokbram", "grot", "grotmars", "grotbram", "blinda")


# ------------------------------------------------------------------ pomocnicze
class Rejestr:
    """Zebrane tłumaczenia do names-map.csv: (kategoria, polska, angielska, uwaga)."""

    def __init__(self):
        self.rows = {}
        self.konflikty = []

    def dodaj(self, kat, pl, en_, uwaga=""):
        if pl is None or en_ is None:
            return en_
        k = (kat, pl)
        if k in self.rows and self.rows[k][0] != en_:
            self.konflikty.append((kat, pl, self.rows[k][0], en_))
        self.rows.setdefault(k, (en_, uwaga))
        return en_


R = Rejestr()


def T(pl, kat="object"):
    """Tłumaczenie z wpisem do mapy nazw; brak w słowniku → wyjątek (słownik musi być kompletny)."""
    if pl is None or pl == "":
        return None
    e = en(pl)
    if e is None:
        raise KeyError("brak tłumaczenia: %r (%s)" % (pl, kat))
    return R.dodaj(kat, pl, e)


def strona(side):
    return "L" if side > 0 else "P"


def r3(v, n=3):
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return [r3(x, n) for x in v]
    if isinstance(v, float):
        return round(v, n)
    return v


def ship_from_gltf(p):
    """Punkt bryg_poklad.json [x, y, z] (glTF) → [x, s, z]."""
    return [p[0], p[2], p[1]]


def opis_tekst(t):
    """Stały tekst generatora → angielski (OPISY + wzorce)."""
    if t is None:
        return None
    if t in NP.OPISY:
        return NP.OPISY[t]
    m = re.match(r"^na percie, przy noku (\w+)$", t)
    if m:
        return "on the footrope at the %s yardarm" % T("reja_" + m.group(1)).replace("_", " ")
    m = re.match(r"^wejście na reling i wanty (\w+)$", t)
    if m:
        return "step onto the rail and into the %s shrouds" % T(m.group(1)).replace("_", " ")
    m = re.match(r"^pomost marsa (\w+)$", t)
    if m:
        return "%s top platform" % T(m.group(1)).replace("_", " ")
    m = re.match(r"^ręce na szprychach na wysokości osi; ([\d.]+) obrotu koła = wychylenie steru o 35°$", t)
    if m:
        return "hands on the spokes at axle height; %s turns of the wheel = 35° of rudder" % m.group(1)
    stale = {"faleń: przyciągnąć łódź pod rufę": "painter: haul the boat under the stern",
             "lokalna Z (zawias)": "local Z (hinge)", "reja obraca się wokół osi masztu (lokalna Z)":
                 "the yard turns about the mast axis (local Z)", "lokalna Z": "local Z",
             "lokalna Z (oś bębna), bez ograniczeń": "local Z (drum axis), unlimited", "lokalna Z (pion)":
                 "local Z (vertical)", "dziecko steru (oś steru)": "child of the rudder (rudder axis)",
             "lokalna Z (poprzecznie)": "local Z (athwartships)", "talia kotbelki": "cat tackle",
             "rzut sondy przez reling przy wantach foka": "heave the lead over the rail by the fore shrouds",
             "log z relingu rufowego": "log heaved from the taffrail",
             "obrót wokół lokalnej Z (oś masztu) – brasowanie": "rotation about local Z (mast axis) – bracing"}
    if t in stale:
        return stale[t]
    raise KeyError("brak tłumaczenia opisu: %r" % t)


# ------------------------------------------------------------------ nazwy lin z opisu wywołań
def nazwy_lin(M):
    """Dla każdej liny rejestru: (nazwa_pl, nazwa_en, typ_pl). Zasady z miejsc wywołania lina() w generatorze."""
    out = []
    licz = {}
    ostatnie_dzialo = None
    for L in M["liny"]:
        o = L.get("opis") or [{}]
        f0 = o[0]
        fn, kod, lok = f0.get("fn"), f0.get("kod", ""), f0.get("lok", {})
        f1 = o[1] if len(o) > 1 else {}
        lok1 = f1.get("lok", {})
        typ, ob, st, nr = None, None, None, None
        if fn == "talrep":
            k1 = f1.get("kod", "")
            key, side = lok1.get("key"), lok1.get("side", 1)
            st = strona(side)
            ob = key
            if "D_TALREP_STENG" in k1:
                typ, nr = "talrep_wanty_stengowej", lok1.get("k", 0) + 1
            elif "* 0.8" in k1:
                i = lok1.get("i", 0)
                typ = "talrep_paduna_stengowego" if i < 2 else "talrep_paduna_bramstengowego"
                nr = i + 1 if i < 2 else None
            else:
                typ, nr = "talrep_wanty", lok1.get("i", 0) + 1
        elif fn == "wanty":
            key, side = lok.get("key"), lok.get("side", 1)
            ob, st = key, strona(side)
            if '[a, top_pt]' in kod:
                typ, nr = "wanta", lok.get("i", 0) + 1
            elif "ring, d_sh * 0.8" in kod:
                typ, nr = "strop_jufersa", lok.get("i", 0) + 1
            elif '"wyblinki", [p0, p1]' in kod:
                typ, nr = "wyblinka", "%d_%d" % (lok.get("j", 0) + 1, lok.get("k", 0) + 1)
            elif '"podwantki"' in kod:
                typ, nr = "podwantka", lok.get("k", 0) + 1
            elif '"sciagacze"' in kod:
                typ, st, nr = "sciagacz", None, lok.get("k", 0) + 1
            elif '"wanty_stengowe"' in kod:
                typ, nr = "wanta_stengowa", lok.get("k", 0) + 1
            elif '"wyblinki", [pa, pb]' in kod:
                kk = ("wyblinka_stengowa", key, st)
                licz[kk] = licz.get(kk, 0) + 1
                typ, nr = "wyblinka_stengowa", licz[kk]
            elif '"wanty_bramstengowe"' in kod:
                typ, nr = "wanta_bramstengowa", lok.get("k", 0) + 1
            elif '"paduny"' in kod:
                i = lok.get("i", 0)
                typ, nr = ("padun_stengowy", i + 1) if i < 2 else ("padun_bramstengowy", None)
            elif "ring, d_sh)" in kod:
                typ, st, nr = "petla_want", None, lok.get("k", 0) + 1
        elif fn == "sztagi":
            for frag, t_ in (("D_GROTSZTAG", "grotsztag"), ("ring, 0.05", "obroza_grotsztagu"),
                             ("[b + Vector((0, -0.08", "taliowka_grotsztagu"), ("D_FOKSZTAG", "foksztag"),
                             ("st_g.p(", "sztag_grotstengi"), ("st_f.p(st_f.z_head + 0.1", "sztag_fokstengi"),
                             ("br_g.p(", "sztag_grotbramstengi"), ("br_f.p(", "sztag_fokbramstengi"),
                             ("D_SZTAG_KLIWRA", "sztag_kliwra"), ("D_WATERSZTAG", "watersztag"),
                             ("D_WANTY_BUKSZ", "wanta_bukszprytu"), ("wiazanie", "wiazanie_bukszprytu")):
                if frag in kod:
                    typ = t_
                    break
            if typ in ("watersztag", "wiazanie_bukszprytu"):
                nr = lok.get("k", 0) + 1
            if typ == "wanta_bukszprytu":
                nr, st = lok.get("k", 0) + 1, strona(lok.get("side", 1))
        elif fn == "reje_liny":
            if '"perty", pts' in kod:
                typ, ob, st = "perta", lok.get("nam"), strona(lok.get("side", 1))
            elif "[top, best]" in kod:
                typ, ob, st, nr = "strzemie", lok.get("nam"), strona(lok.get("side", 1)), lok.get("k", 0) + 1
            elif "m.p(m.z_top + 0.05" in kod:
                typ, ob = "strop_rei", lok.get("key")
            else:
                typ, ob = "tie_marsrei", lok.get("key")
        elif fn == "dziala":
            ostatnie_dzialo = L.get("do")
            ob = L.get("do")
            if "0.045" in kod:
                typ = "lina_hamujaca"
            else:
                typ = "talia_dziala"
            kk = (typ, ob)
            licz[kk] = licz.get(kk, 0) + 1
            nr = licz[kk] if typ == "lina_hamujaca" else (licz[kk] + 1) // 2
            nr = {1: "rufowa", 2: "dziobowa"}.get(nr, nr)
        elif fn == "zwoj" and f1.get("fn") == "dziala":
            typ, ob = "buchta_talii", ostatnie_dzialo
        elif fn == "buchta" and f1.get("fn") == "belay":
            typ, ob = "buchta", lok1.get("nazwa")
        elif fn == "belay":
            nz = lok.get("nazwa")
            typ, ob = "_belay", nz
        elif fn == "kabestan":
            typ = "lina_kabestanu"
        elif fn == "kolo_sterowe":
            typ, st = "sterlina", strona(lok.get("sg", 1))
        elif fn == "rumpel_pokladowy":
            typ, st = "talia_rumpla", strona(lok.get("sg", 1))
        elif fn == "dzwon":
            typ = "linka_dzwonu"
        elif fn == "lodz":
            typ = "fangalina_lodzi"
        elif fn == "kotwice":
            k_ = licz.get("kotwice", 0)
            licz["kotwice"] = k_ + 1
            typ, st = (("talia_kotbelki", "L"), ("lina_kotwiczna", "L"), ("lina_kotwiczna_poklad", "P"))[min(k_, 2)]
        elif fn == "zbuduj" and f0.get("mod") == "ruchome":
            nm, side = lok.get("nm"), lok.get("side", 1)
            st = strona(side)
            ob = nm
            if "[arm, bl]" in kod:
                typ = "topenanta"
            elif "[arm, pend]" in kod:
                typ = "wisior_brasu"
            elif "[pend, via]" in kod or "[pend, rb]" in kod:
                typ = "bras"
            elif "side * 1.45" in kod or "rog_szot" in kod:
                typ = "szot"
            elif "[b0, c" in kod:
                typ, st = "gording", strona(lok.get("gx", 1.0))
            elif "side * h * 0.88" in kod or "[p1, p2]" in kod:
                typ = "szot"
            elif "[a + Vector((off" in kod:
                typ, st = "fal_marsrei", None
            elif "[thr, cb" in kod:
                typ, ob, st = "gardafal", None, None
            elif "[pk, cb" in kod:
                typ, ob, st = "pikfal", None, None
            elif "[peak, corner]" in kod:
                typ, ob = "gaj", None
            elif "[arm, capp" in kod:
                typ, ob = "topenanta", "blinda"
            elif "[arm, rb" in kod:
                typ, ob = "bras", "blinda"
            elif "gm.p(gm.z_top + 0.1" in kod:
                typ, ob = "topenanta_bomu", None
            elif "[b1 + Vector((off" in kod:
                typ, ob, st = "szot_bomu", None, None
            elif "gejtawa_gafla" in kod or "brail" in kod:
                # gejtawy żagla gaflowego (ruchome.py): odnoga wokół wałka płótna i część robocza do bloku na maszcie
                typ = "gejtawa_gafla_odnoga" if "odnoga" in kod else "gejtawa_gafla"
                ob, nr = None, lok.get("i", 0) + 1
        if typ is None:
            typ = "lina_" + L["g"]
        out.append(_zloz(typ, ob, st, nr))
    return out


def _zloz(typ, ob, st, nr):
    """(typ, obiekt, burta, numer) → (nazwa_pl, nazwa_en, typ)."""
    if typ == "_belay":
        pl = ob
        return pl, _en_belay(pl), pl.split("_")[0]
    if typ == "buchta":
        en_ = "coil_" + _en_belay(ob)
        return "buchta_" + ob, en_, "buchta"
    czesci = [typ] + [str(c) for c in (ob, st, nr) if c is not None]
    pl = "_".join(czesci)
    S = NP.STRONA.get(st) if st else None
    nn = None if nr is None else {"rufowa": "aft", "dziobowa": "fore"}.get(str(nr), str(nr))
    base = typ
    if typ.startswith("talrep_"):
        what = {"talrep_wanty": "shroud", "talrep_wanty_stengowej": "topmast_shroud",
                "talrep_paduna_stengowego": "topmast_backstay", "talrep_paduna_bramstengowego": "topgallant_backstay"}[typ]
        e = "%s_%s_lanyard" % (SLOWA[ob], what)
    elif typ in ("topenanta", "wisior_brasu", "bras", "szot", "gording", "perta", "strzemie"):
        word = LINY[typ]
        if typ == "szot" and ob in ("fokmars", "grotmars"):
            word = "sheet"
        e = "%s_%s" % (SLOWA["reja_" + ob], word)
    elif typ == "gejtawa":
        e = "%s_%s" % (SLOWA["reja_" + ob], "clew_garnet" if ob in ("fok", "grot") else "clewline")
    elif typ == "fal_marsrei":
        e = "%s_topsail_halliard" % SLOWA[ob[:-4]]
    elif typ in ("strop_rei", "tie_marsrei"):
        e = "%s_%s" % (SLOWA[ob], LINY[typ])
    elif typ in ("lina_hamujaca", "talia_dziala", "buchta_talii"):
        e = "%s_%s" % (T(ob), LINY[typ])
    elif ob in ("fok", "grot"):
        e = "%s_%s" % (SLOWA[ob], LINY.get(base, base))
    elif ob is None:
        e = LINY.get(base) or SLOWA.get(base) or base
    else:
        e = "%s_%s" % (T(ob), LINY.get(base, base))
    if S:
        e += "_" + S
    if nn:
        e += "_" + nn
    return pl, e, typ


def _en_belay(nz):
    """Nazwa liny z belay() w ruchome.py (np. topenanta_fokmars_L, gardafal, gaj_L, fal_fokmars)."""
    cz = nz.split("_")
    typ = cz[0]
    if typ in ("gardafal", "pikfal"):
        return LINY[typ]
    if nz.startswith("gejtawa_gafla_"):                 # gejtawa_gafla_<nr>_<burta> → brail_<side>_<nr>
        return "%s_%s_%s" % (LINY["gejtawa_gafla"], NP.STRONA[cz[3]], cz[2])
    if typ == "gaj":
        return "vang_" + NP.STRONA[cz[1]]
    if typ == "fal":
        return SLOWA[cz[1][:-4]] + "_topsail_halliard"
    nm, st = cz[1], cz[2] if len(cz) > 2 else None
    pl, e, _ = _zloz(typ, nm, st, None)
    return e


# ------------------------------------------------------------------ parametry
def _jednostka(k):
    for suf, u in (("_m3", "m3"), ("_m", "m"), ("_deg", "deg"), ("_per_m", "1"), ("_ratio", "1"), ("_ratios", "1"),
                   ("_count", "1")):
        if k.endswith(suf):
            return u
    return None


def _wartosc(v):
    if isinstance(v, dict):
        def klucz(k):
            if k in NP.PODKLUCZE:
                return R.dodaj("parameter_subkey", k, NP.PODKLUCZE[k])
            if k in NP.KLUCZE:
                return R.dodaj("json_key", k, NP.KLUCZE[k])
            return T(k, "key")
        return {klucz(k): _wartosc(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_wartosc(x) for x in v]
    if isinstance(v, str):
        e = NP.en_wart(v)
        if e != v or v in ("a", "b"):
            R.dodaj("value", v, e)
        return e
    if isinstance(v, float):
        return round(v, 6)
    return v


def wpis(pl_key, v):
    if pl_key not in NP.PARAM:
        raise KeyError("brak opisu parametru %s" % pl_key)
    k, conf, ch, note = NP.PARAM[pl_key]
    R.dodaj("parameter", pl_key, k)
    d = dict(value=_wartosc(v), confidence=conf, source=ch)
    u = _jednostka(k)
    if u:
        d["unit"] = u
    if note:
        d["note"] = note
    return k, d


def parameters(S, M, nazwy):
    PR = S.PR
    K, D, O, U = PR.KADLUB, PR.DRZEWCA, PR.OLINOWANIE, PR.UKLAD
    st = M.get("stale", {})

    def grupa(opis, zrodla, pary):
        vals = {}
        for pl_key, v in pary:
            k, d = wpis(pl_key, v)
            vals[k] = d
        return dict(description=opis, sources=zrodla, values=vals)
    G = {}
    G["hull"] = grupa("Profile, keel, stem, sternpost and planking of the hull. Hull surface: offsets.json.",
                      [NP.C02, NP.C03],
                      [(k, K[k]) for k in ("ZK0", "ZK_SPADEK", "STEPKA_WYS", "STEPKA_SZER", "DZIOBNICA_SZER",
                                           "DZIOBNICA_GR", "TYLNICA_GR", "POSZYCIE_GR", "DZIOB", "TUCK_S0",
                                           "TUCK_RAKE", "RUFA_SZER", "PILERS_ROZSTAW", "BERGHOLTY",
                                           "LINIA_WODNA_FARBA")] + [("LINIE_PRZESUNIECIE", PR.LINIE_PRZESUNIECIE)])
    G["hull"]["values"]["offsets_file"] = dict(value="offsets.json", confidence=NP.REF, source=NP.C02,
                                               note="research table (moulded) and generator table (outside planking)")
    cz = st.get("chodzenie", {})
    G["decks"] = grupa("Deck lines, camber, bulwarks, rail, ports, hatches, companion; walking test figure.", [NP.C04],
                       [(k, K[k]) for k in ("POKLAD_BOK", "WYPUKLOSC", "POL_B", "POKLAD_GR", "RELING", "POLPOKLAD_S",
                                            "POLPOKLAD_H", "NADBURCIE_GR", "RELING_SZER", "RELING_GR", "PILERS",
                                            "WODOSCIEK", "LISTWA_FURT", "FURTY_S", "FURTY_ZAMKNIETE_S", "FURTA_SZER",
                                            "FURTA_PROG", "FURTA_NADPROZE", "POKRYWA_KAT")] +
                       [(k, U[k]) for k in ("LUK_GLOWNY", "LUK_DZIOBOWY", "ZEJSCIOWKA")] +
                       [(k, v) for k, v in cz.items()])
    gal = st.get("rufa_dziob", {}).get("GALION", {})
    kad = st.get("kadlub", {})
    G["stern_and_head"] = grupa("Transom, counter, rudder clearances and irons, head, catheads, hawse holes.", [NP.C04],
                                [(k, K[k]) for k in ("Z_PAWEZ_DOLNA", "RUFA", "RUFA_WYGIECIE", "Z_NAWIS",
                                                     "STER_LUZ_TYLNICA", "STER_LUZ_KONTRA", "STER_OTWOR_LUZ")] +
                                [(k, v) for k, v in gal.items()] + [(k, v) for k, v in kad.items()])
    G["spars"] = grupa("Masts, yards, bowsprit, gaff and boom: lengths and diameters from Steel's rules, positions, "
                       "taper, tops. Computed positions: spars.csv.", [NP.C05],
                       [(k, D[k]) for k in D] + [("CAL_NA_JARD", PR.CAL_NA_JARD)])
    G["standing_rigging"] = grupa("Numbers and diameters of the standing rigging, deadeyes, ratlines, channels.",
                                  [NP.C06], [(k, O[k]) for k in O])
    # olinowanie ruchome: średnice zapisane w kodzie (ruchome.py) – zebrane z rejestru lin
    typy = {}
    for L, (pl, e, typ) in zip(M["liny"], nazwy):
        if L["g"] != "ruchome":
            continue
        t_en = re.sub(r"_(port|starboard)$", "", e)
        rec = typy.setdefault(t_en, dict(diameter_m=L["d"], material="tarred" if L["m"] == "lina_smolowana" else
                                         "untarred", segments=0))
        rec["segments"] += 1
    G["running_rigging"] = dict(
        description="Running rigging with sails furled. Diameters are set in the generator code (running rigging "
                    "module), collected here per rope from rigging-lines.json; belaying points below.",
        sources=[NP.C07, NP.C08],
        values={k: dict(value=v, confidence=NP.REF, source=NP.C07) for k, v in sorted(typy.items())})
    for k in ("NAGIELBANK", "KOLKOWNICE", "KOLKOWNICA_H"):
        kk, d = wpis(k, U[k])
        G["running_rigging"]["values"][kk] = d
    zag = S.zagle()
    G["sails"] = dict(description="Furled sails in the model (roll radii); set sails estimated from the spars for the "
                                  "sail plan (chapter 08, sections 'Worked example: sails of the reference model' "
                                  "and 'Furled sails in the reference model').", sources=[NP.C08], values={})
    for k, v in st.get("zagle", {}).items():
        kk, conf, ch, note = NP.PARAM[k]
        R.dodaj("parameter", k, kk)
        G["sails"]["values"][kk] = dict(value={("course" if a == "" else {"mars": "topsail", "bram": "topgallant",
                                                                         "blinda": "spritsail"}[a]): b
                                               for a, b in v.items()}, unit="m", confidence=conf, source=ch, note=note)
    kk, d = wpis("zagle_postawione", PR.BRYG["zagle_postawione"])
    G["sails"]["values"][kk] = d
    G["sails"]["values"]["set_sail_estimates"] = dict(
        value={T(_zagiel_pl(n), "sail"): {k2: r3(v2, 2) for k2, v2 in (("head_m", z.get("glowica")),
                                                                       ("foot_m", z.get("stopa")),
                                                                       ("depth_m", z.get("wysokosc")),
                                                                       ("area_m2", z["pole"])) if v2 is not None}
               for n, z in zag.items()},
        confidence=NP.INF, source=NP.C08, note="head 0.9 × yard, foot = head of the sail below (course 0.95 × yard), "
                                               "yards hoisted to the working position, courses down to the rail")
    G["fittings"] = grupa("Deck fittings and guns: positions and sizes.", [NP.C09],
                          [(k, U[k]) for k in ("KABESTAN", "POMPY", "LODZ", "KOMIN", "SZAFKA_KOMPASOWA", "DZWON",
                                               "KOJCE", "SKRZYNIA_BRONI", "BECZKA_WODY", "DZIALA", "DZIALKA_RELINGOWE")])
    G["steering"] = grupa("Two steering variants in one model: wheel (default) and deck tiller.", [NP.C09],
                          [(k, U[k]) for k in ("STEROWANIE", "RUMPEL", "KOLO")])
    kolo = U["KOLO"]
    n = kolo["rumpel_dl"] * math.sin(math.radians(kolo["kat"])) / (math.pi * kolo["D_beben"])
    G["steering"]["values"]["wheel_turns_for_35deg"] = dict(
        value=round(n, 3), confidence=NP.REF, source=NP.C09,
        note="n = tiller_length · sin(35°) / (π · drum_diameter)")
    G["materials"] = dict(description="Paint schemes (region → material) and material settings.", sources=[NP.C04],
                          values={"schemes": dict(value={s_: {T(r_, "paint_region"): T(m_, "material")
                                                              for r_, m_ in v_.items()}
                                                         for s_, v_ in PR.SCHEMATY.items()},
                                                  confidence=NP.SEC, source=NP.C04,
                                                  note="scheme a: period proposal; scheme b: black hull"),
                                  "materials": dict(value=_wartosc(PR.MATERIALY), confidence=NP.REF, source=NP.C04),
                                  "materials_cc0": dict(value=_wartosc(PR.MATERIALY_CC0), confidence=NP.REF,
                                                        source=NP.C04, note="Poly Haven CC0 texture ids")})
    for pl_ in list(PR.SCHEMATY["a"].keys()) + list(PR.MATERIALY.keys()):
        T(pl_, "material")
    kk, d = wpis("WNETRZE_CZERWONE", PR.WNETRZE_CZERWONE)
    G["materials"]["values"][kk] = d
    G["variants"] = grupa("Switches between design variants.", [NP.C01, NP.C04, NP.C07, NP.C09],
                          [("nazwa", PR.BRYG["nazwa"]), ("snow", PR.BRYG["snow"]), ("schemat", PR.BRYG["schemat"]),
                           ("Z_BOMEM", D["Z_BOMEM"])])
    G["variants"]["values"]["steering_drive"] = dict(value=NP.en_wart(U["STEROWANIE"]["naped"]), confidence=NP.REF,
                                                     source=NP.C09)
    G["variants"]["values"]["boat_state"] = dict(value=NP.en_wart(U["LODZ"]["stan"]), confidence=NP.INF, source=NP.C09)
    G["variants"]["values"]["gun_mesh"] = dict(value=NP.en_wart(U["DZIALA"]["wariant"]), confidence=NP.REF,
                                               source=NP.C09)
    return dict(title="Parameters of the reference model (snow, about 1710)", coordinate_system=UKLAD,
                confidence_levels={"period": "from a period source", "secondary": "from secondary literature",
                                   "our inference": "reasoned value, not read from a source",
                                   "reference model": "a choice of the reference model"},
                groups=G)


def _zagiel_pl(n):
    return {"gaflowy": "zagiel_gaflowy"}.get(n, "zagiel_" + n)


# ------------------------------------------------------------------ rzędne
def offsets(S):
    PR = S.PR
    rows = []
    J = dict(coordinate_system=UKLAD, research_table=[], generator_table={}, buttocks=[], stem={}, sternpost={},
             transom={}, deck_and_rail={})
    wl = [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5]
    for (zd, keel, rab, beard, ys, deck, dhb, b, hb, rail, top) in PR.LINIE_WREGI:
        s = round(zd + PR.LINIE_PRZESUNIECIE, 3)
        st = dict(station_s_m=s, station_z_df_m=zd, keel_underside_z_m=keel, rabbet_z_m=rab, bearding_z_m=beard,
                  waterlines={("%+.1f" % w): y for w, y in zip(wl, ys)}, deck_at_side_z_m=deck,
                  deck_half_breadth_m=dhb, greatest_half_breadth_m=b, greatest_half_breadth_z_m=hb,
                  rail_z_m=rail, rail_half_breadth_m=top)
        J["research_table"].append(st)
        for nm, z in (("keel_underside", keel), ("rabbet", rab), ("bearding", beard)):
            rows.append(("research_moulded", s, zd, nm, "", "", z))
        for w, y in zip(wl, ys):
            rows.append(("research_moulded", s, zd, "waterline", w, y, w))
        rows.append(("research_moulded", s, zd, "deck_at_side", "", dhb, deck))
        rows.append(("research_moulded", s, zd, "greatest_breadth", "", b, hb))
        rows.append(("research_moulded", s, zd, "rail_waist", "", top, rail))
    J["generator_table"] = dict(note="half-breadths outside the planking on lines parallel to the keel rabbet; "
                                     "height h above the rabbet: z = keel_rabbet_z(s) + h; null = outside the hull",
                                heights_above_rabbet_m=PR.RZEDNE_H, stations_s_m=PR.RZEDNE_S,
                                half_breadths_m=PR.RZEDNE,
                                keel_rabbet_z_m=dict(at_s0=S.K["ZK0"], per_m=S.K["ZK_SPADEK"]))
    for j, h in enumerate(PR.RZEDNE_H):
        for i, s in enumerate(PR.RZEDNE_S):
            v = PR.RZEDNE[j][i]
            if v is not None:
                rows.append(("generator_outside_planking", s, round(s - PR.LINIE_PRZESUNIECIE, 3),
                             "height_above_rabbet", h, v, round(S.zk(s) + h, 4)))
    for x in (1.0, 2.0, 3.0):
        for s in PR.RZEDNE_S:
            pts = S.wzdluzny_stacja(s, x) if hasattr(S, "wzdluzny_stacja") else None
            z = _buttock_at(S, s, x)
            J["buttocks"].append(dict(x_m=x, station_s_m=s, z_m=r3(z, 3)))
            rows.append(("buttock_generator", s, round(s - PR.LINIE_PRZESUNIECIE, 3), "buttock", x, x,
                         "" if z is None else round(z, 3)))
    K = S.K
    J["stem"] = dict(rabbet_s_z_m=K["DZIOB"], sided_bottom_top_m=K["DZIOBNICA_SZER"], moulded_m=K["DZIOBNICA_GR"])
    for s, z in K["DZIOB"]:
        rows.append(("stem_rabbet", s, "", "point", "", "", z))
    tl = S.tylnica()
    J["sternpost"] = dict(rabbet_heel_s_m=K["TUCK_S0"], rake_deg_from_vertical=K["TUCK_RAKE"],
                          face_s_z_m=[[round(a, 3), round(b, 3)] for a, b in tl], moulded_heel_head_m=K["TYLNICA_GR"],
                          sided_m=K["STEPKA_SZER"])
    for s, z in tl:
        rows.append(("sternpost_rabbet", round(s, 3), "", "point", "", "", round(z, 3)))
    J["transom"] = dict(wing_transom_z_m=K["Z_PAWEZ_DOLNA"], counter_top_z_m=K["Z_NAWIS"],
                        centreline_above_wing_s_z_m=K["RUFA"], half_breadth_z_y_m=K["RUFA_SZER"],
                        round_up_m=K["RUFA_WYGIECIE"])
    for s, z in K["RUFA"]:
        rows.append(("transom_centreline", s, "", "point", "", "", z))
    for z, y in K["RUFA_SZER"]:
        rows.append(("transom_half_breadth", "", "", "point", "", y, z))
    J["deck_and_rail"] = dict(deck_at_side_s_z_m=K["POKLAD_BOK"], camber_m=K["WYPUKLOSC"],
                              rail_above_deck_s_m=K["RELING"], quarterdeck_break_s_m=K["POLPOKLAD_S"],
                              quarterdeck_height_m=K["POLPOKLAD_H"])
    for s, z in K["POKLAD_BOK"]:
        rows.append(("deck_at_side", s, "", "point", "", round(float(S.H(s, z)[0]), 3), z))
    for s in np.arange(-15.0, 14.61, 0.5):
        rows.append(("rail_top", round(float(s), 2), "", "point", "", "", round(S.rail(float(s)), 3)))
    return rows, J


def _buttock_at(S, s, x):
    z0 = S.zk(s)
    zs = np.linspace(z0, S.deck_side(s), 240)
    ys = S.H(np.full_like(zs, s), zs)
    a = np.array([S.kd.a_of_z(z) for z in zs])
    f = np.array([S.stem_s(z) for z in zs])
    ys = np.where((s >= a) & (s <= f), ys, 0.0)
    idx = np.where((ys[:-1] < x) & (ys[1:] >= x))[0]
    if not len(idx):
        return None
    i = idx[0]
    t = (x - ys[i]) / (ys[i + 1] - ys[i])
    return float(zs[i] + t * (zs[i + 1] - zs[i]))


# ------------------------------------------------------------------ drzewca
def spars(S):
    M, D = S.M, S.D
    rows = []
    T_M, T_S, T_R = D["TAPER_MASZT"], D["TAPER_STENGA"], D["TAPER_REJA"]
    for mk in ("fok", "grot"):
        o = M["maszty"][mk]["osie"]
        top = M["maszty"][mk]["top"]
        rake = math.degrees(math.atan(o["tan_rake"]))
        nm = SLOWA[mk]
        cap_T = M["maszty"][mk]["cap_T"]
        st, br = o["st"], o["br"]
        rows.append(dict(spar=nm + "_mast", kind="lower_mast", length_m=D["GROT" if mk == "grot" else "FOK"],
                         d_max_m=o["sr"], d_mid_m=o["sr"] * T_M[2], d_end_m=o["sr"] * T_M[5],
                         start=[0, S.ms(mk, o["z_heel"]), o["z_heel"]], end=[0, S.ms(mk, o["z_cap"]), o["z_cap"]],
                         angle_deg=rake, angle_ref="rake aft from vertical", deck_s_m=o["s_d"], deck_z_m=o["z_d"],
                         top_platform_z_m=top["z"], cap_z_m=o["z_cap"], masthead_from_z_m=o["z_top"],
                         note="d_max at the partners, d_end at the top of the head"))
        rows.append(dict(spar=nm + "_topmast", kind="topmast", length_m=D[("GROT" if mk == "grot" else "FOK") + "_STENGA"],
                         d_max_m=st["sr"], d_mid_m=st["sr"] * T_S[2], d_end_m=st["sr"] * T_S[5],
                         start=[0, S.ms(mk, st["z_heel"], "st"), st["z_heel"]],
                         end=[0, S.ms(mk, st["z_top"], "st"), st["z_top"]], angle_deg=rake,
                         angle_ref="rake aft from vertical", crosstrees_z_m=st["z_head"],
                         cap_z_m=st["z_top"], masthead_from_z_m=st["z_head"],
                         note="stands forward of the lower masthead, heel above the trestle trees"))
        rows.append(dict(spar=nm + "_topgallant_mast", kind="topgallant_mast",
                         length_m=D[("GROT" if mk == "grot" else "FOK") + "_BRAM"] + 1.0,
                         d_max_m=br["sr"], d_mid_m=br["sr"] * 0.775, d_end_m=br["sr"] * 0.55,
                         start=[0, S.ms(mk, br["z_heel"], "br"), br["z_heel"]],
                         end=[0, S.ms(mk, br["z_top"], "br"), br["z_top"]], angle_deg=rake,
                         angle_ref="rake aft from vertical", truck_z_m=br["z_top"],
                         note="rule length + 1.0 m pole"))
    sn = M.get("snow")
    if sn:
        rows.append(dict(spar="snow_mast", kind="snow_mast", length_m=sn["z1"] - sn["z0"] + 0.1,
                         d_max_m=2 * sn["r"], d_mid_m=2 * sn["r"] * 0.925, d_end_m=2 * sn["r"] * 0.85,
                         start=[0, sn["s"], sn["z0"] - 0.1], end=[0, sn["s"] - (sn["z1"] - sn["z0"]) * sn["t"], sn["z1"]],
                         angle_deg=math.degrees(math.atan(sn["t"])), angle_ref="rake aft from vertical",
                         note="from the deck to the underside of the main trestle trees"))
    bs = M["bukszpryt"]
    rows.append(dict(spar="bowsprit", kind="bowsprit", length_m=bs["L"], d_max_m=2 * bs["r0"], d_mid_m=2 * bs["r0"] *
                     (1 - 0.38 * (0.5 - 0.35) / 0.65), d_end_m=2 * bs["r0"] * 0.62,
                     start=[0, bs["heel"][0], bs["heel"][1]], end=[0, bs["end"][0], bs["end"][1]],
                     angle_deg=D["BUKSZPRYT_WZNIOS"], angle_ref="steeve above horizontal",
                     note="full diameter to 0.35 of the length, then tapers"))
    j0, j1 = bs["j0"], bs["j1"]
    rows.append(dict(spar="jib_boom", kind="jib_boom", length_m=D["BOMSTENGA"], d_max_m=D["BOMSTENGA_SR"],
                     d_mid_m=D["BOMSTENGA_SR"] * 0.8, d_end_m=D["BOMSTENGA_SR"] * 0.6, start=j0, end=j1,
                     angle_deg=D["BUKSZPRYT_WZNIOS"], angle_ref="steeve above horizontal",
                     note="heel at 0.62 of the bowsprit length"))
    for nm in REJE:
        Y = M["reje"][nm]
        c = Y["c"]
        L = Y["L"]
        rows.append(dict(spar=SLOWA["reja_" + nm], kind="yard", length_m=L, d_max_m=Y["sr"], d_mid_m=Y["sr"] * T_R[2],
                         d_end_m=Y["sr"] * T_R[4], start=[L / 2, c[1], c[2]], end=[-L / 2, c[1], c[2]],
                         angle_deg=0.0, angle_ref="square (not braced)", lowered_z_m=c[2],
                         hoisted_z_m=c[2] + Y.get("dz_robocza", 0.0), working_height_dz_m=Y.get("dz_robocza", 0.0),
                         note="start = port yardarm; d_mid at 1/2 of the half-length"))
    g = M["reje"]["gafel"]
    rows.append(dict(spar="gaff", kind="gaff", length_m=g["L"], d_max_m=g["sr"], d_mid_m=g["sr"] * 0.88,
                     d_end_m=g["sr"] * 0.65, start=g["c"], end=g["end"], angle_deg=D["GAFEL_KAT"],
                     angle_ref="above horizontal", note="jaws on the snow mast"))
    if "bom" in M["reje"]:
        b = M["reje"]["bom"]
        rows.append(dict(spar="boom", kind="boom", length_m=b["L"], d_max_m=b["sr"], start=b["c"], end=b["end"],
                         angle_deg=2.5, angle_ref="above horizontal"))
    for k, e_ in NP.SPAR_PL.items():
        R.dodaj("spar", k, e_)
    for nm in REJE:
        T("reja_" + nm, "spar")
    return rows


# ------------------------------------------------------------------ liny
def rigging(S, nazwy):
    M = S.M
    # kołki: nagielbanki, kołkownice, knagi (z dziennika belay)
    piny = []
    for key, pins in (M.get("kolki_nagielbankow") or {}).items():
        for p in pins:
            piny.append(dict(pool="nagielbank_" + key, p=p))
    for p in M.get("kolki_kolkownic") or []:
        piny.append(dict(pool="kolkownica_%s_%s" % ("L" if p[0] > 0 else "P", "fok" if p[1] > 3 else "grot"), p=p))
    for b in M.get("belay") or []:
        if b["pool"] == "knagi_rufowe" and not any(abs(q["p"][0] - b["p"][0]) < 1e-3 and abs(q["p"][1] - b["p"][1])
                                                   < 1e-3 for q in piny):
            piny.append(dict(pool="knagi_rufowe", p=b["p"]))
    kody = {"nagielbank_fok": "FF", "nagielbank_grot": "MF", "kolkownica_L_fok": "PF", "kolkownica_P_fok": "SF",
            "kolkownica_L_grot": "PM", "kolkownica_P_grot": "SM", "knagi_rufowe": "K"}
    pin_out = []
    for pool in kody:
        lst = sorted([q for q in piny if q["pool"] == pool], key=lambda q: (-q["p"][1], -q["p"][0]))
        for i, q in enumerate(lst):
            q["id"] = "%s%02d" % (kody[pool], i + 1)
            pool_en = {"knagi_rufowe": "quarterdeck_kevels"}.get(pool) or T(pool, "belaying_point")
            if pool == "knagi_rufowe":
                T(pool, "belaying_point")
            pin_out.append(dict(id=q["id"], kind=pool_en, position=r3(list(q["p"]), 3), ropes=[]))
    def pin_dla(p):
        best, bd = None, 1e9
        for q in piny:
            d = (q["p"][0] - p[0]) ** 2 + (q["p"][1] - p[1]) ** 2 + (q["p"][2] + 0.1 - p[2]) ** 2
            if d < bd:
                best, bd = q, d
        return best["id"] if best and bd < 0.02 else None
    lines = []
    rope_seg = {}
    for i, (L, (pl, e, typ)) in enumerate(zip(M["liny"], nazwy)):
        R.dodaj("rope", pl, e)
        rope_seg.setdefault(e, []).append(i)
    pin_rope = {}
    for b in M.get("belay") or []:
        pin_rope[b["lina"]] = b["p"]
    # przebieg i części ruchome końców z liny.json pełnej budowy (końce dociągnięte do części – olinowanie.
    # zamocuj_konce – i klasyfikacja lin dynamicznych po nim); model w pamięci (do żagli) ma tę samą kolejność rejestru
    LJ0 = S.plik("liny.json") or []
    pelne = len(LJ0) == len(M["liny"]) and all(lj.get("przez") is not None for lj in LJ0)
    for i, (L, (pl, e, typ)) in enumerate(zip(M["liny"], nazwy)):
        if pelne:
            lj = LJ0[i]
            L = dict(L, p=[lj["od"]] + lj["przez"] + [lj["do"]], od=lj.get("od_obiekt"), do=lj.get("do_obiekt"))
        p = L["p"]
        length = sum(math.dist(p[k], p[k + 1]) for k in range(len(p) - 1))
        segs = rope_seg[e]
        kind = "standing" if (L["g"] in STALE_GRUPY or typ in ("strop_rei", "petla_want", "obroza_grotsztagu",
                                                              "taliowka_grotsztagu")) else "running"
        if L["g"] == "buchty":
            kind = "coil"
        bel = None
        if typ != "buchta" and pl in pin_rope and segs[-1] == i:
            bel = pin_dla(pin_rope[pl])
        rec = dict(id=i, rope=e, segment=segs.index(i) + 1, segments=len(segs), group=T(L["g"], "rope_group"),
                   kind=kind, material="tarred" if L["m"] == "lina_smolowana" else "untarred",
                   diameter_m=round(L["d"], 4), length_m=round(length, 3), **{"from": r3(p[0]), "to": r3(p[-1])},
                   via=[r3(q) for q in p[1:-1]], parent=T(L["rodzic"]) if L["rodzic"] else None,
                   from_object=T(L["od"]) if L["od"] else None, to_object=T(L["do"]) if L["do"] else None,
                   dynamic=bool(L["od"] or L["do"]), variant=T(L["wariant"]) if L["wariant"] else None,
                   belayed_to=bel, one_sided=bool(L.get("jednostronna")))
        lines.append(rec)
        if bel:
            for q in pin_out:
                if q["id"] == bel and e not in q["ropes"]:
                    q["ropes"].append(e)
    # końce w układzie lokalnym części ruchomych – z liny.json pełnej budowy (ta sama kolejność rejestru)
    LJ = S.plik("liny.json") or []
    if len(LJ) == len(lines):
        for rec, lj in zip(lines, LJ):
            rec["from_local"] = lj.get("od_lokalnie")
            rec["to_local"] = lj.get("do_lokalnie")
    ropes = {}
    for rec in lines:
        r = ropes.setdefault(rec["rope"], dict(rope=rec["rope"], group=rec["group"], kind=rec["kind"],
                                                material=rec["material"], diameter_m=rec["diameter_m"], segments=0,
                                                length_m=0.0, belayed_to=None, dynamic=False))
        r["segments"] += 1
        r["length_m"] = round(r["length_m"] + rec["length_m"], 3)
        r["belayed_to"] = r["belayed_to"] or rec["belayed_to"]
        r["dynamic"] = r["dynamic"] or rec["dynamic"]
    J = dict(title="Rigging lines of the reference model", coordinate_system=UKLAD,
             note="one entry per straight or sagging segment; a rope may have several segments (same 'rope' name). "
                  "from/to/via are [x, s, z]; from_local/to_local are the end in the local coordinates of the "
                  "moving part named in from_object/to_object (Blender axes of that part).",
             counts=dict(segments=len(lines), ropes=len(ropes), dynamic=sum(1 for r in lines if r["dynamic"])),
             belaying_points=pin_out, ropes=sorted(ropes.values(), key=lambda r: r["rope"]), lines=lines)
    return J


def summary_rows(J):
    G = {}
    for r in J["lines"]:
        g = G.setdefault(r["group"], dict(group=r["group"], kinds=set(), materials=set(), segments=0, ropes=set(),
                                          length=0.0, dmin=9, dmax=0))
        g["kinds"].add(r["kind"])
        g["materials"].add(r["material"])
        g["segments"] += 1
        g["ropes"].add(r["rope"])
        g["length"] += r["length_m"]
        g["dmin"] = min(g["dmin"], r["diameter_m"])
        g["dmax"] = max(g["dmax"], r["diameter_m"])
    rows = []
    for g in sorted(G.values(), key=lambda g: -g["length"]):
        rows.append([g["group"], "/".join(sorted(g["kinds"])), "/".join(sorted(g["materials"])), len(g["ropes"]),
                     g["segments"], round(g["length"], 2), g["dmin"], g["dmax"]])
    rows.append(["TOTAL", "", "", sum(r[3] for r in rows), sum(r[4] for r in rows), round(sum(r[5] for r in rows), 2),
                 "", ""])
    return rows


# ------------------------------------------------------------------ pokład, stanowiska, części ruchome
def deck_layout(S, nazwy_en):
    P = S.plik("bryg_poklad.json")
    out = dict(title="Deck layout of the reference model (walking areas, obstacles, stairs, climbs)",
               coordinate_system=UKLAD, note="polygons are [x, s] in plan; heights z above the design waterline",
               walker=dict(radius_m=P["uklad"]["postac"]["promien"], height_m=P["uklad"]["postac"]["wzrost"],
                           test_grid_step_m=P["uklad"]["krok_siatki_testu"]), surfaces=[], obstacles=[], stairs=[],
               passages=[], climbs=[], side_edge={})
    K = S.K
    for p in P["powierzchnie"]:
        rec = dict(name=T(p["nazwa"].replace("mars_", "mars_x_") if False else _pow_pl(p["nazwa"]), "surface"),
                   level=_poziom(p["poziom"]))
        if "wielokat" in p:
            rec["polygon_x_s"] = r3(p["wielokat"])
        w = p.get("wysokosc", {})
        if "os_z_y" in w:
            rec["height"] = dict(formula="z = centreline_z(s) %s- %.3f·(x / %.2f)²" % (
                "+ %.2f " % K["POLPOKLAD_H"] if p["poziom"] == "rufowy" else "", K["WYPUKLOSC"], K["POL_B"]),
                centreline_s_z=r3(w["os_z_y"]))
        if "stala" in w:
            rec["height"] = dict(constant_z_m=w["stala"])
        if "siatka" in p:
            g = p["siatka"]
            rec["grid"] = dict(x0_m=g["x0"], s0_m=g["z0"], step_m=g["krok"], nx=g["nx"], ns=g["nz"],
                               z_rows_by_s=g["y"], note="z of the deck surface; rows along s from s0, columns along x")
        if "otwor" in p:
            m = re.findall(r"[-\d.]+", p["otwor"].split(":")[1])
            rec["hole"] = dict(kind="lubber's hole", x_half_m=float(m[0]), s_from_m=float(m[1]), s_to_m=float(m[2]))
        if "z0" in p:
            rec.update(s_aft_m=p["z0"], s_fore_m=p["z1"], width_m=p["szerokosc"], note="both sides, outside the bulwark")
        out["surfaces"].append(rec)
    for o in P["przeszkody"]:
        rec = dict(name=T(o["nazwa"], "obstacle"), object=T(o["obiekt"]) if o.get("obiekt") and en(o["obiekt"]) else None,
                   level=_poziom(o["poziom"]), height_m=o["wysokosc"], walkable=o["chodzic"], step_height_m=o["prog"],
                   variant=T(o["wariant"]) if o.get("wariant") else None, shape="circle" if o["typ"] == "kolo" else "rectangle",
                   centre_x_s=o["srodek"])
        if o["typ"] == "kolo":
            rec["radius_m"] = o["r"]
        else:
            rec.update(length_s_m=o["dl_z"], width_x_m=o["szer_x"], rotation_deg=o.get("obrot", 0.0))
        out["obstacles"].append(rec)
    for o in P["schody"]:
        out["stairs"].append(dict(name=T(o["nazwa"]), start=ship_from_gltf(o["poczatek"]), end=ship_from_gltf(o["koniec"]),
                                  width_m=o["szerokosc"], steps=o["stopnie"], rise_m=o["wznios"],
                                  tread_m=o["glebokosc_stopnia"]))
    for o in P["przejscia"]:
        nm = {"luk_glowny_drabina": "main_hatch_ladder", "zejsciowka_kabina": "companion_to_cabin"}[o["nazwa"]]
        R.dodaj("passage", o["nazwa"], nm)
        out["passages"].append(dict(name=nm, type={"drabina_w_dol": "ladder_down", "schody_w_dol": "stairs_down"}[o["typ"]],
                                    start=ship_from_gltf(o["poczatek"]), end=ship_from_gltf(o["koniec"]),
                                    width_m=o["szerokosc"], steps=o["stopnie"],
                                    note="hold not modelled" if "luk" in o["nazwa"] else "cabin interior not modelled"))
    for o in P["wspinaczka"]:
        out["climbs"].append(dict(name=T(o["nazwa"]), points=[ship_from_gltf(q) for q in o["punkty"]],
                                  rung_spacing_m=o["szczeble_co"],
                                  note="ratlines from the rail; last leg up the futtock shrouds to the rim of the top"))
    out["side_edge"] = dict(main_deck_edge="= polygon of main_deck (inner face of the bulwark)",
                            quarterdeck_edge="= polygon of quarterdeck",
                            rail_s_z=[[q[0], q[1]] for q in P["burta"]["reling_y"]],
                            note="outside the deck polygon is overboard; rail = top of the rail cap")
    return out


def _pow_pl(n):
    m = re.match(r"^mars_(fok|grot)$", n)
    if m:
        SLOWA[n] = SLOWA[m.group(1)] + "_top"
    m = re.match(r"^lawy_wantowe_(fok|grot)$", n)
    if m:
        SLOWA[n] = SLOWA[m.group(1)] + "_channels"
    return n


def _poziom(p):
    if p is None:
        return None
    m = re.match(r"^mars_(fok|grot)$", p)
    if m:
        return T(_pow_pl(p), "level")
    return {"lawa": R.dodaj("level", "lawa", "channel")}.get(p) or T(p, "level")


def stations(S, rope_pl_en):
    P = S.plik("bryg_poklad.json")
    rows = []
    for t in P["stanowiska"]:
        f = ship_from_gltf(t["patrzy"])
        yaw = math.degrees(math.atan2(f[0], f[1]))
        ropes = [rope_pl_en.get(x) or _en_belay(x) for x in t["liny"]]
        for x, e_ in zip(t["liny"], ropes):
            R.dodaj("rope", x, e_)
        rows.append([T(t["nazwa"], "station"), T(t["czynnosc"], "activity"), _poziom(t["poziom"]) or "",
                     *r3(ship_from_gltf(t["stopy"])), *r3(f), round(yaw, 1),
                     T(t["obiekt"]) if t.get("obiekt") else "", opis_tekst(t["os"]) or "",
                     "" if not t["zakres"] else t["zakres"][0], "" if not t["zakres"] else t["zakres"][1],
                     t["wysokosc_rak"], ";".join(ropes), opis_tekst(t["opis"]) or "",
                     T(t["wariant"]) if t.get("wariant") else ""])
    return rows


def _glb_nodes(S, plik="bryg.glb"):
    p = os.path.join(S.out_model, plik)
    if not os.path.exists(p):
        return []
    with open(p, "rb") as f:
        head = f.read(20)
        n = struct.unpack("<I", head[12:16])[0]
        G = json.loads(f.read(n))
    return G.get("nodes", [])


def _euler_z(rot):
    """Oś lokalna Z obiektu (Euler XYZ Blendera) w układzie statku [x, s, z]."""
    a, b, c = rot
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    Rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])
    Ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]])
    Rz = np.array([[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]])
    z = (Rz @ Ry @ Rx)[:, 2]
    return [round(float(z[0]), 4), round(float(-z[1]), 4), round(float(z[2]), 4)]


def moving_parts(S):
    P = S.plik("bryg_poklad.json")
    Kj = S.plik("kontrola.json") or {}
    ogr = Kj.get("ograniczenia_ruchu", {})
    lista = _glb_nodes(S)
    nodes = {n.get("name"): n for n in lista}
    pivots = {o["obiekt"]: o for o in P.get("obiekty_ruchome", [])}
    # części ruchome opisane dopiero po etapie chodzenia (pokrywy furt, głowica steru) są w GLB (extras os_ruchu),
    # ale nie w bryg_poklad.json – dopisane z węzłów GLB; punkt obrotu = położenie węzła w świecie
    rodzic = {c: i for i, n in enumerate(lista) for c in n.get("children", [])}

    def _obroc(q, v):
        x, y, z, w = q
        u = np.array([x, y, z])
        v = np.array(v, dtype=float)
        return v + 2.0 * np.cross(u, np.cross(u, v) + w * v)

    def _swiat(i):
        p = np.zeros(3)
        while i is not None:
            n = lista[i]
            p = _obroc(n.get("rotation", [0, 0, 0, 1]), p * np.array(n.get("scale", [1, 1, 1]))) + \
                np.array(n.get("translation", [0, 0, 0]), dtype=float)
            i = rodzic.get(i)
        return [float(v) for v in p]
    for i, n in enumerate(lista):
        nm, e = n.get("name"), n.get("extras") or {}
        if nm and nm not in pivots and e.get("os_ruchu") and not nm.startswith("lina_"):
            pivots[nm] = dict(obiekt=nm, os=e["os_ruchu"], pivot=_swiat(i))
    rows = []
    for nm, o in pivots.items():
        n = nodes.get(nm, {})
        e = n.get("extras") or {}
        ob = S.ob.get(nm)
        axis_dir = _euler_z(ob["obrot"]) if ob else ""
        rodz = "translation" if "zakres_m" in e else "rotation"
        zak = e.get("zakres_m") or e.get("zakres_deg") or ["", ""]
        unit = "m" if "zakres_m" in e else "deg"
        rest = 0
        if nm.startswith("furta_pokrywa"):
            rest = e.get("kat_otwarcia_deg", 0.0)
        lim = None
        for grp in ("pokrywy", "dziala", "reje"):
            if nm in ogr.get(grp, {}):
                g = ogr[grp][nm]
                lim = g.get("ogranicza") if "ogranicza" in g else (g.get("opuszczona") or {}).get("ogranicza")
        hoist = e.get("zakres_deg_podniesiona") or ["", ""]
        rows.append([T(nm), rodz, opis_tekst(e.get("os_ruchu") or o["os"]), *r3(ship_from_gltf(o["pivot"])),
                     *(axis_dir if axis_dir else ["", "", ""]), zak[0], zak[1], unit, rest,
                     T(e["wariant"]) if e.get("wariant") else "", (T(lim) if lim and en(lim) else (lim or "")),
                     hoist[0], hoist[1], e.get("wysokosc_robocza_dz_m", ""),
                     "yes" if e.get("obrot_ciagly") else "", e.get("przelozenie_obroty_na_35deg", ""),
                     "n = tiller_length · sin(35°) / (π · drum_diameter)" if e.get("przelozenie_wzor") else ""])
        for k in e:
            R.dodaj("glb_extras_key", k, NP.KLUCZE.get(k, k))
    return rows


# ------------------------------------------------------------------ mapa nazw
def names_map(S, nazwy):
    for o in S.M["obiekty"]:
        nm = o["nazwa"]
        if nm.startswith("lina_"):
            continue
        T(nm, "object")
    for n in _glb_nodes(S):
        T(n.get("name"), "glb_node")
    # bryły kolizji (bryg_kolizja.glb): kolizja_<nazwa> → collision_<name>
    for n in _glb_nodes(S, "bryg_kolizja.glb"):
        nm = n.get("name") or ""
        if nm.startswith("kolizja_"):
            e_ = en(nm[len("kolizja_"):])
            if e_ is None:
                raise KeyError("brak tłumaczenia bryły kolizji: %r" % nm)
            R.dodaj("collision_node", nm, "collision_" + e_)
    for k, v in NP.KLUCZE.items():
        R.dodaj("json_key", k, v)
    for k, (e_, *_r) in NP.PARAM.items():
        R.dodaj("parameter", k, e_)
    for k, v in NP.PODKLUCZE.items():
        R.dodaj("parameter_subkey", k, v)
    for k, v in NP.LINY.items():
        R.dodaj("rope_kind", k, v)
    for k, v in NP.OPISY.items():
        R.dodaj("text", k, v)
    for g in sorted({L["g"] for L in S.M["liny"]}):
        T(g, "rope_group")
    rows = sorted(((k[0], k[1], v[0], v[1]) for k, v in R.rows.items()), key=lambda r: (r[0], r[1]))
    return rows


# ------------------------------------------------------------------ zapis
def _csv(path, header, rows, komentarz=UKLAD_CSV):
    with open(path, "w", encoding="utf-8", newline="") as f:
        for c in komentarz:
            f.write(c + "\n")
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])


def _json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def zapisz(S, data_dir):
    os.makedirs(data_dir, exist_ok=True)
    M = S.M
    nazwy = nazwy_lin(M)
    rope_pl_en = {pl: e for (pl, e, t) in nazwy}
    P = parameters(S, M, nazwy)
    _json(os.path.join(data_dir, "parameters.json"), P)
    rows, J = offsets(S)
    _csv(os.path.join(data_dir, "offsets.csv"), ["table", "station_s_m", "station_z_df_m", "line", "line_value_m",
                                                 "half_breadth_m", "z_m"], rows)
    _json(os.path.join(data_dir, "offsets.json"), J)
    sp = spars(S)
    cols = ["spar", "kind", "length_m", "d_max_m", "d_mid_m", "d_end_m", "start_x_m", "start_s_m", "start_z_m",
            "end_x_m", "end_s_m", "end_z_m", "angle_deg", "angle_ref", "deck_s_m", "deck_z_m", "top_platform_z_m",
            "masthead_from_z_m", "crosstrees_z_m", "cap_z_m", "truck_z_m", "lowered_z_m", "hoisted_z_m",
            "working_height_dz_m", "note"]
    srows = []
    for r in sp:
        srows.append([r3(r.get("length_m")) if k == "length_m" else
                      (r3(r["start"][i], 3) if k.startswith("start_") else r3(r["end"][i], 3) if k.startswith("end_")
                       else r3(r.get(k), 3))
                      for k, i in [(c, {"x": 0, "s": 1, "z": 2}.get(c.split("_")[1], 0) if c.startswith(("start_",
                                                                                                     "end_")) else 0)
                                   for c in cols]])
    _csv(os.path.join(data_dir, "spars.csv"), cols, srows)
    RJ = rigging(S, nazwy)
    _json(os.path.join(data_dir, "rigging-lines.json"), RJ)
    _csv(os.path.join(data_dir, "rigging-summary.csv"), ["group", "kind", "material", "ropes", "segments",
                                                         "total_length_m", "d_min_m", "d_max_m"], summary_rows(RJ),
         komentarz=("# totals per rope group; lengths are the sum of segment lengths in rigging-lines.json",))
    DL = deck_layout(S, rope_pl_en)
    _json(os.path.join(data_dir, "deck-layout.json"), DL)
    _csv(os.path.join(data_dir, "stations.csv"),
         ["station", "activity", "level", "x_m", "s_m", "z_m", "facing_x", "facing_s", "facing_z", "facing_deg",
          "object", "axis", "range_min", "range_max", "hand_height_m", "ropes", "note", "variant"],
         stations(S, rope_pl_en), komentarz=UKLAD_CSV + ("# x_m, s_m, z_m: feet of the figure; facing_deg: 0 = "
                                                         "forward, +90 = towards port",))
    _csv(os.path.join(data_dir, "moving-parts.csv"),
         ["part", "kind", "axis", "pivot_x_m", "pivot_s_m", "pivot_z_m", "axis_dir_x", "axis_dir_s", "axis_dir_z",
          "range_min", "range_max", "unit", "rest", "variant", "limited_by", "range_hoisted_min", "range_hoisted_max",
          "working_height_dz_m", "continuous", "wheel_turns_for_35deg", "gear_ratio_formula"],
         moving_parts(S), komentarz=UKLAD_CSV + ("# axis_dir: local Z axis of the part in ship coordinates; ranges of "
                                                 "yards: lowered (range_min/max) and hoisted to the working position",))
    NM = names_map(S, nazwy)
    _csv(os.path.join(data_dir, "names-map.csv"), ["category", "polish", "english", "note"], NM,
         komentarz=("# Polish names of objects, GLB nodes, keys and values of the generator -> English names used in "
                    "the public data and drawings; one Polish name, one English name",))
    from dane_schemat import zapisz_schemat
    zapisz_schemat(data_dir, dict(segments=RJ["counts"]["segments"], ropes=RJ["counts"]["ropes"],
                                  stations=len(S.plik("bryg_poklad.json")["stanowiska"]), names=len(NM)))
    return dict(nazwy=nazwy, rigging=RJ, spars=sp, konflikty=R.konflikty, names=len(NM))
