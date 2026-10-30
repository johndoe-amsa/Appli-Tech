"""
Ajoute a Appli-Tec les signes techniques qui manquaient a D-DIN.

Une fiche technique ecrit "≤ 0,01 mm", "≈ 12 kg", "H₂O", "Ω", "Δt" ; D-DIN
n'avait aucun de ces signes, et Word ou InDesign les allaient chercher dans
une autre police, d'un autre dessin. Ils sont construits ici, graisse par
graisse, a partir des signes de la meme police, si bien qu'ils suivent la
famille sans master a part - comme le Ø de tools/diametre.py :

  operateurs   − ≤ ≥ ≈ ≠ ∞ √ ′ ″  d'apres + = < ± ~ / : meme trait, meme axe,
                                   meme chasse ; le chevron de ≤ est celui
                                   du <, retrace a la hauteur voulue ; les
                                   primes sont les guillemets droits couches ;
                                   ∅ vise le Ø, comme ⌀ ;
  fleches      ← → ↔ ↑ ↓          fut du −, pointe tiree du chevron du < ;
  grec         Δ Ω α β μ π σ φ    d'apres A, O, q, µ, n, z, o : leurs futs,
                                   leurs delies, leurs rondes ; μ est le µ ;
                                   ∆ (U+2206) et Ω (U+2126) visent les memes
                                   dessins que Δ et Ω, comme ⌀ vise le Ø ;
  exposants    ⁰ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹ ⁺ ⁻   ⁰ et ⁴ existaient deja sans code ; ⁵ a ⁹,
                                   ⁺ et ⁻ (min⁻¹) sont tires des chiffres et
                                   du + de la police (voir plus bas) ;
  indices      ₀ … ₉              les exposants, descendus sous la ligne ;
  espaces      demi-cadratin, cadratin, espace de chiffre (la chasse du 0),
               espace fine et espace fine insecable (0,6 espace-mot) ;
  traits       ‐ et ‑ (insecable) : le trait d'union.

Les chiffres numerateurs et denominateurs 5 a 9 sont ajoutes en passant, et
GSUB est reecrite : les fonctionnalites "Exposant" et "Indice" couvrent les
dix chiffres, et "Fractions" compose n'importe quelle fraction (3/8, 7/16),
plus seulement ½ ¼ ¾. Toutes les fonctionnalites sont declarees pour DFLT
et latn : InDesign interroge latn, ou D-DIN ne declarait ni les fractions ni
les exposants.

Les exposants d'origine ne sont pas une reduction des chiffres : un chiffre
reduit est trop maigre. Mesure faite, ce sont les chiffres d'une graisse plus
forte, reduits a 60,5 % : le "0" superieur du Bold est le "0" a t = 1,65
reduit, a 1,5 % de surface pres. Les exposants 5 a 9 sont donc fabriques
ainsi, avec les reglages trouves sur les exposants 0 a 4 d'origine
(EXPOSANTS) : leur graisse source, leur largeur et leurs approches.

Les italiques recoivent le dessin du romain de meme graisse, penche de 12°
autour de la meme hauteur que le reste de l'italique ; les chevrons penches
retrouvent deux branches de meme epaisseur (build_italic.chevrons_egaux).

A passer apres diametre.py, avant le crenage et le hinting (voir
tout_construire.sh) : le crenage et le hinting mesurent les nouveaux dessins.

    python3 tools/symboles.py fonts/ttf/*.ttf
"""
import sys, os, io, math, contextlib, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pathops
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.feaLib.builder import addOpenTypeFeatures

from build import build_instance, MASTERS
from build_italic import chevrons_egaux, SLANT, ORIGINE

CHIFFRES = ["zero", "one", "two", "three", "four",
            "five", "six", "seven", "eight", "nine"]

# Codes et noms des glyphes dessines ici.
OPERATEURS = {"minus": 0x2212, "lessequal": 0x2264, "greaterequal": 0x2265,
              "approxequal": 0x2248, "notequal": 0x2260, "infinity": 0x221E,
              "radical": 0x221A, "minute": 0x2032, "second": 0x2033}
VIDE = 0x2205      # ∅, souvent tape pour un diametre : le meme dessin que Ø
FLECHES = {"arrowleft": 0x2190, "arrowup": 0x2191, "arrowright": 0x2192,
           "arrowdown": 0x2193, "arrowboth": 0x2194}
GREC = {"Delta": (0x0394, 0x2206), "Omega": (0x03A9, 0x2126), "alpha": (0x03B1,),
        "beta": (0x03B2,), "pi": (0x03C0,), "sigma": (0x03C3,), "phi": (0x03C6,)}
MU = 0x03BC                      # μ grec : le meme dessin que le µ (U+00B5)
EXPOSANTS_CODES = {0: 0x2070, 1: 0x00B9, 2: 0x00B2, 3: 0x00B3, 4: 0x2074,
                   5: 0x2075, 6: 0x2076, 7: 0x2077, 8: 0x2078, 9: 0x2079}
INDICES_CODES = {i: 0x2080 + i for i in range(10)}
FRACTION = 0x2044                # barre de fraction
# Espaces typographiques, sans dessin : InDesign pose l'espace fine
# insecable (U+202F) entre les milliers et devant : ; ? ! en francais.
ESPACES = {"uni2002": 0x2002, "uni2003": 0x2003, "uni2007": 0x2007,
           "uni2009": 0x2009, "uni202F": 0x202F}
FINE = 0.6                        # espace fine, en part de l'espace-mot
TRAITS = {"uni2010": 0x2010, "uni2011": 0x2011}   # trait d'union, insecable

INDICE_DY = -580   # l'exposant, descendu : de -156 a 274 environ, sous la ligne

# Exposants : chiffre de la graisse t' = a + b.t, reduit a ECHELLE en hauteur
# et ECHELLE x k en largeur, approches du chiffre reduites puis augmentees de
# "marge". Valeurs trouvees sur les exposants 0 a 4 des masters, par balayage
# de t' (ecart de surface : Regular 3,3 %, Bold 1,5 %, Condensed 2,8 et 3,7 %).
ECHELLE = 0.605
EXPOSANTS = {
    #           t'(400) t'(700)  k(400)  k(700)  marge(400) marge(700)
    "":          (0.65,  1.65,   1.016,  1.002,  8.5,      16.0),
    "Condensed": (0.75,  1.10,   1.062,  1.091,  6.5,      7.5),
}
BASE_EXPOSANT = 430                # ligne de pied des exposants d'origine

