# 12. Projektowanie innych statków na tym wzorze

## Po co ten etap

Model wzorcowy to jeden statek: snow z ok. 1710 r., 28,0 m na pokładzie i 7,60 m szerokości. Reguły, z których
powstał, są ogólne. Zmień kilka liczb, a te same reguły dadzą slup, kecz, szkuner, późniejszy bryg albo mały
trójmasztowiec. Zmień datę, a niektóre części muszą zmienić się razem z nią.

Ten rozdział mówi:

- które parametry zmieniać i co wynika z każdego z nich;
- czym główne odmiany ożaglowania różnią się od modelu wzorcowego;
- co się zmienia, gdy przesuniesz datę o kilkadziesiąt lat w jedną albo w drugą stronę;
- co trzeba sprawdzić po każdej zmianie: działa, wysokość pod pokładem, zanurzenie, równowagę żaglową, brasowanie,
  kolizje lin;
- dwa pełne przykłady policzone: slup ok. 21 m i trójmasztowiec ok. 32 m.

Oba przykłady to **nasz wniosek**: zastosowaliśmy reguły z rozdziałów 01, 02 i 05 do nowych wymiarów głównych. To
punkty wyjścia do własnego projektu, a nie rekonstrukcje prawdziwych statków. Oznaczenia pewności (z epoki, wtórne,
nasz wniosek, model wzorcowy) są objaśnione w [rozdziale 01](01-ship-type-and-era.md).

## Pojęcia

- **Parametr**: jedna liczba, z której buduje się projekt (długość pokładu, szerokość, położenie masztu, data).
- **Reguła proporcji**: reguła z epoki albo współczesna, która daje jeden wymiar z innego, np. grotmaszt z długości
  i szerokości pokładu.
- **Wariant**: ten sam kadłub z innym ożaglowaniem, sterowaniem, malowaniem albo położeniem łodzi. W
  `data/parameters.json` grupa `variants` zawiera przełączniki modelu wzorcowego.
- **Środek ożaglowania** (ang. *centre of effort*, CE): punkt, w którym działa wypadkowa siła wiatru na żagle.
  Przyjmujemy go jako środek pola wszystkich żagli narysowanych płasko w rzucie z boku.
- **Środek bocznego oporu** (ang. *centre of lateral resistance*, CLR): punkt, w którym woda opiera się
  spychaniu statku w bok. Przyjmujemy go jako środek pola podwodnego obrysu burty.
- **Wyprzedzenie** (ang. *lead*): o ile CE leży przed CLR, zwykle w procentach długości wodnicy.
- **Zakres brasowania**: o ile reja może obrócić się wokół masztu, zanim dotknie wanty, sztagu albo innej rei.
- **Wyporność**: masa wody wypartej przez kadłub, równa masie statku.

## Łańcuch liczb

Każdy wymiar modelu wzorcowego wynika z kilku liczb, w tej kolejności (model wzorcowy; reguły w rozdziałach 01, 02
i 05):

1. **Typ i data** decydują o ożaglowaniu, rufie, galionie i sterowaniu (rozdział 01).
2. **Długość pokładu L** i **szerokość B** decydują o głębokości ładowni, długości stępki i tonażu (rozdział 01).
3. **Liczby kształtu** (podniesienie dna, wznios, zawał burt, położenie owręża) decydują o wręgach i rzędnych
   (rozdział 02).
4. **Rozstaw furt** i długość śródokręcia decydują o liczbie dział (rozdziały 01 i 04).
5. **L i B** decydują o grotmaszcie, M = (L + B) / 2; wszystkie inne maszty i reje wynikają z M (rozdział 05).
6. **Średnice masztów** decydują o grubości lin: grotsztag to ok. 1/6 średnicy grotmasztu, wanty i talrepy wynikają
   ze sztagu (rozdział 06, źródła wtórne, nasz wniosek).
7. **Reje i wysokości** decydują o żaglach (rozdział 08), a żagle o równowadze (ten rozdział).

Zmiana na górze biegnie więc aż na dół. Zmiana na dole (dłuższa bomstenga, przesunięty maszt) może zepsuć
sprawdzenie wyżej, np. równowagę żaglową.

## Które parametry zmieniać

