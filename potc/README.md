# Statki POTC — pokłady, wnętrza i dwa malowania

Modele przedstawiają zwykłe rodziny statków z Pirates of the Caribbean (2003). Każdy typ ma własny PR oraz dwie kompletne wersje: `ochre` i `navy`. Jednostki specjalne pozostają poza serią. Geometria jest autorska; liczby dział i rodziny pochodzą ze źródeł gry. Wymiary w metrach i szczegółowe wnętrza są rekonstrukcją, a nie wydobytymi modelami gry.

Każdy katalog typu zawiera `layout-research.json`: przeczytane źródła muzealne i planistyczne, ich zastosowanie, decyzje rekonstrukcyjne oraz ograniczenia. Rozplanowanie jest zapisane w `spec.json` pod `detailed_layout`. Źródła dla późniejszych jednostek porównawczych są oznaczone jako analogie. Nie są dowodem wyglądu niedostępnego wnętrza gry.

## Konstrukcja i wyposażenie

Wnętrza mają rzeczywistą geometrię: klepkowe pokłady, wręgi, belki i kolana, stropy, podłogi ładowni, grodzie, przejścia, luki i zejścia. Otwory przechodzą przez właściwe poziomy pokładów. Przeszklone okna mają otwory w drewnie rufy; szkło nie leży na pełnej ścianie. Wyposażenie obejmuje odpowiednie dla typu koje, ławy, stoły, schowki, zapasy, osprzęt cumowniczy i kotwiczny. Działa mają rzeczywiste wnętrza luf i liny oporowe; takielunek otrzymał jufersy, ściągacze, bloki, kołki i wyblinki.

Mała tartana pozostaje otwartą łodzią rybacką z widoczną zęzą, wręgami, ławkami, rumplem i odłożonym sprzętem. Nie otrzymuje wymyślonej pełnej kajuty ani ładowni z pionowym dojściem. Fluita, karawela, szkuner, galeon i okręty artyleryjskie zachowują odrębne układy oraz funkcje przestrzeni.

Punktem odniesienia jakości jest szczegółowy Bryg Mewa z wcześniejszego PR #3: rzeczywiste wnętrza i otwarte dojścia oraz materiały oglądane w porównywalnej skali. Liczba trójkątów nie zastępuje oceny jakości. Główne mapy pokładu i malowanego poszycia zachowują 8192 × 2048 pikseli; drewno i metal korzystają z map 2048², podobnie płótno. Osadzone mapy PBR obejmują kolor, normalne i ORM. Malowania zmieniają farby kadłuba i listew, zachowując naturalne materiały oraz identyczną geometrię.

## Odtwarzanie i weryfikacja

Zalecany Blender: **5.2.3 LTS**. Spakowane sceny wymagają wersji 5.2 lub nowszej. Przykład dla brygu:

```sh
blender -b -t 2 --factory-startup --python-exit-code 1 --python potc/brig/build.py
blender -b -t 2 --factory-startup --python-exit-code 1 --python potc/common/v5_review.py -- --asset-dir potc/brig --resolution 640
```

Podglądy powstają przez ponowny import dostarczonego GLB. Przekroje mają jawnie zapisane tymczasowo ukryte elementy; nie zmieniają geometrii eksportu. Po obejrzeniu rzeczywistych podglądów `detail-review.json` zapisuje ocenę, konkretne obserwacje i hashe obrazów. Renderer sam nie wystawia oceny PASS.

```sh
blender -b -t 2 --factory-startup --python-exit-code 1 --python potc/common/v5_audit.py -- --asset-dir potc/brig --source-root .
python potc/common/v5_integrity.py --asset-dir potc/brig --source-root .
python potc/common/v5_integrity.py --all --source-root .
```

Przenośna kontrola wymaga Pythona, NumPy i Pillow. Raport zachowuje dotychczasowe kontrole geometrii, UV, materiałów, takielunku, dwóch malowań, LOD-ów i zgodności scen źródłowych z eksportami. Dodatkowe bramki mierzą rzeczywistą konstrukcję, wolne otwory, dojścia, okna, materiały i wiążą ręczną ocenę obrazów z dokładnym modelem. SHA-256 obejmuje modele, źródła, podglądy oraz użyty kod.

Szczegółowe paczki mają jawny budżet v5 na rozmiar pliku i trójkąty. Dawne limity prostych modeli (32 MiB i 280 000 trójkątów) pozostają zmierzonymi wynikami w raporcie; ich zastąpienie jest oznaczone jako `SUPERSEDED`, bez zamiany nieudanego pomiaru na PASS. Osobna obowiązkowa kontrola egzekwuje stałe limity szczegółowej serii. Eksport współdzieli identyczne bajty map i UV oraz korzysta z odtwarzanego przez glTF układu stycznych; nie zmniejsza głównych map ani nie kwantyzuje geometrii. Powtarzane komentarze i przełączniki procesu budowania pozostają w scenach Blender oraz dokumentacji; GLB zachowuje geometrię, materiały, przebieg słojów, oznaczenia części i rzeczywiste mocowania takielunku.

Dostawa zawiera osobne główne GLB i dwa LOD-y dla każdego malowania, dwie spakowane sceny Blender, źródłowe mapy, wspólną dokładną kolizję kadłuba i pokładów oraz raporty. Kolizja wymaga obsługi statycznych siatek wklęsłych. Kontrole dojść dotyczą fizycznej geometrii w zapisanej pozie. Kontrolery żeglugi, załogi, obsługi dział i ruchu gracza nie są częścią modeli.

Nowy kod pozostaje w `potc/common/v5_*.py`. Wcześniejsze moduły v4, oryginalne skrypty poradnika i modele wcześniejszej floty są zachowane.