# Graisse de chaque fichier sur l'axe des masters (0 = Regular, 1 = Bold).
T_DE_POIDS = {300: -1 / 3, 400: 0.0, 500: 1 / 3, 700: 1.0, 800: 4 / 3}


# ---------------------------------------------------------------- chemins --

def chemin(font, nom, trans=None):
    p = pathops.Path()
    pen = p.getPen()
    font.getGlyphSet()[nom].draw(TransformPen(pen, trans) if trans else pen)
    return p


def poly(*pts):
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo(pts[0])
    for q in pts[1:]:
        pen.lineTo(q)
    pen.closePath()
    return p


def rect(x0, y0, x1, y1):
    return poly((x0, y0), (x0, y1), (x1, y1), (x1, y0))


def union(*ps):
    out = ps[0]
    for p in ps[1:]:
        out = pathops.op(out, p, pathops.PathOp.UNION, clockwise=True)
    return out


def moins(a, b):
    return pathops.op(a, b, pathops.PathOp.DIFFERENCE, clockwise=True)


def inter(a, b):
    return pathops.op(a, b, pathops.PathOp.INTERSECTION, clockwise=True)


def transforme(p, t):
    q = pathops.Path()
    p.draw(TransformPen(q.getPen(), t))
    return q


def _morceaux(p):
    rec = RecordingPen()
    p.draw(rec)
    out, cur = [], None
    for op, pts in rec.value:
        if op == "moveTo":
            cur = pathops.Path()
            pen = cur.getPen()
            pen.moveTo(*pts)
        elif op in ("closePath", "endPath"):
            pen.closePath()
            if cur.bounds != (0, 0, 0, 0):
                out.append(cur.bounds)
        else:
            getattr(pen, op)(*pts)
    return out


def coupe_h(p, y):
    """Intervalles d'encre (x0, x1) a la hauteur y, de gauche a droite."""
    return sorted((b[0], b[2]) for b in _morceaux(inter(p, rect(-3000, y - 0.5, 4000, y + 0.5))))


def coupe_v(p, x):
    """Intervalles d'encre (y0, y1) a l'abscisse x, de bas en haut."""
    return sorted((b[1], b[3]) for b in _morceaux(inter(p, rect(x - 0.5, -3000, x + 0.5, 4000))))


def trait(points, ep, ferme=False, joint=pathops.LineJoin.MITER_JOIN, limite=4.0):
    """Ligne brisee epaissie de ep, bouts coupes droit."""
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo(points[0])
    for q in points[1:]:
        pen.lineTo(q)
    pen.closePath() if ferme else pen.endPath()
    p.stroke(ep, pathops.LineCap.BUTT_CAP, joint, limite)
    return pathops.simplify(p, clockwise=True)


# ---------------------------------------------------------------- mesures --

def mesures(f):
    """Ce qu'il faut savoir d'un romain pour y construire les signes."""
    m = {"font": f}
    hm = f["hmtx"]

    # Operateurs : le +, le =, le ±, le <.
    plus = chemin(f, "plus")
    px0, py0, px1, py1 = plus.bounds
    barre = coupe_v(plus, px0 + 2)[0]
    m["axe"] = (barre[0] + barre[1]) / 2
    m["trait"] = barre[1] - barre[0]
    m["barre_plus"] = barre
    eg = chemin(f, "equal")
    m["eq"] = eg.bounds
    m["eq_barres"] = coupe_v(eg, (eg.bounds[0] + eg.bounds[2]) / 2)
    m["eq_chasse"] = hm["equal"][0]
    pm = chemin(f, "plusminus")
    m["pm"] = pm.bounds
    m["pm_barre"] = coupe_v(pm, pm.bounds[0] + 2)[0]

    # Le chevron du <, lu sur ses sommets : pointe plate (x0, cy +- e),
    # bouts des branches en x1, creux en xi.
    rec = RecordingPen()
    f.getGlyphSet()["less"].draw(rec)
    pts = [p[0] for op, p in rec.value if op in ("moveTo", "lineTo")]
    lx0 = min(x for x, _ in pts)
    lx1 = max(x for x, _ in pts)
    pointe = sorted(y for x, y in pts if abs(x - lx0) < 1)
    bouts = sorted(y for x, y in pts if abs(x - lx1) < 1)
    creux = [p for p in pts if lx0 + 1 < p[0] < lx1 - 1][0]
    cy = (pointe[0] + pointe[-1]) / 2
    m["chevron"] = dict(x0=lx0, x1=lx1, cy=cy, e=(pointe[-1] - pointe[0]) / 2,
                        h=bouts[-1] - bouts[0], v=bouts[-1] - bouts[-2], xi=creux[0])

    m["tilde"] = chemin(f, "asciitilde")
    sl = chemin(f, "slash")
    sx0, sy0, sx1, sy1 = sl.bounds
    g0, g1 = coupe_h(sl, (sy0 + sy1) / 2)[0]
    m["pente_slash"] = (sx1 - sx0 - (g1 - g0)) / (sy1 - sy0)

    # Lettres : les futs, les delies, les hauteurs.
    o = chemin(f, "o")
    ox0, oy0, ox1, oy1 = o.bounds
    m["o"] = o
    m["o_box"] = o.bounds
    m["o_fut"] = coupe_h(o, (oy0 + oy1) / 2)[0]
    m["o_delie"] = coupe_v(o, (ox0 + ox1) / 2)[-1]
    m["o_marges"] = (hm["o"][1], hm["o"][0] - ox1)
    n = chemin(f, "n")
    m["n_futs"] = coupe_h(n, 150)
    m["n_marges"] = (hm["n"][1], hm["n"][0] - n.bounds[2])
    m["x"] = coupe_v(n, m["n_futs"][0][0] + 2)[-1][1]     # hauteur d'x
    m["fut"] = m["n_futs"][0][1] - m["n_futs"][0][0]
    lb = chemin(f, "l").bounds
    m["asc"] = lb[3]
    m["desc"] = chemin(f, "p").bounds[1]
    z = chemin(f, "z")
    m["z_barre"] = coupe_v(z, z.bounds[0] + 5)[-1]
    E = chemin(f, "E")
    eb = E.bounds
    m["E_pied"] = coupe_v(E, (eb[0] + eb[2]) / 2)[0]
    m["cap"] = eb[3]
    return m


