"""Parametry brygu (jeden plik): wymiary, profil, tabela rzędnych, pokład, drzewca, olinowanie, wyposażenie,
malowanie, materiały. Moduł czystego Pythona (bez bpy) – czyta go też tekstury/kontrola.

Układ statku: s – wzdłuż (+ ku dziobowi), x – w poprzek (+ lewa burta), z – w górę od linii wodnej (m).
Każda grupa liczb ma odwołanie do rozdziału przewodnika (docs/pl/, docs/en/), w którym opisane są źródła
i reguły, albo słowo „przyjęte” z uzasadnieniem; świadome odstępstwa od źródeł są opisane przy parametrze
(„świadome odstępstwo”).

Inny statek (kuter, slup, mniejszy bryg): skopiuj słownik BRYG, zmień liczby (albo skaluj tabelę rzędnych
przez SKALA) i podaj nazwę w wierszu poleceń: buduj.py -- --statek KUTER.
"""
import math

# ------------------------------------------------------------------ kadłub: profil i rzędne
# Źródło: rozdział 02 przewodnika (liczby kształtu, tabela rzędnych po wręgach), rozdział 03 (konstrukcja)
# i rozdział 04 (pokład, nadburcie, rufa, dziób). Układ notatek badawczych: z_dok = 0 na owrężu (12,04 m za
# dziobnicą); tu s = z_dok + 1,96,
# więc środek długości pokładu (28 m między wrębami) wypada w s = 0, dziobnica na pokładzie w s = +14,0,
# tylnica na pokładzie w s = −14,0.
# Wrąb stępki jako linia bazowa: z_k(s) = ZK0 + ZK_SPADEK·s (rozdział 02: spód stępki −3,10 + 0,40·z/22,4, wrąb +0,25).
KADLUB = dict(
    ZK0=-2.885,           # m, wrąb stępki przy s = 0 (rozdział 02)
    ZK_SPADEK=0.40 / 22.4,  # przegłębienie 0,40 m na długości stępki (rozdział 02)
    STEPKA_WYS=0.31,      # m, stępka pod wrębem 0,25 + fałszywa stępka 0,06 (rozdziały 02 i 03)
    STEPKA_SZER=0.26,     # m, szerokość stępki i tylnicy (rozdział 03)
    DZIOBNICA_SZER=(0.26, 0.40),  # u dołu / u góry (rozdział 03)
    DZIOBNICA_GR=0.35,    # m, dziobnica przed wrębem (rozdział 03)
    TYLNICA_GR=(0.40, 0.28),  # m, tylnica za wrębem: przy pięcie / u góry (rozdział 03)
    POSZYCIE_GR=0.065,    # m, poszycie dna (rozdział 03); rzędne z notatek badawczych są po wręgach – dodane w projekt_rzednych.py
    # wrąb dziobnicy (s, z): ćwiartka elipsy od początku łuku (z_dok = 7,34) do pokładu (z_dok = 12,04) (rozdział 02),
    # nad pokładem prawie pionowo do głowicy dziobnicy
    DZIOB=[(9.300, -2.719), (10.116, -2.650), (10.907, -2.444), (11.650, -2.107), (12.321, -1.650),
           (12.900, -1.087), (13.370, -0.435), (13.717, 0.287), (13.929, 1.057), (14.000, 1.850), (14.030, 2.40),
           (14.080, 3.00), (14.120, 3.40)],
    # rufa: płaska pawęż (square tuck) w płaszczyźnie wrębu tylnicy, dolna krawędź tuż nad wodnicą, pawęż
    # skrzydłowa 1,25 m nad wodą, nad nią kontra (nawis) i pawęż z oknami (rozdziały 02 i 04)
    TUCK_S0=-13.10,       # m, wrąb tylnicy przy pięcie (z_dok −15,06)
    TUCK_RAKE=11.4,       # stopnie od pionu: 0,90 m na 4,47 m (rozdział 02: ok. 12°)
    Z_PAWEZ_DOLNA=1.25,   # wing transom (rozdział 04)
    # oś rufy nad pawężą skrzydłową (s, z): kontra 0,85 m (rozdział 04 podaje 0,6 – świadome odstępstwo:
    # oś steru biegnie prosto od pięty tylnicy w górę i na wysokości pokładu rufowego (3,08 m) leży 0,41 m przed
    # licem pawęży w osi; przy 0,6 m byłoby to 0,16 m, a otwór trzonu w pokładzie rufowym (promień 0,21 m) przeciąłby
    # pawęż – przy 0,85 m do wewnętrznej ściany pawęży zostaje ok. 6 cm), potem pawęż pochylona 8°
    RUFA=[(-13.98, 1.25), (-14.30, 1.42), (-14.58, 1.65), (-14.76, 1.85), (-14.83, 1.97), (-14.93, 2.60),
          (-15.06, 3.50), (-15.15, 4.15)],
    # przyjęte (źródła nie podają): zaokrąglenie lica pawęży w rzucie, 0,22 m na 5,1 m szerokości rufy –
    # dobrane wzrokowo, nie zmienia wymiarów głównych
    RUFA_WYGIECIE=0.22,   # m, środek pawęży za narożnikami
    Z_NAWIS=1.97,         # m, górna krawędź kontry = dolna krawędź pawęży z oknami
    # ster (rozdział 04: czopy i okucia, płetwa u dołu 0,8–1,0 m, głowica w kadłubie) – luzy przyjęte z geometrii
    # obrotu ±35°: lico tylnicy przed osią zawiasów, płetwa pod kontrą, trzon w otworze kontry (helm port)
    STER_LUZ_TYLNICA=0.07,   # m, lico tylnicy przed osią zawiasów (płetwa z taśmami czopów sięga 5,4 cm przy 35°)
    STER_LUZ_KONTRA=0.05,    # m, górna krawędź płetwy pod kontrą w najgorszym położeniu (35°)
    STER_OTWOR_LUZ=0.04,     # m, luz trzonu w otworze kontry i pokładu rufowego (promieniowo)
    # półszerokość końca rufowego (z → y): poniżej pierwszego punktu sama tylnica (dejwud); dolna krawędź
    # płaskiej pawęży (tuck) nad wodą: w osi 0,05 (granica farby dna), w narożnikach ok. 0,2, średnio 0,1 jak
    # w notatkach badawczych; pod tuckiem klepki dna zbiegają do tylnicy (square tuck, rozdział 04). Szerokość wyżej
    # z tabeli rzędnych po wręgach (rozdział 02; wręg −15,0: WL+0,5 2,49, pokład 2,54).
    RUFA_SZER=[(0.05, 0.13), (0.10, 1.20), (0.17, 1.80), (0.26, 2.10), (0.40, 2.28), (0.65, 2.40),
               (1.00, 2.50), (1.25, 2.54), (1.60, 2.55), (1.97, 2.52), (2.60, 2.40), (3.20, 2.28), (3.90, 2.12),
               (4.30, 2.03)],
    # pokład główny przy burcie (s → z): 0,90 + 0,95·u² ku dziobowi, 0,90 + 0,45·u² ku rufie (rozdział 02)
    POKLAD_BOK=[(-15.0, 1.38), (-14.0, 1.35), (-12.0, 1.24), (-10.0, 1.153), (-8.0, 1.075), (-6.0, 1.012),
                (-4.0, 0.963), (-2.0, 0.928), (0.0, 0.908), (1.96, 0.900), (4.0, 0.927), (6.0, 1.007),
                (8.0, 1.139), (10.0, 1.325), (12.0, 1.563), (13.0, 1.700), (14.0, 1.850), (14.6, 1.947)],
    WYPUKLOSC=0.12,       # m, wypukłość pokładu (rozdział 04) na półszerokości POL_B
    POL_B=3.80,
    POKLAD_GR=0.07,       # m, deski pokładu (rozdział 04)
    # nadburcie: wysokość relingu nad linią pokładu przy burcie (s → m): pokład rufowy 1,7 + 0,9 (rozdział 04),
    # uskok tuż przed progiem pokładu rufowego, w śródokręciu 1,05 (rozdział 04), lekko w górę ku dziobowi
    RELING=[(-15.6, 2.60), (-5.04, 2.60), (-4.25, 1.05), (9.0, 1.05), (14.6, 1.20)],
    POLPOKLAD_S=-5.04,    # m, próg pokładu rufowego (z_dok = −7,0 w układzie notatek badawczych)
    POLPOKLAD_H=1.70,     # m, pokład rufowy nad głównym (rozdział 04)
    NADBURCIE_GR=0.14,    # m, ścianka nadburcia: poszycie 0,05 + wierzchołki 0,12 – część wystająca (rozdziały 03 i 04)
    RELING_SZER=0.30,     # m, pokrywa relingu – przyjęte: nadburcie 0,14 (rozdział 04) + okap ok. 8 cm z obu stron
    RELING_GR=0.07,
    PILERS=(0.18, 0.11),  # m, wierzchołki wręgów od środka: szerokość × wystawanie (rozdział 04: 0,18 × 0,12)
    PILERS_ROZSTAW=0.52,  # m, odstęp wręgów (rozdział 03)
    WODOSCIEK=(0.25, 0.10),  # m, ściek przy burcie (rozdział 04)
    LINIA_WODNA_FARBA=0.05,  # m nad wodą, granica farby dna (rozdział 03: na wodnicy)
    # berghołty: pasy (od, do – odległości pod linią pokładu przy burcie, wystawanie): dwa grube po 0,26 i pas
    # 0,22 między nimi, górna krawędź na wysokości pokładu (rozdział 03)
    BERGHOLTY=[(0.0, 0.26, 0.06), (0.26, 0.48, 0.02), (0.48, 0.74, 0.06)],
    # pas furt (malowanie b): od / do nad linią pokładu
    LISTWA_FURT=(0.22, 0.92),
    # furty działowe (po każdej burcie): środki s; 7 par co 2,45 m od z_dok = 6,5 (rozdział 04); najbardziej
    # rufowa wypada pod pokładem rufowym (kabina) – tam tylko zamknięta pokrywa
    FURTY_S=[-3.79, -1.34, 1.11, 3.56, 6.01, 8.46],
    FURTY_ZAMKNIETE_S=[-6.24],
    # furty pod działa 4-funtowe (rozdział 04: 0,60 × 0,50, próg 0,32) przy lufie 2,0 m 6-funtówki (rozdział 09:
    # 4- albo 6-funtowe, 6-funtowa 1,8–2,1 m) – świadome: wymiary furt ze źródeł bez zmian, lufa 6-funtowa (wylot ok. 0,25 m)
    # mieści się w otworze 0,60 × 0,50 z zapasem na podniesienie lufy; lawety i odrzut liczone dla lufy 2,0 m
    FURTA_SZER=0.60, FURTA_PROG=0.32, FURTA_NADPROZE=0.82,
    POKRYWA_KAT=95.0,     # stopnie: pokrywy furt otwarte ponad lufę (0 = zamknięte; zakres ruchu 0–100)
)