| Parametr (`data/parameters.json`) | Wartość wzorcowa | Co z niego wynika | Rozdział |
|---|---|---|---|
| długość pokładu L (28,0 m, `data/SCHEMA.pl.md`) | 28,0 m | stępka, tonaż, liczba furt, długości masztów | 01, 02, 05 |
| szerokość B (rozdział 01) | 7,60 m po poszyciu | głębokość ładowni, tonaż, długości masztów, szerokość pokładu na działa | 01, 05 |
| `keel_drag_per_m`, `keel_rabbet_z_at_s0_m` | przegłębienie 0,40 m na długości stępki | zanurzenie na dziobie i rufie | 02 |
| `deck_at_side_s_z_m`, `deck_camber_m` | wznios 0,95 m na dziobie, 0,45 m na rufie; wypukłość 0,12 m | progi furt, wolna burta, powierzchnia do chodzenia | 02, 04 |
| `quarterdeck_break_s_m`, `quarterdeck_height_above_main_deck_m` | −5,04 m; 1,70 m | wysokość pod pokładem na rufie, miejsce na grotmaszt i schody | 04 |
| `gunport_centres_s_m` | 6 otwartych par co 2,45 m | działa, ławy wantowe, puttingi, miejsce na kabestan | 04, 09 |
| `fore_mast_s_at_deck_m`, `main_mast_s_at_deck_m` | +10,08, −1,40 | równowaga żaglowa, luki, kabestan, sztagi | 05 |
| `snow_rig`, `has_boom` (grupa `variants`) | snow, bez bomu | żagiel gaflowy na maszcie snow albo na grotmaszcie | 05, 08 |
| `steering_drive` | koło (rumpel jako wariant) | urządzenie sterowe, stanowiska na rufie | 09 |
| `bowsprit_steeve_deg` | 30° | wysokość bomstengi, żagle przednie, prowadzenie foksztagu | 05, 06 |

Zmieniaj jedną grupę naraz i po każdej zmianie wykonaj sprawdzenia z tego rozdziału.

## Reguły proporcji w jednym miejscu

| Wielkość | Reguła | Pewność i źródło |
|---|---|---|
| Długość pokładu / szerokość | 3,1–3,3 dla slupów z lat 1710–1720; 3,5–3,7 dla slupów-snow z lat 40. XVIII w. | nasz wniosek z danych wtórnych, rozdział 01 |
| Głębokość ładowni | 0,40–0,45 B (slupy); 0,32 dla 20-działowca z 1719 r. | nasz wniosek, rozdział 01; wtórne [1] |
| Stępka | 0,77–0,84 długości pokładu | nasz wniosek, rozdział 01 |
| Tonaż (tons burthen) | K × B × (B/2) / 94 (stopy) | wtórne, rozdział 02 |
| Wyporność | Δ = 1,025 · Cb · L_wl · B_wl · T; Cb ok. 0,50 dla tego kadłuba | standard, rozdział 02; model wzorcowy |
| Rozstaw furt | ok. 2,3–2,6 m między środkami | nasz wniosek z danych wtórnych, rozdział 01 |
| Grotmaszt | M = (L + B) / 2, od pięty do ezelhoftu | z epoki (Steel 1794) [2], rozdział 05 |
| Fokmaszt | 8/9 M | z epoki [2] |
| Bezanmaszt (trójmasztowce) | 6/7 M | z epoki [2] |
| Stengi | grot 3/5 M; fok 8/9 grotstengi; bezan 3/4 grotstengi | z epoki [2] |
| Bramstengi | 1/2 stengi | z epoki [2], rozdział 05 |
| Reja grota | 8/9 M; reja foka 7/8 rei grota | z epoki [2] |
| Marsreje | grot 5/7 rei grota; fok 7/8 grotmarsrei | z epoki [2] |
| Reja bezanowa krojcel (trójmasztowce) | = fokmarsreja | z epoki [2] |
| Reja bezanu (łacińska) | 6/7 rei grota | z epoki [2] |
| Bukszpryt, bomstenga | 3/5 M; bomstenga ok. 5/7 bukszprytu | z epoki [2], rozdział 05 |
| Bom i gafel slupu | bom 2/3 swojego masztu; gafel 3/5 bomu | z epoki [2], rozdział 05 |
| Średnice | 1 cal na jard długości (1/36) dla masztów; 0,7 cala na jard dla rej dolnych | z epoki [2], rozdział 05 |
| Położenie masztów, okręt | fok 1/9, grot 5/9, bezan 17/20 długości pokładu od dziobnicy | z epoki [2], rozdział 05 |
| Grotsztag | ok. 1/6 średnicy grotmasztu | wtórne, rozdział 06 |

