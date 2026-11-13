# 10. Budowa statku w Blenderze

## Po co ten etap

Model 3D z katalogu `model/` nie powstał w ręcznym modelowaniu. To wynik zestawu skryptów Pythona dla Blendera,
które leżą w `blender/`. Skrypty czytają liczby modelu wzorcowego (tabelę rzędnych, reguły drzewc, listę lin, układ
pokładu), budują z nich każdą część, sprawdzają wynik i eksportują go do plików glTF w postaci binarnej (GLB). Ten
rozdział pokazuje, jak uruchomić je samemu i jak się odnaleźć w kodzie.

Po tym rozdziale będziesz mieć:

- pełną budowę statku w `build/`: plik `.blend`, plik GLB z dwoma poziomami szczegółów i bryłami kolizji, raport
  kontroli `kontrola.json` i rendery kontrolne;
- rysunki i pliki danych zrobione od nowa z twojej budowy, w wybranym katalogu;
- cztery pliki z `model/` zrobione z twojej budowy, z angielskimi nazwami;
- słowniczek najczęstszych słów z kodu z ich angielskimi odpowiednikami (dla czytelników bez polskiego i do szukania
  w kodzie).

Skrypty są napisane po polsku: nazwy modułów, zmiennych i komentarze. Publikujemy je w tej postaci, w jakiej
zbudowały model, żeby czytany kod był tym samym kodem, który go zrobił. Komentarze odsyłają do rozdziałów tego
przewodnika („rozdział 05”), w których opisano, co dany etap buduje i dlaczego.

Jeśli chcesz zmienić statek, przeczytaj [rozdział 12](12-designing-other-ships.md); co mierzą kontrole, opisuje
[rozdział 13](13-3d-quality-checklist.md). Oznaczenia pewności objaśnia [rozdział 01](01-ship-type-and-era.md);
liczby w tym rozdziale to wartości **modelu wzorcowego** z naszych własnych uruchomień.

## Pojęcia

- **Blender bez okna**: Blender uruchomiony z `-b` wykonuje skrypt Pythona i nie otwiera okna. Tak działa każdy krok
  tego rozdziału.
- **`bpy`**: moduł Pythona wbudowany w Blendera. Skrypty, które go importują, działają tylko w Blenderze; pozostałe
  w każdym Pythonie 3.
- **Ustawienia fabryczne** (`--factory-startup`): Blender startuje bez twoich preferencji i dodatków, więc budowa nie
  zależy od tego, jak masz go skonfigurowanego.
- **Generator**: tu zestaw skryptów, który buduje statek z liczb. Uruchomiony ponownie z tymi samymi liczbami daje ten
  sam plik.
- **Etap**: jedna część budowy, np. kadłub, drzewca albo olinowanie ruchome. Każdy etap to jeden moduł z funkcją
  `zbuduj(ctx)`.
- **`ctx`**: słownik Pythona przekazywany z etapu do etapu. Są w nim parametry, zbudowane już obiekty i rejestr lin.
- **Tekstura proceduralna**: obraz policzony przez skrypt (szum, układ desek), a nie sfotografowany.
- **CC0**: dedykacja do domeny publicznej Creative Commons. Zasobu CC0 można używać do wszystkiego bez pytania
  i bez podawania autora [3].
- **GLB**: jednoplikowa, binarna postać glTF 2.0 [1]. **Węzeł**, **siatka**, **materiał** i **obraz** to nazwane
  części pliku glTF; **extras** to wolne pole na dane aplikacji [1].

## Wymagania

| Co | Wersja, której używaliśmy | Do czego |
|---|---|---|
| Blender | 5.2 | budowa, model do rysunków, próba wczytania; innych wersji nie sprawdzaliśmy |
| Python 3 w wierszu poleceń jako `python` | 3.14 z numpy 2.5 i Pillow 13 | tekstury (`tekstury*.py`), obraz planu pokładu, pliki danych, narzędzie zamiany nazw |
| Chrome albo Edge (niekonieczne) | dowolna nowa | podglądy PNG i zestawy PDF rysunków; bez przeglądarki `rysunki.py` zapisuje tylko SVG |
| Tekstury Poly Haven (niekonieczne) | 2K, JPG | zestaw tekstur fotograficznych (niżej, „Tekstury”) |
| Wolne miejsce na dysku | ok. 0,5 GB | `build/` po obu budowach, renderach i próbnym przebiegu rysunków (u nas 421 MB) |

Skrypty budowy same wywołują `python` w krokach tekstur, więc polecenie `python` musi uruchamiać Pythona 3 z numpy
i Pillow (`python -m pip install numpy pillow`). Własny Python Blendera służy tylko krokom, które potrzebują `bpy`.

Wszystkie polecenia niżej uruchamia się z katalogu głównego tego repozytorium. `blender` oznacza program Blender:
w Windows podaj w cudzysłowie pełną ścieżkę do `blender.exe` z katalogu instalacji Blendera; w Linuksie i macOS
polecenie `blender` albo ścieżkę do programu w katalogu aplikacji.

