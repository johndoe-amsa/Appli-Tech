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
import sys, os, copy, math
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


def _vers_chemin(contours):
    import pathops
    p = pathops.Path()
    pen = p.getPen()
    for c in contours:
        pen.moveTo(c["start"])
        for p1, p2, p3 in c["segs"]:
            pen.curveTo(p1, p2, p3)
        pen.closePath()
    return p


def _depuis_chemin(p):
    """Chemin pathops -> contours cubiques, par le meme convertisseur que les
    glyphes, pour que harmonize y trouve les memes reperes."""
    from fontTools.pens.ttGlyphPen import TTGlyphPen as _P
    from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f
    pen = _P(None)
    q = Cu2QuPen(pen, max_err=0.05, reverse_direction=False)
    p.draw(q)
    g = pen.glyph()
    return glyph_to_contours(g, table__g_l_y_f())


def _rect(x0, y0, x1, y1):
    import pathops
    r = pathops.Path()
    pen = r.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0))
    pen.closePath()
    return r


def _barre(contours):
    """Abscisses de la barre verticale du $ ou du cent : le bord haut de
    l'ergot superieur, plat, au sommet du glyphe."""
    pts = [p for c in contours for p in [c["start"]] + [sg[2] for sg in c["segs"]]]
    haut = max(y for _, y in pts)
    xs = [x for x, y in pts if y >= haut - 1]
    if len(xs) < 2 or max(xs) - min(xs) < 10:
        return None
    return min(xs), max(xs), min(y for _, y in pts), haut


def _avec_barre(cb):
    """Prolonge les ergots en barre pleine hauteur : dessin a barre traversante."""
    import pathops
    bb = _barre(cb)
    if not bb:
        return None
    x0, x1, y0, y1 = bb
    pb = pathops.op(_vers_chemin(cb), _rect(x0, y0 - 5, x1, y1 + 5),
                    pathops.PathOp.UNION, clockwise=True)
    # la barre ajoutee ne doit pas depasser la hauteur du glyphe
    pb = pathops.op(pb, _rect(-2000, y0, 4000, y1), pathops.PathOp.INTERSECTION,
                    clockwise=True)
    return _depuis_chemin(pb)


def interp_barre(ca, cb, t):
    """$ et cent : la barre traverse la lettre dans le Regular, pas dans le Bold.

    Dans le Regular, la barre coupe les ouvertures du S (ou du c) et y
    enferme de petites contreformes ; dans le Bold, elle se reduit a deux
    ergots. Ce ne sont pas deux graisses d'un meme dessin, mais deux dessins :
    aucun appariement de points ne les relie, et l'ancienne methode - retrecir
    les contreformes orphelines - laissait des contreformes fantomes jusque
    dans le Bold et des ergots parasites dans les graisses extrapolees.

    On traduit le Bold dans le dessin du Regular (barre prolongee sur toute
    la hauteur, par operation booleenne), et l'on interpole entre ces deux
    dessins de meme structure. Puis :
      - avant le Bold (Light, Regular, Medium) : barre traversante, telle quelle ;
      - au Bold : le dessin d'origine, a l'identique ;
      - au-dela (Heavy) : le Bold d'origine, epaissi (voir plus bas).
    """
    if _barre(ca) is None or _barre(cb) is None:
        return None
    if t == 1.0:
        return copy.deepcopy(cb)
    A, B = copy.deepcopy(ca), _avec_barre(cb)
    if B is None:
        return None
    B = match_contours(A, B)
    if len(A) != len(B) or not all(harmonize_pair(x, y) for x, y in zip(A, B)):
        return None
    out = interp_contours(A, B, t)
    if t > 1.0:
        # Au-dela du Bold, on epaissit le Bold d'origine, de l'ecart de fut
        # mesure sur la barre elle-meme, et on lui donne la largeur du dessin
        # extrapole. Ni extrapolation point a point (elle amplifiait un
        # decrochement de quelques unites que le Bold d'origine porte au flanc
        # du S, et en faisait un bec), ni decoupe de la barre apres coup (sur
        # une forme deja grasse, les contreformes sont trop petites pour la
        # guider, et la coupe taillait des biseaux).
        from epaissir import epaissir
        ba, bb = _barre(ca), _barre(cb)
        d = (t - 1.0) * ((bb[1] - bb[0]) - (ba[1] - ba[0])) / 2.0
        xs = [p[0] for c in out for p in [c["start"]] + [q for sg in c["segs"] for q in sg]]
        out = epaissir(copy.deepcopy(cb), d, largeur_cible=(min(xs), max(xs)))
    return out


def interp_mismatched(ca, cb, t):
    """Contours de topologie differente entre les deux masters.

    Le $ et le cent passent d'abord par interp_barre. Repli pour les autres
    cas, s'il s'en presente : on apparie les contours par surface decroissante, on
    interpole les paires, et on retrecit progressivement les contours
    orphelins - ce qui reproduit fidelement ce que fait le dessinateur quand
    une contreforme se referme a mesure que la graisse augmente.
    """
    barre = interp_barre(ca, cb, t)
    if barre is not None:
        return barre
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