# Tabela rzędnych z notatek badawczych (rozdział 02): po wręgach (bez poszycia), półszerokości od osi, y nad wodnicą.
# Wręgi z_dok; kolumny: spód stępki, wrąb, linia brodaty (dejwud do tej wysokości), półszerokości na wodnicach
# −2,5 … +0,5 co 0,5, pokład (y, ½B), największa szerokość (½B, y), nadburcie (y, ½B). None – brak.
LINIE_WREGI = [
    # z,     keel,  rabbet, beard, wl[-2.5 .. 0.5],                          deck, deckHB, b,   hb,   rail, top
    (-15.0, -3.37, -3.12, -1.31, (0.13, 0.13, 0.13, 0.22, 1.03, 2.04, 2.49), 1.30, 2.54, 2.56, 0.88, 2.35, 2.27),
    (-13.0, -3.33, -3.08, -1.94, (0.13, 0.13, 0.32, 1.15, 1.99, 2.66, 2.86), 1.20, 2.85, 2.87, 0.75, 2.25, 2.60),
    (-10.5, -3.29, -3.04, -2.46, (0.13, 0.35, 1.13, 1.92, 2.71, 3.10, 3.19), 1.09, 3.17, 3.20, 0.61, 2.14, 2.94),
    (-7.5, -3.23, -2.98, -2.79, (0.20, 0.95, 1.90, 2.86, 3.30, 3.44, 3.47), 1.00, 3.45, 3.48, 0.48, 2.05, 3.24),
    (-4.5, -3.18, -2.93, -2.89, (1.11, 2.35, 3.11, 3.38, 3.54, 3.63, 3.65), 0.94, 3.62, 3.65, 0.40, 1.99, 3.42),
    (-2.0, -3.14, -2.89, -2.88, (1.57, 2.87, 3.24, 3.47, 3.62, 3.70, 3.71), 0.91, 3.69, 3.72, 0.36, 1.96, 3.49),
    (0.0, -3.10, -2.85, -2.85, (1.78, 2.93, 3.27, 3.49, 3.64, 3.71, 3.73), 0.90, 3.70, 3.73, 0.35, 1.95, 3.51),
    (2.5, -3.06, -2.81, -2.80, (1.26, 2.73, 3.14, 3.38, 3.53, 3.61, 3.63), 0.94, 3.61, 3.63, 0.37, 1.99, 3.42),
    (5.0, -3.01, -2.76, -2.72, (0.68, 1.90, 2.74, 3.02, 3.20, 3.30, 3.33), 1.06, 3.30, 3.33, 0.43, 2.11, 3.14),
    (7.5, -2.97, -2.72, -2.72, (0.17, 0.90, 1.96, 2.35, 2.59, 2.73, 2.78), 1.27, 2.75, 2.78, 0.52, 2.32, 2.62),
    (9.5, None, -2.21, -2.21, (None, 0.17, 0.66, 1.28, 1.81, 2.00, 2.08), 1.49, 2.06, 2.08, 0.63, 2.54, 1.96),
    (11.0, None, -1.02, -1.02, (None, None, None, 0.13, 0.39, 0.86, 1.24), 1.69, 1.25, 1.27, 0.73, 2.74, 1.19),
]
LINIE_PRZESUNIECIE = 1.96   # s = z_dok + 1,96

