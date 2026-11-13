# 14. Użycie modelu w grze

## Po co ten etap

Model wzorcowy jest zbudowany do **używania**: do chodzenia po nim, sterowania, walki i animacji. Ten rozdział
wyjaśnia, co jest w pliku modelu i w plikach danych i jak połączyć je z silnikiem gry. Kroki nie zależą od jednego
silnika. Krótkie uwagi pokazują, jak to samo robi się w formacie glTF i w bibliotece three.js dla przeglądarki.

Na końcu tego rozdziału będziesz wiedzieć:

- jaki jest układ współrzędnych, jednostki i nazwy węzłów;
- gdzie są stanowiska czynności, w którą stronę patrzą ludzie i co obsługują;
- które części się ruszają, wokół jakiej osi i jak daleko;
- jak chodzić po pokładach, przełączać koło i rumpel, brasować reje i trzymać przyczepione do nich liny;
- jak przełączać poziomy szczegółów, używać brył kolizji i nie wpuszczać morza do holowanej łodzi;
- jak podpiąć kabestan, pompy, działa, koło i dzwon;
- co jest zaplanowane, ale jeszcze nie ma tego w modelu, i jak model jest na to przygotowany.

Oznaczenia pewności są objaśnione w [rozdziale 01](01-ship-type-and-era.md). W tym rozdziale prawie każda liczba to
wartość **modelu wzorcowego** z podanego pliku; tempa pracy i liczby ludzi to **nasz wniosek**, chyba że podano inaczej.

## Pojęcia

- **Silnik**: program, który rysuje grę i wykonuje jej reguły (np. three.js, Godot, Unity, Unreal).
- **Węzeł**: jeden element sceny 3D z własnym położeniem, obrotem i skalą; węzły tworzą drzewo (drzewo sceny).
  Dziecko porusza się razem z rodzicem.
- **Extras**: wolne dane zapisane na węźle glTF [1]. three.js kopiuje je do `object.userData` [2].
- **Stanowisko czynności**: oznaczone miejsce, w którym człowiek stoi przy jednej pracy, z kierunkiem patrzenia
  i wysokością rąk.
- **Wariant**: dwie wersje tej samej części w jednym pliku, z których pokazuje się jedną (tu: koło albo rumpel).
- **Lina dynamiczna**: odcinek liny z jednym końcem na części ruchomej; gra musi go przerysować, gdy część się rusza.
- **LOD** (poziom szczegółów): prostsze kopie statku na duże odległości.
- **Bryła kolizji**: prosty, niewidoczny kształt do testów styku.
- **Bufor szablonu** (ang. *stencil buffer*): znacznik dla każdego piksela, który karta graficzna może zapisać
  i sprawdzić; tu służy do tego, żeby nie rysować morza wewnątrz łodzi.

## Pliki

| Plik | Co to jest |
|---|---|
| `model/snow.glb` | pełna szczegółowość: statyczne siatki kadłuba i olinowania, każda część ruchoma jako osobny węzeł, 142 puste węzły stanowisk, oba warianty sterowania, maska wody łodzi |
| `model/snow_lod1.glb`, `model/snow_lod2.glb` | po jednej siatce, części ruchome w pozycji spoczynkowej; ok. 50 % i 5 % trójkątów (w chwili pisania) |
| `model/snow_collision.glb` | 36 prostych brył (węzły `collision_*`), bez materiałów |
| `data/stations.csv` | 142 stanowiska czynności |
| `data/moving-parts.csv` | 59 części ruchomych (w tym 14 pokryw furt) z punktem obrotu, osią i zakresem |
| `data/deck-layout.json` | pokłady, przeszkody, schody, luki, wspinaczki, wysokości relingu, wymiary postaci |
| `data/rigging-lines.json` | wszystkie odcinki lin; dynamiczne z lokalnymi punktami końców |
| `data/names-map.csv` | angielska nazwa każdego węzła, klucza i wartości |

