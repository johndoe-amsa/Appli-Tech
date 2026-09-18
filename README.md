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

**Chaque graisse a son italique** : 10 fichiers au total. Largeur Condensed :
pas encore fabriquée.

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

### Neuf glyphes penchés depuis le romain

`a` `$` `¢` `|` `¦` `ª` `}` `‰` et `.notdef` ne sont pas déduits de l'italique
mais obtenus en penchant le romain à la graisse voulue. Pour `$` et `¢`, leurs
contreformes fusionnent dans le gras. Pour les autres — le `a` surtout, dont
l'italique est une lettre à un seul étage face au romain à deux étages —
aucune correspondance n'existe.

Pour le `a`, c'est un **choix provisoire** : un penchage maintenant, un
redessin de la forme italique propre plus tard. Conséquence assumée :
l'Italic 400 diffère du D-DIN Italic d'origine sur ces neuf glyphes, et le
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
tools/build.py        générateur de graisses
tools/harmonize.py    mise en compatibilité des contours
specimen.html         planche de contrôle
```

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
