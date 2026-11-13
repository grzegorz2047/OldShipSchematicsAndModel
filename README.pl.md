# Plany i model dawnego okrętu: snow z około 1710 roku

[English version](README.md)

To repozytorium jest przewodnikiem po budowie jednego żaglowego okrętu z początku XVIII wieku oraz zbiorem otwartych
danych i rysunków, z których można go zbudować. Okręt to **snow**: mały dwumasztowy żaglowiec z ożaglowaniem
rejowym z około 1710 roku, długi na 28,0 m na pokładzie między wrębami i szeroki na 7,60 m po poszyciu, z dziesięcioma
działami na jednym pokładzie i kołem sterowym; stoi na kotwicy ze zwiniętymi żaglami. Nazywamy go **modelem
wzorcowym**.
Każda liczba w przewodniku pochodzi ze źródła z epoki, z późniejszych opracowań, z naszego własnego wnioskowania albo
z samego modelu wzorcowego i każda jest tak oznaczona.

Przewodnik jest pisany dla dwóch rodzajów czytelników:

- **człowieka**, który chce odtworzyć taki okręt w Blenderze, w programie CAD albo na papierze, a potem tym samym
  sposobem projektować inne statki z epoki;
- **agenta AI**, który wykonuje tę samą pracę: pliki danych da się czytać maszynowo, każdą kolumnę opisuje
  [`data/SCHEMA.pl.md`](data/SCHEMA.pl.md), a każdy parametr ma jednostkę, oznaczenie pewności i rozdział, który go
  objaśnia.

Przewodnik, opis danych, rysunki i książeczka do rysowania są po angielsku i po polsku. Tekst polski jest pełną
wersją, a nie przekładem słowo w słowo.

## Co gdzie leży

| Katalog albo plik | Co zawiera |
|---|---|
| `docs/pl/`, `docs/en/` | przewodnik: rozdziały, dodatek, lista źródeł i słownik (po polsku i po angielsku; pliki mają w obu katalogach te same nazwy) |
| `data/` | liczby modelu wzorcowego: parametry, tabela rzędnych, drzewca, każdy odcinek liny, układ pokładu, stanowiska czynności, części ruchome, mapa nazw; opis w `data/SCHEMA.pl.md` i `data/SCHEMA.md` |
| `plans/` | rysunki wykonane z danych przez skrypty: plan linii teoretycznych, przekroje, plan pokładu, plany drzewc, żagli i olinowania, plan belegowania i szczegóły wyposażenia; arkusze SVG w milimetrach w rzeczywistym rozmiarze kartki, podglądy PNG w `plans/png/` (nie w skali), wszystkie arkusze w `plans/plans-en.pdf`; arkusze polskie w `plans/pl/` i `plans/plans-pl.pdf` |
| `drawing-tutorial/` | książeczka do druku, która krok po kroku uczy rysować okręt (dla młodych rysowników, mniej więcej od 12 do 16 lat), po polsku i po angielsku, razem ze skryptami, które ją zrobiły |
| `model/` | pliki modelu okrętu wzorcowego |
| `blender/` | skrypty, które budują model wzorcowy w Blenderze |
| `LICENSE` | licencja MIT |

### `model/`

Ten katalog zawiera pliki modelu wzorcowego w binarnej postaci glTF (GLB), z angielskimi nazwami:

| Plik | Co to jest |
|---|---|
| `model/snow.glb` | pełny model, ok. 31 MB i 230 000 trójkątów: każda część ruchoma jest osobnym węzłem z osią i zakresem ruchu, a 142 stanowiska czynności są pustymi węzłami |
| `model/snow_lod1.glb`, `model/snow_lod2.glb` | dwa uproszczone poziomy szczegółów, po jednej siatce (ok. 50 % i 5 % trójkątów) |
| `model/snow_collision.glb` | 36 prostych brył kolizji, węzły `collision_*` |