# ---------------------------------------------------- formes de la famille --

def chevron(m, x_pointe, x_bouts, cy, h):
    """Le chevron du <, retrace pointe en x_pointe, bouts en x_bouts, haut de h.

    Garde la pointe plate, l'epaisseur perpendiculaire des branches a leur
    bout et l'epaisseur au creux : a la hauteur d'origine, c'est le < meme.
    Rend les sept sommets, pointe a gauche ou a droite selon x_bouts.
    """
    c = m["chevron"]
    L0 = c["x1"] - c["x0"]
    # epaisseurs a conserver, mesurees sur le < d'origine
    pente0 = (c["h"] / 2 - c["e"]) / L0
    perp_bout = c["v"] * math.cos(math.atan(pente0))
    haut0 = (c["x0"], c["cy"] + c["e"])
    d0 = (L0, c["h"] / 2 - c["e"])
    xi, yi = c["xi"], c["cy"]
    perp_creux = abs((xi - haut0[0]) * d0[1] - (yi - haut0[1]) * d0[0]) / math.hypot(*d0)

    s = 1 if x_bouts > x_pointe else -1
    L = abs(x_bouts - x_pointe)
    e = c["e"]
    pente = (h / 2 - e) / L
    a = math.atan(pente)
    v = perp_bout / math.cos(a)
    # creux : sur l'axe, a perp_creux du bord exterieur
    xc = x_pointe + s * (perp_creux / math.sin(a) - e / pente) if pente > 0 else x_pointe
    # le bord interieur part du bout (x_bouts, cy + h/2 - v) vers le creux
    return [(x_pointe, cy - e), (x_pointe, cy + e), (x_bouts, cy + h / 2),
            (x_bouts, cy + h / 2 - v), (xc, cy), (x_bouts, cy - h / 2 + v),
            (x_bouts, cy - h / 2)]


def stade(x0, y0, x1, y1, quart):
    """Rond de la DIN : flancs droits, quatre arrondis tires du "o".

    quart = (k, u1, v1, u2) : hauteur de l'arrondi en part de la demi-largeur,
    puis ses deux points hors courbe, normalises (u le long de la
    demi-largeur, v le long de la hauteur d'arrondi), lus sur le "o".
    """
    k, u1, v1, u2 = quart
    a = (x1 - x0) / 2
    # au moins un petit flanc droit : sans lui, le contour n'aurait plus un
    # seul point sur la courbe, ce que bien des outils ne savent pas lire
    c = min(k * a, (y1 - y0) / 2 - 2)
    cx = (x0 + x1) / 2
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((x0, y0 + c))
    pen.lineTo((x0, y1 - c))
    pen.qCurveTo((x0, y1 - c + v1 * c), (x0 + u2 * a, y1), (cx, y1))
    pen.qCurveTo((x1 - u2 * a, y1), (x1, y1 - c + v1 * c), (x1, y1 - c))
    pen.lineTo((x1, y0 + c))
    pen.qCurveTo((x1, y0 + c - v1 * c), (x1 - u2 * a, y0), (cx, y0))
    pen.qCurveTo((x0 + u2 * a, y0), (x0, y0 + c - v1 * c), (x0, y0 + c))
    pen.closePath()
    return p


def _quart_modele(v1, u2, n=40):
    """Points (u, v) de l'arrondi de stade(), normalise de (0, 0) a (1, 1)."""
    c1, c2 = (0.0, v1), (u2, 1.0)
    mil = ((c1[0] + c2[0]) / 2, (c1[1] + c2[1]) / 2)
    pts = []
    for p0, c, p1 in (((0.0, 0.0), c1, mil), (mil, c2, (1.0, 1.0))):
        for i in range(n + 1):
            t = i / n
            pts.append(((1 - t) ** 2 * p0[0] + 2 * t * (1 - t) * c[0] + t * t * p1[0],
                        (1 - t) ** 2 * p0[1] + 2 * t * (1 - t) * c[1] + t * t * p1[1]))
    return pts


def _u_a(pts, v):
    for (u0, v0), (u1, v1) in zip(pts, pts[1:]):
        if v0 <= v <= v1 and v1 > v0:
            return u0 + (u1 - u0) * (v - v0) / (v1 - v0)
    return pts[-1][0]


def quarts_du_o(f):
    """Les arrondis exterieur et interieur du "o", normalises pour stade().

    Lus sur le dessin plutot que sur ses points : selon la graisse, le meme
    arrondi est trace en un, deux ou trois segments.
    """
    rec = RecordingPen()
    f.getGlyphSet()["o"].draw(rec)
    contours, cur = [], None
    for op, pts in rec.value:
        if op == "moveTo":
            cur = pathops.Path()
            pen = cur.getPen()
            pen.moveTo(*pts)
        elif op in ("closePath", "endPath"):
            pen.closePath()
            contours.append(cur)
        else:
            getattr(pen, op)(*pts)
    contours.sort(key=lambda c: -(c.bounds[2] - c.bounds[0]))
    out = []
    for c in contours[:2]:
        c = pathops.simplify(c, clockwise=True)
        x0, y0, x1, y1 = c.bounds
        a = (x1 - x0) / 2
        bord = lambda y: coupe_h(c, y)[0][0]
        yf = (y0 + y1) / 2                   # fin du flanc droit
        while yf < y1 - 2 and bord(yf + 2) - x0 < 0.5:
            yf += 2
        hauteur = y1 - yf
        cible = [(v, (bord(yf + v * hauteur) - x0) / a)
                 for v in [i / 16 for i in range(1, 16)]]
        meilleur = None
        for i in range(30, 91):
            for j in range(20, 91):
                mod = _quart_modele(i / 100, j / 100, 12)
                e = sum((_u_a(mod, v) - u) ** 2 for v, u in cible)
                if meilleur is None or e < meilleur[0]:
                    meilleur = (e, i / 100, j / 100)
        _, v1, u2 = meilleur
        out.append((hauteur / a, 0.0, v1, u2))
    return out       # exterieur, interieur


