---
name: drone-agricole-freecad
description: "Créer, modifier ou vérifier les conceptions FreeCAD durables, références de pièces, sous-assemblages, assemblages, placements et manifestes mécaniques du projet Drone Agricole. Ne pas utiliser pour un simple schéma électrique, une note matérielle ou une illustration sans modèle CAO."
---

# CAO FreeCAD du Drone Agricole

Préserver une CAO paramétrique, réutilisable et traçable. Travailler sous `hardware/mecanique/<conception>/` pour tout artefact durable.

## Charger uniquement le contexte utile

Lire :

- `hardware/mecanique/README.md` pour la hiérarchie CAO commune ;
- le `README.md` et le manifeste de la conception ciblée, par exemple `hardware/mecanique/cartographe/README.md` et `hardware/mecanique/cartographe/manifest.json` ;
- `docs/architecture/ARCHITECTURE_MECANIQUE.md` (`DOC-MEC`) pour l'architecture, la BOM, les choix et leur maturité ;
- `docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md` (`DOC-ELEC`) lorsque la modification touche alimentation, connectique, câblage, synchronisation ou interfaces ;
- `docs/architecture/HLD.md` (`DOC-HLD`) seulement si le rôle ou la frontière système change ;
- `docs/VALIDATION_QUALIFICATION.md` (`DOC-VAL`) lorsqu'une vérification ou une qualification est ajoutée.

Ne charger les JSON de `verification/` que pour le contrôle concerné.

## Structurer la conception

Maintenir dans chaque conception :

- `pieces/fabriquees/` : un fichier `.FCStd` par référence fabriquée, avec son arbre de construction natif ;
- `pieces/commerce/` : un fichier par référence achetée ou enveloppe provisoire ; la représentation interne du fabricant peut être conservée ;
- `sous_assemblages/` : documents liant les références de pièces par liens externes ;
- `assemblages/` : assemblage final liant les sous-systèmes ;
- `sources_fabricants/` : fichiers originaux inchangés ;
- `exports/` : formats dérivés régénérables ;
- `verification/` : contrôles structurés, résultats et limites connues.

Réutiliser la même référence pour les occurrences répétées. Ne pas dupliquer un fichier de pièce pour représenter un placement différent. Conserver les repères existants sauf besoin explicite et documenté ; porter les transformations sur les occurrences.

Ne pas aplatir une pièce conçue ni remplacer son arbre natif par un solide importé. Ne jamais modifier une source fabricant ; dériver l'enveloppe ou l'adaptation dans une référence distincte.

## Maintenir le manifeste

Après une création, suppression, substitution ou modification de placement, mettre à jour le manifeste de la conception :

- références, fichiers, types et statuts ;
- occurrences, référence réutilisée, assemblage parent et matrice de placement ;
- sous-assemblages et assemblages finaux ;
- configuration active, variante archivée et liens vers les preuves pertinentes.

Utiliser des identifiants de besoin ou d'exigence et des références vers `DOC-MEC`, `DOC-ELEC` ou `DOC-VAL`, sans dépendre d'un document de décision séparé. Marquer **À valider** toute enveloppe, cote, masse, matériau, choix fournisseur ou performance non confirmé.

## Vérifier et documenter

Adapter les contrôles au changement :

- réouverture et recalcul sans erreur ;
- présence des arbres natifs et validité des liens externes ;
- cohérence entre références, occurrences, fichiers et placements du manifeste ;
- absence d'interférence, accessibilité, débattements et encombrements pertinents ;
- masse, efforts, rigidité, vibration, thermique ou intégrité d'interface seulement si les données nécessaires existent ;
- régénération des exports touchés lorsqu'ils font partie de la livraison.

Conserver les preuves détaillées dans `verification/`, puis synthétiser le résultat et ses limites dans les documents vivants concernés. Une géométrie qui s'ouvre ou un contrôle numérique réussi ne qualifie ni la fabrication, ni le montage, ni le vol, ni la tenue physique. Indiquer clairement les essais non exécutés.

Les fichiers CAO lourds et exports volumineux restent hors Git conformément aux règles du dépôt ; le manifeste et les preuves légères assurent la traçabilité.