Pliki modelu w wydaniu są w katalogu `model/`. Nazwy ich węzłów i klucze extras to nazwy angielskie
z `data/names-map.csv`.

## Układ współrzędnych i jednostki

| Pozycja | Wartość (model wzorcowy, `data/SCHEMA.pl.md`) |
|---|---|
| Jednostki | metry; kąty w plikach danych w stopniach |
| Osie gry / glTF | +Y w górę, dziób ku +Z, +X ku lewej burcie; to zgodne z glTF, gdzie +Z jest do przodu, a −X w prawo [1] |
| Początek | (0, 0, 0) na wodnicy konstrukcyjnej, w połowie 28,0 m długości pokładu |
| Pliki danych | punkty zapisane jako [x, s, z]; w grze (X, Y, Z) = (x, z, s) |
| Kąty patrzenia | `facing_deg` w `data/stations.csv`: 0° = ku dziobowi, +90° = ku lewej burcie, czyli obrót wokół +Y |

**Współrzędne lokalne w plikach danych.** `from_local` i `to_local` w `data/rigging-lines.json` oraz słowa „lokalna
X, Y, Z” w tekstach kolumny `axis` są podane w osiach programu do modelowania (Z w górę). Eksport glTF obraca osie
lokalne każdego węzła tak samo jak osie świata. Dla punktu albo osi podanej lokalnie (Xb, Yb, Zb):

(X, Y, Z) w węźle glTF = (Xb, Zb, −Yb)

| Tekst w danych | Oś w węźle glTF / three.js |
|---|---|
| lokalna Z | lokalna +Y |
| lokalna −X | lokalna −X |
| lokalna Y | lokalna −Z |

Najbezpieczniej w ogóle nie używać nazw osi lokalnych: `data/moving-parts.csv` podaje też oś każdej części jako
kierunek w układzie statku (`axis_dir_x`, `axis_dir_s`, `axis_dir_z`) dla części obracających się wokół lokalnej Z.
Przelicz go na (x, z, s) i obracaj węzeł wokół tej osi świata przez jego punkt obrotu.

## Nazwy węzłów

Wydane pliki używają wyłącznie nazw angielskich z `data/names-map.csv` (kolumna `english`, kategoria `glb_node`;
klucze extras w kategoriach `glb_extras_key` i `json_key`). Druga kolumna tego pliku podaje wewnętrzne nazwy
generatora; potrzebujesz jej tylko dla plików zrobionych wprost przez generator, nie dla plików z `model/`. three.js przy wczytywaniu czyści nazwy węzłów z niektórych znaków [2];
nazwy angielskie mają tylko małe litery, cyfry i podkreślenia, więc się nie zmieniają.

| Grupa | Przykłady (model wzorcowy) |
|---|---|
| Siatki statyczne | `hull_static`, `spars_static`, `rigging_static` |
| Reje i gafel | `fore_yard`, `main_topsail_yard`, `spritsail_yard`, `gaff`; dzieci: `main_yard_parrel`, żagle zwinięte `main_course`, `fore_topsail` … |
| Działa | `gun_port_1` … `gun_port_5`, `gun_starboard_1` … `_5`; lufy `gun_port_1_barrel` …; działka `swivel_gun_port_1` … |
| Pokrywy furt | `gunport_lid_port_1` … `_7`, `gunport_lid_starboard_1` … `_7` |
| Mechanizmy pokładu | `capstan_barrel`, `pump_port_brake`, `pump_starboard_brake`, `bell` |
| Sterowanie | `rudder`, `rudder_head`, `deck_tiller`, `tiller_below_deck`, `steering_wheel`, `wheel_standards`, grupy `steering_wheel_variant`, `deck_tiller_variant` |
| Stanowiska | `station_capstan_1` … `_8`, `station_gun_captain_1` …, `station_wheel_1` … (razem 142) |
| Liny dynamiczne | `rope_dynamic_<group>_<id>_glb`, gdzie `<id>` to `id` odcinka w `data/rigging-lines.json` |
| Łódź | `boat_water_mask` |

