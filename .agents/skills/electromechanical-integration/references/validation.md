# Pipeline déterministe A–D

Figer périmètre, unités, repères, versions, paramètres et critères **avant** la comparaison. Exécuter les portes dans cet ordre. Une porte produit `pass`, `fail`, `unknown` ou `not_executed`, avec motifs et objets concernés ; aucune inconnue n'est traitée comme un succès. Une exigence physique candidate permet une exploration explicitement préliminaire, jamais une qualification fournisseur.

## A — Intégrité

- Identifiants uniques, références d'équipements/connecteurs résolues et orientations observées ; inventaire bijectif avec la source logique du périmètre.
- Chaque liaison apparaît exactement une fois comme route complète, et dans chacun de ses tronçons attendus. Vérifier chaînes contiguës de A à B, aucun raccourci de connectivité, conducteur fusionné, doublon, omission ni ajout. Une modification de topologie ne modifie pas A/B.
- Sources, confiances et hypothèses conservées. Rejeter types, unités, nombres non finis, diamètres négatifs, repères inconnus ou projection qui transforme `null` en nombre.
- Le planificateur contrôle la projection ; vérifier en plus le mapping bijectif `link_id → objet(s) CAO → segments`, car il ne lit pas l'assemblage. Une enveloppe collective ne remplace pas les câbles individuels nécessaires à la validation.

Arrêt local des opérations dépendantes si les données logiques sont incohérentes ; investiguer leur source. Continuer les recherches, calculs et liaisons indépendants pour les propriétés manquantes, en conservant l'état non démontré.

## B — Géométrie fraîche et complète

Sur la copie, inspecter propriétés natives puis générer/recalculer dans un contexte identifié. Capturer exceptions **et** diagnostics FreeCAD. `ArchCable` peut absorber une erreur OCC et garder une ancienne `Shape` : invalider la forme générée dans la copie et utiliser le contrôle de reconstruction fraîche avant de juger sa validité. Ne pas toucher aux formes sources/fabricant.

Contrôler toutes les routes et protections attendues : objets présents, absence d'états Error/Invalid, un fil ouvert ordonné, solides non nuls valides, nombre attendu de solides, volume positif, continuité positionnelle et tangentielle, longueur effective. Sauvegarder puis rouvrir la copie dans un processus neuf et refaire les contrôles ; une réussite en RAM n'atteste pas la finalisation sur disque.

Pour les rayons, analyser la courbe **effective après recalcul**, jamais seulement les points de commande. Lignes et arcs : calcul analytique, avec jonctions contrôlées. Splines : tous les domaines/spans, points singuliers, subdivision adaptative, tolérance de variation et budget enregistrés. Une borne analytique/intervalle ou recherche exhaustive certifiée des extrema peut démontrer un maximum de courbure ; un échantillonnage convergé seul ne le peut pas. Échec si violation détectée ; `unknown` si seuls échantillons favorables, singularité, budget épuisé ou évaluation impossible. Le helper livré échantillonne adaptativement, **ne certifie pas les splines**.

Contrôler positions et tangentes aux deux connecteurs, passages obligatoires (distance à la courbe, pas au nuage seulement), rayons statiques/dynamiques applicables, fixations sur trajectoire et réserves. Comparer diamètre réel, occupation, paroi et enveloppe finale de gaine au prédimensionnement. Une gaine générée n'implique pas sa disponibilité commerciale.

## C — Intégration mécanique

Recenser les occurrences externes avec matrices globales ; un contrôle sur les formes locales ignore les placements d'assemblage. Contrôler paires câble/obstacle, gaine/obstacle, câble/câble et gaine/gaine pertinentes. Un filtre par boîtes englobantes peut réduire le coût, mais ne conclut pas à une collision. Mesurer `common().Volume` et distance BRep, conserver erreurs booléennes comme `unknown` ; volume nul ne prouve pas le dégagement minimal.

Toute exemption nomme précisément les deux occurrences, le type de relation et sa justification. Une inclusion d'un câble dans **l'enveloppe pleine de réservation** de sa gaine est intentionnelle ; l'interférence avec sa paroi matérielle reste interdite. Le helper traite cette seule inclusion vérifiée. Pour appuis, serre-câbles et engagements, documenter les surfaces et limites autorisées, puis contrôler les autres parties ; pas d'exclusion globale d'un équipement.

Vérifier montage/démontage, volume balayé des prises et outils, verrouillage, protection des arêtes, distance aux pièces chaudes/mobiles et zones dangereuses. Vérifier fixations réelles, tenue et desserrage, déformations, abrasion et débattement dans toute la plage de mouvement. Le contrôle nominal statique ne démontre ni collision dynamique absente ni tenue vibratoire. Contrôle interactif et essais physiques demeurent des phases séparées.

## D — Comparaison à périmètre égal

Conserver valeurs initiales/candidates, différences, unités, confiance et méthode. Une valeur indisponible est `null`, jamais zéro. Distinguer métrique abstraite du graphe et mesure de l'assemblage :

