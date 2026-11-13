# -*- coding: utf-8 -*-
"""All words of the tutorial, in English and Polish. Numbers come from the guide chapters
(docs/en, docs/pl) or are measured on the model by render_lines.py."""

T = {}

T['en'] = {
    'title': 'How to Draw a Sailing Ship',
    'subtitle': 'Step by step, in three views',
    'cover_ship': 'Our snow: a small two-masted naval ship of about 1710',
    'cover_note': 'Every picture in this booklet was made by a computer script from the 3D model of our reference ship: '
                  'the lines are traced from the model, not drawn by hand.',
    'cover_ages': 'For curious artists aged about 12 to 16 (and anyone else).',
    'footer': 'MIT License. Drawings rendered as line art from the 3D model of the reference ship.',
    'page': 'page',
    # page 2
    'start_title': 'Before you start',
    'need_title': 'What you need',
    'need': ['Plain paper, A4 or bigger, lying sideways (landscape)',
             'A hard pencil (H or HB) for light construction lines',
             'A soft pencil (2B or 4B) for the final lines and shading',
             'A ruler, best a long one (30 cm)',
             'A soft eraser, and a kneaded one if you have it',
             'Optional: a black fine-liner pen for inking'],
    'how_title': 'How to use this booklet',
    'how': ['Pick one of the three views. The side view is the easiest; start there if this is your first ship.',
            'Each step adds one group of things. Draw only what is new in that step.',
            'Draw construction lines very lightly. You will erase them at the end.',
            'Copy proportions, not millimetres: compare lengths with each other.',
            'Take your time. A ship takes two or three evenings, and that is normal.'],
    'legend_title': 'Colours in the step pictures',
    'legend': [('new', 'black: new lines for this step'),
               ('old', 'light blue: lines you drew in earlier steps'),
               ('guide', 'orange dashes: construction lines (draw lightly, erase later)')],
    'meet_title': 'Meet the ship',
    'meet_intro': 'These names come up in the steps. You do not have to learn them all, but they help you know what you are drawing.',
    'parts': {
        'foremast': 'foremast', 'mainmast': 'mainmast', 'snowmast': 'snow mast (for the gaff sail)',
        'topmast': 'topmast', 'top': 'top (platform)', 'bowsprit': 'bowsprit', 'yard': 'yard',
        'furled_sail': 'furled sail', 'gaff': 'gaff', 'shrouds': 'shrouds', 'ratlines': 'ratlines (rope steps)',
        'stay': 'stay', 'backstay': 'backstay', 'gunport': 'gunport', 'rudder': 'rudder', 'wheel': 'steering wheel',
        'anchor': 'anchor', 'head': 'head (bow decoration)', 'stern': 'stern with windows', 'lantern': 'stern lantern',
        'boat': "ship's boat", 'wale': 'wale', 'quarterdeck': 'quarterdeck', 'waterline': 'waterline',
    },
    # views
    'views': {
        'side': ('View 1: from the side', 'Easy', 'A flat side view, like a plan. Good for learning the proportions.'),
        'bow': ('View 2: from the bow', 'Medium', 'Seen at an angle from the front. You will use vanishing points.'),
        'stern': ('View 3: from the stern', 'Harder', 'Seen at an angle from behind: decorated stern, boat, more overlaps.'),
    },
    'difficulty': 'Difficulty',
    'steps_word': 'Step',
    'steps_plural': 'Steps',
    'bonus_word': 'Bonus',
    'snow_caption': 'Close-up from the side view: the thin snow mast stands just behind the mainmast. '
                    'The gaff hangs from it, and the gaff sail is hoisted along this thin mast.',
    # bonus page
    'bonus_title': 'Bonus challenge: set the sails',
    'bonus_intro': 'In the steps the sails were rolled up on the yards, as on a ship at anchor. Here they are set. '
                   'Erase the furled sails first, then follow these tips.',
    'bonus_tips': ['Draw each sail as a straight four-sided shape first (orange): top corners at the ends of its yard, bottom corners at the ends of the yard below.',
                   'Then curve the edges: the top stays straight along the yard, the sides and the bottom bulge a little, because wind fills the sail.',
                   'Sails hide what is behind them. Erase the masts and ropes behind each sail.',
                   'The gaff sail and the triangular sails at the bow are flat triangles and four-sided shapes along the gaff and the stays.'],
    'bonus_caption': {'side': 'From the side', 'bow': 'From the bow', 'stern': 'From the stern'},
    # mistakes
    'mist_title': 'Common mistakes (and how to fix them)',
    'mistakes': [
        ('mistake-short-masts', 'Masts too short',
         'The masts are nearly as tall as the hull is long. Check with your grid before you draw the rigging.'),
        ('mistake-flat', 'Flat as a board',
         'Only outlines, no light and shadow, no water. Add shading on the side away from the light and a reflection.'),
        ('mistake-thick-ropes', 'Ropes thicker than masts',
         'A rope is about ten times thinner than a mast. Use your sharpest pencil and press lightly.'),
        ('mistake-no-water', 'No waterline',
         'A ship sits in the water: the keel and the bottom are hidden. Start the hull at the waterline.'),
    ],
    'mist_ok': 'Like this',
    # facts
    'facts_title': 'Fun facts about our snow',
    'facts': [
        ('Why the extra thin mast?', 'Right behind the mainmast stands a thin "snow mast", only about 17 cm thick. '
         'The gaff sail runs up and down on it, so the mainmast stays free for its big square sail. This thin mast is what makes the ship a snow.'),
        ('How big is it?', 'The deck is 28 m long and 7.6 m wide, and the ship sits about 3.1 m deep in the water. '
         'The top of the mainmast is almost 29 m above the water: nearly as tall as the ship is long.'),
        ('What do the shrouds do?', 'Shrouds hold each mast from the sides and a little from behind; stays hold it from the front. '
         'Without them the masts would snap or fall over in the first strong wind.'),
        ('Ratlines are a ladder', 'Sailors climbed the shrouds on ratlines: thin ropes tied across them every 33 to 40 cm. '
         'Our model has 456 of them.'),
        ('Ropes are thin', 'The mainmast is about 49 cm thick. The mainstay, one of the thickest ropes, is only 8 cm, a shroud 5 cm and a ratline 1 cm.'),
        ('Turning the wheel', 'The steering wheel is 1.4 m across and has 10 spokes. To swing the rudder from the middle all the way to one side (35 degrees) '
         'the helmsman turns the wheel almost twice: 3.65 turns from one side to the other.'),
        ('Ten guns', 'The snow carries 10 cannons, five on each side, and 8 small swivel guns on the rails.'),
        ('Rolled-up sails', 'In our pictures the sails are furled because the ship is at anchor. Rolling up one big lower sail '
         'took 8 to 12 sailors standing on ropes under the yard for 5 to 10 minutes.'),
        ("The boat behind", "The ship's 5 m boat is towed behind the stern. Before a battle boats were put in the water, "
         "so that cannon balls would not smash them into splinters on deck."),
    ],
    'sources_title': 'Sources (as cited in the construction guide that goes with this booklet)',
    'facts_note': 'All numbers come from the chapters of the construction guide for the reference ship in this repository.',
    # tracing
    'trace_title': 'Tracing and colouring page',
    'trace_intro': 'Clean outlines of the three views. Put thin paper on top and trace, or print this page and colour it in.',
    'about': 'About these pictures: the outlines were rendered from the 3D model with Blender (Freestyle line rendering); '
             'construction lines, shading and reflections were computed by Python scripts. '
             'For the drawings the square yards are swung slightly (braced) so they show better.',
}