Steel wydrukował te reguły w **1794 r.**, ok. 80 lat po naszej dacie. Rozdział 05 wyjaśnia, dlaczego mimo to z nich
korzystamy i gdzie wcześniejsze reguły się różnią.

## Odmiany ożaglowania

| Odmiana | Co się zmienia względem wzorcowego snow | Najwcześniejsza bezpieczna data | Pewność i źródło |
|---|---|---|---|
| **Bryg z bomem** (późniejszy bryg) | bez masztu snow; gafel i bom na samym grotmaszcie; `snow_rig = false`, `has_boom = true` | ok. 1770 dla nazwy i ożaglowania w ścisłym sensie | zapisy z epoki przez opracowanie, rozdział 01 [3] |
| **Brygantyna** | fokmaszt z rejami; grotmaszt tylko z żaglem gaflowym i małymi marslami | ok. 1695 | z epoki, rozdział 01 [3] |
| **Slup** (jeden maszt) | jeden maszt z grotżaglem gaflowym, sztakslem i kliwrem; większe z marslem | przed 1700 | z epoki, rozdział 01 [3] |
| **Kecz** | wysoki grotmaszt i krótki bezan, bez fokmasztu; bezan stoi przed głowicą steru | XVII w.; marynarki używały keczy jako bombard i małych slupów | z epoki, rozdział 01 [3]; wtórne [4] |
| **Szkuner** | dwa maszty z żaglami gaflowymi, możliwe małe marsle | holenderskie obrazy z początku XVII w.; rozwój w Ameryce Brytyjskiej od ok. 1713 | wtórne [5] |
| **Mały trójmasztowiec** (VI ranga) | trzy maszty, żagle rejowe na foku i grocie, łaciński bezan; jeden pokład działowy | 20-działowce ustalenia z 1719 r. | wtórne [1]; bezan: wtórne [6] |

Uwagi dla modelarza (nasz wniosek):

- **Bryg z bomem** potrzebuje miejsca na bom nad pokładem rufowym. W modelu wzorcowym szczęki bomu byłyby 3,95 m nad
  pokładem głównym (`boom_jaws_above_main_deck_m`); sprawdź, czy bom mija głowy na pokładzie rufowym, który jest
  1,70 m wyżej.
- **Kecz** nie ma fokmasztu, więc grotmaszt przesuwa się do przodu, mniej więcej tam, gdzie równoważyłyby się fok
  i grot snow. Policz równowagę żaglową od nowa; bezan przesuwa CE do tyłu.
- **Szkuner** z 1710 r. jest w angielskiej marynarce rzadki. Używaj go dla kupców i żeglugi przybrzeżnej w koloniach.
- W **trójmasztowcu** reja bezanu u Steela to w naszej epoce długa, ukośna reja (łacińska). Kiedy zastąpił ją
  bezan gaflowy, nasze źródła nie rozstrzygają: jedno źródło umieszcza zmianę na początku XIX w. [6] (wtórne).
  Dla 1710 r. zostaw reję łacińską.

## Przesunięcie daty

| Cecha | Wcześniej, ok. 1680–1700 | Wzorzec, ok. 1710 | Później, ok. 1740–1770 | Pewność i źródło |
|---|---|---|---|---|
| Sterowanie | kolderstok albo rumpel | rumpel; koło możliwe od ok. 1703–1712 | koło zwykle; kolderstoki „w dużej mierze zastąpione” do 1750 | wtórne i z epoki, rozdział 09 |
| Galion | figura lwa | zwój na małych okrętach ok. 1720; lew nadal standardem na małych okrętach RN | lew albo zwój; billethead dopiero pod koniec wieku | z epoki (plany, model), wtórne, rozdziały 01, 04 |
| Bukszpryt | stenga blindy na końcu bukszprytu | małe statki przechodzą na bomstengę od 1705 | bomstenga na wszystkich statkach w ok. 20 lat | z epoki, rozdział 05 |
| Blindareja | tak | tak | tak, do ok. 1800 | z epoki, rozdział 05 |
| Żagiel gaflowy | mały, na brygantynach i slupach | bez bomu, gejtowany do masztu | bom coraz częstszy | wtórne, rozdział 08; nasz wniosek co do bomu |
| Nazwa „bryg” | nieużywana | skrót od „brygantyna” | ścisły bryg od ok. 1770 | z epoki i wtórne, rozdział 01 |
| Dno | drewno, *white stuff* | drewno, *white stuff* | miedź od 1761 (HMS *Alarm*) | wtórne, rozdział 01 |
| Działa | mieszane stare wzory | kalibry Borgarda od 1716 | karonady dopiero od lat 70. XVIII w. | wtórne, rozdziały 01, 09 |
| Pompy, kambuz | pompy wiązowe, palenisko z cegły | to samo | żelazne kuchnie od lat 50.; ulepszone pompy łańcuchowe w latach 70. | wtórne, rozdział 09 |
| Łodzie | na legarach albo holowane | to samo | żurawiki dopiero między 1790 a 1804 | wtórne, rozdział 01 |