Nazwy węzłów i dane dodatkowe opisuje [rozdział 14](docs/pl/14-using-the-model-in-a-game.md), a sprawdzenia,
które te pliki przechodzą, [rozdział 13](docs/pl/13-3d-quality-checklist.md).

### `blender/`

Ten katalog zawiera generator: skrypty Pythona dla Blendera 5.2, które zbudowały model wzorcowy, sprawdziły go
i zapisały pliki w `data/`, `plans/` i `model/`. Statek buduje jedno polecenie, uruchamiane z katalogu głównego
repozytorium:

```
blender -b --factory-startup --python blender/buduj.py -- --glb --rendery none
```

Skrypty są opublikowane w takiej postaci, w jakiej były używane, czyli po polsku (nazwy modułów, zmienne,
komentarze). [Rozdział 10](docs/pl/10-building-in-blender.md) wyjaśnia, jak je uruchomić, co robi każdy moduł
i gdzie są liczby opisujące statek. Narzędzie `blender/nazwy_na_angielskie.py` zamienia polskie nazwy
w zbudowanym pliku na angielskie nazwy z `model/` według `data/names-map.csv`.

## Od czego zacząć

Niezależnie od celu zacznij od [rozdziału 01](docs/pl/01-ship-type-and-era.md): objaśnia typ okrętu, epokę
i oznaczenia pewności używane w całym przewodniku. Potem wybierz drogę.

**Na papierze albo w CAD.** Przeczytaj [rozdział 02](docs/pl/02-hull-lines-and-offsets.md) o planie linii
teoretycznych i tabeli rzędnych, a potem [rozdział 11](docs/pl/11-building-in-cad-or-on-paper.md), który krok po
kroku prowadzi od `data/offsets.csv`, `data/spars.csv` i `data/rigging-lines.json` do rysunku, modelu w CAD albo
modelu z kartonu lub drewna, z wymiarami kontrolnymi do sprawdzenia pracy. Porównuj z arkuszami w `plans/`.
Młodszym czytelnikom, którzy chcą okręt narysować, a nie skonstruować, łatwiejszy start daje książeczka
w `drawing-tutorial/`.

**W Blenderze.** Czytaj rozdziały od 01 do 09 po kolei: prowadzą od linii kadłuba przez konstrukcję, pokłady,
maszty, olinowanie stałe i ruchome, liny i żagle aż do mechanizmów pokładu, a każdy kończy się przykładem
policzonym na modelu wzorcowym. Sprawdź swój model według [rozdziału 13](docs/pl/13-3d-quality-checklist.md).
[Rozdział 10](docs/pl/10-building-in-blender.md) pokazuje, jak uruchomić skrypty z `blender/`, którymi zbudowano
sam model wzorcowy.

**W grze.** Przeczytaj [rozdział 14](docs/pl/14-using-the-model-in-a-game.md): objaśnia pliki w `model/`, układ
współrzędnych, nazwy węzłów, stanowiska czynności, części ruchome, chodzenie po pokładach, dwa warianty sterowania,
liny, które muszą iść za ruchomymi rejami, poziomy szczegółów i kolizje. Korzysta z danych w `data/stations.csv`,
`data/moving-parts.csv`, `data/deck-layout.json`, `data/rigging-lines.json` i `data/names-map.csv`.
[Dodatek o obsłudze statku](docs/pl/appendix-sail-handling.md) podsuwa mechaniki gry, które wynikają z tego, jak
załoga naprawdę pracowała przy żaglach.

**Dla innego statku.** [Rozdział 12](docs/pl/12-designing-other-ships.md) pokazuje, które parametry zmieniać, czym
różnią się warianty ożaglowania, co zmienia się wraz z datą, co sprawdzić po każdej zmianie, i podaje dwa przykłady:
slup długi na około 21 m i trzymasztowiec długi na około 32 m.

## Rozdziały

