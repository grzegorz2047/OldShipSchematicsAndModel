"""Test przenikania brył (BVH, układ świata, obiekty przed scaleniem do GLB).

Każdy obiekt siatkowy (bez lin) jest dzielony na spójne części (wyspy). Dla każdej pary wysp o stykających się
obwiedniach (także wysp tego samego obiektu): przecinające się trójkąty (BVHTree.overlap) i głębokość wniknięcia –
największa odległość wierzchołka jednej wyspy, który leży wewnątrz drugiej (najbliższy punkt powierzchni + normalna),
do jej powierzchni. Zgłaszana jest każda para z wniknięciem > PROG (5 mm), której nie obejmuje lista POLACZENIA
(połączenia zamierzone: zakryte albo konstrukcyjnie prawdziwe, z uzasadnieniem).

Do tego: współpłaszczyznowe ściany (migotanie), styk z pokładem przedmiotów stojących, zakresy ruchu części ruchomych
(obrót / przesunięcie próbkowane i ten sam test przenikania z otoczeniem).
"""
import fnmatch
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

PROG = 0.005

# (wzorzec obiektu A, materiał A lub '*', wzorzec obiektu B, materiał B lub '*', uzasadnienie)
POLACZENIA = [
    ("drzewca", "*", "kadlub", "*", "maszty przechodzą przez pokład w opętnikach i stoją na kilsonie (zakryte)"),
    ("drzewca", "*", "drzewca", "*", "dublinki: top kolumny w ezelhofcie i stenga w topie, belki marsa na policzkach, "
                                    "sztaby (fid) w piętach – złącza drzewc"),
    ("bukszpryt", "*", "kadlub", "*", "bukszpryt leży na głowicy dziobnicy i przechodzi przez gródź dziobową"),
    ("bukszpryt", "*", "bukszpryt", "*", "bomstenga w ezelhofcie bukszprytu, nakładki (bees) na drzewcu"),
    ("bukszpryt", "*", "galion", "*", "knechty bukszprytu obejmują drzewce (styk)"),
    ("kadlub_stepka", "*", "kadlub", "*", "stępka, dziobnica i tylnica: poszycie wchodzi w wrąb (rabbet), zakryte"),
    ("kadlub_stepka", "*", "galion", "*", "kolano galionu przykręcone do dziobnicy"),
    ("kadlub_stepka", "*", "kadlub_stepka", "*", "pięta tylnicy na stępce (czop)"),
    ("kadlub_sciek_wregi", "*", "kadlub", "*", "wierzchołki wręgów przechodzą przez pokład i nadburcie, ściek leży "
                                                "w narożniku pokład/nadburcie"),
    ("kadlub_sciek_wregi", "*", "kadlub_sciek_wregi", "*", "wierzchołek wręgu przechodzi przez ściek"),
    ("kadlub_reling", "*", "kadlub", "*", "pokrywa relingu nasadzona na wierzch nadburcia"),
    ("kadlub_reling", "*", "kadlub_sciek_wregi", "*", "wierzchołki wręgów wpuszczone w pokrywę relingu"),
    ("kadlub_reling", "*", "kadlub_reling", "*", "styk pokrywy burty z pokrywą pawęży (czop)"),
    ("kadlub_listwy", "*", "kadlub", "*", "listwy i szpigaty przybite do poszycia (wpuszczone ≤ 4 cm)"),
    ("kadlub_okucia_steru", "*", "kadlub*", "*", "okucia steru przybite do tylnicy i poszycia"),
    ("ster", "*", "kadlub_stepka", "*", "czopy steru w okuciach tylnicy (zawias)"),
    # (trzon w otworze kontry i pokładu rufowego ma luz – reguła zwalniająca ster × kadlub niepotrzebna)
    ("ster", "*", "kadlub_okucia_steru", "*", "czop w okuciu"),
    ("ster*", "*", "rumpel*", "*", "rumpel osadzony w głowicy steru (czop rumpla przez trzon)"),
    ("ster_glowica", "*", "ster", "*", "głowica nasadzona na trzon steru (jeden trzon; część nad pokładem w wariancie z "
                                       "rumplem)"),
    ("rumpel_pod_pokladem", "*", "kadlub", "*", "rumpel pracuje w kabinie pod pokładem rufowym (wnętrze rufówki nie "
                                                "jest modelowane jako pusta przestrzeń – całość zakryta)"),
    ("kolo_sterowe", "*", "kolo_stojaki", "*", "oś koła w łożyskach stojaków (współosiowa)"),
    ("kolo_stojaki", "drewno", "kadlub", "*", "krążek przepustu sterliny w otworze pokładu"),
    ("lina_sterlina", "*", "kadlub", "*", "sterlina przez przepust w pokładzie do krążków pod pokładem (zakryte)"),
    ("lina_sterlina", "*", "kolo_stojaki", "*", "sterlina w szczelinie przepustu"),
    ("lina_sterlina", "*", "kolo_sterowe", "*", "sterlina schodzi z bębna (zwoje)"),
    ("lina_sterlina", "*", "bloki*", "*", "sterlina przez krążek przy burcie"),
    ("lina_sterlina", "*", "rumpel_pod_pokladem", "*", "sterlina na sworzniu końca rumpla"),
    ("lina_talie_rumpla", "*", "rumpel", "*", "talia odciążająca na uchu rumpla"),
    ("lina_talie_rumpla", "*", "bloki*", "*", "talia przez blok"),
    ("lina_talie_rumpla", "*", "okucia_pokladu*", "*", "talia w pierścieniu w nadburciu"),
    ("lina_talie_rumpla", "*", "lina_talie_rumpla", "*", "dwie liny talii przy bloku"),
    ("rufa_*", "*", "kadlub*", "*", "listwy, okna i snycerka pawęży przybite do lica pawęży"),
    ("rufa_*", "*", "rufa_*", "*", "snycerka i listwy nakładane na siebie (płaskorzeźba)"),
    ("latarnia_rufowa", "*", "rufa_*", "*", "wspornik latarni wpuszczony w koronę pawęży"),
    ("latarnia_rufowa", "*", "latarnia_rufowa", "*", "słupki latarni w podstawie i kopule"),
    ("galion*", "*", "kadlub*", "*", "kolano, policzki i relingi galionu przybite do dziobnicy i burty"),
    ("galion*", "*", "galion*", "*", "relingi i słupki galionu łączone na czopy, zwój na kolanie"),
    ("kotbelki", "*", "kadlub*", "*", "kotbelka przechodzi przez nadburcie, wspornik przybity do burty"),
    ("kotbelki", "*", "kotbelki", "*", "kotbelka na wsporniku, rozeta i krążki w kotbelce"),
    ("lawy_wantowe", "*", "kadlub*", "*", "ława wantowa przykręcona do burty, puttingi przybite do berghołtu"),
    ("lawy_wantowe", "*", "lawy_wantowe", "*", "puttingi przechodzą przez nacięcia ławy; wsporniki pod ławą"),
    ("jufersy", "*", "lawy_wantowe", "*", "dolny jufers osadzony w puttingu na krawędzi ławy"),
    ("jufersy", "*", "jufersy", "*", "kipy (otwory) jufersa jako wkładki"),
    ("jufersy", "*", "drzewca", "*", "jufersy want stengowych na krawędzi marsa"),
    ("sztagi_okucia", "*", "drzewca", "*", "serca i okucia sztagów na drzewcach"),
    ("sztagi_okucia", "*", "bukszpryt", "*", "obroże sztagów na bukszprycie"),
    ("sztagi_okucia", "*", "kadlub*", "*", "okucia watersztagu na dziobnicy"),
    ("sztagi_okucia", "*", "galion", "*", "okucie watersztagu w kolanie galionu"),
    ("sztagi_okucia", "*", "lina_sztagi", "*", "mysz i serce na sztagu"),
    ("schody_rufowe", "*", "kadlub*", "*", "schody oparte o pokład i gródź progu"),
    ("schody_rufowe", "*", "schody_rufowe", "*", "stopnie wpuszczone w policzki, słupki poręczy w policzkach"),
    ("balustrada_progu", "*", "kadlub*", "*", "tralki i słupki osadzone w pokładzie rufowym"),
    ("balustrada_progu", "*", "balustrada_progu", "*", "tralki w poręczy i listwie dolnej"),
    ("grodz_drzwi", "*", "kadlub", "*", "drzwi i ościeżnice w grodzi progu"),
    ("grodz_drzwi", "*", "grodz_drzwi", "*", "płyciny w ramie drzwi"),
    ("furta_pokrywa_*", "*", "furta_pokrywa_*", "*", "zawiasy i ucho przybite do pokrywy"),
    ("nagielbank_*", "*", "kadlub", "*", "słupki nagielbanku przechodzą przez pokład"),
    ("nagielbank_*", "*", "nagielbank_*", "*", "kołki w otworach listwy, listwy na słupkach"),
    ("kolkownice", "*", "kadlub*", "*", "kołkownica przybita do wierzchołków wręgów nadburcia"),
    ("kolkownice", "*", "kolkownice", "*", "kołki w otworach kołkownicy"),
    ("kabestan_podstawa", "*", "kadlub", "*", "wieniec zapadek przykręcony do pokładu"),
    ("kabestan_podstawa", "*", "kabestan_podstawa", "*", "zęby wieńca i zapadki na słupkach"),
    ("kabestan_beben", "*", "kabestan_podstawa", "*", "stopa bębna obraca się w gnieździe podstawy na wrzecionie "
                                                      "(współosiowo, 5 mm, zakryte wieńcem zapadek)"),
    ("kabestan_beben", "*", "kabestan_beben", "*", "żebra przybite do rdzenia, drągi w gniazdach głowicy, obręcze"),
    ("pompa_[LP]", "*", "pompa_[LP]*", "*", "widełki i obręcze na pniu pompy, dźwignia w widełkach"),
    ("pompa_[LP]", "*", "kadlub", "*", "pień pompy przechodzi przez pokład do zęzy (sama pompa, nie dźwignia)"),
    ("luk_*", "*", "luk_*", "*", "kraty: listwy na krzyż wpuszczone w siebie, wzdłużnik pod kratą"),
    ("luk_*", "*", "kadlub", "*", "zrębnica luku osadzona w pokładzie"),
    ("dzialo_*", "*", "dzialo_*", "*", "czopy lufy w wycięciach lawety, koła na osiach"),
    ("dzwon*", "*", "dzwon*", "*", "serce i ucho dzwonu, rama na czopach"),
    ("szafka_kompasowa", "*", "szafka_kompasowa", "*", "listwy i szyby w ramie szafki"),
    ("zejsciowka", "*", "zejsciowka", "*", "daszek na ściankach, stopnie drabiny w policzkach"),
    ("zejsciowka", "*", "kadlub", "*", "ścianki zejściówki osadzone w pokładzie rufowym, drabina w otworze"),
    ("rumpel*", "*", "rumpel*", "*", "okucie i sworzeń na rumplu"),
    # części tego samego obiektu modelowane jako osobne zamknięte bryły (bez scalania logicznego) – styki konstrukcyjne
    ("ster", "*", "ster", "*", "czopy, taśmy okuć i trzon na płetwie steru (osobne bryły)"),
    ("ster_glowica", "*", "ster_glowica", "*", "obręcze na głowicy trzonu"),
    ("gafel", "*", "gafel", "*", "szczęki i okucia na gaflu"),
    ("bom", "*", "bom", "*", "szczęki i okucia na bomie"),
    ("pompa_[LP]_dzwignia", "*", "pompa_[LP]_dzwignia", "*", "poprzeczka i sworzeń wpuszczone w dźwignię"),
    ("lodz", "*", "lodz", "*", "wręgi, ławki, listwy i dulki na poszyciu łodzi"),
    ("kolo_sterowe", "*", "kolo_sterowe", "*", "szprychy w piaście i wieńcu, bęben i kołnierze na osi"),
    ("kolo_stojaki", "*", "kolo_stojaki", "*", "stojaki na podwalinie, krążki w ramach przepustów"),
    ("szafka_kompasowa", "*", "szafka_kompasowa_szklo", "*", "szybki w ramkach drzwiczek"),
    ("lina_ruchome", "*", "bukszpryt", "*", "topenanta blindarei obłożona na ezelhofcie bukszprytu"),
    ("wyposazenie_drobne", "*", "wyposazenie_drobne", "*", "obręcze beczki, listwy kojca i skrzyni"),
    ("wyposazenie_drobne", "*", "kadlub*", "*", "komin kambuza przechodzi przez pokład; stojaki na kule na ścieku"),
    ("knagi_rufowe", "*", "kadlub*", "*", "knagi przybite do nadburcia"),
    ("knagi_rufowe", "*", "knagi_rufowe", "*", "róg knagi na podstawie"),
    ("kotwica_*", "*", "kotwica_*", "*", "trzon w koronie, łapy na ramionach, obręcze na poprzeczce"),
    ("dzialko_*", "*", "kadlub_reling", "*", "trzpień działka w gnieździe relingu"),
    ("dzialko_*", "*", "dzialko_*", "*", "lufa w widełkach"),
    ("rak_*", "*", "drzewca", "*", "rak (lina z kulkami) obejmuje maszt"),
    ("rak_*", "*", "reja_*", "*", "rak przywiązany do środka rei"),
    ("rak_*", "*", "rak_*", "*", "kulki raka nawleczone na linę"),
    ("rak_*", "*", "zagiel_*", "*", "rak za środkiem rei przykryty buntem zwiniętego żagla"),
    ("lina_stropy", "*", "zagiel_*", "*", "strop rei (sling) przy środku rei przykryty buntem zwiniętego żagla"),
    ("reja_*", "*", "reja_*", "*", "obręcze i klampy na rei"),
    ("gafel", "*", "drzewca", "*", "szczęki gafla obejmują maszt"),
    ("bom", "*", "drzewca", "*", "szczęki bomu obejmują maszt"),
    ("zagiel_*", "*", "reja_*", "*", "żagiel przywiązany do rei (wałek na rei)"),
    ("zagiel_*", "*", "zagiel_*", "*", "krawaty leżą na płótnie"),
    ("zagiel_gaflowy", "*", "gafel", "*", "żagiel podgarnięty do gafla"),
    ("zagiel_gaflowy", "*", "drzewca", "*", "przednie lik żagla na maszcie snow (raki)"),
    ("zagiel_gaflowy", "*", "bom", "*", "dolne lik na bomie"),
    ("zagle_sztakslowe", "*", "bukszpryt", "*", "sztaksle opuszczone na bukszpryt"),
    ("zagle_sztakslowe", "*", "lina_sztagi", "*", "sztaksel na sztagu (raki sztaksla)"),
    ("bloki", "*", "drzewca", "*", "blok na stropie przy drzewcu"),
    ("bloki", "*", "reja_*", "*", "blok na stropie przy noku / środku rei"),
    ("bloki", "*", "bukszpryt", "*", "blok na stropie na bukszprycie"),
    ("bloki", "*", "gafel", "*", "blok na gaflu"),
    ("bloki", "*", "bom", "*", "blok na bomie"),
    ("bloki", "*", "okucia_pokladu", "*", "blok na pierścieniu"),
    ("okucia_pokladu*", "*", "kadlub*", "*", "trzpienie śrub oczkowych wpuszczone w nadburcie (zakryte)"),
    ("lina_wyblinki", "*", "lina_wanty_*", "*", "wyblinka obłożona wyblinką (clove hitch) na wancie"),
    ("lina_sciagacze", "*", "lina_wanty_*", "*", "ściągacz (catharpin) obłożony na wancie"),
    ("lina_sciagacze", "*", "jufersy", "*", "ściągacz przy jufersie podwantek"),
    ("lina_podwantki", "*", "lina_sciagacze", "*", "podwantki i ściągacze spotykają się na drążku (futtock stave)"),
    ("lina_podwantki", "*", "lina_podwantki", "*", "podwantki obłożone razem na drążku"),
    ("lina_paduny", "*", "lina_wanty_stengowe", "*", "pętle padunów i want stengowych na topie stengi (warstwami)"),
    ("lina_paduny", "*", "lina_paduny", "*", "pętle padunów na topie stengi"),
    ("lina_perty_*", "*", "drzewca", "*", "koniec perty przy środku rei obłożony na maszcie (strop)"),
    ("lina_wiazanie", "*", "kadlub", "*", "wiązanie bukszprytu przez dziobnicę nad galionem"),
    ("lina_wyblinki", "*", "lina_wanty_stengowe", "*", "wyblinka na wancie stengowej"),
    ("lina_wyblinki", "*", "lina_wyblinki", "*", "styk sąsiednich odcinków wyblinki na wancie"),
    ("lina_talrepy", "*", "jufersy", "*", "talrep przewleczony przez kipy jufersów"),
    ("lina_talrepy", "*", "lina_talrepy", "*", "odcinki talrepu stykają się w kipach"),
    ("lina_wanty_*", "*", "jufersy", "*", "wanta obłożona wokół górnego jufersa (strop)"),
    ("lina_wanty_*", "*", "lina_wanty_*", "*", "pętle want na topie ułożone warstwami"),
    ("lina_wanty_*", "*", "drzewca", "*", "pętla wanty na topie masztu"),
    ("lina_wanty_stengowe", "*", "drzewca", "*", "pętla wanty stengowej na topie stengi"),
    ("lina_wanty_bramstengowe", "*", "drzewca", "*", "pętla wanty bramstengowej na topie bramstengi"),
    ("lina_podwantki", "*", "drzewca", "*", "podwantka od płytki na marsie do drążka na wantach"),
    ("lina_podwantki", "*", "jufersy", "*", "podwantka do jufersa want stengowych"),
    ("lina_podwantki", "*", "lina_wanty_*", "*", "podwantka obłożona na wancie (drążek)"),
    ("lina_paduny", "*", "drzewca", "*", "padun z pętlą na topie stengi"),
    ("lina_paduny", "*", "jufersy", "*", "padun na jufersie"),
    ("lina_paduny", "*", "lawy_wantowe", "*", "padun do jufersa na ławie"),
    ("lina_sztagi", "*", "drzewca", "*", "pętla sztagu na topie"),
    ("lina_sztagi", "*", "bukszpryt", "*", "obroża sztagu i wanty bukszprytu na drzewcu"),
    ("lina_sztagi", "*", "sztagi_okucia", "*", "sztag przez serce i mysz"),
    ("lina_sztagi", "*", "kadlub*", "*", "watersztag i wanty bukszprytu na okuciach dziobu"),
    ("lina_sztagi", "*", "galion", "*", "watersztag w uchu kolana galionu"),
    ("lina_wiazanie", "*", "bukszpryt", "*", "wiązanie bukszprytu owinięte wokół drzewca"),
    ("lina_wiazanie", "*", "galion", "*", "wiązanie przez otwór w kolanie galionu"),
    ("lina_wiazanie", "*", "kadlub_stepka", "*", "wiązanie przez dziobnicę"),
    ("lina_wiazanie", "*", "lina_wiazanie", "*", "zwoje wiązania leżą na sobie"),
    ("lina_stropy", "*", "drzewca", "*", "strop rei obłożony na drzewcu"),
    ("lina_stropy", "*", "reja_*", "*", "strop wokół rei"),
    ("lina_stropy", "*", "bloki", "*", "strop bloku"),
    ("lina_perty_*", "*", "reja_*", "*", "perty i strzemiona owinięte wokół rei"),
    ("lina_perty_*", "*", "lina_perty_*", "*", "strzemię zawiązane na percie"),
    ("lina_ruchome", "*", "bloki", "*", "lina przewleczona przez blok"),
    ("lina_ruchome", "*", "reja_*", "*", "topenanta, bras i szoty obłożone na noku rei"),
    ("lina_ruchome", "*", "lina_ruchome", "*", "wisior brasu i bras / talia – połączenie na bloku"),
    ("lina_ruchome", "*", "drzewca", "*", "lina na bloku przy topie / stendze"),
    ("lina_ruchome", "*", "gafel", "*", "gardafał i pikfał na gaflu"),
    ("lina_ruchome", "*", "bom", "*", "dirki i szot na noku bomu"),
    ("lina_ruchome", "*", "nagielbank_*", "*", "lina obłożona na kołku"),
    ("lina_ruchome", "*", "kolkownice", "*", "lina obłożona na kołku"),
    ("lina_ruchome", "*", "knagi_rufowe", "*", "lina obłożona na knadze"),
    ("lina_buchty", "*", "nagielbank_*", "*", "buchta zawieszona na kołku"),
    ("lina_buchty", "*", "kolkownice", "*", "buchta zawieszona na kołku"),
    ("lina_buchty", "*", "lina_buchty", "*", "zwoje buchty"),
    ("lina_dziala", "*", "okucia_pokladu", "*", "lina w pierścieniu przy burcie"),
    ("lina_dziala", "*", "bloki", "*", "talia przez blok"),
    ("lina_dziala", "*", "dzialo_*", "*", "lina hamująca wokół gałki lufy"),
    ("lina_dziala", "*", "lina_dziala", "*", "dwie liny talii przy bloku"),
    ("lina_kabestan_*", "*", "kabestan_beben", "*", "linka przez końce drągów"),
    ("lina_kotwice", "*", "kadlub*", "*", "lina kotwiczna przez kluzę"),
    ("lina_kotwice", "*", "rufa_dziob*", "*", "lina przez pierścień kluzy"),
    ("lina_kotwice", "*", "kotbelki", "*", "stoper na kotbelce"),
    ("lina_kotwice", "*", "kotwica_*", "*", "lina na pierścieniu kotwicy"),
    ("lina_kotwice", "*", "okucia_pokladu", "*", "stoper w pierścieniu"),
    ("lina_lodz", "*", "lodz*", "*", "faleń na dziobie łodzi / zawiesia"),
    ("lina_lodz", "*", "okucia_pokladu", "*", "faleń w pierścieniu"),
    ("lina_lodz", "*", "kadlub_reling", "*", "faleń przez pierścień na relingu pawęży"),
    ("lina_dzwon", "*", "dzwon*", "*", "linka serca dzwonu"),
    ("rak_*", "*", "drzewca", "*", "rak obejmuje maszt"),
    ("bloki", "*", "drzewca", "*", "blok na stropie przy drzewcu"),
    ("bloki", "*", "bloki", "*", "bloki talii przy sobie"),
    # stropy bloków (wyposazenie.stropy_blokow): koniec stropu 2 cm w części, na której blok jest zaczepiony
    ("bloki*", "*", "bloki*", "*", "strop wychodzi z korpusu własnego bloku"),
    ("bukszpryt", "*", "nagielbank_fok", "*", "pięta bukszprytu oparta o słupek nagielbanku foka (czop pięty w bitsach)"),
    ("bloki*", "*", "lawy_wantowe", "*", "strop dolnego bloku talii fału w ławie wantowej"),
    ("bloki*", "*", "kadlub_reling", "*", "strop bloku obłożony na relingu"),
    ("bloki*", "*", "rumpel", "*", "strop bloku talii na rumplu"),
    ("bloki*", "*", "jufersy", "*", "strop bloku przy jufersie"),
    ("bloki*", "*", "dzialo_*", "*", "strop bloku talii działa na lawecie"),
    ("bloki*", "*", "kotbelki", "*", "strop bloku talii kotwicznej na kotbelce"),
    ("bloki*", "*", "lina_sztagi", "*", "blok brasu zawieszony na stropie na sztagu"),
    ("bloki*", "*", "lina_wanty_*", "*", "blok zawieszony na stropie na wancie"),
    ("bloki*", "*", "lina_paduny", "*", "blok zawieszony na stropie na padunie"),
    ("bloki*", "*", "lina_podwantki", "*", "blok zawieszony na stropie na podwantce"),
]


