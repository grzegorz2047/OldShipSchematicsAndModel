"""Słownik etykiet rysunków: tekst angielski (klucz, jak na arkuszu angielskim) → polski; zloz() składa polskie nazwy
lin z części (reja, rodzaj liny, burta). Brakujące etykiety: <cache>/brakujace_etykiety.txt po przebiegu rysunki.py."""
import re

PL = {
    # tabelka i ogólne
    "Scale": "Skala", "Sheet": "Arkusz", "Format": "Format", "dimensions in metres": "wymiary w metrach",
    "Reference model - snow, about 1710 - drawn by script from the model parameters":
        "Model wzorcowy - snow, ok. 1710 - rysunek ze skryptu, z parametrów modelu",
    "Plan": "Rzut z góry", "Total": "Razem", "forward": "ku dziobowi", "other": "inne", "port": "furta",
    # plan linii
    "Lines plan": "Plan linii teoretycznych", "Sheer plan (profile)": "Rzut boczny (profil)",
    "Half-breadth plan": "Rzut z góry (półszerokości)", "Body plan": "Rzut wręgów", "aft body": "część rufowa",
    "fore body": "część dziobowa", "Buttock": "Przekrój wzdłużny", "B": "P",
    "Length between rabbets at the deck": "Długość między wrębami na pokładzie", "draught at s = 0": "zanurzenie w s = 0",
    "dead flat": "owręże", "from AP": "od pionu rufowego", "Deck at side": "Pokład przy burcie",
    "Quarterdeck at side": "Pokład rufowy przy burcie", "Rail (top of cap)": "Reling (wierzch pokrywy)",
    "Keel rabbet": "Wrąb stępki", "Keel and false keel": "Stępka i fałszywa stępka", "Stem": "Dziobnica",
    "Sternpost, rake": "Tylnica, pochylenie", "Counter and transom": "Kontra i pawęż", "Rail": "Reling",
    "half-breadth": "półszerokość", "greatest breadth": "największa szerokość", "breadth": "szerokość",
    "Stations, waterlines every 0.5 m, buttocks 1, 2, 3 m; lines to the outside of the planking (generator surface)":
        "Wręgi, wodnice co 0,5 m, przekroje wzdłużne 1, 2, 3 m; linie po zewnętrznej stronie poszycia (powierzchnia "
        "generatora)",
    "On A3 the drawing is at 1:96 - use the scale bar.": "Na arkuszu A3 rysunek jest w skali 1:96 - mierz podziałką.",
    "Sheer plan and body plan: z above the design waterline; half-breadth plan: x from the centreline.":
        "Profil i rzut wręgów: z nad wodnicą konstrukcyjną; rzut z góry: x od płaszczyzny symetrii.",
    "Lines as generated from the table; the run below WL -1.0 is not faired (bumps of 1-5 cm), "
    "see guide chapter 02.":
        "Linie wprost z tabeli; wybieg poniżej wodnicy -1,0 nie jest wygładzony (nierówności 1-5 cm), "
        "patrz rozdział 02 przewodnika.",
    "Table of offsets (research table, moulded, m)": "Tabela rzędnych (z badań, po wręgach, m)",
    "keel": "stępka", "rabbet": "wrąb", "deck z": "pokład z", "deck y": "pokład y", "rail z": "reling z",
    "rail y": "reling y",
    "Generator table (outside planking, lines parallel to the keel): data/offsets.csv":
        "Tabela generatora (po poszyciu, linie równoległe do stępki): data/offsets.csv",
    # wręg łukami
    "Frame construction by arcs": "Wręg wykreślony łukami",
    "Midship frame (s = +1.96) drawn with arcs, moulded": "Wręg owręża (s = +1,96) wykreślony łukami, po wręgach",
    "Deadrise line, floor sweep, breadth sweep, top-timber sweep (chapter 02)":
        "Linia wzniosu dna, łuk obła, łuk szerokości, łuk nadburcia (rozdział 02)",
    "generator frame, outside of planking": "wręg generatora, po poszyciu", "Arc data (m)": "Dane łuków (m)",
    "rms vs. table": "błąd śr. kw. wobec tabeli",
    "Crosses: research offsets of this station. Dashed: generator frame outside the planking.":
        "Krzyżyki: rzędne z badań dla tej stacji. Kreskowo: wręg generatora po poszyciu.",
    "α fitted to the research offsets of the station (least squares).":
        "α dobrany do rzędnych z badań tej stacji (najmniejsze kwadraty).",
    # konstrukcja
    "Hull structure - profile": "Konstrukcja kadłuba - profil",
    "Structural profile (planking removed, one frame in four)": "Profil konstrukcyjny (bez poszycia, co czwarty wręg)",
    "Backbone, frames, wales, clamp, beams and knees": "Stępka i stewy, wręgi, berghołty, wzdłużnik, pokładniki, knagi",
    "Members not built in the 3D model (keelson, frames, beams, knees, apron) use the proportions of chapter 03 "
    "(our inference).": "Elementy, których nie ma w modelu 3D (nadstępka, wręgi, pokładniki, knagi, fartuch), mają "
                        "proporcje z rozdziału 03 (nasze wnioskowanie).",
    "scarph": "zamek", "Keel (moulded 0.30, sided 0.26)": "Stępka (wys. 0,30, szer. 0,26)",
    "False keel 0.06": "Fałszywa stępka 0,06", "Stem (moulded 0.35)": "Dziobnica (gr. 0,35)", "Apron 0.40": "Fartuch 0,40",
    "Gripe (forefoot)": "Ostroga (stopa dziobnicy)", "Sternpost (0.40 heel, 0.28 head)": "Tylnica (0,40 u pięty, 0,28 u góry)",
    "Deadwood aft (to the bearding line)": "Drewno martwe rufowe (do linii brody)",
    "Keelson 0.25 × 0.28 on the floors": "Nadstępka 0,25 × 0,28 na dennikach",
    "Frames 0.20 sided, room and space 0.52": "Wręgi szer. 0,20, rozstaw 0,52",
    "Main wales 2 × 0.26 + 0.22": "Berghołty 2 × 0,26 + 0,22", "Clamp 0.30 × 0.12 (hidden)": "Wzdłużnik 0,30 × 0,12 (niewidoczny)",
    "Deck beams 0.22 × 0.20, every 1.2": "Pokładniki 0,22 × 0,20, co 1,2", "Hanging knee, arm 0.9": "Knaga pionowa, ramię 0,9",
    "Gun port 0.60 × 0.50 (hidden)": "Furta 0,60 × 0,50 (niewidoczna)", "Knee of the head": "Kolano galionu",
    "Quarterdeck beams": "Pokładniki pokładu rufowego", "Keel section": "Przekrój stępki",
    "Garboard strake 0.065": "Pas przystępkowy 0,065", "False keel": "Fałszywa stępka", "Rabbet": "Wrąb",
    "Bow detail": "Szczegół dziobu", "Stern detail": "Szczegół rufy",
    "Midship section": "Przekrój na owrężu", "Midship section s = +1.96, port half (looking forward)":
        "Przekrój na owrężu s = +1,96, lewa połowa (widok ku dziobowi)",
    "Structure at the dead flat; planking outside the generator surface":
        "Konstrukcja na owrężu; poszycie po powierzchni generatora",
    "Keelson, frames, ceiling, clamp, beams and knees: proportions of chapter 03 (our inference);":
        "Nadstępka, wręgi, poszycie wewnętrzne, wzdłużnik, pokładniki i knagi: proporcje z rozdziału 03 (nasze "
        "wnioskowanie);",
    "hull surface, wales, deck, bulwark, rail and ports from the model parameters.":
        "powierzchnia kadłuba, berghołty, pokład, nadburcie, reling i furty z parametrów modelu.",
    "Floor": "Dennik", "First futtock": "Pierwsze kolano wręgu", "Second futtock": "Drugie kolano wręgu",
    "Top timber": "Wierzchołek wręgu", "Keel": "Stępka", "Keelson": "Nadstępka", "Limber hole": "Otwór ściekowy",
    "Ceiling 0.05": "Poszycie wewnętrzne 0,05", "Clamp 0.30 × 0.12": "Wzdłużnik 0,30 × 0,12",
    "Deck beam 0.22 × 0.20, camber 0.12": "Pokładnik 0,22 × 0,20, wypukłość 0,12", "Hanging knee": "Knaga pionowa",
    "Waterway 0.25 × 0.10": "Ściek 0,25 × 0,10", "Deck planks 0.07": "Deski pokładu 0,07",
    "Spirketting 0.06": "Poszycie nadburcia od środka 0,06", "Bulwark 0.14": "Nadburcie 0,14",
    "Rail cap 0.30 × 0.07": "Pokrywa relingu 0,30 × 0,07", "Main wale": "Berghołt", "Middle strake": "Pas środkowy",
    "Channel (at the masts only)": "Ława wantowa (tylko przy masztach)", "Channel wale": "Pas pod ławą",
    "Port sill": "Próg furty", "Port lintel": "Nadproże furty", "Planking 0.065": "Poszycie 0,065",
    "deck at side": "pokład przy burcie", "half-breadth at rail": "półszerokość przy relingu",
    # plan pokładu
    "Deck plan": "Plan pokładu", "Deck plan: main deck and quarterdeck": "Plan pokładu: pokład główny i rufowy",
    "Main deck and quarterdeck with fittings, walkways, recoil zones and work stations":
        "Pokład główny i rufowy z wyposażeniem, przejściami, strefami odrzutu i stanowiskami",
    "Stations aloft (tops, yardarms, shrouds, channels) are listed but not drawn.":
        "Stanowiska na górze (marsy, noki rei, wanty, ławy) – w wykazie, bez rysunku.",
    "Dashed outlines: obstacles one can step over (cable, thresholds).":
        "Obrys kreskowy: przeszkody do przekroczenia (lina, progi).",
    "Guns labelled P (port) / S (starboard) and number from forward.":
        "Działa: P (port – lewa burta) / S (starboard – prawa) i numer od dziobu.",
    "Guns run out; orange: recoil zone": "Działa wytoczone; pomarańczowo: strefa odrzutu", "Pin rail": "Kołkownica",
    "Anchor cable (step over)": "Lina kotwiczna (do przekroczenia)", "Fore mast": "Fokmaszt", "Main mast": "Grotmaszt",
    "Snow mast": "Maszt snow", "Circle swept by the capstan bars": "Koło drągów kabestanu",
    "Ladder to the quarterdeck": "Schody na pokład rufowy", "Quarterdeck break": "Próg pokładu rufowego",
    "deck length between rabbets": "długość pokładu między wrębami", "breadth at the rail": "szerokość przy relingu",
    "Work stations (numbers on the plan; data/stations.csv)": "Stanowiska czynności (numery na planie; data/stations.csv)",
    "walkways at least 0.8 m wide (from the walking test of the model)":
        "przejścia o szerokości co najmniej 0,8 m (z testu chodzenia modelu)",
    "recoil zone of each gun (to the first obstacle)": "strefa odrzutu działa (do pierwszej przeszkody)",
    "Arms chest": "Skrzynia broni", "Bell": "Dzwon", "Binnacle": "Szafka kompasowa", "Companion": "Zejściówka",
    "Deck tiller": "Rumpel na pokładzie", "Fore fife rail": "Nagielbank foka", "Fore hatch": "Luk dziobowy",
    "Galley chimney": "Komin kambuza", "Hen coop": "Kojec", "Hen coop port": "Kojec lewy", "Hen coop starboard": "Kojec prawy", "Main fife rail": "Nagielbank grota", "Main hatch": "Luk główny",
    "Pump port": "Pompa lewa", "Pump port brake": "Dźwignia pompy lewej", "Quarterdeck ladder": "Schody rufowe",
    "Steering wheel": "Koło sterowe", "Water cask": "Beczka wody", "Wheel standards": "Stojaki koła", "Bowsprit": "Bukszpryt",
    "gun captain": "działo – celowniczy", "gun loader": "działo – ładowniczy", "gun sponger": "działo – wyciorowy",
    "gun side tackle": "działo – talia boczna", "gun train tackle": "działo – talia odciągowa",
    "gun powder boy": "działo – chłopiec prochowy", "port lid": "pokrywa furty", "capstan": "kabestan", "pump": "pompa",
    "hatch": "luk", "wheel": "koło", "rudder": "ster", "compass": "kompas", "bell": "dzwon", "boat": "łódź",
    "anchor": "kotwica", "cathead": "kotbelka", "water cask": "beczka", "braces": "brasy", "vangs": "gaje",
    "clewlines": "gejtawy", "sheets": "szoty", "lifts": "topenanty", "halliards": "fały", "shrouds climb": "wejście na wanty",
    "top": "mars", "yardarm": "nok rei", "hand lead": "sonda ręczna", "log line": "log",
    # rufa i dziób
    "Stern and head": "Rufa i dziób", "Stern seen from aft": "Rufa – widok od tyłu", "Head from starboard":
        "Galion – widok z prawej burty",
    "Projected from the 3D model with hidden lines removed; dimensions from the parameters":
        "Rzut modelu 3D z usuniętymi liniami zasłoniętymi; wymiary z parametrów",
    "Visible edges solid, hidden edges dashed (ray test against all meshes);":
        "Krawędzie widoczne ciągłe, niewidoczne kreskowe (test promieniem wobec wszystkich siatek);",
    "in the stern view hidden edges are left out for legibility.":
        "w widoku rufy krawędzie niewidoczne pominięte dla czytelności.",
    "breadth of the stern": "szerokość rufy", "Stern lantern": "Latarnia rufowa",
    "Carvings, pilasters, frieze": "Snycerka, pilastry, fryz", "Quarter piece": "Narożnik rufy", "Rudder": "Ster",
    "Upper transom": "Pawęż górna", "Windows": "Okna", "Counter": "Kontra", "Lower (flat) transom": "Pawęż dolna (płaska)",
    "Wing transom": "Pawęż skrzydłowa", "stem head": "głowica dziobnicy", "knee": "kolano",
    "Knee of the head with scroll": "Kolano galionu ze zwojem", "Figure / scroll": "Figura / zwój",
    "Cheeks and head rails": "Policzki i relingi galionu", "Grating (head)": "Krata galionu", "Hawse hole": "Kluza",
    "Cathead": "Kotbelka", "projects": "wysięg", "steeve": "wznios", "Gripe": "Ostroga",
    # sterowanie
    "Steering gear": "Urządzenie sterowe", "Wheel variant, side view from starboard": "Wariant z kołem, widok z prawej burty",
    "Wheel variant, plan": "Wariant z kołem, rzut z góry", "Deck tiller variant, plan": "Wariant z rumplem, rzut z góry",
    "axle": "oś", "Wheel, 10 spokes": "Koło, 10 szprych", "Drum": "Bęben", "turns of tiller rope": "zwojów sterliny",
    "Standards": "Stojaki", "Tiller below the quarterdeck": "Rumpel pod pokładem rufowym", "depth": "głębokość",
    "Rudder head (axis)": "Głowica steru (oś)", "tiller": "rumpel", "Tiller arc ±35°": "Łuk rumpla ±35°",
    "Sheaves in the deck and blocks at the sides": "Krążki w pokładzie i bloki przy burtach",
    "Relieving tackles to the bulwark rings": "Talie odciążające do pierścieni w nadburciu",
    "Gear ratio of the wheel": "Przełożenie koła sterowego", "turns": "obrotu",
    "L - tiller length, D - drum diameter; turns of the wheel for 35° of rudder.":
        "L – długość rumpla, D – średnica bębna; obroty koła na wychylenie steru o 35°.",
    "Tiller rope": "Sterlina", "Wheel, drum, tiller rope, tiller; deck tiller variant":
        "Koło, bęben, sterlina, rumpel; wariant z rumplem na pokładzie",
    "Fittings projected from the 3D model; tiller ropes from the rigging data.":
        "Okucia z rzutu modelu 3D; sterliny z danych lin.",
    # kabestan
    "Capstan": "Kabestan", "Capstan bars": "Drągi kabestanu", "Swifter": "Lina spinająca drągi",
    "Circle swept by the bars": "Koło zakreślane drągami", "Elevation from starboard": "Widok z prawej burty",
    "height": "wysokość", "bars at": "drągi na", "Drumhead with bar holes": "Głowica z gniazdami drągów",
    "Barrel with whelps": "Bęben z żebrami", "Pawl rim and pawls": "Pierścień zapadek i zapadki", "Bar": "Drąg",
    "Pawl rim, barrel with whelps, drumhead, bars, swifter": "Pierścień zapadek, bęben z żebrami, głowica, drągi, lina",
    "Projected from the 3D model; the barrel turns about its vertical axis without limit.":
        "Rzut modelu 3D; bęben obraca się wokół osi pionowej bez ograniczeń.",
    # kotwica
    "Anchor and cathead": "Kotwica i kotbelka", "Bower anchor, arms in the plane of the drawing":
        "Kotwica główna, ramiona w płaszczyźnie rysunku", "shank": "trzon", "span of the arms": "rozstaw ramion",
    "Ring": "Pierścień", "Stock (end on)": "Poprzeczka (z czoła)", "Shank": "Trzon", "Crown": "Korona", "Arm": "Ramię",
    "Palm (fluke)": "Łapa", "Bill": "Szpic", "Side view, stock across": "Widok z boku, poprzeczka w poprzek",
    "stock": "poprzeczka", "Wooden stock with iron hoops": "Drewniana poprzeczka z obręczami",
    "Bow from starboard: cathead, hawse, cable": "Dziób z prawej burty: kotbelka, kluza, lina kotwiczna",
    "Starboard anchor let go": "Kotwica prawa rzucona", "Port anchor catted (far side)": "Kotwica lewa na kotbelce (druga burta)",
    "Bower anchor with its parts; catted and let-go positions": "Kotwica główna i jej części; położenie na kotbelce i rzucona",
    "Anchor projected from the 3D model in its own coordinates; cable and cat fall from the rope data.":
        "Kotwica z rzutu modelu 3D w jej własnym układzie; lina kotwiczna i talia kotbelki z danych lin.",
    # pompa
    "Pump": "Pompa", "tube length below deck": "długość rury pod pokładem", "Section through the pump": "Przekrój pompy", "Deck": "Pokład", "brake": "dźwignia",
    "Elm tube (bored trunk)": "Rura z wiązu (wydrążony pień)", "Lower box, fixed valve": "Dolny zawór, stały",
    "Bucket with valve on the spear": "Tłok z zaworem na drągu", "Spear (pump rod)": "Drąg pompy",
    "Brake pivot": "Oś dźwigni", "Spout (dale to the scupper)": "Wylew (rynna do szpigatu)",
    "Foot in the well, above the keelson": "Stopa w studzience, nad nadstępką",
    "Model pump from starboard (port pump)": "Pompa modelu z prawej burty (pompa lewa)",
    "Elm-tree (common) pump: tube, bucket, valves, brake ±25°, spout":
        "Pompa z pnia wiązu: rura, tłok, zawory, dźwignia ±25°, wylew",
    "Section drawn from the parameters (tube Ø, height, brake, swing); valves and tube length: our inference "
    "(chapter 09). The 3D model has only the outside.":
        "Przekrój z parametrów (średnica rury, wysokość, dźwignia, wahanie); zawory i długość rury: nasze wnioskowanie "
        "(rozdział 09). Model 3D ma tylko wygląd zewnętrzny.",
    # działo
    "Gun and carriage": "Działo z lawetą", "Side elevation (looking forward), port gun run out":
        "Widok z boku (ku dziobowi), działo lewej burty wytoczone",
    "sill": "próg", "barrel": "lufa", "trunnions": "czopy", "carriage": "laweta", "recoil": "odrzut",
    "Barrel, 6-pounder": "Lufa 6-funtowa", "Truck carriage": "Laweta na kołach", "Quoin under the breech": "Klin pod zamkiem",
    "Breeching": "Lina hamująca", "Gun port": "Furta",
    "Side tackles to ringbolts in the side": "Talie boczne do pierścieni w burcie",
    "Breeching through the cascabel": "Lina hamująca przez gałkę lufy",
    "6-pounder on a truck carriage with breeching and side tackles":
        "6-funtówka na lawecie z liną hamującą i taliami bocznymi",
    "Gun, carriage and port projected from the 3D model; ropes from the rope data; recoil distance from the model's "
    "clearance test.": "Działo, laweta i furta z rzutu modelu 3D; liny z danych lin; odrzut z testu wolnej drogi modelu.",
    # drzewca
    "Spar plan": "Plan drzewc", "Spar plan, side elevation from starboard": "Plan drzewc, widok z prawej burty",
    "Top": "Mars", "Cap": "Ezelhoft", "Crosstrees": "Saling", "Truck": "Gałka", "Gaff": "Gafel", "Jib-boom": "Bomstenga",
    "Yards end on: lowered (solid), hoisted (dashed)": "Reje z czoła: opuszczone (ciągłe), podniesione (kreskowo)",
    "Yards, gaff (length, diameter at slings / yardarm)": "Reje i gafel (długość, średnica w środku / na noku)",
    "Main top and cap, plan": "Grotmars i ezelhoft, rzut z góry", "Lubber's hole": "Otwór marsa",
    "Masts with rake, heights, yards lowered and hoisted, bowsprit, jib-boom, gaff":
        "Maszty z pochyleniem, wysokości, reje opuszczone i podniesione, bukszpryt, bomstenga, gafel",
    "All lengths, diameters and heights: data/spars.csv.": "Wszystkie długości, średnice i wysokości: data/spars.csv.",
    "Main yard": "Grotreja", "Fore yard": "Fokreja", "Main topsail yard": "Grotmarsreja", "Fore topsail yard": "Fokmarsreja",
    "Spritsail yard": "Blinda reja", "Main topgallant yard": "Grotbramreja", "Fore topgallant yard": "Fokbramreja",
    # olinowanie
    "Standing rigging": "Olinowanie stałe", "Side elevation from starboard": "Widok z prawej burty",
    "View from ahead": "Widok od dziobu", "Shrouds and backstays to the channels": "Wanty i paduny do ław wantowych",
    "Futtock shrouds": "Podwantki",
    "Shrouds, topmast and topgallant shrouds, backstays, stays, bowsprit rigging":
        "Wanty, wanty stengowe i bramstengowe, paduny, sztagi, olinowanie bukszprytu",
    "Each label: rope, number per side and diameter. Ratlines and lanyards thin.":
        "Każdy podpis: lina, liczba na burtę i średnica. Wyblinki i talrepy cienko.",
    "Geometry and lengths: data/rigging-lines.json.": "Geometria i długości: data/rigging-lines.json.",
    "Bobstay": "Watersztag", "Bowsprit shroud": "Wanta bukszprytu", "Gammoning turn": "Zwój wiązania bukszprytu",
    "Jib stay": "Sztag kliwra",
    # jufers
    "Deadeye and lanyard": "Jufers i talrep", "Pair of deadeyes, front view (main shroud)":
        "Para jufersów, widok z przodu (wanta grota)",
    "Shroud Ø %s mm, turned in round the upper deadeye": "Wanta Ø %s mm, opasana wokół górnego jufersa",
    "Chain plate (iron strop) to the wale": "Putting (żelazny strop) do berghołtu", "Holes 3 × at 0.45 R": "Otwory 3 × na 0,45 R",
    "Lanyard Ø %s mm, 6 parts: 1-3 in front, 4-6 behind": "Talrep Ø %s mm, 6 odcinków: 1-3 z przodu, 4-6 z tyłu",
    "Side view with channel": "Widok z boku z ławą wantową", "thickness": "grubość", "channel": "ława",
    "Ship's side": "Burta", "Channel": "Ława wantowa", "Deadeye sizes (reference model)": "Wielkości jufersów (model wzorcowy)",
    "main shroud": "wanta grota", "fore shroud": "wanta foka", "backstays": "paduny",
    "topmast shrouds (in the top)": "wanty stengowe (na marsie)", "deadeye spacing on the channel": "rozstaw jufersów na ławie",
    "Deadeye pair with lanyard, chain plate and channel": "Para jufersów z talrepem, puttingiem i ławą",
    "Lanyard rove as in the model: three parts in front, three behind; knot at the upper back hole.":
        "Talrep jak w modelu: trzy odcinki z przodu, trzy z tyłu; węzeł przy górnej tylnej kipie.",
    # ruchome
    "Running rigging": "Olinowanie ruchome", "Side elevation from starboard, sails furled":
        "Widok z prawej burty, żagle zwinięte",
    "Colour = yard or spar the rope works": "Kolor = reja albo drzewce, które lina obsługuje",
    "Numbers after the names: diameter in mm.": "Liczby po nazwach: średnica w mm.",
    "Starboard ropes shown; port side mirrored.": "Pokazane liny prawej burty; lewa w odbiciu.",
    "Standing rigging in light grey.": "Olinowanie stałe jasnoszare.",
    "Lifts, braces, clewlines, sheets, buntlines, halliards, ties, gaff ropes":
        "Topenanty, brasy, gejtawy, szoty, gordingi, fały, tie, liny gafla",
    "Leads of the reference model (chapter 07); belaying points: belaying plan.":
        "Prowadzenie lin modelu wzorcowego (rozdział 07); kołki: plan kołkowania.",
    "fore yard": "fokreja", "fore topsail yard": "fokmarsreja", "fore topgallant yard": "fokbramreja", "main yard": "grotreja",
    "main topsail yard": "grotmarsreja", "main topgallant yard": "grotbramreja", "spritsail yard": "blinda reja",
    "gaff": "gafel", "throat halliard": "gardafał", "peak halliard": "pikfał", "vang": "gaj", "vang port": "gaj lewy",
    "vang starboard": "gaj prawy", "fore topsail halliard": "fał fokmarsrei", "main topsail halliard": "fał grotmarsrei",
    # gejtawy żagla gaflowego (runda 2e)
    **{"brail %s %d" % (b_en, k): "gejtawa gafla %s %d" % (b_pl, k) for b_en, b_pl in (("port", "lewa"), ("starboard", "prawa"))
       for k in (1, 2, 3)},
    **{"brail leg %s %d" % (b_en, k): "odnoga gejtawy gafla %s %d" % (b_pl, k)
       for b_en, b_pl in (("port", "lewa"), ("starboard", "prawa")) for k in (1, 2, 3)},
    "fore topsail tie": "tie fokmarsrei", "main topsail tie": "tie grotmarsrei", "fore yard sling": "strop fokrei",
    "main yard sling": "strop grotrei",
    # kołkowanie
    "Belaying plan": "Plan kołkowania", "Belaying points, plan (reconstruction)": "Kołki i knagi, rzut z góry (rekonstrukcja)",
    "Pin or kevel - rope belayed (reference model, reconstruction)": "Kołek albo knaga – lina (model wzorcowy, rekonstrukcja)",
    "FF/MF fore/main fife rail, PF/SF/PM/SM pin rails port/starboard fore/main, K kevels; open circles: free pins.":
        "FF/MF nagielbank foka/grota, PF/SF/PM/SM kołkownice lewa/prawa przy foku/grocie, K knagi; puste kółka: wolne kołki.",
    "Which rope is belayed on which pin, cleat or kevel": "Która lina schodzi na który kołek, knagę albo kołek nadburcia",
    "Reconstruction for the reference model; pin rails along the bulwark are a likely anachronism for 1710 (chapter 07).":
        "Rekonstrukcja dla modelu wzorcowego; kołkownice wzdłuż nadburcia to prawdopodobny anachronizm dla 1710 "
        "(rozdział 07).",
    # bloki
    "Blocks and deadeyes": "Bloki i jufersy",
    "Blocks, deadeye and heart - proportions in rope diameters d (drawn for d = 20 mm)":
        "Bloki, jufers i serce – proporcje w średnicach liny d (narysowane dla d = 20 mm)",
    "Single block": "Blok pojedynczy", "Double block": "Blok podwójny", "Fiddle block": "Blok skrzypcowy",
    "Deadeye (main shroud d_s = 49 mm), 1:5": "Jufers (wanta grota d_s = 49 mm), 1:5",
    "Heart (main stay collar, d = 80 mm), 1:5": "Serce (obroża grotsztagu, d = 80 mm), 1:5", "Rules (chapter 08)":
        "Zasady (rozdział 08)", "sheave thickness": "grubość krążka", "sheave diameter": "średnica krążka",
    "block length": "długość bloku", "block breadth": "szerokość bloku", "block thickness": "grubość bloku",
    "deadeye diameter": "średnica jufersa", "deadeye thickness": "grubość jufersa", "heart (our inference)":
        "serce (nasze wnioskowanie)", "1.1 d": "1,1 d", "5.5 d": "5,5 d", "8-9 d": "8-9 d", "0.7 × length": "0,7 × długość",
    "0.5 × length + 0.4 × length per extra sheave": "0,5 × długość + 0,4 × długość na każdy dodatkowy krążek",
    "1.5 × circumference of the shroud": "1,5 × obwód wanty", "D/2": "D/2", "4.4 d outside, hole 2.4 d":
        "4,4 d na zewnątrz, otwór 2,4 d", "Proportions as multiples of the rope diameter": "Proporcje jako wielokrotności średnicy liny",
    "Reference model block lengths: 0.10-0.22 m (lifts 0.14, braces 0.16, topsail halliard 0.20).":
        "Długości bloków w modelu: 0,10-0,22 m (topenanty 0,14, brasy 0,16, fał marsrei 0,20).",
    # żagle
    "Sail plan": "Plan ożaglowania", "Sail plan, all sails set (estimated from the spars)":
        "Plan ożaglowania, wszystkie żagle postawione (oszacowanie z drzewc)",
    "Fore course": "Fok", "Fore topsail": "Fokmarsel", "Fore topgallant": "Fokbramsel", "Main course": "Grot",
    "Main topsail": "Grotmarsel", "Main topgallant": "Grotbramsel", "Spritsail": "Blinda", "Gaff sail (no boom)":
        "Żagiel gaflowy (bez bomu)", "Jib": "Kliwer", "Fore topmast staysail": "Fokstaksel", "Main topmast staysail":
        "Grotsztaksel stengowy", "Main staysail": "Grotsztaksel", "Sail areas (our inference)": "Powierzchnie żagli (nasze wnioskowanie)",
    "Head 0.9 × yard; foot = head of the sail below": "Lik górny 0,9 × reja; lik dolny = lik górny żagla niżej",
    "(course: 0.95 × its yard);": "(żagiel dolny: 0,95 × jego reja);", "yards hoisted to the working position;":
        "reje podniesione do pozycji roboczej;", "courses to 0.3 m above the rail;": "żagle dolne do 0,3 m nad relingiem;",
    "cloths 0.61 m, seams every 0.57 m;": "bryty 0,61 m, szwy co 0,57 m;", "topsails 2 reef bands (1710).":
        "marsle: 2 pasy refowe (1710).", "Square sails drawn in profile as if": "Żagle rejowe narysowane z boku tak, jakby",
    "braced fore and aft (sail plan convention).": "reje były zbrasowane wzdłuż (konwencja planu żagli).",
    "Outlines computed from the spars; seams, reef bands and area of each sail":
        "Obrysy wyliczone z drzewc; szwy, pasy refowe i powierzchnia każdego żagla",
    "The 3D model carries its sails furled; set sails here are an estimate (chapter 08).":
        "Model 3D ma żagle zwinięte; żagle postawione to oszacowanie (rozdział 08).",
    # typy
    "Rigs on one hull": "Ożaglowania na jednym kadłubie", "Snow (reference model, about 1710)": "Snow (model wzorcowy, ok. 1710)",
    "Later brig (gaff sail on the main mast, boom)": "Późniejszy bryg (żagiel gaflowy na grotmaszcie, bom)",
    "Brigantine (no main course)": "Brygantyna (bez grota rejowego)", "Ketch (main and mizzen)": "Kecz (grotmaszt i bezanmaszt)",
    "Mizzen mast": "Bezanmaszt",
    "Snow, later brig, brigantine and ketch on the hull of the reference model":
        "Snow, późniejszy bryg, brygantyna i kecz na kadłubie modelu wzorcowego",
    "Schematic: same hull and spar proportions, sails set; no dimensions.":
        "Schemat: ten sam kadłub i proporcje drzewc, żagle postawione; bez wymiarów.",
}

