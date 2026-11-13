# 13. Lista kontrolna jakości modelu 3D

## Po co ten etap

Model statku może dobrze wyglądać na jednym obrazku i mimo to być zepsuty: działo przechodzi przez pokrywę furty,
gdy się porusza, tekstura jest rozciągnięta wzdłuż jednej deski, reja w grze robi się czarna, bo jej ściany patrzą
do środka. Ten rozdział to lista kontrolna dla modelu 3D statku, który ma być używany, a nie tylko oglądany: w grze,
w symulacji albo w przeglądarce.

Dla każdego punktu dostajesz:

- **co** sprawdzić;
- **dlaczego** to ważne;
- **jak to sprawdzić**, ręcznie albo skryptem;
- wynik albo cel **modelu wzorcowego**, jeśli go mamy.

Ostatnia część wymienia błędy, które naprawdę popełniliśmy przy budowie modelu wzorcowego, z objawem, przyczyną
i testem, który teraz łapie każdy z nich.

Liczby oznaczone „w chwili pisania” (liczba trójkątów, rozmiary plików, liczba lin) zmieniają się trochę przy każdej
przebudowie modelu. Aktualne wartości bierz z plików danych i z własnego uruchomienia testów. Oznaczenia pewności są
objaśnione w [rozdziale 01](01-ship-type-and-era.md); w tym rozdziale większość wartości to wybory albo pomiary
**modelu wzorcowego**.

## Pojęcia

- **Siatka**: powierzchnia obiektu 3D z **wierzchołków** (punktów), **krawędzi** i **ścian** (zwykle trójkątów).
- **Bryła zamknięta** (rozmaitość, „szczelna”): siatka, w której każda krawędź należy do dokładnie dwóch ścian.
- **Normalna**: kierunek, w który patrzy ściana. Na bryle zamkniętej wszystkie normalne powinny patrzeć na zewnątrz.
- **Punkt obrotu** (początek obiektu): punkt, wokół którego obiekt się obraca. **Osie lokalne**: własne X, Y, Z
  obiektu.
- **Mapa UV**: płaskie rozłożenie powierzchni na obrazie tekstury. **u** i **v** to dwa kierunki obrazu.
- **Gęstość tekseli**: ile pikseli tekstury przypada na metr powierzchni (px/m).
- **Anizotropia** (mapy UV): o ile bardziej tekstura jest rozciągnięta w jednym kierunku niż w drugim.
- **PBR** (renderowanie oparte na fizyce): materiały opisane kolorem bazowym (**albedo**), **chropowatością**
  i **metalicznością**, żeby wyglądały dobrze w każdym świetle.
- **sRGB i liniowy**: dwa sposoby zapisu wartości koloru. Obrazy zapisuje się w sRGB (więcej stopni dla ciemnych
  tonów); oświetlenie liczy się w wartościach liniowych. Współczynniki koloru w glTF są liniowe [1].
- **glTF / GLB**: otwarty format plików scen 3D; GLB to jego jednoplikowa postać binarna [1].
- **Extras**: wolne pole w glTF na dane aplikacji [2]. Model wzorcowy zapisuje tam osie i zakresy części ruchomych.
- **LOD** (poziom szczegółów): prostsze wersje modelu pokazywane z daleka.
- **Bryły kolizji**: kilka prostych brył, które zastępują statek, gdy gra sprawdza, co czego dotyka.
- **BVH** (hierarchia brył otaczających): drzewo pudełek wokół trójkątów, które przyspiesza pytanie „czy to
  dotyka tamtego?”.

## A. Jednostki, skala i osie

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Model wzorcowy |
|---|---|---|---|---|
| A1 | Jednostki to metry, skala 1 | długości w glTF są w metrach [1]; zła jednostka robi statek 1000 razy za dużym albo za małym | wczytaj plik i zmierz obwiednię | szerokość 7,60 m, gałka grota 28,84 m nad wodą (`data/spars.csv`) |
| A2 | Osie: +Y w górę, dziób ku +Z, +X ku lewej burcie | glTF ma +Y w górę i +Z do przodu, a −X w prawo [1], więc +X to lewa burta | w przeglądarce spójrz wzdłuż +Z: widzisz dziób; lewa burta jest po twojej lewej | (X, Y, Z) = (x, z, s) (`data/SCHEMA.pl.md`) |
| A3 | Korzeń w sensownym punkcie | gra ustawia i unosi statek na wodzie według korzenia | korzeń (0, 0, 0) musi leżeć na wodnicy konstrukcyjnej w połowie długości pokładu | z = 0 wodnica, s = 0 środek pokładu (model wzorcowy) |
| A4 | Przekształcenia zastosowane na częściach stałych | ukryta skala albo obrót psuje fizykę, instancje i eksport | każdy obiekt stały: skala 1, obrót 0 | 0 obiektów ze skalą ≠ 1 (w chwili pisania) |

