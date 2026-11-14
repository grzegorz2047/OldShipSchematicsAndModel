# Dodatkowe warianty łodzi SailerTales

Audyt kodu gry przypięto do commita [`ea77e560`](https://github.com/grzegorz2047/SailerTales/tree/ea77e560ba4668c9dda55433813addbdb2f50176). Rejestr fabuły kończy się na `a1_3`; typy `boat_frame` i `capsized_boat` są zarejestrowane i używane. Uzupełnienie obejmuje te dwa warianty kadłuba „Mewki”, a nie dwie nowe klasy jednostek.

| Wariant | Rzeczywiste użycie | Wymagany kontrakt modelu |
|---|---|---|
| **Łódź w budowie / naprawie** (`boat_frame`) | A1.1: etap 3, praca na burcie wybranej według pozycji ojca. Po A1.3: nowy szkielet na pochylni, etap 0. Próba deweloperska korzysta z etapów 0–3. | Cztery grupy etapów; osobna deska w luce na dowolnej burcie, listwy i ławki, pięć kołków, trzy miejsca przecieków, dwa znaki na stewie i punkty interakcji. Bez masztu i steru. |
| **Wywrócona łódź ojca** (`capsized_boat`) | A1.3: scena ratunku i odtworzenie punktu kontrolnego; obrót w planie 0,6 rad, dryf z wiatrem 0,2 m/s. | Odwrócony kadłub, nalot, pływające wiosło, lina za rufą i luźne płótno. Oddzielne punkty siedzenia na kadłubie i trzymania się burty z wody; parametry pływania. |

Wspólny profil źródłowy ma **6,5 m długości, 1,72 m pełnej szerokości i 0,92 m wysokości burty na śródokręciu**. `HULL.B = 0.86` oznacza półszerokość. Kozły, stercząca deska, lina i inne dodatki powiększają obrys całego assetu. Wywołania misji nie zmieniają skali; zarządca rekwizytów przyjmuje domyślnie skalę 1.

Etapy budowy to kolejno: stępka, stewy i pięć wręgów; pozostałe cztery wręgi oraz trzy dolne pasy poszycia; trzy następne pasy; dwa górne pasy z listwami i ławkami. W A1.1 prawie gotowa łódź zachowuje osobną lukę w pasie `j=4`, na odcinku `u=-0.42…0.42` (2,73 m w rzucie wzdłużnym). Stan naprawy zmieniają `setGapPlank`, `setPegs`, `setWater`, `setLeak`, `setMarks`, `carve` i `setTrim`; `point` podaje współrzędne świata dla deski, kołków, przecieków, kropli i znaków.

Dla wywrotki źródłowy punkt siedzenia wynosi `(0.4, 0.185, 0)`; oblicza się go z powierzchni kadłuba, zamiast używać stałej wysokości. Druga gałąź sceny trzyma ojca przy burcie w `(1.15, -1.05, 0)`. Pływanie ma `lift=0`, `span=2.4`, `beam=0.7`, `bob=0.03`, `sway=0.09`, `tilt=0.7`. Źródłowy komentarz o szczycie stępki 0,38 m nie uwzględnia całego przekroju belki: zmiana geometrii lub linii wody wymaga jawnego odstępstwa i ponownego wyznaczenia podparcia siedzenia. Te warianty wymagają obsługi budowy i ratunku; kod źródłowy nie obiecuje chodzenia stojącą postacią po szkielecie ani po odwróconym dnie.

## Typy występujące w planie M2

| Planowany typ | Stan w sprawdzonym commicie |
|---|---|
| `cutter` — kuter celny | Brak fabryki i wywołania w czynnej grze. Plan przewiduje patrol z latarnią i trzema ludźmi; nie określa wymiarów kadłuba. |
| `longboat` — szalupa Hallowaya i Skerry'ego | Rekwizyt przyszłych A1.6 i A1.8. Nie jest to istniejąca mała szalupa szybkiej podróży. Brak wymiarów kadłuba. |
| `sloop` — „Paloma Negra” | Przyszły nieoświetlony slup przemytników. Nie jest dekoracyjnym slupem osady ani istniejącym wariantem wraku na rafie. Brak profilu liczbowego. |
| `raceboat` | Cztery planowane warianty z żaglem i odcieniami płótna, oparte na `dugout_canoe.glb`. Brak czynnego modułu regat i fabryki tego typu. |

Kontrakt M2 sam oznacza ten zakres jako projekt do akceptacji, jeszcze niezbudowany. Bieżący `night_hull` z prologu jest już osobnym rekwizytem; komentarz misji wprost zaznacza brak właściwego slupa Kapitanatu. Aktywny dekoracyjny `createSloop(..., { scale: 0.6 })` z osady ma inny cel niż planowana „Paloma Negra”.

## Źródła kodu i zakresu

- [Rejestr misji](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/missions/index.js#L17-L21) oraz [rejestr rekwizytów i domyślna skala](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/props.js#L19-L32) / [tworzenie egzemplarza](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/props.js#L105-L123).
- [Profil wspólnego kadłuba](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/models/hull.js#L6-L27), [fabryka etapów budowy](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/models/boat.js#L8-L51) i [interakcje naprawy](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/models/boat_work.js#L8-L25) / [API punktów i stanu](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/models/boat_work.js#L164-L207).
- [Wywołanie budowy w A1.1](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/missions/a1_1.js#L1151-L1157), [przywracanie postępu naprawy](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/missions/a1_1.js#L465-L475) oraz [szkielet po A1.3](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/missions/a1_3.js#L2718-L2724).
- [Fabryka wywrotki i punkt siedzenia](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/models/boat.js#L54-L104), [obie pozycje ojca](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/missions/a1_3.js#L358-L371) oraz [rzeczywisty spawn ratunku](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/missions/a1_3.js#L1867-L1875).
- [Status projektu M2](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/docs/kampania/M2_KONTRAKT.md#L3-L3), [lista brakujących typów](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/docs/kampania/M2_KONTRAKT.md#L31-L38), [planowane modele](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/docs/kampania/M2_KONTRAKT.md#L241-L245) i [przemytnicza scena A1.6](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/docs/kampania/M2_SCENARIUSZ.md#L528-L542).
- [Brak slupa Kapitanatu w prologu](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/campaign/missions/prolog.js#L30-L33) oraz [dekoracyjny slup osady](https://github.com/grzegorz2047/SailerTales/blob/ea77e560ba4668c9dda55433813addbdb2f50176/src/colony/colony.js#L953-L956).
