"""
Visionneur de revue : chaque glyphe de chaque style, un par un.

Produit revue.html, a ouvrir dans un navigateur :

    fleches gauche / droite   glyphe precedent / suivant
    fleches haut / bas        style precedent / suivant (meme glyphe)
    1  2  3                   mode Normal / Contour / Difference
    F                         plein ecran
    R                         marquer le glyphe "a revoir"

    python3 tools/revue.py              # difference contre le dernier commit
    python3 tools/revue.py HEAD~3       # contre une version plus ancienne
    python3 tools/revue.py 9a46589      # contre un commit precis

Le mode Difference superpose le dessin de la version de reference : la zone
qui a change est coloriee. L'ecart affiche est l'epaisseur de la plus
zone modifiee : la plus grande distance entre l'ancien et le nouveau
contour, en unites sur 1 000 par cadratin. En-deca d'une
unite, c'est le bruit de la conversion des courbes en quadratiques,
invisible a toute taille d'impression ; le glyphe est alors tenu pour
inchange.
"""
import sys, os, io, glob, json, base64, subprocess, datetime, math

import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.perimeterPen import PerimeterPen

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "revue_gabarit.html")
SEUIL = 1.0   # unites : plus grande distance entre ancien et nouveau contour

# ordre de passage avec les fleches haut / bas : par famille, puis par graisse
GRAISSES = ["Light", "Regular", "Medium", "Bold", "Heavy"]
ORDRE = ([("", g, False) for g in GRAISSES]
         + [("", g, True) for g in GRAISSES]
         + [("Condensed", g, False) for g in GRAISSES])


def _fichier(largeur, graisse, italique):
    if largeur:
        nom = f"Condensed-{graisse}"
    elif italique:
        nom = "Italic" if graisse == "Regular" else f"{graisse}Italic"
    else:
        nom = graisse
    return os.path.join(RACINE, "fonts/ttf", f"Appli-Tec-{nom}.ttf")


def _libelle(largeur, graisse, italique):
    if italique and graisse == "Regular":
        graisse = ""
    return " ".join(x for x in (largeur, graisse, "Italic" if italique else "") if x)


def _ancienne(ref, chemin):
    rel = os.path.relpath(chemin, RACINE)
    try:
        data = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=RACINE,
                              capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None
    return TTFont(io.BytesIO(data))


def _chemin(gs, nom):
    """Trace simplifie : sans cette etape, deux dessins identiques dont un
    contour demarre ailleurs donnent un ecart fantome."""
    p = pathops.Path()
    gs[nom].draw(p.getPen(glyphSet=gs))
    try:
        return pathops.simplify(p, clockwise=p.clockwise)
    except Exception:
        return p


def _svg_pathops(p):
    pen = SVGPathPen(None, ntos=lambda v: str(int(round(v))))
    p.draw(pen)
    return pen.getCommands()


def _svg(gs, nom):
    pen = SVGPathPen(gs, ntos=lambda v: str(int(round(v))))
    gs[nom].draw(pen)
    return pen.getCommands()


def _points(font, nom):
    """Points du trace, tels qu'ils sont dans le fichier : [x, y, sur_courbe].
    Composites decomposes, pour voir ce qui s'affiche vraiment."""
    glyf = font["glyf"]
    g = glyf[nom]
    if g.numberOfContours == 0:
        return [], []
    coords, ends, flags = g.getCoordinates(glyf)
    return [[int(x), int(y), int(f & 1)] for (x, y), f in zip(coords, flags)], list(ends)


