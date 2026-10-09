"""
Generateur d'italiques pour la famille Appli-Tec.

D-DIN ne fournit qu'UN seul italique, en graisse Regular. Il faut en deduire
les quatre autres.

La tentation serait de simplement pencher les droits de 12 degres. Ce serait
une erreur : l'italique de D-DIN n'est pas un penchage mecanique. Sur 169
glyphes comparables, 64 ont ete REDESSINES par le dessinateur apres penchage
- les rondes surtout (a, e, g, s, 0, 2, 3). Les pencher betement reviendrait
a jeter ce travail.

Methode retenue - report d'ecart :

    italique(w) = italique(400) + cisaillement( ecart de graisse w )

ou l'ecart de graisse est mesure sur l'axe droit, entre Regular et Bold. On
applique donc a l'italique existant exactement la variation d'epaisseur du
droit, penchee de 12 degres. Les corrections du dessinateur sont conservees.

Cela suppose que les trois dessins - droit Regular, droit Bold, italique -
partagent une meme structure de points. On y parvient en deux passes :
  1. harmoniser droit-Regular avec l'italique ;
  2. harmoniser le resultat avec droit-Bold, en journalisant les operations,
     puis les rejouer sur l'italique pour qu'il reste aligne.
"""
import sys, os, copy, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from harmonize import (glyph_to_contours, harmonize_pair, match_contours,
                       replay, anchors, lisser)
from build import interp_contours, interp_mismatched, recaler_marges, draw_contours, sans_scories
import naming

SLANT = math.tan(math.radians(12.0))     # 0.21256
ORIGINE = 254.1   # hauteur autour de laquelle le dessinateur a penche (mesuree)
SEUIL_RESIDU = 45.0   # au-dela, romain et italique ne sont plus la meme lettre
SEUIL_PIRE = 120.0    # ecart du point le plus mal apparie ; meme sens

# Penches depuis le romain, quoi qu'en dise l'appariement :
#  - les operateurs, que D-DIN Italic laisse DROITS. A l'Italic 400 ils
#    detonnaient au milieu du texte penche ; aux autres graisses, l'ecart de
#    graisse penche leur taillait des bouts obliques et tordait le "×".
#  - les guillemets, que D-DIN Italic obtient par simple cisaillement des
#    droits : voir chevrons_egaux.
#  - "0", "3", "5", "C" et "Ç" : le dessinateur les a a peine retouches, et ses
#    retouches y ont mis des defauts. Le bord interieur du terminal bas du
#    "3" et du "5" reste vertical et rejoint la courbe en faisant un angle ;
#    le bout du "C" est bossele. Penches depuis le romain, ils sont lisses.
PENCHES = {"three", "five", "C", "Ccedilla", "zero",
           "plus", "less", "equal", "greater", "asciicircum", "multiply",
           "divide", "plusminus", "logicalnot", "underscore",
           "guillemotleft", "guillemotright", "guilsinglleft", "guilsinglright"}
CHEVRONS = {"guillemotleft", "guillemotright", "guilsinglleft", "guilsinglright",
            "less", "greater", "asciicircum"}


def redresser(contours):
    """Inverse de `pencher` : ramene l'italique a la verticale.

    Indispensable AVANT tout appariement avec le romain. Le cisaillement
    detruit les extrema horizontaux - un point a tangente verticale ne l'est
    plus une fois penche de 12 degres - si bien qu'un italique et son romain
    n'exposent pas les memes reperes structurels. Compares tels quels, le "e"
    affiche 13 reperes d'un cote et 10 de l'autre, et rien ne s'aligne.
    Redresse, il en montre autant des deux cotes.
    """
    def f(p):
        return (p[0] - SLANT * (p[1] - ORIGINE), p[1])
    return [{"start": f(c["start"]),
             "segs": [tuple(f(q) for q in sg) for sg in c["segs"]]}
            for c in contours]


def pencher(contours):
    """Cisaillement mecanique reproduisant celui du dessinateur :
    x' = x + tan(12 deg) x (y - 254.1). Sert de repli pour les rares glyphes
    dont la topologie differe entre Regular et Bold ($ et cent, dont les
    contreformes fusionnent dans le gras)."""
    def f(p):
        return (p[0] + SLANT * (p[1] - ORIGINE), p[1])
    return [{"start": f(c["start"]),
             "segs": [tuple(f(q) for q in sg) for sg in c["segs"]]}
            for c in contours]