def anneau(m, x0, y0, x1, y1, fut, delie, contre_droit=False):
    """Anneau de la DIN dans la boite donnee : futs fut, delies delie.

    contre_droit : contreforme a angles droits du cote gauche, contre le
    fut, comme les panses du B.
    """
    ext, intr = m["quarts"]
    cx0, cy0, cx1, cy1 = x0 + fut, y0 + delie, x1 - fut, y1 - delie
    contre = stade(cx0, cy0, cx1, cy1, intr)
    if contre_droit:
        contre = union(contre, rect(cx0, cy0, (cx0 + cx1) / 2, cy1))
    return moins(stade(x0, y0, x1, y1, ext), contre)


# ------------------------------------------------------------- operateurs --
# Chaque dessin rend (morceaux, chasse) ; un morceau est (chemin, chevron?),
# le drapeau signalant les chevrons a reequilibrer une fois penches.

def d_minus(m):
    x0, _, x1, _ = m["eq"]
    y0, y1 = m["barre_plus"]
    return [(rect(x0, y0, x1, y1), False)], m["eq_chasse"]


def _barre_et_chevron(m, vers_gauche):
    x0, _, x1, _ = m["eq"]
    b0, b1 = m["pm_barre"]
    haut = m["pm"][3]
    ecart = 0.6 * m["trait"]
    h = haut - (b1 + ecart)
    cy = haut - h / 2
    pts = chevron(m, x0, x1, cy, h) if vers_gauche else chevron(m, x1, x0, cy, h)
    return [(rect(x0, b0, x1, b1), False), (poly(*pts), True)], m["eq_chasse"]


def d_lessequal(m):
    return _barre_et_chevron(m, True)


def d_greaterequal(m):
    return _barre_et_chevron(m, False)


def d_approxequal(m):
    (a0, a1), (b0, b1) = m["eq_barres"][0], m["eq_barres"][-1]
    d = ((b0 + b1) - (a0 + a1)) / 2
    t = m["tilde"]
    tcy = (t.bounds[1] + t.bounds[3]) / 2
    bas = transforme(t, (1, 0, 0, 1, 0, m["axe"] - d / 2 - tcy))
    haut = transforme(t, (1, 0, 0, 1, 0, m["axe"] + d / 2 - tcy))
    return [(union(bas, haut), False)], m["eq_chasse"]


def d_notequal(m):
    x0, _, x1, _ = m["eq"]
    eg = chemin(m["font"], "equal")
    c = m["chevron"]
    hy = c["h"] / 2
    cx = (x0 + x1) / 2
    k = m["pente_slash"]
    largeur = m["trait"] / math.cos(math.atan(k))
    dx = hy * k
    barre = poly((cx - dx - largeur / 2, m["axe"] - hy), (cx - dx + largeur / 2, m["axe"] - hy),
                 (cx + dx + largeur / 2, m["axe"] + hy), (cx + dx - largeur / 2, m["axe"] + hy))
    return [(union(eg, barre), False)], m["eq_chasse"]


