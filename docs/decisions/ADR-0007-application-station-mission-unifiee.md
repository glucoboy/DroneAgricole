# ADR-0007 — Application desktop comme station de mission unifiée

- Statut : accepté
- Date : 2 septembre 2026
- Complète : ADR-0004, ADR-0005 et ADR-0006

## Contexte

L'application Qt actuelle est issue du plan de contrôle des simulations. Le workflow système approuvé confie cependant au même poste logique la réception des acquisitions du drone cartographe, les traitements hors ligne, la production et la validation de la carte, la préparation des missions du drone de traitement, les transferts et l'analyse des retours de mission.

Sans responsabilité explicite de bout en bout, ces fonctions risquent d'être développées sous forme d'outils séparés, avec des formats, des historiques et des interfaces incompatibles. À l'inverse, placer tous les algorithmes directement dans la fenêtre Qt produirait un monolithe difficile à tester, automatiser et déployer sur plusieurs architectures.

## Décision

L'application desktop Qt constitue la **station de mission métier unifiée** du système Drone Agricole. Elle devient le point d'entrée opérateur pour le cycle complet suivant :

1. recevoir et contrôler les données acquises par le drone cartographe ;
2. compiler les acquisitions et construire une carte 3D/sémantique candidate ;
3. éditer les informations métier de la carte et les prescriptions, notamment les données nécessaires à la navigation, au ciblage et au pilotage haut niveau du bras de traitement ;
4. contrôler la qualité, approuver et signer la carte afin de la rendre exploitable ;
5. préparer, simuler, approuver et transférer la carte et la mission vers le drone de traitement ;
6. recevoir les données produites par le drone de traitement ;
7. compiler ces données en carte de couverture, bilan de traitement, événements et rapport traçable.

L'application est une coque de composition et d'orchestration. Les algorithmes, importateurs, compilateurs, constructeurs de carte, validateurs, adaptateurs de transfert et générateurs de rapport restent des modules C++17 headless, indépendants de Qt Widgets et testables sans interface graphique. Les modules exposent des contrats typés à la couche station ; la fenêtre Qt fournit leur navigation, leur configuration, leur état, leurs portes opérateur et leurs visualisations.

La couche métier de la station est indépendante des widgets et des transports concrets. Les dépendances vont du shell Qt vers les interfaces métier, puis vers des adaptateurs de stockage, de calcul ou de communication. Aucun module métier ne dépend de `MainWindow`.

Les échanges conservent les cinq paquets versionnés de l'ADR-0004 :

- `SurveyMissionPackage` ;
- `SurveyRunPackage` ;
- `VineyardMapPackage` ;
- `TreatmentMissionPackage` ;
- `MissionReportPackage`.

Les paquets et résultats validés sont immuables. Une modification d'une carte approuvée crée une nouvelle version candidate et invalide son ancienne preuve d'approbation. La signature doit au minimum lier l'identité de l'approbateur, la version du manifeste et l'empreinte du contenu. Le mécanisme cryptographique, la gestion des identités, le magasin de confiance et le support matériel éventuel restent **À valider** avant toute qualification opérationnelle.

Le transfert utilise un adaptateur explicite et vérifie manifeste, empreintes, compatibilité de version, cible et accusé de réception. Le transport concret — réseau local, liaison radio, support amovible ou autre — reste **À valider**. Le drone de traitement doit rester autonome après le chargement et ne dépend jamais d'une connexion permanente à la station.

QGroundControl conserve la préparation et la supervision de vol, l'armement, les alarmes et l'interruption. PX4 conserve les boucles de vol et les failsafes. La station métier ne commande pas directement les moteurs et ne remplace aucune fonction critique de vol.

Le nom technique `drone-agricole-dashboard` est conservé provisoirement pour la compatibilité des builds et des configurations VS Code. Son éventuel renommage vers un nom de station définitif reste **À valider** et ne change pas la responsabilité décidée ici.

## Architecture logique retenue

```text
Qt 6 Widgets — shell de station et fichiers .ui
                         |
                         v
Couche application — workflow, portes, tâches et audit
                         |
                         v
Couche domaine — paquets, carte, mission, approbation, rapport
                         |
                         v
Ports C++17 — acquisition, calcul, stockage, signature, transfert
                         |
                         v
Adaptateurs — fichiers, ROS 2, Docker, réseau, drone, outils headless
```

Les calculs longs sont représentés par des tâches annulables et observables. Leur résultat est écrit dans un nouvel espace de travail ou paquet ; une annulation ou une erreur ne modifie jamais silencieusement un paquet approuvé.

## Conséquences

- l'interface de simulation devient un module de la station, pas sa finalité unique ;
- l'ajout d'une fonction métier passe par une interface de module et un contrat de paquet, sans étendre directement `MainWindow` avec l'algorithme ;
- l'historique, les versions, les approbations, les transferts et les rapports partagent une même traçabilité ;
- l'interface devra évoluer vers une navigation couvrant acquisition, cartes, missions, transferts, opérations et simulations ;
- les calculs restent automatisables en ligne de commande et déployables dans des environnements Docker `amd64` et `arm64` ;
- les fonctions non encore implémentées sont exposées comme planifiées et ne sont jamais présentées comme opérationnelles ;
- les données brutes, cartes volumineuses, modèles et résultats restent hors versionnement Git.

## Alternatives rejetées

- Une application différente par étape : fragmente la traçabilité, les versions et l'expérience opérateur.
- Tous les algorithmes dans le processus Qt : empêche l'isolation, l'automatisation et la reprise robuste des calculs longs.
- Une station qui commande directement le vol : viole la séparation PX4/ROS 2 et rend la liaison station critique.
- Modifier sur place une carte signée : détruit la preuve d'approbation et la reproductibilité.

## Validation attendue

Chaque lot futur doit démontrer la chaîne `exigence -> module/algorithme -> test -> paquet/résultat`. La première validation de cette décision porte sur le catalogue de modules C++ et ses frontières ; les fonctions de calcul, de signature et de transfert seront validées dans leurs lots respectifs.
