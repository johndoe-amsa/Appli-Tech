"""
Mise en correspondance structurelle de deux contours de graisses differentes.

Pour interpoler une graisse intermediaire, chaque point du Regular doit etre
apparie au point qui lui correspond VRAIMENT dans le Bold. Un appariement
approximatif ne produit pas un resultat approximatif : il produit une bosse
ou un creux, parce qu'un point se met a voyager en travers de la lettre.

La methode : on ne se repere pas a la distance parcourue le long du contour
(deux dessins de graisses differentes ne repartissent pas leurs points de la
meme facon), mais aux POINTS STRUCTURELS, qui eux sont stables d'une graisse
a l'autre :
  - les angles      (rupture de direction : coin d'un fut, amorce d'un jambage)
  - les extrema     (sommet d'une panse, flanc gauche d'un rond)
Le haut de la panse du "p" est le haut de la panse dans les deux graisses.

On apparie donc ces reperes, puis on n'ajoute des points qu'A L'INTERIEUR
d'un intervalle deja apparie. Une erreur eventuelle reste ainsi confinee a un
petit morceau de lettre, au lieu de traverser le dessin.
"""
import math

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.qu2cuPen import Qu2CuPen

CORNER_DEG = 20.0   # au-dela, on considere que c'est un angle et non une courbe