def d_infinity(m):
    """Deux boucles qui se croisent, d'un seul trait de la graisse des operateurs."""
    x0, _, x1, _ = m["eq"]
    ep = m["trait"]
    # plus large et plus haut a mesure que le trait epaissit, pour que les
    # contreformes restent ouvertes
    w = (x1 - x0) * 1.25 + 1.0 * ep
    lsb = x0
    chasse = round(w + 2 * lsb)
    cx, cy = chasse / 2, m["axe"]
    a = (w - ep) / 2                 # demi-largeur de la ligne mediane
    b = 0.20 * w + 0.35 * ep         # demi-hauteur d'une boucle
    xm = 0.52 * a                    # sommet d'une boucle
    k = 1.1 * b / xm                 # pente de la croisee
    # ligne mediane : du centre, la boucle droite dans le sens horaire, puis
    # la gauche ; tangente horizontale aux sommets, verticale aux bouts
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((cx, cy))
    for s in (1, -1):
        pen.curveTo((cx + s * 0.45 * xm, cy + 0.45 * xm * k), (cx + s * 0.6 * xm, cy + b),
                    (cx + s * xm, cy + b))
        pen.curveTo((cx + s * (xm + 0.55 * (a - xm)), cy + b), (cx + s * a, cy + 0.55 * b),
                    (cx + s * a, cy))
        pen.curveTo((cx + s * a, cy - 0.55 * b), (cx + s * (xm + 0.55 * (a - xm)), cy - b),
                    (cx + s * xm, cy - b))
        pen.curveTo((cx + s * 0.6 * xm, cy - b), (cx + s * 0.45 * xm, cy - 0.45 * xm * k),
                    (cx, cy))
    pen.closePath()
    p.stroke(ep, pathops.LineCap.BUTT_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    return [(pathops.simplify(p, clockwise=True), False)], chasse


def d_radical(m):
    """Le radical : un jambage qui descend jusqu'a la ligne de base, la
    montee jusqu'a la hauteur des capitales, la barre.

    Construit en aplats plutot qu'en trait epaissi : le creux entre le
    jambage et la montee s'elargit avec la graisse, sans quoi il se bouche
    des le Bold.
    """
    x0, _, x1, _ = m["eq"]
    ep = m["trait"]
    cap = m["cap"]
    W = 1.15 * (x1 - x0) + 0.6 * ep
    xb = 0.30 * W + 0.4 * ep                  # pied de la montee
    course = 0.20 * W                         # avancee de la montee
    hw = ep / math.sin(math.atan2(cap, course))
    montee = poly((xb, 0), (xb + hw, 0), (xb + course + hw, cap), (xb + course, cap))
    barre = rect(xb + course, cap - 0.9 * ep, W, cap)
    # jambage : du haut a gauche jusqu'au pied de la montee, bout coupe
    # d'equerre
    ha = 0.40 * cap + 0.2 * ep
    jambage = trait([(0, ha), (xb + 0.35 * hw, -ep)], 0.9 * ep)
    p = inter(union(montee, barre, jambage), rect(-10 * ep, 0, W + 1, cap))
    b = p.bounds
    p = transforme(p, (1, 0, 0, 1, x0 - b[0], 0))
    return [(p, False)], round(b[2] - b[0] + 2 * x0)


def _prime(m, nom):
    """Le guillemet droit, couche comme un prime : pied rentre, tete dehors."""
    f = m["font"]
    p = chemin(f, nom)
    x0, y0, x1, y1 = p.bounds
    k = math.tan(math.radians(16))
    q = transforme(p, (1, 0, k, 1, -k * (y0 + y1) / 2, 0))
    return [(q, False)], f["hmtx"][nom][0]


def d_minute(m):
    return _prime(m, "quotesingle")


def d_second(m):
    return _prime(m, "quotedbl")


# ---------------------------------------------------------------- fleches --

def _fleche(m, gauche, droite):
    x0, _, x1, _ = m["eq"]
    ep = m["trait"]
    # la pointe grandit avec le trait : a taille fixe, ses branches
    # raccourcissent a mesure qu'elles epaississent, et des le Bold le
    # chevron se referme en un bloc
    w = (x1 - x0) * 1.3 + 0.5 * ep
    lsb = x0
    chasse = round(w + 2 * lsb)
    a, b = lsb, lsb + w
    y0, y1 = m["barre_plus"]
    cy = (y0 + y1) / 2
    c = m["chevron"]
    hh = 0.28 * c["h"] + 0.9 * ep    # demi-hauteur de la pointe
    L = hh * 1.0                     # branches a 45 degres
    if gauche and droite:
        # deux pointes : la fleche s'allonge pour que la tige reste visible
        w += 0.6 * L
        chasse = round(w + 2 * lsb)
        b = lsb + w
    morceaux = []
    fut_a, fut_b = a, b
    if gauche:
        pts = chevron(m, a, a + L, cy, 2 * hh)
        morceaux.append((poly(*pts), True))
        fut_a = pts[4][0] - 1
    if droite:
        pts = chevron(m, b, b - L, cy, 2 * hh)
        morceaux.append((poly(*pts), True))
        fut_b = pts[4][0] + 1
    morceaux.insert(0, (rect(fut_a, y0, fut_b, y1), False))
    return morceaux, chasse


def d_arrowright(m):
    return _fleche(m, False, True)


def d_arrowleft(m):
    return _fleche(m, True, False)


def d_arrowboth(m):
    return _fleche(m, True, True)


def _verticale(m, vers_haut):
    morceaux, w = _fleche(m, False, True)
    # la fleche couchee, tournee d'un quart de tour, centree a mi-capitale
    cx, cy = w / 2, (m["barre_plus"][0] + m["barre_plus"][1]) / 2
    chasse = m["eq_chasse"]
    s = 1 if vers_haut else -1
    t = (0, s, -s, 0, 0, 0)          # rotation de +-90 degres
    out = []
    for p, chev in morceaux:
        q = transforme(p, (1, 0, 0, 1, -cx, -cy))
        q = transforme(q, t)
        q = transforme(q, (1, 0, 0, 1, chasse / 2, m["cap"] / 2))
        out.append((q, chev))
    return out, chasse


def d_arrowup(m):
    return _verticale(m, True)


def d_arrowdown(m):
    return _verticale(m, False)


# ------------------------------------------------------------------- grec --

def d_Delta(m):
    """Le A, ferme : son enveloppe, moins la contreforme prolongee jusqu'au
    pied, epais comme le pied du E."""
    f = m["font"]
    rec = RecordingPen()
    f.getGlyphSet()["A"].draw(rec)
    contours, cur = [], []
    for op, pts in rec.value:
        if op == "moveTo":
            cur = [pts[0]]
        elif op == "lineTo":
            cur.append(pts[0])
        elif op == "closePath":
            contours.append(cur)
    contours.sort(key=len)
    contre, ext = contours[0], contours[-1]
    # enveloppe : le A sans l'echancrure entre les jambes
    bas = [p for p in ext if abs(p[1]) < 1]
    hautp = [p for p in ext if p[1] > 1]
    gauche = min(bas, key=lambda p: p[0])
    droite = max(bas, key=lambda p: p[0])
    hauts = sorted(hautp, key=lambda p: (-p[1], p[0]))[:2]
    hauts.sort()
    env = poly(gauche, hauts[0], hauts[1], droite)
    sommet = max(contre, key=lambda p: p[1])
    base = sorted([p for p in contre if p is not sommet], key=lambda p: p[0])
    pied = m["E_pied"][1]
    def prolonge(p):
        t = (pied - sommet[1]) / (p[1] - sommet[1])
        return (sommet[0] + (p[0] - sommet[0]) * t, pied)
    trou = poly(sommet, prolonge(base[1]), prolonge(base[0]))
    hm = f["hmtx"]["A"]
    return [(moins(env, trou), False)], hm[0]


def d_Omega(m):
    """Le O, ouvert en bas : ses flancs descendent droit jusqu'aux pieds,
    qui filent vers l'exterieur sur la ligne de base.

    La coupe se fait tant que la contreforme est encore large : plus bas,
    aux graisses fortes, elle se referme et les deux jambes se touchaient.
    """
    f = m["font"]
    O = chemin(f, "O")
    x0, y0, x1, y1 = O.bounds
    cy = (y0 + y1) / 2
    fut = coupe_h(O, cy)[0]
    fut = fut[1] - fut[0]
    pied = m["E_pied"][1] - m["E_pied"][0]

    def contre(y):
        c = coupe_h(O, y)
        return c[-1][0] - c[0][1] if len(c) >= 2 else 0
    large = contre(cy)
    y = cy
    while y > y0 + pied and contre(y - 2) >= 0.70 * large \
            and coupe_h(O, y - 2)[0][0] - x0 < 0.35 * fut:
        y -= 2
    g, d = coupe_h(O, y)[0], coupe_h(O, y)[-1]
    corps = inter(O, rect(x0 - 10, y, x1 + 10, y1 + 10))
    jambes = union(rect(g[0], 0, g[1], y + 1), rect(d[0], 0, d[1], y + 1))
    # pieds : au moins 0,6 fut au-dela des jambes, quitte a elargir la chasse
    deb = max(0.0, (x0 - (g[0] - 0.6 * fut)))
    pieds = union(rect(x0 - deb, 0, g[1], pied), rect(d[0], 0, x1 + deb, pied))
    p = union(corps, jambes, pieds)
    p = transforme(p, (1, 0, 0, 1, deb, 0))
    return [(p, False)], round(f["hmtx"]["O"][0] + 2 * deb)


def d_alpha(m):
    """Le q sans sa queue, le fut finissant sur un pied vers la droite."""
    f = m["font"]
    q = chemin(f, "q")
    qb = q.bounds
    fut = coupe_h(q, -50)[0]
    pied = m["z_barre"][1] - m["z_barre"][0]
    ext = 0.45 * (fut[1] - fut[0])
    corps = moins(q, rect(fut[0] - 1, qb[1] - 10, fut[1] + 1, 0))
    p = union(corps, rect(fut[0], 0, fut[1] + ext, pied))
    hm = f["hmtx"]["q"]
    return [(p, False)], round(hm[0] + ext)


def d_beta(m):
    """Fut du p, deux panses comme celles du B, l'arrondi du haut tire du o."""
    fut = m["fut"]
    delie = m["o_delie"][1] - m["o_delie"][0]
    lsb = m["n_marges"][0]
    x0 = lsb
    ow = m["o_box"][2] - m["o_box"][0]
    xl = x0 + 0.98 * ow
    xh = x0 + 0.86 * ow
    haut = m["asc"] + (m["o_box"][3] - m["x"])          # depassement du o
    bas = m["o_box"][1]
    ym = round(0.54 * m["asc"])
    panse_h = anneau(m, x0, ym, xh, haut, fut, delie, contre_droit=True)
    panse_b = anneau(m, x0, bas, xl, ym + delie, fut, delie, contre_droit=True)
    # le fut monte jusqu'a l'arrondi du haut : la panse superieure s'y
    # raccorde sans echancrure
    # la barre du milieu part du fut sans encoche : les arrondis exterieurs
    # des deux panses y laissaient un creux, plus large que le fut aux
    # graisses maigres
    milieu = rect(x0, ym, (x0 + xh) / 2, ym + delie)
    p = union(rect(x0, m["desc"], x0 + fut, (ym + haut) / 2), milieu, panse_h, panse_b)
    return [(p, False)], round(xl + m["o_marges"][1])


def d_pi(m):
    """Les deux futs du n sous la barre du z, qui deborde."""
    (a0, a1), (b0, b1) = m["n_futs"][0], m["n_futs"][-1]
    ep = m["z_barre"][1] - m["z_barre"][0]
    deb = 0.55 * m["fut"]
    xh = m["x"]
    p = union(rect(a0 - deb, xh - ep, b1 + deb, xh),
              rect(a0, 0, a1, xh), rect(b0, 0, b1, xh))
    # la barre deborde des futs : elle prend sur les approches du n
    lsb, rsb = m["n_marges"]
    decale = lsb - deb / 2 - (a0 - deb)
    p = transforme(p, (1, 0, 0, 1, decale, 0))
    return [(p, False)], round(b1 + deb + decale + rsb - deb / 2)


def d_sigma(m):
    """Le o, sa queue filant a droite au sommet."""
    o = m["o"]
    ox0, oy0, ox1, oy1 = o.bounds
    ep = m["z_barre"][1] - m["z_barre"][0]
    ext = 0.30 * (ox1 - ox0)
    cx = (ox0 + ox1) / 2
    p = union(o, rect(cx, oy1 - ep, ox1 + ext, oy1))
    return [(p, False)], round(m["font"]["hmtx"]["o"][0] + ext)


def d_phi(m):
    """Un rond plus large que le o, traverse d'un fut de l'ascendante a la
    descendante."""
    ox0, oy0, ox1, oy1 = m["o_box"]
    fut = m["o_fut"][1] - m["o_fut"][0]
    delie = m["o_delie"][1] - m["o_delie"][0]
    w = 1.28 * (ox1 - ox0)
    lsb = m["o_marges"][0]
    rond = anneau(m, lsb, oy0, lsb + w, oy1, fut, delie)
    cx = lsb + w / 2
    tige = rect(cx - m["fut"] / 2, m["desc"], cx + m["fut"] / 2, m["asc"])
    return [(union(rond, tige), False)], round(lsb + w + m["o_marges"][1])


DESSINS = {
    "minus": d_minus, "lessequal": d_lessequal, "greaterequal": d_greaterequal,
    "approxequal": d_approxequal, "notequal": d_notequal, "infinity": d_infinity,
    "radical": d_radical, "minute": d_minute, "second": d_second,
    "arrowleft": d_arrowleft, "arrowright": d_arrowright, "arrowboth": d_arrowboth,
    "arrowup": d_arrowup, "arrowdown": d_arrowdown,
    "Delta": d_Delta, "Omega": d_Omega, "alpha": d_alpha, "beta": d_beta,
    "pi": d_pi, "sigma": d_sigma, "phi": d_phi,
}


# -------------------------------------------------------------- exposants --

def exposants(chemin_ttf, f):
    """Exposants 5 a 9 d'un romain : (chemin, chasse) par chiffre."""
    largeur = "Condensed" if f["OS/2"].usWidthClass == 3 else ""
    t = T_DE_POIDS[f["OS/2"].usWeightClass]
    ta, tb, ka, kb, ma, mb = EXPOSANTS[largeur]
    tp = ta + (tb - ta) * t
    k = ka + (kb - ka) * t
    marge = ma + (mb - ma) * t
    reg, bold = (f"sources/upstream-d-din/{x}" for x in MASTERS[largeur])
    tmp = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False).name
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            build_instance(reg, bold, tp, 400, "Regular", tmp, width_name=largeur)
        src = TTFont(tmp)
        out = {}
        sx, sy = ECHELLE * k, ECHELLE
        for i in range(10):
            nom = CHIFFRES[i]
            p = chemin(src, nom, (sx, 0, 0, sy, 0, BASE_EXPOSANT))
            b = p.bounds
            lsb = sx * src["hmtx"][nom][1] + marge
            rsb = sx * (src["hmtx"][nom][0] - (src["hmtx"][nom][1] +
                                               (b[2] - b[0]) / sx)) + marge
            p = transforme(p, (1, 0, 0, 1, lsb - b[0], 0))
            out[i] = (p, round(lsb + (b[2] - b[0]) + rsb))
        # ⁺ et ⁻ (min⁻¹) : le + de la meme graisse forte, reduit de meme, et
        # sa barre seule ; approches du + reduites
        plus = chemin(src, "plus", (sx, 0, 0, sy, 0, BASE_EXPOSANT))
        b = plus.bounds
        barre = coupe_v(plus, b[0] + 1)[0]
        lsb = sx * src["hmtx"]["plus"][1] + marge
        chasse = round(2 * lsb + (b[2] - b[0]))
        out["+"] = (transforme(plus, (1, 0, 0, 1, lsb - b[0], 0)), chasse)
        out["-"] = (rect(lsb, barre[0], lsb + b[2] - b[0], barre[1]), chasse)
        return out
    finally:
        os.unlink(tmp)