def _grupa_liny(n):
    """lina_dyn_<grupa>_<nr>[_glb] → lina_<grupa> (reguły pisane dla grup lin)."""
    if n.endswith("_glb"):
        n = n[:-4]
    if n.startswith("lina_dyn_"):
        core = n[len("lina_dyn_"):]
        if "_" in core and core.rsplit("_", 1)[1].isdigit():
            core = core.rsplit("_", 1)[0]
        return "lina_" + core
    return n


def pasuje(a, ma, b, mb):
    a, b = _grupa_liny(a), _grupa_liny(b)
    for (pa, pma, pb, pmb, why) in POLACZENIA:
        for (x, mx, y, my) in ((a, ma, b, mb), (b, mb, a, ma)):
            if fnmatch.fnmatch(x, pa) and fnmatch.fnmatch(y, pb) and fnmatch.fnmatch(mx, pma) and fnmatch.fnmatch(my, pmb):
                return why
    return None


def wyspy(ob, M=None):
    """Spójne części obiektu: lista (wierzchołki świata (n×3), trójkąty (m×3), materiał dominujący)."""
    me = ob.data
    M = M or ob.matrix_world
    n = len(me.vertices)
    if n == 0:
        return []
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    Mn = np.array(M)
    co = co @ Mn[:3, :3].T + Mn[:3, 3]
    ed = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    par = np.arange(n)

    def find(i):
        r = i
        while par[r] != r:
            r = par[r]
        while par[i] != r:
            par[i], i = r, par[i]
        return r
    for a, b in ed:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
    roots = np.array([find(i) for i in range(n)])
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tri)
    tri = tri.reshape(-1, 3)
    tmat = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("material_index", tmat)
    mats = [m.name if m else "-" for m in me.materials]
    out = []
    troot = roots[tri[:, 0]]
    for r in np.unique(roots):
        vi = np.where(roots == r)[0]
        ti = np.where(troot == r)[0]
        if len(ti) == 0:
            continue
        remap = -np.ones(n, np.int64)
        remap[vi] = np.arange(len(vi))
        t = remap[tri[ti]]
        mi = np.bincount(tmat[ti]).argmax() if len(mats) else 0
        # zamknięta: każda krawędź trójkątów występuje parzyście (po zszyciu położeń)
        e = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
        _, cnt = np.unique(e, axis=0, return_counts=True)
        closed = bool(np.all(cnt % 2 == 0))
        out.append((co[vi], t, mats[mi] if mi < len(mats) else "-", closed))
    return out


