# 11. Budowa statku w CAD albo na papierze

## Po co ten etap

Do zbudowania tego statku nie potrzebujesz Blendera. Każda liczba, z której powstał model 3D, jest w `data/`, a każdy
arkusz w `plans/` narysowano z tych liczb. Ten rozdział pokazuje trzy inne drogi odtworzenia statku:

- **na papierze**, ołówkiem, stalową linijką, cyrklem i listwą krzywikową, tak jak pracowała kreślarnia stoczni;
- **w dowolnym programie CAD** (komputerowe wspomaganie projektowania), darmowym albo komercyjnym, krokami
  niezależnymi od programu;
- **jako model kartonowy albo drewniany** zbudowany na szkielecie wręgów.

Na końcu tego rozdziału będziesz mieć:

- własny plan linii teoretycznych, wygładzony w trzech rzutach, albo wygładzoną powierzchnię kadłuba w CAD;
- pokład, furty, stępkę, dziobnicę, tylnicę, drzewca i (jeśli chcesz) olinowanie ustawione według plików danych;
- krótką listę wymiarów kontrolnych do sprawdzenia pracy z `data/parameters.json` i `data/spars.csv`.

Najpierw przeczytaj [rozdział 02](02-hull-lines-and-offsets.md): wyjaśnia plan linii, tabelę rzędnych i łuki wręgu.
Oznaczenia pewności (z epoki, wtórne, nasz wniosek, model wzorcowy) są objaśnione w
[rozdziale 01](01-ship-type-and-era.md). Większość liczb w tym rozdziale to wartości **modelu wzorcowego** z plików
danych; za każdym razem podajemy nazwę pliku. Model jest jeszcze poprawiany, więc aktualną wartość bierz z pliku.

## Pojęcia

- **Skala**: stosunek rysunku do prawdziwego statku. W skali 1:48 1 mm na papierze to 48 mm na statku.
- **Wręg teoretyczny** (stacja): przekrój kadłuba w ustalonym miejscu wzdłuż statku.
- **Wodnica**: przekrój kadłuba płaszczyzną poziomą. **Przekrój wzdłużny**: przekrój płaszczyzną pionową
  równoległą do osi.
- **Plan wręgów, plan półszerokości, plan boczny**: trzy rzuty planu linii (z przodu, z góry, z boku).
- **Listwa krzywikowa**: cienki, równy pasek drewna albo plastiku wygięty przez punkty, żeby narysować gładką krzywą.
  **Obciążniki** (ang. *ducks*) trzymają ją na miejscu.
- **Gładki** (wygładzony): bez garbów, płaskich miejsc i nagłych zmian krzywizny.
- **Krzywa sklejana** (spline): komputerowa listwa, gładka krzywa przez punkty albo blisko nich.
- **Loft** (wyciągnięcie po przekrojach): w CAD powierzchnia rozpięta na szeregu krzywych przekrojów. (W stoczni
  *lofting* to rysowanie linii w skali 1:1 na podłodze trasowni [1] (wtórne).)
- **Po wręgach** (ang. *moulded*): mierzone do zewnętrznej strony wręgów, bez poszycia. **Po poszyciu**: mierzone
  do zewnętrznej strony desek.
- **Powłoka**: powierzchnia z nadaną grubością, np. poszycie.
- **Wypukłość pokładu**: wygięcie pokładu w górę ku osi. **Wznios pokładu**: podnoszenie się pokładu ku końcom.
- **Wręg modelu** (gródź modelu): płaska deska wycięta w kształt jednego wręgu; szereg takich desek na stępce
  tworzy szkielet modelu.

## Czego potrzebujesz z repozytorium