## Krok po kroku: jedna budowa

### 1. Budowa z teksturami proceduralnymi

```
blender -b --factory-startup --python blender/buduj.py -- --glb --rendery none --out build/proceduralne
```

Polecenie buduje statek, zapisuje `build/proceduralne/bryg.blend`, eksportuje pliki GLB i przeprowadza wszystkie
kontrole; z `--rendery none` pomija rendery. U nas trwało to 4 minuty; `build/proceduralne/bryg.glb` ma te same 330 węzłów i 230 419 trójkątów co budowa z CC0, ale jest mniejszy (29,2 MB zamiast 31,0 MB), a kontrole dają te same 34 × `tak`, 2 × `info`, 0 × `nie`.

### 2. Budowa z fotograficznymi teksturami CC0 (jak pliki w `model/`)

```
blender -b --factory-startup --python blender/buduj.py -- --glb --rendery all --tekstury-cc0 path/to/polyhaven
```

`path/to/polyhaven` to katalog, w którym leżą tekstury Poly Haven (niżej, „Tekstury”). Tym poleceniem powstały pliki
w `model/`. U nas sama budowa trwała 3 minuty, a całe uruchomienie z kontrolami i renderami ok. 8 minut.

### 3. Opcje

Wszystko po `--` należy do skryptu. Opcje z wartością:

| Opcja | Wartości | Domyślnie | Znaczenie |
|---|---|---|---|
| `--out` | katalog | `build` | dokąd trafiają wyniki |
| `--rendery` | `all`, `none`, `detale`, `porownanie` albo lista nazw ujęć po przecinku | `all` | które rendery kontrolne zrobić |
| `--tekstury-cc0` | katalog | brak | użyj zestawu tekstur Poly Haven z tego katalogu |
| `--schemat` | `a`, `b` | `a` | schemat malowania: `a` z epoki (białe dno, olejowane burty, czerń i ochra), `b` czarny kadłub |
| `--etapy` | lista po przecinku | wszystkie | zbuduj tylko część etapów, np. `kadlub,poklad,rufa_dziob` |
| `--naped` | `kolo`, `rumpel` | `kolo` | napęd steru widoczny domyślnie: koło sterowe albo rumpel na pokładzie |
| `--lodz` | `za_rufa`, `na_pokladzie`, `brak` | `za_rufa` | łódź holowana za rufą, na pokładzie albo bez łodzi |
| `--snow` | `0`, `1` | `1` | ożaglowanie snow (maszt gaflowy za grotmasztem) albo zwykły bryg |
| `--dzialo-polyhaven` | plik | brak | model działa CC0 z tego pliku glTF zamiast naszych dział |
| `--statek` | nazwa | `BRYG` | który statek z `parametry.py` zbudować |

Przełączniki bez wartości:

| Przełącznik | Znaczenie |
|---|---|
| `--glb` | eksport plików GLB, poziomów szczegółów i brył kolizji, potem kontrole |
| `--kontrola` | kontrole bez eksportu |
| `--bez-blend` | bez zapisu pliku `.blend` |
| `--bez-ao` | bez wypalania okluzji otoczenia (szybciej, ale bez przyciemnienia w zakamarkach) |
| `--nowe-tekstury` | zrób tekstury desek CC0 od nowa, nawet jeśli już są |

Budowa bez `--glb` kończy się na pliku `.blend` i renderach.

## Budowa etap po etapie

`buduj.py` uruchamia etapy w tej kolejności. Obok nazwy modułu podajemy jej znaczenie po angielsku, bo tak opisuje
ją wersja angielska tego rozdziału.