Zmieniaj części zestawem. Kadłub z 1740 r. z kolderstokiem albo kadłub z 1700 r. z kołem i billetheadem miesza daty.

## Co sprawdzić po zmianie

### 1. Furty i miejsce na obsługę dział

- Furty co 2,3–2,6 m (rozdział 01). Furta nie może przecinać puttinga, ławy wantowej ani opętnika masztu.
- W poprzek pokładu dwa działa pary wtoczone razem z odrzutem muszą zostawić przejście. W modelu wzorcowym laweta
  ma 1,5 m długości, a odrzut do 1,5 m (`guns`, grupa `fittings`); kilka dział odskakuje mniej, bo zatrzymuje je
  wyposażenie (`limited_by` w `data/moving-parts.csv`: nagielbank grota, wieniec zapadkowy kabestanu, luk główny
  i dziobowy).
- Każda osoba przy dziale potrzebuje wolnego koła o promieniu ok. 0,45 m (0,30 m przy burcie); test chodzenia modelu
  wzorcowego używa tych wartości (model wzorcowy, rozdział 13).
- Progi furt co najmniej ok. 1,2 m nad wodą (rozdział 02).

### 2. Wysokość pod pokładem

- Głębokość ładowni wyznacza przestrzeń pod pokładem głównym. Pod pokładem rufowym 1,70 m wysokim, przy pokładnikach
  ok. 0,22 m, wysokość w świetle to ok. 1,5–1,6 m (rozdział 04, nasz wniosek).
- Jeśli obniżasz pokład rufowy, sprawdź koło albo rumpel pod nim i schody zejściówki (8 stopni w
  `data/deck-layout.json`).

### 3. Zanurzenie i wyporność

Dla kadłuba o tym samym kształcie skaluj wyporność długością, szerokością i zanurzeniem (nasz wniosek):

Δ₂ ≈ Δ₁ · (L₂ / L₁) · (B₂ / B₁) · (T₂ / T₁)

gdzie Δ₁ ok. 317 t, L₁ = 28,0 m, B₁ = 7,60 m, T₁ = 2,85 m do wrębu (rozdział 02). Jeśli zmieniasz też kształt, zmierz
nowy kadłub metodą z rozdziału 02. Sprawdź też, czy tonaż (bm) mieści się w ok. 10 % od prawdziwego statku tej
wielkości (rozdział 01). W modelu wzorcowym bm / Δ to ok. 243 / 317 = 0,77 (nasze obliczenie); statek z płytką
ładownią ma większy stosunek, bo wzór bm pomija głębokość.

### 4. Równowaga żaglowa

Jeśli CE jest za bardzo z tyłu, statek sam obraca się w wiatr (nawietrzność); jeśli jest za bardzo z przodu,
odpada od wiatru (zawietrzność). Prawdziwe środki przesuwają się, gdy statek się przechyla i nabiera prędkości,
więc projektanci rysują CE w pewnej odległości przed CLR [8] (wtórne).

1. **CLR**: narysuj podwodny obrys burty (stępka, dziobnica, tylnica, do wodnicy; bez steru) i znajdź środek jego
   pola. Na papierze: wytnij go z kartonu i zrównoważ na szpilce [7] (wtórne).
2. **CE**: narysuj każdy żagiel płasko w rzucie z boku; znajdź środek pola każdego (trapez dla żagla rejowego,
   trójkąt dla żagla przedniego, czworokąt dla gaflowego); weź średnią ważoną polem.
3. **Wyprzedzenie** = s(CE) − s(CLR), podzielone przez długość wodnicy.