| Plik | Co daje | Gdzie używany |
|---|---|---|
| `data/offsets.csv` (albo `data/offsets.json`) | kadłub: wręgi, wodnice, wysokości; punkty dziobnicy, tylnicy i pawęży; linie pokładu i relingu | części A, B, C |
| `data/parameters.json` | wymiary główne, wymiary stępki i dziobnicy, grubość poszycia, wypukłość pokładu, położenia i wymiary furt, wyposażenie | wszystkie części, kontrola końcowa |
| `data/spars.csv` | każdy maszt, reja, gafel i drzewce bukszprytu: końce, trzy średnice, wysokości marsów, ezelhoftów i gałek | A.8, B.10, C.5 |
| `data/rigging-lines.json` | każdy odcinek liny jako łamana ze średnicą | A.8, B.11 |
| `data/deck-layout.json` | obrysy pokładów, wzór wysokości pokładu, przeszkody, schody | B.7 |
| `plans/lines-plan.svg` | wygładzony plan linii w skali 1:48 na arkuszu A1 | porównanie z twoim rysunkiem |
| `plans/frame-construction-arcs.svg` | wręg owręża wykreślony trzema łukami w skali 1:25 | A.6 |
| `plans/midship-section.svg`, `plans/hull-profile-structure.svg` | wręg, stępka, kilson i konstrukcja pokładu | B.9, C.2 |
| `plans/deck-plan.svg`, `plans/spar-plan.svg` | układ pokładu 1:80, drzewca 1:150 | A.8 |
| `data/SCHEMA.pl.md` | znaczenie każdej kolumny | zawsze |

## Układ współrzędnych i jednostki

Wszystkie pliki używają metrów i osi statku ([rozdział 02](02-hull-lines-and-offsets.md), `data/SCHEMA.pl.md`):

| Oś | Kierunek | Zero |
|---|---|---|
| s | wzdłuż statku, + ku dziobowi | środek 28,0 m długości pokładu (wrąb dziobnicy na pokładzie s = +14,0) |
| x | w poprzek, + ku lewej burcie | oś statku |
| z | w górę | wodnica konstrukcyjna |

Większość programów CAD ma osie X, Y, Z z Z w górę. Prosty wybór: X w CAD = s (ku dziobowi), Y w CAD = x (ku lewej
burcie), Z w CAD = z. Taki układ zostaje prawoskrętny, jak dane (model wzorcowy, `data/SCHEMA.pl.md`). Zapisz to
przyporządkowanie na pierwszym arkuszu, żeby nikt przez pomyłkę nie odbił statku lustrzanie. Kadłub jest symetryczny:
pliki podają lewą połowę (x ≥ 0), a ty ją odbijasz.

## Część A. Na papierze

### A.1 Wybierz skalę i arkusz

Kadłub ma ok. 29,2 m od głowicy dziobnicy do relingu rufowego. Z bukszprytem i bomstengą cały statek ma ok. 37,5 m:
od końca bomstengi w s = +22,36 (`data/spars.csv`) do szczytu pawęży w s = −15,15 (`transom_centreline`
w `data/offsets.csv`) (nasze obliczenie).

| Skala | Kadłub na papierze | Cały statek z bomstengą | Arkusz na plan linii |
|---|---|---|---|
| 1:48 | 608 mm | 781 mm | A1 (841 × 594 mm), jak `plans/lines-plan.svg` |
| 1:64 | 456 mm | 586 mm | A2 (594 × 420 mm) |
| 1:96 | 304 mm | 391 mm | A3 (420 × 297 mm) |

1:48 to ćwierć cala na stopę. W tej skali są narysowane plany z epoki *Ferret* (1711) i *Swift* (1721) wymienione
w rozdziale 01 [2] (z epoki, plany). Wybierz ją, jeśli możesz. W skali 1:96 linia ołówka 0,5 mm ma już 48 mm na
statku, za grubo do wygładzania (nasz wniosek).

### A.2 Narysuj siatkę

1. Przyklej arkusz płasko. Użyj twardego ołówka (2H albo twardszego) i stalowej linijki.
2. Narysuj **linię bazową** (poziomą linię pod stępką), a nad nią **wodnicę konstrukcyjną** z = 0.
3. Narysuj wodnice co 0,5 m: w skali 1:48 to 10,42 mm. Opisz je −2,5 … +0,5 jak w `data/offsets.csv`.
4. Narysuj **linie wręgów** w położeniach s z pliku: −13,04, −11,04, −8,54, −5,54, −2,54, −0,04, +1,96, +4,46,
   +6,96, +9,46, +11,46, +12,96. Przy końcach leżą gęściej, bo tam kształt zmienia się najszybciej.
5. Narysuj przekroje wzdłużne w x = 1, 2 i 3 m na planie półszerokości i na planie wręgów.
6. **Sprawdź siatkę**: zmierz obie przekątne każdego dużego prostokąta. Jeśli różnią się o więcej niż 0,5 mm,
   siatka nie jest prostokątna; narysuj ją od nowa. Krzywa siatka psuje każdy następny krok.

