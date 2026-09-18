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

FAMILY = "Appli-Tec"
VENDOR = "Applitec Moutier SA"


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

        needed = any(len(x["segs"]) != len(y["segs"]) for x, y in zip(ca, cb))
        if needed and not all(harmonize_pair(x, y) for x, y in zip(ca, cb)):
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

    # --- metadonnees ---
    os2 = fa["OS/2"]
    os2.usWeightClass = weight_class
    sub = subfamily or ("Regular" if style in ("Regular", "Italic") else style)
    full = f"{FAMILY}{(' ' + width_name) if width_name else ''}"
    ps = (full + "-" + style).replace(" ", "")

    copyright_ = ("Copyright (c) 2017 Datto Inc. (D-DIN, SIL OFL 1.1). "
                  f"Modifications copyright (c) 2026 {VENDOR}. "
                  "This Font Software is licensed under the SIL Open Font "
                  "License, Version 1.1. Reserved Font Name 'Appli-Tec'.")
    nm = fa["name"]
    nm.names = [n for n in nm.names if n.nameID not in
                (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17)]
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        def setn(i, s):
            nm.setName(s, i, pid, eid, lid)
        setn(0, copyright_)
        setn(1, full if style in ("Regular", "Bold", "Italic", "Bold Italic") else f"{full} {style}")
        setn(2, sub)
        setn(3, f"{VENDOR}: {full} {style}: 2026")
        setn(4, f"{full} {style}")
        setn(5, "Version 1.000")
        setn(6, ps)
        setn(9, "Charles Nix (Monotype), dessin d'origine D-DIN")
        setn(11, "https://github.com/johndoe-amsa/Appli-Tech")
        setn(13, "This Font Software is licensed under the SIL Open Font "
                 "License, Version 1.1. No modification of this font may use "
                 "the Reserved Font Name 'D-DIN'.")
        setn(14, "https://scripts.sil.org/OFL")
        setn(16, full)
        setn(17, style)

    os2.achVendID = "APTC"
    fa["post"].underlinePosition = fa["post"].underlinePosition
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fa.save(out_path)
    return stats


if __name__ == "__main__":
    R = "sources/upstream-d-din/D-DIN.ttf"
    B = "sources/upstream-d-din/D-DIN-Bold.ttf"
    t = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3333
    wc = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    style = sys.argv[3] if len(sys.argv) > 3 else "Medium"
    out = sys.argv[4] if len(sys.argv) > 4 else f"fonts/ttf/Appli-Tec-{style}.ttf"
    s = build_instance(R, B, t, wc, style, out)
    print(f"  {style:<10} t={t:+.3f}  poids={wc}")
    print(f"     interpolation directe : {s['interp']}")
    print(f"     apres harmonisation   : {s['harmonise']}")
    print(f"     composites (accents)  : {s['composite']}")
    if s.get("topologie"):
        print(f"     topologie differente  : {s['topologie']} (contreformes fusionnees)")
    if s.get("repare"):
        print(f"     repares (bug amont)   : {s['repare']}")
    print(f"     echecs                : {len(s['echec'])} {s['echec']}")
    print(f"     -> {out}")