## B. Nazwy

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Model wzorcowy |
|---|---|---|---|---|
| B1 | Tylko małe litery, cyfry i podkreślenia; bez końcówek kopii typu `.001` | kod znajduje części po nazwie; końcówki kopii zmieniają się między eksportami | wyrażenie regularne na wszystkich nazwach węzłów, np. `^[a-z0-9_]+$` | 0 błędów (w chwili pisania) |
| B2 | Jeden język, jedna nazwa na część | dwie nazwy jednej części to ciche błędy | porównaj z `data/names-map.csv` (kategoria `glb_node`, kolumna `english`) | nazwy angielskie, np. `main_topsail_yard`, `gun_port_3`, `gunport_lid_starboard_2` |
| B3 | Burta i numer w nazwie | gra musi odróżnić burty | `_port_` / `_starboard_` i numer; położenia sprawdź w plikach danych | `swivel_gun_port_1` … `_4`; `gun_starboard_1` … `_5` |
| B4 | Spójne nazwy materiałów | duplikaty chowają się w podobnych nazwach | wypisz materiały; bez prawie-duplikatów | 33 materiały w pliku głównym (w chwili pisania) |

Uwaga na pułapkę w nazwach wzorcowych: `gun_port_1` to pierwsze **działo na lewej burcie** (ang. *port* = lewa
burta), a `gunport_lid_port_1` to **pokrywa furty** (ang. *gun port*) na lewej burcie.

## C. Punkty obrotu części ruchomych

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Model wzorcowy |
|---|---|---|---|---|
| C1 | Każda część ruchoma to osobny węzeł | część scalona z kadłubem nie może się ruszać | wypisz węzły; porównaj z `data/moving-parts.csv` | 59 wierszy w `data/moving-parts.csv` (w chwili pisania), w tym 14 pokryw furt i głowica steru |
| C2 | Punkt obrotu na prawdziwej osi, lokalna Z wzdłuż niej | wtedy ruch to jeden kąt wokół jednej osi | obróć część w całym zakresie w przeglądarce; nic nie może się przesuwać | reje: lokalna Z wzdłuż masztu; ster: wzdłuż linii czopów (`axis_dir_*` w `data/moving-parts.csv`) |
| C3 | Oś i zakres zapisane w pliku | gra potrzebuje granic bez zgadywania | odczytaj extras węzła (`motion_axis`, `range_deg` albo `range_m`) | mają je wszystkie części ruchome (w chwili pisania: 59 obiektów, 0 braków) |
| C4 | Dzieci poruszają się z rodzicem | żagle zwinięte, raki, perty muszą iść za reją | obróć reję; dzieci idą za nią | żagle zwinięte i raki są dziećmi swoich rej |

