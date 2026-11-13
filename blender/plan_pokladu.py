"""Rzut pokładu z góry z danymi chodzenia (zwykły Python, PIL): tło – render ortogonalny z Blendera (jeśli jest),
na nim strefy, w których może stanąć postać (zielone), przeszkody (czerwone obrysy z nazwami), schody,
wejścia na wanty i stanowiska (punkty z kierunkiem patrzenia i podpisem).

    python blender/plan_pokladu.py build
"""
import json
import math
import os
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass

from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]
J = json.load(open(os.path.join(out, "bryg_poklad.json"), encoding="utf-8"))
bg_path = os.path.join(out, "rendery", "_plan_tlo.png")
# skala i obszar: z (wzdłuż) od −16 do +16 → szerokość obrazu, x od −5 do +5 → wysokość
PX = 75.0
Z0, Z1, X0, X1 = -16.0, 16.0, -5.333, 5.333
W, H = int((Z1 - Z0) * PX), int((X1 - X0) * PX)
if os.path.exists(bg_path):
    img = Image.open(bg_path).convert("RGB").resize((W, H))
    img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.35)
else:
    img = Image.new("RGB", (W, H), (235, 235, 230))
d = ImageDraw.Draw(img, "RGBA")
try:
    font = ImageFont.truetype("arial.ttf", 13)
    fbig = ImageFont.truetype("arialbd.ttf", 22)
except Exception:
    font = ImageFont.load_default()
    fbig = font


def px(x, z):
    # dziób w prawo, lewa burta (x+) u góry
    return ((z - Z0) * PX, (X1 - x) * PX)


for nm, S in J["siatka_chodzenia"].items():
    k = S["krok"]
    for i, row in enumerate(S["wiersze"]):
        z = S["z0"] + i * k
        for j, c in enumerate(row):
            if c == "1":
                x = S["x0"] + j * k
                a = px(x + k / 2, z - k / 2)
                b = px(x - k / 2, z + k / 2)
                d.rectangle([a, b], fill=(40, 190, 60, 70) if nm == "glowny" else (40, 120, 220, 70))
for p in J["powierzchnie"]:
    if "wielokat" in p:
        pts = [px(x, z) for (x, z) in p["wielokat"]]
        col = (20, 20, 20, 255) if p["nazwa"].startswith("poklad") else (90, 90, 90, 120)
        d.line(pts + [pts[0]], fill=col, width=2 if p["nazwa"].startswith("poklad") else 1)
for o in J["przeszkody"]:
    col = (200, 30, 30, 255) if not o["chodzic"] else (230, 150, 0, 255)
    if o["typ"] == "kolo":
        x, z = o["srodek"]
        r = o["r"] * PX
        c = px(x, z)
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=col, width=2)
    else:
        x, z = o["srodek"]
        L, Wd, rot = o["dl_z"], o["szer_x"], o["obrot"]
        cs, sn = math.cos(rot), math.sin(rot)
        corners = []
        for (u, v) in ((-L / 2, -Wd / 2), (L / 2, -Wd / 2), (L / 2, Wd / 2), (-L / 2, Wd / 2)):
            corners.append(px(x + v * cs + u * sn, z + u * cs - v * sn))
        d.polygon(corners, outline=col, width=2)
    if o["nazwa"] not in ("kolkownica", "lodz_legar"):
        c = px(*o["srodek"])
        d.text((c[0] + 3, c[1] - 7), o["nazwa"], fill=(140, 0, 0, 255), font=font)
for s in J["schody"]:
    a = px(s["poczatek"][0] - s["szerokosc"] / 2, s["poczatek"][2])
    b = px(s["koniec"][0] + s["szerokosc"] / 2, s["koniec"][2])
    d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], outline=(120, 0, 160, 255), width=3)
    d.text((b[0] + 4, b[1] + 2), "schody %d × %.2f m" % (s["stopnie"], s["wznios"]), fill=(120, 0, 160, 255), font=font)
for w in J["wspinaczka"]:
    pts = [px(p[0], p[2]) for p in w["punkty"][:3]]
    d.line(pts, fill=(160, 0, 160, 255), width=3)
seen = {}
for t in J["stanowiska"]:
    x, y, z = t["stopy"]
    if t["czynnosc"] in ("nok_rei", "mars") or abs(x) > 5:
        continue
    c = px(x, z)
    col = (20, 60, 200, 255) if not t["czynnosc"].startswith("dzialo") else (0, 140, 160, 255)
    d.ellipse([c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5], fill=col)
    fx, fz = t["patrzy"][0], t["patrzy"][2]
    e = px(x + fx * 0.35, z + fz * 0.35)
    d.line([c, e], fill=col, width=2)
    key = t["czynnosc"]
    if not key.startswith("dzialo") and key not in ("furta",):
        d.text((c[0] + 6, c[1] + 2), t["nazwa"].replace("stan_", ""), fill=(10, 30, 120, 255), font=font)
k = J["kontrola"]
txt = ("Rzut pokładu (dziób w prawo, lewa burta u góry; siatka 0,25 m). Zielone/niebieskie: tu może stanąć środek postaci "
       "r 0,3 m (pokład główny/rufowy). Czerwone: przeszkody, pomarańczowe: do przejścia (kraty, lina). Punkty: stanowiska "
       "(turkus – obsługa dział). Dojście do wszystkich: %s; przejścia < 0,8 m: %d; kolizja drągów kabestanu: %s."
       % ("TAK" if k["dojscie_wszystkie"] else "NIE", len(k["przejscia_ponizej_08"]), "TAK" if k["kabestan_kolizja"] else "NIE"))
d.rectangle([0, H - 30, W, H], fill=(255, 255, 255, 220))
d.text((10, H - 24), txt, fill=(0, 0, 0, 255), font=font)
p = os.path.join(out, "rendery", "plan_pokladu.png")
img.save(p)
print("PLAN", p, img.size)