| # | Moduł | Znaczenie (ang.) | Co robi |
|---|---|---|---|
| 0 | `tekstury.py` | textures | proceduralne, kafelkujące tekstury (pokład, burta, farba, drewno, żelazo, lina, płótno, okno); zwykły Python, tylko gdy `build/tekstury/` jest pusty |
| 0 | `tekstury_cc0.py`, `tekstury_deski.py` | CC0 textures, plank textures | z `--tekstury-cc0`: kopie robocze zdjęć Poly Haven i nasze atlasy desek (`td_*`) |
| 1 | `materialy.py` | materials | materiały Blendera ułożone tak, żeby eksport glTF zapisał je poprawnie |
| 2 | `rzedne.py`, `kadlub.py` | offsets, hull | powierzchnia kadłuba z tabeli rzędnych, berghołty, nadburcia, pokłady, grodzie, furty; stępka, dziobnica, tylnica; ster |
| 3 | `poklad.py` | deck | pokrywa relingu, ściek, wierzchołki wręgów, listwy, szpigaty, pokrywy furt, schody, balustrada progu |
| 4 | `rufa_dziob.py` | stern and bow | okna i snycerka rufy, latarnia; kolano galionu, zwój, relingi galionu, kotbelki, kluzy |
| 5 | `drzewca.py` | spars | maszty, marsy, ezelhofty, stengi, maszt snow, bukszpryt, reje, gafel (reguły Steela, rozdział 05) |
| 6 | `olinowanie.py` | (standing) rigging | ławy wantowe, jufersy, wanty, talrepy, wyblinki, podwantki, sztagi, paduny, olinowanie bukszprytu (rozdział 06) |
| 7 | `wyposazenie.py`, `sterowanie.py` | fittings, steering | działa, kabestan, pompy, luki, nagielbanki i kołkownice, warianty koła i rumpla, łódź, dzwon, kotwice (rozdział 09) |
| 8 | `ruchome.py` | running (rigging) | topenanty, brasy, gejtawy, szoty, fały, liny gafla, buchty na kołkach (rozdział 07) |
| 9 | `zagle.py` | sails | żagle zwinięte na rejach, żagiel gaflowy podgarnięty, sztaksle sklarowane (rozdział 08) |
| 10 | `przenikanie.py` | interpenetration | ograniczenia ruchu z geometrii (pokrywy furt, odrzut dział), później scalanie brył i zakres brasowania rej |
| 11 | `chodzenie.py` | walking | powierzchnie do chodzenia, przeszkody, schody, stanowiska, test chodzenia (`bryg_poklad.json`, węzły `stan_*`) |
| 12 | `kadlub.py` (`zabrudzenia`) | hull (dirt) | zabrudzenia w kolorach wierzchołków: pas przy wodnicy, zacieki pod furtami i szpigatami |
| 13 | `przenikanie.py` (`scal_bryly`, `porzadki`) | interpenetration | jedna czysta bryła na obiekt; usunięte zdublowane wierzchołki, ściany o zerowym polu, luźne części |
| 14 | `olinowanie.py` (`zamocuj_konce`, `realizuj`) | rigging | końce lin dociągnięte do części, na których się kończą; rurki lin z rejestru |
| 15 | `eksport.py` | export | części ruchome jako osobne węzły, reszta scalona w siatki statyczne; wypalona okluzja; `bryg.glb` |
| 16 | `lod.py` | level of detail | `bryg_lod1.glb`, `bryg_lod2.glb` i bryły kolizji `bryg_kolizja.glb` |
| 17 | `kontrola.py`, `praktyki.py` | check, good practice | raport `kontrola.json` (niżej, „Kontrole”) |
| 18 | `rendery.py`, `plan_pokladu.py` | renders, deck plan | rendery kontrolne w `build/rendery/`, obraz planu pokładu z danymi chodzenia |
| 19 | `kontrola_glb.py` | GLB check | plik po eksporcie wobec źródła: obrazy, kolory, rendery z wczytanego GLB |

Moduły pomocnicze: `parametry.py` (parameters, niżej), `narzedzia.py` i `narzedzia_math.py` (tools: budowniczy siatek,
rurki, krzywe), `deski.py` (planks: cięcie poszycia wzdłuż szwów), `projekt_rzednych.py` (offsets design: przelicza
tabelę mierzoną po wręgach na tabelę generatora), `plansza.py` (contact sheet: plansza renderów).

## Gdzie są parametry i jak je zmienić

Wszystkie liczby statku są w jednym pliku, `blender/parametry.py`, w zwykłych słownikach Pythona:

| Słownik | Zawartość | Dane publiczne |
|---|---|---|
| `KADLUB` | kadłub: linia stępki, profil dziobu i rufy, linia pokładu, wypukłość, wysokości relingu, berghołty, furty | `data/parameters.json`, grupa `hull` |
| `LINIE_WREGI`, `RZEDNE_*` | tabela rzędnych po wręgach i tabela generatora | `data/offsets.csv` |
| `DRZEWCA` | drzewca z reguł Steela, położenia, pochylenia, wznios bukszprytu | `data/spars.csv` |
| `OLINOWANIE` | liczby i średnice lin stałych | `data/rigging-summary.csv` |
| `UKLAD` | układ pokładu: kabestan, pompy, luki, łódź, sterowanie, działa | `data/deck-layout.json` |
| `SCHEMATY`, `MATERIALY`, `MATERIALY_CC0`, `MATERIALY_TD` | schematy malowania i materiały | `data/parameters.json` |
| `STATKI` | nazwane definicje statków (`BRYG`) | – |

`data/names-map.csv` (kategoria `parameter`) podaje angielską nazwę każdego klucza, a `data/SCHEMA.pl.md` jednostkę
i znaczenie. Żeby zbudować inny statek, skopiuj definicję `BRYG`, zmień liczby i podaj nazwę w `--statek`. Które
liczby zmieniać, w jakiej kolejności i co potem sprawdzić, opisuje [rozdział 12](12-designing-other-ships.md). Po
zmianie tabeli po wręgach (`LINIE_WREGI`) tabelę generatora w `parametry.py` przelicza `projekt_rzednych.py`:

```
python blender/projekt_rzednych.py
```

Bez opcji tylko wypisuje nową tabelę; z `--zapisz` przepisuje ją w `parametry.py` (blok między `# >>> RZEDNE`
a `# <<< RZEDNE`).