def _inter(p, d, q, e):
    """Intersection des droites (p, direction d) et (q, direction e)."""
    det = d[0] * e[1] - d[1] * e[0]
    if abs(det) < 1e-12:
        return None
    k = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / det
    return (p[0] + d[0] * k, p[1] + d[1] * k)


TOURNES = {"multiply"}
RECALES = {"percent", "perthousand"}   # voir recaler


def tourner(contours):
    """Le "×" reste droit, deplace comme le serait le texte penche.

    Cisaille, il garde deux bras epais et deux bras minces ; tourne de
    l'angle de l'italique, il ressemble a un "+" de travers. Symetrique, il
    n'a pas d'inclinaison a montrer.
    """
    pts = [c["start"] for c in contours] + [q for c in contours for sg in c["segs"] for q in sg]
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    co, si = 1.0, 0.0
    dx = SLANT * (cy - ORIGINE)

    def f(p):
        x, y = p[0] - cx, p[1] - cy
        return (cx + dx + x * co - y * si, cy + x * si + y * co)
    return [{"start": f(c["start"]), "segs": [tuple(f(q) for q in sg) for sg in c["segs"]]}
            for c in contours]


def recaler(cU, cB, cI, t):
    """Le "%" et le "‰" : le trace du romain, aux places de l'italique.

    L'italique est ici un vrai redessin, plus etroit que le romain penche.
    Mais le dessinateur a ajoute dans ses contreformes des points que le
    romain n'a pas ; a travers la double correspondance romain - italique -
    gras, ils cabossaient les zeros du Bold et du Heavy Italic. On prend donc
    le romain a la graisse voulue (propre, comme le Bold romain d'origine),
    et l'on loge chaque contour dans la boite du contour correspondant de
    l'italique redresse : places et proportions de l'italique, trace du
    romain. Le resultat reste a pencher.
    """
    def boite(c):
        pts = [c["start"]] + [sg[2] for sg in c["segs"]]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    if not (len(cU) == len(cB) == len(cI)) or not cU:
        return None
    droit = droit_a_la_graisse(copy.deepcopy(cU), copy.deepcopy(cB), t)
    if not droit or len(droit) != len(cU):
        return None
    out = []
    for u, i, d in zip(cU, cI, droit):
        ux0, uy0, ux1, uy1 = boite(u)
        ix0, iy0, ix1, iy1 = boite(i)
        sx = (ix1 - ix0) / max(ux1 - ux0, 1e-6)
        sy = (iy1 - iy0) / max(uy1 - uy0, 1e-6)
        # centre a centre : l'epaississement deborde la boite du Regular
        ucx, ucy = (ux0 + ux1) / 2, (uy0 + uy1) / 2
        icx, icy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
        f = lambda p: (icx + (p[0] - ucx) * sx, icy + (p[1] - ucy) * sy)
        out.append({"start": f(d["start"]),
                    "segs": [tuple(f(q) for q in sg) for sg in d["segs"]]})
    return out