def _echantillons(gs, nom, pas=2.0):
    """Points du contour tous les `pas` unites environ."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    rec = DecomposingRecordingPen(gs)
    gs[nom].draw(rec)
    pts, pos, debut = [], None, None

    def ajouter(courbe, n):
        for i in range(1, n + 1):
            pts.append(courbe(i / n))

    for op, args in rec.value:
        if op == "moveTo":
            pos = debut = args[0]; pts.append(pos)
        elif op == "lineTo":
            a, b = pos, args[0]
            n = max(1, int(math.dist(a, b) / pas))
            ajouter(lambda t: (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), n)
            pos = b
        elif op == "qCurveTo":
            ctrl = list(args[:-1]); fin = args[-1] if args[-1] is not None else debut
            # decomposition en quadratiques simples (points implicites)
            segs, p0 = [], pos
            for i, c in enumerate(ctrl):
                p2 = fin if i == len(ctrl) - 1 else ((c[0] + ctrl[i + 1][0]) / 2, (c[1] + ctrl[i + 1][1]) / 2)
                segs.append((p0, c, p2)); p0 = p2
            for p0, c, p2 in segs:
                n = max(1, int((math.dist(p0, c) + math.dist(c, p2)) / pas))
                ajouter(lambda t, p0=p0, c=c, p2=p2: tuple(
                    (1 - t) ** 2 * p0[k] + 2 * (1 - t) * t * c[k] + t * t * p2[k] for k in (0, 1)), n)
            pos = fin
        elif op == "curveTo":
            p0, (c1, c2, p3) = pos, args
            n = max(1, int((math.dist(p0, c1) + math.dist(c1, c2) + math.dist(c2, p3)) / pas))
            ajouter(lambda t: tuple((1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * c1[k]
                                    + 3 * (1 - t) * t * t * c2[k] + t ** 3 * p3[k] for k in (0, 1)), n)
            pos = p3
        elif op in ("closePath", "endPath"):
            if pos is not None and debut is not None and pos != debut:
                a, b = pos, debut
                n = max(1, int(math.dist(a, b) / pas))
                ajouter(lambda t: (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), n)
            pos = debut
    return pts


def _ecart_max(ga, gb, nom):
    """Plus grande distance entre les deux contours, en unites.

    Une encoche de 10 unites donne 10 ; l'arrondi de la conversion des
    courbes, une demi-unite. Les mesures de surface s'y trompaient : une
    difference le long d'une contreforme forme un anneau fin dont chaque
    bord, pris seul, parait enorme.
    """
    import numpy as np

    def dirige(gx, gy):
        # X echantillonne grossierement, Y finement (une demi-unite) : la
        # distance d'un point de X au trace de Y est connue a 0,25 pres.
        X = np.array(_echantillons(gx, nom, 2.0))
        Y = np.array(_echantillons(gy, nom, 0.5))
        if not len(X) or not len(Y):
            return 0.0 if not len(X) and not len(Y) else float("inf")
        # Grille de deux unites : un point de X qui a un point de Y dans sa
        # case ou une voisine est proche ; la distance exacte n'est calculee
        # que pour les autres, qui sont rares.
        cases = set(map(tuple, np.floor(Y / 2.0).astype(int).tolist()))
        loin = [i for i, (u, v) in enumerate(np.floor(X / 2.0).astype(int).tolist())
                if not any((u + du, v + dv) in cases for du in (-1, 0, 1) for dv in (-1, 0, 1))]
        if not loin:
            return 0.0
        Z = X[loin]
        d = ((Z[:, None, :] - Y[None, :, :]) ** 2).sum(-1).min(1)
        return float(d.max()) ** 0.5

    return max(dirige(ga, gb), dirige(gb, ga))


def _perimetre(gs, nom):
    pen = PerimeterPen(gs, tolerance=0.5)
    gs[nom].draw(pen)
    return pen.value


def _style(largeur, graisse, italique, ref):
    f = _fichier(largeur, graisse, italique)
    if not os.path.exists(f):
        return None
    font = TTFont(f)
    gs = font.getGlyphSet()
    avant = _ancienne(ref, f) if ref else None
    ga = avant.getGlyphSet() if avant else None
    cmap = font.getBestCmap()
    inverse = {}
    for u, n in sorted(cmap.items()):
        inverse.setdefault(n, u)
    # caracteres codes d'abord, dans l'ordre Unicode ; puis les variantes
    ordre = sorted(inverse, key=lambda n: inverse[n]) + \
        [n for n in font.getGlyphOrder() if n not in inverse]
    os2 = font["OS/2"]
    glyphes, modifies = [], 0
    for n in ordre:
        u = inverse.get(n)
        e = {"n": n, "c": chr(u) if u and u > 32 else "", "u": u or 0,
             "a": font["hmtx"][n][0], "d": _svg(gs, n)}
        e["p"], e["f"] = _points(font, n)
        if ga is not None:
            if n not in ga:
                e["x"] = {"nouveau": 1}
                modifies += 1
            else:
                pa, pb = _chemin(ga, n), _chemin(gs, n)
                try:
                    diff = pathops.op(pa, pb, pathops.PathOp.XOR)
                    surf = abs(diff.area)
                except Exception:
                    diff, surf = None, float("inf")
                # glyphe inchange (surface differente nulle) : rien a mesurer
                ep = _ecart_max(ga, gs, n) if surf > 0.5 else 0.0
                la = avant["hmtx"][n][0]
                if ep >= SEUIL or la != e["a"]:
                    e["x"] = {"e": round(ep, 1) if ep != float("inf") else -1,
                              "d": _svg(ga, n), "z": _svg_pathops(diff) if diff else "",
                              "a": la}
                    modifies += 1
        glyphes.append(e)
    return {"style": _libelle(largeur, graisse, italique),
            "fichier": os.path.basename(f),
            "italique": italique,
            "xh": os2.sxHeight, "cap": os2.sCapHeight,
            "asc": os2.sTypoAscender, "desc": os2.sTypoDescender,
            "modifies": modifies, "glyphes": glyphes}


def _commit(ref):
    try:
        return subprocess.run(["git", "log", "-1", "--format=%h %s", ref],
                              cwd=RACINE, capture_output=True, text=True,
                              check=True).stdout.strip()
    except subprocess.CalledProcessError:
        return ref


if __name__ == "__main__":
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    sortie = sys.argv[2] if len(sys.argv) > 2 else os.path.join(RACINE, "revue.html")
    styles = [s for s in (_style(*o, ref) for o in ORDRE) if s]
    donnees = {"reference": _commit(ref),
               "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
               "styles": styles}
    with open(GABARIT, encoding="utf-8") as fh:
        page = fh.read()
    # l'interface est composee dans la police elle-meme
    for graisse in ("Regular", "Bold"):
        with open(os.path.join(RACINE, f"fonts/woff2/Appli-Tec-{graisse}.woff2"), "rb") as fh:
            page = page.replace(f"/*POLICE_{graisse.upper()}*/",
                                base64.b64encode(fh.read()).decode("ascii"))
    page = page.replace("/*DONNEES*/null",
                        json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))
                        .replace("</", "<\\/"))
    with open(sortie, "w", encoding="utf-8") as fh:
        fh.write(page)
    total = sum(s["modifies"] for s in styles)
    print(f"  {len(styles)} styles, {sum(len(s['glyphes']) for s in styles)} glyphes")
    print(f"  {total} glyphes modifies depuis {donnees['reference']}")
    for s in styles:
        if s["modifies"]:
            print(f"     {s['style']:<22} {s['modifies']}")
    print(f"  -> {os.path.relpath(sortie)} ({os.path.getsize(sortie) // 1024} Ko)")
