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
                       replay)
from build import interp_contours, interp_mismatched
import naming

SLANT = math.tan(math.radians(12.0))     # 0.21256
ORIGINE = 254.1   # hauteur autour de laquelle le dessinateur a penche (mesuree)


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


def droit_a_la_graisse(cU, cB, t):
    """Le droit interpole a la graisse t, topologies divergentes comprises."""
    if not cU or not cB:
        return None
    if (len(cU) == len(cB)
            and all(len(x["segs"]) == len(y["segs"]) for x, y in zip(cU, cB))):
        return interp_contours(cU, cB, t)
    return interp_mismatched(cU, cB, t)


def draw_contours(contours, pen):
    q = Cu2QuPen(pen, max_err=0.6, reverse_direction=False)
    for c in contours:
        q.moveTo(c["start"])
        for p1, p2, p3 in c["segs"]:
            q.curveTo(p1, p2, p3)
        q.closePath()


def _report(pu, pb, pi, t):
    """italique + cisaillement(t x ecart de graisse)"""
    dx = (pb[0] - pu[0]) * t
    dy = (pb[1] - pu[1]) * t
    return (pi[0] + dx + SLANT * dy, pi[1] + dy)


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
        cI = match_contours(cU, glyph_to_contours(Ig, gI))

        if not aligner(cU, cB, cI):
            # Repli : on prend le DROIT a la bonne graisse et on le penche.
            # On perd les retouches du dessinateur sur ce glyphe, mais on garde
            # la bonne epaisseur - ce qui compte davantage a cote d'un texte gras.
            droit = droit_a_la_graisse(
                glyph_to_contours(A, gU),
                match_contours(glyph_to_contours(A, gU),
                               glyph_to_contours(Bg, gB)), t)
            if droit:
                pen = TTGlyphPen(None)
                draw_contours(pencher(droit), pen)
                neufs[name] = pen.glyph()
                largeurs[name] = (int(round(hU[name][0] + (hB[name][0] - hU[name][0]) * t)),
                                  hU[name][1])
                stats["penche"] = stats.get("penche", 0) + 1
            else:
                stats["repli"].append(name)
                neufs[name] = Ig
                largeurs[name] = hI[name]
            continue

        sortie = []
        for u, b, i in zip(cU, cB, cI):
            start = _report(u["start"], b["start"], i["start"], t)
            segs = [tuple(_report(pu, pb, pi, t) for pu, pb, pi in zip(su, sb, si))
                    for su, sb, si in zip(u["segs"], b["segs"], i["segs"])]
            sortie.append({"start": start, "segs": segs})

        pen = TTGlyphPen(None)
        draw_contours(sortie, pen)
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
    for name in I.getGlyphOrder():
        gI[name].recalcBounds(gI)
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