T['pl'] = {
    'title': 'Jak narysować żaglowiec',
    'subtitle': 'Krok po kroku, w trzech ujęciach',
    'cover_ship': 'Nasz snow: mały dwumasztowy okręt z około 1710 roku',
    'cover_note': 'Wszystkie obrazki w tej książeczce zrobił skrypt komputerowy z modelu 3D naszego statku wzorcowego: '
                  'linie są odrysowane z modelu, a nie rysowane ręcznie.',
    'cover_ages': 'Dla ciekawych rysowników w wieku mniej więcej 12–16 lat (i dla wszystkich innych).',
    'footer': 'Licencja MIT. Rysunki wyrenderowane jako grafika liniowa z modelu 3D statku wzorcowego.',
    'page': 'strona',
    'start_title': 'Zanim zaczniesz',
    'need_title': 'Czego potrzebujesz',
    'need': ['Gładki papier A4 lub większy, położony poziomo',
             'Twardy ołówek (H albo HB) do lekkich linii pomocniczych',
             'Miękki ołówek (2B albo 4B) do linii końcowych i cieniowania',
             'Linijkę, najlepiej długą (30 cm)',
             'Miękką gumkę, a jeśli masz, także gumkę chlebową',
             'Dla chętnych: czarny cienkopis do obrysowania'],
    'how_title': 'Jak korzystać z książeczki',
    'how': ['Wybierz jedno z trzech ujęć. Najłatwiejszy jest widok z boku; od niego zacznij, jeśli to twój pierwszy statek.',
            'Każdy krok dodaje jedną grupę elementów. Rysuj tylko to, co w danym kroku jest nowe.',
            'Linie pomocnicze rysuj bardzo lekko. Na końcu je wymażesz.',
            'Przenoś proporcje, nie milimetry: porównuj długości między sobą.',
            'Nie spiesz się. Statek zajmuje dwa albo trzy wieczory i to jest normalne.'],
    'legend_title': 'Kolory na obrazkach kroków',
    'legend': [('new', 'czarne: nowe linie w tym kroku'),
               ('old', 'jasnoniebieskie: linie narysowane w poprzednich krokach'),
               ('guide', 'pomarańczowe kreski: linie pomocnicze (rysuj lekko, potem wymaż)')],
    'meet_title': 'Poznaj statek',
    'meet_intro': 'Te nazwy pojawiają się w krokach. Nie musisz uczyć się ich na pamięć, ale pomagają zrozumieć, co rysujesz.',
    'parts': {
        'foremast': 'fokmaszt', 'mainmast': 'grotmaszt', 'snowmast': 'maszt snow (do żagla gaflowego)',
        'topmast': 'stenga', 'top': 'mars (platforma)', 'bowsprit': 'bukszpryt', 'yard': 'reja',
        'furled_sail': 'zwinięty żagiel', 'gaff': 'gafel', 'shrouds': 'wanty', 'ratlines': 'wyblinki (szczeble z lin)',
        'stay': 'sztag', 'backstay': 'padun', 'gunport': 'furta działowa', 'rudder': 'ster', 'wheel': 'koło sterowe',
        'anchor': 'kotwica', 'head': 'galion (ozdoba dziobu)', 'stern': 'rufa z oknami', 'lantern': 'latarnia rufowa',
        'boat': 'łódź okrętowa', 'wale': 'berghołt', 'quarterdeck': 'pokład rufowy', 'waterline': 'linia wody',
    },
    'views': {
        'side': ('Ujęcie 1: z boku', 'łatwe', 'Płaski widok z boku, jak na planie. Dobry do nauki proporcji.'),
        'bow': ('Ujęcie 2: od dziobu', 'średnie', 'Widok ukośnie z przodu. Użyjesz punktów zbiegu.'),
        'stern': ('Ujęcie 3: od rufy', 'trudniejsze', 'Widok ukośnie z tyłu: zdobiona rufa, łódź, więcej zasłaniania.'),
    },
    'difficulty': 'Trudność',
    'steps_word': 'Krok',
    'steps_plural': 'Kroki',
    'bonus_word': 'Bonus',
    'snow_caption': 'Zbliżenie z widoku z boku: cienki maszt snow stoi tuż za grotmasztem. '
                    'Wisi na nim gafel, a żagiel gaflowy podnosi się wzdłuż tego cienkiego masztu.',
    'bonus_title': 'Wyzwanie dodatkowe: postaw żagle',
    'bonus_intro': 'W krokach żagle były zwinięte na rejach, jak na statku stojącym na kotwicy. Tutaj są postawione. '
                   'Najpierw wymaż zwinięte żagle, potem skorzystaj z tych wskazówek.',
    'bonus_tips': ['Każdy żagiel narysuj najpierw jako prosty czworokąt (pomarańczowy): górne rogi na końcach jego rei, dolne na końcach rei poniżej.',
                   'Potem wygnij brzegi: góra zostaje prosta wzdłuż rei, boki i dół lekko się wybrzuszają, bo żagiel wypełnia wiatr.',
                   'Żagle zasłaniają to, co jest za nimi. Wymaż maszty i liny schowane za każdym żaglem.',
                   'Żagiel gaflowy i trójkątne żagle przy dziobie to płaskie trójkąty i czworokąty wzdłuż gafla i sztagów.'],
    'bonus_caption': {'side': 'Z boku', 'bow': 'Od dziobu', 'stern': 'Od rufy'},
    'mist_title': 'Częste błędy (i jak je poprawić)',
    'mistakes': [
        ('mistake-short-masts', 'Maszty za krótkie',
         'Maszty są prawie tak wysokie, jak kadłub jest długi. Sprawdź to na siatce, zanim narysujesz olinowanie.'),
        ('mistake-flat', 'Statek płaski jak deska',
         'Same kontury, bez światła i cienia, bez wody. Dodaj cień po stronie odwróconej od światła i odbicie.'),
        ('mistake-thick-ropes', 'Liny grubsze niż maszty',
         'Lina jest mniej więcej dziesięć razy cieńsza od masztu. Użyj najostrzejszego ołówka i naciskaj lekko.'),
        ('mistake-no-water', 'Brak linii wody',
         'Statek siedzi w wodzie: stępki i dna nie widać. Zacznij kadłub od linii wody.'),
    ],
    'mist_ok': 'Tak jest dobrze',
    'facts_title': 'Ciekawostki o naszym snow',
    'facts': [
        ('Po co dodatkowy cienki maszt?', 'Tuż za grotmasztem stoi cienki „maszt snow”, gruby tylko na około 17 cm. '
         'Po nim chodzi w górę i w dół żagiel gaflowy, więc grotmaszt zostaje wolny dla dużego żagla rejowego. Właśnie ten maszcik sprawia, że statek jest snow.'),
        ('Jaki jest duży?', 'Pokład ma 28 m długości i 7,6 m szerokości, a statek zanurza się na około 3,1 m. '
         'Szczyt grotmasztu jest prawie 29 m nad wodą: niemal tyle, ile statek ma długości.'),
        ('Do czego służą wanty?', 'Wanty trzymają maszt z boków i trochę od tyłu, a sztagi od przodu. '
         'Bez nich maszty złamałyby się albo przewróciły przy pierwszym mocnym wietrze.'),
        ('Wyblinki to drabina', 'Marynarze wspinali się po wantach po wyblinkach: cienkich linkach zawiązanych w poprzek co 33–40 cm. '
         'Nasz model ma ich 456.'),
        ('Liny są cienkie', 'Grotmaszt ma około 49 cm grubości. Grotsztag, jedna z najgrubszych lin, ma tylko 8 cm, wanta 5 cm, a wyblinka 1 cm.'),
        ('Kręcenie kołem', 'Koło sterowe ma 1,4 m średnicy i 10 szprych. Żeby wychylić ster ze środka do końca w jedną stronę (35 stopni), '
         'sternik obraca koło prawie dwa razy: 3,65 obrotu z jednej skrajnej pozycji do drugiej.'),
        ('Dziesięć dział', 'Snow ma 10 dział, po pięć na każdej burcie, i 8 małych działek relingowych.'),
        ('Zwinięte żagle', 'Na naszych obrazkach żagle są zwinięte, bo statek stoi na kotwicy. Zwinięcie jednego dużego dolnego żagla '
         'zajmowało 8–12 marynarzom stojącym na linach pod reją od 5 do 10 minut.'),
        ('Łódź za rufą', 'Pięciometrowa łódź okrętowa płynie na holu za rufą. Przed bitwą łodzie spuszczano na wodę, '
         'żeby kule armatnie nie roztrzaskały ich w drzazgi na pokładzie.'),
    ],
    'sources_title': 'Źródła (za rozdziałami przewodnika budowy, który towarzyszy tej książeczce)',
    'facts_note': 'Wszystkie liczby pochodzą z rozdziałów przewodnika budowy statku wzorcowego w tym repozytorium.',
    'trace_title': 'Strona do kalkowania i kolorowania',
    'trace_intro': 'Czyste kontury trzech ujęć. Połóż na wierzchu cienki papier i odrysuj albo wydrukuj tę stronę i pokoloruj.',
    'about': 'O obrazkach: kontury wyrenderowano z modelu 3D w Blenderze (renderowanie linii Freestyle); '
             'linie pomocnicze, cieniowanie i odbicia policzyły skrypty w Pythonie. '
             'Na potrzeby rysunków reje są lekko obrócone (zbrasowane), żeby było je lepiej widać.',
}

