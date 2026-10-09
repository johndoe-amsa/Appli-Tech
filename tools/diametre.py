"""
Redessine le "Ø" en signe de diametre : un cercle barre.

Dans D-DIN, le Ø est la lettre danoise et norvegienne : le O ovale de la
DIN 1451, barre. Dans une documentation technique, il ne sert pratiquement
qu'a coter un diametre - "Ø 12 mm" - et l'on attend alors un cercle, comme
sur un plan.

Le dessin est construit, graisse par graisse, a partir des mesures du O de
la meme police, si bien qu'il suit la famille sans master a part :

  - cercle exterieur : la hauteur du O, depassements compris ;
  - epaisseur du trait : celle du O, sur le flanc (fut) et au sommet
    (delie) - le contraste de la DIN est garde, la contreforme est une
    ellipse a peine aplatie ;
  - barre : l'epaisseur de la barre du Ø d'origine ; elle depasse le
    cercle en haut et en bas, et s'arrete a son aplomb sur les cotes, ce
    qui la couche a 50° environ ;
  - approches : celles du O.

Les italiques recoivent le dessin du romain de meme graisse, penche de 12°
comme le reste de l'italique.

Le signe de diametre du standard, U+2300 "⌀", est rattache au meme glyphe :
un texte saisi depuis un logiciel de DAO l'affiche donc a l'identique.

A passer apres les generateurs, avant le crenage et le hinting (voir
tout_construire.sh) : le crenage mesure le nouveau dessin.

    python3 tools/diametre.py fonts/ttf/*.ttf
"""
import sys, os, math

import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen

SLANT = math.tan(math.radians(12.0))   # l'inclinaison des italiques
DEPASSE = 0.06    # la barre depasse le cercle de ce rapport du rayon
KAPPA = 0.5522847498                   # quart de cercle en courbe de Bezier
DIAMETRE = 0x2300


def chemin(font, nom):
    p = pathops.Path()
    font.getGlyphSet()[nom].draw(p.getPen())
    return p


def morceaux(p):
    """Boites des contours separes d'un chemin."""
    rec = RecordingPen()
    p.draw(rec)
    out, cur = [], None
    for op, pts in rec.value:
        if op == "moveTo":
            cur = BoundsPen(None)
            cur.moveTo(*pts)
        elif op in ("closePath", "endPath"):
            cur.closePath()
            if cur.bounds:
                out.append(cur.bounds)
        else:
            getattr(cur, op)(*pts)
    return out


def bande(p, x0, y0, x1, y1):
    r = pathops.Path()
    pen = r.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
    pen.closePath()
    return morceaux(pathops.op(p, r, pathops.PathOp.INTERSECTION, clockwise=True))


def mesures(font):
    """Mesures du O et de la barre du Ø, dans un romain."""
    O = chemin(font, "O")
    x0, y0, x1, y1 = O.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    gauche = min(bande(O, -1000, cy - 0.5, 2000, cy + 0.5), key=lambda b: b[0])
    haut = max(bande(O, cx - 0.5, -1000, cx + 0.5, 2000), key=lambda b: b[3])
    # barre du Ø d'origine : ce que le Ø a de plus que le O, coupe a deux
    # hauteurs proches du centre, donne sa largeur horizontale et sa pente,
    # donc son epaisseur vraie.
    S = pathops.op(chemin(font, "Oslash"), O, pathops.PathOp.DIFFERENCE, clockwise=True)
    milieux = []
    for y in (cy - 25, cy + 25):
        m = bande(S, -1000, y - 0.5, 2000, y + 0.5)
        if len(m) != 1:
            raise ValueError(f"barre du Ø introuvable a y={y:.0f}")
        milieux.append(m[0])
    (a0, _, a1, _), (b0, _, b1, _) = milieux
    angle = math.atan2(50, (b0 + b1) / 2 - (a0 + a1) / 2)
    barre = ((a1 - a0) + (b1 - b0)) / 2 * math.sin(angle)
    lsb = x0
    rsb = font["hmtx"]["O"][0] - x1
    return dict(y0=y0, y1=y1, fut=gauche[2] - gauche[0], delie=haut[3] - haut[1],
                barre=barre, lsb=lsb, rsb=rsb, chasse_o=font["hmtx"]["O"][0])


