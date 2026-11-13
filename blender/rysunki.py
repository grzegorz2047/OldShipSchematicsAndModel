"""Rysunki techniczne i dane publiczne modelu wzorcowego – jedno polecenie (Blender 5.2, bez okna), uruchamiane
z katalogu głównego repozytorium:

    blender -b --factory-startup --python blender/rysunki.py -- [--model DIR] [--generator DIR] [--blend PLIK]
        [--cache DIR] [--publiczne KATALOG] [--tylko a,b] [--bez-png] [--bez-pdf] [--bez-danych] [--migawka]

Wyjście: <publiczne>/data/ i <publiczne>/plans/; domyślnie --publiczne to katalog główny repozytorium (nadpisuje
data/ i plans/ w repozytorium). Do próby bez nadpisywania: --publiczne build/<katalog>.
Wejście (stan modelu): --model – katalog z wynikami pełnej budowy (bryg.blend, bryg.glb, parametry.json, liny.json,
bryg_poklad.json, kontrola.json, tekstury/), domyślnie kopia build/rysunki_robocze/model; --generator – katalog z kopią
modułów generatora z tego samego stanu (domyślnie build/rysunki_robocze/generator; brak – moduły z blender/);
--blend – plik do rzutów siatek (domyślnie <model>/bryg.blend). --migawka: najpierw kopiuje wyniki budowy z build/
i moduły generatora do build/rysunki_robocze (stan do odtworzenia).

1. model_rysunkowy.py: generator (kopia) do etapu żagli w pamięci – liczby z ctx (drzewca, liny z opisem wywołań,
   kołki) → <cache>/model.json; potem otwiera kopię bryg.blend i robi rzuty krawędzi siatek z usuwaniem linii
   zasłoniętych → <cache>/rzuty.json.
2. dane_publiczne.py → <publiczne>/data/ (z plików w --model).
3. arkusze_*.py → <publiczne>/plans/<nazwa>.svg (angielskie) i plans/pl/<nazwa>.svg (polskie).
4. Podglądy PNG (plans/png/, plans/png/pl/, szerokość 2400 px) i plans/plans-en.pdf, plans/plans-pl.pdf (A3 poziomo)
   – przeglądarką Edge albo Chrome bez okna (osobny profil w katalogu podręcznym).
5. kontrola_publiczna.py – zgodność danych z modelem i brak polskich nazw.

Bez Blendera (gdy katalog podręczny jest aktualny): python blender/rysunki.py [opcje] – kroki 2–5.
"""
import json
import os
import shutil
import subprocess
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))     # katalog główny repozytorium (blender/ leży w nim)

try:
    import bpy  # noqa: F401
    W_BLENDERZE = True
except ImportError:
    W_BLENDERZE = False


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    rob = os.path.join(ROOT, "build", "rysunki_robocze")
    o = {"--publiczne": ROOT,
         "--model": os.path.join(rob, "model"), "--generator": os.path.join(rob, "generator"),
         "--cache": os.path.join(rob, "cache"), "--blend": None, "--tylko": None}
    flags = set()
    for i, x in enumerate(a):
        if x in o and i + 1 < len(a):
            o[x] = a[i + 1]
        elif x.startswith("--"):
            flags.add(x)
    o["flags"] = flags
    for k in ("--publiczne", "--model", "--generator", "--cache", "--blend"):
        if o[k]:
            o[k] = os.path.abspath(o[k])
    if not o["--blend"]:
        o["--blend"] = os.path.join(o["--model"], "bryg.blend")
    return o


MOJE = ("model_rysunkowy", "geometria", "nazwy_publiczne", "dane_publiczne", "dane_schemat", "kontrola_publiczna",
        "rysunki_svg", "slownik_rysunkow", "rysunki")


def migawka(A):
    """Kopia wyników pełnej budowy i modułów generatora (bez modułów rysunków) – stan, z którego powstają rysunki."""
    src = os.path.join(ROOT, "build")
    os.makedirs(A["--model"], exist_ok=True)
    os.makedirs(A["--generator"], exist_ok=True)
    for f in ("bryg.blend", "bryg.glb", "parametry.json", "liny.json", "bryg_poklad.json", "kontrola.json",
              "bryg_kolizja.glb"):
        shutil.copy2(os.path.join(src, f), os.path.join(A["--model"], f))
    if os.path.isdir(os.path.join(src, "tekstury")):
        shutil.copytree(os.path.join(src, "tekstury"), os.path.join(A["--model"], "tekstury"), dirs_exist_ok=True)
    for f in os.listdir(HERE):
        if f.endswith(".py") and f[:-3] not in MOJE and not f.startswith("arkusze_"):
            shutil.copy2(os.path.join(HERE, f), os.path.join(A["--generator"], f))