## D. Czystość siatek

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Model wzorcowy |
|---|---|---|---|---|
| D1 | Bryły są zamknięte | testy objętości, testy wnętrza i wiele narzędzi wymaga zamkniętych powłok | policz krawędzie, które nie mają dokładnie dwóch ścian | 0 obiektów otwartych (w chwili pisania); liny mają otwarte końce ukryte w okuciach |
| D2 | Bez zdublowanych wierzchołków (bliżej niż 0,01 mm), ścian o zerowym polu, luźnych wierzchołków i krawędzi | psują normalne, wygładzanie i operacje logiczne | scal wierzchołki w odległości 1e-5 m; policz przed i po | 0 / 0 / 0 |
| D3 | Normalne na zewnątrz | przy pomijaniu tylnych ścian ściany odwrócone znikają | objętość ze znakiem każdej zamkniętej części musi być dodatnia | 0 odwróconych |
| D4 | Bez ścian współpłaszczyznowych bliżej niż 1 mm | migoczą (z-fighting) | dla ścian różnych obiektów: najbliższa ściana w odległości do 1 mm i równoległe normalne | 0 par |
| D5 | Mało trójkątów-„igieł” na powierzchniach gładko cieniowanych | cienkie trójkąty źle się cieniują tam, gdzie powierzchnia jest krzywa; na płaskiej ściance nie szkodzą | stosunek najdłuższej krawędzi do wysokości > 40; policz te, które mają sąsiada przez krawędź pod kątem 2–30° | ok. 640 na powierzchniach gładko cieniowanych, poniżej naszej granicy 1500; ok. 3400 więcej na płaskich ściankach, powstałych przy scalaniu nakładających się brył (w chwili pisania) |
| D6 | Gęstość siatki dopasowana do wielkości | 24 boki na wyblince to marnowanie trójkątów | policz boki części przeciąganych | liny 8, 6, 5 albo 4 boki zależnie od średnicy; maszty 16; reje 12 (rozdział 08) |
| D7 | Kadłub jest gładki | nierówności widać w odbiciach i na planie linii, a z tabeli przepisuje je każdy, kto z niej korzysta | przetnij kadłub wodnicami, przekrojami wzdłużnymi i wręgami; podziel każde przecięcie na garby o jednym znaku krzywizny; policz garby o strzałce ponad 4 mm; gładka linia ma najwyżej 3 | **niespełnione pod wodnicą w części rufowej**: 34 nadmiarowe garby, nierówności 1–5 cm w wybiegu; burty nad wodą i część dziobowa gładkie (zmierzone, patrz [rozdział 02](02-hull-lines-and-offsets.md)) |
| D8 | Brak skręconych rurek | rurka, której pierwszy pierścień jest lustrzanym odbiciem następnego, w połowie długości spłaszcza się do paska („klepsydra”), a test brył zamkniętych nadal ją przepuszcza | w każdym czworokącie przeciwległe krawędzie muszą biec obok siebie; policz czworokąty, w których się krzyżują | 0 w linach; 7 drobnych ścianek w snycerce rufy i na górze kadłuba ma jeszcze skrzyżowane krawędzie (w chwili pisania). Do późnego przeglądu pierwszy odcinek każdej przeciąganej rurki był skręcony: jedna trzecia wszystkich ścian lin, a każda prosta wanta, talrep i wyblinka na całej długości |

## E. Przenikanie brył (części wewnątrz innych części)

**Dlaczego**: lufa przez pokrywę, lina przez łódź albo laweta w nadburciu od razu wyglądają źle i psują fizykę
oraz animację.

**Jak to sprawdza model wzorcowy** (nasza metoda, model wzorcowy):

1. Podziel każdą siatkę (oprócz lin) na **spójne części** („wyspy”); działo to lufa, laweta, koła.
2. Dla każdej pary części, których obwiednie się stykają (także dwóch części tego samego obiektu), zbuduj BVH każdej
   i zapytaj o przecinające się trójkąty.
3. Gdzie trójkąty się przecinają, zmierz **głębokość**: dla wierzchołków jednej części sprawdź, czy leżą wewnątrz
   drugiej (puść promienie w trzech kierunkach i policz przecięcia: liczba nieparzysta oznacza wnętrze), i weź
   największą odległość takiego wierzchołka od powierzchni drugiej części.
4. Zgłoś każdą parę głębszą niż **5 mm**, chyba że para jest na liście **połączeń zamierzonych**. Każde połączenie
   zamierzone ma zapisane uzasadnienie, np.: maszt przechodzi przez pokład w opętniku i stoi na kilsonie (zakryte);
   wierzchołki wręgów przechodzą przez pokład do pokrywy relingu; czop steru siedzi w okuciu; rumpel jest osadzony
   w głowicy steru.
5. Liny nie mają wnętrza, więc dla liny zgłasza się tylko dotknięcie, a nie głębokość.