## Co powstaje w `build/`

| Plik albo katalog | Co to jest |
|---|---|
| `bryg.blend` | scena Blendera przed eksportem, ze wszystkimi obiektami osobno |
| `bryg.glb` | główny plik GLB (z polskimi nazwami) |
| `bryg_lod1.glb`, `bryg_lod2.glb` | poziomy szczegółów: ok. 50 % i ok. 5 % trójkątów |
| `bryg_kolizja.glb` | 36 brył kolizji, węzły `kolizja_*` |
| `kontrola.json` | raport kontroli |
| `parametry.json` | wszystkie parametry jako JSON |
| `liny.json` | każda lina: grupa, średnica, materiał, końce, długość |
| `bryg_poklad.json` | dane do chodzenia i stanowiska |
| `rendery/` | rendery kontrolne i obraz planu pokładu |
| `tekstury/`, `tekstury_cc0/` | kopie robocze tekstur |

Pliki w `build/` mają polskie nazwy generatora. Nazwy w `model/` powstają z nich przez narzędzie zamiany nazw (niżej).
`build/` jest wpisany do `.gitignore`.

## Kontrole

`kontrola.py` zapisuje `build/kontrola.json`. Najważniejsze części:

| Klucz | Co zawiera |
|---|---|
| `dobre_praktyki` | tabela dobrych praktyk: 36 kryteriów, każde z `wynik` = `tak`, `nie` albo `info` i liczbami |
| `wymiary`, `maszty`, `reje` | wymiary główne, maszty i reje zmierzone na modelu |
| `kadlub_powloka` | powłoka kadłuba: krawędzie brzegowe i nierozmaitościowe, normalne, objętość, symetria |
| `gestosc_tekseli_px_m` | gęstość tekseli na materiał |
| `chodzenie`, `stanowiska_liczba` | test chodzenia i liczba stanowisk |
| `symetria_lin` | symetria lin (pary lewa–prawa burta) |
| `konce_lin` | końce lin: każdy musi być zamocowany (`wiszace` – wiszące) |
| `bloki` | bloki: każdy musi być czegoś uczepiony (`bez_zaczepu`) |
| `przenikanie` | przenikanie brył: pary ponad progiem 5 mm (`zgloszone_ponad_prog`) |
| `zakresy_ruchu`, `ograniczenia_ruchu` | części ruchome sprawdzone w całym zakresie; znalezione ograniczenia |
| `glb`, `kontrola_glb` | plik po eksporcie wczytany ponownie i porównany ze źródłem |

Każdą kontrolę objaśnia [rozdział 13](13-3d-quality-checklist.md). Trzy doszły późno i warto je znać z nazwy:

- **końce lin** (`konce_lin`, rozdział 13, E5): każdy koniec każdej liny musi leżeć najdalej 1 cm od innej części,
  w niej albo na innej linie;
- **bloki** (`bloki`, E6): każdy blok musi dotykać bryły, wisieć na smołowanym wisiorze, siedzieć na prostej, napiętej
  talii albo mieć strop;
- **skręcone rurki** (kryterium „brak skręconych rurek lin”, D8): w żadnym czworokącie rurki liny przeciwległe
  krawędzie nie mogą się krzyżować.

Dobra budowa ma 0 kryteriów z `nie`. Nasza budowa z teksturami CC0 dała 34 × `tak`, 2 × `info`, 0 × `nie`;
0 wiszących końców lin na 2136; 0 bloków bez zaczepu na 105; 0 par przenikania ponad próg.

## Tekstury: proceduralne i CC0

Bez `--tekstury-cc0` każdy materiał używa tekstur proceduralnych z `tekstury.py`. Niczego nie trzeba pobierać.

Z `--tekstury-cc0 KATALOG` pokład, poszycie burt, farby, drewno drzewc i wyposażenia, żelazo i płótno dostają zdjęcia
z Poly Haven [2], wszystkie na licencji CC0 [3]; liny i szkło zostają proceduralne. Zdjęć nie ma w tym repozytorium.
`blender/tekstury_cc0_spis.json` wymienia wszystkie 18 zasobów, które mieliśmy, ze stroną każdego zasobu, autorami,
licencją, rzeczywistym rozmiarem kafla i nazwami plików. Generator używa ośmiu z nich (`"uzywany": true`):
`wood_planks_grey`, `brown_planks_09`, `brown_planks_03`, `black_painted_planks`, `white_planks_clean`,
`oak_veneer_01`, `rough_linen`, `rusty_metal_04`.

Jak przygotować katalog:

