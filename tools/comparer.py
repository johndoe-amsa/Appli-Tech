"""
Planche de controle avant / apres, glyphe par glyphe.

Compare les polices de fonts/ttf/ a celles d'une version anterieure du depot
(par defaut le dernier commit) et produit comparaison.html : pour chaque
graisse, les glyphes dont le dessin a change, classes du plus touche au moins
touche, avec le dessin d'avant, celui d'apres, et les deux superposes.

    python3 tools/comparer.py              # contre le dernier commit (HEAD)
    python3 tools/comparer.py HEAD~3       # contre une version plus ancienne
    python3 tools/comparer.py 9a46589      # contre un commit precis

L'ecart affiche est l'ecart moyen du contour, en unites (1 000 par cadratin) :
la surface qui differe entre les deux dessins, rapportee a la longueur du
contour. La vue "superpose" colorie cette surface. Un glyphe dont seuls
les points ont ete renumerotes, sans que le trace bouge, n'apparait pas.
"""
import sys, os, io, glob, json, base64, subprocess, datetime

import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.perimeterPen import PerimeterPen

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Ecart moyen (surface differente / longueur du contour), en unites sur 1 000
# par cadratin. En-deca de 0,1 unite, c'est le bruit de la conversion des
# courbes en quadratiques, invisible a toute taille d'impression.
SEUIL = 0.1


def _ancienne(ref, chemin):
    rel = os.path.relpath(chemin, RACINE)
    try:
        data = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=RACINE,
                              capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None
    return TTFont(io.BytesIO(data))


def _chemin(gs, nom):
    """Trace du glyphe, simplifie : sans cette etape, deux dessins identiques
    mais dont un contour demarre ailleurs donnent un ecart fantome."""
    p = pathops.Path()
    gs[nom].draw(p.getPen(glyphSet=gs))
    try:
        return pathops.simplify(p, clockwise=p.clockwise)
    except Exception:
        return p


def _difference(a, b):
    """Surface qui differe entre deux traces (ajoutee + retiree), et son dessin."""
    try:
        x = pathops.op(a, b, pathops.PathOp.XOR)
    except Exception:
        return float("inf"), ""
    pen = SVGPathPen(None, ntos=lambda v: str(int(round(v))))
    x.draw(pen)
    return abs(x.area), pen.getCommands()


def _perimetre(gs, nom):
    pen = PerimeterPen(gs, tolerance=0.5)
    gs[nom].draw(pen)
    return pen.value


def _svg(gs, nom):
    pen = SVGPathPen(gs, ntos=lambda v: str(int(round(v))))
    gs[nom].draw(pen)
    return pen.getCommands()


def _boite(*chemins):
    xs, ys = [], []
    for p in chemins:
        b = p.bounds
        if b and b[2] > b[0]:
            xs += [b[0], b[2]]; ys += [b[1], b[3]]
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def comparer(ref):
    styles = []
    for f in sorted(glob.glob(os.path.join(RACINE, "fonts/ttf/*.ttf"))):
        nom_fichier = os.path.basename(f)[:-4].replace("Appli-Tec-", "")
        apres = TTFont(f)
        avant = _ancienne(ref, f)
        if avant is None:
            styles.append({"style": nom_fichier, "nouveau": True, "glyphes": []})
            continue
        ga, gb = avant.getGlyphSet(), apres.getGlyphSet()
        cmap = {v: k for k, v in apres.getBestCmap().items()}
        changes = []
        for g in apres.getGlyphOrder():
            if g not in ga:
                continue
            pa, pb = _chemin(ga, g), _chemin(gb, g)
            d, diff = _difference(pa, pb)
            moyen = d / max(_perimetre(gb, g), 1.0)
            la, lb = avant["hmtx"][g][0], apres["hmtx"][g][0]
            if moyen < SEUIL and la == lb:
                continue
            boite = _boite(pa, pb)
            if boite is None:
                continue
            u = cmap.get(g)
            changes.append({
                "nom": g,
                "car": chr(u) if u and u > 32 else "",
                "u": f"U+{u:04X}" if u else "",
                "ecart": round(moyen, 2) if d != float("inf") else -1,
                "diff": diff,
                "chasse": [la, lb],
                "avant": _svg(ga, g),
                "apres": _svg(gb, g),
                "boite": [round(v) for v in boite],
            })
        changes.sort(key=lambda c: -c["ecart"] if c["ecart"] >= 0 else -1e12)
        styles.append({"style": nom_fichier, "glyphes": changes})
    return styles


def _commit(ref):
    try:
        return subprocess.run(["git", "log", "-1", "--format=%h %s", ref],
                              cwd=RACINE, capture_output=True, text=True,
                              check=True).stdout.strip()
    except subprocess.CalledProcessError:
        return ref


GABARIT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "comparaison_gabarit.html")

if __name__ == "__main__":
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    sortie = sys.argv[2] if len(sys.argv) > 2 else os.path.join(RACINE, "comparaison.html")
    donnees = {
        "reference": _commit(ref),
        "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "styles": comparer(ref),
    }
    with open(GABARIT, encoding="utf-8") as fh:
        page = fh.read()
    # la planche est composee dans la police elle-meme, version courante
    for graisse in ("Regular", "Bold"):
        with open(os.path.join(RACINE, f"fonts/woff2/Appli-Tec-{graisse}.woff2"), "rb") as fh:
            page = page.replace(f"/*POLICE_{graisse.upper()}*/",
                                base64.b64encode(fh.read()).decode("ascii"))
    page = page.replace("/*DONNEES*/null",
                        json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))
                        .replace("</", "<\\/"))
    with open(sortie, "w", encoding="utf-8") as fh:
        fh.write(page)
    total = sum(len(s["glyphes"]) for s in donnees["styles"])
    print(f"  {total} glyphes modifies, contre {donnees['reference']}")
    for s in donnees["styles"]:
        if s["glyphes"]:
            print(f"     {s['style']:<22} {len(s['glyphes'])}")
    print(f"  -> {os.path.relpath(sortie)}")
