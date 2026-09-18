"""
Calcul du crenage par aire de blanc.

Le crenage corrige l'espace entre deux lettres voisines. Un "AT" non crene
laisse un trou, parce que la diagonale du A et le fut du T ne se voient pas :
leurs encombrements rectangulaires se touchent, mais pas leur encre.

Methode : on ne mesure pas la distance minimale entre les deux dessins - elle
serait dictee par un seul point, souvent en haut du T - mais l'AIRE DE BLANC
que l'oeil percoit entre eux. Pour chaque hauteur, on releve le bord droit de
la premiere lettre et le bord gauche de la seconde ; la moyenne des ecarts
donne le blanc percu. Le crenage est la correction qui ramene ce blanc a la
valeur de reference de la police - celle que le dessinateur a fixee lui-meme
sur des paires comme "nn" ou "HH".

Tout le probleme est de distinguer le blanc qui APPARTIENT a la lettre de
celui qui appartient a l'intervalle. On s'en remet pour cela a un cone de
visibilite : l'encre ne masque le blanc que dans un cone. L'echancrure d'un
"E" ou le dessous du bras d'un "T" sont bouches a l'oeil par l'encre voisine ;
le coin largement ouvert d'un "AV" ne l'est pas. Voir Mesureur.masque().

On retient ensuite deux mesures : l'ecart MOYEN et l'ecart MINIMAL. Le moyen
seul laisserait passer "AV", dont les deux diagonales s'ecartent en sens
inverse sans jamais se rapprocher. Le minimal seul condamnerait "oo", dont les
bords se frolent a mi-hauteur alors que le blanc total est voulu genereux.
Leur ponderation est ajustee sur des paires que le dessinateur a lui-meme bien
espacees - "nn", "oo", "HH" - qui doivent ressortir a zero.
"""
import math
from fontTools.pens.recordingPen import RecordingPen

PAS = 20.0          # hauteur d'echantillonnage, en unites
PENTE = 0.7         # pente du cone de visibilite


def _polylignes(font, nom, finesse=8.0):
    """Contours du glyphe aplatis en lignes brisees."""
    gs = font.getGlyphSet()
    if nom not in gs:
        return []
    rec = RecordingPen()
    gs[nom].draw(rec)
    lignes, cur, pos, start = [], [], None, None

    def seg(p0, p1):
        d = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        k = max(1, int(d / finesse))
        for i in range(1, k + 1):
            t = i / k
            cur.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))

    def quad(p0, p1, p2):
        k = max(2, int((math.hypot(p1[0]-p0[0], p1[1]-p0[1]) +
                        math.hypot(p2[0]-p1[0], p2[1]-p1[1])) / finesse))
        for i in range(1, k + 1):
            t = i / k; u = 1 - t
            cur.append((u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0],
                        u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]))

    for op, args in rec.value:
        a = [tuple(p) for p in args] if args else []
        if op == "moveTo":
            if cur: lignes.append(cur)
            cur = [a[0]]; pos = start = a[0]
        elif op == "lineTo":
            seg(pos, a[0]); pos = a[0]
        elif op == "qCurveTo":
            prev = pos
            for i in range(len(a) - 1):
                c = a[i]
                mid = ((c[0]+a[i+1][0])/2, (c[1]+a[i+1][1])/2) if i+1 < len(a)-1 else a[-1]
                quad(prev, c, mid); prev = mid
            pos = a[-1]
        elif op == "curveTo":
            # cubique : on passe par des quadratiques approchees
            p0 = pos
            for i in range(1, 9):
                t = i / 8.0; u = 1 - t
                cur.append((u**3*p0[0] + 3*u*u*t*a[0][0] + 3*u*t*t*a[1][0] + t**3*a[2][0],
                            u**3*p0[1] + 3*u*u*t*a[0][1] + 3*u*t*t*a[1][1] + t**3*a[2][1]))
            pos = a[2]
        elif op == "closePath":
            if cur and start: seg(pos, start); pos = start
    if cur: lignes.append(cur)
    return lignes