# Tabela rzędnych (półszerokości po zewnętrznej stronie poszycia, m). Wiersze: wysokość h nad wrębem stępki
# (linie równoległe do stępki), kolumny: wręgi teoretyczne s (m). None – punkt poza kadłubem (za dziobnicą,
# za płaszczyzną pawęży albo powyżej). Liczby wyprowadzone z tabeli po wręgach (LINIE_WREGI wyżej) przez
# projekt_rzednych.py: przeliczenie wodnic na linie równoległe do stępki, dodanie poszycia (POSZYCIE_GR),
# zaokrąglenie do cm. Blok przepisuje skrypt – zmiany kształtu wprowadzać w LINIE_WREGI.
# >>> RZEDNE (blok przepisywany przez projekt_rzednych.py)
RZEDNE_H = [0.0, 0.03, 0.08, 0.15, 0.25, 0.38, 0.55, 0.75, 1.0, 1.3, 1.65, 2.05, 2.5, 2.8, 3.0, 3.15, 3.3, 3.45, 3.6, 3.8, 4.05, 4.35, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5]
RZEDNE_S = [-13.04, -11.04, -8.54, -5.54, -2.54, -0.04, 1.96, 4.46, 6.96, 9.46, 11.46, 12.96]
RZEDNE = [
    [0.130, None, 0.130, None, None, 0.149, 0.130, 0.150, None, None, None, None],  # h = 0.00
    [0.130, 0.130, 0.130, 0.130, 0.201, 0.280, 0.308, 0.275, 0.199, 0.132, None, None],  # h = 0.03
    [0.130, 0.130, 0.130, 0.130, 0.322, 0.494, 0.597, 0.480, 0.316, 0.141, None, None],  # h = 0.08
    [0.130, 0.130, 0.130, 0.130, 0.491, 0.783, 0.980, 0.758, 0.481, 0.162, None, None],  # h = 0.15
    [0.130, 0.130, 0.130, 0.135, 0.734, 1.170, 1.464, 1.133, 0.719, 0.206, None, None],  # h = 0.25
    [0.130, 0.130, 0.130, 0.178, 1.052, 1.617, 1.940, 1.583, 1.043, 0.349, None, None],  # h = 0.38
    [0.130, 0.130, 0.130, 0.281, 1.483, 2.154, 2.430, 2.173, 1.480, 0.647, 0.142, None],  # h = 0.55
    [0.130, 0.130, 0.185, 0.578, 2.011, 2.701, 2.859, 2.707, 1.943, 1.029, 0.227, None],  # h = 0.75
    [0.130, 0.130, 0.382, 1.043, 2.546, 3.051, 3.129, 2.998, 2.437, 1.618, 0.497, None],  # h = 1.00
    [0.130, 0.174, 0.784, 1.607, 3.038, 3.257, 3.309, 3.202, 2.837, 2.114, 0.869, None],  # h = 1.30
    [0.130, 0.457, 1.372, 2.309, 3.319, 3.439, 3.478, 3.383, 3.037, 2.375, 1.310, 0.138],  # h = 1.65
    [0.217, 1.160, 2.005, 3.003, 3.491, 3.592, 3.624, 3.528, 3.200, 2.589, 1.775, 0.379],  # h = 2.05
    [0.865, 1.928, 2.733, 3.372, 3.621, 3.708, 3.732, 3.633, 3.322, 2.748, 2.015, 0.782],  # h = 2.50
    [1.482, 2.396, 3.027, 3.471, 3.680, 3.757, 3.771, 3.675, 3.369, 2.807, 2.092, 1.059],  # h = 2.80
    [1.916, 2.658, 3.152, 3.507, 3.700, 3.774, 3.787, 3.689, 3.387, 2.833, 2.131, 1.232],  # h = 3.00
    [2.145, 2.766, 3.194, 3.525, 3.710, 3.783, 3.794, 3.695, 3.395, 2.844, 2.145, 1.304],  # h = 3.15
    [2.320, 2.845, 3.223, 3.539, 3.715, 3.782, 3.795, 3.695, 3.395, 2.844, 2.145, 1.330],  # h = 3.30
    [2.462, 2.902, 3.245, 3.545, 3.715, 3.772, 3.792, 3.692, 3.390, 2.841, 2.144, 1.335],  # h = 3.45
    [2.549, 2.926, 3.262, 3.542, 3.709, 3.765, 3.780, 3.684, 3.381, 2.836, 2.142, 1.334],  # h = 3.60
    [2.602, 2.935, 3.261, 3.530, 3.692, 3.755, 3.759, 3.671, 3.367, 2.826, 2.137, 1.330],  # h = 3.80
    [2.625, 2.929, 3.242, 3.508, 3.661, 3.721, 3.719, 3.633, 3.339, 2.811, 2.129, 1.324],  # h = 4.05
    [2.610, 2.909, 3.201, 3.454, 3.599, 3.655, 3.656, 3.569, 3.287, 2.777, 2.114, 1.315],  # h = 4.35
    [2.555, 2.833, 3.114, 3.370, 3.521, 3.578, 3.589, 3.498, 3.227, 2.725, 2.078, 1.297],  # h = 4.70
    [2.431, 2.716, 3.018, 3.297, 3.465, 3.527, 3.545, 3.454, 3.185, 2.680, 2.034, 1.270],  # h = 5.10
    [2.314, 2.629, 2.955, 3.247, 3.420, 3.483, 3.503, 3.412, 3.149, 2.649, 2.005, 1.248],  # h = 5.60
    [2.241, 2.562, 2.893, 3.188, 3.363, 3.426, 3.448, 3.358, 3.104, 2.613, 1.978, 1.232],  # h = 6.20
    [2.164, 2.490, 2.827, 3.128, 3.306, 3.369, 3.394, 3.304, 3.058, 2.576, 1.950, 1.215],  # h = 6.80
    [2.074, 2.407, 2.751, 3.065, 3.256, 3.326, 3.358, 3.268, 3.022, 2.536, 1.916, 1.195],  # h = 7.50
]
# <<< RZEDNE

