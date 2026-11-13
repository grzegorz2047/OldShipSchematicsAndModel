"""Słownik nazw publicznych (czysty Python): polskie nazwy obiektów, węzłów GLB, kluczy i wartości generatora →
angielskie nazwy w danych publicznych i na rysunkach. Jedna polska nazwa – jedna angielska.

Zawartość:
- SLOWA: pojedyncze słowa i nazwy złożone (obiekty, grupy lin, materiały, czynności, przeszkody, pule kołków),
- BAZY: wzorce nazw obiektów z burtą i numerem (L1, P3) – en(nazwa) składa nazwę angielską,
- PARAM: klucze parametry.py → (klucz angielski, pewność, rozdział przewodnika, uwaga),
- PODKLUCZE: klucze słowników w UKLAD i innych grupach,
- OPISY: stałe teksty opisowe generatora (osie ruchu itd.) → angielski.
Kontrola (kontrola_publiczna.py) sprawdza, że w danych publicznych nie zostało żadne polskie słowo spoza tego słownika.
"""
import re

C01 = "docs/en/01-ship-type-and-era.md"
C02 = "docs/en/02-hull-lines-and-offsets.md"
C03 = "docs/en/03-hull-construction.md"
C04 = "docs/en/04-decks-bulwarks-stern-head.md"
C05 = "docs/en/05-masts-and-spars.md"
C06 = "docs/en/06-standing-rigging.md"
C07 = "docs/en/07-running-rigging-and-belaying.md"
C08 = "docs/en/08-ropes-blocks-and-sails.md"
C09 = "docs/en/09-deck-machinery.md"

PER, SEC, INF, REF = "period", "secondary", "our inference", "reference model"

STRONA = {"L": "port", "P": "starboard"}

