"""
Nommage OpenType de la famille Appli-Tec.

Windows n'accepte que quatre styles dans le couple famille/sous-famille
historique : Regular, Italic, Bold, Bold Italic. Une famille de cinq graisses
doit donc etre declaree en plusieurs sous-familles ("Appli-Tec Light",
"Appli-Tec Medium"...), tout en portant les noms typographiques modernes
(name ID 16/17) qui permettent aux logiciels recents de regrouper le tout
sous un seul "Appli-Tec".
"""
RIBBI = ("Regular", "Italic", "Bold", "Bold Italic")

FAMILY = "Appli-Tec"
VENDOR = "Applitec Moutier SA"
REPO = "https://github.com/johndoe-amsa/Appli-Tech"

COPYRIGHT = ("Copyright (c) 2017 Datto Inc. (D-DIN, SIL OFL 1.1). "
             "Modifications copyright (c) 2026 Applitec Moutier SA. "
             "This Font Software is licensed under the SIL Open Font License, "
             "Version 1.1. Reserved Font Name 'Appli-Tec'.")

LICENSE = ("This Font Software is licensed under the SIL Open Font License, "
           "Version 1.1. No modification of this font may use the Reserved "
           "Font Name 'D-DIN'.")


def names_for(style, width=""):
    """-> (famille, sous-famille, famille typo, style typo, nom PostScript)"""
    base_family = FAMILY + (" " + width if width else "")
    italic = style.endswith("Italic")
    poids = style[:-6].strip() if italic else style     # "Light", "" , "Bold"...

    if style in RIBBI:
        fam, sub = base_family, style
    else:
        fam = f"{base_family} {poids}".strip()
        sub = "Italic" if italic else "Regular"

    ps = (base_family + "-" + style).replace(" ", "")
    return fam, sub, base_family, style, ps


def apply(font, style, weight_class, width="", version="1.002"):
    fam, sub, typo_fam, typo_sub, ps = names_for(style, width)
    # Les bits ITALIC / BOLD / REGULAR decrivent la place du fichier DANS SA
    # sous-famille, pas son poids absolu. Le Heavy est le romain de la famille
    # "Appli-Tec Heavy" : il ne doit surtout pas porter le bit gras, sinon
    # Windows le propose comme le gras de cette famille.
    italic = sub in ("Italic", "Bold Italic")
    gras = sub in ("Bold", "Bold Italic")

    os2 = font["OS/2"]
    os2.usWeightClass = weight_class
    os2.achVendID = "APTC"
    fs = os2.fsSelection & ~0x0061          # on remet a plat ITALIC/BOLD/REGULAR
    if italic:
        fs |= 0x0001
    if gras:
        fs |= 0x0020
    if sub == "Regular":
        fs |= 0x0040
    os2.fsSelection = fs

    head = font["head"]
    head.macStyle = (0x0001 if gras else 0) | (0x0002 if italic else 0)

    font["post"].italicAngle = -12.0 if style.endswith("Italic") else 0.0

    nm = font["name"]
    nm.names = [n for n in nm.names
                if n.nameID not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                                    12, 13, 14, 16, 17)]
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        def setn(i, s):
            nm.setName(s, i, pid, eid, lid)
        setn(0, COPYRIGHT)
        setn(1, fam)
        setn(2, sub)
        setn(3, f"{VENDOR}: {typo_fam} {style}: 2026")
        setn(4, f"{typo_fam} {style}" if style != "Regular" else typo_fam)
        setn(5, f"Version {version}")
        setn(6, ps)
        setn(8, VENDOR)
        setn(9, "Charles Nix (Monotype), dessin d'origine D-DIN")
        setn(11, REPO)
        setn(13, LICENSE)
        setn(14, "https://openfontlicense.org")
        setn(16, typo_fam)
        setn(17, typo_sub)
    return ps