def ellipse(pen, cx, cy, rx, ry, sens=1):
    kx, ky = rx * KAPPA, ry * KAPPA * sens
    pen.moveTo((cx + rx, cy))
    pen.curveTo((cx + rx, cy + ky), (cx + kx, cy + ry * sens), (cx, cy + ry * sens))
    pen.curveTo((cx - kx, cy + ry * sens), (cx - rx, cy + ky), (cx - rx, cy))
    pen.curveTo((cx - rx, cy - ky), (cx - kx, cy - ry * sens), (cx, cy - ry * sens))
    pen.curveTo((cx + kx, cy - ry * sens), (cx + rx, cy - ky), (cx + rx, cy))
    pen.closePath()


def dessin(m):
    """Le cercle barre, dans un romain : (chemin, chasse, centre)."""
    R = (m["y1"] - m["y0"]) / 2
    cx, cy = m["lsb"] + R, (m["y0"] + m["y1"]) / 2
    anneau = pathops.Path()
    ellipse(anneau.getPen(), cx, cy, R, R)
    contre = pathops.Path()
    ellipse(contre.getPen(), cx, cy, R - m["fut"], R - m["delie"])
    anneau = pathops.op(anneau, contre, pathops.PathOp.DIFFERENCE, clockwise=True)

    # barre : parallelogramme d'axe passant par le centre, coupe a
    # l'horizontale au-dela du cercle, ses coins exterieurs a l'aplomb du
    # cercle.
    h = R * (1 + DEPASSE)
    e = m["barre"] / 2                        # demi-largeur horizontale,
    for _ in range(5):                        # qui depend de la pente
        a = math.atan2(h, R - e)
        e = m["barre"] / 2 / math.sin(a)
    dx = R - e
    barre = pathops.Path()
    pen = barre.getPen()
    pen.moveTo((cx - dx - e, cy - h)); pen.lineTo((cx - dx + e, cy - h))
    pen.lineTo((cx + dx + e, cy + h)); pen.lineTo((cx + dx - e, cy + h))
    pen.closePath()
    tout = pathops.op(anneau, barre, pathops.PathOp.UNION, clockwise=True)
    chasse = round(cx + R + m["rsb"])
    return tout, chasse, cx


def romain_de(chemin_ttf):
    """Le romain de meme graisse et largeur qu'un italique."""
    d, f = os.path.split(chemin_ttf)
    nom = f.replace("Italic", "")
    if nom.endswith("-.ttf"):
        nom = nom.replace("-.ttf", "-Regular.ttf")
    return os.path.join(d, nom)


def appliquer(chemin_ttf, m):
    """Ecrit le Ø dessine d'apres les mesures m du romain de meme graisse."""
    font = TTFont(chemin_ttf)
    p, chasse, cx = dessin(m)

    trans = (1, 0, 0, 1, 0, 0)
    if font["post"].italicAngle:
        # Penche autour de la ligne de base, puis cale sur le O italique :
        # le centre du cercle a mi-hauteur tombe la ou tombe celui du O,
        # decale de la demi-difference de chasse, comme dans le romain.
        bo = chemin(font, "O").bounds
        cy = (m["y0"] + m["y1"]) / 2
        chasse_o = font["hmtx"]["O"][0]
        chasse += chasse_o - m["chasse_o"]
        cible = (bo[0] + bo[2]) / 2 + (chasse - chasse_o) / 2
        trans = (1, 0, SLANT, 1, cible - (cx + SLANT * cy), 0)

    tt = TTGlyphPen(None)
    p.draw(TransformPen(Cu2QuPen(tt, max_err=0.5, reverse_direction=False), trans))
    g = tt.glyph()
    glyf = font["glyf"]
    glyf["Oslash"] = g
    g.recalcBounds(glyf)
    font["hmtx"]["Oslash"] = (chasse, g.xMin)

    for t in font["cmap"].tables:
        if t.isUnicode() and "Oslash" in t.cmap.values():
            t.cmap[DIAMETRE] = "Oslash"
    font.save(chemin_ttf)
    return chasse


if __name__ == "__main__":
    chemins = sys.argv[1:]
    deja = [os.path.basename(c) for c in chemins if DIAMETRE in TTFont(c).getBestCmap()]
    if deja:
        sys.exit(f"Ø deja redessine dans {deja} : relancer d'abord les generateurs")
    # Toutes les mesures avant toute ecriture : les italiques se mesurent sur
    # leur romain, dont le Ø d'origine donne l'epaisseur de la barre.
    mes = {}
    for c in chemins:
        r = romain_de(c) if TTFont(c)["post"].italicAngle else c
        if r not in mes:
            mes[r] = mesures(TTFont(r))
    for c in chemins:
        m = mes[romain_de(c) if TTFont(c)["post"].italicAngle else c]
        print(f"   {os.path.basename(c):<34} chasse {appliquer(c, m)}")