Dla modelu wzorcowego (nasze obliczenie z `data/offsets.csv`, `data/spars.csv` i szacunków żagli postawionych
w `data/parameters.json`):

| Pozycja | Wartość |
|---|---|
| Obrys podwodny | 80,4 m², CLR w s = −0,92, 1,53 m pod wodą |
| Żagle dolne, marsle, żagiel gaflowy, kliwer, fok-sztaksel stengowy | 638 m², CE w s = +3,33, 10,6 m nad wodą |
| Wyprzedzenie | 4,24 m = 15,5 % L_wl 27,31 m |
| Tylko marsle, żagiel gaflowy i kliwer („żagle bojowe”) | 345 m², CE w s = +1,89, wyprzedzenie 2,81 m = 10,3 % |

Dla jachtów projektanci podają wyprzedzenie 7–12 % dla szkunerów, 11–14 % dla keczy i 13–17 % dla slupów [8]
(wtórne, współczesne jachty). Liczby z epoki dla żaglowców rejowych nie znaleźliśmy. Używaj modelu wzorcowego jako
miary: trzymaj wyprzedzenie w granicach kilku procent od jego 15 % dla tych samych żagli, a dla ożaglowania
skośnego w zakresie jachtowym (nasz wniosek).

### 5. Zakres brasowania

Reja obraca się na maszcie. Gdy obróci się o kąt θ, jej tylna krawędź idzie ku wantom i padunom, a przednia ku
sztagom. Dla wanty oddalonej o w na bok od masztu i o a ku rufie, na wysokości rei, reja dotknie jej przy ok.
θ ≈ atan(a / w) (nasz wniosek, geometria płaska; odejmij grubość rei). W modelu wzorcowym reje opuszczone obracają
się tylko o ±5° do ±10°, zanim dotkną sztagów albo wyblinek, a wszystkie reje obracają się o ±35° po podniesieniu do
pozycji roboczej (model wzorcowy, `data/moving-parts.csv`). Szersze ławy wantowe i bardziej pochylone wanty dają
więcej miejsca. Po każdej zmianie ław wantowych, want albo długości rej wykonaj test jeszcze raz (rozdział 13).

### 6. Kolizje lin

Każdy nowy sztag albo wanta musi omijać reje, marsy, łódź na legarach i wyposażenie pokładu. Po każdej zmianie
wykonaj na olinowaniu test przenikania z rozdziału 13. Sztag przez łódź był prawdziwym błędem w modelu wzorcowym.

## Przykład policzony A: slup ok. 21 m (nasz wniosek)

**Założenia.** Jednomasztowy slup handlowy albo kaperski z ok. 1715 r., grotżagiel gaflowy, sztaksel i kliwer,
dziesięć małych dział. Wszystkie liczby poniżej to nasz wniosek, chyba że podano źródło.

**Kadłub.**

| Wielkość | Reguła | Wartość |
|---|---|---|
| Długość pokładu L | wybrana | 21,0 m |
| Szerokość B | L / 3,26 (slupy 3,1–3,3) | 6,45 m |
| Głębokość ładowni | 0,43 B | 2,77 m |
| Stępka | 0,78 L | 16,38 m |
| Tonaż | 53,7 × 21,16 × 10,58 / 94 (stopy) | 128 bm (*Ferret* 1711: 114; *Cruizer* 1709: 123, rozdział 01) |
| Zanurzenie do wrębu | 2,85 × 2,77 / 3,20 | 2,47 m |
| Wyporność | 317 × (21,0/28,0) × (6,45/7,60) × (2,47/2,85) | ok. 175 t |

**Działa.** Pięć par furt co 2,45 m: 9,8 m między pierwszą a ostatnią furtą. Dziesięć 3-funtówek (lufa ok. 1,37 m,
rozdział 09).

**Pierwsze ożaglowanie: reguły takie, jakie są.** M = (21,0 + 6,45) / 2 = 13,72 m; bom 2/3 M = 9,15 m; gafel 3/5
bomu = 5,49 m; bukszpryt 3/5 M = 8,23 m; bomstenga 5,88 m. Maszt stawiamy 0,45 L za głowicą dziobnicy (s = +1,05),
czego wymaga sprawdzenie równowagi poniżej; pierwsza próba z 0,38 L dała wyprzedzenie ok. 22 %. Żagle: grotżagiel
gaflowy 62 m², kliwer 40 m², fok-sztaksel 28 m², razem 130 m². Wyprzedzenie 3,56 m = 17 % długości wodnicy
(20,5 m).