| # | Sprawdzenie | Model wzorcowy (w chwili pisania) |
|---|---|---|
| E1 | Brak niezamierzonych par głębszych niż 5 mm | 0 par powyżej progu; 35 styków lin bez wnikania wypisanych do przejrzenia |
| E2 | Każde połączenie zamierzone ma uzasadnienie | lista 192 reguł, każda z uzasadnieniem, w raporcie kontroli |
| E3 | Części ruchome sprawdzone w całym zakresie | działka co 45°, działa w całym odrzucie, pokrywy w całym otwarciu, reje co 5° do 35°, opuszczone i podniesione |
| E4 | Przedmioty stojące dotykają pokładu | lawety, pompy, podstawa kabestanu, szafka kompasowa, nagielbanki: bez szczeliny i bez zapadania się |
| E5 | Każdy koniec liny jest zamocowany | każdy koniec każdej liny leży najwyżej 1 cm od innej części, w jej środku albo na innej linie; zamknięte buchty i wolny koniec linki dzwonu to wypisane wyjątki: 0 wiszących końców na 2 136 |
| E6 | Każdy blok jest czymś trzymany | każdy blok styka się z bryłą, wisi na smołowanym wisiorze, jest nawleczony na prostą, napiętą talię albo ma strop do drzewca, okucia lub liny stałej; lina ruchoma, która załamuje się na bloku, go nie trzyma: 105 bloków, w tym 59 ze stropem, 0 bez zaczepu |

Testy E5 i E6 doszły późno, po przeglądzie wzrokowym. Wszystkie wcześniejsze testy przechodziły, a 69 końców lin wisiało
w powietrzu: wcześniejsza poprawka lin przechodzących przez reling po prostu je skróciła. Gdy każdy koniec liny zaczął
czegoś dotykać, okazało się, że 41 bloków samo wisi w powietrzu, a końce lin na nich leżą. Test dowodzi tylko tego,
co mierzy: „nic przez nic nie przechodzi” nie znaczy „wszystko jest przymocowane”, więc każdy z tych warunków ma własny test.

Test zakresu daje granice zapisane w `data/moving-parts.csv` (kolumna `limited_by`): np. `gun_port_3` odskakuje o
0,75 m, zanim dojdzie do luku głównego, a opuszczona `main_topsail_yard` obraca się tylko o ±5°, zanim dotknie
wyblinek (model wzorcowy).

## F. Mapy UV i tekstury

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Cel albo wartość wzorcowa |
|---|---|---|---|---|
| F1 | Gęstość tekseli na materiał | za mała wygląda na rozmytą obok ostrych części; za duża marnuje pamięć | dla każdej ściany: px/m = √(pole UV × piksele obrazu / pole 3D); dla materiału mediana ważona polem i 5. percentyl | ok. 1024 px/m na dużych powierzchniach; co najmniej ok. 450 px/m na sprzętach (cel modelu wzorcowego) |
| F2 | Równa gęstość w materiale | część o połowie gęstości ma większe słoje | stosunek 95. do 5. percentyla ≤ 1,44 (±20 %); liny i szkło sprawdzane osobno | wszystkie 19 materiałów w normie (w chwili pisania) |
| F3 | Anizotropia poniżej 1,25 | rozciągnięta tekstura: deski szersze w jedną stronę | dla każdego trójkąta dwie wartości osobliwe s₁ ≥ s₂ odwzorowania płaszczyzny trójkąta na piksele; anizotropia = s₁ / s₂; podaj udział pola powyżej 1,25 | pokład 0,2 %, czarna farba 4 %, burta z olejowanego dębu 7,6 % pola powyżej 1,25 |
| F4 | Słoje wzdłuż elementu | słoje w poprzek drzewca od razu wyglądają fałszywie | dla każdej wydłużonej części drewnianej (oś główna ≥ 2,5 × następnej) udział pola ścian bocznych, gdzie kierunek u odchyla się od osi części o mniej niż 25° | 94–100 % dla materiałów drewnianych |
| F5 | Tekstura liny skalowana średnicą | stały kafel daje proste sploty na cienkich linach | u = długość / (2 × 3,3 × d), v dookoła liny (rozdział 08) | jak podano |
| F6 | Rozmiary tekstur to potęgi dwójki | mipmapy i kompresja ich oczekują | sprawdź szerokość i wysokość | wszystkie |
| F7 | Mapy koloru w sRGB, mapy danych liniowe, mapy normalnych z +Y w górę | glTF czyta kolor bazowy jako sRGB, mapy normalnych jako liniowe; mapa ORM ma chropowatość w G i metaliczność w B, okluzję w R [2] | obejrzyj gniazda tekstur | kolor sRGB; normalne w stylu OpenGL; ORM = okluzja, chropowatość, metal |
| F8 | Okluzja na własnym UV | wypalona mapa AO potrzebuje unikalnych, nienachodzących UV | drugi zestaw UV; tekstura okluzji używa texCoord 1 | kadłub z wyposażeniem (2048 px) i drzewca (1024 px) |