# --------------------------------------------------------------- ecriture --

def vers_glyphe(p):
    tt = TTGlyphPen(None)
    p.draw(Cu2QuPen(tt, max_err=0.5, reverse_direction=False))
    return tt.glyph()


def vers_chemin(g, glyf):
    p = pathops.Path()
    g.draw(p.getPen(), glyf)
    return p


def penche(morceaux, glyf, dx=0.0):
    """Les morceaux d'un romain, penches comme l'italique ; les chevrons
    retrouvent deux branches egales."""
    t = (1, 0, SLANT, 1, -SLANT * ORIGINE + dx, 0)
    out = []
    for p, chev in morceaux:
        q = transforme(p, t)
        if chev:
            g = vers_glyphe(q)
            g = chevrons_egaux(g, glyf)
            q = vers_chemin(g, glyf)
        out.append(q)
    return union(*out)


def poser(font, nom, p, chasse, codes=()):
    g = vers_glyphe(pathops.simplify(p, clockwise=True))
    _ajouter(font, nom, g, chasse, codes)


def composite(font, nom, base, dx, dy, chasse, codes=()):
    g = Glyph()
    g.numberOfContours = -1
    c = GlyphComponent()
    c.glyphName, c.x, c.y, c.flags = base, int(round(dx)), int(round(dy)), 0x4
    g.components = [c]
    _ajouter(font, nom, g, chasse, codes)