def bvh(v, t):
    return BVHTree.FromPolygons([tuple(p) for p in v], [tuple(x) for x in t], all_triangles=True)


DIRS = [Vector((1, 0.013, 0.007)).normalized(), Vector((0.011, 1, 0.017)).normalized(),
        Vector((0.009, 0.015, 1)).normalized()]


def wewnatrz(tree, p):
    votes = 0
    for d in DIRS:
        n = 0
        o = Vector(p)
        for _ in range(64):
            hit = tree.ray_cast(o, d)
            if hit[0] is None:
                break
            n += 1
            o = hit[0] + d * 1e-5
        votes += n & 1
    return votes >= 2


def glebokosc(vA, bB, mn, mx, closed=True):
    """Największe wniknięcie wierzchołków A w zamkniętą bryłę B (test wnętrza promieniami, odległość do
    powierzchni). Dla otwartej B – 0 (liczą się tylko przecięcia trójkątów)."""
    if not closed:
        return 0.0
    m = np.all((vA > mn) & (vA < mx), axis=1)
    idx = np.nonzero(m)[0]
    if len(idx) > 300:
        idx = idx[:: len(idx) // 300 + 1]
    best = 0.0
    global _OSTATNI_PUNKT
    for j in idx:
        p = vA[j]
        if wewnatrz(bB, p):
            loc, nrm, _, d = bB.find_nearest(Vector(p))
            if loc is not None and d > best:
                best = d
                _OSTATNI_PUNKT = tuple(p)
    return best


_OSTATNI_PUNKT = None


def test(objs, prog=PROG, wsp_plaszcz=True):
    """objs: lista obiektów; zwraca (zgłoszenia, zamierzone, migotanie)."""
    parts = []
    for ob in objs:
        for (v, t, m, cl) in wyspy(ob):
            parts.append(dict(ob=ob.name, mat=m, v=v, t=t, mn=v.min(0), mx=v.max(0), cl=cl))
    if not parts:
        return [], [], []
    mn = np.array([p["mn"] for p in parts])
    mx = np.array([p["mx"] for p in parts])
    zgl, zam, mig = {}, {}, {}
    cache = {}

    def B(i):
        if i not in cache:
            cache[i] = bvh(parts[i]["v"], parts[i]["t"])
        return cache[i]
    n = len(parts)
    for i in range(n):
        ov = np.where(np.all(mn[i + 1:] <= mx[i] + prog, axis=1) & np.all(mx[i + 1:] >= mn[i] - prog, axis=1))[0] + i + 1
        for j in ov:
            a, b = parts[i], parts[j]
            pairs = B(i).overlap(B(j))
            key = (a["ob"], a["mat"], b["ob"], b["mat"]) if a["ob"] <= b["ob"] else (b["ob"], b["mat"], a["ob"], a["mat"])
            if pairs:
                global _OSTATNI_PUNKT
                _OSTATNI_PUNKT = None
                d1 = glebokosc(a["v"], B(j), b["mn"], b["mx"], b["cl"])
                p1 = _OSTATNI_PUNKT
                d2 = glebokosc(b["v"], B(i), a["mn"], a["mx"], a["cl"])
                d, pk = (d1, p1) if d1 >= d2 else (d2, _OSTATNI_PUNKT)
                if pk is None:                               # bez wnikania: środek pierwszej pary trójkątów
                    ta = a["t"][pairs[0][0]]
                    pk = tuple(a["v"][ta].mean(0))
                lina_x = a["ob"].startswith("lina_") or b["ob"].startswith("lina_")
                if not a["cl"] and not b["cl"]:
                    d = max(d, 0.0)
                if d > prog or (lina_x and d == 0.0 and not (a["cl"] and b["cl"])):
                    why = pasuje(a["ob"], a["mat"], b["ob"], b["mat"])
                    tgt = zam if why else zgl
                    rec = tgt.setdefault(key, dict(obiekty=[key[0], key[2]], materialy=[key[1], key[3]], pary=0,
                                                   max_wnikniecie_m=0.0, gdzie=None, uzasadnienie=why))
                    rec["pary"] += 1
                    if d > rec["max_wnikniecie_m"] or rec["gdzie"] is None:
                        rec["max_wnikniecie_m"] = max(rec["max_wnikniecie_m"], round(float(d), 4))
                        # (x, s, z) okrętu: najgłębszy punkt
                        rec["gdzie"] = [round(float(pk[0]), 2), round(float(-pk[1]), 2), round(float(pk[2]), 2)]
            elif wsp_plaszcz and a["ob"] != b["ob"]:
                # współpłaszczyznowe ściany w odległości < 1 mm (bez przecięć)
                tA = a["t"][:200]
                cen = a["v"][tA].mean(1)
                nA = np.cross(a["v"][tA[:, 1]] - a["v"][tA[:, 0]], a["v"][tA[:, 2]] - a["v"][tA[:, 0]])
                for c, nn in zip(cen, nA):
                    ln = np.linalg.norm(nn)
                    if ln < 1e-9:
                        continue
                    loc, nrm, idx, dd = B(j).find_nearest(Vector(c), 0.001)
                    if loc is not None and abs(Vector(nn / ln).dot(nrm)) > 0.995:
                        mig.setdefault(key, dict(obiekty=[key[0], key[2]], scian=0))
                        mig[key]["scian"] += 1
                        break
    return list(zgl.values()), list(zam.values()), list(mig.values())


PELNY_TEST = ("ster", "kolo_sterowe")
DOZWOLONE_DZIECI = ("rumpel", "ster_glowica", "rumpel_pod_pokladem")
WSPOLNE = {}


def zakresy(ctx, statyczne, prog=PROG, wariant=None):
    """Części ruchome w zakresie ruchu: próbkowanie położeń i test przenikania z obiektami w pobliżu (bez obiektów
    z listy zamierzonych połączeń danej części)."""
    wyniki = []
    sts = []
    for ob in statyczne:
        for (v, t, m, cl) in wyspy(ob):
            sts.append(dict(ob=ob.name, mat=m, v=v, t=t, mn=v.min(0), mx=v.max(0), b=None, cl=cl))

    def sprawdz(ob, M, nazwa_stanu, pelny=False):
        hits = []
        for (v, t, m, cl) in wyspy(ob, M):
            mnA, mxA = v.min(0), v.max(0)
            bA = None
            for s in sts:
                if np.any(s["mn"] > mxA + prog) or np.any(s["mx"] < mnA - prog):
                    continue
                if not pelny and pasuje(ob.name, m, s["ob"], s["mat"]):
                    continue
                # reja przy brasowaniu ciągnie za sobą swoje liny ruchome (w modelu stałe odcinki) – nie przeszkoda
                if ob.name.startswith(("reja_", "zagiel_")) and s["ob"].startswith(("lina_ruchome", "lina_dyn_")):
                    continue
                if s["ob"] == ob.name or s["ob"] in WSPOLNE.get(ob.name, ()):
                    continue
                if bA is None:
                    bA = bvh(v, t)
                if s["b"] is None:
                    s["b"] = bvh(s["v"], s["t"])
                if bA.overlap(s["b"]):
                    d = max(glebokosc(v, s["b"], s["mn"], s["mx"], s["cl"]), glebokosc(s["v"], bA, mnA, mxA, cl))
                    if d > prog or (pelny and d > 0):
                        hits.append(dict(z=s["ob"], wnikniecie_m=round(float(d), 4), czesc=m))
        return hits

    def przyrost(h, h0):
        """Pełny test: zgłoszenie tylko, gdy wniknięcie w danego sąsiada wzrosło względem spoczynku o > prog
        (części współosiowe – czopy, trzon, oś koła – mają stałe, zakryte styki)."""
        base = {}
        for r in h0:
            k = (r["z"], r.get("czesc"))
            base[k] = max(base.get(k, 0.0), r["wnikniecie_m"])
        out = []
        for r in h:
            if r["wnikniecie_m"] > base.get((r["z"], r.get("czesc")), 0.0) + prog:
                out.append(r)
        return out
    rules = []

    def inny(o):
        w = o.get("wariant")
        return wariant is not None and w is not None and w != wariant
    for ob in bpy.data.objects:
        if ob.type != "MESH" or inny(ob):
            continue
        n = ob.name
        if n == "ster" or n.startswith("rumpel"):
            rules.append((ob, "Z", [-35, -17, 0, 17, 35], "obrot"))
        elif n == "kolo_sterowe":
            rules.append((ob, "Z", list(range(0, 360, 30)), "obrot"))
        elif n.startswith("furta_pokrywa_"):
            kmax = float(ob.get("zakres_deg", [0, 100])[1])
            rules.append((ob, "Z", sorted(set([0, 30, 60, kmax])), "obrot_od_zamknietej"))
        elif n in ("pompa_L_dzwignia", "pompa_P_dzwignia"):
            rules.append((ob, "Z", [-25, 0, 25], "obrot"))
        elif n == "kabestan_beben":
            rules.append((ob, "Z", list(range(0, 360, 15)), "obrot"))
        elif n.startswith("reja_") and n != "reja_blinda":
            k = float(ob.get("zakres_brasowania_deg", 35))
            rules.append((ob, "Z", [-k, 0, k], "obrot"))
        elif n.startswith("dzialko_"):
            rules.append((ob, "Z", list(range(0, 360, 45)), "obrot"))
        elif n == "dzwon":
            rules.append((ob, "Z", [-30, 0, 30], "obrot"))
        elif n.startswith("dzialo_") and not n.endswith("_lufa") and "odrzut_m" in ob.keys():
            rules.append((ob, "-X", [0.0, float(ob["odrzut_m"])], "przesuniecie"))
    gmap = {g["obj"].name: g for g in ctx.get("dziala", [])}
    for (ob, ax, vals, kind) in rules:
        M0 = ob.matrix_world.copy()
        base_open = ob.get("otwarta", False)
        stany = []
        pelny = ob.name in PELNY_TEST
        if pelny:
            h0 = sprawdz(ob, M0, 0, True)
            for ch in ob.children:
                if ch.type == "MESH" and not ch.name.startswith("lina_") and ch.name in DOZWOLONE_DZIECI and not inny(ch):
                    h0 += sprawdz(ch, ch.matrix_world, 0, True)
        for v in vals:
            if kind == "przesuniecie" and ob.name in gmap:
                M = macierz_dziala(ctx, gmap[ob.name], v)
            elif kind == "przesuniecie":
                M = M0 @ Matrix.Translation((-v, 0, 0))
            elif kind == "obrot_od_zamknietej":
                kat = math.radians(ob.get("kat_otwarcia_deg", ctx["K"]["POKRYWA_KAT"])) if base_open else 0.0
                M = M0 @ Matrix.Rotation(math.radians(v) - kat, 4, "Z")
            else:
                M = M0 @ Matrix.Rotation(math.radians(v), 4, "Z")
            h = sprawdz(ob, M, v, pelny)
            # dzieci (lufa, rumple steru) przesuwają się razem z rodzicem
            for ch in ob.children:
                if ch.type == "MESH" and not ch.name.startswith("lina_") and not inny(ch) and                         (not pelny or ch.name in DOZWOLONE_DZIECI):
                    Mc = M @ M0.inverted() @ ch.matrix_world
                    h += sprawdz(ch, Mc, v, pelny and ch.name != "rumpel_pod_pokladem")
            if pelny:
                h = przyrost(h, h0)
            stany.append(dict(polozenie=v, kolizje=h))
        wyniki.append(dict(obiekt=ob.name, rodzaj=kind, stany=stany,
                           kolizji=sum(len(s["kolizje"]) for s in stany)))
    return wyniki


def styk_z_pokladem(ctx, nazwy):
    """Najniższy punkt przedmiotu względem pokładu pod nim (luz > 0 – wisi, < 0 – zatopiony)."""
    tree = _podpora(ctx)
    out = []
    for n in nazwy:
        ob = bpy.data.objects.get(n)
        if ob is None or ob.type != "MESH":
            continue
        for (v, t, m, cl) in wyspy(ob):
            low = v[np.argmin(v[:, 2])]
            if low[2] > 4.0 or low[2] < 0.5:
                continue
            x, s = float(low[0]), -float(low[1])
            zs = _wys_podpory(tree, low[0], low[1], low[2])
            if zs is None:
                continue
            gap = float(low[2]) - zs
            # tylko części stojące na pokładzie (najniższy punkt ≤ 5 cm nad nim); wyżej – niesione przez inne części
            if gap < 0.05:
                stan = "styk" if -0.0005 <= gap <= 0.003 else ("wisi" if gap > 0.003 else (
                    "zatopiony" if gap > -0.03 else "przez_poklad"))
                out.append(dict(obiekt=n, material=m, luz_m=round(gap, 4), stan=stan, gdzie=[round(x, 2), round(s, 2)]))
    return out


def scal_bryly(ctx):
    """Bryły składane z nakładających się prymitywów → jedna czysta bryła na obiekt (union). Szyby (materiał 'szklo')
    najpierw do osobnego obiektu '<nazwa>_szklo' (płaska powierzchnia nie jest bryłą). Pomija kadłub (już zamknięty),
    liny i żagle. Każda siatka (także współdzielona przez instancje) tylko raz."""
    import narzedzia as N
    done = set()
    raport = {}
    kolekcje = [ctx["kol"][k] for k in ("kadlub", "rufa_dziob", "drzewca", "olinowanie", "wyposazenie")]
    obs = []
    for c in kolekcje:
        for ob in c.all_objects:
            if ob.type == "MESH" and not ob.name.startswith(("lina_", "zagiel", "zagle")) and ob.name != "kadlub":
                obs.append(ob)
    for ob in obs:
        if ob.data.name in done:
            continue
        done.add(ob.data.name)
        mats = [m.name if m else "" for m in ob.data.materials]
        if "szklo" in mats and len(mats) > 1:
            gi = mats.index("szklo")
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            gl = [f for f in bm.faces if f.material_index == gi]
            if gl:
                me2 = bpy.data.meshes.new(ob.name + "_szklo")
                bm2 = bmesh.new()
                vm = {}
                uvl = bm.loops.layers.uv.active
                uvl2 = bm2.loops.layers.uv.new("UVMap")
                for f in gl:
                    vs = []
                    for v in f.verts:
                        if v.index not in vm:
                            vm[v.index] = bm2.verts.new(v.co)
                        vs.append(vm[v.index])
                    f2 = bm2.faces.new(vs)
                    for l, l2 in zip(f.loops, f2.loops):
                        l2[uvl2].uv = l[uvl].uv
                bm2.to_mesh(me2)
                bm2.free()
                me2.materials.append(bpy.data.materials["szklo"])
                o2 = bpy.data.objects.new(ob.name + "_szklo", me2)
                o2.matrix_world = ob.matrix_world.copy()
                for c in ob.users_collection:
                    c.objects.link(o2)
                if ob.parent is not None:
                    o2.parent = ob.parent
                    o2.matrix_world = ob.matrix_world.copy()
                bmesh.ops.delete(bm, geom=gl, context="FACES")
                bm.to_mesh(ob.data)
            bm.free()
        ok, nm = N.polacz_bryly(ob)
        raport[ob.name] = dict(union=ok, krawedzie_niemanifold=nm)
    ctx["scalanie_bryl"] = raport
    return raport


def macierz_dziala(ctx, g, d):
    """Macierz lawety po odrzucie o d (koła na wypukłym pokładzie, jak w wyposazenie.poza_dziala)."""
    from wyposazenie import poza_dziala
    from mathutils import Euler
    loc, rot = poza_dziala(ctx, g["side"], g["s"], g["xc"] - d)
    return Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4()


def _przeszkody(obs):
    out = []
    for ob in obs:
        for (v, t, m, cl) in wyspy(ob):
            out.append(dict(ob=ob.name, mat=m, v=v, t=t, mn=v.min(0), mx=v.max(0), cl=cl, b=None))
    return out


def _koliduje(ob, M, sts, prog=PROG, dzieci=True):
    M0 = ob.matrix_world
    czesci = [(ob, M)]
    if dzieci:
        czesci += [(ch, M @ M0.inverted() @ ch.matrix_world) for ch in ob.children
                   if ch.type == "MESH" and not ch.name.startswith("lina_")]
    for (o, Mo) in czesci:
        for (v, t, m, cl) in wyspy(o, Mo):
            mnA, mxA = v.min(0), v.max(0)
            bA = None
            for s in sts:
                if np.any(s["mn"] > mxA + prog) or np.any(s["mx"] < mnA - prog):
                    continue
                if bA is None:
                    bA = bvh(v, t)
                if s["b"] is None:
                    s["b"] = bvh(s["v"], s["t"])
                if bA.overlap(s["b"]):
                    d = max(glebokosc(v, s["b"], s["mn"], s["mx"], s["cl"]), glebokosc(s["v"], bA, mnA, mxA, cl))
                    if d > prog:
                        return s["ob"]
    return None


def zbuduj(ctx):
    """Ograniczenia ruchu z geometrii (przed testem chodzenia): największy kąt otwarcia pokrywy furty bez wejścia
    w ławę wantową, puttingi i listwy (pokrywy pod ławą opierają się o nią) i odrzut działa do pierwszej przeszkody
    (kabestan, luki, pompy, nagielbanki) z zapasem 3 cm. Wynik w ctx['ograniczenia_ruchu'] i we właściwościach."""
    K = ctx["K"]
    wynik = dict(pokrywy={}, dziala={})
    pobl = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(
        ("lawy_wantowe", "jufersy", "kadlub_listwy", "rufa_", "kotbelki", "galion", "sztagi_okucia"))]
    sts = _przeszkody(pobl)
    kat = math.radians(K["POKRYWA_KAT"])
    for ob in ctx.get("pokrywy", []):
        Mc = ob.matrix_world @ Matrix.Rotation(-kat, 4, "Z") if ob.get("otwarta") else ob.matrix_world.copy()
        kmax, przez = 0, None
        for a in range(0, 101, 5):
            hit = _koliduje(ob, Mc @ Matrix.Rotation(math.radians(a), 4, "Z"), sts, dzieci=False)
            if hit:
                przez = hit
                break
            kmax = a
        ob["zakres_deg"] = [0, kmax]
        if ob.get("otwarta") and kmax < K["POKRYWA_KAT"]:
            ob.matrix_world = Mc @ Matrix.Rotation(math.radians(kmax), 4, "Z")
        ob["kat_otwarcia_deg"] = min(K["POKRYWA_KAT"], kmax) if ob.get("otwarta") else 0
        wynik["pokrywy"][ob.name] = dict(zakres_deg=[0, kmax], ogranicza=przez)
    U = ctx["PR"].UKLAD["DZIALA"]
    pobl = [o for o in bpy.data.objects if o.type == "MESH" and o.users_collection and
            o.users_collection[0].name in ("wyposazenie", "kadlub") and not o.name.startswith(("dzialo_", "lina_"))
            and o.name not in ("kadlub_stepka", "ster", "kadlub_okucia_steru") and not o.name.startswith("furta_pokrywa_")]
    sts = _przeszkody(pobl)
    for g in ctx.get("dziala", []):
        ob = g["obj"]
        r_ok, przez = 0.0, None
        for d in np.arange(0.05, U["odrzut"] + 1e-6, 0.05):
            hit = _koliduje(ob, macierz_dziala(ctx, g, float(d)), sts)
            if hit:
                przez = hit
                break
            r_ok = float(d)
        if przez:
            r_ok = max(0.0, r_ok - 0.03)
        ob["odrzut_m"] = round(r_ok, 2)
        wynik["dziala"][ob.name] = dict(odrzut_m=round(r_ok, 2), ogranicza=przez)
    ctx["ograniczenia_ruchu"] = wynik
    osadz(ctx)
    return wynik


