# Budowa i odbiór modeli SailerTales

Modele w osobnych PR-ach korzystają z oryginalnej metody konstrukcyjnej
OldShipSchematicsAndModel: dane kadłuba i interpolacja rzędnych, konstrukcja
drewniana, proporcje drzewc i ożaglowania oraz wyposażenie. Wnętrza i odstępstwa
potrzebne graczowi są osobno opisane w `design.json` każdej jednostki.

Wymagane narzędzia: Blender 5.2 (sprawdzone na 5.2.3 LTS), jego Python i NumPy.
Nie są potrzebne dodatki, Tripo, pobieranie fotograficznych tekstur ani Pillow.
Wariant proceduralny PBR jest jawnie opisany w danych; nie udajemy, że to
fotograficzne materiały CC0 modelu wzorcowego. Bazowe moduły `blender/` pozostają
oryginalnymi plikami z commita `2e6f7e922e95396722376d42f3e2e0a12256029e`.

## Odtworzenie

Z katalogu głównego repozytorium, zastępując `<id>` identyfikatorem jednostki:

| Identyfikator | Generator |
|---|---|
| `brig`, `night-hull` | `sailertales/common/v2_big.py` |
| `merchant-sloop` | `sailertales/common/v2_sloop.py` |
| `mewka`, `dinghy`, `rowboat`, `dugout` | `sailertales/common/v2_boats.py` |
| `wreck` | `sailertales/common/v2_wreck.py` |

Dokładne argumenty CLI są podane przez `--help` danego generatora. Wspólny wzór:

```sh
blender -b --factory-startup --python-exit-code 1 --python sailertales/common/v2_boats.py -- sailertales/dinghy/spec.json --out build/final/dinghy
```

`v2_reference.py` uruchamia oryginalny generator i stosuje udokumentowany profil
konstrukcyjny. `rebuild_reference.py` udostępnia funkcje parametrów i proceduralnych
tekstur; jego wcześniejszy samodzielny tryb buduje tylko scenę konstrukcji i nie
zastępuje końcowego generatora. `v2_rigging.py` buduje roboczy takielunek brygu.

`v2_export.py` zapisuje modele wizualne, osobne kolizje, LOD-y oraz spakowany Blender.
`v2_materials.py` przygotowuje atlasy PBR o wymiarach fizycznych zgodnych z układem
desek poradnika. Mniejsze jednostki mogą używać oryginalnych materiałów drewna
2048 px na 2 m, jeżeli pomiar potwierdza ich gęstość i kierunek słojów.

## Niezależna kontrola

```sh
blender -b --factory-startup --python-exit-code 1 --python sailertales/common/v2_review.py -- build/final/dinghy --resolution 640
blender -b --factory-startup --python-exit-code 1 --python sailertales/common/v2_audit.py -- sailertales/dinghy/spec.json --asset-dir build/final/dinghy
python sailertales/common/v2_integrity.py --asset-dir build/final/dinghy --source-root .
```

Kolejność ma znaczenie: najpierw końcowy eksport, potem porównawcze rendery, potem
audyt i jego odciski plików. `v2_package.py` odmawia publikacyjnego przeniesienia
assetu, jeżeli audyt lub porównanie sceny źródłowej z GLB nie zostały zaliczone.

`validation.json` ma pełną macierz punktów A–J rozdziału 13. PASS, FAIL i NA nie
są zamienne. NA zawsze wymaga uzasadnienia; pomiar niewykonany nie staje się PASS.
Raport tras potwierdza wskazane drogi i miejsca gracza w zapisanym ustawieniu.
Nie oznacza automatycznie zweryfikowania wszystkich stanowisk załogi, ruchu
każdego mechanizmu czy całego obszaru dostępnego w przyszłej grze.

`export-review.json` porównuje rzeczywisty eksport GLB ze spakowaną sceną, przy
identycznych kamerach i oświetleniu: liczby trójkątów, jasność i udziały kolorów.
PNG w `previews/` powstają z ponownie zaimportowanego GLB. Deck view ukrywa
takielunek tylko na potrzeby obejrzenia pokładu; plik modelu pozostaje kompletny.

## Kontrakt integracji

- Metry; glTF X ku lewej burcie, Y w górę, Z ku dziobowi.
- Postać kontrolna: promień 0,38 m, całkowita wysokość 1,85 m, chodzenie do 35°.
- Otwory luków są rzeczywistą geometrią. Kolizje muszą pozostać siatkami wklęsłymi.
- Trasy `climb` wymagają kontrolera drabiny; nie przedstawiamy ich jako chodzenia po łagodnej schodni.
- Wnętrza mają własne powierzchnie i dostęp; małe otwarte łodzie nie otrzymują fikcyjnych kajut.
- Drzwi, pokrywy i mechanizmy wymagają podpięcia zachowanych węzłów i punktów obrotu do silnika.
- Ruch postaci wraz z płynącym statkiem, maskowanie wody, fizyka żeglugi i wykonywanie akcji nie są kodem zawartym w statycznym modelu.
- Przechył wraku jest zapisany w modelu i trasach; nie nakładać go po raz drugi.

Nie należy łączyć kontroli konstrukcji, ergonomii i eksportu w jedną nieprecyzyjną
deklarację „model przeszedł testy”. Każdy raport podaje, co dokładnie sprawdzono.
