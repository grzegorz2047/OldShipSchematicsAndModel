# Bryg Mewa

Osobna, uproszczona rekonstrukcja modelu z SailerTales, przygotowana z myślą o
stojącej postaci gracza. Wymiary: 29 × 8.6 m.
Wnętrza i układ przejść są decyzjami do gry. Adapter sterowania postacią i
integracja z SailerTales pozostają do wykonania.

![Model](previews/hero.jpg)

![Pokład z usuniętym w podglądzie takielunkiem i dachem kajuty](previews/deck.jpg)

Pliki:

- [Model wizualny](model/ship.glb)
- [Osobne kolizje](model/collision.glb)
- [Scena Blender](model/ship.blend)
- [Trasy i parametry postaci](navigation.json)
- [Raport kontroli eksportów](validation.json)
- [Odtwarzanie modelu i zakres weryfikacji](../common/README.md)

Źródło: [SailerTales, commit ea77e56](https://github.com/grzegorz2047/SailerTales/tree/ea77e560ba4668c9dda55433813addbdb2f50176).

- `src/ship/vessels.js`
- `src/ship/ship.js`

Ograniczenia i odstępstwa:

- Wymiary główne z profilu BRIG. Wnętrza i układ przejść to rekonstrukcja do gry.
- Nowy model wymaga adaptera w SailerTales; nie zastępuje automatycznie brygu Tripo.

Raport dotyczy tras zapisanych w `navigation.json` dla kapsuły o promieniu
0,38 m i wysokości 1,85 m. Weryfikator ponownie importuje oba dostarczone GLB,
kontroluje podłoże, nachylenie i miejsce na postać oraz szuka przecięć żagli z
olinowaniem i drzewcami w zapisanym ustawieniu. SHA-256 wiąże wynik z plikami
modelu, specyfikacją, trasami i skryptami. Test nie zastępuje sprawdzenia
kontrolera postaci w działającej grze.