def zakres_rej(ctx, kmax=35, krok=5):
    """Brasowanie rej w dwóch stanach: reja opuszczona (jak w modelu, żagle zwinięte) i podniesiona do pozycji
    roboczej (przesunięcie wzdłuż osi masztu o 'wysokosc_robocza_dz_m'): największy kąt (≤ kmax) w obie strony bez
    wejścia rei, żagla zwiniętego na niej i jej lin w wanty, sztagi, maszt (po realizacji lin). Rak (dziecko rei)
    obejmuje maszt – jego styk z masztem jest zamierzony. Zapis: reja['zakres_brasowania_deg'] (stan modelu)
    i reja['zakres_brasowania_podniesiona_deg'] (do extras GLB)."""
    obs = [o for o in bpy.data.objects if o.type == "MESH" and (
        o.name.startswith(("lina_wanty", "lina_sztagi", "lina_wyblinki", "lina_paduny", "lina_podwantki", "drzewca",
                           "jufersy", "lina_sciagacze")))]
    sts = _przeszkody(obs)
    wynik = {}

    def zakres(ob, M0, zagle=True):
        for a in range(krok, kmax + 1, krok):
            for sg in (1, -1):
                M = M0 @ Matrix.Rotation(math.radians(sg * a), 4, "Z")
                hit = _koliduje(ob, M, sts, dzieci=False)
                if hit is None:
                    for ch in ob.children:
                        if ch.type != "MESH" or ch.name.startswith(("lina_", "rak_")):
                            continue
                        if not zagle and ch.name.startswith("zagiel_"):
                            continue          # pozycja robocza: żagiel postawiony, nie zwinięty na rei
                        hit = _koliduje(ch, M @ ob.matrix_world.inverted() @ ch.matrix_world, sts, dzieci=False)
                        if hit:
                            break
                if hit:
                    return a - krok, hit
        return kmax, None
    for ob in bpy.data.objects:
        if ob.type != "MESH" or not ob.name.startswith("reja_") or ob.name == "reja_blinda":
            continue
        M0 = ob.matrix_world.copy()
        k0, p0 = zakres(ob, M0)
        dz = float(ob.get("wysokosc_robocza_dz_m", 0.0))
        k1, p1 = zakres(ob, M0 @ Matrix.Translation((0, 0, dz)), zagle=False)
        ob["zakres_brasowania_deg"] = k0
        ob["zakres_brasowania_podniesiona_deg"] = k1
        wynik[ob.name] = dict(opuszczona=dict(zakres_deg=k0, ogranicza=p0),
                              podniesiona=dict(zakres_deg=k1, ogranicza=p1, dz_m=dz))
    ctx.setdefault("ograniczenia_ruchu", {})["reje"] = wynik
    return wynik