### A.3 Odczytaj rzędne

`data/offsets.csv` to jedna długa tabela. Wiersze zaczynające się od `#` to komentarze. Do rysunku po wręgach
użyj wierszy z `table = research_moulded`; każdy wiersz podaje wręg (`station_s_m`), czym jest wiersz (`line`)
oraz półszerokość (`half_breadth_m`) albo wysokość (`z_m`). Na przykład wręg owręża s = +1,96 zawiera:

| line | line_value_m | half_breadth_m | z_m | Znaczenie |
|---|---|---|---|---|
| keel_underside | | | −3,10 | spód stępki |
| rabbet | | | −2,85 | miejsce, gdzie poszycie wchodzi w stępkę |
| waterline | −2,0 | 2,93 | −2,0 | półszerokość na wodnicy −2,0 |
| waterline | 0,0 | 3,71 | 0,0 | półszerokość na wodnicy konstrukcyjnej |
| greatest_breadth | | 3,73 | 0,35 | najszersze miejsce wręgu |
| deck_at_side | | 3,70 | 0,90 | krawędź pokładu |
| rail_waist | | 3,51 | 1,95 | wierzch nadburcia w śródokręciu |

Jeśli chcesz rysunek **po poszyciu** (kształt, który widać), użyj zamiast tego `generator_outside_planking`: te same
12 wręgów, ale z półszerokościami na 28 liniach równoległych do wrębu stępki (`line_value_m` to wysokość nad
wrębem). Nie mieszaj dwóch tabel w jednym rysunku: różnią się o poszycie, 0,065 m (model wzorcowy,
`planking_thickness_m` w `data/parameters.json`).

Kilka linijek w Pythonie wypisuje jeden wręg w milimetrach w twojej skali:

```python
import csv
SCALE = 48
rows = [r for r in csv.DictReader(l for l in open("data/offsets.csv", encoding="utf-8") if not l.startswith("#"))
        if r["table"] == "research_moulded" and r["station_s_m"] == "1.96"]
for r in rows:
    hb = r["half_breadth_m"] and "%.1f mm" % (float(r["half_breadth_m"]) * 1000 / SCALE)
    z = r["z_m"] and "%.1f mm" % (float(r["z_m"]) * 1000 / SCALE)
    print(r["line"], r["line_value_m"], hb, z)
```

### A.4 Nanieś trzy rzuty

1. **Plan boczny.** Nanieś spód stępki i wrąb na każdym wręgu. Dziobnicę nanieś z wierszy `stem_rabbet`, tylnicę
   z `sternpost_rabbet` (pięta w s = −13,10, pochylenie 11,4° od pionu). Linię pokładu nanieś z `deck_at_side`,
   reling z `rail_top`.
2. **Plan wręgów.** Dla każdego wręgu zaznacz półszerokość na każdej wodnicy, największą szerokość, pokład
   i reling. Zwyczajowo wręgi rufowe idą na lewą połowę, a dziobowe na prawą.
3. **Plan półszerokości.** Dla każdej wodnicy przenieś cyrklem półszerokości wszystkich wręgów. Dodaj linię
   pokładu (półszerokości w `deck_at_side`) i pawęż (`transom_half_breadth`).

### A.5 Wygładź listwą

1. Przypnij albo obciąż listwę na punktach jednej wodnicy na planie półszerokości.
2. Pozwól listwie samej znaleźć krzywą. Gdzie nie przejdzie przez punkt bez załamania, zostaw punkt.
3. **Przesuń punkt, nie listwę.** Popraw ten sam punkt na planie wręgów, żeby oba rzuty się zgadzały.
4. Narysuj przekroje wzdłużne na planie bocznym z planu półszerokości i planu wręgów i wygładź je tak samo.
5. Dopuść do 1 mm różnicy na papierze w skali 1:48 (ok. 50 mm na statku) między rzutami (nasz wniosek, jak
   w rozdziale 02).

### A.6 Wykreśl wręg łukami

Dawne wręgi rysowano łukami okręgów, a nie krzywą przez punkty ([rozdział 02](02-hull-lines-and-offsets.md)). Arkusz
`plans/frame-construction-arcs.svg` wykreśla wręg owręża w skali 1:25 trzema łukami i podaje wszystkie liczby
(model wzorcowy; promienie metody to nasz wniosek):