def sans_scories(glyph, glyf):
    """Retire les contours de moins de trois points.

    Les fichiers de D-DIN en contiennent : un point isole au-dessus du "ª",
    a cote des guillemets du Bold, au-dessus du point-virgule, dans le "Å",
    sur le "$". Invisibles a l'impression, ils faussent la boite du glyphe
    (et donc sa marge) et apparaissent dans tout editeur de police.
    """
    if glyph.isComposite() or glyph.numberOfContours <= 0:
        return glyph
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    g = copy.deepcopy(glyph)
    coords, ends, flags = list(g.coordinates), list(g.endPtsOfContours), list(g.flags)
    nc, nf, ne, debut = [], [], [], 0
    for fin in ends:
        if fin - debut + 1 >= 3:
            nc.extend(coords[debut:fin + 1]); nf.extend(flags[debut:fin + 1])
            ne.append(len(nc) - 1)
        debut = fin + 1
    if len(ne) == len(ends):
        return glyph
    g.coordinates = GlyphCoordinates(nc)
    g.flags = bytearray(nf)
    g.endPtsOfContours = ne
    g.numberOfContours = len(ne)
    g.recalcBounds(glyf)
    return g


def recaler_marges(font):
    """Aligne la marge gauche de la table des chasses sur le bord du dessin.

    En TrueType, la marge gauche (hmtx) DOIT egaler le xMin du glyphe : les
    moteurs de rendu (FreeType, Windows) font confiance a la table et
    recalent le dessin pour qu'elle soit vraie. Les generateurs recopiaient
    la marge du Regular d'origine sans la recalculer : sur pres de 2 900
    glyphes, le dessin affiche etait decale de quelques unites par rapport a
    son propre trace - un espacement faux, et, dans le visionneur, des
    contours qui ne passaient plus par leurs points.
    """
    glyf, hmtx = font["glyf"], font["hmtx"]
    for name in font.getGlyphOrder():
        g = glyf[name]
        g.recalcBounds(glyf)
        largeur = hmtx[name][0]
        hmtx[name] = (largeur, g.xMin if g.numberOfContours != 0 else 0)


def _est_droit(p0, seg, tol=0.02):
    """Segment issu d'un trait droit : poignees au tiers et aux deux tiers.
    L'interpolation et la decoupe de deux traits droits en donnent encore un."""
    p1, p2, p3 = seg
    for q, f in ((p1, 1 / 3.0), (p2, 2 / 3.0)):
        ex, ey = p0[0] + (p3[0] - p0[0]) * f, p0[1] + (p3[1] - p0[1]) * f
        L = max(1.0, math.hypot(p3[0] - p0[0], p3[1] - p0[1]))
        if math.hypot(q[0] - ex, q[1] - ey) > tol * L:
            return False
    return True


def _aligne(a, b, c, tol=0.75):
    """b est-il sur la droite ac (a moins de tol unites) ?"""
    dx, dy = c[0] - a[0], c[1] - a[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return True
    return abs((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) / L < tol


def draw_contours(contours, pen):
    """Ecrit les contours cubiques en quadratiques TrueType.

    Les traits droits sont ecrits comme des droites, et les points poses au
    milieu d'un trait droit (decoupes de l'appariement) sont retires. Sans
    cela, chaque droite revenait en courbe aux poignees arrondies a l'unite :
    la diagonale du "y" Regular ondulait d'une demi-unite et passait de 15 a
    40 points.
    """
    qpen = Cu2QuPen(pen, max_err=0.35, reverse_direction=False)
    for c in contours:
        ops, pos = [], c["start"]
        for seg in c["segs"]:
            ops.append(("l", (seg[2],)) if _est_droit(pos, seg) else ("c", seg))
            pos = seg[2]
        # fusion des droites consecutives alignees
        fus = []
        for op in ops:
            if (op[0] == "l" and fus and fus[-1][0] == "l"):
                a = fus[-2][1][-1] if len(fus) > 1 else c["start"]
                if _aligne(a, fus[-1][1][0], op[1][0]):
                    fus[-1] = op
                    continue
            fus.append(op)
        qpen.moveTo(c["start"])
        for kind, pts in fus:
            if kind == "l":
                if pts[0] != c["start"] or (kind, pts) != fus[-1]:
                    qpen.lineTo(pts[0])
            else:
                qpen.curveTo(*pts)
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

        # Aux masters eux-memes, le dessin d'origine tel quel : le refaire
        # passer par l'appariement ne peut que l'abimer (droites recoupees,
        # poignees arrondies). Le $ et le cent du Bold sont dans ce cas.
        src_g, src_h = (ga, hma) if t == 0.0 else (gb, hmb)
        # (un composite du Bold peut viser un glyphe absent du Regular : le
        # Condensed Bold assemble ses fractions a partir de "glyph249")
        if t in (0.0, 1.0) and all(c.glyphName in ga for c in
                                   getattr(src_g[name], "components", [])):
            new_glyphs[name] = sans_scories(src_g[name], src_g)
            new_hmtx[name] = src_h[name]
            stats["interp"] += 1
            continue

        if A.isComposite() and B.isComposite() and \
                len(A.components) == len(B.components) and \
                [c.glyphName for c in A.components] == [c.glyphName for c in B.components]:
            g = ga[name].__class__()
            g.numberOfContours = -1
            g.components = []
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
        _copy = copy
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
    recaler_marges(fa)
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