# ------------------------------------------------------------------ drzewca
# Źródło: rozdział 05 przewodnika (reguły Steela, tabela drzewc, położenie i pochylenie masztów). Długości liczone
# tu z reguł dla naszego kadłuba (pokład 28 m, szerokość z poszyciem 7,6 m) – notatki badawcze podają liczby dla
# szerokości 8,5 m (grotmaszt 18,25 m); różnica ok. 2 %.
CAL_NA_JARD = 0.0254 / 0.9144     # 1 cal na jard długości = 1/36 długości


def _drzewca(L=28.0, B=7.6):
    M = (L + B) / 2                                     # grotmaszt od pięty (rozdział 05, reguła A)
    d = dict(
        GROT=M, FOK=M * 8 / 9,
        GROT_STENGA=M * 3 / 5, FOK_STENGA=M * 3 / 5 * 8 / 9,
        GROT_BRAM=M * 3 / 5 / 2, FOK_BRAM=M * 3 / 5 * 8 / 9 / 2,
        BUKSZPRYT=M * 3 / 5, BOMSTENGA=M * 3 / 5 * 5 / 7,
        GROTREJA=M * 8 / 9, FOKREJA=M * 8 / 9 * 7 / 8,
        GROTMARSREJA=M * 8 / 9 * 5 / 7, FOKMARSREJA=M * 8 / 9 * 5 / 7 * 7 / 8,
        GROTBRAMREJA=M * 8 / 9 * 5 / 7 * 3 / 5, FOKBRAMREJA=M * 8 / 9 * 5 / 7 * 7 / 8 * 3 / 5,
        BLINDAREJA=M * 8 / 9 * 5 / 7 * 7 / 8,
        BOM=11.9, GAFEL=7.4,                            # rozdział 05: 11,6–12,2 / 7,3–7,6
    )
    j = lambda x: x / 0.9144                            # metry → jardy
    d.update(
        GROT_SR=j(M) * 0.0254, FOK_SR=j(M) * 0.0254 * 0.9,
        GROT_STENGA_SR=j(d["GROT_STENGA"]) * 0.0254, FOK_STENGA_SR=j(d["FOK_STENGA"]) * 0.0254,
        GROT_BRAM_SR=j(d["GROT_BRAM"]) * 0.0254, FOK_BRAM_SR=j(d["FOK_BRAM"]) * 0.0254,
        BUKSZPRYT_SR=j(M) * 0.0254, BOMSTENGA_SR=j(d["BOMSTENGA"]) * 0.0254 * 7 / 8,
        GROTREJA_SR=j(d["GROTREJA"]) * 0.0254 * 0.7, FOKREJA_SR=j(d["FOKREJA"]) * 0.0254 * 0.7,
        GROTMARSREJA_SR=j(d["GROTMARSREJA"]) * 0.0254 * 0.625, FOKMARSREJA_SR=j(d["FOKMARSREJA"]) * 0.0254 * 0.625,
        GROTBRAMREJA_SR=j(d["GROTBRAMREJA"]) * 0.0254 * 0.6, FOKBRAMREJA_SR=j(d["FOKBRAMREJA"]) * 0.0254 * 0.6,
        BLINDAREJA_SR=j(d["BLINDAREJA"]) * 0.0254 * 0.625,
        BOM_SR=0.176, GAFEL_SR=0.176,
        GROT_TOP=j(M) * 5 * 0.0254, FOK_TOP=j(M * 8 / 9) * 5 * 0.0254,               # top kolumny: 5 cali/jard
        GROT_STENGA_TOP=j(d["GROT_STENGA"]) * 4 * 0.0254, FOK_STENGA_TOP=j(d["FOK_STENGA"]) * 4 * 0.0254,
    )
    return d


DRZEWCA = dict(
    **_drzewca(),
    # położenie na pokładzie (s): fok 0,14 L za dziobnicą, grot 0,55 L (rozdział 05 podaje 0,55 i regułę 2/3 – przy
    # 2/3 grot stałby na progu pokładu rufowego i nie zmieściłyby się schody)
    FOK_S=14.0 - 0.14 * 28.0, GROT_S=14.0 - 0.55 * 28.0,
    GROT_POCHYL=1.2, FOK_POCHYL=0.2,      # stopnie w tył (rozdział 05)
    KILSON_NAD_WREBEM=0.50,               # pięta masztu na nadstępce (m nad wrębem) – przyjęte: dennik nad wrębem
                                          # ok. 0,22 + nadstępka 0,28 (rozdział 03)
    TAPER_MASZT=[1, 60 / 61, 14 / 15, 6 / 7, 3 / 4, 5 / 8],
    TAPER_STENGA=[1, 60 / 61, 14 / 15, 6 / 7, 13 / 16, 6 / 11],
    TAPER_REJA=[1, 30 / 31, 7 / 8, 7 / 10, 3 / 7],
    MARS_SZER_STENGI=1 / 3, MARS_DL_SZER=3 / 4,
    # stopnie: rozdział 05 podaje 30°; 36° to reguła Steela z 1794 r. – dla 1710 świadomie 30°
    BUKSZPRYT_WZNIOS=30.0,
    BUKSZPRYT_NAD_DZIOBNICA=0.20,         # m nad głowicą dziobnicy (spód drzewca)
    SNOW_MASZT_SR=0.35,                   # × średnica grotmasztu (rozdział 01)
    SNOW_ODSTEP=0.45,                     # m za osią grotmasztu – przyjęte: „tuż za grotmasztem” (rozdział 01):
                                          # promień grotmasztu 0,25 + masztu snow 0,09 + luz na szczęki gafla
    REJA_POD_MARSEM=0.75,                 # dolna reja 0,5–1 m pod belkami marsa (rozdział 05)
    # reje w pozycji roboczej (żagiel postawiony; rozdziały 05 i 08): marsreja podniesiona pod salingi stengi,
    # bramreja pod top bramstengi – odstępy przyjęte tak, by reja nie wchodziła w okucia i bloki topenant
    MARSREJA_POD_SALINGIEM=0.90, BRAMREJA_POD_TOPEM=1.40,
    # rozdział 01 (snow: żagiel gaflowy pierwotnie bez bomu) i rozdział 08 (1700–1720: zrzucany gejtawami do masztu):
    # domyślnie bez bomu; True – wariant późniejszy z bomem, szotem bomu i dirkami (ruchome.py, zagle.py)
    Z_BOMEM=False,
    BOM_NAD_POKLADEM=3.95,                # m nad pokładem głównym przy maszcie (≥ 2 m nad pokładem rufowym)
    GAFEL_KAT=38.0,                       # stopnie nad poziomem – przyjęte (źródła nie podają kąta gafla)
)