| Rozdział | O czym jest |
|---|---|
| [01. Typ okrętu i epoka](docs/pl/01-ship-type-and-era.md) | Jak wybrać typ i datę, wziąć główne wymiary z udokumentowanych okrętów i uniknąć anachronizmów; dlaczego model wzorcowy jest snow z około 1710 roku. |
| [02. Linie teoretyczne kadłuba i tabela rzędnych](docs/pl/02-hull-lines-and-offsets.md) | Plan linii teoretycznych, liczby opisujące kształt, wręg owręża rysowany łukami, tabela rzędnych modelu wzorcowego i sprawdzenie wyporności oraz gładkości. |
| [03. Konstrukcja kadłuba](docs/pl/03-hull-construction.md) | Stępka, dziobnica, tylnica, wręgi, berghołty i poszycie: do czego służy każdy element, jaki jest duży, jak wygląda i jak go zamodelować. |
| [04. Pokłady, nadburcia, rufa i galion](docs/pl/04-decks-bulwarks-stern-head.md) | Pokłady z wypukłością i wzniosem, nadburcia, furty i ich pokrywy, ławy wantowe, kotbelki, pawęż, ster, galion i układ pokładu z miejscem do pracy. |
| [05. Maszty i drzewca](docs/pl/05-masts-and-spars.md) | Od długości i szerokości pokładu do pełnej tabeli drzewc według reguł proporcji z epoki oraz jak drzewca narysować i zamodelować. |
| [06. Olinowanie stałe](docs/pl/06-standing-rigging.md) | Wanty, wyblinki, sztagi, paduny, olinowanie bukszprytu i liny na rejach, z oboma końcami i średnicą każdej liny. |
| [07. Olinowanie ruchome i belegowanie](docs/pl/07-running-rigging-and-belaying.md) | Przebieg każdej liny ruchomej, zrekonstruowany plan belegowania, liny z końcem na ruchomym drzewcu i granice brasowania rej. |
| [08. Liny, bloki i żagle](docs/pl/08-ropes-blocks-and-sails.md) | Jak powstaje lina i jaka jest mocna, bloki i jufersy, budowa żagli i ich wygląd w każdym stanie oraz jak rysować liny w 3D bez migotania. |
| [09. Mechanizmy i wyposażenie pokładu](docs/pl/09-deck-machinery.md) | Kabestan, pompy, sterowanie, działa, kotwice, łodzie, dzwon i drobniejsze wyposażenie: części, wymiary, obsługa i to, co się porusza. |
| [10. Budowa statku w Blenderze](docs/pl/10-building-in-blender.md) | Uruchamianie skryptów generatora: jedna budowa krok po kroku, moduły, parametry, kontrole, tekstury, rysunki i dane, narzędzie zamiany nazw oraz słowniczek polskich słów z kodu (dla czytelnika angielskiego). |
| [11. Budowa statku w CAD albo na papierze](docs/pl/11-building-in-cad-or-on-paper.md) | Odtworzenie okrętu z plików danych ręcznie, w dowolnym programie CAD albo jako model z kartonu lub drewna, z wymiarami kontrolnymi. |
| [12. Projektowanie innych statków na tym wzorze](docs/pl/12-designing-other-ships.md) | Które parametry zmieniać, warianty ożaglowania, przesunięcie daty, sprawdzenia po każdej zmianie i dwa przykłady. |
| [13. Lista kontrolna jakości modelu 3D](docs/pl/13-3d-quality-checklist.md) | Sprawdzenia jednostek, nazw, punktów obrotu, siatek, przenikania brył, map UV, materiałów, rozmiaru pliku, poziomów szczegółów, kolizji i chodzenia oraz błędy, które popełniliśmy. |
| [14. Użycie modelu w grze](docs/pl/14-using-the-model-in-a-game.md) | Pliki modelu i danych z punktu widzenia gry: współrzędne, węzły, stanowiska, części ruchome, sterowanie, liny dynamiczne, kolizje i holowana łódź. |
| [Dodatek. Obsługa statku](docs/pl/appendix-sail-handling.md) | Jak załoga stawia, refuje i zwija żagle, robi zwrot przez sztag i przez rufę, staje w dryf i kotwiczy; ludzie i czas; wynikające z tego mechaniki gry. |
| [Źródła](docs/pl/sources.md) | Każde źródło cytowane w rozdziałach, wymienione raz, z rozdziałami, które je cytują. |
| [Słownik](docs/pl/glossary.md) | Wszystkie terminy z rozdziałów w kolejności alfabetycznej: angielski, polski i krótkie objaśnienie. |