def stan_modelu(A):
    """Daty plików modelu, z których powstały rysunki i dane (do raportu i do pliku w katalogu podręcznym)."""
    out = {}
    for f in ("bryg.blend", "bryg.glb", "parametry.json", "liny.json", "bryg_poklad.json", "kontrola.json",
              "bryg_kolizja.glb"):
        p = os.path.join(A["--model"], f)
        if os.path.exists(p):
            out[f] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))
    return out


ARKUSZE = [
    # (plik, moduł, funkcja)
    ("ship-types", "arkusze_takielunek", "ship_types"),
    ("lines-plan", "arkusze_kadlub", "lines_plan"),
    ("frame-construction-arcs", "arkusze_konstrukcja", "frame_arcs"),
    ("hull-profile-structure", "arkusze_konstrukcja", "hull_profile"),
    ("midship-section", "arkusze_konstrukcja", "midship_section"),
    ("deck-plan", "arkusze_poklad", "deck_plan"),
    ("stern-and-head", "arkusze_poklad", "stern_and_head"),
    ("steering-gear", "arkusze_wyposazenie", "steering_gear"),
    ("capstan", "arkusze_wyposazenie", "capstan"),
    ("anchor-and-cathead", "arkusze_wyposazenie", "anchor"),
    ("pump", "arkusze_wyposazenie", "pump"),
    ("gun-and-carriage", "arkusze_wyposazenie", "gun"),
    ("spar-plan", "arkusze_takielunek", "spar_plan"),
    ("standing-rigging", "arkusze_takielunek", "standing_rigging"),
    ("deadeye-and-lanyard", "arkusze_takielunek", "deadeye"),
    ("running-rigging", "arkusze_takielunek", "running_rigging"),
    ("belaying-plan", "arkusze_takielunek", "belaying_plan"),
    ("blocks-and-deadeyes", "arkusze_takielunek", "blocks"),
    ("sail-plan", "arkusze_takielunek", "sail_plan"),
]


def przegladarka():
    """Chrome bez okna (Edge bez okna nie zapisuje tu zrzutów – zostaje jako ostatnia możliwość)."""
    kand = []
    for prog in (("Google", "Chrome", "Application", "chrome.exe"), ("Microsoft", "Edge", "Application", "msedge.exe")):
        for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            b = os.environ.get(env)
            if b:
                kand.append(os.path.join(b, *prog))
    for n in ("chrome", "google-chrome", "chromium", "msedge"):
        w = shutil.which(n)
        if w:
            kand.append(w)
    for k in kand:
        if os.path.exists(k):
            return k
    return None


def _uri(p):
    return "file:///" + os.path.abspath(p).replace("\\", "/").replace(" ", "%20")


def _uruchom(cmd, timeout=120):
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()            # tylko własny proces (PID)
    return p.returncode


def png_i_pdf(plans, cache, nazwy, jezyki=("en", "pl"), png=True, pdf=True):
    exe = przegladarka()
    if not exe:
        print("RYSUNKI: brak przeglądarki Edge/Chrome – bez PNG i PDF")
        return dict(png=0, pdf=0)
    prof = os.path.join(cache, "profil_przegladarki")
    html = os.path.join(cache, "html")
    os.makedirs(html, exist_ok=True)
    wynik = dict(png=0, pdf=0)
    base = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--user-data-dir=" + prof, "--force-device-scale-factor=1"]
    for jez in jezyki:
        sdir = plans if jez == "en" else os.path.join(plans, "pl")
        pdir = os.path.join(plans, "png") if jez == "en" else os.path.join(plans, "png", "pl")
        os.makedirs(pdir, exist_ok=True)
        if png:
            for n in nazwy:
                svg = os.path.join(sdir, n + ".svg")
                if not os.path.exists(svg):
                    continue
                W = 2400
                with open(svg, encoding="utf-8") as f:
                    head = f.read(400)
                a1 = 'width="841mm"' in head
                H = int(round(W * (594 / 841 if a1 else 297 / 420)))
                hp = os.path.join(html, "%s_%s.html" % (jez, n))
                with open(hp, "w", encoding="utf-8") as f:
                    f.write('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
                            'background:#fff}img{display:block;width:%dpx;height:%dpx}</style></head><body>'
                            '<img src="%s"></body></html>' % (W, H, _uri(svg)))
                out = os.path.join(pdir, n + ".png")
                if os.path.exists(out):
                    os.remove(out)
                _uruchom(base + ["--window-size=%d,%d" % (W, H), "--screenshot=" + out, _uri(hp)])
                if os.path.exists(out):
                    wynik["png"] += 1
        if pdf:
            hp = os.path.join(html, "pdf_%s.html" % jez)
            strony = []
            for n in nazwy:
                svg = os.path.join(sdir, n + ".svg")
                if os.path.exists(svg):
                    strony.append('<div class="p"><img src="%s"></div>' % _uri(svg))
            with open(hp, "w", encoding="utf-8") as f:
                f.write('<!doctype html><html><head><meta charset="utf-8"><style>@page{size:420mm 297mm;margin:0}'
                        'html,body{margin:0;padding:0}.p{width:420mm;height:297mm;page-break-after:always;'
                        'overflow:hidden}.p:last-child{page-break-after:auto}img{width:420mm;height:297mm;'
                        'display:block}</style></head><body>%s</body></html>' % "".join(strony))
            out = os.path.join(plans, "plans-%s.pdf" % jez)
            if os.path.exists(out):
                os.remove(out)
            _uruchom(base + ["--no-pdf-header-footer", "--print-to-pdf=" + out, _uri(hp)], timeout=300)
            if os.path.exists(out):
                wynik["pdf"] += 1
    return wynik


