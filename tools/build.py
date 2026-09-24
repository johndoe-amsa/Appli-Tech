"""
Generateur de graisses pour la famille Appli-Tec.

Fabrique une graisse intermediaire (ou extreme) a partir des deux dessins
d'origine Regular et Bold, par interpolation point a point.

  t = 0.0  -> Regular (400)      t = 1.0  -> Bold (700)
  t = 0.33 -> Medium  (500)      t < 0    -> Light  (extrapolation)
  t > 1.0  -> Black                        (extrapolation)

Base sur D-DIN (c) 2017 Datto Inc., sous licence SIL OFL 1.1.
Conformement a la clause 3 de cette licence, la famille derivee porte un
nom different du nom reserve "D-DIN".
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from harmonize import glyph_to_contours, harmonize_pair, match_contours
import naming

def lerp(a, b, t):
    return a + (b - a) * t


def _centroid(c):
    pts = [c["start"]] + [sg[2] for sg in c["segs"]]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _area(c):
    pts = [c["start"]] + [sg[2] for sg in c["segs"]]
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def _shrink(c, f):
    """Retrecit un contour vers son centre (facteur f)."""
    cx, cy = _centroid(c)
    sc = lambda p: (cx + (p[0] - cx) * f, cy + (p[1] - cy) * f)
    return {"start": sc(c["start"]),
            "segs": [tuple(sc(p) for p in sg) for sg in c["segs"]]}


def interp_mismatched(ca, cb, t):
    """Contours de topologie differente entre les deux masters.

    Cas reel dans D-DIN : le $ et le cent voient leurs contreformes fusionner
    dans le Bold. On apparie alors les contours par surface decroissante, on
    interpole les paires, et on retrecit progressivement les contours
    orphelins - ce qui reproduit fidelement ce que fait le dessinateur quand
    une contreforme se referme a mesure que la graisse augmente.
    """
    A = sorted(ca, key=_area, reverse=True)
    B = sorted(cb, key=_area, reverse=True)
    out = []
    for i, x in enumerate(A):
        if i < len(B) and len(x["segs"]) == len(B[i]["segs"]):
            out.extend(interp_contours([x], [B[i]], t))
        elif i < len(B):
            xa, xb = [x], [B[i]]
            if harmonize_pair(xa[0], xb[0]):
                out.extend(interp_contours(xa, xb, t))
            else:
                out.append(_shrink(x, 1.0 - 0.35 * max(0.0, t)))
        else:
            out.append(_shrink(x, 1.0 - 0.35 * max(0.0, t)))
    return out


def interp_contours(ca, cb, t):
    out = []
    for x, y in zip(ca, cb):
        start = (lerp(x["start"][0], y["start"][0], t),
                 lerp(x["start"][1], y["start"][1], t))
        segs = [tuple((lerp(p[0], q[0], t), lerp(p[1], q[1], t))
                      for p, q in zip(sx, sy))
                for sx, sy in zip(x["segs"], y["segs"])]
        out.append({"start": start, "segs": segs})
    return out


def draw_contours(contours, pen):
    qpen = Cu2QuPen(pen, max_err=0.6, reverse_direction=False)
    for c in contours:
        qpen.moveTo(c["start"])
        for p1, p2, p3 in c["segs"]:
            qpen.curveTo(p1, p2, p3)
        qpen.closePath()


def build_instance(reg_path, bold_path, t, weight_class, style, out_path,
                   subfamily=None, width_name=""):
    fa, fb = TTFont(reg_path), TTFont(bold_path)
    ga, gb = fa["glyf"], fb["glyf"]
    hma, hmb = fa["hmtx"], fb["hmtx"]
    order = fa.getGlyphOrder()

    stats = {"interp": 0, "harmonise": 0, "composite": 0, "echec": []}
    new_glyphs, new_hmtx = {}, {}

    for name in order:
        if name not in gb:
            new_glyphs[name] = ga[name]
            new_hmtx[name] = hma[name]
            continue
        A, B = ga[name], gb[name]
        aw = int(round(lerp(hma[name][0], hmb[name][0], t)))

        if A.isComposite() and B.isComposite() and \
                len(A.components) == len(B.components) and \
                [c.glyphName for c in A.components] == [c.glyphName for c in B.components]:
            g = ga[name].__class__()
            g.numberOfContours = -1
            g.components = []
            import copy
            for compA, compB in zip(A.components, getattr(B, "components", A.components)):
                c = copy.deepcopy(compA)
                if hasattr(c, "x") and hasattr(compB, "x"):
                    c.x = int(round(lerp(compA.x, compB.x, t)))
                    c.y = int(round(lerp(compA.y, compB.y, t)))
                g.components.append(c)
            new_glyphs[name] = g
            new_hmtx[name] = (aw, hma[name][1])
            stats["composite"] += 1
            continue

        if A.numberOfContours == 0:
            new_glyphs[name] = A
            new_hmtx[name] = (aw, hma[name][1])
            continue

        ca, cb = glyph_to_contours(A, ga), glyph_to_contours(B, gb)
        # apparier les contours entre eux AVANT toute comparaison : rien ne
        # garantit que les deux dessins les enumerent dans le meme ordre
        cb = match_contours(ca, cb)
        if not ca or not cb:
            # Glyphe vide d'un cote : defaut du dessin d'origine (le point
            # median "periodcentered" est vide dans le D-DIN Bold). On le
            # reconstruit plus bas a partir du point final.
            stats["echec"].append(name)
            new_glyphs[name] = A
            new_hmtx[name] = (hma[name][0], hma[name][1])
            continue
        if len(ca) != len(cb):
            pen = TTGlyphPen(None)
            draw_contours(interp_mismatched(ca, cb, t), pen)
            new_glyphs[name] = pen.glyph()
            new_hmtx[name] = (aw, hma[name][1])
            stats["topologie"] = stats.get("topologie", 0) + 1
            continue

        # On realigne TOUJOURS, meme quand les deux masters ont deja le meme
        # nombre de points. Rien ne garantit qu'ils commencent leur contour au
        # meme endroit : sur une forme symetrique comme le "±", dont la croix
        # se retrouve un quart de tour en avance d'un cote, chaque point est
        # alors apparie a son voisin. Le deplacement reste faible - donc
        # invisible aux mesures - mais l'interpolation fait pivoter la forme,
        # et la croix devient un moulin a vent.
        needed = any(len(x["segs"]) != len(y["segs"]) for x, y in zip(ca, cb))
        if not all(harmonize_pair(x, y) for x, y in zip(ca, cb)):
            stats["echec"].append(name)
            new_glyphs[name] = A
            new_hmtx[name] = (hma[name][0], hma[name][1])
            continue

        pen = TTGlyphPen(None)
        draw_contours(interp_contours(ca, cb, t), pen)
        new_glyphs[name] = pen.glyph()
        new_hmtx[name] = (aw, hma[name][1])
        stats["harmonise" if needed else "interp"] += 1

    # Reparation du point median, vide dans le D-DIN Bold d'origine :
    # on le reconstruit en remontant le point final a mi-hauteur de x.
    if "periodcentered" in new_glyphs and "period" in new_glyphs:
        import copy as _copy
        per = new_glyphs["period"]
        if getattr(per, "numberOfContours", 0) > 0:
            pc = _copy.deepcopy(per)
            ref = glyph_to_contours(ga["periodcentered"], ga)
            ys = [p[1] for c in ref for p in [c["start"]] + [s2[2] for s2 in c["segs"]]]
            rise = int(round(min(ys))) if ys else 223
            pc.coordinates = _copy.deepcopy(per.coordinates)
            for i in range(len(pc.coordinates)):
                x, y = pc.coordinates[i]
                pc.coordinates[i] = (x, y + rise)
            new_glyphs["periodcentered"] = pc
            new_hmtx["periodcentered"] = new_hmtx.get("periodcentered", hma["periodcentered"])
            if "periodcentered" in stats["echec"]:
                stats["echec"].remove("periodcentered")
                stats["repare"] = stats.get("repare", 0) + 1

    for name in order:
        ga[name] = new_glyphs[name]
        hma[name] = new_hmtx[name]
    for name in order:
        ga[name].recalcBounds(ga)
    fa["head"].recalcBounds = 1

    naming.apply(fa, style, weight_class, width_name)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fa.save(out_path)
    return stats


MASTERS = {
    "": ("D-DIN.ttf", "D-DIN-Bold.ttf"),
    "Condensed": ("D-DINCondensed.ttf", "D-DINCondensed-Bold.ttf"),
    "Exp": ("D-DINExp.ttf", "D-DINExp-Bold.ttf"),
}


if __name__ == "__main__":
    t = float(sys.argv[1])
    wc = int(sys.argv[2])
    style = sys.argv[3]
    largeur = sys.argv[4] if len(sys.argv) > 4 else ""
    if largeur not in MASTERS:
        sys.exit(f"largeur inconnue : {largeur!r} (connues : {sorted(MASTERS)})")
    reg, bold = (f"sources/upstream-d-din/{f}" for f in MASTERS[largeur])
    nom = f"Appli-Tec{'-' + largeur if largeur else ''}-{style.replace(' ', '')}"
    out = f"fonts/ttf/{nom}.ttf"
    s = build_instance(reg, bold, t, wc, style, out, width_name=largeur)
    etiquette = f"{largeur + ' ' if largeur else ''}{style}"
    print(f"  {etiquette:<22} t={t:+.3f}  poids={wc}")
    print(f"     interpolation directe : {s['interp']}")
    print(f"     apres harmonisation   : {s['harmonise']}")
    print(f"     composites (accents)  : {s['composite']}")
    if s.get("topologie"):
        print(f"     topologie differente  : {s['topologie']} (contreformes fusionnees)")
    if s.get("repare"):
        print(f"     repares (bug amont)   : {s['repare']}")
    print(f"     echecs                : {len(s['echec'])} {s['echec']}")
    print(f"     -> {out}")