SOURCES = [
    'D. Steel, The Elements and Practice of Rigging and Seamanship (1794): https://whalesite.org/anthology/1794_Steel_Elements_and_Practice.htm',
    "D. Lever, The Young Sea Officer's Sheet Anchor (1808): https://archive.org/details/youngseaofficers00leve",
    'R. Kenchington, "William Sutherland\'s Ship, circa 1710", The Northern Mariner (1993): https://cnrs-scrn.org/northern_mariner/vol03/tnm_3_1_1-43.pdf',
    'T. Blanckley, A Naval Expositor (1750): https://www.gutenberg.org/ebooks/52902',
    'Royal Museums Greenwich, ship model SLR0416: https://www.rmg.co.uk/collections/objects/rmgc-object-66377',
    'Wikipedia: Snow (ship): https://en.wikipedia.org/wiki/Snow_(ship); Ratlines: https://en.wikipedia.org/wiki/Ratlines; '
    "Ship's wheel: https://en.wikipedia.org/wiki/Ship%27s_wheel",
    'Lehman Shipyard, Standing rigging: https://lehmanshipyard.com/2024/04/06/standing-rigging-shrouds-stays/',
    'Polish rigging names: https://potempski.com/rejowe/inne/zagle.htm',
]

# ------------------------------------------------------------------ step texts
# STEPS[lang][view] = list of (title, text) for steps 1..9 ; '{...}' fields are filled from measured numbers.
STEPS = {'en': {}, 'pl': {}}

