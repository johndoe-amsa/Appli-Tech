# Appli-Tec

Police de caractères d'entreprise d'**Applitec Moutier SA**, pour la
documentation technique : catalogues, fiches produits, documents bureautiques
et web.

Appli-Tec est dérivée de [**D-DIN**](https://github.com/amcchord/datto-d-din),
publiée par Datto Inc. sous licence SIL Open Font License 1.1, elle-même une
adaptation de la DIN 1451 (norme allemande de 1931).

**Le problème résolu :** D-DIN n'existe qu'en deux graisses, Regular et Bold.
Appli-Tec ajoute les graisses manquantes en calculant les dessins
intermédiaires à partir des deux originaux.

## Graisses disponibles

| Graisse | Poids | Origine | Fût du « I » | Remarque |
|---|---|---|---|---|
| Light   | 300 | fabriquée | 53 u | |
| Regular | 400 | **d'origine** | 73 u | référence |
| Medium  | 500 | fabriquée | 93 u | |
| Bold    | 700 | **d'origine** | 131 u | |
| Heavy   | 800 | fabriquée | 151 u | extrapolée — graisse d'affichage retenue |

Le Black 900 a été évalué puis écarté : il referme trop les contreformes
(74,3 % d'encre dans le « e », pour un seuil de travail à 72 %). Il reste
régénérable à tout moment : `python3 tools/build.py 1.6667 900 Black`.

**Chaque graisse a son italique** en largeur normale, et le **Condensed**
ajoute cinq romains : 15 fichiers au total.

## Le Condensed

Une seconde largeur, environ **24 % plus étroite**, pour les tableaux de
références et les colonnes de cotes. Cinq graisses romaines, dérivées des deux
masters condensés d'origine par la même méthode que la largeur normale.

Pas d'italique : D-DIN n'en fournit aucun dans cette largeur, et il ne sert
pratiquement jamais dans un catalogue technique.

Le Condensed est volontairement un peu plus fin que la normale au même nom de
graisse — 122 unités contre 131 en Bold. C'est le choix du dessinateur, et il
est juste : une lettre étroite paraît plus grasse à épaisseur égale.

## Les italiques

D-DIN ne fournit qu'**un seul italique**, en Regular. Les quatre autres sont
obtenues par report de l'écart de graisse mesuré sur l'axe romain :

```
italique(graisse) = italique(400) + cisaillement( romain(graisse) − romain(400) )
```

avec un cisaillement de `tan(12°)`, l'inclinaison exacte de l'italique d'origine.

C'est important : l'italique de D-DIN **n'est pas un penchage mécanique**. Sur
169 glyphes comparables, 64 ont été redessinés par le dessinateur — les rondes
surtout. Le « a » italique est un `ɑ` à un seul étage, une lettre différente du
« a » à deux étages du romain. Pencher les romains aurait jeté ce travail ; le
report de l'écart le préserve, seule l'épaisseur change.

### Les pièges rencontrés

**Pencher une lettre détruit ses extrema horizontaux.** Un point à tangente
verticale ne l'est plus après 12° d'inclinaison. L'appariement se fait donc
sur l'italique **redressé**, et n'est repenché qu'à la fin.

**Les micro-repères.** Le terminal du « e » romain porte deux ergots verticaux
de 3 et 5 unités — un artefact du tracé, pas une articulation de la lettre —
que l'italique n'a pas. Les repères distants de moins de 15 unités sont
désormais fusionnés, l'angle l'emportant sur l'extremum.

**L'insertion des points de remplissage.** Quand un intervalle doit recevoir
des points pour égaler l'autre dessin, ils sont insérés **à la position qu'ils
occupent** dans celui-ci, et non en coupant le plus long segment en deux — ce
qui les envoyait au fond de la courbe, à 120 unités de leur place, et laissait
l'écart de graisse du terminal y creuser une encoche. Résidus ramenés de 123 à
29 unités sur le « e », de 129 à 28 sur le « c », de 127 à 24 sur le « s ».

**Des points au même nombre, mais pas à la même place.** L'épaule du « C »
romain porte deux points intermédiaires, au tiers et aux deux tiers de la
courbe ; celle du Bold n'en porte qu'un, à mi-chemin. Appariés par rang, le
point du tiers glissait vers le milieu. Interpolé, le défaut restait discret ;
extrapolé au Heavy, le point dépassait son voisin et le contour se repliait :
l'encoche du « C » des italiques Bold et Heavy. Chaque dessin reçoit
désormais les positions de l'autre qui lui manquent, si bien que tout point
a un homologue au même endroit. Couper une courbe ne change pas son tracé.
Le même correctif lisse `C` `Ç` `G` `S` `6` `9` `@` `&` `¶` `Þ` et les
autres rondes touchées à des degrés moindres.

**Des repères qui n'ont pas d'homologue.** Deux dessins peuvent compter
autant de repères sans que ce soient les mêmes : dans le « e » de `æ`, le
romain a un extremum au bout de la barre, l'italique sur le flanc opposé.
Forcé de tout marier, l'apparieur décalait les points d'un rang, et le
Heavy Italic creusait un coin effilé dans la contreforme. Un repère sans
homologue crédible reste désormais seul. De même, un point posé au milieu
d'un trait droit n'est plus un repère : le fût du E de `Œ` Regular porte un
décrochement d'une unité qui attirait à lui le coin de la barre du Bold, et
le Heavy biseautait la jonction.

**Garder ce qui est lisse, garder ce qui est droit.** Deux points voisins
reçoivent des écarts de graisse un peu différents ; extrapolés, ils
zigzaguent là où le dessin d'origine est lisse. Un point lisse dans tous les
dessins de référence le reste (ses poignées sont réalignées), et un point
posé au milieu d'un trait droit dans tous les dessins de référence est
retiré. Les droites sont écrites comme des droites, et les masters (Regular,
Bold, Italic) sont repris tels quels, sans repasser par l'appariement.

**Le `$` et le `¢`.** Dans le Regular, la barre traverse la lettre et ferme
de petites contreformes ; dans le Bold, elle se réduit à deux ergots. Ce
sont deux dessins, pas deux graisses. Le Bold est traduit dans le dessin du
Regular (barre prolongée, par opération booléenne) pour l'interpolation ;
le Bold reste le dessin d'origine à l'identique, et le Heavy l'épaissit
de 10 unités par flanc avec `tools/epaissir.py`.

### Les glyphes penchés depuis le romain

`a` `$` `¢` `|` `¦` `ª` `}` et `.notdef` ne sont pas déduits de l'italique
mais obtenus en penchant le romain à la graisse voulue. Pour `$` et `¢`, leurs
contreformes fusionnent dans le gras. Pour les autres — le `a` surtout, dont
l'italique est une lettre à un seul étage face au romain à deux étages —
aucune correspondance n'existe.

Le `0`, le `3`, le `5`, le `C` et le `Ç` le sont aussi : le dessinateur les
a à peine retouchés, et ses retouches y ont mis des défauts (le bord du
terminal bas du `3` et du `5` reste vertical et rejoint la courbe par un
angle, le bout du `C` est bosselé). Le `%` et le `‰`, eux, sont un vrai
redessin, plus étroit : on garde l'italique, mais les points superflus de
leurs contreformes, qui gonflaient au gras, sont retirés.

Les opérateurs `+ − < = > ^ ± ÷ ¬ _` et les guillemets `« » ‹ ›` le sont
aussi, par choix. D-DIN Italic laisse les opérateurs **droits** au milieu du
texte penché, et obtient ses guillemets en cisaillant les droits : la
branche montante s'amincit, la descendante s'épaissit (52 contre 65 unités à
l'Italic 400). Penchés depuis le romain, les chevrons (`« » ‹ › < > ^`)
retrouvent ensuite deux branches de même épaisseur. Le `×`, symétrique,
reste droit : cisaillé, il a deux bras épais et deux minces ; tourné, il
ressemble à un `+` de travers.

Pour le `a`, c'est un **choix provisoire** : un penchage maintenant, un
redessin de la forme italique propre plus tard. Conséquence assumée :
l'Italic 400 diffère du D-DIN Italic d'origine sur ces huit glyphes, et le
reproduit à 1,01 unité près sur tous les autres.

`tools/epaissir.py` reste dans le dépôt, débranché : il épaissit un contour
sans master de référence, à ~27 unités d'écart du vrai Bold de Monotype
(contre ~1 unité pour une vraie interpolation). C'est le point de départ si
l'on reprend le `a` italique.

## Organisation du dépôt

```
fonts/ttf/            polices à installer sur les postes (Windows, macOS)
fonts/woff2/          polices pour le web
sources/upstream-d-din/   les dessins d'origine de Datto, intacts
tools/build.py        générateur de graisses romaines
tools/build_italic.py générateur d'italiques
tools/harmonize.py    mise en compatibilité des contours
tools/crenage.py      mesure du blanc entre lettres
tools/appliquer_crenage.py  écriture de la table GPOS
tools/appliquer_hinting.py  optimisation de l'affichage écran
tools/naming.py       nomenclature OpenType
tools/verifier.py     balayage complet avant livraison
tools/revue.py        visionneur de revue, glyphe par glyphe
tools/tout_construire.sh    reconstruction complète, dans l'ordre
specimen.html         planche de contrôle
```

## Le crénage

D-DIN ne comptait que **122 paires de crénage**, et aucune pour A, T, V, W, Y
ni P. Sur 39 paires critiques dans vos documents, 37 manquaient — dont `AT` et
`T-`, qui sont le format même de vos références.

Appli-Tec en porte environ **5 600 par fichier**, écrites en GPOS par classes.
La méthode mesure le blanc entre deux lettres à chaque hauteur et le ramène à
la valeur que le dessinateur a lui-même fixée sur des paires comme « nn » ou
« HH » — lesquelles ressortent donc à zéro sur les dix fichiers.

Le point dur est de distinguer le blanc qui appartient à la lettre de celui
qui appartient à l'intervalle. Un écrêtage à profondeur fixe les confond : il
bouche le coin ouvert d'un « AV » aussi bien que l'échancrure d'un « E ». Un
**cône de visibilité** les sépare : l'encre ne masque le blanc que dans un
cône.

La valeur de référence est mesurée graisse par graisse, et descend de 166
unités en Light à 102 en Heavy.

## L'affichage écran (hinting)

À l'écran en petit corps, un fût vertical de 1,4 pixel de large tombe à cheval
sur deux pixels : les deux ressortent gris et la lettre paraît floue. Le
hinting est un jeu d'instructions, enfouies dans la police, qui disent au
système de caler ce fût sur un pixel entier.

macOS les ignore ; **Windows s'appuie dessus**, et c'est là que travaillent les
postes d'Applitec, dans Word, autour de 10-11 pt. À l'impression, en revanche,
ça ne change rien.

D-DIN en portait sur 237 de ses 251 glyphes. Reconstruire les contours pour
fabriquer les graisses les a détruites — en laissant les programmes globaux
(`fpgm`, `prep`, `cvt`) en place, sans plus rien à piloter. Elles sont
régénérées avec `ttfautohint`, environ 210 glyphes par fichier ; les 41
restants sont des composites, pilotés par leurs composants.

Les métriques verticales sont inchangées : l'interligne de vos documents
existants ne bouge pas.

## Fabriquer une graisse

```bash
pip install fonttools brotli
python3 tools/build.py <facteur> <poids> <nom>
```

Le facteur situe la graisse entre les deux originaux : `0.0` donne le Regular,
`1.0` le Bold, `0.333` le Medium. En dehors de l'intervalle `[0, 1]`, on
extrapole — c'est là que les contreformes se referment et qu'un contrôle
visuel devient indispensable.

```bash
python3 tools/build.py 0.3333 500 Medium
python3 tools/build_italic.py 1.0 700 "Bold Italic"
```

**Attention à l'ordre** : le crénage puis le hinting sont écrits *dans* les
fichiers produits par les générateurs. Relancer un générateur seul efface les
deux pour la graisse concernée — il faut repasser `appliquer_crenage.py` et
`appliquer_hinting.py` dessus. Pour tout reconstruire proprement :

```bash
./tools/tout_construire.sh
```

## Vérifier avant de livrer

```bash
python3 tools/verifier.py
```

Balaie les 15 fichiers : hinting, GSUB, GDEF, crénage, écritures déclarées,
drapeaux de style, métriques verticales, marges gauches (la marge de la
table des chasses doit égaler le bord du dessin, sinon le moteur de rendu
décale le glyphe), points isolés, progression des fûts, et l'encre de
chaque glyphe comparée à l'interpolation des masters. Ce dernier contrôle est
le seul capable d'attraper un appariement de points décalé d'un cran, qui ne
se voit sur aucune mesure de distance.

## Passer la police en revue, glyphe par glyphe

```bash
python3 tools/revue.py            # différences contre le dernier commit
python3 tools/revue.py 9a46589    # contre une version précise
```

Produit `revue.html`, à ouvrir dans un navigateur : tous les glyphes des
15 styles, un par un, en grand.

| Touche | Action |
|---|---|
| ← → | glyphe précédent / suivant |
| ↑ ↓ | style précédent / suivant, même glyphe |
| 1 2 3 | Normal, Contour (avec les points), Différence |
| F | plein écran |
| R | marquer « à revoir » |
| G | grille de tous les glyphes du style |
| M | seulement les glyphes modifiés |
| L | liste à revoir, avec remarques, à copier |

Le mode Différence superpose la version de référence et colorie la zone qui
a changé. L'écart est la plus grande distance entre l'ancien et le nouveau
contour, en unités (1 000 par cadratin). Sous une unité, c'est le bruit de
conversion des courbes, et le glyphe est tenu pour inchangé. En bas, la
bande montre le glyphe courant dans les 15 styles.

## Licence

SIL Open Font License 1.1 — voir [`LICENSE.txt`](LICENSE.txt).

En bref : utilisation commerciale libre et sans redevance, modification
autorisée, redistribution autorisée. **Les documents composés avec cette police
ne sont pas concernés par la licence** (clause 5) — vos catalogues et PDF vous
appartiennent entièrement.

Deux obligations : la police doit rester sous OFL et être accompagnée de son
fichier de licence partout où elle est transmise (agence, imprimeur, site) ; et
elle ne peut pas être vendue seule.

Le nom « D-DIN » est un *Reserved Font Name* : une version modifiée ne peut pas
le porter. C'est la raison pour laquelle cette famille s'appelle Appli-Tec.
