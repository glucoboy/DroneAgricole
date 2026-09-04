# Architecture de la station de mission unifiée

| Champ | Valeur |
|---|---|
| Référence | DOC-28 |
| Version | V0.1 |
| Date | 2 septembre 2026 |
| Statut | Architecture approuvée, socle C++ implémenté |
| Références | DOC-19, ADR-0004, ADR-0006, ADR-0007 |

## 1. Rôle de l'application

L'application desktop Qt est la station métier du système. Elle doit couvrir le cycle complet entre les deux drones :

```text
drone cartographe
  -> réception et contrôle des acquisitions
  -> compilation des données
  -> construction d'une carte candidate
  -> édition des entités et instructions métier
  -> contrôle, approbation et signature
  -> préparation et simulation de la mission
  -> transfert carte + mission
drone de traitement
  -> retour des données de mission
  -> compilation et rapport de traitement
```

Cette responsabilité ne transforme pas l'application en autorité de vol. PX4 conserve les fonctions critiques et QGroundControl la supervision opérationnelle du vol. La station produit, vérifie et transfère des paquets de données et des consignes haut niveau approuvées.

## 2. Frontières du code

Le code est séparé en quatre ensembles :

| Couche | Emplacement | Responsabilité |
|---|---|---|
| Shell opérateur | `software/cpp/ui/`, `software/cpp/src/ui/` | navigation, formulaires `.ui`, visualisation, portes opérateur |
| Station métier | `software/cpp/include/drone_agricole/station/`, `software/cpp/src/station/` | workflow, modules, paquets, validation et audit |
| Noyau technique | `software/cpp/include/drone_agricole/core/`, `software/cpp/src/core/` | contrats existants, résultats, datasets, analyses et runners |
| Adaptateurs | exécutables C++ et paquets ROS 2 | stockage, calculs headless, Docker, ROS 2 et transports futurs |

La bibliothèque `drone_agricole_station` ne dépend que de Qt Core. Elle ne dépend ni de Qt Widgets, ni de `MainWindow`, ni d'un algorithme tiers. L'application Qt et les outils headless peuvent tous deux la consommer.

`IStationModule` est le port d'extension minimal. Un futur module déclare sa responsabilité puis valide une requête typée. Son exécution concrète sera fournie par un adaptateur headless observable et testable. La forme définitive des tâches longues et de leur reprise reste **À valider** au premier module B1.

## 3. Catalogue initial des modules

| Identifiant | Fonction | Entrée principale | Sortie principale | Maturité actuelle |
|---|---|---|---|---|
| `survey-reception` | réception et intégrité des acquisitions | `SurveyRunPackage` | paquet importé | Planifié |
| `survey-compilation` | normalisation, horodatages, calibrations, qualité | `SurveyRunPackage` | paquet compilable | Prototype |
| `map-construction` | trajectoire optimisée et carte candidate | `SurveyRunPackage` | `VineyardMapPackage` | Planifié |
| `map-editing` | entités, zones et instructions métier | `VineyardMapPackage` | nouvelle version candidate | Planifié |
| `map-approval` | revue, approbation et signature | carte candidate | carte approuvée | Planifié |
| `treatment-mission-preparation` | prescription, route et paramètres du bras | carte approuvée | `TreatmentMissionPackage` | Planifié |
| `mission-simulation` | simulation et porte de mission | mission candidate | résultat de validation | Opérationnel préliminaire pour PX4/LIO |
| `operational-transfer` | vérification et transfert au drone | carte + mission approuvées | accusé de réception | Planifié |
| `treatment-return-reception` | import du retour d'opération | `MissionReportPackage` | paquet contrôlé | Planifié |
| `treatment-report-compilation` | couverture, dose, bras, incidents et rapport | paquet de retour | rapport consolidé | Planifié |

Le catalogue décrit la cible sans prétendre implémenter les modules planifiés. Leur maturité ne peut être augmentée qu'avec un contrat, des tests et une preuve de résultat.

## 4. Données et versions

Les cinq paquets de l'ADR-0004 restent les frontières stables :

- `SurveyMissionPackage` ;
- `SurveyRunPackage` ;
- `VineyardMapPackage` ;
- `TreatmentMissionPackage` ;
- `MissionReportPackage`.

Une référence de paquet porte un identifiant, une version, un manifeste, une empreinte de contenu et, lorsqu'elle existe, une référence de preuve d'approbation. Les formats volumineux restent référencés par chemin ou URI et checksum ; ils ne sont pas versionnés dans Git.

Une carte approuvée n'est jamais modifiée en place. Une édition produit une nouvelle candidate. La signature cryptographique, les rôles opérateur, le magasin de confiance et les règles de révocation restent **À valider**.

## 5. Évolution prévue de l'interface

La navigation Qt devra progressivement exposer :

1. **Acquisitions** ;
2. **Cartes** ;
3. **Missions** ;
4. **Transferts** ;
5. **Opérations et rapports** ;
6. **Simulations et validation**.

Les vues statiques restent décrites au maximum dans des fichiers `.ui`. Une vue planifiée doit être clairement distinguée d'une fonction opérationnelle. Aucun bouton ne doit transférer ou approuver un paquet sans validation explicite et journal d'audit.

## 6. Règles d'extension

Pour intégrer une nouvelle fonction :

1. rattacher l'exigence à un module du catalogue ;
2. définir ou versionner son paquet d'entrée et de sortie ;
3. implémenter la logique dans un composant C++17 headless ;
4. fournir un adaptateur respectant `IStationModule` ;
5. écrire les tests de contrat, de sécurité et de reprise ;
6. ajouter la vue Qt dans un fichier `.ui` ;
7. archiver le résultat et mettre à jour la traçabilité.

## 7. Traçabilité du socle

| Exigence | Composant | Test | Résultat |
|---|---|---|---|
| STN-FUN-001 — recevoir les acquisitions cartographe | `survey-reception` | présence et unicité dans `TestStationArchitecture` | Architecture conforme, fonction planifiée |
| STN-FUN-002 — compiler et construire la carte | `survey-compilation`, `map-construction` | ordre du workflow | Architecture conforme, construction planifiée |
| STN-FUN-003 — éditer les informations métier | `map-editing` | catalogue et types de paquets | Architecture conforme, fonction planifiée |
| STN-FUN-004 — approuver et signer la carte | `map-approval`, `PackageReference` | porte opérateur et entrée/sortie carte | Architecture conforme, mécanisme **À valider** |
| STN-FUN-005 — préparer et transférer au drone | préparation, simulation, transfert | carte + mission exigées par le transfert | Architecture conforme, transport **À valider** |
| STN-FUN-006 — recevoir les données de traitement | `treatment-return-reception` | ordre du workflow | Architecture conforme, fonction planifiée |
| STN-FUN-007 — compiler le rapport | `treatment-report-compilation` | entrée/sortie `MissionReportPackage` | Architecture conforme, fonction planifiée |
| SAFE-REQ-001 — préserver l'autorité PX4 | tous les descripteurs | aucun module ne contrôle les fonctions critiques | Conforme |

## 8. Prochaine implémentation

Le prochain module autorisé reste B1 : `survey-reception` puis `survey-compilation`. Il doit commencer par les schémas `SurveyMissionPackage` et `SurveyRunPackage`, leur vérification d'intégrité et l'import reproductible d'un jeu BotanicGarden. La construction de carte, la signature et le transfert ne doivent pas être simulés par des boutons factices.
