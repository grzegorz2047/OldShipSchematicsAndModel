# Zwykłe typy statków z Pirates of the Caribbean (2003)

Każdy katalog typu dostarcza nową, autorską rekonstrukcję inspirowaną podstawową grą Akelli. Rodzina, klasa i liczba dział pochodzą ze wskazanych źródeł gry. Wymiary w metrach, linie kadłuba, rozplanowanie pokładów i szczegóły takielunku są autorską interpretacją, a nie odzyskanymi modelami gry. Źródła i granice wierności opisują `spec.json` i `design.json` danego typu.

Zakres obejmuje Tartane, Yacht, Lugger, Galeoth, Xebec, Barque, Schooner, Caravel, Fleut, Pinnace, Brig, Galleon, Corvette, Frigate i Battleship. Każdy typ trafia do osobnego PR. Istniejąca rodzina Sloop pozostaje we wcześniejszych PR-ach. Nowy Brig ma dwa zasadnicze maszty i gafel na grotmaszcie; wcześniejszy model nazwany w grze „brygiem” korzysta z układu snowa. Jednostki specjalne oraz wersje z modów nie należą do tej serii.

Dwie kompletne wersje kolorystyczne, `ochre` i `navy`, zawierają osobne główne GLB, LOD1, LOD2 i spakowane sceny Blender. Zmieniają się farby kadłuba i listew; drewno, płótno, liny i żelazo zachowują materiały naturalne. Wspólna kolizja jest dokładną kopią zadeklarowanych zamkniętych powłok kadłuba i płyt pokładów. Zachowuje rzeczywiste furty i otwarte kokpity, więc wymaga obsługi wklęsłej statycznej siatki kolizji.

To statyczne modele do prezentacji jednostek i integracji z grą. Nie zawierają kontrolera żeglugi, załogi, chodzenia ani animacji obsługi dział. Audyt dotyczy dostarczonej pozy żagli. Nie certyfikuje dowolnego przetrymowania ani historycznej zgodności każdego detalu.

## Odtwarzanie i kontrola

Modele i porównania wykonano w Blenderze **5.2.3 LTS**. Spakowane sceny źródłowe wymagają Blendera 5.2 lub nowszego. Wszystkie tekstury są osadzone w GLB i scenach źródłowych.

Przykład dla katalogu `potc/tartane`; zastąp identyfikator wybranym dostarczonym typem:

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/tartane/build.py
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v4_audit.py -- --asset-dir potc/tartane --source-root .
python potc/common/v4_integrity.py --asset-dir potc/tartane --source-root .
```

Samodzielna kontrola wszystkich dostarczonych typów, bez Blendera:

```sh
python potc/common/v4_integrity.py --all --source-root .
```

Raporty wiążą modele, spakowane źródła, podglądy i użyty kod przez SHA-256. Pełny audyt ponownie importuje wszystkie siedem GLB, sprawdza rzeczywistą geometrię i mocowania olinowania, oba malowania, LOD-y, materiałowe UV oraz zgodność scen źródłowych z eksportami i ich obrazami. Tryb diagnostyczny `--geometry-only` nie tworzy raportu odbioru.

Wspólny kod tej serii ma osobną przestrzeń `potc/common/v4_*.py`. Wcześniejsze moduły i progi kontroli pozostają identyczne z zamrożoną integracją wcześniejszej floty.