Wzór gęstości krok po kroku: ściana 1 m², która zajmuje 1/4096 obrazu 4096 × 4096, ma pole UV 1/4096 i dostaje
√(1/4096 × 4096 × 4096 / 1) = 64 px/m. (Gęstość 1024 px/m wymaga 1024² = 1 048 576 pikseli na każdy metr
kwadratowy.)

## G. Materiały

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Cel albo wartość wzorcowa |
|---|---|---|---|---|
| G1 | Kolor bazowy w zakresie fizycznym | czysta czerń albo biel nie występuje w farbie ani drewnie i psuje oświetlenie | kolory bazowe niemetali nie niżej niż 30–50 sRGB i nie wyżej niż 240 sRGB (na 255) [3] | wszystkie w zakresie (w chwili pisania); najciemniejsza jest gładka czarna farba relingu, ok. 50 sRGB, po tym jak wcześniejsza wersja o ok. 32 sRGB nie przeszła |
| G2 | Metaliczność 0 albo 1 | prawdziwe powierzchnie są metalem albo nie; wartości szare tylko dla brudu na metalu [3] | współczynnik metaliczności 0 albo 1; mapa prawie czarna albo biała | żelazo i brąz 1, wszystko inne 0 |
| G3 | Współczynnik koloru podany liniowo | `baseColorFactor` w glTF to mnożnik **liniowy** [2] | przelicz sRGB c na liniowe: c / 12,92, jeśli c ≤ 0,04045, w przeciwnym razie ((c + 0,055) / 1,055)^2,4 | `colour_multiplier_srgb` w `data/parameters.json` jest zapisany w sRGB i przeliczany przy eksporcie |
| G4 | Dwustronność tylko tam, gdzie trzeba | dwustronne bryły kosztują czas i ukrywają odwrócone normalne | wypisz materiały z `doubleSided` (domyślnie false [2]) | tylko płótno i szyby |
| G5 | Bez zdublowanych materiałów | każdy duplikat to jedno wywołanie rysowania więcej | wypisz materiały i ich mapy | kopie tylko tam, gdzie część potrzebuje własnej mapy AO |

Przykład do G3: mnożnik sRGB 0,33 to liniowo 0,089. Wpisany jako 0,33 wprost do współczynnika liniowego daje kolor tak
jasny jak wartość sRGB ok. 0,61: prawie dwa razy jaśniejszy (nasze obliczenie).

## H. Budżet pliku i eksport

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Cel albo wartość wzorcowa |
|---|---|---|---|---|
| H1 | Rozmiar pliku | czas pobierania i pamięć | rozmiar `model/snow.glb` | ≤ 32 MB; 31,0 MB w chwili pisania |
| H2 | Budżet trójkątów | liczba klatek na sekundę | policz trójkąty indeksowane w pliku | ok. 230 000 w chwili pisania (nasz budżet 280 000) |
| H3 | Plik zgadza się ze źródłem | eksporter potrafi po cichu zgubić części, scalić obrazy albo zmienić kolory | wczytaj wyeksportowany plik z powrotem; porównaj liczbę trójkątów (małe straty z trójkątów zdegenerowanych są normalne), listę obiektów i obwiednię | żadnej brakującej części |
| H4 | Obrazy przeżywają eksport | trzy mapy jednego materiału muszą zostać trzema obrazami | dla każdego materiału w pliku: obrazy koloru, ORM i normalnych są różne; średni kolor wyeksportowanej mapy koloru różni się od źródła o ≤ 0,05 na kanał; rozmiar równy albo zmniejszony 2, 4 albo 8 razy | wszystkie materiały przechodzą (w chwili pisania) |
| H5 | Rendery kontrolne z wyeksportowanego pliku | ostatecznym dowodem jest wygląd | wyrenderuj te same ujęcia (burta z wody, pokład z wysokości oczu, rufa, koło z bliska) z wyeksportowanego pliku i ze źródła przy tym samym świetle; porównaj średnią jasność (różnica ≤ 10 %) i udział każdego kanału koloru (≤ 0,04) | wszystkie cztery ujęcia przechodzą (w chwili pisania) |
| H6 | Styczne | mapy normalnych ich potrzebują | plik wzorcowy celowo ich nie zawiera: three.js wyznacza je w shaderze, a plik jest mniejszy | brak w pliku |