# ------------------------------------------------------------------ słowa i nazwy złożone
SLOWA = {
    # maszty, drzewca, reje
    "fok": "fore", "grot": "main", "fokmars": "fore_topsail", "grotmars": "main_topsail", "fokbram": "fore_topgallant",
    "grotbram": "main_topgallant", "blinda": "spritsail", "gafel": "gaff", "bom": "boom", "snow": "snow_mast",
    "drzewca": "spars", "bukszpryt": "bowsprit", "bomstenga": "jib_boom",
    "reja_fok": "fore_yard", "reja_grot": "main_yard", "reja_fokmars": "fore_topsail_yard",
    "reja_grotmars": "main_topsail_yard", "reja_fokbram": "fore_topgallant_yard", "reja_grotbram": "main_topgallant_yard",
    "reja_blinda": "spritsail_yard",
    "rak_fok": "fore_yard_parrel", "rak_grot": "main_yard_parrel", "rak_fokmars": "fore_topsail_yard_parrel",
    "rak_grotmars": "main_topsail_yard_parrel", "rak_fokbram": "fore_topgallant_yard_parrel",
    "rak_grotbram": "main_topgallant_yard_parrel",
    "maszt_fok": "fore_mast", "maszt_grot": "main_mast", "maszt_snow": "snow_mast",
    # żagle
    "zagiel_fok": "fore_course", "zagiel_grot": "main_course", "zagiel_fokmars": "fore_topsail",
    "zagiel_grotmars": "main_topsail", "zagiel_fokbram": "fore_topgallant", "zagiel_grotbram": "main_topgallant",
    "zagiel_blinda": "spritsail", "zagiel_gaflowy": "gaff_sail", "zagle_sztakslowe": "staysails_and_jib",
    "zagiel_kliwer": "jib", "zagiel_sztaksel_fokstengi": "fore_topmast_staysail",
    "zagiel_sztaksel_grotstengi": "main_topmast_staysail", "zagiel_sztaksel_grota": "main_staysail",
    # kadłub, rufa, dziób
    "kadlub": "hull", "kadlub_listwy": "hull_mouldings", "kadlub_okucia_steru": "hull_rudder_irons",
    "kadlub_reling": "hull_rail", "kadlub_sciek_wregi": "hull_waterway_and_timberheads", "kadlub_stepka": "hull_backbone",
    "kadlub_statyczny": "hull_static", "drzewca_statyczne": "spars_static", "takielunek_statyczny": "rigging_static",
    "balustrada_progu": "breastwork_rail", "grodz_drzwi": "bulkhead_with_doors", "schody_rufowe": "quarterdeck_ladder",
    "rufa_boki": "stern_quarter_pieces", "rufa_pawez": "stern_transom", "rufa_rzezby": "stern_carvings",
    "latarnia_rufowa": "stern_lantern", "galion": "head", "galion_rzezby": "head_carvings", "kotbelki": "catheads",
    "ster": "rudder", "ster_glowica": "rudder_head", "pokrywa_trzonu": "rudder_stock_cover",
    "lawy_wantowe": "channels", "jufersy": "deadeyes", "sztagi_okucia": "stay_fittings",
    # pokład i wyposażenie
    "bloki": "blocks", "bloki_kolo": "blocks_wheel_variant", "bloki_rumpel": "blocks_tiller_variant",
    "dzwon": "bell", "dzwon_rama": "belfry", "kabestan": "capstan", "kabestan_beben": "capstan_barrel",
    "kabestan_podstawa": "capstan_pawl_rim", "knagi_rufowe": "quarterdeck_kevels", "kolkownice": "pin_rails",
    "kolkownica": "pin_rail", "kolo_sterowe": "steering_wheel", "kolo_stojaki": "wheel_standards",
    "lodz": "boat", "lodz_maska_wody": "boat_water_mask", "luk_dziobowy": "fore_hatch", "luk_glowny": "main_hatch",
    "nagielbank_fok": "fore_fife_rail", "nagielbank_grot": "main_fife_rail", "naped_kolo": "steering_wheel_variant",
    "naped_rumpel": "deck_tiller_variant", "okucia_pokladu": "deck_fittings", "okucia_pokladu_rumpel":
        "deck_fittings_tiller_variant", "okucia_pokladu_kolo": "deck_fittings_wheel_variant",
    "rumpel": "deck_tiller", "rumpel_pod_pokladem": "tiller_below_deck", "szafka_kompasowa": "binnacle",
    "wyposazenie_drobne": "small_fittings", "zejsciowka": "companion", "beczka_wody": "water_cask", "kojec": "hen_coop",
    "nadburcie_L": "bulwark_port", "nadburcie_P": "bulwark_starboard",
    "komin": "galley_chimney", "lina_kotwiczna": "anchor_cable", "skrzynia_broni": "arms_chest",
    "kotwica_L": "bower_anchor_port", "kotwica_P": "bower_anchor_starboard",
    # grupy lin
    "talrepy": "lanyards", "wyblinki": "ratlines", "buchty": "coils", "ruchome": "running", "perty": "footropes",
    "wanty_grot": "main_shrouds", "wanty_fok": "fore_shrouds", "dziala": "gun_tackle", "sztagi": "stays",
    "podwantki": "futtock_shrouds", "wanty_stengowe": "topmast_shrouds", "paduny": "backstays", "wiazanie": "gammoning",
    "wanty_bramstengowe": "topgallant_shrouds", "sciagacze": "catharpins", "stropy": "slings_and_ties",
    "talie_rumpla": "tiller_tackles", "kotwice": "anchor_gear", "sterlina": "tiller_rope",
    # materiały
    "lina_smolowana": "rope_tarred", "lina_jasna": "rope_untarred", "burta_drewno": "side_oiled_oak",
    "farba_czarna": "paint_black", "farba_ochra": "paint_ochre", "farba_czerwona": "paint_red",
    "farba_niebieska": "paint_blue", "farba_dno_biala": "bottom_white_stuff", "farba_dno_czerwona": "bottom_red_brown",
    "poklad": "deck_planking", "drewno": "wood", "drewno_ciemne": "wood_dark", "drewno_czarne": "wood_black",
    "laweta": "carriage_red_ochre", "rzezby_zlote": "carvings_yellow", "zelazo": "iron", "braz": "bronze",
    "farba_czarna_gladka": "paint_black_smooth", "zelazo_lufa": "iron_gun_barrel",
    "plotno": "canvas", "szklo": "glass", "krata": "grating",
    # regiony malowania
    "dno": "bottom", "burta": "side", "bergholt": "wale", "burta_gorna": "upper_side", "pas_furt": "port_band",
    "listwa": "moulding", "reling": "rail", "wnetrze": "inboard", "pawez": "transom", "rzezby": "carvings",
    "pokrywa_zew": "lid_outboard", "pokrywa_wew": "lid_inboard",
    # czynności (stanowiska)
    "beczka": "water_cask", "dzialo_chlopiec": "gun_powder_boy", "dzialo_kapitan": "gun_captain",
    "dzialo_ladowniczy": "gun_loader", "dzialo_odciag": "gun_train_tackle", "dzialo_talia": "gun_side_tackle",
    "dzialo_wyciorowy": "gun_sponger", "furta": "port_lid", "kolo": "wheel", "kompas": "compass",
    "kotbelka": "cathead", "kotwica": "anchor", "liny_brasy": "braces", "liny_faly": "halliards", "liny_gaje": "vangs",
    "liny_gejtawy": "clewlines", "liny_szoty": "sheets", "liny_topenanty": "lifts", "log": "log_line", "luk": "hatch",
    "mars": "top", "nok_rei": "yardarm", "pompa": "pump", "sonda": "hand_lead", "wanty": "shrouds_climb",
    # pule kołków, miejsca
    "nagielbank": "fife_rail", "knagi": "kevels", "lawa_fok": "fore_channel", "lawa_grot": "main_channel",
    "reling_dziobu": "bow_rail",
    # grupy liny w stanowiskach
    "topenanty": "lifts", "brasy": "braces", "gejtawy": "clewlines", "szoty": "sheets", "faly": "halliards",
    "gaje": "vangs",
    # poziomy, warianty, stany
    "glowny": "main_deck", "rufowy": "quarterdeck", "poklad_glowny": "main_deck", "poklad_rufowy": "quarterdeck",
    "za_rufa": "towed_astern", "na_pokladzie": "on_deck", "brak": "none", "wlasne": "own_mesh", "polyhaven": "polyhaven_cc0",
    "schody": "stairs", "wspinaczka": "climb", "drabina_w_dol": "ladder_down", "prostokat": "rectangle", "kolo_ksztalt": "circle",
    "wielokat": "polygon", "obrot": "rotation", "przesuniecie": "translation",
    # inne obiekty
    "pompa_L": "pump_port", "pompa_P": "pump_starboard", "pompa_L_dzwignia": "pump_port_brake",
    "pompa_P_dzwignia": "pump_starboard_brake", "stan": "station",
}