# ------------------------------------------------------------------ olinowanie stałe (rozdział 06)
OLINOWANIE = dict(
    WANTY={"grot": 6, "fok": 5}, WANTY_STENGOWE=3, WANTY_BRAMSTENGOWE=2, PADUNY_STENGOWE=2, PADUNY_BRAM=1,
    D_GROTSZTAG=0.080, D_FOKSZTAG=0.073, D_WANTY_GROT=0.049, D_WANTY_FOK=0.045, D_TALREP=0.024,
    D_WYBLINKA=0.010, D_PODWANTKA=0.028, D_WANTY_STENG=0.028, D_TALREP_STENG=0.014, D_PADUN_STENG=0.036,
    D_SZTAG_STENG=0.040, D_WANTY_BRAM=0.016, D_PADUN_BRAM=0.020, D_SZTAG_BRAM=0.020, D_WATERSZTAG=0.057,
    D_WANTY_BUKSZ=0.040, D_WIAZANIE=0.032, D_SZTAG_KLIWRA=0.032, D_PERTA=0.024, D_STRZEMIE=0.020,
    WYBLINKI_ROZSTAW=0.36, WYBLINKI_ZWIS=0.015, JUFERS_Z_OBWODU=1.5, JUFERS_ODSTEP=2.7,
    PERTA_ZWIS=0.9, STRZEMIONA=4, STRZEMIONA_MARS=3, WIAZANIE_ZWOJE=9, WATERSZTAGI=2, WANTY_BUKSZPRYTU=2,
    LAWA_SZER=0.45, LAWA_GR=0.09,          # rozdział 06: 0,40–0,50 × 0,08–0,10
    JUFERSY_ROZSTAW=0.40,                  # m między osiami jufersów na ławie – przyjęte (rozdział 06 podaje tylko
                                           # odstęp górny–dolny); średnica jufersa + luz między talrepami
    D_MIN_GLB=0.014,                       # dolna granica średnicy liny w GLB (przyjęte)
)

# ------------------------------------------------------------------ wyposażenie i układ pokładu
# Źródło: rozdział 09 przewodnika – gabaryty i położenie względem masztów; miejsca dobrane
# tak, żeby przeszedł test chodzenia (kontrola.py): przejścia ≥ 0,8 m, koło drągów kabestanu wolne od masztu
# i luków, działa po odrzucie nie zamykają jedynego przejścia. s – wzdłuż (+ dziób), x – w poprzek (+ lewa burta).
UKLAD = dict(
    # kabestan 2,35 m przed grotmasztem (świadome odstępstwo od rozdziału 09 – za masztem): za grotmasztem koło drągów
    # zamykało przejście od schodów pokładu rufowego ku burtom (test chodzenia)
    KABESTAN=dict(s=0.95, r_glowica=0.47, r_beben=0.31, h=1.22, dragi=8, r_draga=1.75, h_draga=1.10),
    # rozdział 09: drągi 2,8–3,2 m (koło 6,5 m) to szacunek; przy pokładzie 7,6 m i grotmaszcie 2,5 m dalej koło 3,5 m
    POMPY=dict(s=-4.35, x=1.05, r=0.175, h=1.0, dzwignia=1.5, wahanie=25.0),    # rozdział 09: 1 m za G – tu obok schodów
    # (przy grotmaszcie zamykały przejście od schodów ku burtom); ±25° (rozdział 09)
    LUK_GLOWNY=dict(s0=2.9, s1=5.3, pol_x=0.9, h=0.25),                        # rozdział 09: 2,4 × 1,8 × 0,25
    LUK_DZIOBOWY=dict(s0=8.05, s1=9.05, pol_x=0.6, h=0.25),                    # mniejszy niż w rozdziale 09 (miejsce)
    LODZ=dict(stan="za_rufa", s0=2.7, s1=7.7, szer=1.72, glebokosc=0.72),   # stan: za_rufa | na_pokladzie | brak (przyjęte)
    # rozdział 09: szalupa 7,0 × 2,0 – tu jol 5,0 × 1,7 na legarach (booms) 2,25 m nad pokładem nad lukiem głównym: pod spodem
    # da się przejść i pracować przy luku, a działa mają miejsce na odrzut; słupki legarów między działami
    KOMIN=dict(s=7.35, x=0.0, a=0.35, h=0.8),        # w osi: przy burcie blokował odrzut działa P5
    NAGIELBANK=dict(pol=0.60, h=0.9, kolki_co=0.2),                             # rozdział 09: 1,4 × 1,4 – tu 1,2 × 1,2 (przejścia)
    # kołkownice w nadburciu (odcinki s przy burtach, między działami, nie za lufą) – rekonstrukcja: rozdział 07 kładzie
    # liny na kołki przy wantach i nagielbankach; przy niskim nadburciu brygu kołki w listwie na wierzchołkach wręgów
    KOLKOWNICE=[(-3.30, -1.92), (6.60, 7.40), (9.05, 10.30)],
    KOLKOWNICA_H=0.82,
    SZAFKA_KOMPASOWA=dict(s=-10.35, szer=0.9, gl=0.45, h=0.85),                # rozdział 09; tuż przed kołem sterowym
    # Sterowanie: dwa warianty w jednym modelu (grupy węzłów naped_kolo / naped_rumpel, extras.wariant).
    # Koło sterowe pojawia się ok. 1703–1710 (rozdział 09); model RMG z ok. 1720 ma koło, model z ok. 1740
    # – rumpel na pokładzie. Domyślny wariant (widoczny w .blend i oznaczony w GLB): koło (przyjęte);
    # rumpel na pokładzie zostaje jako druga grupa.
    STEROWANIE=dict(naped="kolo"),                                                # kolo | rumpel
    RUMPEL=dict(dl=3.5, przekr=0.18, kat=35.0, h_glowicy=0.45, h_konca=0.90),   # rozdział 09; wariant naped_rumpel
    # Wariant naped_kolo (rozdział 09; wymiary przyjęte): koło Ø 1,40 m, 10 szprych z rękojeściami, oś 1,05 m nad pokładem
    # rufowym, bęben Ø 0,30 m z 6 zwojami sterliny między dwoma stojakami, rumpel 3,0 m w kabinie pod pokładem rufowym
    # (0,40 m pod pokładem), sterlina przez dwa przepusty z krążkami w pokładzie, krążki przy burtach, koniec rumpla.
    KOLO=dict(s=-11.55, D=1.40, szprychy=10, os_h=1.05, D_beben=0.30, L_beben=0.50, zwoje=6, d_sterliny=0.026,
              rumpel_dl=3.0, rumpel_pod=0.40, kat=35.0),
    # dzwon na przedniej krawędzi pokładu rufowego – świadome odstępstwo od źródeł (dzwon na baku, rozdział 09): model nie ma baku,
    # dzwon stoi przy progu pokładu rufowego, skąd słychać go na całym pokładzie głównym
    DZWON=dict(s=-5.45, x=1.55, r=0.14),
    ZEJSCIOWKA=dict(s0=-7.35, s1=-6.35, pol_x=0.45, h=1.0),
    KOJCE=[dict(s=-8.1, x=2.62)],                                                # po jednym na burtę (lustro)
    SKRZYNIA_BRONI=dict(s=-6.0, x=2.35),
    BECZKA_WODY=dict(s=-4.45, x=-2.95, r=0.33, h=0.9),
    DZIALA=dict(furty="FURTY_S", lufa=2.0, lawa_dl=1.5, lawa_szer=0.8, os_lufy=0.60, odrzut=1.5, bez_dziala=[-3.79],
                z_linami=[1.11, -1.34], wariant="wlasne"),                       # rozdział 09; "polyhaven" – wariant CC0
    DZIALKA_RELINGOWE=[-6.6, -9.4, -12.2, 11.6],                                  # s na relingach (obie burty)
)

