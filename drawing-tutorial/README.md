# How to draw the ship: a step-by-step drawing tutorial

A printable booklet for young artists (about 12 to 16 years old) that teaches how to draw
our snow, the reference ship of this repository (a small two-masted naval vessel of about 1710),
from simple shapes to a finished, shaded drawing.

| File | What it is |
|---|---|
| `how-to-draw-the-ship-en.pdf` | the booklet in English (A4 portrait, 18 pages) |
| `how-to-draw-the-ship-pl.pdf` | the same booklet in Polish |
| `steps/en/`, `steps/pl/` | every step picture as a PNG (labels in the pictures are translated) |
| `src/` | the scripts that make all of it |

The booklet contains: a cover, what you need and how to use the booklet, a labelled
"meet the ship" picture, three step sequences (from the side: easy; from the bow: medium;
from the stern: harder) with 8 steps each, a bonus step with set sails for every view,
common mistakes, fun facts with sources, and a tracing / colouring page.

In every step picture the **new lines are black**, lines from earlier steps are **light blue**,
and construction lines (to be drawn lightly and erased) are **orange and dashed**.
The pages also work when printed in black and white.

## How the pictures were made

No picture is drawn by hand or taken from elsewhere. Everything comes from the 3D model of the
reference ship:

1. `src/render_lines.py` runs inside Blender. For each view it places a level camera
   (eye height 3 m, 100 mm lens for the side view, 50 mm for the two oblique views) and renders
   the outlines with **Freestyle** (silhouettes, borders and sharp creases; thicker lines for
   outlines, thinner for details) on a transparent background. Every step is rendered twice,
   with the same hidden-line removal: once with only the new group of parts, once with the
   older groups. The hull is cut at the waterline, the ratlines are thinned to every third rung,
   and running rigging is left out so the ropes do not merge into a dark mass. The square yards are
   swung (braced) by 30 degrees so they show up even in the side view. For the bonus step the script
   adds simple curved sheets spanned between the yards as set sails. It also renders a mirrored
   camera for the reflection, a grey shaded render for the hatching, and writes the construction
   shapes as 2D data: horizon and vanishing points, the proportion grid on the centre plane,
   hull blocks, mast and yard axes, shroud triangles, the gunport line and the sail outlines,
   all computed by projecting the model's own bounding boxes and parts into the camera.
2. `src/compose_steps.py` (Pillow + numpy) colours and stacks those layers into the step pictures,
   draws the construction lines, turns the shaded render into pencil-like hatching and the
   mirrored render into a broken-up reflection.
3. `src/build_pdf.py` lays out the pages at 240 dpi and writes the PDFs (pages are stored as
   compressed images). Texts are in `src/texts.py`; fonts are taken from the operating system.

## Rebuilding

You need Blender (made with 5.2) and Python 3 with Pillow and numpy. Work on a copy of the model file;
the scripts never save it.

```
blender -b --factory-startup path/to/ship_copy.blend --python src/render_lines.py -- --out build/layers --res 2400x1333
python src/compose_steps.py --layers build/layers --out steps --extra build/extra --lang en,pl --width 1800
python src/build_pdf.py --steps steps --extra build/extra --out . --pages build/pages --lang en,pl
```

The render takes a while (Freestyle, about 60 images). `build/` holds only intermediate files.

## Facts and sources

All numbers in the fun facts come from the chapters of the construction guide in `../docs/`;
the sources listed on the facts page are the ones those chapters cite.

## Licence

MIT, like the rest of the repository (see `../LICENSE`).

---

## Po polsku w skrócie

Książeczka do wydruku (A4, 18 stron, wersja angielska i polska) uczy krok po kroku rysować naszego
snow, statek wzorcowy z tego repozytorium, w trzech ujęciach: z boku (łatwe), od dziobu (średnie)
i od rufy (trudniejsze). Każde ujęcie ma 8 kroków i krok dodatkowy z postawionymi żaglami.
Na obrazkach nowe linie są czarne, wcześniejsze jasnoniebieskie, a pomocnicze pomarańczowe
i kreskowane. Wszystkie rysunki wygenerowały skrypty z modelu 3D (kontury Freestyle w Blenderze,
linie pomocnicze liczone z rzutu brył modelu na kamerę), nic nie jest rysowane ręcznie.
Jak odtworzyć: trzy polecenia z sekcji „Rebuilding”. Licencja MIT.