| Element | Wartość (m, po wręgach) |
|---|---|
| Punkt początkowy na stępce R0 | (0,13; −2,85) |
| Podniesienie dna | 12° do głowicy dennika F (2,20; −2,41) |
| Łuk dna | promień R_f = 1,42, styczny do linii podniesienia w F |
| Łuk szerokości | promień R_b = 3,92, styczna pionowa w B (3,73; 0,35) |
| Punkt styku obu łuków | T (3,08; −1,80) |
| Łuk wierzchołków | promień R_u = 5,93, od B do punktu relingu N (3,51; 1,95) |

Narysuj go cyrklem drążkowym. Potem sprawdź: tam, gdzie twoje łuki przecinają wodnice, muszą zgadzać się
z półszerokościami wręgu owręża w `data/offsets.csv` z dokładnością 0,05 m (model wzorcowy). Zrób to samo dla jednego
wręgu dziobowego i jednego rufowego, biorąc ich promienie z tabeli B rozdziału 02.

### A.7 Sprawdź zgodność trzech rzutów

- Każdy punkt (przecięcie wodnicy z wręgiem, przekroju wzdłużnego z wodnicą) leży w tym samym s, x i z we
  wszystkich trzech rzutach.
- Wodnice z góry: gładkie, dziób pełniejszy niż rufa.
- Przekroje wzdłużne z boku: gładkie, wznoszą się ku obu końcom.
- Jedna diagonala przez obło (rozdział 02): bez wklęśnięć i garbów.
- Po wygładzeniu **zapisz poprawione rzędne**. Teraz prawdą jest wygładzony rysunek.

### A.8 Pokład, furty, drzewca i olinowanie na papierze

- **Furty**: środki w s = −3,79, −1,34, +1,11, +3,56, +6,01, +8,46, furta zamknięta w −6,24; otwór 0,60 szeroki,
  próg 0,32 i nadproże 0,82 nad pokładem (`gunport_*` w `data/parameters.json`, grupa `decks`).
- **Drzewca**: dla każdego wiersza `data/spars.csv` narysuj na planie bocznym linię od (`start_s_m`, `start_z_m`)
  do (`end_s_m`, `end_z_m`) i zaznacz szerokości `d_max_m`, `d_mid_m`, `d_end_m`. Reje widziane z boku to krótkie
  kreski na swojej wysokości; w pełnej długości narysuj je w rzucie z przodu (x i z).
- **Olinowanie**: każdy odcinek z `data/rigging-lines.json` rysuj od `from` przez `via` do `to`, z boku (s, z) albo
  z przodu (x, z). Najpierw sztagi i wanty; 456 wyblinek (`data/rigging-summary.csv`) zostaw na koniec.

## Część B. W dowolnym programie CAD

Poniższe kroki działają w każdym programie, który ma krzywe sklejane 3D i loft (zwany też „przez przekroje” albo
„skin”). Nazwy poleceń są różne, idea ta sama.

### B.1 Przygotowanie

1. Ustaw jednostki na metry (albo milimetry i każdą wartość pomnóż przez 1000).
2. Wybierz przyporządkowanie osi z części „Układ współrzędnych i jednostki” i trzymaj się go.
3. Zrób jedną warstwę albo grupę na każdy element: siatka, wręgi, profil, powierzchnia kadłuba, pokład, drzewca,
   olinowanie.

### B.2 Krzywe wręgów z rzędnych

1. Dla każdego wręgu zrób listę punktów (x, z) z `research_moulded` (albo `generator_outside_planking`), od stępki
   w górę: wrąb, linia brodaty, punkty wodnic, największa szerokość, pokład, reling.
2. Umieść każdą listę w płaszczyźnie jej wręgu (X w CAD = s).
3. Przez każdą listę poprowadź **interpolującą krzywą sklejaną** (stopnia 3). Nie łącz punktów odcinkami prostymi:
   12 wręgów połączonych odcinkami daje widoczne fasety (rozdział 02, typowe błędy).

### B.3 Krzywe profilu

1. Narysuj wrąb dziobnicy przez punkty `stem_rabbet` w płaszczyźnie symetrii.
2. Narysuj wrąb tylnicy jako odcinek od pięty (s = −13,10, z = −3,119) do punktu (s = −13,981, z = 1,25)
   (`sternpost_rabbet` w `data/offsets.csv`).