# ------------------------------------------------------------------ malowanie
# Regiony kadłuba: dno (pod wodnicą), burta (od wodnicy do berghołtów), bergholt, burta_gorna (nad berghołtami
# do relingu), pas_furt (pas furt od zewnątrz), reling (pokrywa i listwy), wnetrze (nadburcie od środka, grodzie,
# podszycie furt), pawez (lico pawęży nad kontrą), rzezby (snycerka), pokrywa_zew / pokrywa_wew (pokrywy furt)
SCHEMATY = {
    # (a) epoka (rozdział 03, propozycja na podstawie źródeł): dno białawe („white stuff”), od wodnicy do berghołtów
    # drewno olejowane, berghołty czarne, nad nimi pas ochry (rozkaz Admiralicji 1715: żółty i czarny), reling
    # i listwy czarne, rzeźby żółte; wnętrze nadburcia: drewno olejowane (czerwień od środka niepotwierdzona –
    # wariant parametrem WNETRZE_CZERWONE)
    "a": dict(dno="farba_dno_biala", burta="burta_drewno", bergholt="farba_czarna", burta_gorna="farba_ochra",
              pas_furt="farba_ochra", listwa="farba_czarna_gladka", reling="farba_czarna_gladka", wnetrze="burta_drewno",
              pawez="farba_czarna", rzezby="rzezby_zlote", pokrywa_zew="farba_ochra", pokrywa_wew="burta_drewno"),
    # (b) wariant późniejszy: czarny kadłub, ochrowy pas furt, ciemne dno (smołowe, czerwonobrązowe),
    # czerwone wnętrze
    "b": dict(dno="farba_dno_czerwona", burta="farba_czarna", bergholt="farba_czarna", burta_gorna="farba_czarna",
              pas_furt="farba_ochra", listwa="farba_czarna", reling="farba_czarna", wnetrze="farba_czerwona",
              pawez="farba_czarna", rzezby="rzezby_zlote", pokrywa_zew="farba_czarna", pokrywa_wew="farba_czerwona"),
}
WNETRZE_CZERWONE = False   # schemat (a): nadburcie od środka czerwoną ochrą (wariant)
if WNETRZE_CZERWONE:
    SCHEMATY["a"]["wnetrze"] = "farba_czerwona"
    SCHEMATY["a"]["pokrywa_wew"] = "farba_czerwona"

# Materiały: tekstura (zestaw z tekstury.py), mnożnik koloru (sRGB 0..1), kafel w metrach (u, v)
MATERIALY = {
    "burta_drewno": dict(tex="burta", kolor=(0.80, 0.66, 0.52), kafel=(8.0, 8.0)),      # dąb olejowany, ciepły brąz (A2)
    "farba_czarna": dict(tex="farba", nrm="burta", kolor=(0.055, 0.05, 0.047), kafel=(8.0, 8.0), szorstkosc=0.72),
    "farba_ochra": dict(tex="farba", nrm="burta", kolor=(0.33, 0.16, 0.035), kafel=(8.0, 8.0)),
    "farba_czarna_gladka": dict(tex="farba", nrm="burta", kolor=(0.055, 0.05, 0.047), kafel=(2.0, 2.0)),   # reling, listwy  # ochra (mnożnik liniowy; sRGB ≈ 0,61 0,44 0,20)
    "farba_czerwona": dict(tex="farba", nrm="burta", kolor=(0.55, 0.13, 0.08), kafel=(8.0, 8.0)),
    "farba_niebieska": dict(tex="farba", nrm="burta", kolor=(0.13, 0.20, 0.33), kafel=(8.0, 8.0)),
    "farba_dno_biala": dict(tex="farba", nrm="burta", kolor=(0.80, 0.78, 0.70), kafel=(8.0, 8.0)),
    "farba_dno_czerwona": dict(tex="farba", nrm="burta", kolor=(0.36, 0.13, 0.09), kafel=(8.0, 8.0)),
    "poklad": dict(tex="poklad", kolor=(0.93, 0.88, 0.80), kafel=(6.4, 6.4)),            # szaro-beżowy, szorowany (A2)
    "drewno": dict(tex="drewno", kolor=(1, 1, 1), kafel=(2.0, 2.0)),
    "drewno_ciemne": dict(tex="drewno", kolor=(0.42, 0.36, 0.31), kafel=(2.0, 2.0)),
    "drewno_czarne": dict(tex="drewno", kolor=(0.12, 0.11, 0.10), kafel=(2.0, 2.0)),
    "laweta": dict(tex="drewno", kolor=(0.30, 0.085, 0.045), kafel=(2.0, 2.0)),   # czerwona ochra, przybrudzona
    "rzezby_zlote": dict(tex="farba", nrm="drewno", kolor=(0.86, 0.64, 0.24), kafel=(2.0, 2.0)),   # snycerka malowana na żółto
    "zelazo": dict(tex="zelazo", kolor=(1, 1, 1), kafel=(1.0, 1.0)),
    "zelazo_lufa": dict(tex="zelazo", kolor=(1, 1, 1), kafel=(1.0, 1.0)),
    "braz": dict(tex="farba", nrm="zelazo", rm="zelazo", kolor=(0.70, 0.50, 0.24), kafel=(1.0, 1.0)),
    "lina_smolowana": dict(tex="lina", kolor=(0.26, 0.21, 0.16), kafel=(1.0, 1.0)),
    "lina_jasna": dict(tex="lina", kolor=(0.86, 0.78, 0.62), kafel=(1.0, 1.0)),
    "plotno": dict(tex="plotno", kolor=(1, 1, 1), kafel=(2.4, 2.4)),
    "szklo": dict(tex="okno", kolor=(1, 1, 1), kafel=(1.0, 1.0)),
}