# wzorce: polska baza z {S} (burta L/P), {N} (numer), {SN} (np. L3) → angielska
BAZY = [
    (r"^dzialko_(?P<S>[LP])(?P<N>\d+)$", "swivel_gun_{S}_{N}"),
    (r"^dzialo_(?P<S>[LP])(?P<N>\d+)_lufa$", "gun_{S}_{N}_barrel"),
    (r"^dzialo_(?P<S>[LP])(?P<N>\d+)$", "gun_{S}_{N}"),
    (r"^furta_pokrywa_(?P<S>[LP])(?P<N>\d+)$", "gunport_lid_{S}_{N}"),
    (r"^stan_(?P<A>[a-z_]+?)_(?P<N>\d+)$", "station_{A}_{N}"),
    (r"^lina_dyn_(?P<G>[a-z_]+?)_(?P<N>\d+)_glb$", "rope_dynamic_{G}_{N}_glb"),
    (r"^lina_dyn_(?P<G>[a-z_]+?)_(?P<N>\d+)$", "rope_dynamic_{G}_{N}"),
    (r"^lina_(?P<G>[a-z_]+?)_(?P<O>reja_[a-z]+|kabestan_beben)_glb$", "rope_{G}_{O}_glb"),
    (r"^lina_(?P<G>[a-z_]+?)_(?P<O>reja_[a-z]+|kabestan_beben)$", "rope_{G}_{O}"),
    (r"^lina_(?P<G>[a-z_]+?)_glb$", "rope_{G}_glb"),
    (r"^lina_(?P<G>[a-z_]+)$", "rope_{G}"),
    (r"^kolkownica_(?P<S>[LP])_(?P<M>fok|grot)$", "pin_rail_{S}_{M}"),
    (r"^wanty_(?P<M>fok|grot)_(?P<S>[LP])$", "shrouds_{M}_{S}"),
    (r"^(?P<B>[a-z_]+)_(?P<S>[LP])$", "{B}_{S}"),
]

# ------------------------------------------------------------------ nazwy lin (rodzaje) – dane_publiczne.py
LINY = {
    "wanta": "shroud", "strop_jufersa": "deadeye_strop", "talrep": "lanyard", "wyblinka": "ratline",
    "podwantka": "futtock_shroud", "wyblinka_stengowa": "topmast_ratline", "sciagacz": "catharpin", "wanta_stengowa": "topmast_shroud",
    "wanta_bramstengowa": "topgallant_shroud", "padun_stengowy": "topmast_backstay",
    "padun_bramstengowy": "topgallant_backstay", "petla_want": "shroud_eye_at_masthead",
    "grotsztag": "main_stay", "obroza_grotsztagu": "main_stay_collar", "taliowka_grotsztagu": "main_stay_lanyard",
    "foksztag": "fore_stay", "sztag_grotstengi": "main_topmast_stay", "sztag_fokstengi": "fore_topmast_stay",
    "sztag_grotbramstengi": "main_topgallant_stay", "sztag_fokbramstengi": "fore_topgallant_stay",
    "sztag_kliwra": "jib_stay", "watersztag": "bobstay", "wanta_bukszprytu": "bowsprit_shroud",
    "wiazanie_bukszprytu": "gammoning_turn", "perta": "footrope", "strzemie": "stirrup", "strop_rei": "yard_sling",
    "tie_marsrei": "topsail_tie", "lina_hamujaca": "breeching", "talia_dziala": "gun_side_tackle",
    "buchta_talii": "gun_tackle_coil", "lina_kabestanu": "capstan_swifter", "sterlina": "tiller_rope",
    "talia_rumpla": "tiller_tackle", "linka_dzwonu": "bell_rope", "fangalina_lodzi": "boat_painter",
    "talia_kotbelki": "cat_fall", "lina_kotwiczna": "anchor_cable", "lina_kotwiczna_kluza": "anchor_cable_hawse",
    "lina_kotwiczna_poklad": "anchor_cable_on_deck",
    "topenanta": "lift", "wisior_brasu": "brace_pendant", "bras": "brace", "gejtawa": "clewline",
    "szot": "sheet", "gording": "buntline", "fal_marsrei": "topsail_halliard", "gardafal": "throat_halliard",
    "pikfal": "peak_halliard", "gaj": "vang", "buchta": "coil", "lina_ruchoma": "running_rope",
    "gejtawa_gafla": "brail", "gejtawa_gafla_odnoga": "brail_leg", "szot_bomu": "boom_sheet", "topenanta_bomu": "boom_topping_lift",
}

