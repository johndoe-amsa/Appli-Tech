"""
Verification complete de la famille Appli-Tec.

Ecrit apres coup : trois regressions ont ete introduites sans etre vues, et
toutes avaient le meme profil - invisibles aux controles ponctuels, visibles
a l'usage. Les contours deformes, la nomenclature OpenType qui declarait le
Heavy comme un gras, et le hinting detruit par la reconstruction des trace.

Ce script balaie tout ce qui doit etre vrai d'un fichier livrable, et se
lance AVANT de livrer, pas apres.
"""
import sys, os, glob, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.areaPen import AreaPen

MASTERS = {
    ("", "Regular"): "D-DIN.ttf",
    ("", "Italic"): "D-DIN-Italic.ttf",
    ("Condensed", "Regular"): "D-DINCondensed.ttf",
}
RIBBI = ("Regular", "Italic", "Bold", "Bold Italic")
PAS = 1.5


def _echantillons(font, ch):
    gs = font.getGlyphSet(); cm = font.getBestCmap()
    if ord(ch) not in cm:
        return []
    rec = RecordingPen(); gs[cm[ord(ch)]].draw(rec)
    pts, pos, start = [], None, None

    def n_pour(*p):
        L = sum(math.hypot(p[i+1][0]-p[i][0], p[i+1][1]-p[i][1]) for i in range(len(p)-1))
        return max(2, int(L / PAS))

    def ligne(p0, p1):
        k = n_pour(p0, p1)
        for i in range(k+1):
            t = i/k; pts.append((p0[0]+(p1[0]-p0[0])*t, p0[1]+(p1[1]-p0[1])*t))

    def quad(p0, p1, p2):
        k = n_pour(p0, p1, p2)
        for i in range(k+1):
            t = i/k; u = 1-t
            pts.append((u*u*p0[0]+2*u*t*p1[0]+t*t*p2[0], u*u*p0[1]+2*u*t*p1[1]+t*t*p2[1]))

    for op, args in rec.value:
        a = [tuple(p) for p in args] if args else []
        if op == "moveTo":
            pos = start = a[0]; pts.append(pos)
        elif op == "lineTo":
            ligne(pos, a[0]); pos = a[0]
        elif op == "qCurveTo":
            prev = pos
            for i in range(len(a)-1):
                c = a[i]
                mid = ((c[0]+a[i+1][0])/2, (c[1]+a[i+1][1])/2) if i+1 < len(a)-1 else a[-1]
                quad(prev, c, mid); prev = mid
            pos = a[-1]
        elif op == "closePath":
            if pos and start:
                ligne(pos, start); pos = start
    return pts