# ------------------------------------------------------------------ nazwy lin złożone z części
REJE = {"fore yard": "fokrei", "main yard": "grotrei", "fore topsail yard": "fokmarsrei", "main topsail yard": "grotmarsrei",
        "fore topgallant yard": "fokbramrei", "main topgallant yard": "grotbramrei", "spritsail yard": "blindy rei"}
LINY_R = {"lift": "topenanta", "brace": "bras", "brace pendant": "wisior brasu", "clewline": "gejtawa",
          "clew garnet": "gejtawa", "sheet": "szot", "buntline": "gording", "sling": "strop", "footrope": "perta",
          "stirrup": "strzemię"}
MASZT = {"main": ("grota", "grotstengi", "grotbramstengi", "grotsztag"), "fore": ("foka", "fokstengi", "fokbramstengi",
                                                                                    "foksztag")}
STALE = {"shroud": ("wanta", 0), "topmast shroud": ("wanta", 1), "topgallant shroud": ("wanta", 2),
         "topmast backstay": ("padun", 1), "topgallant backstay": ("padun", 2), "topmast stay": ("sztag", 1),
         "topgallant stay": ("sztag", 2), "futtock shroud": ("podwantka", 0), "catharpin": ("ściągacz want", 0),
         "deadeye strop": ("strop jufersa", 0), "shroud eye at masthead": ("pętla want na topie", 0),
         "stay collar": ("obroża sztagu", 3), "stay lanyard": ("talrep sztagu", 3)}