def _podpora(ctx):
    """BVH pokładu i ścieku (świat) – podpora przedmiotów stojących."""
    obs = [o for o in (bpy.data.objects.get("kadlub"), bpy.data.objects.get("kadlub_sciek_wregi")) if o]
    vs, ts = [], []
    for o in obs:
        for (v, t_, m, cl) in wyspy(o):
            ts.append(t_ + sum(len(x) for x in vs))
            vs.append(v)
    return bvh(np.concatenate(vs), np.concatenate(ts))


def _wys_podpory(tree, x, y, z):
    hit = tree.ray_cast(Vector((x, y, z + 0.08)), Vector((0, 0, -1)), 0.4)
    return hit[0].z if hit[0] is not None else None


OSADZ = ("wyposazenie_drobne", "szafka_kompasowa", "zejsciowka", "dzwon_rama", "kolo_stojaki", "kabestan_podstawa",
         "nagielbank_fok", "nagielbank_grot", "pompa_L", "pompa_P", "lodz_legary", "luk_glowny", "luk_dziobowy")


def osadz(ctx, luz=0.0015):
    """Spód każdej części stojącej (wyspy, której najniższy punkt jest do 7 cm od podpory) dopasowany do pokładu
    lub ścieku pod nią: wyspa przesunięta na podporę, wierzchołki dolnych 3 cm idą za powierzchnią (wypukłość,
    wznios). Części przechodzące przez pokład (komin, pień pompy, słupki) zostają."""
    tree = _podpora(ctx)
    wyn = {}
    for n in OSADZ:
        ob = bpy.data.objects.get(n)
        if ob is None or ob.type != "MESH":
            continue
        me = ob.data
        M = ob.matrix_world
        Mi = M.inverted()
        nv = len(me.vertices)
        co = np.empty(nv * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        W = co @ np.array(M)[:3, :3].T + np.array(M)[:3, 3]
        ed = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get("vertices", ed)
        par = np.arange(nv)

        def f(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for a, b in ed.reshape(-1, 2):
            ra, rb = f(a), f(b)
            if ra != rb:
                par[ra] = rb
        roots = np.array([f(i) for i in range(nv)])
        zm = 0
        for r in np.unique(roots):
            idx = np.where(roots == r)[0]
            k = idx[np.argmin(W[idx, 2])]
            zs = _wys_podpory(tree, W[k, 0], W[k, 1], W[k, 2])
            if zs is None or not (-0.06 < W[k, 2] - zs < 0.07):
                continue
            low = W[k, 2]
            for i in idx:
                dz = W[i, 2] - low
                if dz < 0.03:
                    zi = _wys_podpory(tree, W[i, 0], W[i, 1], W[i, 2]) or zs
                    W[i, 2] = W[i, 2] + (zi + luz - low) * max(0.0, 1.0 - dz / 0.012)
            zm += 1
        loc = W @ np.array(Mi)[:3, :3].T + np.array(Mi)[:3, 3]
        me.vertices.foreach_set("co", loc.ravel())
        me.update()
        wyn[n] = zm
    ctx["osadzenie"] = wyn
    return wyn


def porzadki(obs):
    """Scalenie zdublowanych wierzchołków (1e-5 m, m.in. środki brył obrotowych), usunięcie ścian o zerowym polu
    i luźnych wierzchołków, normalne na zewnątrz dla brył zamkniętych."""
    stat = dict(scalone=0, zdegenerowane=0, luzne=0)
    done = set()
    for ob in obs:
        if ob.type != "MESH" or ob.data.name in done:
            continue
        done.add(ob.data.name)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        n0 = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        stat["scalone"] += n0 - len(bm.verts)
        f0 = len(bm.faces)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-6)
        zero = [f for f in bm.faces if f.calc_area() < 1e-9]
        if zero:
            bmesh.ops.delete(bm, geom=zero, context="FACES_ONLY")
        stat["zdegenerowane"] += f0 - len(bm.faces)
        le = [e for e in bm.edges if not e.link_faces]
        if le:
            bmesh.ops.delete(bm, geom=le, context="EDGES")
        loose = [v for v in bm.verts if not v.link_faces]
        stat["luzne"] += len(loose)
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        if not ob.name.startswith(("lina_", "zagiel", "zagle")):
            # spójne normalne, potem znak objętości każdej zamkniętej części rozstrzyga kierunek (recalc sam
            # odwracał długie walce rej i części łodzi)
            if not ob.name.startswith("lodz"):      # łódź: poszycie otwarte – kierunek z budowy (do wnętrza)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            import narzedzia as N_
            N_.orientuj_na_zewnatrz(bm)
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
    return stat


ZAKRESY_OPIS = {"furta_pokrywa_": ("obrót wokół lokalnej Z (zawias nad furtą)", "deg"),
                "dzwon": ("wahanie wokół lokalnej Z", "deg")}


def opisz_ruchome(ctx):
    """extras każdej części ruchomej: 'os_ruchu' i 'zakres' (stopnie lub metry) – do gry."""
    for ob in bpy.data.objects:
        n = ob.name
        if ob.type != "MESH":
            continue
        if n.startswith("furta_pokrywa_"):
            ob["os_ruchu"] = "obrót wokół lokalnej Z (zawias nad furtą), dodatni otwiera na zewnątrz"
            ob["zakres_deg"] = list(ob.get("zakres_deg", [0, 100]))
            ob["kat_otwarcia_deg"] = float(ob.get("kat_otwarcia_deg", 0))
        elif n.startswith("reja_") or n in ("gafel", "bom"):
            ob["os_ruchu"] = ("obrót wokół lokalnej Z (oś masztu) – brasowanie; reje: przesunięcie wzdłuż lokalnej Z "
                              "o wysokosc_robocza_dz_m – pozycja robocza (żagiel postawiony)")
            k = float(ob.get("zakres_brasowania_deg", 35))
            ob["zakres_deg"] = [-k, k]
            if "zakres_brasowania_podniesiona_deg" in ob.keys():
                k1 = float(ob["zakres_brasowania_podniesiona_deg"])
                ob["zakres_deg_podniesiona"] = [-k1, k1]
        elif n.startswith("dzialo_") and not n.endswith(("_lufa", "_szklo")) and "odrzut_m" in ob.keys():
            ob["zakres_m"] = [0.0, float(ob["odrzut_m"])]
        elif n.endswith("_lufa"):
            ob["zakres_deg"] = [-5, 10]
        elif n.startswith("ster") or n.startswith("rumpel"):
            if "os_ruchu" not in ob.keys():
                ob["os_ruchu"] = "dziecko steru: obrót razem ze sterem wokół jego osi"
            ob["zakres_deg"] = [-35, 35]
        elif n == "kolo_sterowe" or n == "kabestan_beben" or n.startswith("dzialko_"):
            ob["zakres_deg"] = [0, 360]
            ob["obrot_ciagly"] = True
        elif n.startswith("pompa_") and n.endswith("dzwignia"):
            ob["zakres_deg"] = [-25, 25]
        elif n == "dzwon":
            ob["os_ruchu"] = ob.get("os_ruchu", "wahanie wokół lokalnej Z")
            ob["zakres_deg"] = [-30, 30]


FAZY = ("kadlub_reling", "kadlub_sciek_wregi", "luk_glowny", "luk_dziobowy", "schody_rufowe", "kolo_stojaki",
        "nagielbank_fok", "nagielbank_grot", "kolkownice", "szafka_kompasowa", "zejsciowka")
WAZONE = ("dzialo_",)          # lawety: ważone normalne (instancja 10×; fazy dodałyby ok. 15 tys. trójkątów)


def fazy(ctx, szer=0.006):
    """Fazy 6 mm (1 segment, krawędzie > 40°, utwardzone normalne) na belkach widocznych z pokładu; lawety też
    (wspólna siatka – modyfikator na każdym obiekcie). Stosowane przy eksporcie (export_apply)."""
    n = 0
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        if ob.name.startswith(WAZONE) and not ob.name.endswith(("_lufa", "_szklo")) and "wazone" not in ob.modifiers:
            m = ob.modifiers.new("wazone", "WEIGHTED_NORMAL")
            m.keep_sharp = True
            m.weight = 70
            n += 1
            continue
        if ob.name in FAZY:
            if "fazy" in ob.modifiers:
                continue
            m = ob.modifiers.new("fazy", "BEVEL")
            m.width = szer
            m.segments = 1
            m.limit_method = "ANGLE"
            m.angle_limit = math.radians(40)
            m.harden_normals = True
            n += 1
    return n