# ------------------------------------------------------------------ teksty opisowe generatora
OPISY = {
    "obrót wokół lokalnej Z 360°, przechył ±30°": "rotation about local Z 360°, tilt ±30°",
    "obrót wokół lokalnej Y (podniesienie lufy, ok. −5…+10°)": "rotation about local Y (barrel elevation, about −5…+10°)",
    "lokalna -X (wzdłuż lufy, do środka okrętu)": "local −X (along the barrel, inboard)",
    "wahanie wokół lokalnej Z (wzdłuż okrętu)": "swing about local Z (fore and aft)",
    "obrót wokół lokalnej Z (zawias nad furtą), dodatni otwiera na zewnątrz":
        "rotation about local Z (hinge above the port), positive opens outboard",
    "obrót wokół lokalnej Z (oś masztu) – brasowanie; reje: przesunięcie wzdłuż lokalnej Z o wysokosc_robocza_dz_m – "
    "pozycja robocza (żagiel postawiony)":
        "rotation about local Z (mast axis) – bracing; yards: translation along local Z by working_height_dz_m – "
        "working position (sail set)",
    "obrót wokół lokalnej Z (pion), bez ograniczeń": "rotation about local Z (vertical), unlimited",
    "obrót wokół lokalnej Z (oś bębna, ku dziobowi), bez ograniczeń": "rotation about local Z (drum axis, forward), unlimited",
    "obrót wokół lokalnej Z (poprzecznie), wahanie ±25°": "rotation about local Z (athwartships), swing ±25°",
    "dziecko steru: obrót razem ze sterem wokół jego osi, ±35°": "child of the rudder: turns with the rudder about its axis, ±35°",
    "dziecko steru: obrót razem ze sterem, ±35°": "child of the rudder: turns with the rudder, ±35°",
    "dziecko steru: obrót razem ze sterem wokół jego osi": "child of the rudder: turns with the rudder about its axis",
    "obrót wokół lokalnej Z (oś zawiasów = oś trzonu), ±35°": "rotation about local Z (pintle axis = stock axis), ±35°",
    "lokalna -X: odrzut": "local −X: recoil",
}