def profils(font, nom):
    """-> (bords, ymin, ymax) ; bords[y] = (x_gauche, x_droit) de l'encre."""
    lignes = _polylignes(font, nom)
    pts = [p for l in lignes for p in l]
    if not pts:
        return {}, 0.0, 0.0
    ymin = min(p[1] for p in pts); ymax = max(p[1] for p in pts)
    bords = {}
    y = math.floor(ymin / PAS) * PAS
    while y <= ymax:
        xs = []
        for l in lignes:
            for i in range(len(l) - 1):
                (x0, y0), (x1, y1) = l[i], l[i + 1]
                if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
                    xs.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
        if xs:
            bords[round(y)] = (min(xs), max(xs))
        y += PAS
    return bords, ymin, ymax


class Mesureur:
    def __init__(self, font, pente=1.0, **_):
        self.pente = pente
        self._masques = {}
        self.font = font
        self.cm = font.getBestCmap()
        self.hmtx = font["hmtx"]
        self._cache = {}

    def prof(self, nom):
        if nom not in self._cache:
            self._cache[nom] = profils(self.font, nom)
        return self._cache[nom]

    def masque(self, nom, cote):
        """Profil du glyphe apres application du cone de visibilite.

        L'encre ne masque le blanc que dans un cone : un creux etroit et
        profond - l'echancrure d'un E, le dessous du bras d'un T - est
        bouche a l'oeil par l'encre voisine, alors qu'un coin largement
        ouvert - celui d'un "AV" - ne l'est pas, parce qu'aucune encre n'est
        assez proche pour le couvrir.

        C'est ce qui distingue un blanc appartenant a la lettre d'un blanc
        appartenant a l'intervalle. Un ecretage a profondeur fixe, lui, les
        confond : il bouchait le coin du "AV" aussi bien que l'echancrure du
        "E", et le "AV" ressortait comme n'ayant pas besoin de crenage.
        """
        cle = (nom, cote)
        if cle in self._masques:
            return self._masques[cle]
        bords, _, _ = self.prof(nom)
        ys = sorted(bords)
        out = {}
        for y in ys:
            if cote == "droit":
                out[y] = max(bords[t][1] - self.pente * abs(y - t) for t in ys)
            else:
                out[y] = min(bords[t][0] + self.pente * abs(y - t) for t in ys)
        self._masques[cle] = out
        return out

    def detail(self, na, nb):
        """-> (ecart minimal, ecart moyen) sur la bande reunie."""
        ma, mb = self.masque(na, "droit"), self.masque(nb, "gauche")
        if not ma or not mb:
            return None
        ya, yb = sorted(ma), sorted(mb)
        bande = sorted(set(ya) | set(yb))
        if len(bande) < 3:
            return None
        adv = self.hmtx[na][0]
        mini, tot = 1e9, 0.0
        for y in bande:
            # hors de sa propre hauteur, le glyphe prolonge son profil selon
            # le meme cone : le blanc y est reel mais s'eloigne progressivement
            d = ma[y] if y in ma else max(ma[t] - self.pente * abs(y - t) for t in ya)
            g = mb[y] if y in mb else min(mb[t] + self.pente * abs(y - t) for t in yb)
            e = (adv - d) + g
            mini = min(mini, e)
            tot += e
        return mini, tot / len(bande)


# ---------------------------------------------------------------------------
# Classement et generation
# ---------------------------------------------------------------------------

REGLAGES = dict(pente=0.7)


def classes(M, noms, cote):
    """Regroupe les glyphes dont le bord (droit ou gauche) est identique.

    Le "n", le "m", le "h" et le "i" presentent le meme flanc gauche - un fut
    vertical - et se crenent donc de la meme facon. Les regrouper ramene des
    dizaines de milliers de paires a quelques centaines, et c'est ce que fait
    toute police professionnelle.
    """
    groupes = {}
    for n in noms:
        bords, _, _ = M.prof(n)
        if not bords:
            continue
        adv = M.hmtx[n][0]
        if cote == "droit":
            sig = tuple(sorted((y, round((adv - v[1]) / 8)) for y, v in bords.items()))
        else:
            sig = tuple(sorted((y, round(v[0] / 8)) for y, v in bords.items()))
        groupes.setdefault(sig, []).append(n)
    return list(groupes.values())


