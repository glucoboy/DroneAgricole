# Contrat d'intégration et règles de cohabitation

## Deux niveaux de données

Le dossier d'intégration porte les contraintes complètes ci-dessous. Le [contrat du planificateur](planner-contract.md) est une **projection réduite** de ce dossier ; il ne valide pas les champs électriques, CEM ou mécaniques non consommés. Conserver la référence et le SHA-256 du dossier complet dans les preuves. Une adaptation ne doit ni inventer des valeurs ni perdre les références à la source.

Unités communes : mm, degrés, A, V, °C, Hz, g, g/m. Choisir un repère d'assemblage global, préciser convention des matrices et unité avant toute conversion. Les axes de sortie pointent **du connecteur vers l'extérieur** : la tangente du câble orienté de A vers B suit l'axe A et s'oppose à l'axe B. Ne pas utiliser un label FreeCAD comme identité stable.

Chaque paramètre physique est un enregistrement :

```json
{"value": null, "unit": "mm", "data_class": "INCONNUE", "source": null, "confidence": "unknown", "scope": "dynamic", "revision": null, "uncertainty": null, "input_refs": [], "method": null}
```

`data_class` est obligatoire dans le dossier complet pour les données nouvelles ou réexaminées. Ne pas reclasser silencieusement une ancienne valeur sans inspecter sa provenance :

