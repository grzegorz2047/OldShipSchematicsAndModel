"""Plansza zbiorcza renderów (PIL): siatka miniatur z podpisami → rendery/plansza.png.

    python blender/plansza.py build/rendery
"""
import os
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass

from PIL import Image, ImageDraw, ImageFont

d = sys.argv[1]
KOL = [("z_glb_burta_z_wody_a", "Z GLB: burta z wody"), ("z_glb_oczy_ku_dziobowi_a", "Z GLB: pokład z oczu"),
       ("z_glb_rufa_z_wody_a", "Z GLB: rufa"), ("z_glb_detal_kolo_oczy_sternika_a", "Z GLB: koło sterowe"),
       ("burta_z_wody_a", "burta z wody, 12 m (schemat a)"), ("burta_z_wody_b", "burta z wody (schemat b)"),
       ("rufa_z_wody_a", "rufa z wody (a)"), ("rufa_z_wody_b", "rufa z wody (b)"),
       ("dziob_z_wody_a", "dziób z wody (a)"), ("dziob_z_wody_b", "dziób z wody (b)"),
       ("bok_calosc_a", "całość z boku (a)"), ("bok_calosc_b", "całość z boku (b)"),
       ("z_gory_a", "z góry"), ("poklad_z_rufy_a", "pokład z rufy"),
       ("oczy_ku_dziobowi_a", "oczy 1,6 m ku dziobowi"), ("oczy_ku_rufie_a", "oczy 1,6 m ku rufie"),
       ("deski_zblizenie_a", "deski z 1,5 m"), ("dzialo_zblizenie_a", "działo"),
       ("kabestan_zblizenie_a", "kabestan"), ("lawa_wantowa_a", "ława wantowa z jufersami"),
       ("mars_z_gory_a", "mars z góry"), ("pawez_okna_a", "pawęż z oknami"), ("galion_a", "galion"),
       ("manekin_kabestan_a", "manekin 1,75 m przy kabestanie"), ("manekin_dzialo_a", "manekin przy dziale"),
       ("dzialo_polyhaven_a", "wariant działa CC0 (Poly Haven)")]
items = [(os.path.join(d, n + ".png"), c) for n, c in KOL if os.path.exists(os.path.join(d, n + ".png"))]
W, H = 640, 360
cols = 4
rows = (len(items) + cols - 1) // cols
sheet = Image.new("RGB", (cols * W, rows * (H + 28)), (25, 25, 28))
dr = ImageDraw.Draw(sheet)
try:
    f = ImageFont.truetype("arial.ttf", 18)
except Exception:
    f = ImageFont.load_default()
for k, (p, c) in enumerate(items):
    im = Image.open(p).convert("RGB").resize((W, H))
    x, y = (k % cols) * W, (k // cols) * (H + 28)
    sheet.paste(im, (x, y))
    dr.text((x + 8, y + H + 4), c, fill=(235, 235, 235), font=f)
out = os.path.join(d, "plansza.png")
sheet.save(out)
print("PLANSZA", out, sheet.size, len(items))