3. Narysuj obrys pawęży z `transom_half_breadth` (półszerokość na wysokości z) w płaszczyźnie pawęży, pochylonej
   jak tylnica.
4. Narysuj linię wrębu stępki z = −2,885 + 0,017857 · s (`keel_rabbet_z_at_s0_m`, `keel_drag_per_m`).

### B.4 Loft kadłuba

1. Rozepnij gładką (nie prostokreślną) powierzchnię na krzywych wręgów, od pawęży do dziobnicy.
2. Użyj krzywych profilu jako prowadnic, jeśli program na to pozwala; w przeciwnym razie dodaj po jednym przekroju
   na każdym końcu.
3. Odbij powierzchnię lustrzanie względem płaszczyzny symetrii.

### B.5 Sprawdź gładkość

1. Przetnij powierzchnię płaszczyznami wodnic i przekrojów wzdłużnych. Porównaj przekroje z wartościami w pliku
   (i z tabelami A i C rozdziału 02).
2. Włącz **grzebień krzywizny** na każdym przekroju. Grzebień musi zmieniać się płynnie i nie zmieniać znaku,
   z wyjątkiem zamierzonego wklęśnięcia przy stępce.
3. Włącz pasy „zebry” (linie odbicia), jeśli program je ma. Pasy muszą biec gładkimi wstęgami.
4. Jeśli coś jest źle, popraw **punkty** wręgu i zrób loft jeszcze raz. Nie popychaj powierzchni ręcznie.

### B.6 Grubość poszycia

- Powierzchnia po wręgach to zewnętrzna strona wręgów. Poszycie dodaje 0,065 m na dnie (model wzorcowy,
  `planking_thickness_m`); berghołty wystają z niego o 0,02–0,06 m (`wales_from_to_projection_m`).
- Albo odsuń powierzchnię po wręgach o 0,065 m na zewnątrz, albo zrób loft wprost z tabeli
  `generator_outside_planking`. Drugi sposób stosuje model wzorcowy; poszycie zanika w nim do zera przy dejwudzie
  (model wzorcowy).
- Do modelu bryłowego pogrub powierzchnię do środka (powłoka). Do rysunków zostaw ją jako powierzchnię.

### B.7 Pokład z wypukłością i wzniosem

Wysokość pokładu w dowolnym punkcie (model wzorcowy, `data/deck-layout.json`):

z = centreline_z(s) − 0,120 · (x / 3,80)²

`centreline_z(s)` jest w pliku co 0,5 m (np. 1,025 m na owrężu, nasz odczyt z listy); pokład rufowy jest 1,70 m
wyżej, od s = −5,04 ku rufie (`quarterdeck_break_s_m`, `quarterdeck_height_above_main_deck_m`). Zbuduj pokład jako
powierzchnię rozpiętą na tych łukach, a potem przytnij ją wewnętrzną stroną nadburcia (`polygon_x_s` pokładu
w `data/deck-layout.json`).

### B.8 Furty

Wytnij każdą furtę jako prostopadłościan: 0,60 m wzdłuż statku, od progu 0,32 m do nadproża 0,82 m nad pokładem przy
burcie, przez nadburcie (`gunport_*`). Boki otworu zostają pionowe; próg idzie za wzniosem.

### B.9 Stępka, dziobnica i tylnica

| Element | Wymiar (model wzorcowy, `data/parameters.json`, grupa `hull`) |
|---|---|
| Stępka | 0,26 szerokości (w poprzek), 0,31 pod wrębem (stępka 0,25 + stępka fałszywa 0,06) |
| Dziobnica | 0,26 szerokości u stopy, 0,40 u głowicy; 0,35 grubości przed wrębem |
| Tylnica | 0,40 grubości za wrębem u pięty, 0,28 u głowicy |
| Odstęp wręgów (room and space) | 0,52 |

Przeciągnij prostokąt tych wymiarów wzdłuż linii wrębu. Rozdział 03 objaśnia te części.

### B.10 Drzewca

Dla każdego wiersza `data/spars.csv`: narysuj oś od początku do końca, ustaw okręgi o średnicy `d_max_m`
w najgrubszym miejscu, `d_mid_m` w środku i `d_end_m` na końcu, i zrób przez nie loft. Reje dolne i marsrei są
w środku ośmiokątne (z epoki, [rozdział 05](05-masts-and-spars.md)). Marsy, ezelhofty i salingi idą na wysokości
`top_platform_z_m`, `cap_z_m`, `crosstrees_z_m`. Reje są podane opuszczone; `hoisted_z_m` daje wysokość roboczą.