# ------------------------------------------------------------------ parametry (parametry.py)
# klucz PL → (klucz EN z jednostką, pewność, rozdział, uwaga EN)
PARAM = {
    # ---- kadłub
    "ZK0": ("keel_rabbet_z_at_s0_m", SEC, C02, "keel rabbet height at s = 0; rabbet line z = keel_rabbet_z_at_s0_m + keel_drag_per_m · s"),
    "ZK_SPADEK": ("keel_drag_per_m", SEC, C02, "drag 0.40 m over the 22.4 m keel"),
    "STEPKA_WYS": ("keel_depth_below_rabbet_m", SEC, C03, "keel 0.25 below the rabbet + false keel 0.06"),
    "STEPKA_SZER": ("keel_sided_m", SEC, C03, "siding of keel and sternpost"),
    "DZIOBNICA_SZER": ("stem_sided_bottom_top_m", SEC, C03, "stem siding at the foot / at the head"),
    "DZIOBNICA_GR": ("stem_moulded_m", SEC, C03, "stem thickness forward of the rabbet"),
    "TYLNICA_GR": ("sternpost_moulded_heel_head_m", SEC, C03, "sternpost aft of the rabbet, at heel / head"),
    "POSZYCIE_GR": ("planking_thickness_m", SEC, C03, "bottom planking; added to the moulded offsets"),
    "DZIOB": ("stem_rabbet_curve_s_z_m", SEC, C02, "stem rabbet (s, z): quarter ellipse to the deck, then nearly upright"),
    "TUCK_S0": ("sternpost_rabbet_s_at_heel_m", SEC, C02, "sternpost rabbet at the heel"),
    "TUCK_RAKE": ("sternpost_rake_deg", SEC, C02, "from vertical, about 12° in the research notes"),
    "Z_PAWEZ_DOLNA": ("wing_transom_z_m", SEC, C04, "top of the flat lower transom (wing transom)"),
    "RUFA": ("stern_centreline_s_z_m", REF, C04, "stern centreline above the wing transom: counter, then upper transom "
             "raked 8°; counter 0.85 m instead of 0.6 m so the rudder stock clears the transom"),
    "RUFA_WYGIECIE": ("transom_round_up_m", INF, C04, "round of the transom face in plan, 0.22 m over 5.1 m"),
    "Z_NAWIS": ("counter_top_z_m", SEC, C04, "top of the counter = foot of the windowed transom"),
    "STER_LUZ_TYLNICA": ("rudder_clearance_sternpost_m", INF, C04, "sternpost face forward of the pintle axis"),
    "STER_LUZ_KONTRA": ("rudder_clearance_counter_m", INF, C04, "blade top under the counter at 35°"),
    "STER_OTWOR_LUZ": ("helm_port_clearance_m", INF, C04, "radial clearance of the stock in the helm port"),
    "RUFA_SZER": ("transom_half_breadth_z_y_m", SEC, C02, "half-breadth of the after end (z, y); below the first "
                  "point only the deadwood"),
    "POKLAD_BOK": ("deck_at_side_s_z_m", SEC, C02, "main deck at side: 0.90 + 0.95 u² forward, 0.90 + 0.45 u² aft"),
    "WYPUKLOSC": ("deck_camber_m", SEC, C04, "camber of the beams at the reference half-breadth"),
    "POL_B": ("camber_reference_half_breadth_m", SEC, C04, "half-breadth at which the camber is measured"),
    "POKLAD_GR": ("deck_plank_thickness_m", SEC, C04, ""),
    "RELING": ("rail_height_above_deck_s_m", SEC, C04, "rail above the deck at side: quarterdeck 1.7 + 0.9, waist 1.05"),
    "POLPOKLAD_S": ("quarterdeck_break_s_m", SEC, C04, "front edge of the quarterdeck"),
    "POLPOKLAD_H": ("quarterdeck_height_above_main_deck_m", SEC, C04, ""),
    "NADBURCIE_GR": ("bulwark_thickness_m", SEC, C04, "planking 0.05 + top timbers 0.12, the part standing proud"),
    "RELING_SZER": ("rail_cap_width_m", INF, C04, "bulwark 0.14 + about 8 cm overhang each side"),
    "RELING_GR": ("rail_cap_thickness_m", INF, C04, ""),
    "PILERS": ("timberhead_width_projection_m", SEC, C04, "top timbers seen inboard: width × projection"),
    "PILERS_ROZSTAW": ("frame_spacing_m", SEC, C03, "room and space"),
    "WODOSCIEK": ("waterway_width_height_m", SEC, C04, ""),
    "LINIA_WODNA_FARBA": ("bottom_paint_line_above_wl_m", SEC, C04, "boot top at the waterline"),
    "BERGHOLTY": ("wales_from_to_projection_m", SEC, C03, "wale strakes: (from, to) below the deck line, projection"),
    "LISTWA_FURT": ("port_band_from_to_above_deck_m", REF, C04, "painted band of the ports, scheme b"),
    "FURTY_S": ("gunport_centres_s_m", SEC, C04, "open gunports, each side: 7 pairs at 2.45 m in the research notes"),
    "FURTY_ZAMKNIETE_S": ("closed_gunport_centres_s_m", REF, C04, "aftmost port under the quarterdeck: closed lid only"),
    "FURTA_SZER": ("gunport_width_m", SEC, C04, "ports for 4-pounders 0.60 × 0.50; the model carries 6-pounder "
                   "barrels of 2.0 m (deliberate)"),
    "FURTA_PROG": ("gunport_sill_above_deck_m", SEC, C04, ""),
    "FURTA_NADPROZE": ("gunport_lintel_above_deck_m", SEC, C04, ""),
    "POKRYWA_KAT": ("port_lid_open_angle_deg", INF, C04, "lids open above the barrel; game range 0–100"),
    # ---- drzewca (długości, średnice, topy z reguł Steela: generowane w PARAM_DRZEWCA niżej)
    "FOK_S": ("fore_mast_s_at_deck_m", REF, C05, "0.14 L abaft the stem head"),
    "GROT_S": ("main_mast_s_at_deck_m", REF, C05, "0.55 L abaft the stem head (rule 2/3 L would put it on the "
               "quarterdeck break)"),
    "GROT_POCHYL": ("main_mast_rake_deg", SEC, C05, "aft"),
    "FOK_POCHYL": ("fore_mast_rake_deg", SEC, C05, "aft"),
    "KILSON_NAD_WREBEM": ("mast_heel_above_rabbet_m", INF, C05, "heel on the keelson: floor 0.22 + keelson 0.28"),
    "TAPER_MASZT": ("lower_mast_taper_ratios", PER, C05, "diameter ratios at 0, 1/4, 1/2, 3/4, under the head, top of head"),
    "TAPER_STENGA": ("topmast_taper_ratios", PER, C05, "as above for topmasts"),
    "TAPER_REJA": ("yard_taper_ratios", PER, C05, "slings, 1/4, 1/2, 3/4, yardarm"),
    "MARS_SZER_STENGI": ("top_breadth_per_topmast_length", PER, C05, "top breadth = 1/3 topmast"),
    "MARS_DL_SZER": ("top_length_per_breadth", PER, C05, "top length = 3/4 breadth"),
    "BUKSZPRYT_WZNIOS": ("bowsprit_steeve_deg", SEC, C05, "30° (Steel 1794 gives 36°)"),
    "BUKSZPRYT_NAD_DZIOBNICA": ("bowsprit_above_stem_head_m", INF, C05, "underside of the bowsprit over the stem head"),
    "SNOW_MASZT_SR": ("snow_mast_diameter_per_main_mast", SEC, C05, ""),
    "SNOW_ODSTEP": ("snow_mast_abaft_main_mast_m", INF, C05, "radius of main mast 0.25 + snow mast 0.09 + gaff jaws"),
    "REJA_POD_MARSEM": ("lower_yard_below_top_m", SEC, C05, "0.5–1 m below the trestle trees"),
    "MARSREJA_POD_SALINGIEM": ("topsail_yard_hoisted_below_crosstrees_m", INF, C05, "working position, sail set"),
    "BRAMREJA_POD_TOPEM": ("topgallant_yard_hoisted_below_truck_m", INF, C05, "working position, sail set"),
    "Z_BOMEM": ("has_boom", SEC, C07, "false: gaff sail without boom, brailed to the mast (1700–1720)"),
    "BOM_NAD_POKLADEM": ("boom_jaws_above_main_deck_m", INF, C05, ""),
    "GAFEL_KAT": ("gaff_angle_above_horizontal_deg", INF, C05, "not given in the sources"),
    # ---- olinowanie stałe
    "WANTY": ("lower_shrouds_per_side", SEC, C06, "main 6, fore 5"),
    "WANTY_STENGOWE": ("topmast_shrouds_per_side", SEC, C06, ""),
    "WANTY_BRAMSTENGOWE": ("topgallant_shrouds_per_side", SEC, C06, ""),
    "PADUNY_STENGOWE": ("topmast_backstays_per_side", SEC, C06, ""),
    "PADUNY_BRAM": ("topgallant_backstays_per_side", SEC, C06, ""),
    "D_GROTSZTAG": ("main_stay_diameter_m", SEC, C06, ""),
    "D_FOKSZTAG": ("fore_stay_diameter_m", SEC, C06, ""),
    "D_WANTY_GROT": ("main_shroud_diameter_m", SEC, C06, ""),
    "D_WANTY_FOK": ("fore_shroud_diameter_m", SEC, C06, ""),
    "D_TALREP": ("lanyard_diameter_m", SEC, C06, ""),
    "D_WYBLINKA": ("ratline_diameter_m", SEC, C06, ""),
    "D_PODWANTKA": ("futtock_shroud_diameter_m", SEC, C06, ""),
    "D_WANTY_STENG": ("topmast_shroud_diameter_m", SEC, C06, ""),
    "D_TALREP_STENG": ("topmast_lanyard_diameter_m", SEC, C06, ""),
    "D_PADUN_STENG": ("topmast_backstay_diameter_m", SEC, C06, ""),
    "D_SZTAG_STENG": ("topmast_stay_diameter_m", SEC, C06, ""),
    "D_WANTY_BRAM": ("topgallant_shroud_diameter_m", SEC, C06, ""),
    "D_PADUN_BRAM": ("topgallant_backstay_diameter_m", SEC, C06, ""),
    "D_SZTAG_BRAM": ("topgallant_stay_diameter_m", SEC, C06, ""),
    "D_WATERSZTAG": ("bobstay_diameter_m", SEC, C06, ""),
    "D_WANTY_BUKSZ": ("bowsprit_shroud_diameter_m", SEC, C06, ""),
    "D_WIAZANIE": ("gammoning_diameter_m", SEC, C06, ""),
    "D_SZTAG_KLIWRA": ("jib_stay_diameter_m", SEC, C06, ""),
    "D_PERTA": ("footrope_diameter_m", SEC, C06, ""),
    "D_STRZEMIE": ("stirrup_diameter_m", SEC, C06, ""),
    "WYBLINKI_ROZSTAW": ("ratline_spacing_m", SEC, C06, ""),
    "WYBLINKI_ZWIS": ("ratline_sag_ratio", SEC, C06, ""),
    "JUFERS_Z_OBWODU": ("deadeye_diameter_per_shroud_circumference", SEC, C06, "deadeye diameter = 1.5 × circumference"),
    "JUFERS_ODSTEP": ("deadeye_gap_per_diameter", SEC, C06, "upper to lower deadeye centres, in deadeye diameters"),
    "PERTA_ZWIS": ("footrope_sag_m", SEC, C06, "lower yards"),
    "STRZEMIONA": ("stirrups_per_side_lower_yard", SEC, C06, ""),
    "STRZEMIONA_MARS": ("stirrups_per_side_topsail_yard", SEC, C06, ""),
    "WIAZANIE_ZWOJE": ("gammoning_turns", SEC, C06, ""),
    "WATERSZTAGI": ("bobstays", SEC, C06, ""),
    "WANTY_BUKSZPRYTU": ("bowsprit_shrouds_per_side", SEC, C06, ""),
    "LAWA_SZER": ("channel_width_m", SEC, C06, "0.40–0.50"),
    "LAWA_GR": ("channel_thickness_m", SEC, C06, "0.08–0.10"),
    "JUFERSY_ROZSTAW": ("deadeye_spacing_on_channel_m", INF, C06, "deadeye diameter + clearance between lanyards"),
    "D_MIN_GLB": ("min_rope_diameter_in_glb_m", REF, C08, "lower limit of rope thickness in the game file"),
    # ---- układ pokładu
    "KABESTAN": ("capstan", REF, C09, "2.35 m forward of the main mast (bars clear the ladder route)"),
    "POMPY": ("pumps", REF, C09, "beside the ladder; brake swing ±25°"),
    "LUK_GLOWNY": ("main_hatch", SEC, C04, "2.4 × 1.8 × 0.25"),
    "LUK_DZIOBOWY": ("fore_hatch", REF, C04, "smaller than in the research notes (space)"),
    "LODZ": ("boat", INF, C09, "yawl 5.0 × 1.7"),
    "KOMIN": ("galley_chimney", REF, C09, "on the centreline"),
    "NAGIELBANK": ("fife_rail", REF, C07, "1.2 × 1.2 (research notes 1.4 × 1.4)"),
    "KOLKOWNICE": ("pin_rails_s_ranges_m", INF, C07, "pin rails along the bulwark (likely anachronism for 1710)"),
    "KOLKOWNICA_H": ("pin_rail_height_above_deck_m", INF, C07, ""),
    "SZAFKA_KOMPASOWA": ("binnacle", SEC, C09, "just forward of the wheel"),
    "STEROWANIE": ("steering", REF, C09, "default drive: wheel (c. 1703–1710); deck tiller kept as second variant"),
    "RUMPEL": ("deck_tiller", SEC, C09, "tiller variant"),
    "KOLO": ("steering_wheel", INF, C09, "wheel variant: wheel Ø 1.40, drum Ø 0.30, tiller 3.0 m below deck"),
    "DZWON": ("bell", REF, C09, "at the quarterdeck break (no forecastle in the model)"),
    "ZEJSCIOWKA": ("companion", INF, C04, ""),
    "KOJCE": ("hen_coops", INF, C09, "one per side (mirrored)"),
    "SKRZYNIA_BRONI": ("arms_chest", INF, C09, ""),
    "BECZKA_WODY": ("water_cask", INF, C09, ""),
    "DZIALA": ("guns", SEC, C09, "6-pounder barrels 2.0 m on truck carriages"),
    "DZIALKA_RELINGOWE": ("swivel_guns_s_m", INF, C09, "s on the rails, both sides"),
    # ---- warianty i zestaw
    "nazwa": ("name", REF, C01, ""), "snow": ("snow_rig", SEC, C01, "true: snow (trysail mast abaft the main mast)"),
    "schemat": ("paint_scheme", REF, C04, "a: period (white stuff, oiled sides, yellow and black); b: black hull"),
    "zagle_postawione": ("sails_set", REF, C08, "false: all sails furled, ship at anchor"),
    "WNETRZE_CZERWONE": ("bulwarks_red_inboard", INF, C04, "variant for scheme a (red ochre inboard unconfirmed)"),
    # ---- stałe z modułów
    "GALION": ("head", INF, C04, "shape of the head: our interpretation of the descriptions"),
    "KOLANO": ("knee_of_head_z_offset_m", INF, C04, "(z, distance forward of the stem face)"),
    "KOLANO_GR": ("knee_of_head_thickness_m", INF, C04, ""),
    "OKNA_X": ("stern_window_centres_x_m", SEC, C04, "4 windows (2–4 in the sources)"),
    "OKNO": ("stern_window_width_height_m", INF, C04, ""),
    "OKNO_Z": ("stern_window_centre_z_m", INF, C04, ""),
    "KOTBELKA_S": ("cathead_s_m", SEC, C04, ""),
    "KOTBELKA_WYST": ("cathead_projection_m", SEC, C04, ""),
    "KOTBELKA_PRZEKR": ("cathead_section_m", SEC, C04, ""),
    "KLUZA_S": ("hawse_hole_s_m", INF, C04, ""), "KLUZA_Z": ("hawse_hole_z_m", INF, C04, ""),
    "KLUZA_R": ("hawse_hole_radius_m", INF, C04, ""),
    "STER_KAT": ("rudder_angle_deg", SEC, C09, "helm hard over each side"),
    "STER_CZOPY": ("pintle_straps_z_m", SEC, C04, "5 pairs (4–5 in the sources)"),
    "TRZON_R": ("rudder_stock_radius_bottom_top_m", INF, C04, ""),
    "RAD": ("furled_sail_radii_m", INF, C08, "furled roll radius at the slings / at the yardarm, by yard kind"),
    "R_POSTACI": ("walker_radius_m", REF, C04, "walking test"), "WZROST": ("walker_height_m", REF, C04, "walking test"),
    "KROK_SIATKI": ("walk_grid_step_m", REF, C04, "walking test"),
    "CAL_NA_JARD": ("inch_per_yard_ratio", PER, C05, "one inch of diameter per yard of length"),
    "LINIE_PRZESUNIECIE": ("research_station_offset_m", REF, C02, "s = z_df + 1.96"),
}