def _ajouter(font, nom, g, chasse, codes):
    glyf, hmtx = font["glyf"], font["hmtx"]
    if nom not in glyf:
        order = font.getGlyphOrder() + [nom]
        font.setGlyphOrder(order)
        glyf.glyphOrder = order
    glyf[nom] = g
    g.recalcBounds(glyf)
    hmtx[nom] = (int(chasse), getattr(g, "xMin", 0))
    for t in font["cmap"].tables:
        if t.isUnicode():
            for c in codes:
                t.cmap[c] = nom


def romain_de(chemin_ttf):
    d, f = os.path.split(chemin_ttf)
    nom = f.replace("Italic", "")
    if nom.endswith("-.ttf"):
        nom = nom.replace("-.ttf", "-Regular.ttf")
    return os.path.join(d, nom)


def dessins_du_romain(chemin_romain):
    f = TTFont(chemin_romain)
    m = mesures(f)
    m["quarts"] = quarts_du_o(f)
    dessins = {nom: fn(m) for nom, fn in DESSINS.items()}
    return dessins, exposants(chemin_romain, f)


# ------------------------------------------------------------------- GSUB --

def _ligatures(font, tag):
    """Les ligatures d'une fonctionnalite de la police d'origine, en FEA."""
    g = font["GSUB"].table
    out = []
    for fr in g.FeatureList.FeatureRecord:
        if fr.FeatureTag != tag:
            continue
        for i in fr.Feature.LookupListIndex:
            for st in g.LookupList.Lookup[i].SubTable:
                for premier, ligs in st.ligatures.items():
                    for lg in ligs:
                        out.append(f"    sub {premier} {' '.join(lg.Component)} by {lg.LigGlyph};")
    return sorted(set(out))


def _miroirs(font):
    g = font["GSUB"].table
    for fr in g.FeatureList.FeatureRecord:
        if fr.FeatureTag == "rtla":
            for i in fr.Feature.LookupListIndex:
                for st in g.LookupList.Lookup[i].SubTable:
                    return [f"    sub {a} by {b};" for a, b in sorted(st.mapping.items())]
    return []


def gsub(font):
    """Reecrit GSUB : celle de D-DIN, plus exposants, indices et fractions
    pour les dix chiffres, declarees pour DFLT et latn."""
    sup = " ".join(_nom_exposant(i) for i in range(10))
    fea = f"""
languagesystem DFLT dflt;
languagesystem latn dflt;

@chiffres = [{' '.join(CHIFFRES)}];
@exposants = [{sup}];
@indices = [{' '.join(f'uni{0x2080 + i:04X}' for i in range(10))}];
@numr = [{' '.join(c + '.numr' for c in CHIFFRES)}];
@dnom = [{' '.join(c + '.dnom' for c in CHIFFRES)}];

feature rtla {{
{chr(10).join(_miroirs(font))}
}} rtla;

feature liga {{
{chr(10).join(_ligatures(font, 'liga'))}
}} liga;

feature dlig {{
{chr(10).join(_ligatures(font, 'dlig'))}
}} dlig;

feature sups {{
    sub @chiffres by @exposants;
}} sups;

feature subs {{
    sub @chiffres by @indices;
}} subs;

feature sinf {{
    sub @chiffres by @indices;
}} sinf;

feature numr {{
    sub @chiffres by @numr;
}} numr;

feature dnom {{
    sub @chiffres by @dnom;
}} dnom;

feature frac {{
    sub [@chiffres] slash' [@chiffres] by fraction;
    rsub @chiffres' [fraction @numr] by @numr;
    sub [fraction @dnom] @chiffres' by @dnom;
}} frac;
"""
    gpos = font["GPOS"] if "GPOS" in font else None
    gdef = font["GDEF"] if "GDEF" in font else None
    del font["GSUB"]
    addOpenTypeFeatures(font, io.StringIO(fea), tables=["GSUB"])
    if gpos is not None:
        font["GPOS"] = gpos
    if gdef is not None:
        font["GDEF"] = gdef
        cd = gdef.table.GlyphClassDef
        if cd is not None:
            for n in font.getGlyphOrder():
                cd.classDefs.setdefault(n, 1)


def _nom_exposant(i):
    return {1: "uni00B9", 2: "uni00B2", 3: "uni00B3"}.get(i, f"uni{EXPOSANTS_CODES[i]:04X}")


# -------------------------------------------------------------- programme --