### B.11 Olinowanie

Każdy odcinek w `data/rigging-lines.json` to łamana (`from`, `via`, `to`) ze średnicą `diameter_m`. Przeciągnij
wzdłuż niej okrąg o tej średnicy. W chwili pisania jest 1317 odcinków 836 lin (`counts` w pliku); zacznij od grup
`stays`, `main_shrouds`, `fore_shrouds` i `backstays` (`data/rigging-summary.csv`). `ratlines` i `coils` zostaw
na koniec.

### Uwagi o kilku darmowych narzędziach

| Narzędzie | Do czego dobre | Uwaga |
|---|---|---|
| FreeCAD | pełne 3D: krzywe sklejane, loft, powłoka, operacje logiczne | darmowy, otwarty, parametryczny [3] |
| FREE!ship | powierzchnie kadłuba i hydrostatyka | GPL v2, powierzchnie podziałowe zamiast NURBS, Windows [4] |
| LibreCAD | plan linii i plan wręgów w 2D | GPL v2, tylko 2D [5] |
| Inkscape | odrysowywanie i edycja arkuszy SVG z `plans/` | GPL, SVG to jego własny format [6] |

Skrypty, z których powstały arkusze w `plans/`, zapisują SVG w milimetrach arkusza, więc arkusz otwiera się
w edytorze wektorowym w prawdziwym rozmiarze papieru (model wzorcowy). Nie bierz wymiarów z kopii PNG: piksele nie
są w skali.

## Część C. Model kartonowy albo drewniany na szkielecie

Modelarze budują puste kadłuby na dwa częste sposoby: **poszycie na grodziach** (wycięte deski w poprzek stępki,
potem poszycie) i **poszycie na wręgach** (najpierw stępka, dziobnica i tylnica, potem prawdziwe wręgi, potem deski,
jak na prawdziwym statku) [7] (wtórne). Modele kartonowe mają ten sam szkielet, pokryty paskami albo płatami papieru.

### C.1 Szablony z wręgów

1. Wybierz skalę (1:48 daje kadłub 608 mm; 1:96 daje 304 mm, dobre do kartonu).
2. Narysuj każdy wręg planu wręgów w pełnej wielkości w twojej skali (część A, albo wydrukuj z rysunku CAD).
3. **Odejmij poszycie.** Wręgi modelu stoją wewnątrz poszycia. Narysuj każdy szablon wewnątrz linii po wręgach
   o grubość twojego poszycia w skali modelu (np. listewka 1,5 mm w 1:48), a nie o prawdziwe 0,065 m.
4. Dodaj wręgi, jeśli odstęp jest za duży dla twojego poszycia: karton potrzebuje podparcia co 30–50 mm na modelu,
   listewka drewniana co 50–80 mm (nasz wniosek). Nowe wręgi interpoluj z wygładzonego rysunku, nie z tabeli.
5. Na dole każdego szablonu wytnij wpust na stępkę i zaznacz linię pokładu z `deck_at_side`.

### C.2 Stępka i składanie

1. Wytnij deskę stępki według planu bocznego: na dole linia wrębu, na górze linia pokładu, z wpustami przy każdym
   wręgu.
2. Wklej wręgi prostopadle do stępki. Sprawdź z góry, czy stoją pod kątem prostym do niej, a z przodu, czy każdy jest
   pionowy.
3. Połóż cienką listwę wzdłuż wręgów (jak w A.5). Gdzie nie dotyka wręgu, szablon jest zły; szlifuj albo podklejaj,
   aż listwa leży gładko na wszystkich.

### C.3 Poszycie, pokład, drzewca

- **Drewno**: poszywaj od stępki w górę i od linii wzniosu w dół; deski zwężają się ku dziobowi.
- **Karton**: klej paski albo wycięte płaty; zakładki na wręgach.
- **Pokład**: arkusz kartonu albo forniru wygięty na pokładnikach z wypukłością (0,12 m przy półszerokości 3,8 m,
  model wzorcowy).
- **Drzewca** z `data/spars.csv` w skali: grotmaszt ma 17,80 m długości i 0,494 m grubości w opętniku, więc w skali
  1:48 ma 371 mm długości i 10,3 mm grubości (nasze obliczenie).