SPAR_PL = {"GROT": "main_mast", "FOK": "fore_mast", "GROT_STENGA": "main_topmast", "FOK_STENGA": "fore_topmast",
           "GROT_BRAM": "main_topgallant_mast", "FOK_BRAM": "fore_topgallant_mast", "BUKSZPRYT": "bowsprit",
           "BOMSTENGA": "jib_boom", "GROTREJA": "main_yard", "FOKREJA": "fore_yard", "GROTMARSREJA": "main_topsail_yard",
           "FOKMARSREJA": "fore_topsail_yard", "GROTBRAMREJA": "main_topgallant_yard",
           "FOKBRAMREJA": "fore_topgallant_yard", "BLINDAREJA": "spritsail_yard", "BOM": "boom", "GAFEL": "gaff"}
for _k, _e in SPAR_PL.items():
    _c = INF if _k in ("BOM", "GAFEL") else PER
    PARAM[_k] = (_e + "_length_m", _c, C05, "Steel's rules (1794) applied to the hull" if _c == PER else "chosen in the range")
    PARAM[_k + "_SR"] = (_e + "_diameter_m", _c, C05, "largest diameter")
    if _k in ("GROT", "FOK", "GROT_STENGA", "FOK_STENGA"):
        PARAM[_k + "_TOP"] = (_e + "_head_length_m", PER, C05, "masthead: 5 in per yard (lower), 4 in per yard (topmast)")