def _lerp_pt(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def split_cubic(p0, p1, p2, p3, t):
    """Coupe une cubique en t (De Casteljau). La reunion des deux moities est
    rigoureusement identique a la courbe d'origine : le trace ne bouge pas."""
    a, b, c = _lerp_pt(p0, p1, t), _lerp_pt(p1, p2, t), _lerp_pt(p2, p3, t)
    d, e = _lerp_pt(a, b, t), _lerp_pt(b, c, t)
    m = _lerp_pt(d, e, t)
    return (p0, a, d, m), (m, e, c, p3)


def glyph_to_contours(glyph, glyf_table):
    """Glyphe TrueType (quadratique) -> contours cubiques.
    contour = {"start": point, "segs": [(ctrl1, ctrl2, arrivee), ...]}"""
    rec = RecordingPen()
    glyph.draw(Qu2CuPen(rec, max_err=0.05, all_cubic=True), glyf_table)

    contours, cur, pos = [], None, None
    for op, args in rec.value:
        if op == "moveTo":
            cur = {"start": tuple(args[0]), "segs": []}
            pos = tuple(args[0])
        elif op == "lineTo":
            end = tuple(args[0])
            cur["segs"].append((_lerp_pt(pos, end, 1 / 3.0),
                                _lerp_pt(pos, end, 2 / 3.0), end))
            pos = end
        elif op == "curveTo":
            pts = [tuple(p) for p in args]
            cur["segs"].append(tuple(pts[-3:]))
            pos = pts[-1]
        elif op == "closePath":
            if cur is not None and cur["segs"]:
                if cur["segs"][-1][2] != cur["start"]:
                    end = cur["start"]
                    cur["segs"].append((_lerp_pt(pos, end, 1 / 3.0),
                                        _lerp_pt(pos, end, 2 / 3.0), end))
                contours.append(cur)
            cur = None
    # contours degeneres (surface nulle) : scories du dessin d'origine
    return [c for c in contours if len(c["segs"]) > 1]


# --------------------------------------------------------------------------
# reperes structurels
# --------------------------------------------------------------------------

def anchors(c):
    """Les points d'ancrage (on-curve) du contour, dans l'ordre."""
    return [c["start"]] + [s[2] for s in c["segs"][:-1]]


def _tangents(c, j):
    """Directions d'arrivee et de depart au point d'ancrage j."""
    segs, n = c["segs"], len(c["segs"])
    a = anchors(c)[j]
    si, so = segs[(j - 1) % n], segs[j]
    p = si[1] if si[1] != a else si[0]
    q = so[0] if so[0] != a else so[1]
    return (a[0] - p[0], a[1] - p[1]), (q[0] - a[0], q[1] - a[1])


def feature_type(c, j):
    """None si le point est 'au milieu d'une courbe', sinon son type."""
    tin, tout = _tangents(c, j)
    ni, no = math.hypot(*tin), math.hypot(*tout)
    if ni < 1e-9 or no < 1e-9:
        return "corner"
    cosang = max(-1.0, min(1.0, (tin[0] * tout[0] + tin[1] * tout[1]) / (ni * no)))
    if math.degrees(math.acos(cosang)) > CORNER_DEG:
        return "corner"
    # Extremum : changement de signe de la tangente, OU tangente parallele a
    # l'axe. Au sommet d'un ovale la tangente est exactement horizontale, donc
    # la composante y vaut ZERO des deux cotes : tester le seul changement de
    # signe laisse passer les quatre extrema de toute contreforme ronde.
    if tin[1] * tout[1] < 0 or (abs(tin[1]) < 0.08 * ni and abs(tout[1]) < 0.08 * no):
        return "yext"
    if tin[0] * tout[0] < 0 or (abs(tin[0]) < 0.08 * ni and abs(tout[0]) < 0.08 * no):
        return "xext"
    return None


RANG = {"corner": 2, "yext": 1, "xext": 1}
ECART_MINI = 15.0   # unites ; en-deca, deux reperes n'en font qu'un


def feature_indices(c):
    """Reperes structurels du contour, debarrasses des micro-reperes.

    Un bord de terminal quasi vertical produit un extremum a 3 unites de
    l'angle voisin : c'est un artefact du trace, pas une articulation de la
    lettre. L'italique, dont le terminal est coupe autrement, n'a pas le sien
    au meme endroit - l'apparieur mariait alors ces faux reperes a des points
    situes ailleurs dans la lettre, d'ou l'encoche observee sur le "e" et le
    "c". On fusionne donc les reperes distants de moins de 15 unites, en
    gardant le plus fort : un angle l'emporte sur un extremum.
    """
    bruts = [j for j in range(len(c["segs"])) if feature_type(c, j)]
    if len(bruts) < 2:
        return bruts
    A = anchors(c)
    gardes = []
    for j in bruts:
        if gardes and math.dist(A[j], A[gardes[-1]]) < ECART_MINI:
            if RANG[feature_type(c, j)] > RANG[feature_type(c, gardes[-1])]:
                gardes[-1] = j
            continue
        gardes.append(j)
    # le contour est ferme : verifier aussi le voisinage dernier / premier
    if len(gardes) > 2 and math.dist(A[gardes[0]], A[gardes[-1]]) < ECART_MINI:
        if RANG[feature_type(c, gardes[0])] >= RANG[feature_type(c, gardes[-1])]:
            gardes.pop()
        else:
            gardes.pop(0)
    return gardes


def rotate(c, k):
    """Fait demarrer le contour a son point d'ancrage k (trace inchange)."""
    n = len(c["segs"])
    k %= n
    if k == 0:
        return c
    return {"start": anchors(c)[k], "segs": c["segs"][k:] + c["segs"][:k]}


def _centroid(c):
    p = anchors(c)
    return (sum(q[0] for q in p) / len(p), sum(q[1] for q in p) / len(p))


def match_contours(ca, cb):
    """Reordonne cb pour que chaque contour fasse face a son homologue dans ca.

    Necessaire : rien ne garantit que les deux dessins enumerent leurs contours
    dans le meme ordre. Apparier la panse d'un "o" avec sa contreforme detruit
    le glyphe.
    """
    if len(ca) != len(cb) or len(ca) < 2:
        return cb
    libres, out = list(range(len(cb))), []
    for x in ca:
        cx, ax = _centroid(x), abs(_area(x))
        best, bi = None, None
        for i in libres:
            y = cb[i]
            cy, ay = _centroid(y), abs(_area(y))
            d = math.hypot(cy[0] - cx[0], cy[1] - cx[1])
            d += 200.0 * abs(ax - ay) / max(ax, ay, 1.0)
            if best is None or d < best:
                best, bi = d, i
        libres.remove(bi)
        out.append(cb[bi])
    return out


def _area(c):
    p = anchors(c)
    s = 0.0
    for i in range(len(p)):
        x0, y0 = p[i]
        x1, y1 = p[(i + 1) % len(p)]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def replay(contour, journal):
    """Rejoue sur un troisieme dessin les operations subies par un master.

    Necessaire pour les italiques : le droit-Regular doit etre harmonise
    d'abord avec l'italique, puis avec le droit-Bold. La seconde passe ajoute
    des points au droit-Regular ; sans rejeu, l'italique ne serait plus aligne
    sur lui et les ecarts de graisse s'appliqueraient de travers.
    """
    for op in journal:
        if op[0] == "rotate":
            r = rotate(contour, op[1])
            contour["start"], contour["segs"] = r["start"], r["segs"]
        elif op[0] == "split":
            insert_anchor(contour, op[1], op[2])
    return contour


def insert_anchor(contour, seg_index, t=0.5):
    segs = contour["segs"]
    p0 = contour["start"] if seg_index == 0 else segs[seg_index - 1][2]
    p1, p2, p3 = segs[seg_index]
    left, right = split_cubic(p0, p1, p2, p3, t)
    segs[seg_index:seg_index + 1] = [left[1:], right[1:]]


def _chord(contour, i):
    p0 = contour["start"] if i == 0 else contour["segs"][i - 1][2]
    p3 = contour["segs"][i][2]
    return math.hypot(p3[0] - p0[0], p3[1] - p0[1])


def _jalons(contour, lo, hi):
    """Positions normalisees (0..1) des points d'ancrage internes a l'intervalle."""
    L = [_chord(contour, k) for k in range(lo, hi)]
    tot = sum(L)
    if tot <= 0 or len(L) < 2:
        return []
    out, acc = [], 0.0
    for k in range(len(L) - 1):
        acc += L[k]
        out.append(acc / tot)
    return out


def _localiser(contour, lo, hi, p):
    """Segment et parametre local correspondant a la position normalisee p."""
    L = [_chord(contour, k) for k in range(lo, hi)]
    tot = sum(L)
    if tot <= 0:
        return lo, 0.5
    cible, acc = p * tot, 0.0
    for m, l in enumerate(L):
        if acc + l >= cible or m == len(L) - 1:
            t = (cible - acc) / l if l > 1e-9 else 0.5
            return lo + m, min(0.9, max(0.1, t))
        acc += l
    return hi - 1, 0.5


def _grow_span(contour, lo, hi, target, journal=None, ref=None, rlo=0, rhi=0):
    """Amene l'intervalle [lo, hi) a `target` segments.

    Les points ajoutes sont places A LA POSITION QU'ILS OCCUPENT dans l'autre
    master, et non au milieu du plus long segment. La difference n'est pas
    theorique : le terminal du "e" romain porte deux ergots verticaux de 3 et
    5 unites que l'italique n'a pas. Couper "le plus long au milieu" envoyait
    ces deux points au fond de la courbe, a 120 unites de leur place, et
    l'ecart de graisse destine au terminal y creusait une encoche.
    """
    while hi - lo < target:
        jalons_ref = _jalons(ref, rlo, rhi) if ref is not None else []
        if jalons_ref:
            miens = _jalons(contour, lo, hi)
            # la position de reference la plus mal couverte par les miennes
            p = max(jalons_ref,
                    key=lambda x: min((abs(x - q) for q in miens), default=1.0))
            j, t = _localiser(contour, lo, hi, p)
        else:
            j = max(range(lo, hi), key=lambda k: _chord(contour, k))
            t = 0.5
        insert_anchor(contour, j, t)
        if journal is not None:
            journal.append(("split", j, t))
        hi += 1
    return hi


def _norm(c):
    """Ancres ramenees dans un carre unite : compare des formes, pas des tailles.
    Indispensable, le Bold etant plus large que le Regular."""
    p = anchors(c)
    xs = [q[0] for q in p]; ys = [q[1] for q in p]
    w = max(max(xs) - min(xs), 1.0); h = max(max(ys) - min(ys), 1.0)
    return [((q[0] - min(xs)) / w, (q[1] - min(ys)) / h) for q in p]


def match_features(ca, cb, fa, fb):
    """Apparie les reperes des deux contours en respectant leur ordre.

    Les deux dessins n'ont pas forcement le meme nombre de reperes : le "g"
    du Regular a un extremum la ou le Bold a un angle. On retient alors le
    plus grand sous-ensemble appariable, dans l'ordre, et les reperes en trop
    redeviennent de simples points interieurs a un intervalle.
    """
    NA, NB = _norm(ca), _norm(cb)
    swap = len(fa) > len(fb)
    if swap:
        fa, fb, NA, NB = fb, fa, NB, NA
    m, n = len(fa), len(fb)
    if m == 0 or n == 0:
        return None
    cout = [[math.hypot(NA[fa[i]][0] - NB[fb[j]][0],
                        NA[fa[i]][1] - NB[fb[j]][1]) for j in range(n)]
            for i in range(m)]

    meilleur = None
    for r in range(n):                      # fa[0] essaye chaque repere de fb
        ordre = [(r + k) % n for k in range(n)]
        INF = float("inf")
        dp = [[INF] * n for _ in range(m)]
        prev = [[-1] * n for _ in range(m)]
        dp[0][0] = cout[0][ordre[0]]
        for i in range(1, m):
            best_j, best_v = -1, INF
            for j in range(i, n):
                if dp[i - 1][j - 1] < best_v:
                    best_v, best_j = dp[i - 1][j - 1], j - 1
                if best_v < INF:
                    dp[i][j] = best_v + cout[i][ordre[j]]
                    prev[i][j] = best_j
        for j in range(m - 1, n):
            if dp[m - 1][j] < INF and (meilleur is None or dp[m - 1][j] < meilleur[0]):
                chemin, jj = [], j
                for i in range(m - 1, -1, -1):
                    chemin.append(jj)
                    jj = prev[i][jj] if i else -1
                chemin.reverse()
                meilleur = (dp[m - 1][j], [(fa[i], fb[ordre[chemin[i]]])
                                           for i in range(m)])
    if meilleur is None:
        return None
    paires = meilleur[1]
    return [(y, x) for x, y in paires] if swap else paires


def harmonize_pair(ca, cb, journal=None):
    """Rend deux contours structurellement identiques. Modifie sur place.

    `journal` : si une liste est fournie, on y consigne les operations subies
    par `ca`, afin de pouvoir les rejouer sur un dessin parallele (voir replay).
    """
    fa, fb = feature_indices(ca), feature_indices(cb)
    paires = match_features(ca, cb, fa, fb) if (fa and fb) else None

    if paires and len(paires) >= 2:
        ka, kb = paires[0]
        if journal is not None:
            journal.append(("rotate", ka))
        ca_r, cb_r = rotate(ca, ka), rotate(cb, kb)
        na, nb = len(ca["segs"]), len(cb["segs"])
        bornes_a = sorted((x - ka) % na for x, _ in paires)
        bornes_b = sorted((y - kb) % nb for _, y in paires)
    else:
        ca_r, cb_r = ca, cb
        bornes_a, bornes_b = [0], [0]

    ca["start"], ca["segs"] = ca_r["start"], ca_r["segs"]
    cb["start"], cb["segs"] = cb_r["start"], cb_r["segs"]

    if len(bornes_a) != len(bornes_b) or bornes_a[0] != 0 or bornes_b[0] != 0:
        bornes_a, bornes_b = [0], [0]

    # du dernier intervalle au premier : couper dans l'un decale les suivants
    bornes_a = bornes_a + [len(ca["segs"])]
    bornes_b = bornes_b + [len(cb["segs"])]
    for i in range(len(bornes_a) - 2, -1, -1):
        la, ha = bornes_a[i], bornes_a[i + 1]
        lb, hb = bornes_b[i], bornes_b[i + 1]
        cible = max(ha - la, hb - lb)
        _grow_span(ca, la, ha, cible, journal, ref=cb, rlo=lb, rhi=hb)
        _grow_span(cb, lb, hb, cible, None, ref=ca, rlo=la, rhi=ha)

    return len(ca["segs"]) == len(cb["segs"])