1. Otwórz stronę każdego używanego zasobu (np. https://polyhaven.com/a/wood_planks_grey).
2. Pobierz w rozdzielczości 2K, w formacie JPG, mapy **Diffuse**, **Normal (GL)** i **AO/Rough/Metal**. Poly Haven
   nazywa je `<id>_diff_2k.jpg`, `<id>_nor_gl_2k.jpg` i `<id>_arm_2k.jpg`.
3. Połóż trzy pliki każdego zasobu w podkatalogu o nazwie identyfikatora zasobu:

```
polyhaven/
  wood_planks_grey/
    wood_planks_grey_diff_2k.jpg
    wood_planks_grey_nor_gl_2k.jpg
    wood_planks_grey_arm_2k.jpg
  brown_planks_09/
    ...
```

4. Uruchom budowę z `--tekstury-cc0 polyhaven` (albo ścieżką do katalogu).

Jeśli katalog ma własny `_spis.json` (z tymi samymi wpisami co spis), generator bierze jego; jeśli nie, bierze spis
z `blender/`. Pobranych plików budowa nigdy nie zmienia: kopie robocze (obrócone słoje, odbarwione farby i płótno,
nasze atlasy desek `td_*`) zapisuje w `build/tekstury_cc0/`. Po zmianie tekstury usuń ten katalog albo dodaj
`--nowe-tekstury`.

## Rysunki i dane

`blender/rysunki.py` robi z gotowej budowy pliki danych `data/` i arkusze `plans/`:

1. `model_rysunkowy.py` uruchamia generator jeszcze raz do etapu żagli, w pamięci, i zapisuje liczby oraz rejestr lin;
   potem rzutuje siatki z `bryg.blend` z usuwaniem linii zasłoniętych;
2. `dane_publiczne.py` zapisuje `data/` z angielskimi nazwami (`nazwy_publiczne.py`);
3. `arkusze_*.py` (`kadlub`, `konstrukcja`, `poklad`, `wyposazenie`, `takielunek`) rysują arkusze SVG po angielsku
   i po polsku;
4. Chrome albo Edge bez okna robi podglądy PNG i zestawy PDF;
5. `kontrola_publiczna.py` porównuje dane z modelem i szuka polskich słów, które zostały w danych i na angielskich
   arkuszach.

Domyślnie `rysunki.py` zapisuje do `data/` i `plans/` repozytorium. Żeby spróbować bez ich nadpisywania, podaj inny
katalog w `--publiczne`:

```
blender -b --factory-startup --python blender/rysunki.py -- --migawka --publiczne build/rysunki_test
```

`--migawka` najpierw kopiuje wyniki budowy i moduły generatora do `build/rysunki_robocze/`, więc rysunki zawsze
powstają z jednego, spójnego stanu. U nas trwało to nieco ponad minutę i skończyło się wierszem
`KONTROLA DANYCH: błędów 0`. Inne opcje: `--tylko lines-plan,deck-plan` (tylko te arkusze), `--bez-png`,
`--bez-pdf`, `--bez-danych`.

## Angielskie nazwy: narzędzie zamiany nazw i pliki w `model/`

`blender/nazwy_na_angielskie.py` to zwykły Python 3, bez Blendera i bez dodatkowych pakietów. Czyta plik GLB
i `data/names-map.csv` i zapisuje kopię, w której nazwy węzłów, siatek, materiałów i obrazów, klucze w extras i znane
teksty w extras są angielskie. Zmienia tylko część JSON pliku; część binarna (geometria i obrazy) przechodzi bajt
w bajt.

Tłumaczenie bierze najpierw z `data/names-map.csv` (kategoria zależy od miejsca nazwy: węzeł szuka w `glb_node`,
`collision_node` albo `object`; klucz extras w `glb_extras_key` albo `json_key`; opis osi ruchu w `text`), potem
z reguł w `nazwy_publiczne.py` (np. `lina_dyn_dziala_904_glb` daje `rope_dynamic_gun_tackle_904_glb`: grupa i numer
ze wzorca `lina_dyn_<grupa>_<numer>`), a na końcu z krótkiej listy w samym narzędziu (`DODATKI`) dla nazw, których
nie ma w danych publicznych: trzech wspólnych siatek, materiałów scalonych `<materiał>__<grupa>`, nazw obrazów i trzech
tekstów węzłów pomocniczych. Narzędzie jest ścisłe: gdy jakaś nazwa, klucz albo tekst nie ma angielskiego
odpowiednika, niczego nie zapisuje, wypisuje braki i kończy się kodem wyjścia 1. Na końcu sprawdza własny wynik: brak
polskich liter, brak polskich słów z mapy, brak dwóch różnych węzłów o tej samej nazwie angielskiej.

Cztery pliki w `model/` powstały tak z naszej budowy:

```
python blender/nazwy_na_angielskie.py build/bryg.glb model/snow.glb
python blender/nazwy_na_angielskie.py build/bryg_lod1.glb model/snow_lod1.glb
python blender/nazwy_na_angielskie.py build/bryg_lod2.glb model/snow_lod2.glb
python blender/nazwy_na_angielskie.py build/bryg_kolizja.glb model/snow_collision.glb
```

Samo sprawdzenie pliku: `python blender/nazwy_na_angielskie.py --sprawdz model/snow.glb`.

| Plik | Węzły | Trójkąty | Zawartość |
|---|---|---|---|
| `model/snow.glb` | 330 | 230 419 | pełny model: części ruchome jako osobne węzły z osiami i zakresami w extras, dwie siatki statyczne, 142 węzły stanowisk |
| `model/snow_lod1.glb` | 1 | 119 626 | jedna siatka, ok. 50 % trójkątów, tekstury 1K |
| `model/snow_lod2.glb` | 1 | 11 019 | jedna siatka, ok. 5 %, bez wyblinek, talrepów i olinowania ruchomego, tekstury 512 px |
| `model/snow_collision.glb` | 36 | 3 286 | bryły kolizji, węzły `collision_*` |

(Trójkąty policzone z buforów indeksów pliku; w chwili pisania.)

Jeśli zmienisz generator i zrobi on części o nowych nazwach, uruchom najpierw `rysunki.py`, żeby `data/names-map.csv`
dostał nowe nazwy, a dopiero potem narzędzie zamiany nazw.

## Niezależne testy w `blender/niezalezne/`

Tych sześć skryptów nie korzysta z generatora: otwiera gotowy plik `.blend` albo GLB i sprawdza go po swojemu, jako
drugą opinię obok kontroli z `kontrola.json`.

| Skrypt | Znaczenie (ang.) | Co sprawdza | Wynik |
|---|---|---|---|
| `konce_lin.py` | rope ends | każdy koniec każdej rurki liny dotyka części, leży w bryle albo przecina część blisko końca | plik JSON |
| `bloki_wiszace.py` | hanging blocks | zespoły części bloków, które nie dotykają bryły, liny stałej ani kończącego się na nich smołowanego wisiora | plik JSON |
| `przenikanie.py` | interpenetration | pary spójnych części, których trójkąty się przecinają, z głębokością | plik JSON |
| `skrecone.py` | twisted | czworokąty, których dwa trójkąty patrzą w przeciwne strony (rurka „klepsydra”) | tabela na wyjściu |
| `igly.py` | needles | trójkąty dłuższe niż 40 × ich wysokość, na płaskich i na gładkich powierzchniach | sumy na wyjściu |
| `zblizenia2.py` | close-ups (2) | rendery zbliżeń z pliku GLB według listy położeń kamery | pliki PNG |

Uruchamia się je tak (każdy otwiera plik podany przed `--python`):

```
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/konce_lin.py -- build/test_konce_lin.json
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/bloki_wiszace.py -- build/test_bloki.json
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/przenikanie.py -- build/test_przenikanie.json
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/skrecone.py
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/igly.py
blender -b --factory-startup --python blender/niezalezne/zblizenia2.py -- model/snow.glb build/zblizenia build/kadry.json
```

`--disable-autoexec` nie pozwala uruchomić skryptów zapisanych w pliku `.blend`; używaj go dla każdego pliku, którego
nie zrobiłeś sam. Opcjonalna ostatnia liczba w trzech pierwszych poleceniach to tolerancja w metrach. `build/kadry.json`
dla `zblizenia2.py` to lista ujęć `{"nazwa": [[cel x, y, z], [kamera x, y, z], ogniskowa_mm], ...}` we współrzędnych
pliku `.blend`.
Nasze uruchomienie na `build/bryg.blend` dało: `konce_lin.py` – 0 z 1523 końców rurek w powietrzu (tolerancja 3 cm);
`bloki_wiszace.py` – 96 zespołów bloków, wszystkie zamocowane (71 dotyka bryły, 23 wisi na linie stałej albo wisiorze,
2 są schowane w bryle), żadnego podejrzanego; `przenikanie.py` – 505 par obiektów z przecinającymi się trójkątami. Ten
test nie ma listy połączeń zamierzonych, więc większość par jest zamierzona (najgłębsze to żagle zwinięte leżące
w swoich rejach); czytaj go razem z częścią `przenikanie` w `kontrola.json`. `skrecone.py` znalazł 71 z 93 522
czworokątów, których trójkąty patrzą w przeciwne strony, głównie małe ściany na ostrych zagięciach: to miara
ostrzejsza niż test krzyżujących się krawędzi w `kontrola.json`, który przechodzi. `igly.py` naliczył 4772 trójkąty
igłowe, z tego 831 na powierzchniach gładko cieniowanych. `zblizenia2.py` zapisał dwa ujęcia z `build/kadry.json`
do `build/zblizenia/`.

## Ograniczenia

- Sprawdzone tylko z Blenderem 5.2 w Windows. Skrypty używają `os.path` i powinny działać w Linuksie i macOS, ale tego
  nie próbowaliśmy. Inne wersje Blendera mogą zmienić eksport glTF albo API Pythona.
- Jedna definicja statku (`BRYG`, snow z ok. 1710 r.). Inne statki wymagają nowych liczb (rozdział 12), a inna rufa,
  inny galion czy inne ożaglowanie – nowego kodu.
- Pełna budowa trwa ok. 8 minut; `build/` z obiema budowami, renderami i rysunkami zajmuje ok. 0,5 GB.
- Budowa bez tekstur CC0 daje inne obrazy i inny rozmiar pliku niż `model/`; geometria jest ta sama.
- Narzędzie zamiany nazw zna nazwy, które robi ten generator. Nowe części wymagają nowych wierszy w
  `data/names-map.csv` (robi je `rysunki.py`) albo na liście `DODATKI` narzędzia.
- Kod jest po polsku. Identyfikatory są pisane bez polskich liter (`kadlub` zamiast *kadłub*), komentarze – z nimi.

## Czytanie kodu: polskie słowa

Słowniczek jest przede wszystkim dla czytelnika wersji angielskiej, ale przydaje się też do szukania w kodzie, bo
identyfikatory nie mają polskich liter: ą → a, ć → c, ę → e, ł → l, ń → n, ó → o, ś → s, ź i ż → z. `L` i `P` za
nazwą to burty: lewa (*port*) i prawa (*starboard*). Osie statku: `s` (wzdłuż, + ku dziobowi), `x` (w poprzek,
+ ku lewej burcie), `z` (w górę od wodnicy konstrukcyjnej).

| W kodzie | Po polsku | Po angielsku |
|---|---|---|
| `kadlub` | kadłub | hull |
| `poklad`, `poklad_rufowy`, `polpoklad` | pokład, pokład rufowy, półpokład | deck, quarterdeck |
| `wregi`, `wreg` | wręgi, wręg | frames, frame |
| `rzedne` | rzędne | offsets |
| `poszycie`, `deski` | poszycie, deski | planking, planks |
| `stepka`, `wrab` | stępka, wrąb | keel, rabbet |
| `dziobnica`, `tylnica` | dziobnica, tylnica | stem, sternpost |
| `dziob`, `rufa`, `pawez` | dziób, rufa, pawęż | bow, stern, transom |
| `burta`, `nadburcie`, `reling` | burta, nadburcie, reling | side, bulwark, rail |
| `bergholt` | berghołt | wale |
| `furta`, `pokrywa` | furta, pokrywa | gun port, lid |
| `ster`, `rumpel`, `kolo_sterowe` | ster, rumpel, koło sterowe | rudder, tiller, steering wheel |
| `galion`, `kotbelka`, `kluza` | galion, kotbelka, kluza | head, cathead, hawse hole |
| `drzewca`, `maszt` | drzewca, maszt | spars, mast |
| `fok`, `grot` | fok, grot | fore, main (maszt albo żagiel) |
| `stenga`, `bramstenga` | stenga, bramstenga | topmast, topgallant mast |
| `reja`, `mars`, `ezelhoft` | reja, mars, ezelhoft | yard, top, cap |
| `bukszpryt`, `bomstenga`, `blinda` | bukszpryt, bomstenga, blinda | bowsprit, jib-boom, spritsail |
| `gafel`, `bom` | gafel, bom | gaff, boom |
| `olinowanie`, `takielunek` | olinowanie, takielunek | rigging |
| `lina`, `liny` | lina, liny | rope, ropes |
| `wanta`, `wanty`, `podwantka` | wanta, wanty, podwantka | shroud, shrouds, futtock shroud |
| `sztag`, `padun` | sztag, padun | stay, backstay |
| `jufers`, `talrep`, `wyblinka` | jufers, talrep, wyblinka | deadeye, lanyard, ratline |
| `lawa_wantowa` | ława wantowa | channel |
| `blok`, `bloki`, `strop` | blok, bloki, strop | block, blocks, strop |
| `ruchome` | (liny) ruchome | running (rigging) |
| `topenanta`, `bras`, `szot`, `fal`, `gejtawa` | topenanta, bras, szot, fał, gejtawa | lift, brace, sheet, halliard, clewline |
| `perta` | perta | footrope |
| `zagiel`, `zagle` | żagiel, żagle | sail, sails |
| `wyposazenie` | wyposażenie | fittings, equipment |
| `dzialo`, `dzialko`, `laweta`, `lufa` | działo, działko, laweta, lufa | gun, swivel gun, carriage, barrel |
| `kabestan`, `pompa`, `luk` | kabestan, pompa, luk | capstan, pump, hatch |
| `kotwica`, `lodz`, `dzwon` | kotwica, łódź, dzwon | anchor, boat, bell |
| `nagielbank`, `kolkownica`, `kolek` | nagielbank, kołkownica, kołek | fife rail, pin rail, pin |
| `stanowisko`, `stan_*` | stanowisko | work station |
| `czynnosc`, `przeszkoda` | czynność, przeszkoda | activity, obstacle |
| `chodzenie`, `postac` | chodzenie, postać | walking, figure |
| `kolizja`, `przenikanie` | kolizja, przenikanie | collision, interpenetration |
| `os_ruchu`, `zakres` | oś ruchu, zakres | motion axis, range |
| `kontrola`, `wynik`, `tak`, `nie` | kontrola, wynik, tak, nie | check, result, yes, no |
| `tekstury`, `kolor`, `normalne`, `szorstkosc` | tekstury, kolor, normalne, szorstkość | textures, colour, normals, roughness |
| `farba`, `drewno`, `zelazo`, `plotno`, `szklo` | farba, drewno, żelazo, płótno, szkło | paint, wood, iron, canvas, glass |
| `srednica`, `dlugosc`, `szerokosc`, `wysokosc` | średnica, długość, szerokość, wysokość | diameter, length, breadth, height |
| `rysunki`, `arkusz`, `dane`, `nazwy` | rysunki, arkusz, dane, nazwy | drawings, sheet, data, names |
| `zbuduj`, `buduj`, `zapisz`, `scal` | zbuduj, buduj, zapisz, scal | build, build, save, merge |
| `statek`, `bryg` | statek, bryg | ship, brig |

Dokładną angielską nazwę obiektów i węzłów, grup lin, materiałów, parametrów i kluczy, użytą w danych i w `model/`,
podaje `data/names-map.csv` (kolumny `category`, `polish`, `english`).

## Sprawdź się

- [ ] Budowa kończy się wierszem `KONIEC` i bez błędu.
- [ ] W `build/kontrola.json`: 0 kryteriów z `nie`; `konce_lin.wiszace` = 0; `bloki.bez_zaczepu` = 0;
  `przenikanie.zgloszone_ponad_prog` = 0.
- [ ] Z teksturami CC0 `build/bryg.glb` ma 330 węzłów i ok. 230 tys. trójkątów.
- [ ] `rysunki.py` z `--publiczne build/...` kończy się wierszem `KONTROLA DANYCH: błędów 0`, a `data/` i `plans/`
  repozytorium są bez zmian.
- [ ] Narzędzie zamiany nazw kończy się `błędów 0` dla wszystkich czterech plików, a `--sprawdz` niczego nie znajduje.
- [ ] Pliki z `model/` wczytują się w Blenderze (File > Import > glTF 2.0) z angielskimi nazwami.

## Typowe błędy

1. Uruchamianie poleceń z katalogu `blender/` zamiast z katalogu głównego repozytorium: wyniki trafiają wtedy do innego
   `build/`, a `--tekstury-cc0` ze ścieżką względną nie znajduje katalogu.
2. `python` w wierszu poleceń to Python bez numpy albo Pillow: krok tekstur kończy się błędem importu.
3. Pliki Poly Haven w innej rozdzielczości albo o innych nazwach (np. 4K albo PNG): krok CC0 ich nie znajduje. Nazwy
   są w `blender/tekstury_cc0_spis.json`.
4. Poprawianie kopii roboczych tekstur w `build/` i zdziwienie, że nic się nie zmienia: budowa używa ich, dopóki
   istnieją; po zmianie źródeł usuń katalog.
5. Uruchamianie `rysunki.py` bez `--publiczne` przy próbach: nadpisuje `data/` i `plans/`.
6. Narzędzie zamiany nazw na pliku ze zmienionego generatora bez wcześniejszego uzupełnienia mapy: narzędzie staje
   i wypisuje nowe nazwy. Tak ma być.
7. Otwieranie cudzego pliku `.blend` bez `--disable-autoexec`.

## Źródła

1. Khronos Group, *glTF 2.0 Specification* https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html (kontener
   binarny GLB, węzły, siatki, materiały, obrazy, extras).
2. Poly Haven https://polyhaven.com/ (tekstury; strona każdego zasobu podaje autorów i licencję CC0); lista użytych
   zasobów: `blender/tekstury_cc0_spis.json`.
3. Creative Commons, *CC0 1.0 Universal* https://creativecommons.org/publicdomain/zero/1.0/.
4. Blender Manual, *Command Line Arguments* https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
   (`-b`, `--python`, `--factory-startup`, `--disable-autoexec`, argumenty po `--`).
5. Blender Manual, dodatek glTF 2.0 https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html (właściwości
   własne eksportowane jako extras).

## Terminy użyte w rozdziale

| Angielski | Polski | Objaśnienie |
|---|---|---|
| background mode | tryb bez okna | Blender wykonujący skrypt bez okna (`-b`). |
| factory settings | ustawienia fabryczne | Blender bez preferencji użytkownika i dodatków. |
| generator | generator | Skrypty, które budują model z liczb. |
| stage | etap | Jedna część budowy, jeden moduł. |
| procedural texture | tekstura proceduralna | Obraz policzony przez skrypt. |
| working copy | kopia robocza | Plik zrobiony przez budowę ze źródła, które zostaje bez zmian. |
| node, mesh, material, image | węzeł, siatka, materiał, obraz | Nazwane części pliku glTF. |
| extras | extras (dane dodatkowe glTF) | Wolne pole na dane aplikacji w glTF. |
| level of detail (LOD) | poziom szczegółów | Prostszy model do oglądania z daleka. |
| collision solid | bryła kolizji | Prosta bryła do testów kolizji. |
| check report | raport kontroli | `kontrola.json`. |
| exit code | kod wyjścia | Liczba zwracana przez program; 0 oznacza powodzenie. |