def chevrons_egaux(glyph, glyf):
    """Redonne aux deux branches d'un chevron penche la meme epaisseur
    (guillemets, < > ^).

    Cisailler un chevron droit aplatit et amincit la branche montante, et
    redresse et epaissit la descendante. On garde le bord exterieur et la
    coupe des extremites du chevron penche, et l'on retrace chaque bord
    interieur parallele a son bord exterieur, a l'epaisseur du romain.

    Le chevron se lit a partir de son seul point rentrant, le creux : de
    part et d'autre, le bord interieur mene a la coupe, puis le bord
    exterieur repart vers la pointe (plate ou non).
    """
    coords, ends, flags = glyph.getCoordinates(glyf)
    if any(not f & 1 for f in flags):
        return glyph
    pts = [tuple(p) for p in coords]
    neufs, debut = list(pts), 0
    for fin in ends:
        idx = list(range(debut, fin + 1))
        debut = fin + 1
        n = len(idx)
        if n not in (6, 7):
            continue
        droit = {i: (pts[i][0] - SLANT * (pts[i][1] - ORIGINE), pts[i][1]) for i in idx}
        aire = sum(droit[idx[k]][0] * droit[idx[(k + 1) % n]][1]
                   - droit[idx[(k + 1) % n]][0] * droit[idx[k]][1] for k in range(n))

        def tour(k):
            p0, p1, p2 = (droit[idx[(k + d) % n]] for d in (-1, 0, 1))
            return (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
        rentrants = [k for k in range(n) if tour(k) * aire < 0]
        if len(rentrants) != 1:
            continue
        kv = rentrants[0]
        V = idx[kv]
        bras = []
        for sens in (1, -1):
            A2, A, Ta = (idx[(kv + sens * d) % n] for d in (1, 2, 3))
            (x0, y0), (x1, y1), (x, y) = droit[A], droit[Ta], droit[V]
            w = abs((x - x0) * (y1 - y0) - (y - y0) * (x1 - x0)) / math.hypot(x1 - x0, y1 - y0)
            d = (pts[Ta][0] - pts[A][0], pts[Ta][1] - pts[A][1])
            L = math.hypot(*d)
            nrm = (-d[1] / L, d[0] / L)
            vx, vy = pts[V][0] - pts[A][0], pts[V][1] - pts[A][1]
            if nrm[0] * vx + nrm[1] * vy < 0:
                nrm = (-nrm[0], -nrm[1])
            o = (pts[A][0] + nrm[0] * w, pts[A][1] + nrm[1] * w)
            coupe = (pts[A2][0] - pts[A][0], pts[A2][1] - pts[A][1])
            p = _inter(o, d, pts[A], coupe)
            if p is None:
                break
            neufs[A2] = p
            bras.append((o, d))
        if len(bras) != 2:
            continue
        v = _inter(bras[0][0], bras[0][1], bras[1][0], bras[1][1])
        if v is not None:
            neufs[V] = v
    g = copy.deepcopy(glyph)
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    g.coordinates = GlyphCoordinates([(int(round(x)), int(round(y))) for x, y in neufs])
    g.recalcBounds(glyf)
    return g


def droit_a_la_graisse(cU, cB, t):
    """Le droit interpole a la graisse t, topologies divergentes comprises."""
    if not cU or not cB:
        return None
    if len(cU) == len(cB):
        # Harmoniser TOUJOURS, comme pour les romains : meme nombre de points
        # ne veut pas dire meme point de depart. Sans cela, le "5" Medium
        # Italic, tire du romain, se dechirait.
        A, B = copy.deepcopy(cU), copy.deepcopy(cB)
        if all(harmonize_pair(x, y) for x, y in zip(A, B)):
            return lisser(interp_contours(A, B, t), [A, B])
    return interp_mismatched(cU, cB, t)


def _report(pu, pb, pi, t):
    """Composites : l'ecart d'un decalage de composant se penche lineairement."""
    dx = (pb[0] - pu[0]) * t
    dy = (pb[1] - pu[1]) * t
    return (pi[0] + dx + SLANT * dy, pi[1] + dy)


def _ecart(pu, pb, pi, t):
    """Repere droit : italique redresse + t x ecart de graisse du romain."""
    return (pi[0] + (pb[0] - pu[0]) * t, pi[1] + (pb[1] - pu[1]) * t)


def residu(cU, cI):
    """Ecart median entre l'italique redresse et le romain, apres appariement.
    Eleve = les deux dessins ne representent pas la meme lettre (le "a" romain
    a deux etages, l'italique un seul) : le report d'ecart n'a alors aucun sens.
    """
    d = []
    for u, i in zip(cU, cI):
        for pu, pi in zip(anchors(u), anchors(i)):
            d.append(math.hypot(pi[0] - pu[0], pi[1] - pu[1]))
    return sorted(d)[len(d) // 2] if d else 0.0


def pire(cU, cI):
    """Ecart du point le plus mal apparie. La mediane ne suffit pas : le "ª"
    italique (un etage) et le romain (deux etages) partagent assez de points
    pour une mediane basse, mais la panse du romain n'a pas d'homologue, a
    180 unites de la, et l'epaississement en faisait un pate."""
    d = [math.hypot(pi[0] - pu[0], pi[1] - pu[1])
         for u, i in zip(cU, cI) for pu, pi in zip(anchors(u), anchors(i))]
    return max(d) if d else 0.0


def aligner(cU, cB, cI):
    """Amene les trois jeux de contours a une structure de points commune."""
    if not (len(cU) == len(cB) == len(cI)) or not cU:
        return False
    for u, i in zip(cU, cI):                       # passe 1 : droit <-> italique
        if not harmonize_pair(u, i):
            return False
    for u, b, i in zip(cU, cB, cI):                # passe 2 : droit <-> gras
        j = []
        if not harmonize_pair(u, b, journal=j):
            return False
        replay(i, j)                               # l'italique suit le mouvement
        if not (len(u["segs"]) == len(b["segs"]) == len(i["segs"])):
            return False
    return True


def build_italic(t, weight_class, style, out_path,
                 upright="sources/upstream-d-din/D-DIN.ttf",
                 bold="sources/upstream-d-din/D-DIN-Bold.ttf",
                 italic="sources/upstream-d-din/D-DIN-Italic.ttf"):
    U, B, I = TTFont(upright), TTFont(bold), TTFont(italic)
    # calibrage de l'epaississeur : demi-ecart de fut entre Regular et Bold
    from fontTools.pens.boundsPen import BoundsPen
    def _fut(f):
        gs = f.getGlyphSet(); bp = BoundsPen(gs)
        gs[f.getBestCmap()[ord("I")]].draw(bp)
        return bp.bounds[2] - bp.bounds[0]
    demi_ecart = (_fut(B) - _fut(U)) / 2.0
    gU, gB, gI = U["glyf"], B["glyf"], I["glyf"]
    hU, hB, hI = U["hmtx"], B["hmtx"], I["hmtx"]

    stats = {"report": 0, "composite": 0, "repli": []}
    neufs, largeurs = {}, {}

    for name in I.getGlyphOrder():
        if name not in gU or name not in gB:
            neufs[name] = gI[name]
            largeurs[name] = hI[name]
            continue

        A, Bg, Ig = gU[name], gB[name], gI[name]
        aw = int(round(hI[name][0] + (hB[name][0] - hU[name][0]) * t))

        if (A.isComposite() and Bg.isComposite() and Ig.isComposite()
                and len(A.components) == len(Bg.components) == len(Ig.components)
                and A.components[0].glyphName == Bg.components[0].glyphName):
            g = copy.deepcopy(Ig)
            for cc, ca, cb in zip(g.components, A.components, Bg.components):
                if hasattr(cc, "x") and hasattr(ca, "x") and hasattr(cb, "x"):
                    x, y = _report((ca.x, ca.y), (cb.x, cb.y), (cc.x, cc.y), t)
                    cc.x, cc.y = int(round(x)), int(round(y))
            neufs[name] = g
            largeurs[name] = (aw, hI[name][1])
            stats["composite"] += 1
            continue

        if Ig.numberOfContours == 0:
            neufs[name] = Ig
            largeurs[name] = (aw, hI[name][1])
            continue

        cU = glyph_to_contours(A, gU)
        cB = match_contours(cU, glyph_to_contours(Bg, gB))
        cI = match_contours(cU, redresser(glyph_to_contours(Ig, gI)))

        if name in RECALES:
            droit = recaler(cU, cB, cI, t)
            if droit:
                pen = TTGlyphPen(None)
                draw_contours(pencher(droit), pen)
                neufs[name] = pen.glyph()
                largeurs[name] = (aw, hI[name][1])
                stats["report"] += 1
                continue

        alignable = aligner(cU, cB, cI)
        if (not alignable or residu(cU, cI) > SEUIL_RESIDU
                or pire(cU, cI) > SEUIL_PIRE or name in PENCHES):
            # Soit les topologies divergent ($ et cent, dont les contreformes
            # fusionnent dans le gras), soit romain et italique ne sont pas la
            # meme lettre (le "a" romain a deux etages, l'italique un seul).
            # Dans les deux cas on prend le ROMAIN a la bonne graisse et on le
            # penche. Choix de l'atelier : on renonce provisoirement a la forme
            # italique propre de ces glyphes, quitte a la redessiner plus tard.
            # tools/epaissir.py reste disponible pour cette reprise.
            # Repli : on prend le DROIT a la bonne graisse et on le penche.
            # On perd les retouches du dessinateur sur ce glyphe, mais on garde
            # la bonne epaisseur - ce qui compte davantage a cote d'un texte gras.
            droit = droit_a_la_graisse(
                glyph_to_contours(A, gU),
                match_contours(glyph_to_contours(A, gU),
                               glyph_to_contours(Bg, gB)), t)
            if droit:
                pen = TTGlyphPen(None)
                draw_contours(tourner(droit) if name in TOURNES else pencher(droit), pen)
                neufs[name] = pen.glyph()
                largeurs[name] = (int(round(hU[name][0] + (hB[name][0] - hU[name][0]) * t)),
                                  hU[name][1])
                stats["penche"] = stats.get("penche", 0) + 1
            else:
                stats["repli"].append(name)
                neufs[name] = Ig
                largeurs[name] = hI[name]
            continue

        if t == 0.0 and name not in RECALES:
            # l'Italic 400 est le dessin d'origine : on le garde tel quel
            neufs[name] = sans_scories(Ig, gI)
            largeurs[name] = hI[name]
            stats["report"] += 1
            continue

        droite = []
        for u, b, i in zip(cU, cB, cI):
            start = _ecart(u["start"], b["start"], i["start"], t)
            segs = [tuple(_ecart(pu, pb, pi, t) for pu, pb, pi in zip(su, sb, si))
                    for su, sb, si in zip(u["segs"], b["segs"], i["segs"])]
            droite.append({"start": start, "segs": segs})

        pen = TTGlyphPen(None)
        droite = lisser(droite, [cI, cU, cB])
        draw_contours(pencher(droite), pen)
        neufs[name] = pen.glyph()
        largeurs[name] = (aw, hI[name][1])
        stats["report"] += 1

    # Le point median est vide dans le D-DIN Bold : on le reconstruit a partir
    # du point final de l'italique que l'on vient de fabriquer.
    if "periodcentered" in stats["repli"] and "period" in neufs:
        per = neufs["period"]
        if getattr(per, "numberOfContours", 0) > 0:
            ref = glyph_to_contours(gI["periodcentered"], gI)
            ys = [p[1] for c in ref for p in [c["start"]] + [q[2] for q in c["segs"]]]
            rise = int(round(min(ys))) if ys else 223
            pc = copy.deepcopy(per)
            pc.coordinates = copy.deepcopy(per.coordinates)
            for k in range(len(pc.coordinates)):
                x, y = pc.coordinates[k]
                pc.coordinates[k] = (int(round(x + SLANT * rise)), y + rise)
            neufs["periodcentered"] = pc
            stats["repli"].remove("periodcentered")
            stats["repare"] = stats.get("repare", 0) + 1

    for name in I.getGlyphOrder():
        gI[name] = neufs[name]
        hI[name] = largeurs[name]
    for name in CHEVRONS & set(I.getGlyphOrder()):
        if not gI[name].isComposite():
            gI[name] = chevrons_egaux(gI[name], gI)
    for name in I.getGlyphOrder():
        gI[name].recalcBounds(gI)
    recaler_marges(I)
    I["head"].recalcBounds = 1

    naming.apply(I, style, weight_class)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    I.save(out_path)
    return stats


if __name__ == "__main__":
    t = float(sys.argv[1]); wc = int(sys.argv[2]); style = sys.argv[3]
    out = sys.argv[4] if len(sys.argv) > 4 else \
        f"fonts/ttf/Appli-Tec-{style.replace(' ', '')}.ttf"
    s = build_italic(t, wc, style, out)
    print(f"  {style:<14} t={t:+.3f}  poids={wc}")
    print(f"     report d'ecart        : {s['report']}")
    print(f"     composites (accents)  : {s['composite']}")
    if s.get("penche"):
        print(f"     penches depuis le droit: {s['penche']}")
    if s.get("repare"):
        print(f"     repares (bug amont)   : {s['repare']}")
    print(f"     replis                : {len(s['repli'])} {s['repli'][:12]}")
    print(f"     -> {out}")