_en_common = {
    3: ('The hull outline',
        'Now draw the real shape of the hull over your blocks. Start with the waterline, then the line of the rail: it is not straight '
        'but rises a little towards the bow and steps up at the quarterdeck. Add the stem at the bow, the stern, the rudder and the long lines of the wales along the side.'),
    4: ('Masts and bowsprit',
        'Give the mast lines their thickness: each mast gets thinner towards the top and is made of three pieces (orange crosses show where one piece ends). '
        'Draw the tops, the small platforms where the pieces meet. Then the bowsprit, and the thin snow mast behind the mainmast.'),
    5: ('Yards, furled sails and the gaff',
        'Draw each yard as a long thin shape crossing its mast, using the orange centre lines. The rolled-up sails sit on top of the yards like sausages. '
        'Add the gaff: the slanting spar behind the mainmast.'),
    6: ('Standing rigging',
        'Stays first: long straight lines running forward and down from each mast. Then the shrouds: draw the orange triangles lightly '
        'and fill them with lines fanning down to the side of the hull. Ratlines last, and only a few: every third one is plenty.'),
    7: ('Hull details',
        'Add the gunport lids along the orange line, with a gun barrel in most of the ports, and the channels: the ledges on the side where the shrouds end. '
        'Then the small things: windows and lantern at the stern, anchor at the bow, the steering wheel and the boat on its line behind the ship.'),
    8: ('Shading, reflection, finish',
        'Go over the lines you want to keep with a soft pencil or a pen, and erase all construction lines. Shade the side of the hull that is away from the light '
        'with close parallel lines. Draw the reflection as broken, wobbly strokes under the ship.'),
    9: ('Bonus: set sails', ''),
}
_pl_common = {
    3: ('Zarys kadłuba',
        'Teraz narysuj prawdziwy kształt kadłuba na bryłach. Zacznij od linii wody, potem linia relingu: nie jest prosta, '
        'lekko wznosi się ku dziobowi i robi stopień przy pokładzie rufowym. Dodaj dziobnicę, rufę, ster i długie linie berghołtów wzdłuż burty.'),
    4: ('Maszty i bukszpryt',
        'Nadaj liniom masztów grubość: każdy maszt zwęża się ku górze i składa się z trzech części (pomarańczowe krzyżyki pokazują, gdzie kończy się część). '
        'Narysuj marsy, czyli małe platformy na łączeniach. Potem bukszpryt i cienki maszt snow za grotmasztem.'),
    5: ('Reje, zwinięte żagle i gafel',
        'Każdą reję narysuj jako długi, wąski kształt w poprzek masztu, wzdłuż pomarańczowej osi. Zwinięte żagle leżą na rejach jak kiełbaski. '
        'Dodaj gafel: ukośne drzewce za grotmasztem.'),
    6: ('Olinowanie stałe',
        'Najpierw sztagi: długie proste linie biegnące od masztu do przodu i w dół. Potem wanty: lekko narysuj pomarańczowe trójkąty '
        'i wypełnij je liniami rozchodzącymi się wachlarzem do burty. Wyblinki na końcu i tylko kilka: wystarczy co trzecia.'),
    7: ('Szczegóły kadłuba',
        'Dodaj pokrywy furt działowych wzdłuż pomarańczowej linii, w większości furt lufę działa, i ławy wantowe: listwy na burcie, na których kończą się wanty. '
        'Potem drobiazgi: okna i latarnia na rufie, kotwica przy dziobie, koło sterowe i łódź na linie za statkiem.'),
    8: ('Cieniowanie, odbicie, wykończenie',
        'Poprowadź miękkim ołówkiem albo cienkopisem linie, które zostają, i wymaż wszystkie linie pomocnicze. Zacieniuj burtę odwróconą od światła '
        'gęstymi równoległymi kreskami. Odbicie narysuj jako przerywane, falujące kreski pod statkiem.'),
    9: ('Bonus: postawione żagle', ''),
}