def ajuster(M, refs):
    """Ajuste base et w sur des paires que le dessinateur a bien espacees."""
    R = [r for r in (M.detail(a, b) for a, b in refs) if r]
    mn = [r[0] for r in R]; mo = [r[1] for r in R]
    X = [a - b for a, b in zip(mn, mo)]; Y = mo
    n = len(X); sx = sum(X); sy = sum(Y)
    sxx = sum(v * v for v in X); sxy = sum(a * b for a, b in zip(X, Y))
    w = -(n * sxy - sx * sy) / (n * sxx - sx * sx)
    return (sy + w * sx) / n, w


def crenage(M, na, nb, base, w):
    r = M.detail(na, nb)
    if not r:
        return 0
    return base - (r[1] + w * (r[0] - r[1]))


def jeu_utile(font):
    """Glyphes qui meritent d'etre crenes.

    On ecarte les accents isoles (´ ` ˆ ¨ ˜ ˚ ¸ ˇ ¯ ˙) et les signes
    combinants : ce sont de petits dessins flottants qui ne se suivent jamais
    dans un texte, et dont l'appariement produit des valeurs absurdes - jusqu'a
    -378 unites entre une cedille et un point suscrit.
    """
    cm = font.getBestCmap()
    garde = set()
    for a, b in [(0x41, 0x5A), (0x61, 0x7A), (0x30, 0x39),
                 (0xC0, 0xD6), (0xD8, 0xF6), (0xF8, 0xFF)]:
        garde.update(range(a, b + 1))
    garde.update([
        0x2E, 0x2C, 0x3A, 0x3B, 0x21, 0x3F, 0x27, 0x22, 0x2D, 0x2F, 0x5C,
        0x28, 0x29, 0x5B, 0x5D, 0x7B, 0x7D, 0x26, 0x40, 0x25, 0x23, 0x2A,
        0x2B, 0x3D, 0x3C, 0x3E, 0x24, 0xA3, 0xA2, 0x20AC, 0xA7, 0xB0, 0xB1,
        0xB5, 0xD7, 0xAB, 0xBB, 0x2018, 0x2019, 0x201C, 0x201D, 0x2013,
        0x2014, 0x2026, 0x2122, 0xAE, 0xA9, 0x152, 0x153, 0x160, 0x161,
        0x178, 0x17D, 0x17E, 0xAA, 0xBA, 0xBC, 0xBD, 0xBE, 0x2030, 0x2039,
        0x203A, 0xBF, 0xA1,
    ])
    return sorted({cm[c] for c in garde if c in cm})


CAT_PONCT = set(".,:;!?'\"«»‹›()[]{}/\\-–—…‘’“”¿¡")
CAT_SYMB = set("&@%#*+=<>$£¢€°±µ×§®©™‰ªº¼½¾")


def categorie(font, nom):
    rev = {v: k for k, v in font.getBestCmap().items()}
    c = chr(rev[nom]) if nom in rev else ""
    if c.isalpha():
        return "LET"
    if c.isdigit():
        return "CHI"
    if c in CAT_PONCT:
        return "PON"
    if c in CAT_SYMB:
        return "SYM"
    return "AUT"


def paire_utile(ca, cb):
    """Une paire vaut-elle d'etre crenee ?

    On ecarte symbole contre symbole et ponctuation contre ponctuation : ces
    suites n'existent pas dans un texte, et leurs dessins - souvent petits et
    places haut ou bas - produisent des valeurs aberrantes (-139 entre une
    etoile et un signe multiplie, +158 entre deux cadratins).
    """
    if ca in ("SYM", "AUT") and cb in ("SYM", "AUT", "PON"):
        return False
    if cb in ("SYM", "AUT") and ca in ("SYM", "AUT", "PON"):
        return False
    if ca == "PON" and cb == "PON":
        return False
    return True