## I. LOD i kolizje

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Model wzorcowy (w chwili pisania) |
|---|---|---|---|---|
| I1 | Poziomy LOD istnieją i są dużo mniejsze | daleki statek nie potrzebuje 200 000 trójkątów | policz trójkąty w każdym pliku | LOD0 100 %; LOD1 ok. 50 % (jedna siatka, tekstury 1K); LOD2 ok. 5 % (bez wyblinek, talrepów, olinowania ruchomego, drobnego wyposażenia; tekstury 512 px) |
| I2 | Przełączanie LOD nie skacze | nagła zmiana sylwetki jest widoczna | obejrzyj odległość przełączania; sylwetka (maszty, reje, wanty) musi zostać | rozdział 08 podaje odległości dla lin |
| I3 | Bryły kolizji są proste i pokrywają statek | fizyka i chodzenie potrzebują tanich, zamkniętych kształtów | policz bryły i trójkąty; nałóż je na model | 36 brył w `model/snow_collision.glb`, węzły `collision_*`: uproszczony zamknięty kadłub, płyty pokładów, prostopadłościany nadburć, ośmioboczne walce masztów i bukszprytu, prostopadłościany i walce dział, kabestanu, pomp, koła i innych dużych sprzętów |
| I4 | Części wariantów oznaczone | koło i rumpel pokładowy nie mogą oba blokować pokładu | każda bryła wariantu ma tę samą wartość `variant` co część | bryły koła i rumpla oznaczone |

## J. Chodzenie, stanowiska i liny

| # | Sprawdzenie | Dlaczego | Jak sprawdzić | Model wzorcowy |
|---|---|---|---|---|
| J1 | Do każdego stanowiska da się dojść | członek załogi, który nie dojdzie do kabestanu, to błąd | siatka 0,1 m na każdym pokładzie; postać o promieniu 0,3 m i wzroście 1,75 m; wypełnianie od komórki startowej do każdego stanowiska | wszystkie stanowiska osiągalne (`data/deck-layout.json`, `walker`) |
| J2 | Wolne miejsce przy każdym stanowisku | ludzie potrzebują miejsca do pracy | wolne koło o promieniu 0,45 m (0,30 m przy burcie) | stanowiska przesunięte przez test są wypisane w raporcie |
| J3 | Przejścia | załoga musi przejść | najwęższa szczelina między przeszkodami ≥ 0,8 m | żadnej węższej (rozdział 04) |
| J4 | Miejsce nad głową | pokładniki i drzewca na wysokości głowy | promienie w górę z wolnych komórek między 1,45 a 2,0 m nad pokładem, liny pominięte | brak w chwili pisania |
| J5 | Działa wtoczone | odrzut może przeciąć pokład na pół | powtórz J1 ze wszystkimi działami w pełnym odrzucie | w chwili pisania stanowiska dziobowe (kotwica, kotbelki, sonda ręczna, wanty foka) są odcięte, gdy wszystkie działa są wtoczone |
| J6 | Symetria lin | brak prawego brasu łatwo przeoczyć | każda lina z końcem na lewej burcie (x > 3 cm) musi mieć prawą bliźniaczkę z odbitymi końcami (do 3 cm), tą samą grupą, średnicą i materiałem; wyjątki: buchty, kotwice, łódź, sterowanie, liny dział i dzwonu, liny jednostronne | 508 par, żadnej liny bez bliźniaczki i żadnej o innej średnicy (w chwili pisania) |

## Przykład policzony: deski pokładu

1. Tekstura pokładu to atlas 4096 × 1024 piksele, który pokrywa 3,52 m × 0,88 m pokładu (cztery rzędy desek, model
   wzorcowy). Wzdłuż desek: 4096 / 3,52 = 1164 px/m. W poprzek: 1024 / 0,88 = 1164 px/m. Gęstość jest taka sama
   w obu kierunkach, więc anizotropia wynosi 1,0 (nasze obliczenie).