Numery lin zmieniają się przy przebudowie olinowania. Szukaj lin dynamicznych po ich extras (`from_object`,
`to_object`, `dynamic`), a nie po stałym numerze.

## Stanowiska czynności

`data/stations.csv` ma jeden wiersz na stanowisko (142 w chwili pisania). Te same stanowiska są w pliku modelu pustymi
węzłami; na takim węźle **lokalna +Z to kierunek patrzenia** człowieka, a extras powtarzają `activity`, `object`,
`hand_height_m` i `variant`.

| Kolumna | Znaczenie |
|---|---|
| `x_m`, `s_m`, `z_m` | gdzie stoją stopy |
| `facing_x`, `facing_s`, `facing_z`, `facing_deg` | gdzie człowiek patrzy |
| `object`, `axis`, `range_min`, `range_max` | obsługiwana część i jej ruch |
| `hand_height_m` | wysokość rąk nad stopami (np. 1,12 m przy drągach kabestanu, 1,05 m przy kole) |
| `ropes` | liny obsługiwane w tym miejscu (brasy, topenanty, szoty …) |
| `variant` | tylko w jednym wariancie sterowania |

| Czynność | Stanowiska | Czynność | Stanowiska |
|---|---|---|---|
| obsługa dział (kapitan działa, ładowniczy, wyciorowy, dwaj przy taliach bocznych, przy talii odciągowej, chłopiec z prochem) | 70 na 10 dział | pokrywy furt | 10 |
| kabestan | 8 (po jednym na drąg) | noki rej, marsy | 8, 2 |
| pompy | 4 | wanty (wspinaczka) | 4 |
| obsługa lin (brasy, fały, gejtawy, szoty, topenanty, gaje) | 20 | luki | 3 |
| koło, rumpel pokładowy | 2, 2 | kotbelki, kotwica | 2, 1 |
| kompas, dzwon, łódź, beczka z wodą, sonda ręczna, log | po 1 | | |

Stanowiska na górze (marsy i noki rej) mają puste `level`; stoi się na pertach i na pomostach marsów.

## Części ruchome

`data/moving-parts.csv` wymienia każdą część ruchomą (59 w chwili pisania): `kind` (obrót albo przesunięcie), punkt
obrotu (`pivot_x_m`, `pivot_s_m`, `pivot_z_m`), oś, `range_min` i `range_max` z `unit`, wartość spoczynkową,
`variant` oraz `limited_by` (co zatrzymuje część). Plik modelu niesie te same dane w extras węzłów (`motion_axis`,
`range_deg` albo `range_m`, `continuous_rotation`).

| Część | Ruch | Zakres (model wzorcowy) |
|---|---|---|
| `capstan_barrel` | obrót wokół osi pionowej | bez ograniczeń |
| `pump_port_brake`, `pump_starboard_brake` | wahanie wokół osi poprzecznej | ±25° |
| `rudder` | obrót wokół linii czopów | ±35°; oba rumple są jego dziećmi |
| `steering_wheel` | obrót wokół wzdłużnej osi bębna | bez ograniczeń; 1,826 obrotu na 35° steru |
| `gun_port_1` … | odrzut wzdłuż lufy, do środka | 0,4–1,5 m; mniej tam, gdzie zatrzymuje je wyposażenie |
| `gun_port_1_barrel` … | podniesienie | −5° do +10° |
| `swivel_gun_*` | obrót na trzpieniu; pochylenie w widełkach | 360°; ±30° |
| `bell` | wahanie wzdłuż statku | ±30° |
| reje i `gaff` | obrót wokół masztu (brasowanie) | patrz „Reje” niżej |
| `gunport_lid_port_1` … `_7`, `gunport_lid_starboard_1` … `_7` | obrót wokół górnego zawiasu | 0–100°; 95° albo 85° tam, gdzie zatrzymują je ławy wantowe, 75° tam, gdzie listwy kadłuba |