- **Liny**: w skali 1:48 wanta grota 49 mm to 1,0 mm, a wyblinka 10 mm to 0,2 mm (nasze obliczenie). Nici cieńsze
  niż ok. 0,1 mm trudno obrabiać; weź najcieńsze, jakie dasz radę, a wyblinki niech będą lżejsze niż wanty.

## Sprawdzenie wyniku z danymi

Zmierz te wielkości na rysunku, w modelu CAD albo na modelu i porównaj z plikami.

| Sprawdzenie | Wartość (model wzorcowy) | Plik i klucz |
|---|---|---|
| Długość pokładu między wrębami | 28,0 m (wrąb dziobnicy na pokładzie s = +14,0, tylnica s = −14,0) | `data/SCHEMA.pl.md` |
| Szerokość po wręgach / po poszyciu | 7,46 / 7,60 m | rozdział 01; `offsets.csv` (największa półszerokość po wręgach 3,73) |
| Wrąb stępki w s = 0 | z = −2,885 | `parameters.json`, `keel_rabbet_z_at_s0_m` |
| Spód stępki na owrężu | z = −3,10 | `offsets.csv`, `keel_underside` w s = +1,96 |
| Pokład przy burcie na owrężu | z = 0,90 | `offsets.csv`, `deck_at_side` |
| Wypukłość pokładu | 0,12 m przy półszerokości 3,80 m | `parameters.json`, `deck_camber_m`, `camber_reference_half_breadth_m` |
| Pokład rufowy | 1,70 m nad pokładem głównym, od s = −5,04 ku rufie | `parameters.json`, grupa `decks` |
| Progi furt nad wodą | ok. 1,22–1,50 m | rozdział 02 (zmierzone w modelu) |
| Fokmaszt / grotmaszt na pokładzie | s = +10,08 / −1,40 | `spars.csv`, `deck_s_m` |
| Mars grota, ezelhoft grota, gałka grota | z = 13,22 / 15,39 / 28,84 | `spars.csv`, `main_mast`, `main_topgallant_mast` |
| Reja grota | 15,82 m długości, 0,308 m w stropach | `spars.csv`, `main_yard` |
| Wznios bukszprytu | 30° | `spars.csv`, `bowsprit`, `angle_deg` |

Dopuść 1 mm na papierze w skali 1:48 (ok. 50 mm na statku); w CAD 10 mm (nasz wniosek). Jeśli wartość bardzo się
różni, szukaj najpierw odbitej osi, złej jednostki (milimetry odczytane jako metry) albo pomieszanych tabel po
wręgach i po poszyciu.

## Przykład policzony: wręg owręża w skali 1:48

1. Weź wiersze owręża z `research_moulded` (A.3).
2. Każdą wartość w metrach podziel przez 48 i pomnóż przez 1000, żeby dostać milimetry na papierze (nasze
   obliczenie):

| Punkt | Statek (m) | Papier w 1:48 (mm) |
|---|---|---|
| Wrąb | x 0,13, z −2,85 | x 2,7, z −59,4 |
| Wodnica −2,0 | x 2,93 | x 61,0 |
| Wodnica 0 | x 3,71 | x 77,3 |
| Największa szerokość | x 3,73, z 0,35 | x 77,7, z 7,3 |
| Pokład przy burcie | x 3,70, z 0,90 | x 77,1, z 18,8 |
| Reling | x 3,51, z 1,95 | x 73,1, z 40,6 |

3. Nanieś punkty na linię wręgu na planie wręgów, mierząc od osi (x) i od wodnicy konstrukcyjnej (z).
4. Wykreśl wręg trzema łukami z A.6, przeskalowanymi tak samo (R_f = 29,6 mm, R_b = 81,7 mm, R_u = 123,5 mm).
5. Łuki muszą przejść w odległości do 1 mm od punktów. Jeśli tak jest, wręg i tabela się zgadzają.

## Sprawdź się