**Sprawdzenie powierzchni żagli.** Porównaj powierzchnię żagli z wypornością jako SA / Δ^(2/3) (pole w m², Δ w t).
Wzorcowy snow daje 345 / 317^(2/3) = 7,4 dla żagli bojowych i 13,7 dla żagli roboczych. Nasz pierwszy slup daje
130 / 175^(2/3) = 4,1: o wiele za mało żagli. Reguła M = (L + B) / 2 powstała dla grotmasztu dwumasztowca; przy
jednym maszcie jest za krótka (nasz wniosek). W naszych źródłach nie znaleźliśmy reguły z epoki na maszt
jednomasztowego slupu.

**Drugie ożaglowanie: wszystkie drzewca 1,3 raza dłuższe.**

| Drzewce | Wartość | Reguła |
|---|---|---|
| Maszt | 17,84 m, Ø 0,496 m | 1,3 × (L + B)/2; średnica 1/36 długości |
| Top masztu | 2,48 m | 5/36 masztu |
| Stenga | 10,70 m, Ø 0,297 m | 3/5 masztu |
| Bom | 11,89 m | 2/3 masztu; koniec bomu sięga s = −10,7, tuż za rufę w −10,5 |
| Gafel | 7,14 m, pod kątem 38° | 3/5 bomu |
| Bukszpryt, bomstenga | 10,71 m, 7,65 m | 3/5 masztu; 5/7 bukszprytu |
| Marsreja (opcjonalnie) | 11,33 m | 5/7 z 8/9 masztu |

| Żagiel | Pole | Środek pola (s, wysokość nad wodą) |
|---|---|---|
| Grotżagiel gaflowy | 117 m² | (−3,89; 8,21) |
| Kliwer | 71 m² | (+11,81; 8,01) |
| Fok-sztaksel | 42 m² | (+4,62; 5,79) |
| **Razem** | **230 m²** | **CE (+2,49; 7,71)** |

- CLR: obrys wzorcowy przeskalowany do 21 m daje s = −0,69.
- Wyprzedzenie: 2,49 − (−0,69) = 3,18 m = 15,5 % z 20,5 m. W zakresie dla slupów wg [8] i tyle samo co wzorcowy snow.
- Powierzchnia żagli: 230 / 175^(2/3) = 7,4, tyle co żagle bojowe wzorcowego snow.
- CE stoi teraz 7,7 m nad wodą, wyżej niż wcześniej. Stateczności ten przewodnik nie omawia; wyższe ożaglowanie
  potrzebuje więcej balastu.
- Opcjonalny marsel dodałby pole wysoko i przed masztem; jeśli go dodasz, sprawdź wyprzedzenie jeszcze raz.

## Przykład policzony B: trójmasztowiec ok. 32 m (nasz wniosek)

**Założenia.** Mały trójmasztowy okręt wojenny z ok. 1719 r. z dwudziestoma działami na jednym pokładzie, wielkości
20-działowca z ustalenia z 1719 r. (pokład działowy 106 ft 0 in = 32,3 m, szerokość 28 ft 4 in = 8,6 m, głębokość
9 ft 2 in = 2,8 m, stępka 87 ft 9 in = 26,7 m, 374 49/94 bm [1] (wtórne)).

**Kadłub.**

| Wielkość | Reguła | Wartość |
|---|---|---|
| Długość pokładu L | wybrana | 32,0 m |
| Szerokość B | L / 3,72 | 8,60 m |
| Głębokość ładowni | 0,32 B, jak w 1719 r. | 2,75 m |
| Stępka | 0,83 L | 26,56 m |
| Tonaż | 87,1 × 28,2 × 14,1 / 94 (stopy) | 369 bm (ustalenie z 1719 r.: 374,5, w granicach 2 %) |
| Zanurzenie do wrębu | 2,85 × 2,75 / 3,20 | 2,45 m |
| Wyporność | 317 × (32,0/28,0) × (8,60/7,60) × (2,45/2,85) | ok. 353 t (niepewne: ładownia jest dużo płytsza niż nasza) |

**Maszty i reje** (reguły Steela [2]):