Uwaga: dla dział `kind = translation` wzdłuż lokalnej −X, a dla luf obrót wokół lokalnej Y; dla nich kolumny
`axis_dir_*` podają lokalną Z części (w górę), a nie oś ruchu. Użyj tabeli osi lokalnych wyżej.

## Chodzenie po pokładach

`data/deck-layout.json` zawiera wszystko, czego potrzebuje system chodzenia (model wzorcowy):

1. **Powierzchnie**: `main_deck` i `quarterdeck` jako wielokąty [x, s] (wnętrze nadburć), z wysokością
   z = centreline_z(s) − 0,120 · (x / 3,80)² (pokład rufowy 1,70 m wyżej), i te same wysokości jako siatka co 0,5 m.
   Oba marsy są płaskie (z = 11,725 i 13,219) z otworem (otwór w marsie). Ławy wantowe też są wymienione.
2. **Przeszkody**: prostokąty albo koła w rzucie z wysokością, `walkable` i `step_height_m` (zrębnice luków i linę
   kotwiczną da się przekroczyć; działa, kabestanu, masztów nie). Niektóre mają `variant`.
3. **Schody i przejścia**: schody na pokład rufowy (9 stopni po 0,191 m, 0,22 m głębokości, 0,9 m szerokości);
   drabina luku głównego i schody zejściówki prowadzą pod pokład, gdzie na razie nic nie jest zamodelowane.
4. **Wspinaczki**: łamane w górę po wantach na marsy, szczeble co 0,36 m.
5. **Krawędź burty**: wysokość relingu wzdłuż statku; poza wielokątem pokładu jest za burtą.
6. **Postać**: figura testowa, promień 0,30 m, wzrost 1,75 m. Użyj tej samej wielkości dla załogi albo powtórz test
   dojścia (rozdział 13).

Żeby postawić człowieka: znajdź powierzchnię, której wielokąt zawiera (x, s), weź jej wysokość, sprawdź przeszkody
w tym punkcie.

## Dwa warianty sterowania

Oba są w jednym pliku (model wzorcowy, `steering_drive` w `data/parameters.json`):

- `steering_wheel_variant` (widoczny domyślnie): koło na stojakach, rumpel pod pokładem rufowym, sterliny i ich
  bloki;
- `deck_tiller_variant`: rumpel pokładowy na głowicy steru z dwiema taliami rumpla.

Każdy węzeł wariantu ma w extras `variant`; dwa węzły grup mają też `visible_by_default`. Pokaż węzły jednego wariantu,
a ukryj drugiego. Tak samo postąp ze stanowiskami, przeszkodami, bryłami kolizji i odcinkami lin, które mają `variant`.
Oba rumple są dziećmi `rudder`, więc obrót steru obraca ten rumpel, który jest widoczny.

**Przełożenie koła.** Koniec rumpla przesuwa się w poprzek o L_r · sin α; tyle samo liny nawija się na bęben, więc
koło robi n = L_r · sin α / (π · D) obrotów (rozdział 09). Przy L_r = 3,0 m i D = 0,30 m 35° steru wymaga 1,826 obrotu
(`wheel_turns_for_35deg`). Proste przeliczenie liniowe (18,8° koła na stopień steru) wystarcza do gry (nasz wniosek);
dokładne jest w przykładzie policzonym niżej.

## Reje