STEPS['en']['side'] = {
    1: ('Horizon, water and a grid',
        'Draw the horizon across the paper: it is at the height of your eyes. Just below it goes the waterline. '
        'On the waterline draw a grid of {cols} equal squares for the length of the hull and {rows} squares up. '
        'Mark the masts: the foremast about {fore_pos} squares from the bow, the mainmast about {main_pos}. Their tops reach about {fore_top} and {main_top} squares up.'),
    2: ('Simple blocks',
        'Build the hull from simple shapes: a long low box in the middle, a taller box at the stern (the quarterdeck), and a wedge at the bow. '
        'Then draw the mast axes straight up from your marks, and a slanting line for the bowsprit, about {bsp} squares beyond the bow.'),
}
STEPS['pl']['side'] = {
    1: ('Horyzont, woda i siatka',
        'Narysuj horyzont przez całą kartkę: jest na wysokości twoich oczu. Tuż pod nim idzie linia wody. '
        'Na linii wody narysuj siatkę: {cols} równych kwadratów na długość kadłuba i {rows} w górę. '
        'Zaznacz maszty: fokmaszt mniej więcej {fore_pos} kwadratu od dziobu, grotmaszt około {main_pos}. Ich szczyty sięgają około {fore_top} i {main_top} kwadratów w górę.'),
    2: ('Proste bryły',
        'Zbuduj kadłub z prostych kształtów: długie niskie pudełko pośrodku, wyższe pudełko na rufie (pokład rufowy) i klin na dziobie. '
        'Potem narysuj osie masztów pionowo w górę od znaczków i ukośną linię bukszprytu, sięgającą około {bsp} kwadratu przed dziób.'),
}
STEPS['en']['bow'] = {
    1: ('Horizon, water and a frame',
        'Draw the horizon at your eye level, low on the page. Both vanishing points (VP) lie on it, far outside the paper to the left and right. '
        'Draw the waterline slanting gently towards one of them. Then a light frame for the whole ship, divided into 4 by 4, and mark where the masts stand and how high they reach.'),
    2: ('Boxes in perspective',
        'Draw the hull as boxes in perspective. Lines along the ship run towards one vanishing point, lines across it towards the other; '
        'upright lines stay upright. Use a ruler and aim at your VP marks. Add the bow wedge, then the mast axes and the bowsprit line.'),
}
STEPS['pl']['bow'] = {
    1: ('Horyzont, woda i ramka',
        'Narysuj horyzont na wysokości oczu, nisko na kartce. Leżą na nim oba punkty zbiegu (PZ), daleko poza kartką z lewej i z prawej. '
        'Narysuj linię wody, lekko pochyloną w stronę jednego z nich. Potem lekką ramkę na cały statek, podzieloną na 4 na 4, i zaznacz, gdzie stoją maszty i jak wysoko sięgają.'),
    2: ('Pudełka w perspektywie',
        'Narysuj kadłub jako pudełka w perspektywie. Linie wzdłuż statku biegną do jednego punktu zbiegu, linie w poprzek do drugiego, '
        'a pionowe zostają pionowe. Użyj linijki i celuj w znaczki PZ. Dodaj klin dziobu, potem osie masztów i linię bukszprytu.'),
}
STEPS['en']['stern'] = {
    1: ('Horizon, water and a frame',
        'Draw the horizon at your eye level. The vanishing points (VP) are on it, outside the paper. '
        'Draw the waterline sloping gently towards one of them, then a light frame divided into 4 by 4. Mark the mast positions and tops: '
        'here the mainmast is the one closer to you, so it looks taller.'),
    2: ('Boxes in perspective',
        'The stern is a tall box facing you at an angle, the rest of the hull a longer, lower box behind it. '
        'Aim every line along the ship at one VP and every line across it at the other. Then draw the mast axes and the bowsprit line.'),
}
STEPS['pl']['stern'] = {
    1: ('Horyzont, woda i ramka',
        'Narysuj horyzont na wysokości oczu. Punkty zbiegu (PZ) leżą na nim, poza kartką. '
        'Narysuj linię wody lekko pochyloną w stronę jednego z nich, potem lekką ramkę podzieloną na 4 na 4. Zaznacz miejsca i szczyty masztów: '
        'tutaj bliżej ciebie jest grotmaszt, więc wydaje się wyższy.'),
    2: ('Pudełka w perspektywie',
        'Rufa to wysokie pudełko zwrócone do ciebie ukośnie, reszta kadłuba to dłuższe, niższe pudełko za nim. '
        'Każdą linię wzdłuż statku kieruj do jednego PZ, każdą w poprzek do drugiego. Potem narysuj osie masztów i linię bukszprytu.'),
}