# ------------------------------------------------------------------ zestaw fotograficzny CC0 (opcja --tekstury-cc0)
# Źródło tekstur: Poly Haven (CC0), katalog z pobranymi plikami podawany argumentem (spis: tekstury_cc0_spis.json);
# tekstury_cc0.py robi z nich kopie robocze w <out>/tekstury_cc0 (obrót słojów wzdłuż u, odbarwienie farb i płótna,
# ARM bez metalu).
# Przypisanie i mnożniki koloru – przyjęte (porównanie z zestawem proceduralnym: rendery porownanie_*). Szerokość deski
# poszycia i pokładu 0,22–0,24 m (założenie: 20–28 cm; rozdział 03: deski 9–10" ≈ 0,23–0,25 m). Żelazo i liny – proceduralne.
# Wybór po porównaniu (rendery porownanie_*): deski pokładu, poszycia i farb oraz płótno – CC0 (prawdziwe słoje,
# zużycie i splot, spoiny desek z obrazu); drewno drzewc i wyposażenia – proceduralne (fornir oak_veneer_01 wygląda
# jak mebel: zbyt drobne, równe słoje). wybor=False – materiał zostaje proceduralny także przy --tekstury-cc0.
MATERIALY_CC0 = {
    "poklad": dict(id="wood_planks_grey", deski=True, szer_deski=0.24, kolor=(1.0, 0.90, 0.76)),   # szorowany, szary beż
    "burta_drewno": dict(id="brown_planks_09", deski=True, szer_deski=0.22, kolor=(0.95, 0.74, 0.52)),  # dąb olejowany, ciepły brąz
    "farba_czarna": dict(id="black_painted_planks", deski=True, szer_deski=0.22),
    "farba_ochra": dict(id="white_planks_clean", deski=True, szer_deski=0.22, szarosc=True, kontrast=0.8),
    "farba_czerwona": dict(id="white_planks_clean", deski=True, szer_deski=0.22, szarosc=True, kontrast=0.8),
    "farba_niebieska": dict(id="white_planks_clean", deski=True, szer_deski=0.22, szarosc=True, kontrast=0.8),
    "farba_dno_biala": dict(id="white_planks_clean", deski=True, szer_deski=0.22, szarosc=True, kontrast=0.8),
    "farba_dno_czerwona": dict(id="white_planks_clean", deski=True, szer_deski=0.22, szarosc=True, kontrast=0.8),
    "drewno": dict(id="oak_veneer_01", sloje=True, kolor=(0.92, 0.84, 0.74), wybor=False),
    "drewno_ciemne": dict(id="oak_veneer_01", sloje=True, wybor=False),   # mnożnik z MATERIALY (ciemniejszy)
    "drewno_czarne": dict(id="oak_veneer_01", sloje=True, wybor=False),
    "laweta": dict(id="oak_veneer_01", sloje=True, wybor=False),
    "plotno": dict(id="rough_linen", szarosc=True, kontrast=0.6, kolor_plotna=(0.86, 0.82, 0.72)),
}

# ------------------------------------------------------------------ deski z układu pasów (deski.py, tekstury_deski.py)
# Poszycie (rozdział 03): pasy 0,25–0,30 m → 0,275; styki na wręgach (odstęp 0,55 m), klepka 13 wręgów = 7,15 m, kolejny pas
# przesunięty o 4 wręgi (2,2 m ≥ 1,8 m), ten sam układ co 13 pasów; szew 7 mm (rozdział 03: 6–10 mm). Atlas 4 rzędy × 4,4 m
# (8 wręgów) → kafel (4,4; 1,1) m, 4096 × 1024 px = 931 px/m. Pokład (rozdział 04): deski 0,22 m, pokładniki co 1,173 m,
# deska 7 pokładników = 8,2 m, przesunięcie 2 pokładniki na deskę (ten sam pokładnik co 7 desek), szew 8 mm; atlas
# 4 rzędy × 3,52 m (3 pokładniki) → kafel (3,52; 0,88) m = 1164 px/m.
DESKI = dict(
    burta=dict(szer=0.275, krok=0.55, dl=13, przes=4, okres=13, rzedy=4, L_tex=4.4, szew=0.007, odcien=(0.06, 0.03)),
    poklad=dict(szer=0.22, krok=1.1733, dl=7, przes=2, okres=7, rzedy=4, L_tex=3.52, szew=0.008, odcien=(0.07, 0.035)),
)
# Źródła i kolory tekstur td_* (tekstury_deski.py); kolory – średnie albedo sRGB po wyrównaniu zdjęcia
TEKSTURY_TD = dict(
    burta=dict(zrodlo="wood_planks_grey", kolor=(0.46, 0.33, 0.22)),          # dąb olejowany, ciepły brąz
    poklad=dict(zrodlo="wood_planks_grey", kolor=(0.62, 0.575, 0.50)),         # wyszorowane deski, szary beż
    farby=dict(czarna=dict(kolor=(0.075, 0.07, 0.065), chrop=0.42, przetarcie=0.7),   # smoła z sadzą, lekki połysk
               ochra=dict(kolor=(0.68, 0.52, 0.27), chrop=0.6),
               biala=dict(kolor=(0.84, 0.81, 0.73), chrop=0.62, przetarcie=0.6),     # white stuff (łój, siarka, biel)
               czerwona=dict(kolor=(0.55, 0.17, 0.10), chrop=0.58),
               niebieska=dict(kolor=(0.16, 0.23, 0.36), chrop=0.55),
               dno_czerwona=dict(kolor=(0.42, 0.18, 0.12), chrop=0.6)),
    # elementy: kafel 2 m z wnętrz desek zdjęcia (pasy 0,2–0,25 m, miękkie przejścia) – prawdziwe słoje bez szwów
    drewno=dict(zrodlo="brown_planks_03", kafel=2.0, pas=0.2, min_szer=0.06, kolor=(0.44, 0.33, 0.23)),  # dąb olejowany
    sosna=dict(zrodlo="wood_planks_grey", kafel=2.0, pas=0.25, min_szer=0.12, kolor=(0.62, 0.48, 0.32)),  # sosna drzewc
    laweta=dict(kolor=(0.40, 0.15, 0.09)),                                      # czerwona ochra, przybrudzona
    zelazo=dict(zrodlo="rusty_metal_04", kafel=1.0, kolor=(0.085, 0.083, 0.08), rdza=(0.30, 0.17, 0.09), metal=0.55,
                N=1024),
    plotno=dict(zrodlo="rough_linen", kafel=0.54, kolor=(0.84, 0.80, 0.70)),
)
# Materiały z td_* (z --tekstury-cc0): pliki, kafel (m), mnożnik koloru (sRGB), chropowatość×, metaliczność (None – 0, bez
# kanału; liczba – z kanału B tekstury × liczba). Zastępują MATERIALY / MATERIALY_CC0.
_KB, _KP = (DESKI["burta"]["L_tex"], DESKI["burta"]["rzedy"] * DESKI["burta"]["szer"]), \
    (DESKI["poklad"]["L_tex"], DESKI["poklad"]["rzedy"] * DESKI["poklad"]["szer"])