2. Wyeksportowany plik daje medianę 1163 px/m i 5. percentyl 1160 px/m: cały pokład jest odwzorowany równo.
3. Mediana anizotropii to 1,001; 0,2 % pola pokładu jest powyżej 1,25 (w chwili pisania).
4. Pokład spełnia F1, F2 i F3.

## Błędy, które naprawdę popełniliśmy

| Błąd | Objaw | Przyczyna | Test, który teraz to łapie |
|---|---|---|---|
| Lufy przez pokrywy furt | przy otwartej pokrywie i wytoczonym dziale wylot lufy przechodził przez pokrywę | kąt otwarcia pokrywy i lufę z jej podniesieniem ustawiano osobno; nikt nie sprawdził ich razem | test zakresu (E3) każdej pokrywy razem z działem; pokrywy otwierają się teraz na 95° do 100° ponad lufę, a zakres jest obcięty do 85° albo 75° tam, gdzie pokrywę zatrzymują ławy wantowe albo listwy (`range_max` w `data/moving-parts.csv`) |
| Lawety w nadburciu | przód niektórych lawet wchodził w wewnętrzną stronę nadburcia, najbardziej na dziobie | burta pochyla się do środka nad wodnicą i zwęża ku dziobowi; lawetę ustawiano od krawędzi pokładu na jednej wysokości | E1; przód lawety trzyma teraz 3 cm od nadburcia na całej swojej wysokości i długości |
| Sztag przez łódź | przy łodzi na legarach nad lukiem głównym przez łódź przechodził sztag | łódź ustawiono według układu pokładu, bez patrzenia na olinowanie | E1 z linami: lina, która dotyka bryły zamkniętej, jest zgłaszana |
| Tekstury 1K sklejone w jeden obraz | w wyeksportowanym pliku mapa koloru, ORM i normalnych jednego materiału wskazywały ten sam obraz; materiał wyglądał płasko i miał zły kolor | kopie o połowie rozmiaru robione na eksport dostały nieunikalne nazwy, więc jeden obraz zastąpił pozostałe | H4: trzy mapy każdego materiału muszą być różnymi obrazami |
| Mnożnik koloru w sRGB użyty jako liniowy | części w grze wyglądały dużo jaśniej niż w źródle | mnożnik zapisano w sRGB, a współczynnik glTF jest liniowy | G3, H4 (średni kolor względem źródła), H5 (rendery kontrolne) |
| Zdublowane sloty materiałów po operacji Boolean | po wycięciu otworu na trzon steru operacją Boolean pas furt dostał materiał pokładu | kilka regionów malowania wskazywało ten sam materiał w osobnych slotach, a Boolean przenumerował sloty | jeden slot na materiał; rendery kontrolne H5 i obejrzenie burty po każdej operacji Boolean |
| Ścinanie UV na burcie | deski tekstury kadłuba skręcały się przy rufie; anizotropia do 2 | u liczono jako długość łuku w 3D wzdłuż każdego rzędu siatki kadłuba od śródokręcia; rzędy z większym wzniosem były dłuższe, więc sąsiednie rzędy rozjeżdżały się | F3; u liczy się teraz w rzucie poziomym (x, s) |
| Odwrócone normalne rej | niektóre reje (i części łodzi) ciemniały albo znikały przy pomijaniu tylnych ścian | automatyczne „przelicz normalne” odwracało długie, cienkie walce | D3: po ujednoliceniu normalnych o ich kierunku decyduje znak objętości każdej zamkniętej części |
| Generator tekstur AI na sklejanych siatkach | białe i czarne pasy w wygenerowanych teksturach na drobnych luźnych kawałkach i na ścianach wewnętrznych | części wysyłano jako wiele otwartych, nachodzących na siebie powierzchni; generator oczekuje jednej zamkniętej powłoki | D1 przed wysłaniem; otwarte powierzchnie najpierw się pogrubia, potem wszystkie kawałki przetapia w jedną zamkniętą powłokę i upraszcza do budżetu trójkątów |

## Sprawdź się