def appliquer(chemin_ttf, dessins, sups):
    font = TTFont(chemin_ttf)
    glyf = font["glyf"]
    italique = bool(font["post"].italicAngle)

    if italique:
        # decalage et chasse des exposants penches, lus sur le "2" superieur
        R = TTFont(romain_de(chemin_ttf))
        (xr, yr) = R["glyf"]["two.sups"].getCoordinates(R["glyf"])[0][0]
        (xi, yi) = glyf["two.sups"].getCoordinates(glyf)[0][0]
        dx_sup = xi - (xr + SLANT * (yr - ORIGINE))
        dchasse_sup = font["hmtx"]["two.sups"][0] - R["hmtx"]["two.sups"][0]

    for nom, (morceaux, chasse) in dessins.items():
        codes = list(GREC.get(nom, ())) + ([OPERATEURS[nom]] if nom in OPERATEURS else []) \
            + ([FLECHES[nom]] if nom in FLECHES else [])
        p = penche(morceaux, glyf) if italique else union(*[q for q, _ in morceaux])
        poser(font, nom, p, chasse, codes)

    for i in range(5, 10):
        p, chasse = sups[i]
        if italique:
            p = penche([(p, False)], glyf, dx_sup)
            chasse += dchasse_sup
        poser(font, f"{CHIFFRES[i]}.sups", p, chasse)

    for cle, code in (("+", 0x207A), ("-", 0x207B)):
        p, chasse = sups[cle]
        if italique:
            p = penche([(p, False)], glyf, dx_sup)
            chasse += dchasse_sup
        poser(font, f"uni{code:04X}", p, chasse, [code])

    # numerateurs et denominateurs 5 a 9 : comme ceux de 0 a 4, des
    # composites de l'exposant
    zn = glyf["zero.numr"].components[0]
    zd = glyf["zero.dnom"].components[0]
    for i in range(5, 10):
        base = f"{CHIFFRES[i]}.sups"
        ch = font["hmtx"][base][0]
        composite(font, f"{CHIFFRES[i]}.numr", base, zn.x, zn.y, ch)
        composite(font, f"{CHIFFRES[i]}.dnom", base, zd.x, zd.y, ch)

    # exposants et indices codes
    for i in range(10):
        base = f"{CHIFFRES[i]}.sups"
        ch = font["hmtx"][base][0]
        if i in (0, 4) or i >= 5:
            composite(font, f"uni{EXPOSANTS_CODES[i]:04X}", base, 0, 0, ch, [EXPOSANTS_CODES[i]])
        dx = SLANT * INDICE_DY if italique else 0
        composite(font, f"uni{INDICES_CODES[i]:04X}", base, dx, INDICE_DY, ch, [INDICES_CODES[i]])

    # espaces typographiques et traits d'union
    mot = font["hmtx"]["space"][0]
    largeurs = {"uni2002": 500, "uni2003": 1000, "uni2007": font["hmtx"]["zero"][0],
                "uni2009": round(FINE * mot), "uni202F": round(FINE * mot)}
    for nom, code in ESPACES.items():
        _ajouter(font, nom, Glyph(), largeurs[nom], [code])
    for nom, code in TRAITS.items():
        composite(font, nom, "hyphen", 0, 0, font["hmtx"]["hyphen"][0], [code])

    # μ grec : le µ
    composite(font, "uni03BC", "uni00B5", 0, 0, font["hmtx"]["uni00B5"][0], [MU])

    for t in font["cmap"].tables:
        if t.isUnicode():
            t.cmap[VIDE] = "Oslash"

    # barre de fraction : celle des fractions toutes faites
    if "glyph249" in glyf:
        composite(font, "fraction", "glyph249", 0, 0, font["hmtx"]["glyph249"][0], [FRACTION])
    else:
        barre, chasse = barre_de_fraction(font)
        poser(font, "fraction", barre, chasse, [FRACTION])

    gsub(font)
    font["OS/2"].ulUnicodeRange2 |= (1 << (32 - 32)) | (1 << (37 - 32)) | (1 << (38 - 32))
    font.save(chemin_ttf)


def barre_de_fraction(font):
    """La barre du ½, quand le Condensed le dessine d'un bloc, sans glyph249.

    Le ½ y est un numerateur "1", la barre et un denominateur "2", poses
    comme les exposants le seraient : on retrouve leurs origines par les
    approches des exposants, et la barre se cale entre les deux, comme
    glyph249 le fait dans la largeur normale.
    """
    rec = RecordingPen()
    font.getGlyphSet()["onehalf"].draw(rec)
    contours, cur = [], None
    for op, pts in rec.value:
        if op == "moveTo":
            cur = pathops.Path()
            pen = cur.getPen()
            pen.moveTo(*pts)
        elif op in ("closePath", "endPath"):
            pen.closePath()
            contours.append(cur)
        else:
            getattr(pen, op)(*pts)
    barre = max(contours, key=lambda c: c.bounds[3] - c.bounds[1])
    autres = [c for c in contours if c is not barre]
    num = min(autres, key=lambda c: c.bounds[0])
    den = max(autres, key=lambda c: c.bounds[0])
    hm = font["hmtx"]
    fin_num = num.bounds[0] - hm["one.sups"][1] + hm["one.sups"][0]
    debut_den = den.bounds[0] - hm["two.sups"][1]
    return transforme(barre, (1, 0, 0, 1, -fin_num, 0)), round(debut_den - fin_num)


if __name__ == "__main__":
    chemins = sys.argv[1:]
    deja = [os.path.basename(c) for c in chemins if 0x2264 in TTFont(c).getBestCmap()]
    if deja:
        sys.exit(f"signes deja ajoutes dans {deja} : relancer d'abord les generateurs")
    # Tous les dessins avant toute ecriture : les italiques reprennent ceux
    # de leur romain, construits d'apres le romain intact.
    cache = {}
    for c in chemins:
        r = romain_de(c) if TTFont(c)["post"].italicAngle else c
        if r not in cache:
            cache[r] = dessins_du_romain(r)
    for c in chemins:
        r = romain_de(c) if TTFont(c)["post"].italicAngle else c
        dessins, sups = cache[r]
        avant = TTFont(c)
        n0, c0 = len(avant.getGlyphOrder()), len(avant.getBestCmap())
        appliquer(c, dessins, sups)
        apres = TTFont(c)
        print(f"   {os.path.basename(c):<34} {len(apres.getGlyphOrder()) - n0} glyphes, "
              f"{len(apres.getBestCmap()) - c0} caracteres ajoutes")