def zloz(en):
    """Polska nazwa liny albo podpisu złożonego z części (np. 'fore topsail yard brace port', 'Main topmast stay')."""
    t = en.strip()
    m = re.match(r"^(.*?)( port| starboard)?$", t)
    base, side = m.group(1), (m.group(2) or "").strip()
    sfx = {"port": " (L)", "starboard": " (P)", "": ""}[side]
    low = base.lower()
    for y, yg in sorted(REJE.items(), key=lambda kv: -len(kv[0])):
        if low.startswith(y + " "):
            r = low[len(y) + 1:]
            if r in LINY_R:
                out = "%s %s%s" % (LINY_R[r], yg, sfx)
                return out[0].upper() + out[1:] if base[0].isupper() else out
    m = re.match(r"^(main|fore) (.+)$", low)
    if m and m.group(2) in STALE:
        nazwa, poz = STALE[m.group(2)]
        g = MASZT[m.group(1)]
        if poz == 3:
            out = "%s %s" % (nazwa.replace("sztagu", ""), g[3] + "u") if False else "%s %s" % (
                nazwa.replace(" sztagu", ""), g[3] + "u")
        else:
            out = "%s %s" % (nazwa, g[poz])
        out += sfx
        return out[0].upper() + out[1:] if base[0].isupper() else out
    if low in ("main stay", "fore stay"):
        return MASZT[low.split()[0]][3].capitalize() + sfx
    return None