def rysuj(A, cache, kontekst):
    import importlib
    import rysunki_svg as RS
    plans = os.path.join(A["--publiczne"], "plans")
    tylko = A["--tylko"].split(",") if A["--tylko"] else None
    zrobione = []
    for i, (plik, mod, fn) in enumerate(ARKUSZE):
        if tylko and plik not in tylko:
            continue
        m = importlib.import_module(mod)
        for jez in ("en", "pl"):
            t = time.time()
            ark = getattr(m, fn)(kontekst, jez, i + 1, len(ARKUSZE))
            sciezka = os.path.join(plans, plik + ".svg") if jez == "en" else os.path.join(plans, "pl", plik + ".svg")
            ark.nazwa = plik
            ark.zapisz(sciezka)
        zrobione.append(plik)
        print("ARKUSZ %s %.1f s" % (plik, time.time() - t))
    with open(os.path.join(cache, "brakujace_etykiety.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(RS.BRAKUJACE)))
    if RS.BRAKUJACE:
        print("RYSUNKI: brak polskich etykiet: %d (<cache>/brakujace_etykiety.txt)" % len(RS.BRAKUJACE))
    return plans, zrobione


def main():
    t0 = time.time()
    A = args()
    if "--migawka" in A["flags"]:
        migawka(A)
    # moduły generatora z kopii (ten sam stan co pliki modelu) mają pierwszeństwo przed blender/
    if os.path.isdir(A["--generator"]) and os.path.exists(os.path.join(A["--generator"], "parametry.py")):
        sys.path.insert(0, A["--generator"])
    cache = A["--cache"]
    os.makedirs(cache, exist_ok=True)
    with open(os.path.join(cache, "stan_modelu.json"), "w", encoding="utf-8") as f:
        json.dump(dict(model=A["--model"], generator=A["--generator"], blend=A["--blend"], pliki=stan_modelu(A)), f,
                  ensure_ascii=False, indent=1)
    if W_BLENDERZE and "--bez-modelu" not in A["flags"]:
        import model_rysunkowy as MR
        ctx = MR.zbuduj_model(A["--model"])
        ctx["_cache"] = cache
        MR.zapisz_model(ctx, os.path.join(cache, "model.json"))
        R = MR.rzuty_z_pliku(A["--blend"], cache, MR.rzut_kotwicy(ctx))
        with open(os.path.join(cache, "rzuty.json"), "w", encoding="utf-8") as f:
            json.dump(R, f)
        print("RYSUNKI: model i rzuty %.1f s" % (time.time() - t0))
    import geometria as G
    S = G.Statek(cache, A["--model"])
    with open(os.path.join(cache, "rzuty.json"), encoding="utf-8") as f:
        rzuty = json.load(f)
    import dane_publiczne as DP
    data_dir = os.path.join(A["--publiczne"], "data")
    wynik = DP.zapisz(S, data_dir) if "--bez-danych" not in A["flags"] else None
    if wynik is None:
        nazwy = DP.nazwy_lin(S.M)
        wynik = dict(nazwy=nazwy, rigging=DP.rigging(S, nazwy), spars=DP.spars(S))
    kontekst = dict(S=S, rzuty=rzuty, dane=wynik, data_dir=data_dir)
    plans, zrobione = rysuj(A, cache, kontekst)
    if "--bez-png" not in A["flags"] or "--bez-pdf" not in A["flags"]:
        nazwy_ark = [p for p, _, _ in ARKUSZE]
        w = png_i_pdf(plans, cache, zrobione if A["--tylko"] else nazwy_ark,
                      png="--bez-png" not in A["flags"], pdf="--bez-pdf" not in A["flags"] and not A["--tylko"])
        print("RYSUNKI: PNG %d, PDF %d" % (w["png"], w["pdf"]))
    import kontrola_publiczna as KP
    k = KP.kontrola(A["--publiczne"], A["--model"])
    print("KONTROLA DANYCH: błędów %d" % len(k["bledy"]))
    for b in k["bledy"][:20]:
        print("  " + b)
    print("RYSUNKI KONIEC %.1f s" % (time.time() - t0))


main()