| Mesure | Interprétation |
|---|---|
| Faisceaux indépendants | composantes physiques effectivement regroupées, avec branches ; un compte de tronçons n'est pas ce compte |
| Tronçons mutualisés, nombre/longueur | chaînes maximales à membres identiques ; longueur commune comptée une fois |
| Longueur cumulée des câbles | somme de chaque liaison avec réserves et terminaisons ; les gaines ne sont pas des liaisons supplémentaires |
| Dérivations / fixations | nœuds de séparation et pièces réellement retenues ; les sites proposés ne sont pas des colliers réalisés |
| Encombrement / accrochage | enveloppes globales, saillies et volumes nécessaires au montage ; l'aire estimée du graphe ne suffit pas |
| Masse | câbles + gaines + fixations + accessoires, sources et inclusions sans doublon ; total `null` si postes manquants |
| Rayon minimal | minimum démontré ou observé, méthode et domaines ; ne pas comparer échantillonné et exact comme mêmes preuves |
| Collisions / dégagements | périmètre des paires, exceptions, erreurs, distance minimale et marges |
| Maintenabilité | accès, séquence de montage/extraction, possibilité de remplacement, réserve utile ; protocole explicite |

Filtrer les violations impératives avant de classer. Une conformité inconnue reste non démontrée même si le candidat a un meilleur score. L'ordre par défaut est sécurité/compatibilité/montage, dispersion, passages/fixations, encombrement/accrochage, maintenance, longueur/masse ; documenter tout autre ordre. Comparer plusieurs topologies si le regroupement accroît rayon, longueur, température ou complexité de montage.

## Preuve et conclusion

### Verdicts de conception et portée

Conserver les résultats natifs `pass/fail/unknown/not_executed` des contrôles. Ajouter au dossier complet des verdicts par candidat **et par domaine**, avec preuves, hypothèses et couverture. Ils ne remplacent ni les codes du planificateur ni les maturités `Planifié`, `Implémenté`, `Qualifié`, `À valider` de DroneAgricole.

| Statut | Condition |
|---|---|
| `VALIDÉ_GÉOMÉTRIQUEMENT` | contraintes géométriques applicables documentées/établies, contrôles requis réussis sur formes fraîches sauvegardées/réouvertes, poses et tolérances du périmètre couvertes, aucune hypothèse non validée déterminante pour ce verdict ; aucune qualification physique implicite |
| `CANDIDAT_CONDITIONNEL` | solution utile pour poursuivre, sans violation impérative établie dans le périmètre retenu, mais hypothèse, couverture ou validation déterminante encore ouverte ; conditions explicites |
| `NON_CONFORME` | au moins une violation démontrée d'une contrainte applicable, avec objets, seuil, source et résultat ; un score favorable ne l'efface pas |
| `NON_VÉRIFIÉ` | contrôle absent, outil indisponible ou données insuffisantes pour juger ; pas un succès |
| `VALIDATION_PHYSIQUE_REQUISE` | montage, thermique, CEM, traction, vibration ou fatigue exigent encore des preuves physiques adaptées ; peut coexister avec les verdicts géométriques/conditionnels |

Un `pass` face à un rayon **hypothétique** n'autorise jamais `VALIDÉ_GÉOMÉTRIQUEMENT` pour l'admissibilité du câble : conserver le résultat numérique exploratoire et `CANDIDAT_CONDITIONNEL`. Un sous-contrôle indépendant peut être réussi (par exemple absence d'intersection à une pose) sans promouvoir la solution entière. Une hypothèse réfutée rend non conforme le scénario qui viole le seuil étudié ; elle ne démontre pas une propriété fournisseur réelle. Une simulation favorable ou des poses échantillonnées ne garantissent pas la continuité du mouvement ni la tenue physique.

Si aucun candidat n'est démontré admissible, conserver le meilleur conditionnel avec réserves, ou les échecs `NON_CONFORME` s'il n'en existe aucun. Ne pas renommer un candidat violant une contrainte connue pour pouvoir le sélectionner. Donner les prochaines vérifications discriminantes plutôt qu'une déclaration globale « conforme ».

### Journal et finalisation

Réunir un manifeste d'expérience avec SHA-256 des entrées, constructeurs/helpers, configuration et sorties, versions, commandes, tolérances, budgets, baseline, identifiant de candidat et mapping CAO. Rapports de mesures JSON et vue Markdown dérivée ; aucune vue ne devient la source canonique. Les rapports du planificateur et du helper FreeCAD sont séparés : les relier par candidat, hashes et IDs avant de conclure ; pas de fusion implicite entre deux exécutions.

Conserver dans cette preuve le [journal structuré des décisions](engineering-autonomy.md#journal-structuré-de-conception), y compris variantes rejetées, données et hypothèses qui conditionnent les résultats. Dans DroneAgricole, intégrer la vue utile dans les documents vivants plutôt que créer un journal narratif séparé.

```json
{"phases":{"offline":"passed","generation":"not_executed","recompute":"not_executed","saved_reopened":"not_executed","interactive":"not_executed","physical":"not_executed"},"conclusion":"preliminary","unknowns":["manufacturer_dynamic_radius"],"candidate_id":"candidate-1"}
```

La première mission de création de cette skill n'exécute aucun faisceau réel. Les cas synthétiques vérifient des invariants logiciels et des géométries élémentaires ; ils ne qualifient pas le drone. Les chiffres F16 (425,174 mm/R22 candidat, BSpline_K 456,959 mm/R0,006 échantillonné et échec de gaine, BSpline_P R23,663 et huit intersections dans le périmètre audité) servent de diagnostic historique, pas de nouveaux seuils ni de tests rejoués par la skill.