PODKLUCZE = {
    "s": "s_m", "x": "x_m", "h": "height_m", "r": "radius_m", "a": "side_m", "s0": "s_aft_m", "s1": "s_fore_m",
    "pol_x": "half_width_m", "r_glowica": "drumhead_radius_m", "r_beben": "barrel_radius_m", "dragi": "bars_count",
    "r_draga": "bar_reach_radius_m", "h_draga": "bar_height_m", "dzwignia": "brake_length_m", "wahanie": "swing_deg",
    "stan": "state", "szer": "width_m", "glebokosc": "depth_m", "pol": "half_size_m", "kolki_co": "pin_spacing_m",
    "gl": "depth_m", "naped": "drive", "dl": "length_m", "przekr": "section_m", "kat": "angle_deg",
    "h_glowicy": "height_at_head_m", "h_konca": "height_at_end_m", "D": "diameter_m", "szprychy": "spokes_count",
    "os_h": "axle_height_above_deck_m", "D_beben": "drum_diameter_m", "L_beben": "drum_length_m",
    "zwoje": "rope_turns_on_drum", "d_sterliny": "tiller_rope_diameter_m", "rumpel_dl": "tiller_length_m",
    "rumpel_pod": "tiller_below_deck_m", "furty": "ports", "lufa": "barrel_length_m", "lawa_dl": "carriage_length_m",
    "lawa_szer": "carriage_width_m", "os_lufy": "trunnion_height_m", "odrzut": "recoil_m",
    "bez_dziala": "ports_without_gun_s_m", "z_linami": "guns_with_tackle_s_m", "wariant": "variant",
    "grot": "main", "fok": "fore", "tex": "texture_set", "nrm": "normal_map_set", "rm": "roughness_metal_set",
    "kolor": "colour_multiplier_srgb", "kafel": "tile_m", "szorstkosc": "roughness", "id": "cc0_texture_id",
    "deski": "planks", "szer_deski": "plank_width_m", "szarosc": "greyscale", "kontrast": "contrast",
    "sloje": "grain", "wybor": "use_cc0", "kolor_plotna": "canvas_colour",
}
WARTOSCI = {"FURTY_S": "gunport_centres_s_m", "kolo": "wheel", "rumpel": "tiller", "za_rufa": "towed_astern",
            "wlasne": "own_mesh", "bryg": "reference_model", "a": "a", "b": "b",
            "burta": "side", "farba": "paint", "poklad": "deck", "drewno": "wood", "zelazo": "iron", "lina": "rope",
            "plotno": "canvas", "okno": "window"}


