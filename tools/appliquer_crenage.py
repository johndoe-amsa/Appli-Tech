"""
Calcule et ecrit la table de crenage d'une police Appli-Tec.

Le crenage est ecrit en GPOS par classes, comme le fait toute police
professionnelle : les glyphes qui presentent le meme flanc sont regroupes, si
bien que quelques milliers de paires individuelles tiennent en quelques
centaines de regles.
"""
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeatures
from crenage import (Mesureur, classes, ajuster, crenage, jeu_utile,
                     categorie, paire_utile, REGLAGES)

SEUIL = 25.0      # en-deca, l'oeil ne voit rien a l'impression
PLAFOND = 130.0   # garde-fou contre les valeurs aberrantes

PAIRES_REF = ["nn", "no", "on", "oo", "mn", "un", "ho", "oc", "hn", "ou", "nu",
              "om", "HH", "HO", "OH", "OO", "HN", "NO", "HE", "DO", "OD", "NN",
              "MN", "HD", "DH", "pq", "bd", "db", "ee", "aa", "ss"]


def table(font, seuil=SEUIL, plafond=PLAFOND, pente=None):
    M = Mesureur(font, pente=pente or REGLAGES["pente"])
    cm = font.getBestCmap()
    noms = jeu_utile(font)
    cat = {n: categorie(font, n) for n in noms}
    refs = [(cm[ord(a)], cm[ord(b)]) for a, b in PAIRES_REF
            if ord(a) in cm and ord(b) in cm]
    base, w = ajuster(M, refs)

    cd = classes(M, noms, "droit")
    cg = classes(M, noms, "gauche")
    regles = []
    for A in cd:
        for B in cg:
            if not paire_utile(cat[A[0]], cat[B[0]]):
                continue
            k = crenage(M, A[0], B[0], base, w)
            k = max(-plafond, min(plafond, k))
            if abs(k) >= seuil:
                regles.append((A, B, int(round(k))))
    return regles, cd, cg, base, w


def fea(regles, cd, cg):
    """Rend la table en syntaxe FEA, par classes."""
    idx_d = {id(c): i for i, c in enumerate(cd)}
    idx_g = {id(c): i for i, c in enumerate(cg)}
    out = io.StringIO()
    # Sans ces declarations, le crenage n'est enregistre que sous l'ecriture
    # DFLT. Plusieurs logiciels - InDesign notamment - interrogent "latn" et
    # n'appliqueraient alors aucun crenage.
    out.write("languagesystem DFLT dflt;\n")
    out.write("languagesystem latn dflt;\n\n")
    utiles_d = {id(A) for A, _, _ in regles}
    utiles_g = {id(B) for _, B, _ in regles}
    for c in cd:
        if id(c) in utiles_d:
            out.write(f"@KD{idx_d[id(c)]} = [{' '.join(c)}];\n")
    for c in cg:
        if id(c) in utiles_g:
            out.write(f"@KG{idx_g[id(c)]} = [{' '.join(c)}];\n")
    out.write("\nfeature kern {\n")
    for A, B, k in regles:
        out.write(f"  pos @KD{idx_d[id(A)]} @KG{idx_g[id(B)]} {k};\n")
    out.write("} kern;\n")
    return out.getvalue()


def appliquer(chemin, sortie=None, pente=None):
    font = TTFont(chemin)
    regles, cd, cg, base, w = table(font, pente=pente)
    # feaLib reconstruit les tables decrites par le fichier de fonctionnalites.
    # Le notre ne decrit que le crenage : sans precaution, GSUB disparait, et
    # avec elle les ligatures, les fractions et les exposants de la police
    # d'origine. On les met de cote et on les remet ensuite.
    gsub = font["GSUB"] if "GSUB" in font else None
    gdef = font["GDEF"] if "GDEF" in font else None
    if "GPOS" in font:
        del font["GPOS"]          # on remplace le crenage d'origine, tres pauvre
    if "kern" in font:
        del font["kern"]
    addOpenTypeFeatures(font, io.StringIO(fea(regles, cd, cg)))
    if gsub is not None:
        font["GSUB"] = gsub
    if gdef is not None and "GDEF" not in font:
        font["GDEF"] = gdef
    font.save(sortie or chemin)
    indiv = sum(len(A) * len(B) for A, B, _ in regles)
    return len(regles), indiv, base, w


if __name__ == "__main__":
    for chemin in sys.argv[1:]:
        n, indiv, base, w = appliquer(chemin)
        print(f"   {os.path.basename(chemin):<28} {n:>5} regles  "
              f"{indiv:>6} paires   (base {base:.0f}, w {w:.2f})")