| Drzewce | Reguła | Długość | Średnica |
|---|---|---|---|
| Grotmaszt | (L + B) / 2 | 20,30 m | 0,564 m |
| Fokmaszt | 8/9 grota | 18,04 m | 0,507 m (9/10 grota) |
| Bezanmaszt | 6/7 grota | 17,40 m | 0,483 m (1/36 długości, nasz wniosek) |
| Grotstenga, fokstenga, bezanstenga | 3/5 grota; 8/9 z niej; 3/4 z niej | 12,18, 10,83, 9,13 m | |
| Grotbramstenga, fokbramstenga | 1/2 stengi | 6,09, 5,41 m | |
| Reja grota, reja foka | 8/9 grotmasztu; 7/8 z niej | 18,04, 15,79 m | grot 0,351 m |
| Grotmarsreja, fokmarsreja | 5/7 rei grota; 7/8 z niej | 12,89, 11,28 m | |
| Krojcel, blindareja | = fokmarsreja | 11,28 m | |
| Reja bezanu (łacińska) | 6/7 rei grota | 15,47 m | |
| Bukszpryt, bomstenga | 3/5 grotmasztu; 5/7 z niego | 12,18, 8,70 m | |

**Położenie masztów** (fok 1/9, grot 5/9, bezan 17/20 L od dziobnicy [2]): fok 3,56 m (s = +12,44), grot 17,78 m
(s = −1,78), bezan 27,20 m (s = −11,20).

**Działa.** Dziesięć par co 2,45 m wymaga 22,05 m między pierwszą a ostatnią furtą: np. od s = +11,50 do −10,55.
Grotmaszt w s = −1,78 wypada wtedy między furtami w −0,75 i −3,20, więc jego ławy wantowe i puttingi mieszczą się
między furtami. Obsada: 6–7 ludzi na 6-funtówkę (rozdział 09), czyli ok. 70 ludzi na jedną burtę.

**Równowaga żaglowa, z grubsza.** Przypisz fokowi i grotowi wagi równe sumie kwadratów długości rei dolnej
i marsrei, bezanowi ok. ćwierć kwadratu jego rei łacińskiej, a żaglom przednim ok. 12 % wag foka i grota razem: CE
wychodzi w s = +5,2, CLR (przeskalowany) w s = −1,05, wyprzedzenie ok. 6,3 m = 20 % długości wodnicy. To więcej niż
15 % wzorcowego snow. Metoda jest zgrubna; zanim jej zaufasz, narysuj żagle i wykonaj pełne sprawdzenie. Jeśli pełne
sprawdzenie da to samo, przesuń maszty trochę ku rufie albo skróć bomstengę.

**Sprawdzenie daty.** Dla 1719 r.: rumpel albo koło (oba możliwe), figura lwa, bomstenga (małe statki zmieniały
od 1705 r.), blindareja, łaciński bezan, bez miedzi, bez karonad, łodzie na legarach (rozdziały 01, 05, 09).

## Sprawdź się

- [ ] Zmieniałem jedną grupę parametrów naraz i zapisałem dlaczego.
- [ ] L / B, głębokość / B i stępka / L mieszczą się w zakresach z rozdziału 01 albo mam źródło na odstępstwo.
- [ ] Mój tonaż różni się o mniej niż ok. 10 % od prawdziwego statku tej wielkości.
- [ ] Każdy maszt i reja wynika z M według reguły, którą umiem nazwać, albo jest oznaczony jako mój wybór.
- [ ] Furty co 2,3–2,6 m, z dala od ław wantowych i masztów, progi ok. 1,2 m albo więcej nad wodą.
- [ ] Działa wtoczone z pełnym odrzutem zostawiają przejście; każde stanowisko ma wolne koło.
- [ ] Równowaga żaglowa: wyprzedzenie w granicach kilku procent od modelu wzorcowego dla tych samych żagli.
- [ ] Powierzchnia żagli na wyporność bliska modelowi wzorcowemu.
- [ ] Reje brasują się tak daleko, jak trzeba; w teście przenikania nic nie koliduje.
- [ ] Wszystkie części pasują do wybranej daty (sterowanie, galion, bukszpryt, gafel, dno, działa, łodzie).

## Typowe błędy

1. Skalowanie całego modelu wzorcowego w górę albo w dół jednym współczynnikiem: maszty, furty, ludzie i schody tak
   się nie skalują.
