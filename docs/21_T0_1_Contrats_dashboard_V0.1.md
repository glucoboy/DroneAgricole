# DOC-21 — T0.1 — Contrats et compatibilité du tableau de bord

- Version : V0.1
- Date : 29 août 2026
- Statut : opérationnel préliminaire
- Références : DOC-19, DOC-20, ADR-0005

## 1. Objectif

Le lot T0.1 crée les contrats versionnés nécessaires pour faire évoluer le tableau de bord LIO actuel vers le plan de contrôle générique défini dans l'ADR-0005. Il doit préserver les résultats existants, permettre leur lecture commune et préparer l'ajout de datasets sans condition codée en dur dans le serveur.

T0.1 ne remplace pas encore les lanceurs historiques ni l'interface de sélection actuelle. Cette migration appartient à T0.2. Il fournit le socle validé que T0.2 consommera.

## 2. Contrats publiés

Les schémas JSON utilisent le draft 2020-12 et sont stockés dans `configs/visualization/schemas/`.

| Contrat | Rôle |
|---|---|
| `DatasetDefinition` | Décrit un dataset, ses séquences, capacités, ressources, état local et licence. |
| `SimulationDefinition` | Décrit une simulation, ses variantes, paramètres, entrées exigées, sorties et vues. |
| `RunRequest` | Fige la demande transmise à un runner. |
| `RunManifest` | Décrit l'exécution réellement effectuée, son état, ses entrées, paramètres et fichiers. |
| `Metrics` | Fournit des métriques synthétiques comparables et des groupes détaillés. |
| `Artifacts` | Inventorie les fichiers rechargeables, leur rôle et leur type. |
| `Event` | Normalise la chronologie d'une exécution ou d'un scénario. |

`DatasetDefinition` s'ajoute aux six contrats explicitement prévus dans DOC-20. Cette séparation évite que les datasets restent imbriqués dans un catalogue LIO monolithique.

## 3. Sélection générique des datasets

Une simulation ne cite pas une liste fermée de datasets. Elle déclare les capacités requises, par exemple :

- `lidar.pointcloud2` ;
- `imu.si` ;
- `ground_truth.pose`.

Chaque dataset et chaque séquence déclarent leurs propres capacités. Le registre calcule alors l'intersection compatible pour chaque variante algorithmique. Une séquence désactivée ou dépourvue d'une capacité obligatoire est automatiquement exclue.

Pour ajouter ultérieurement un dataset, le chemin prévu est donc :

1. créer un fichier dans `configs/visualization/datasets/` ;
2. déclarer ses séquences, ressources et capacités ;
3. valider le registre ;
4. ajouter, dans T0.2, un profil de conversion/configuration lorsque le format capteur diffère du pipeline courant.

Un test automatisé ajoute un second dataset compatible dans un registre temporaire et vérifie qu'il devient sélectionnable sans modification du code.

## 4. Première définition concrète

`configs/visualization/datasets/botanicgarden.json` décrit BotanicGarden et les trois entrées déjà exploitées :

- `1006-03-smoke` — 5 s ;
- `1006-03-dynamic` — 30 s ;
- `1006-03-full` — 581,12 s.

La définition indique explicitement que l'installation locale est partielle. Les caméras, annotations sémantiques et cartes de vérité terrain absentes localement sont signalées dans les métadonnées. La licence reste qualifiée de restreinte et la redistribution est interdite.

`configs/visualization/simulations/lio_benchmark.json` décrit le benchmark commun et ses variantes FAST-LIO2, Point-LIO et LIO-SAM. Les paramètres disposent de bornes et d'un niveau d'exposition. Les identifiants canoniques restent indépendants des clés internes des logiciels ; `runner_key` conserve la correspondance nécessaire pour LIO-SAM.

Les configurations LIO référencées sont encore spécifiques à BotanicGarden Velodyne/Xsens. La notion de profil dataset–algorithme sera ajoutée dans T0.2 avant de prétendre exécuter un autre format de capteur.

## 5. Adaptateurs de lecture historique

`software/visualization/result_adapters.py` reconnaît et normalise à la volée :

- les résultats LIO historiques comportant `run_manifest.json` et `metrics.json` ;
- les résultats `drone_agricole.px4_offboard_test.v1` du lot A.

L'adaptation produit en mémoire un `RunManifest`, des `Metrics`, des `Artifacts` et des `Event` T0.1. Aucun fichier historique n'est déplacé, réécrit ou enrichi sur disque. Le contrat indique l'adaptateur et le schéma source utilisés, ce qui prépare les migrations de lecture versionnées.

Les résultats LIO sont rattachés au groupe de comparaison `lio_trajectory_v1`. Les résultats PX4 sont rattachés à `px4_offboard_v1`. Cette séparation empêche une comparaison de métriques sans signification entre domaines différents.

## 6. Intégration transitoire au serveur

Le catalogue historique référence désormais les répertoires de définitions. Au démarrage, le serveur :

- valide toutes les définitions ;
- refuse un chemin de registre extérieur au workspace ;
- calcule les séquences compatibles par simulation et variante ;
- expose ces données dans `contract_options` de l'API d'options.

L'interface graphique continue d'utiliser les contrôles historiques durant T0.1. Le remplacement de cette lecture par les définitions génériques, ainsi que les runners PX4 génériques, relèvent de T0.2.

## 7. Validation réalisée

Huit tests unitaires couvrent :

- le chargement des huit documents JSON Schema ;
- BotanicGarden et les trois variantes LIO ;
- l'ajout déclaratif d'un second dataset ;
- le filtrage d'une séquence incompatible ;
- le rejet d'un chemin sortant du workspace ;
- un `RunRequest` valide ;
- l'adaptation LIO sans écriture ;
- l'adaptation PX4 avec événements.

La commande de validation a aussi été exécutée sur quatre résultats réels du projet : FAST-LIO2, Point-LIO, LIO-SAM et le scénario PX4 de perte Offboard. Les quatre résultats sont reconnus et valident les contrats T0.1. Chaque résultat LIO expose dix métriques synthétiques et le résultat PX4 sept métriques.

## 8. Critères de fin T0.1

| Critère | État |
|---|---|
| Schémas versionnés publiés | Satisfait |
| Définition de dataset séparée du code | Satisfait |
| Compatibilité par capacités | Satisfait |
| Lecture non destructive des résultats LIO | Satisfait |
| Import des résultats PX4 du lot A | Satisfait |
| Migrations de lecture identifiables par adaptateur | Satisfait |
| Tests automatisés | Satisfait |
| Interface entièrement alimentée par les nouveaux contrats | Reporté à T0.2 |

## 9. Suite recommandée

T0.2 doit maintenant :

1. définir l'interface commune des runners headless ;
2. créer les adaptateurs de lancement FAST-LIO2, Point-LIO, LIO-SAM et PX4 ;
3. introduire les profils dataset–variante pour ne plus dépendre de configurations BotanicGarden codées dans le catalogue historique ;
4. alimenter les sélecteurs et paramètres de l'interface depuis `contract_options` ;
5. écrire nativement les contrats T0.1 pour toute nouvelle exécution tout en conservant les adaptateurs historiques.
