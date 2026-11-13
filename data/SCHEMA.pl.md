# Pliki danych modelu wzorcowego

Wszystkie pliki w `data/` zapisują skrypty generatora z tych samych parametrów co model 3D. Nie poprawiaj ich ręcznie:
zmień parametry i uruchom eksport ponownie (zob. główny README).

## Układ współrzędnych (wszystkie pliki)

Każdy punkt zapisany jest jako **[x, s, z] w metrach**:

| Oś | Kierunek | Zero |
|---|---|---|
| x | w poprzek, **dodatnio ku lewej burcie** | płaszczyzna symetrii |
| s | wzdłuż, **dodatnio ku dziobowi** | środek 28,0 m długości pokładu między wrębami (wrąb dziobnicy na pokładzie s = +14,0, tylnica s = −14,0) |
| z | w górę | wodnica konstrukcyjna |

Trójka (s, x, z) jest prawoskrętna. Przeliczenia:

- glTF / plik gry (+Y w górę): (X, Y, Z) = (x, z, s); dziób ku +Z.
- Blender (Z w górę): (X, Y, Z) = (x, −s, z); dziób ku −Y.
- Notatki badawcze liczą wręgi od owręża: s = z_df + 1,96.

Wielokąty w rzucie to [x, s]. Pliki JSON mają ten opis w polu `coordinate_system`; pliki CSV zaczynają się od wierszy
komentarza z `#` (w pandas: `comment="#"`, albo pomiń wiersze zaczynające się od `#`).

## Źródła i pewność

Każda wartość w `parameters.json` ma `confidence` (`period` – źródło z epoki, `secondary` – literatura wtórna,
`our inference` – nasze wnioskowanie, `reference model` – wybór modelu wzorcowego) i `source` (rozdział przewodnika,
np. `docs/pl/02-hull-lines-and-offsets.md` w wersji polskiej, w pliku podany odnośnik do wersji angielskiej).

## Pliki

### parameters.json
Wszystkie parametry generatora w grupach: `hull` (kadłub), `decks` (pokłady), `stern_and_head` (rufa i dziób),
`spars` (drzewca), `standing_rigging` (olinowanie stałe), `running_rigging` (olinowanie ruchome), `sails` (żagle),
`fittings` (wyposażenie), `steering` (sterowanie), `materials` (materiały), `variants` (warianty). Każda wartość:
`value`, `unit` (gdy klucz nie kończy się jednostką), `confidence`, `source`, `note`. Końcówki kluczy podają
jednostkę: `_m` metry, `_deg` stopnie, `_m2` metry kwadratowe; `_s_z_m` – lista punktów [s, z].

### offsets.csv, offsets.json
Linie kadłuba. `offsets.csv` to długa tabela o kolumnach `table, station_s_m, station_z_df_m, line, line_value_m,
half_breadth_m, z_m`:

| table | zawartość |
|---|---|
| research_moulded | rzędne z badań, po wręgach (bez poszycia): spód stępki, wrąb, linia brody (z), wodnice −2,5 … +0,5 (line_value_m = z wodnicy, half_breadth_m), pokład przy burcie, największa szerokość, reling w śródokręciu |
| generator_outside_planking | tabela generatora: półszerokości po zewnętrznej stronie poszycia na liniach równoległych do wrębu stępki, line_value_m = wysokość nad wrębem; z_m = z wrębu + wysokość |
| buttock_generator | wysokość dna tam, gdzie powierzchnia generatora osiąga półszerokość line_value_m (1, 2, 3 m) |
| stem_rabbet, sternpost_rabbet, transom_centreline | punkty profilu (s, z) |
| transom_half_breadth | półszerokość końca rufowego na wysokości z |
| deck_at_side, rail_top | linia pokładu przy burcie i górna krawędź relingu wzdłuż s |

`offsets.json` – te same liczby w postaci uporządkowanej.

### spars.csv
Wiersz na drzewce: długość, średnice (największa, w środku, na końcu), początek i koniec (pięta i top masztu, noki rei
lewy i prawy, szczęki i nok gafla), kąt (pochylenie masztu od pionu, wznios bukszprytu, kąt gafla), wysokości pokładu,
marsa, początku topu, salingu, ezelhoftu i gałki, dla rej wysokość opuszczona i podniesiona.