| Reja | Opuszczona (żagle zwinięte) | Podniesiona do pozycji roboczej | Podniesienie (`working_height_dz_m`) |
|---|---|---|---|
| `fore_yard` | ±5° (sztagi) | ±35° | 0 |
| `fore_topsail_yard` | ±10° (wyblinki) | ±35° | 4,784 m |
| `fore_topgallant_yard` | ±35° | ±35° | 2,902 m |
| `main_yard` | ±10° (sztagi) | ±35° | 0 |
| `main_topsail_yard` | ±5° (wyblinki) | ±35° | 5,534 m |
| `main_topgallant_yard` | ±35° | ±35° | 3,362 m |
| `spritsail_yard` | ±35° | – | – |
| `gaff` | ±35° | – | – |

(Model wzorcowy, `data/moving-parts.csv`.) Żeby postawić żagiel, najpierw przesuń reję w górę wzdłuż osi masztu
o `working_height_dz_m`, potem brasuj ją w zakresie dla rei podniesionej. Reje jednego masztu brasuj razem
(rozdział 07).

## Liny dynamiczne

100 odcinków lin ma jeden koniec na części ruchomej (`dynamic: true`, w chwili pisania; `counts`
w `data/rigging-lines.json`): topenanty, wisiory brasów, gejtawy (także żagla gaflowego), szoty, stropy i tie, gaje i fały gafla,
brasy blindarei, talie dział, sterliny i talie rumpla, linka dzwonu.
Żeby zostały przyczepione (rozdział 07):

1. Weź ruchomy koniec we współrzędnych lokalnych (`from_local` albo `to_local`), przelicz go wzorem
   (Xb, Yb, Zb) → (Xb, Zb, −Yb) i przekształć bieżącą macierzą świata części ruchomej.
2. Drugi koniec zostaw na miejscu.
3. Przerysuj odcinek prosto albo ze zwisem, jeśli miał punkty `via` (rozdział 08).
4. Pozostałe odcinki tej samej liny (od bloku do kołka) się nie ruszają.

Odcinki, które cały czas jadą na rei (perty, strzemiona), są dziećmi rei i nie wymagają aktualizacji.

## Poziomy szczegółów

Pokazuj pełny model z bliska, LOD1 na średnią odległość i LOD2 z daleka. Rozdział 08 proponuje przełączanie przy ok.
15–60 m dla cienkich lin i przy ok. 250 m dla wszystkiego poza drzewcami i żaglami (nasz wniosek). LOD1 i LOD2 to po
jednej siatce ze wszystkimi częściami ruchomymi w spoczynku, więc przełączaj na nie tylko tam, gdzie ruchu już nie
widać, albo zostaw na wierzchu części ruchome pełnego modelu.

three.js ma gotowy obiekt LOD: `addLevel(object, distance, hysteresis)`; histereza (ułamek odległości) zapobiega
migotaniu na granicy [3].

## Bryły kolizji

Plik kolizji zawiera 36 zamkniętych, prostych brył (w chwili pisania): uproszczony kadłub z ok. 1500 trójkątów, płyty
5 cm dla pokładu głównego i rufowego, prostopadłościany wzdłuż nadburć, ośmioboczne walce masztów i bukszprytu oraz
prostopadłościany albo walce dział, kabestanu, pomp, koła, szafki kompasowej, kojców i innych dużych przedmiotów.
Nazwy ich węzłów zaczynają się od `collision_`, a dalej mają nazwę części, którą zastępują. Wczytaj plik, zostaw go niewidocznym i przekaż bryły systemowi
fizyki. Bryły wariantu sterowania mają tę samą wartość `variant`; przełączaj je razem z wariantem.

## Holowana łódź i jej maska wody

Domyślnie statek stoi na kotwicy, a łódź jest holowana za rufą na faleniu (`boat_state = towed_astern`
w `data/parameters.json`). Otwarta łódź pływająca w płaszczyźnie wody pokazuje powierzchnię morza **w środku** łodzi.
Węzeł `boat_water_mask` to naprawia: płaski, jednostronny wielokąt (normalna w górę) wzdłuż zewnętrznej strony
poszycia łodzi na jej wodnicy. Ta wodnica leży 0,27 m nad spodem stępki łodzi (`boat_waterline_m` w extras) i na
wysokości 0 w świecie, tak jak morze.