## Układ współrzędnych i jednostki

Wszystkie pliki danych używają metrów i stopni, a każdy punkt zapisują jako **[x, s, z]** w osiach statku
(`data/SCHEMA.pl.md`):

| Oś | Kierunek | Zero |
|---|---|---|
| x | w poprzek, **dodatnio ku lewej burcie** | płaszczyzna symetrii |
| s | wzdłuż, **dodatnio ku dziobowi** | środek 28,0 m długości pokładu między wrębami (wrąb dziobnicy na pokładzie s = +14,0, tylnica s = −14,0) |
| z | w górę | wodnica konstrukcyjna |

Trójka (s, x, z) jest prawoskrętna. Przeliczenia:

- glTF i pliki gry (+Y w górę): (X, Y, Z) = (x, z, s); dziób ku +Z.
- Blender (Z w górę): (X, Y, Z) = (x, −s, z); dziób ku −Y.

Wielokąty w rzucie to [x, s]. Pliki JSON powtarzają ten opis w polu `coordinate_system`; pliki CSV zaczynają się od
wierszy komentarza z `#`. Nazwy kluczy kończą się jednostką: `_m` metry, `_deg` stopnie, `_m2` metry kwadratowe.

## Oznaczenia pewności

Każda wartość w przewodniku i w `data/parameters.json` ma jedno z czterech oznaczeń, objaśnionych
w [rozdziale 01](docs/pl/01-ship-type-and-era.md):

- **z epoki** (w danych `period`): źródło z tamtego czasu albo kilka zgodnych;
- **wtórne** (`secondary`): współczesne opracowanie, forum, zestaw modelarski, replika albo streszczenie, którego nie
  mogliśmy porównać z oryginałem;
- **nasz wniosek** (`our inference`): nasze własne obliczenie albo rekonstrukcja bez bezpośredniego źródła;
- **model wzorcowy** (`reference model`): wartość wybrana albo zmierzona w modelu wzorcowym.

Wiele reguł z epoki pochodzi od Steela (1794), około 80 lat po naszej dacie, i od Levera (1808); rozdziały mówią,
gdzie wcześniejsze źródła się różnią.

## Ograniczenia modelu wzorcowego

Model wzorcowy jest staranną rekonstrukcją, a nie zachowanym okrętem, i nie jest skończony. Zanim go skopiujesz,
poznaj jego ograniczenia:

- **Wybieg pod wodnicą nie jest gładki.** Między tylnicą a mniej więcej s = −4 kadłub ma nierówności 1–5 cm
  i sprawdzenie gładkości kadłuba nie przechodzi w tym miejscu (34 nadmiarowe garby). Burty nad wodą i część
  dziobowa są gładkie. Błąd siedzi w samej tabeli rzędnych; gdy prowadzisz własny kadłub, traktuj rzędne za s = −4
  i poniżej wodnicy −1,0 jako jeszcze do wygładzenia ([rozdział 02](docs/pl/02-hull-lines-and-offsets.md),
  [rozdział 13](docs/pl/13-3d-quality-checklist.md), sprawdzenie D7).
- **Żagle są zwinięte, a okręt stoi na kotwicy.** Żagle postawione istnieją tylko jako szacowane wymiary
  w `data/parameters.json` ([rozdział 08](docs/pl/08-ropes-blocks-and-sails.md)).
