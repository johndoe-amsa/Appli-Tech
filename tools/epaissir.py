"""
Epaississement (ou amaigrissement) d'un contour, sans master de reference.

Sert aux rares glyphes dont l'italique n'est pas le romain retouche mais une
LETTRE DIFFERENTE : le "a" romain a deux etages, le "ɑ" italique un seul. Il
n'existe alors aucune correspondance point a point entre les deux, et le
report d'ecart de graisse ne veut rien dire.

On deplace donc chaque point perpendiculairement au trace, d'une distance
calibree pour que le fut obtenu egale celui des autres lettres de la meme
graisse. La lettre garde exactement sa forme ; seule son epaisseur change.

Le travail se fait dans le repere DROIT (italique redresse), pour que la
distance mesuree soit comparable a celle des romains.
"""
import math


def _points(c):
    """Suite cyclique de tous les points du contour, controles compris."""
    pts = [c["start"]]
    for sg in c["segs"][:-1]:
        pts.extend(sg)
    pts.extend(c["segs"][-1][:2])       # le dernier point d'arrivee = start
    return pts


def _rebuild(c, pts):
    n = len(c["segs"])
    start = pts[0]
    segs = []
    for k in range(n):
        i = 1 + 3 * k
        if k < n - 1:
            segs.append((pts[i], pts[i + 1], pts[i + 2]))
        else:
            segs.append((pts[i], pts[i + 1], start))
    return {"start": start, "segs": segs}


def _aire(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def _normale(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None
    return (-dy / L, dx / L)          # normale a gauche du sens de parcours


def _decaler(pts, d, limite=2.5):
    """Deplace chaque point de d le long de la normale, avec onglet aux angles."""
    n = len(pts)
    out = []
    for i in range(n):
        p = pts[i]
        n1 = _normale(pts[(i - 1) % n], p)
        n2 = _normale(p, pts[(i + 1) % n])
        if n1 is None and n2 is None:
            out.append(p)
            continue
        if n1 is None:
            n1 = n2
        if n2 is None:
            n2 = n1
        sx, sy = n1[0] + n2[0], n1[1] + n2[1]
        L = math.hypot(sx, sy)
        if L < 1e-6:                   # rebroussement : on ne touche pas
            out.append(p)
            continue
        ux, uy = sx / L, sy / L
        # onglet : sur un angle vif, il faut aller plus loin que d pour que les
        # deux flancs decales se rejoignent
        cos = ux * n1[0] + uy * n1[1]
        k = 1.0 / max(1.0 / limite, abs(cos))
        out.append((p[0] + ux * d * k, p[1] + uy * d * k))
    return out


def _bornes_y(contours):
    ys = [p[1] for c in contours for p in _points(c)]
    return min(ys), max(ys)


def _recaler_y(contours, y0, y1):
    """Ramene le glyphe a sa hauteur d'origine.

    Un decalage uniforme fait grandir la lettre dans toutes les directions :
    le "a" epaissi depasserait la hauteur d'x de ses voisines. Un vrai gras
    garde la meme hauteur d'x - ses barres horizontales epaississent vers
    l'interieur, en mangeant la contreforme. La recompression verticale
    reproduit ce comportement.
    """
    a, b = _bornes_y(contours)
    if b - a < 1e-6:
        return contours
    k = (y1 - y0) / (b - a)
    def f(p):
        return (p[0], y0 + (p[1] - a) * k)
    return [{"start": f(c["start"]),
             "segs": [tuple(f(q) for q in sg) for sg in c["segs"]]}
            for c in contours]


def _bornes_x(contours):
    xs = [p[0] for c in contours for p in _points(c)]
    return min(xs), max(xs)


def _recaler_x(contours, x0, x1):
    a, b = _bornes_x(contours)
    if b - a < 1e-6:
        return contours
    k = (x1 - x0) / (b - a)
    def f(p):
        return (x0 + (p[0] - a) * k, p[1])
    return [{"start": f(c["start"]),
             "segs": [tuple(f(q) for q in sg) for sg in c["segs"]]}
            for c in contours]


def epaissir(contours, d, largeur_cible=None, hauteur_cible=None):
    """d > 0 epaissit, d < 0 amaigrit. La hauteur du glyphe est preservee.

    `largeur_cible` : (x_min, x_max) vise. Un vrai gras n'est pas seulement
    plus epais, il est aussi plus LARGE ; sans cette consigne le glyphe
    epaissi reste trop etroit a cote de ses voisines.

    `hauteur_cible` : (y_min, y_max) vise. De meme, les rondes d'un gras
    debordent un peu plus de la hauteur d'x ; a defaut, le glyphe epaissi
    serait legerement plus court que ses voisines.
    """
    if abs(d) < 1e-6:
        return contours
    y0, y1 = _bornes_y(contours)
    listes = [_points(c) for c in contours]
    total = sum(_aire(p) for p in listes)
    sens = 1.0 if total < 0 else -1.0   # on veut que l'encre augmente
    out = []
    for c, pts in zip(contours, listes):
        out.append(_rebuild(c, _decaler(pts, d * sens)))
    # verification : si l'encre a diminue alors qu'on epaississait, on s'est
    # trompe de sens ; on recommence a l'envers.
    neuf = sum(_aire(_points(c)) for c in out)
    if (abs(neuf) - abs(total)) * d < 0:
        out = [_rebuild(c, _decaler(p, -d * sens)) for c, p in zip(contours, listes)]
    out = _recaler_y(out, *(hauteur_cible if hauteur_cible else (y0, y1)))
    if largeur_cible is not None:
        out = _recaler_x(out, largeur_cible[0], largeur_cible[1])
    return out
