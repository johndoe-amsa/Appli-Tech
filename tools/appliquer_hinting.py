"""
Optimisation de l'affichage ecran (hinting) de la famille Appli-Tec.

A l'ecran en petit corps, une lettre est dessinee sur une grille de pixels
grossiere. Un fut vertical de 1,4 pixel de large tombe a cheval sur deux
pixels : les deux ressortent gris et la lettre parait floue. Le hinting est
un jeu d'instructions, enfouies dans la police, qui disent au systeme de
caler ce fut sur un pixel entier.

macOS ignore ces instructions - Apple prefere rester fidele au dessin, quitte
a ce que ce soit flou. Windows s'appuie dessus, et c'est la que travaillent
les postes d'Applitec, dans Word, autour de 10-11 pt.

Les instructions de D-DIN ont ete perdues en reconstruisant les contours pour
fabriquer les graisses (237 glyphes sur 251 en portaient). On les regenere
avec ttfautohint, qui les calcule a partir du dessin.

Reglages :
  fallback_script='latn'    sans quoi les glyphes dont ttfautohint ne devine
                            pas l'ecriture ne recoivent aucune instruction ;
  windows_compatibility     evite que les lettres hautes soient rognees dans
                            les applications Office ;
  reference_file            toute la famille herite des zones de reference du
                            Regular, pour que les graisses se calent a la
                            meme hauteur d'x et sur la meme ligne de base.

Les modes de fut restent ceux recommandes par ttfautohint : ferme pour le
rendu GDI ClearType de Windows, quantifie en niveaux de gris - ou le mode
ferme rend la couleur du texte irreguliere.
"""
import sys, os, shutil, tempfile

from fontTools.ttLib import TTFont
from ttfautohint import ttfautohint

REFERENCE = "fonts/ttf/Appli-Tec-Regular.ttf"


def appliquer(chemin, reference=None):
    tmp = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False)
    tmp.close()
    opts = dict(in_file=chemin, out_file=tmp.name,
                fallback_script="latn", default_script="latn",
                windows_compatibility=True)
    if reference:
        opts["reference_file"] = reference
    ttfautohint(**opts)
    shutil.move(tmp.name, chemin)
    f = TTFont(chemin)
    g = f["glyf"]
    return sum(1 for n in f.getGlyphOrder()
               if getattr(getattr(g[n], "program", None), "bytecode", b"")), \
        len(f.getGlyphOrder())


if __name__ == "__main__":
    chemins = sys.argv[1:]
    # le Regular sert de reference a toute la famille : on en garde une copie
    # intacte, car il sera lui-meme modifie au passage.
    ref = None
    if os.path.exists(REFERENCE):
        ref = tempfile.NamedTemporaryFile(suffix=".ttf", delete=False).name
        shutil.copy(REFERENCE, ref)
    try:
        for c in chemins:
            n, tot = appliquer(c, ref)
            print(f"   {os.path.basename(c):<28} {n:>4}/{tot} glyphes instruits")
    finally:
        if ref and os.path.exists(ref):
            os.unlink(ref)