Jak tego użyć (w każdym silniku): narysuj maskę po nieprzezroczystym statku, a przed wodą, zapisując tylko do bufora
szablonu (bez koloru, bez głębi); potem rysuj wodę tylko tam, gdzie szablon nie jest ustawiony. W three.js flagi
materiału to `colorWrite`, `depthWrite`, `stencilWrite`, `stencilRef`, `stencilFunc`, `stencilZPass` [4], a renderer
trzeba utworzyć z `stencil: true`, bo domyślnie jest false [5].

## Podpięcie interakcji

| Mechanizm | Węzły | Stanowiska | Ruch i liczby |
|---|---|---|---|
| Kabestan | `capstan_barrel` | `station_capstan_1` … `_8` (ręce 1,12 m) | obrót bębna wokół pionu; 2,5 m liny na obrót (Ø 0,80 z żebrami); 16 kliknięć zapadek na obrót; 4–6 obrotów na minutę przy wybieraniu, 1–2 przy wyrywaniu (rozdział 09, tempo to nasz wniosek) |
| Pompy | `pump_port_brake`, `pump_starboard_brake` | `station_pump_1` … `_4` | dźwignia waha się ±25°; ok. 40 ruchów na minutę, ok. 100 l na minutę na pompę (rozdział 09, wtórne) |
| Działa | `gun_*`, `gun_*_barrel`, `gunport_lid_*` | 7 na działo: kapitan działa, ładowniczy, wyciorowy, 2 przy taliach bocznych, przy talii odciągowej, chłopiec z prochem | otwórz pokrywę (do jej `range_max`, 75–100°), obsługa jak w rozdziale 09 (wycior, ładunek, dobicie, wytoczenie, podsypka, celowanie, strzał); odrzut wzdłuż lokalnej −X do zakresu działa; podniesienie −5° do +10°; jeden strzał na 2–3 minuty dla 1710 r. (nasz wniosek) |
| Koło | `steering_wheel`, `rudder` | `station_wheel_1`, `_2` (ręce 1,05 m) | steruj kątem steru; kąt koła wyprowadź z niego; ster ±35° |
| Rumpel pokładowy | `deck_tiller` (dziecko `rudder`) | `station_rudder_1`, `_2` | sternik idzie razem z rumplem; ±35° |
| Dzwon | `bell` | `station_bell_1` | wahanie ±30°; uderzenia co pół godziny, za każdym razem o jedno więcej, osiem szklanek na koniec czterogodzinnej wachty (rozdział 09, wtórne) |

Najkrótszy szkic w three.js (nasz wniosek; kierunki sprawdź we własnej przeglądarce):

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const renderer = new THREE.WebGLRenderer({ antialias: true, stencil: true });
const ship = (await new GLTFLoader().loadAsync('model/snow.glb')).scene;

// wariant sterowania: pokaż węzły jednego wariantu, ukryj drugi
const active = 'steering_wheel_variant';
ship.traverse(o => { if (o.userData.variant) o.visible = o.userData.variant === active; });

// kabestan: obraca się wokół swojej lokalnej +Y (pion); jego obrót spoczynkowy to tożsamość
const capstan = ship.getObjectByName('capstan_barrel');
function turnCapstan(deg) { capstan.rotateY(THREE.MathUtils.degToRad(deg)); }

// ster i koło: oba obracają się wokół lokalnej +Y (lokalnej Z w plikach danych)
const rudder = ship.getObjectByName('rudder');
const wheel = ship.getObjectByName('steering_wheel');
const r0 = rudder.quaternion.clone(), w0 = wheel.quaternion.clone(), up = new THREE.Vector3(0, 1, 0);
function setRudder(deg) {
  const a = THREE.MathUtils.degToRad(deg);
  rudder.quaternion.copy(r0).multiply(new THREE.Quaternion().setFromAxisAngle(up, a));
  const turns = 3.0 * Math.sin(a) / (Math.PI * 0.30);            // 1,826 przy 35°
  wheel.quaternion.copy(w0).multiply(new THREE.Quaternion().setFromAxisAngle(up, turns * 2 * Math.PI));
}