| Classe | Critère et provenance minimale |
|---|---|
| `MESURÉE` | mesure ou inspection effective, méthode, objet/occurrence, repère, instrument/outil, incertitude et preuve ; préciser CAO ou matériel |
| `DOCUMENTÉE` | source identifiable, référence, version/révision (ou absence de version explicite avec date d'accès/empreinte), page et variante applicables |
| `CALCULÉE` | résultat reproductible, formule/modèle et entrées sourcées par références, unités, domaine et propagation des incertitudes |
| `ESTIMÉE` | approximation technique, méthode/analogie, justification d'applicabilité, plage d'incertitude et limites |
| `HYPOTHÈSE` | valeur ou modèle choisi pour explorer, justification des bornes, prédiction et condition de réfutation |
| `INCONNUE` | aucune détermination fiable ; `value:null`, recherches effectuées et moyen de lever l'inconnue |

Une donnée `CALCULÉE` peut dépendre d'une `HYPOTHÈSE` : la classe décrit son origine, pas sa validité physique. Préserver la chaîne `input_refs` jusqu'aux sources et propager les réserves. Une incertitude non quantifiable reste `null` avec raison, jamais zéro. Les paramètres de scénario sont des enregistrements distincts de l'inconnue source.

Le champ historique `confidence` vaut toujours `supplier`, `measured`, `candidate` ou `unknown` pour rester compatible avec le planificateur v1. Projection conservatrice : `DOCUMENTÉE` → `supplier` seulement pour une spécification fabricant applicable ; `MESURÉE` → `measured` uniquement dans le domaine effectivement observé. Une mesure CAO ne fournit pas une limite de traction ou de fatigue matérielle. `CALCULÉE`, `ESTIMÉE`, `HYPOTHÈSE`, ainsi que toute documentation non fournisseur ou non applicable → `candidate` ; `INCONNUE` → `unknown`. Cette projection peut laisser un calcul rigoureux en réserve : le dossier complet porte sa justification, pas une promotion artificielle du champ historique. `supplier` exige document, révision, page et variante ; `candidate` renvoie au calcul/estimation/hypothèse et à ses limites.

Valeur absente = `null`, jamais zéro, rayon de 22 mm par défaut ou diamètre déduit arbitrairement du type de signal. Source documentaire ≠ tolérance garantie ; estimation ≠ spécification fournisseur. Distinguer rayon statique et dynamique, température, nombre de cycles et conditions de mesure.

## Contraintes et libertés de conception

Classer chaque contrainte rencontrée avec `id`, `constraint_class`, objets concernés, justification/source, domaine, valeur/plage et contrôle associé :

- `IMPÉRATIVE` : fonction mécanique/électrique, géométrie ou sécurité justifiée ; elle prime les scores et préférences.
- `MODIFIABLE` : paramètre de conception ajustable dans un domaine décrit ; modifier sur copie puis recontrôler les conséquences.
- `HÉRITÉE` : choix de l'ancienne intégration sans justification confirmée ; conserver comme baseline, investiguer son rôle et comparer des alternatives.
- `INCONNUE` : origine ou nécessité non établie ; rechercher et analyser son rôle avant de l'assouplir, surtout si la sécurité pourrait être concernée.

Les longueurs, retenues et stations ne deviennent pas impératives parce qu'un constructeur les contient. Construire les passages obligatoires après cette classification. Documenter avant/après, contraintes affectées et vérifications ; un choix hérité peut devenir impératif si une fonction est démontrée. Une contrainte ne devient pas modifiable uniquement parce qu'elle empêche le routage.

## Objets du dossier complet

| Objet | Champs à conserver |
|---|---|
| Liaison logique | `id`, référence du schéma/registre, équipement et connecteur A/B, broches/conducteurs si définis, fonction et variante ; conserver l'identité au travers des tronçons |
| Connecteur/port | identifiant, référence fabricant, occurrence CAO et chemin de lien, position, orientation/matrice, axe de sortie, repère local/global, volume d'engagement et d'extraction, outil et verrouillage, limite de traction ; chaque valeur sourcée |
| Câble | catégorie, nature (flexible, coaxial, multiconducteur, blindé…), diamètre/enveloppe et tolérances, rayon statique/dynamique, réserve de service, masse linéique, constitution, prétermination et encombrement des connecteurs |
| Électrique | tensions, courant continu/crête et profil, fréquence/fronts, impédance si pertinente, section/isolement, dissipation, blindage et terminaison, référence de masse ; inconnues explicites |
| Conditions | température, vibrations, mouvement relatif/course, zone dangereuse, humidité/abrasion, séparation fonctionnelle, démontages/cycles, déformations prévisibles |
| Corridor | nœuds d'entrée/sortie, espace utilisable, obstacles, zones interdites, passages obligatoires, tolérances et marges ; arêtes distinctes si une séparation spatiale est nécessaire |
| Groupe/segment | ID physique, ensemble de `link_id`, arêtes, ordre et offsets des câbles, enveloppe estimée/réelle, relation aux gaines ; aucun changement des bornes logiques |
| Gaine/protection | référence ou candidat, diamètre intérieur/extérieur, épaisseur, ouverture/fendue, matière, abrasion/thermique, rayon et taux d'occupation, extrémités, masse et inclusion dans la BOM |
| Dérivation | nœud, membres entrants/sortants, accessibilité, protection, rayons, absence d'épissure électrique implicite |
| Fixation | occurrence, type/support, câbles/groupes retenus, position, plage de serrage, effort et espacement admissibles, jeu, accès outil, preuve ; distinguer site potentiel et pièce réellement montée |
| Contrôle | identifiant d'exigence, objets/instances, méthode, seuil et sa source, résultat, tolérances, phase, données/logiciel/empreintes et limites |

La connectivité peut être plusieurs circuits dans un câble multiconducteur. Conserver ce détail au dossier ; ne pas convertir les conducteurs en câbles supplémentaires ni compter une gaine comme une liaison électrique.

## Compatibilité configurable et contextuelle

Taxonomie de départ, modifiable : `propulsion_power`, `electronics_power`, `digital`, `sensitive_analog`, `rf_gnss`, `control_telemetry_sensors`. Une catégorie aide à rechercher les contraintes ; elle ne prouve pas leur respect. Aucun `allow` ou `deny` universel n'est préchargé.

Pour chaque cohabitation candidate, décider `allow`, `deny` ou `unknown` en citant les conditions : courant et retour de courant, fronts/couplage, blindage et terminaisons, température/déclassement, indépendance fonctionnelle et montage. Une autorisation vaut uniquement pour ces conditions, ces références et cette configuration. Un blindage inconnu ne vaut pas blindage absent ni blindage efficace.

Avant de projeter vers une règle par paire de catégories du planificateur, vérifier que **tous** les câbles de chaque catégorie satisfont le même domaine de validité. Sinon créer des catégories contextualisées (`digital_shielded_revA`, par exemple) ou séparer les sous-problèmes avec leurs contraintes d'interface. Le moteur traite `unknown` de façon conservatrice pour le partage ; il ne transforme pas cette absence de preuve en interdiction électromagnétique générale. Un regroupement exige l'accord de chaque paire et la vérification du groupe complet (courant/échauffement cumulé, remplissage, fonctions redondantes).

Deux routes séparées dans la même arête abstraite ne prouvent **aucune distance CEM**. Si une règle exige un écart, créer des corridors spatialement distincts, attribuer des axes/volumes et mesurer l'écart final. Ne pas utiliser un score de longueur pour contourner cette contrainte.

## Dimensionnement des gaines

À diamètres circulaires connus, aire occupée `A = π/4 × Σdᵢ²` ; diamètre intérieur de prédimensionnement `Daire = sqrt(Σdᵢ² / f)` avec taux `0 < f ≤ 1` explicitement justifié. Ce calcul est une **condition d'aire**, pas une démonstration d'empilement de disques, d'insertion ou de fabrication. Pour un seul câble, ne pas ajouter automatiquement une gaine.

Vérifier ensuite disposition des sections, tolérances, assemblabilité (passage du connecteur le plus gros ou gaine ouverte), courbures, friction, retrait/ajout de câble, chaleur, réserve et références disponibles. Choisir une référence effective avec diamètre intérieur utile suffisant et diamètre extérieur incluant paroi/protection ; sinon conserver un candidat. Le rayon du faisceau et les offsets internes peuvent imposer une contrainte plus forte que chaque câble seul. Prévoir des entrées/sorties protégées et une transition de section à chaque dérivation. Évaluer les volumes internes, parois et enveloppes de réservation séparément ; ne jamais compter leur union comme cuivre ou comme plusieurs masses de gaine.