def _strona(s):
    return STRONA.get(s, s)


def en(nazwa):
    """Polska nazwa obiektu / węzła / klucza → angielska (None, gdy brak w słowniku)."""
    if nazwa is None:
        return None
    if nazwa in SLOWA:
        return SLOWA[nazwa]
    if nazwa in LINY:
        return LINY[nazwa]
    for wz, szablon in BAZY:
        m = re.match(wz, nazwa)
        if not m:
            continue
        g = m.groupdict()
        out = {}
        for k, v in g.items():
            if k == "S":
                out[k] = _strona(v)
            elif k == "N":
                out[k] = v
            elif k in ("A", "G", "B", "O", "M"):
                e = en(v)
                if e is None:
                    return None
                out[k] = e
        return szablon.format(**out)
    return None


def en_wart(v):
    """Wartość tekstowa parametru → angielska."""
    if isinstance(v, str):
        return WARTOSCI.get(v) or en(v) or v
    return v


# klucze plików generatora (liny.json, bryg_poklad.json, extras GLB, parametry.json) → klucze publiczne
KLUCZE = {
    # liny.json
    "grupa": "group", "srednica_m": "diameter_m", "material": "material", "rodzic": "parent", "dlugosc_m": "length_m",
    "od": "from", "do": "to", "od_obiekt": "from_object", "do_obiekt": "to_object", "wariant": "variant",
    "od_lokalnie": "from_local", "do_lokalnie": "to_local", "przez": "via",
    # extras GLB
    "czynnosc": "activity", "kat_otwarcia_deg": "open_angle_deg", "lina_dynamiczna": "dynamic", "obiekt": "object",
    "obrot_ciagly": "continuous_rotation", "odrzut_m": "recoil_m", "opis": "description", "os_ruchu": "motion_axis",
    "osobny_wezel": "separate_node", "otwarta": "open", "przelozenie_obroty_na_35deg": "wheel_turns_for_35deg",
    "przelozenie_wzor": "gear_ratio_formula", "wezly": "nodes", "widoczny_domyslnie": "visible_by_default",
    "wodnica_lodzi_m": "boat_waterline_m", "wysokosc_rak": "hand_height_m", "pomocniczy": "helper",
    "pomocniczy_opis": "helper_note",
    "wysokosc_robocza_dz_m": "working_height_dz_m", "zakres_brasowania_deg": "brace_range_deg",
    "zakres_brasowania_podniesiona_deg": "brace_range_hoisted_deg", "zakres_deg": "range_deg",
    "zakres_deg_podniesiona": "range_deg_hoisted", "zakres_m": "range_m", "stan": "state",
    # bryg_poklad.json
    "uklad": "coordinate_system", "osie": "axes", "postac": "walker", "promien": "radius_m", "wzrost": "height_m",
    "krok_siatki_testu": "test_grid_step_m", "uwagi": "notes", "powierzchnie": "surfaces", "nazwa": "name",
    "poziom": "level", "wielokat": "polygon_x_s", "wysokosc": "height", "siatka": "grid", "schody": "stairs",
    "typ": "type", "poczatek": "start", "koniec": "end", "szerokosc": "width_m", "stopnie": "steps",
    "wznios": "rise_m", "glebokosc_stopnia": "tread_m", "wspinaczka": "climbs", "punkty": "points",
    "szczeble_co": "rung_spacing_m", "przejscia": "passages", "przeszkody": "obstacles", "chodzic": "walkable",
    "prog": "step_height_m", "srodek": "centre_x_s", "dl_z": "length_s_m", "szer_x": "width_x_m", "obrot": "rotation_deg",
    "burta": "side_edge", "reling_y": "rail_z", "stanowiska": "stations", "stopy": "feet", "patrzy": "facing",
    "yaw_rad": "yaw_rad", "os": "axis", "zakres": "range", "liny": "ropes", "obiekty_ruchome": "moving_parts",
    "pivot": "pivot", "kontrola": "check", "siatka_chodzenia": "walk_grid", "stanowiska_liczba": "station_counts",
    "wzor": "formula", "os_z_y": "centreline_s_z", "stala": "constant_z_m", "otwor": "hole", "z0": "s_aft",
    "z1": "s_fore", "krok": "step_m", "wiersze": "rows", "x0": "x0_m", "nx": "nx", "nz": "ns", "y": "z",
    "krawedz_pokladu_glownego": "main_deck_edge", "krawedz_pokladu_rufowego": "quarterdeck_edge", "r": "radius_m",
}

# litery i słowa, po których poznaje się polski tekst (kontrola)
POLSKIE_ZNAKI = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