// maska wody holowanej łodzi: tylko szablon, potem woda tam, gdzie szablon nie jest ustawiony
const mask = ship.getObjectByName('boat_water_mask');
mask.material = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false, stencilWrite: true,
  stencilRef: 1, stencilZPass: THREE.ReplaceStencilOp });
mask.renderOrder = 1;
// water.material.stencilWrite = true; water.material.stencilRef = 1;
// water.material.stencilFunc = THREE.NotEqualStencilFunc; water.renderOrder = 2;
```

## Przykład policzony: jeden obrót koła

1. Jeden pełny obrót: n = 1. Z n = L_r · sin α / (π · D): sin α = 1 × π × 0,30 / 3,0 = 0,314, więc α = 18,3°.
2. Przeliczenie liniowe daje 35° / 1,826 = 19,2° na obrót: o 0,9° więcej, czego żaden gracz nie zauważy.
3. Wychylenie do oporu (35°) wymaga 1,826 obrotu, więc od oporu do oporu jest 3,65 obrotu (nasze obliczenie, jak
   w rozdziale 09).
4. Sternik stoi na `station_wheel_1`: stopy w x = 0,5, s = −12,10, z = 3,005, czyli (0,5; 3,005; −12,10) w grze;
   `facing_deg` = 0, więc patrzy ku dziobowi (model wzorcowy, `data/stations.csv`).

## Zaplanowane, jeszcze nie w modelu

To jest zaplanowane; nie podajemy terminów. Niżej opisujemy tylko, jak model jest na to przygotowany.

| Temat | Stan obecny | Jak model jest przygotowany (model wzorcowy) |
|---|---|---|
| **Żagle postawione** | wszystkie żagle zwinięte (`sails_set = false`); statek stoi na kotwicy | każda reja ma wysokość roboczą i zakres brasowania po podniesieniu; wymiary żagli postawionych są oszacowane w `set_sail_estimates` (`data/parameters.json`) i w rozdziale 08; żagle zwinięte to węzły-dzieci swoich rej, więc można je podmienić na postawione |
| **Wnętrze pod pokładem** | ładownia i kabina nie są zamodelowane | drabina luku głównego i schody zejściówki są w `data/deck-layout.json` razem z dolnymi końcami; wymiary konstrukcji kadłuba są w rozdziale 03 |
| **Zniszczenia od pocisków**: dziury i przecieki | kadłub i pokład to scalone siatki statyczne | powierzchnia kadłuba i jej grubość są znane z `data/offsets.csv` i `planking_thickness_m`, więc punkt trafienia można zamienić na dziurę o znanej głębokości pod albo nad wodą |
| pożar | brak | materiały są nazwane według rodzaju (drewno, farba, lina, płótno), więc system ognia może rozpoznać, co się pali |
| zerwane liny | brak | każdy odcinek liny to osobny, nazwany wpis w `data/rigging-lines.json` z końcami, średnicą i miejscem obłożenia, więc jeden odcinek można usunąć albo poluzować |
| złamane drzewca | brak | każda część masztu (kolumna, stenga, bramstenga) to osobny wiersz w `data/spars.csv` z końcami i wysokościami marsów i ezelhoftów; reje i gafel to osobne węzły; liny zapisują drzewce, na którym wiszą (`parent`) |
| **Liny na wietrze** | liny są statyczne, zwisają tylko od ciężaru | odcinki dynamiczne znają już swoje ruchome końce; zwis to wzór zależny od rozpiętości i luzu (rozdział 08), więc wiatr można dodać jako obciążenie boczne |

## Sprawdź się

- [ ] Przeliczam punkty danych [x, s, z] na (x, z, s), a dziób wskazuje +Z.
- [ ] Używam angielskich nazw węzłów z `data/names-map.csv` i szukam lin dynamicznych po ich extras.
- [ ] Stawiam ludzi na stanowiskach i obracam ich o `facing_deg` wokół +Y.
- [ ] Każda część ruchoma obraca się wokół własnej osi w swoim zakresie.
- [ ] Widoczny jest tylko jeden wariant sterowania, razem z jego stanowiskami, przeszkodami i bryłami kolizji.
- [ ] Reje są podnoszone, zanim brasuję je poza zakres dla rei opuszczonej.
- [ ] Liny dynamiczne idą za rejami, działami i rumplami.
- [ ] LOD przełącza się tylko tam, gdzie ruchu nie widać.
- [ ] Morze nie pokazuje się wewnątrz holowanej łodzi.

## Typowe błędy

1. Odczytanie [x, s, z] jako (X, Y, Z): statek leży na burcie.
2. Użycie osi lokalnych z plików danych jako osi lokalnych glTF bez obrotu (X, Z, −Y).
3. Pokazanie obu wariantów sterowania naraz.
4. Brasowanie zwiniętych rej do 35° i przepychanie ich przez sztagi.
5. Obrócenie rei i zostawienie jej topenant i brasów w starym miejscu.
6. Renderowanie pliku kolizji.
7. Zapomnienie o `stencil: true` w three.js, przez co maska wody nic nie robi.

## Źródła

1. Khronos Group, *glTF 2.0 Specification* https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html i schemat
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/extras.schema.json (osie, metry,
   extras jako dane aplikacji).
2. three.js, kod `GLTFLoader` https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/jsm/loaders/GLTFLoader.js
   (extras kopiowane do `userData`; tekstury koloru bazowego ustawiane na sRGB; nazwy węzłów czyszczone przez
   `PropertyBinding.sanitizeNodeName`).
3. three.js, kod `LOD` https://raw.githubusercontent.com/mrdoob/three.js/dev/src/objects/LOD.js
   (`addLevel(object, distance, hysteresis)`).
4. three.js, kod `Material` https://raw.githubusercontent.com/mrdoob/three.js/dev/src/materials/Material.js (flagi
   szablonu i zapisu).
5. three.js, kod `WebGLRenderer` https://raw.githubusercontent.com/mrdoob/three.js/dev/src/renderers/WebGLRenderer.js
   (`stencil` domyślnie false).

## Terminy użyte w rozdziale

| Angielski | Polski | Objaśnienie |
|---|---|---|
| engine | silnik gry | Program, który rysuje grę i wykonuje jej reguły. |
| node, scene graph | węzeł, drzewo sceny | Element sceny 3D; ich drzewo. |
| extras, userData | extras, userData | Wolne dane na węźle; ich nazwa w three.js. |
| work station | stanowisko czynności | Miejsce, gdzie człowiek stoi przy jednej pracy. |
| facing direction | kierunek patrzenia | Gdzie człowiek patrzy. |
| variant | wariant | Jedna z dwóch wersji części w jednym pliku. |
| dynamic rope | lina dynamiczna | Odcinek liny z końcem na części ruchomej. |
| level of detail (LOD) | poziom szczegółów | Prostsza kopia na odległość. |
| hysteresis | histereza | Margines, który zapobiega przełączaniu tam i z powrotem. |
| collision solid | bryła kolizji | Niewidoczny prosty kształt do testów styku. |
| stencil buffer | bufor szablonu | Znacznik pikseli do maskowania rysowania. |
| water mask | maska wody | Wielokąt, który nie wpuszcza morza do łodzi. |
| painter | faleń | Lina, na której łódź jest holowana albo przycumowana. |
| bracing, hoisting | brasowanie, podnoszenie (rei) | Obracanie rei; podnoszenie jej na maszcie. |
