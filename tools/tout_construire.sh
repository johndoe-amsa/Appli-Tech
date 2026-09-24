#!/bin/sh
# Reconstruit la famille Appli-Tec entiere, dans l'ordre.
#
# L'ordre compte : le crenage puis le hinting sont ecrits DANS les fichiers
# produits par les deux generateurs. Relancer un generateur seul efface les
# deux pour la graisse concernee - il faut alors repasser appliquer_crenage.py
# et appliquer_hinting.py dessus.
set -e
cd "$(dirname "$0")/.."

echo "== romains =="
python3 tools/build.py -0.3333 300 Light
python3 tools/build.py  0.0    400 Regular
python3 tools/build.py  0.3333 500 Medium
python3 tools/build.py  1.0    700 Bold
python3 tools/build.py  1.3333 800 Heavy

echo "== italiques =="
python3 tools/build_italic.py -0.3333 300 "Light Italic"
python3 tools/build_italic.py  0.0    400 "Italic"
python3 tools/build_italic.py  0.3333 500 "Medium Italic"
python3 tools/build_italic.py  1.0    700 "Bold Italic"
python3 tools/build_italic.py  1.3333 800 "Heavy Italic"

echo "== romains condenses =="
python3 tools/build.py -0.3333 300 Light   Condensed
python3 tools/build.py  0.0    400 Regular Condensed
python3 tools/build.py  0.3333 500 Medium  Condensed
python3 tools/build.py  1.0    700 Bold    Condensed
python3 tools/build.py  1.3333 800 Heavy   Condensed

echo "== crenage =="
python3 tools/appliquer_crenage.py fonts/ttf/*.ttf

echo "== hinting (affichage ecran) =="
python3 tools/appliquer_hinting.py fonts/ttf/*.ttf

echo "== verification =="
python3 tools/verifier.py

echo "== formats web =="
python3 - <<'PY'
from fontTools.ttLib import TTFont
import glob, os
for f in sorted(glob.glob("fonts/ttf/*.ttf")):
    t = TTFont(f); t.flavor = "woff2"
    t.save("fonts/woff2/" + os.path.basename(f).replace(".ttf", ".woff2"))
print(f"  {len(glob.glob('fonts/woff2/Appli-Tec-*.woff2'))} fichiers")
PY
