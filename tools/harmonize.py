"""
Harmonisation de contours entre deux masters de graisse differente.

Pour interpoler une graisse intermediaire (ex. Medium entre Regular et Bold),
les deux dessins doivent avoir EXACTEMENT la meme structure de points.
Dans D-DIN ce n'est vrai que pour 66% des glyphes.

Ce module rend les contours compatibles en inserant des points la ou il en
manque, sans modifier le trace : on coupe une courbe en deux au bon endroit
(algorithme de De Casteljau), ce qui donne deux courbes dont la reunion est
rigoureusement identique a la courbe d'origine.
"""
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.qu2cuPen import Qu2CuPen


def _lerp_pt(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def split_cubic(p0, p1, p2, p3, t):
    """Coupe une courbe cubique en t. Retourne les deux moities."""
    a, b, c = _lerp_pt(p0, p1, t), _lerp_pt(p1, p2, t), _lerp_pt(p2, p3, t)
    d, e = _lerp_pt(a, b, t), _lerp_pt(b, c, t)
    m = _lerp_pt(d, e, t)
    return (p0, a, d, m), (m, e, c, p3)


def glyph_to_contours(glyph, glyf_table):
    """Convertit un glyphe TrueType (quadratique) en contours cubiques.

    Chaque contour = {"start": point, "segs": [(p1, p2, p3), ...]}
    Toutes les portions sont des cubiques : une ligne droite est encodee
    comme une cubique dont les controles sont sur le segment.
    """
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
    # On ecarte les contours degeneres (surface nulle) : ce sont des scories
    # laissees dans le dessin d'origine, invisibles a l'impression, mais qui
    # faussent la comparaison de structure entre les deux masters.
    return [c for c in contours if len(c["segs"]) > 1]


def _anchor_positions(contour):
    """Position normalisee [0,1] de chaque point d'ancrage, par longueur de corde."""
    pts = [contour["start"]] + [s[2] for s in contour["segs"]]
    lens, total = [], 0.0
    for i in range(len(pts) - 1):
        dx, dy = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        d = (dx * dx + dy * dy) ** 0.5
        lens.append(d)
        total += d
    if total == 0:
        return [0.0] * len(contour["segs"])
    out, acc = [], 0.0
    for d in lens:
        acc += d
        out.append(acc / total)
    return out  # une position par segment (celle de son point d'arrivee)


def insert_anchor(contour, seg_index, t):
    """Coupe le segment seg_index en t, ajoutant un point d'ancrage."""
    segs = contour["segs"]
    p0 = contour["start"] if seg_index == 0 else segs[seg_index - 1][2]
    p1, p2, p3 = segs[seg_index]
    left, right = split_cubic(p0, p1, p2, p3, t)
    segs[seg_index:seg_index + 1] = [left[1:], right[1:]]


def harmonize_pair(ca, cb):
    """Rend deux contours structurellement identiques. Modifie sur place.

    Le contour qui a le moins de points recoit des points supplementaires,
    places a la position (en longueur de corde) qui correspond aux points
    en trop de l'autre contour.
    """
    guard = 0
    while len(ca["segs"]) != len(cb["segs"]):
        guard += 1
        if guard > 60:
            return False
        short, long_ = (ca, cb) if len(ca["segs"]) < len(cb["segs"]) else (cb, ca)
        pos_s, pos_l = _anchor_positions(short), _anchor_positions(long_)
        # on cherche le point du contour long qui n'a pas de correspondant proche
        best_i, best_gap = None, -1.0
        for i, pl in enumerate(pos_l):
            gap = min(abs(pl - ps) for ps in pos_s) if pos_s else 1.0
            if gap > best_gap:
                best_gap, best_i = gap, i
        target = pos_l[best_i]
        # dans quel segment du contour court tombe cette position ?
        seg_i, prev = 0, 0.0
        for i, ps in enumerate(pos_s):
            if target <= ps:
                seg_i = i
                break
            prev = ps
        else:
            seg_i, prev = len(pos_s) - 1, pos_s[-2] if len(pos_s) > 1 else 0.0
        span = pos_s[seg_i] - prev
        t = (target - prev) / span if span > 1e-9 else 0.5
        insert_anchor(short, seg_i, min(0.92, max(0.08, t)))
    return True