2. Użycie M = (L + B) / 2 dla jedynego masztu slupu, co daje za mało żagli.
3. Przesunięcie masztu dla układu pokładu i zapomnienie o równowadze żaglowej.
4. Kecz z bezanem za głowicą steru (to jest jol [4]).
5. Trójmasztowiec z 1710 r. z gaflowym bezanem i martwym kutrem (dolphin striker).
6. Więcej dział, niż mieści śródokręcie, albo furty przez puttingi.
7. Zmiana daty kadłuba bez zmiany galionu, sterowania albo bukszprytu.

## Źródła

1. Wikipedia, „1719 Establishment” https://en.wikipedia.org/wiki/1719_Establishment (CC BY-SA). 20-działowiec: pokład
   działowy 106 ft, stępka 87 ft 9 in, szerokość 28 ft 4 in, głębokość 9 ft 2 in, 374 49/94 bm.
2. D. Steel, *The Elements and Practice of Rigging and Seamanship* (1794), transkrypcja
   https://whalesite.org/anthology/1794_Steel_Elements_and_Practice.htm. Grotmaszt z długości dolnego pokładu
   i największej szerokości, bezanmaszt 6/7 grotmasztu, bezanstenga 3/4 grotstengi, krojcel równy fokmarsrei, reja
   bezanu 6/7 rei grota; położenie masztów 1/9, 5/9, 17/20. Pozostałe reguły jak w rozdziale 05.
3. W. A. Baker, „Vessel Types of Colonial Massachusetts” i pozostałe źródła [rozdziału 01](01-ship-type-and-era.md)
   (nazwy ożaglowań i daty).
4. Wikipedia, „Ketch” https://en.wikipedia.org/wiki/Ketch (CC BY-SA). Bezan przed trzonem steru; kecz a jol.
5. Wikipedia, „Schooner” https://en.wikipedia.org/wiki/Schooner (CC BY-SA). Holenderskie obrazy z początku XVII w.;
   rozwój w Ameryce Brytyjskiej od ok. 1713.
6. Wikipedia, „Lateen” https://en.wikipedia.org/wiki/Lateen (CC BY-SA). Łaciński bezan na pełnorejowcach; według tej
   strony zastąpiony bezanem gaflowym (driver, spanker) na początku XIX w.
7. Duckworks Magazine, artykuł o równowadze łodzi https://duckworksmagazine.com/08/howto/balance/index.htm
   (wyznaczanie środka bocznego oporu przez zrównoważenie obrysu na szpilce).
8. D. Gerr, „Helm Control: The Delicate Balance”, *Small Boat Journal* 60 (1988), przedruk
   https://duckworksmagazine.com/05/vintage/sbj/3/index.htm (wyprzedzenie w procentach długości wodnicy według
   ożaglowania; współczesne małe jednostki).

## Terminy użyte w rozdziale

| Angielski | Polski | Objaśnienie |
|---|---|---|
| parameter | parametr | Jedna liczba, z której buduje się projekt. |
| proportion rule | reguła proporcji | Reguła dająca jeden wymiar z innego. |
| variant | wariant | Ten sam kadłub, inne ożaglowanie albo wyposażenie. |
| centre of effort (CE) | środek ożaglowania | Środek pola żagli, gdzie działa siła wiatru. |
| centre of lateral resistance (CLR) | środek bocznego oporu | Środek pola podwodnego obrysu burty. |
| lead | wyprzedzenie (środka ożaglowania) | Odległość CE przed CLR. |
| weather helm, lee helm | nawietrzność, zawietrzność | Skłonność do obracania się w wiatr albo od wiatru. |
| bracing range | zakres brasowania | Jak daleko reja może się obrócić. |
| displacement | wyporność | Masa wody wypartej przez kadłub. |
| ketch, yawl | kecz, jol (ożaglowanie) | Dwumasztowce z bezanem przed albo za głowicą steru. |
| schooner | szkuner | Dwa albo więcej masztów z żaglami gaflowymi. |
| sixth rate, Establishment | okręt VI rangi, ustalenie wymiarów (Establishment) | Najmniejszy okręt rangowy; ustalone wymiary klasy. |
| lateen mizzen | bezan łaciński | Długa ukośna reja na bezanmaszcie. |
| cross-jack yard | krojcel (reja bezanowa) | Najniższa reja na bezanmaszcie okrętu. |
| driver, spanker | bezan gaflowy | Żagiel gaflowy na bezanmaszcie późniejszego okrętu. |