- **Olinowanie samo się nie porusza.** Każda lina to nieruchoma geometria, która zwisa tylko pod własnym ciężarem:
  liny nie przesuwają się przez bloki i nie ruszają się na wietrze. Odcinki z końcem na części ruchomej są oznaczone,
  a gra musi je przerysowywać sama ([rozdział 07](docs/pl/07-running-rigging-and-belaying.md),
  [rozdział 14](docs/pl/14-using-the-model-in-a-game.md)). Lin potrzebnych tylko przy postawionych żaglach (m.in.
  halsów, bulin, nokgordingów, talii refowych oraz fałów, szotów i kontrafałów sztaksli i kliwra) nie zamodelowano.
- **Pod pokładem nie ma nic.** Ładowni i kabiny nie zbudowano; drabina luku głównego i schody zejściówki prowadzą
  w dół do przestrzeni, których nie ma w modelu. Wewnętrzne elementy, takie jak kilson, są opisane, ale nie zamodelowane
  ([rozdział 03](docs/pl/03-hull-construction.md)).
- **Plan belegowania jest rekonstrukcją.** Nie znaleźliśmy planu belegowania brygu ani snow z epoki, a kołkownice
  wzdłuż nadburcia są dla 1710 roku prawdopodobnie anachronizmem
  ([rozdział 07](docs/pl/07-running-rigging-and-belaying.md)).
- **Wiele wymiarów to szacunki.** Wielu wymiarów mechanizmów małych okrętów z lat 1700–1720 nikt nie zapisał; podajemy
  nasze szacunki ([rozdział 09](docs/pl/09-deck-machinery.md)).
- **Część sprawdzeń jest jeszcze otwarta**: gładkość kadłuba (wyżej), wolne przejście na dziobie przy wszystkich
  działach wtoczonych i siedem drobnych ścianek o skrzyżowanych krawędziach w snycerce rufy i na górze kadłuba
  ([rozdział 13](docs/pl/13-3d-quality-checklist.md), sprawdzenia D7, J5 i D8).
- **Uszkodzeń nie zamodelowano**: nie ma przestrzelin, ognia, przeciętych lin ani złamanych drzewc; rozdział 14 mówi,
  jak dane są na nie przygotowane.

Liczby oznaczone „w chwili pisania” zmieniają się trochę przy każdej przebudowie modelu. Aktualne wartości są
zawsze w plikach w `data/`.

## Licencja i materiały innych autorów

Przewodnik, dane, rysunki i skrypty z tego repozytorium są udostępnione na licencji MIT (zob. [`LICENSE`](LICENSE)).

Materiały innych autorów są **podane jako odnośniki, a nie skopiowane**, z jednym wyjątkiem, którym są tekstury
wewnątrz plików modelu:

- Tekstury modelu wzorcowego powstały z ośmiu fotograficznych tekstur z Poly Haven, wszystkich na licencji CC0.
  Pliki w `model/` zawierają te obrazy po przetworzeniu przez nasze skrypty (obrócone słoje, zmienione kolory,
  układ desek w atlasach). Oryginalnych plików Poly Haven w repozytorium nie ma: `blender/tekstury_cc0_spis.json`
  wymienia każdy zasób z adresem strony i autorami, a [rozdział 10](docs/pl/10-building-in-blender.md) opisuje,
  jak je pobrać do własnej budowy.
- Plany F. H. af Chapmana (*Architectura Navalis Mercatoria*, 1768), użyte do kalibracji, są w domenie publicznej;
  podajemy do nich odnośniki (Wikimedia Commons i Sjöhistoriska museet) i ich nie kopiujemy.
- Plany i modele Royal Museums Greenwich podajemy jako odnośniki tylko do oglądania, na warunkach muzeum.
- Fakty z książek, artykułów, forów i Wikipedii streszczamy własnymi słowami; każde źródło wymienia
  [lista źródeł](docs/pl/sources.md).