# view-specific extra hints for later steps (appended to the common text)
EXTRA = {
    'en': {
        ('side', 5): ' From the side the yards point a little towards you, so they look short.',
        ('bow', 5): ' The yards also follow the perspective: the far ends look shorter.',
        ('stern', 3): ' The stern is wide and flat with windows; draw its outline first, the windows come in step 7.',
        ('stern', 7): ' The stern has the most detail: take it slowly, window by window.',
        ('bow', 3): ' At the bow the hull narrows to the stem; the head with its decoration sticks out in front.',
    },
    'pl': {
        ('side', 5): ' Z boku reje są skierowane trochę w twoją stronę, więc wyglądają na krótkie.',
        ('bow', 5): ' Reje też podlegają perspektywie: dalsze końce wyglądają na krótsze.',
        ('stern', 3): ' Rufa jest szeroka i płaska, z oknami; najpierw narysuj jej obrys, okna przyjdą w kroku 7.',
        ('stern', 7): ' Rufa ma najwięcej szczegółów: rysuj powoli, okno po oknie.',
        ('bow', 3): ' Przy dziobie kadłub zwęża się do dziobnicy; galion z ozdobą wystaje do przodu.',
    },
}

def step_text(lang, view, step, nums):
    if step in (1, 2):
        title, body = STEPS[lang][view][step]
    else:
        title, body = (_en_common if lang == 'en' else _pl_common)[step]
        body = body + EXTRA[lang].get((view, step), '')
    return title, body.format(**nums)