- [ ] Plik wczytuje się w metrach z dziobem ku +Z i lewą burtą ku +X.
- [ ] Każda część ruchoma ma punkt obrotu na swojej osi i zakres w extras.
- [ ] Brak niezamierzonego przenikania powyżej 5 mm, także w całym zakresie każdej części ruchomej.
- [ ] Gęstość tekseli ok. 1024 px/m na dużych powierzchniach, co najmniej ok. 450 px/m na sprzętach, rozrzut ≤ ±20 %.
- [ ] Anizotropia powyżej 1,25 tylko na małej części każdego materiału; słoje wzdłuż elementów.
- [ ] Kolory bazowe w zakresie 30–240 sRGB; metaliczność 0 albo 1; współczynniki koloru liniowe.
- [ ] Wyeksportowany plik zgadza się ze źródłem w trójkątach, obrazach, kolorach i renderach kontrolnych.
- [ ] Pliki LOD i bryły kolizji istnieją; części wariantów są oznaczone.
- [ ] Do każdego stanowiska da się dojść, także z wtoczonymi działami.

## Typowe błędy

1. Wiara w ładny render zamiast w liczby.
2. Sprawdzanie modelu tylko w pozycji spoczynkowej.
3. Wpisywanie kolorów sRGB do pól liniowych.
4. Jeden rozmiar tekstury dla wszystkiego, przez co małe części są ostre, a kadłub rozmyty (albo odwrotnie).
5. Pozwolenie eksporterowi na scalenie części, które mają się ruszać.
6. Wyjątki od testów bez zapisanego uzasadnienia.
7. Sprawdzanie pliku źródłowego, a nie wyeksportowanego.

## Źródła

1. Khronos Group, *glTF 2.0 Specification* https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html (układ
   współrzędnych: +Y w górę, +Z do przodu, −X w prawo; długości w metrach).
2. Khronos Group, schemat JSON glTF 2.0:
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/material.pbrMetallicRoughness.schema.json
   (`baseColorFactor` i `metallicFactor` to mnożniki liniowe; tekstura koloru bazowego w sRGB; metaliczność w B,
   chropowatość w G);
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/material.schema.json (tekstura
   normalnych liniowa; okluzja w R; `doubleSided` domyślnie false);
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/extras.schema.json
   („application-specific data”).
3. Adobe, *The PBR Guide, part 2* https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2 (ciemne
   wartości nie niżej niż 30–50 sRGB, jasne nie wyżej niż 240 sRGB; mapa metaliczności zwykle czarna albo biała).
4. Blender Manual, dodatek glTF 2.0 https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html (właściwości
   własne eksportowane jako extras; opcja +Y w górę; okluzja przez grupę węzłów „glTF Material Output”).

## Terminy użyte w rozdziale

| Angielski | Polski | Objaśnienie |
|---|---|---|
| mesh, vertex, edge, face | siatka, wierzchołek, krawędź, ściana | Części powierzchni 3D. |
| closed solid (manifold) | bryła zamknięta (rozmaitość) | Każda krawędź ma dokładnie dwie ściany. |
| normal | normalna | Kierunek, w który patrzy ściana. |
| pivot, origin | punkt obrotu, początek obiektu | Punkt, wokół którego obraca się obiekt. |
| UV map | mapa UV | Płaskie rozłożenie powierzchni na teksturze. |
| texel density | gęstość tekseli | Piksele tekstury na metr powierzchni. |
| anisotropy | anizotropia | Nierówne rozciągnięcie tekstury. |
| albedo, base colour | albedo, kolor bazowy | Kolor powierzchni bez światła i cienia. |
| metalness, roughness | metaliczność, chropowatość | Wartości materiału PBR. |
| sRGB, linear | sRGB, liniowy | Dwa sposoby zapisu wartości koloru. |
| occlusion (AO) | okluzja otoczenia | Przyciemnienie w zakamarkach, wypalone w mapę. |
| level of detail (LOD) | poziom szczegółów | Prostszy model na odległość. |
| collision proxy | bryła kolizji | Prosta bryła do testów kolizji. |
| BVH | hierarchia brył otaczających (BVH) | Drzewo pudełek do szybkich testów przecięć. |
| interpenetration | przenikanie brył | Jedna część wewnątrz drugiej. |
| z-fighting | migotanie (z-fighting) | Migotanie dwóch ścian w tym samym miejscu. |
| back-face culling | pomijanie tylnych ścian | Nierysowanie ścian odwróconych od kamery. |
| extras | extras (dane dodatkowe glTF) | Wolne pole na dane aplikacji w glTF. |