### rigging-lines.json
`belaying_points` (kołki nagielbanków, kołkownic i knagi: `id`, `kind`, `position`, `ropes`), `ropes` (wpis na
nazwaną linę z długością, liczbą odcinków, kołkiem) i `lines` – 1317 odcinków 836 lin. Pola odcinka: nazwa
liny i numer odcinka, grupa, rodzaj (`standing` stała, `running` ruchoma, `coil` buchta), materiał (`tarred`
smołowana, `untarred` jasna), średnica, długość, początek, koniec i punkty pośrednie [x, s, z], rodzic (drzewce,
z którym lina się obraca), części ruchome pod końcami (`from_object`, `to_object`, `dynamic`), końce w układzie
lokalnym tych części, wariant (końce: `from`, `to`, punkty pośrednie `via`), kołek ostatniego odcinka (`belayed_to`), `one_sided` (lina tylko po jednej burcie).

### rigging-summary.csv
Sumy na grupę lin: liczba lin i odcinków, łączna długość, najmniejsza i największa średnica.

### deck-layout.json
Dane do chodzenia: `surfaces` (wielokąty pokładów [x, s], wzór wysokości i siatka z; marsy z otworami; ławy
wantowe), `obstacles` (prostokąty i koła w rzucie z wysokością, `walkable`, `step_height_m`), `stairs`, `passages`,
`climbs` (łamane po wantach), `side_edge` (wysokość relingu wzdłuż s), `walker` (promień i wzrost postaci testu).

### stations.csv
142 stanowisk czynności: nazwa, czynność, poziom, położenie stóp, kierunek patrzenia i kąt (0° = ku dziobowi,
+90° = ku lewej burcie), obiekt, jego oś i zakres, wysokość rąk, liny w rękach.

### moving-parts.csv
Każda część ruchoma: rodzaj (obrót albo przesunięcie), opis osi, punkt obrotu, oś lokalna Z w układzie statku, zakres
i jednostka, stan spoczynkowy, wariant, co ogranicza zakres; dla rej zakres brasowania opuszczonej i podniesionej
(`range_hoisted_*`) i wysokość podniesienia `working_height_dz_m`; przełożenie koła sterowego (obroty na 35°) i wzór.

### names-map.csv
2140 wierszy: polskie nazwy obiektów, węzłów glTF, kluczy i wartości używanych przez skrypty generatora →
angielskie nazwy użyte w danych. Ta tabela posłuży do angielskiej wersji skryptów.

## Odczyt w Pythonie

```python
import csv, json

def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))

P = json.load(open("data/parameters.json", encoding="utf-8"))
print(P["groups"]["spars"]["values"]["main_mast_length_m"])

spars = {r["spar"]: r for r in read_csv("data/spars.csv")}
print(spars["main_mast"]["length_m"], spars["main_mast"]["cap_z_m"])

R = json.load(open("data/rigging-lines.json", encoding="utf-8"))
wanty = [l for l in R["lines"] if l["group"] == "main_shrouds"]
print(len(wanty), sum(l["length_m"] for l in wanty))
```

## Jak narysować statek bez Blendera

1. **Profil i wręgi.** Z `offsets.csv` weź `generator_outside_planking` (albo `research_moulded` dla linii po
   wręgach). Dla każdej stacji narysuj punkty (half_breadth_m, z_m) – to wręg. Dla każdej wysokości narysuj
   (station_s_m, half_breadth_m) wzdłuż statku – to linia równoległa do stępki w rzucie z góry. Końce zamknij punktami
   `stem_rabbet` i `transom_*`; w profilu dorysuj `deck_at_side` i `rail_top`. Wygładzaj krzywą sklejaną, nie odcinkami.
2. **Drzewca.** Z `spars.csv` narysuj każde drzewce jako zwężający się odcinek od `start` do `end` (widok z boku:
   s poziomo, z pionowo), średnice `d_max_m`, `d_mid_m`, `d_end_m`; zaznacz wysokości marsów, ezelhoftów, salingów.
3. **Liny.** Z `rigging-lines.json` narysuj każdy odcinek od `from` przez `via` do `to` (z boku: s, z; z przodu: x, z).
   Grubość kreski ∝ `diameter_m`; liny smołowane ciemne, jasne – jasne.
4. **Pokład.** Z `deck-layout.json` narysuj wielokąty pokładów, przeszkody i schody w rzucie (x, s), a stanowiska
   z `stations.csv`.
5. Wszystkie rysunki w `plans/` powstały właśnie tak, skryptem, z tych liczb.