- [ ] Zapisałem, która oś CAD to s, x i z, i statek nie jest odbity (lewa burta to +x).
- [ ] Użyłem albo tabeli po wręgach, albo tabeli po poszyciu, nie obu naraz.
- [ ] Siatka jest prostokątna (przekątne w granicach 0,5 mm).
- [ ] Każdy punkt leży w tym samym miejscu we wszystkich trzech rzutach (1 mm w skali 1:48).
- [ ] Przekroje mojej powierzchni wodnicami i przekrojami wzdłużnymi są gładkie i zgadzają się z plikiem do 50 mm.
- [ ] Wypukłość pokładu 0,12 m, pokład rufowy 1,70 m wyżej od s = −5,04.
- [ ] Maszty stoją w s = +10,08 i −1,40; gałka grota jest ok. 28,8 m nad wodą.
- [ ] Moje wymiary kontrolne zgadzają się z tabelą wyżej.

## Typowe błędy

1. Łączenie punktów rzędnych odcinkami zamiast listwą albo krzywą sklejaną.
2. Mieszanie rzędnych po wręgach i po poszyciu, przez co kadłub jest miejscami o 0,065 m za szeroki albo za wąski.
3. Odbicie statku: lewa burta narysowana jako prawa, bo oś Y w CAD wzięto ku prawej burcie.
4. Branie wymiarów z PNG zamiast z SVG albo z danych.
5. Ręczne wygładzanie powierzchni w CAD, aż przestaje zgadzać się z liczbami.
6. Wręgi modelu wycięte po linii po wręgach, przez co poszycie robi kadłub za dużym.
7. Grubości lin przeniesione bezmyślnie w skali: w małej skali cienkie znikają, a grube wyglądają jak kable.

## Źródła

1. Wikipedia, „Lofting” https://en.wikipedia.org/wiki/Lofting (CC BY-SA). Rysunek w skali 1:1, listwy, trasownia.
2. Royal Museums Greenwich, plan ZAZ4877 *Ferret* (1711) i plan ZAZ4853 *Swift* (1721), oba 1:48, jak w źródłach
   [rozdziału 01](01-ship-type-and-era.md) (tylko do oglądania, warunki licencji RMG). Skali innych zbiorów nie
   sprawdzaliśmy.
3. FreeCAD https://www.freecad.org/ (darmowy, otwarty, parametryczny program 3D).
4. FREE!ship, SourceForge https://sourceforge.net/projects/freeship/ (GPL v2; powierzchnie podziałowe, hydrostatyka).
5. LibreCAD https://librecad.org/ (darmowy, otwarty CAD 2D, GPL v2).
6. Wikipedia, „Inkscape” https://en.wikipedia.org/wiki/Inkscape (darmowy edytor wektorowy, GPL, SVG jako format
   własny).
7. Wikipedia, „Ship model” https://en.wikipedia.org/wiki/Ship_model (CC BY-SA). Poszycie na grodziach, poszycie na
   wręgach.

## Terminy użyte w rozdziale

| Angielski | Polski | Objaśnienie |
|---|---|---|
| scale | skala | Stosunek rysunku do statku. |
| station, theoretical frame | wręg teoretyczny | Przekrój w ustalonym miejscu wzdłuż statku. |
| waterline, buttock | wodnica, przekrój wzdłużny | Przekroje poziomy i pionowy wzdłużny. |
| body plan, half-breadth plan, sheer plan | plan wręgów, plan półszerokości, plan boczny | Trzy rzuty planu linii. |
| batten, ducks | listwa krzywikowa, obciążniki | Listwa do gładkich krzywych i ciężarki, które ją trzymają. |
| fair, fairing | gładki, wygładzanie | Bez garbów; nadawanie krzywej gładkości. |
| spline | krzywa sklejana (spline) | Gładka krzywa komputerowa przez punkty. |
| loft | wyciągnięcie po przekrojach (loft) | Powierzchnia rozpięta na szeregu przekrojów. |
| curvature comb | grzebień krzywizny | Wykres krzywizny wzdłuż krzywej. |
| moulded, outside planking | po wręgach, po poszyciu | Mierzone do wręgów; do zewnętrznych desek. |
| shell (thickness) | powłoka (z grubością) | Powierzchnia z nadaną grubością. |
| camber, sheer | wypukłość pokładu, wznios pokładu | Wygięcie pokładu w poprzek i wzdłuż. |
| bulkhead (model) | wręg modelu (gródź modelu) | Deska w kształcie wręgu w szkielecie modelu. |
| plank-on-bulkhead, plank-on-frame | poszycie na grodziach, poszycie na wręgach | Dwa sposoby budowy kadłuba modelu. |