def ecart_trace(ref, gen, exclure=()):
    """Ecart maximal du trace, en unites, entre deux polices."""
    import string
    A, B = TTFont(ref), TTFont(gen)
    chars = [c for c in string.ascii_letters + string.digits + "àéèçôöüßØø±°µ€&%?!.,:;()«»"
             if c not in exclure]
    pire = 0.0
    for ch in chars:
        pa, pb = _echantillons(A, ch), _echantillons(B, ch)
        if not pa or not pb:
            continue
        g, cell = {}, 8.0
        for p in pa:
            g.setdefault((int(p[0]//cell), int(p[1]//cell)), []).append(p)
        for q in pb:
            gx, gy = int(q[0]//cell), int(q[1]//cell); best, r = 1e18, 1
            while True:
                for i in range(gx-r, gx+r+1):
                    for j in range(gy-r, gy+r+1):
                        for p in g.get((i, j), ()):
                            d = math.hypot(q[0]-p[0], q[1]-p[1])
                            if d < best: best = d
                if best <= r*cell or r > 6: break
                r += 1
            pire = max(pire, best)
    return pire


def _aires(chemin):
    f = TTFont(chemin); gs = f.getGlyphSet()
    out = {}
    for n in f.getGlyphOrder():
        ap = AreaPen(gs)
        try:
            gs[n].draw(ap)
        except Exception:
            continue
        out[n] = abs(ap.value)
    return out


def controler_interpolation(master_a, master_b, genere, t, tolerance=0.25):
    """L'encre de chaque glyphe suit-elle l'interpolation des deux masters ?

    Attrape la famille de defauts la plus sournoise : un appariement de points
    decale d'un cran. Sur une forme symetrique - la croix du "±" - le
    deplacement de chaque point reste faible, donc aucune mesure de distance
    ne le signale, mais l'interpolation fait PIVOTER la forme et la croix
    devient un moulin a vent. L'encre, elle, s'effondre : c'est elle qu'on
    surveille.
    """
    A, B, G = _aires(master_a), _aires(master_b), _aires(genere)
    suspects = []
    for n, ag in G.items():
        if n not in A or n not in B:
            continue
        attendu = A[n] + (B[n] - A[n]) * t
        if attendu < 2000:          # glyphes minuscules : bruit
            continue
        # Hors de l'intervalle des masters, l'encre ne varie plus lineairement
        # - l'aire d'un point rond suit le carre de son rayon - donc on
        # relache la tolerance a mesure qu'on extrapole.
        seuil = tolerance + 0.5 * max(0.0, -t, t - 1.0)
        ecart = abs(ag - attendu) / attendu
        if ecart > seuil:
            suspects.append((ecart, n, attendu, ag))
    suspects.sort(reverse=True)
    return suspects


def controler(chemin):
    f = TTFont(chemin); n = f["name"]; g = f["glyf"]
    fam, sub = n.getDebugName(1), n.getDebugName(2)
    style = n.getDebugName(17) or sub
    pbs = []

    instr = sum(1 for x in f.getGlyphOrder()
                if getattr(getattr(g[x], "program", None), "bytecode", b""))
    if instr < 150:
        pbs.append(f"hinting absent ou incomplet ({instr} glyphes)")

    if "GSUB" not in f or not f["GSUB"].table.FeatureList.FeatureRecord:
        pbs.append("GSUB absente (ligatures, fractions, exposants perdus)")
    if "GDEF" not in f:
        pbs.append("GDEF absente")

    if "GPOS" not in f:
        pbs.append("GPOS absente (aucun crenage)")
    else:
        feats = {fr.FeatureTag for fr in f["GPOS"].table.FeatureList.FeatureRecord}
        scripts = {r.ScriptTag for r in f["GPOS"].table.ScriptList.ScriptRecord}
        if "kern" not in feats:
            pbs.append("pas de fonctionnalite kern")
        if "latn" not in scripts:
            pbs.append("ecriture latn non declaree (plusieurs logiciels ignoreraient le crenage)")

    italique = style.endswith("Italic")
    gras = sub in ("Bold", "Bold Italic")
    fs = f["OS/2"].fsSelection
    if bool(fs & 0x0001) != italique:
        pbs.append("drapeau ITALIC incoherent")
    if bool(fs & 0x0020) != gras:
        pbs.append("drapeau BOLD incoherent avec la sous-famille")
    if (sub == "Regular") != bool(fs & 0x0040):
        pbs.append("drapeau REGULAR incoherent")
    if sub not in RIBBI:
        pbs.append(f"sous-famille '{sub}' non admise par Windows")
    if italique != (f["post"].italicAngle != 0):
        pbs.append("angle d'italique incoherent")

    # Epaisseur du fut, mesuree sur le "I". En italique, la largeur
    # horizontale du glyphe englobe le penchage : on la corrige, sinon un
    # italique parait deux fois plus gras que son romain.
    gs = f.getGlyphSet(); cm = f.getBestCmap()
    bp = BoundsPen(gs); gs[cm[ord("I")]].draw(bp)
    fut = bp.bounds[2] - bp.bounds[0]
    angle = f["post"].italicAngle
    if angle:
        fut -= abs(math.tan(math.radians(angle))) * (bp.bounds[3] - bp.bounds[1])
    return dict(fichier=os.path.basename(chemin), famille=fam, sous=sub, style=style,
                poids=f["OS/2"].usWeightClass, largeur=f["OS/2"].usWidthClass,
                instr=instr, fut=fut, glyphes=len(f.getGlyphOrder()),
                asc=f["OS/2"].usWinAscent, desc=f["OS/2"].usWinDescent,
                typo=(f["OS/2"].sTypoAscender, f["OS/2"].sTypoDescender),
                pbs=pbs)


if __name__ == "__main__":
    fichiers = sorted(glob.glob("fonts/ttf/*.ttf"))
    res = [controler(c) for c in fichiers]
    print(f"{'fichier':<34}{'famille':<28}{'sous':<13}{'poids':<7}{'lg':<4}{'instr':<7}{'fut':<6}")
    print("-" * 100)
    for r in res:
        print(f"{r['fichier']:<34}{r['famille']:<28}{r['sous']:<13}{r['poids']:<7}"
              f"{r['largeur']:<4}{r['instr']:<7}{r['fut']:<6.0f}")

    print("\n--- metriques verticales (doivent etre identiques partout) ---")
    mets = {(r["asc"], r["desc"], r["typo"]) for r in res}
    print(f"   {len(mets)} jeu(x) distinct(s) : " +
          ("coherent" if len(mets) == 1 else "*** INCOHERENT *** " + str(mets)))

    print("\n--- progression des futs par famille ---")
    import collections
    par_fam = collections.defaultdict(list)
    for r in res:
        cle = ("Condensed" if r["largeur"] == 3 else "Normale",
               "italique" if r["style"].endswith("Italic") else "romain")
        par_fam[cle].append((r["poids"], r["fut"], r["style"]))
    for cle, v in sorted(par_fam.items()):
        v.sort()
        futs = [x[1] for x in v]
        mono = all(futs[i] < futs[i+1] for i in range(len(futs)-1))
        print(f"   {cle[0]:<11}{cle[1]:<10}" + "  ".join(f"{p}:{fu:.0f}" for p, fu, _ in v)
              + ("   monotone" if mono else "   *** NON MONOTONE ***"))

    print("\n--- interpolation : l'encre suit-elle les masters ? ---")
    src = "sources/upstream-d-din"
    jeux = [("", f"{src}/D-DIN.ttf", f"{src}/D-DIN-Bold.ttf",
             [("Light", -1/3), ("Regular", 0.0), ("Medium", 1/3), ("Bold", 1.0), ("Heavy", 4/3)]),
            ("Condensed-", f"{src}/D-DINCondensed.ttf", f"{src}/D-DINCondensed-Bold.ttf",
             [("Light", -1/3), ("Regular", 0.0), ("Medium", 1/3), ("Bold", 1.0), ("Heavy", 4/3)])]
    total_interp = 0
    for prefixe, ma, mb, styles in jeux:
        for style, t in styles:
            chemin = f"fonts/ttf/Appli-Tec-{prefixe}{style}.ttf"
            if not os.path.exists(chemin):
                continue
            sus = controler_interpolation(ma, mb, chemin, t)
            etiq = f"{prefixe.rstrip('-') or 'Normale'} {style}"
            if sus:
                total_interp += len(sus)
                print(f"   {etiq:<22} {len(sus)} glyphe(s) suspect(s) : " +
                      ", ".join(f"{n} ({e*100:.0f}%)" for e, n, _, _ in sus[:6]))
            else:
                print(f"   {etiq:<22} conforme")
    print("\n--- anomalies ---")
    total = 0
    for r in res:
        for p in r["pbs"]:
            print(f"   {r['fichier']:<34} {p}"); total += 1
    print(f"   {'aucune' if total == 0 else str(total) + ' anomalie(s)'}")
    sys.exit(1 if (total or total_interp) else 0)