MATERIALY_TD = {
    "burta_drewno": dict(td="td_burta", kafel=_KB),
    "farba_czarna": dict(td="td_farba_czarna", nrm="td_farba_ochra", kafel=_KB),
    "farba_ochra": dict(td="td_farba_ochra", kafel=_KB, kolor=(0.86, 0.88, 1.0)),   # o ton mniej jaskrawa
    "farba_czerwona": dict(td="td_farba_czerwona", nrm="td_farba_ochra", kafel=_KB),
    "farba_niebieska": dict(td="td_farba_niebieska", nrm="td_farba_ochra", kafel=_KB),
    "farba_dno_biala": dict(td="td_farba_biala", nrm="td_farba_ochra", kafel=_KB),
    "farba_dno_czerwona": dict(td="td_farba_dno_czerwona", nrm="td_farba_ochra", kafel=_KB),
    "poklad": dict(td="td_poklad", kafel=_KP),
    "drewno": dict(td="td_sosna", kafel=(2.0, 2.0)),                     # drzewca i jasne drewno
    "drewno_ciemne": dict(td="td_drewno", kafel=(2.0, 2.0), kolor=(0.90, 0.87, 0.84)),   # dąb wyposażenia
    "drewno_czarne": dict(td="td_drewno", kafel=(2.0, 2.0), kolor=(0.34, 0.32, 0.30)),   # smołowane (topy, czapy)
    "laweta": dict(td="td_laweta", kafel=(2.0, 2.0)),
    "rzezby_zlote": dict(td="td_farba_gladka", kafel=(1.0, 1.0), kolor=(0.82, 0.63, 0.30)),   # ochra żółta na snycerce
    # reling, listwy (jedna belka): smolista czerń – mnożnik sRGB 0,225 × obraz 0,88 → albedo sRGB ≈ 0,19 / 0,18 / 0,175
    # (wcześniej 0,13 → albedo ≈ 0,11, baseColorFactor liniowo 0,015 – test praktyk: prawie czysta czerń)
    "farba_czarna_gladka": dict(td="td_farba_gladka", orm="td_farba_gladka_mat", kafel=(1.0, 1.0), kolor=(0.225, 0.215, 0.205)),
    "zelazo": dict(td="td_zelazo", kafel=(1.0, 1.0), metal=1.0),
    "zelazo_lufa": dict(td="td_zelazo", orm="td_zelazo_lufa", kafel=(1.0, 1.0), metal=1.0),   # lufy: lekki połysk
    "braz": dict(td="td_farba_gladka", orm="td_braz", kafel=(1.0, 1.0), kolor=(0.62, 0.42, 0.20), metal=1.0),
    "plotno": dict(td="td_plotno", kafel=(0.54, 0.54)),
}

# cel gęstości tekseli z 1 m (5. percentyl, px/m): poniżej tekstura w GLB nie jest zmniejszana (eksport.py)
GESTOSC_CEL = {"poklad": 800, "burta_drewno": 800, "farba_czarna": 800, "farba_ochra": 800, "farba_dno_biala": 450,
               "farba_czerwona": 800, "drewno": 1000, "drewno_ciemne": 1000, "drewno_czarne": 800, "laweta": 1000,
               "zelazo": 800, "zelazo_lufa": 800, "rzezby_zlote": 800, "plotno": 400, "*": 500}

# ------------------------------------------------------------------ zestaw
BRYG = dict(nazwa="bryg", kadlub=KADLUB, schemat="a", snow=True, zagle_postawione=False)   # rozdział 01: snow
STATKI = {"BRYG": BRYG}


def zapisz_json(sciezka, statek="BRYG"):
    """Wszystkie grupy parametrów jako jeden plik JSON (dla CAD, arkusza, rysunku): kadłub, tabela rzędnych po wręgach
    i tabela generatora, drzewca, olinowanie, układ wyposażenia, malowanie, materiały."""
    import json
    st = STATKI[statek]
    dane = dict(uklad_wspolrzednych=(
        "Układ statku (s, x, z), metry, prawoskrętny: s – wzdłuż, + ku dziobowi, s = 0 w środku długości pokładu "
        "między wrębami (dziobnica na pokładzie s = +14,0, tylnica s = −14,0); x – w poprzek, + ku lewej burcie; "
        "z – w górę, z = 0 na wodnicy konstrukcyjnej. Tabela LINIE_WREGI w układzie notatek badawczych: z_dok = s − 1,96 "
        "(z_dok = 0 na owrężu), y_dok = z. W Blenderze (bryg.blend): (x, −s, z), dziób ku −Y. W GLB (glTF, +Y w górę): "
        "(x, z, s), dziób ku +Z – tak jak bryg_poklad.json (x, y, z)."),
        statek=st["nazwa"], snow=st["snow"], schemat=st["schemat"], kadlub=st["kadlub"], linie_wregi=dict(przesuniecie_s=LINIE_PRZESUNIECIE, wregi=LINIE_WREGI),
        rzedne=dict(h=RZEDNE_H, s=RZEDNE_S, polszerokosci=RZEDNE), drzewca=DRZEWCA, olinowanie=OLINOWANIE,
        wyposazenie=UKLAD, schematy=SCHEMATY, materialy=MATERIALY)
    with open(sciezka, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False, indent=1)
    return sciezka
