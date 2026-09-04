# Plan de développement du workflow et du tableau de bord

| Champ | Valeur |
|---|---|
| Référence | DOC-20 |
| Version | V0.1 |
| Date | 28 août 2026 |
| Statut | Approuvé — exécution portée par ADR-0005 et ADR-0007 |
| Références | DOC-19, ADR-0004, ADR-0005 et ADR-0007 |

## 1. Objectif

Ce plan transforme le workflow validé en lots de développement ordonnés. Chaque lot livre à la fois :

1. un contrat de données stable ;
2. une baseline algorithmique mesurable ;
3. un lanceur headless reproductible ;
4. son intégration dans le tableau de bord ;
5. une visualisation en direct et/ou après calcul ;
6. des métriques et critères d'acceptation ;
7. le rechargement et la comparaison des résultats historiques.

L'application desktop devient la station de mission et le plan de contrôle du workflow complet. La simulation en est un module. Les algorithmes n'habitent pas dans les widgets : les composants headless restent autonomes et testables en ligne de commande, puis l'interface les orchestre au moyen de contrats versionnés.

## 2. Règle transversale du tableau de bord

Un module de simulation n'est pas considéré comme terminé tant que l'opérateur ne peut pas, depuis le tableau de bord :

- sélectionner son dataset, scénario, carte, mission ou modèle ;
- modifier les paramètres expérimentaux autorisés ;
- voir les valeurs par défaut, unités, limites et explications ;
- lancer, suivre, arrêter et identifier clairement l'exécution ;
- visualiser les couches 3D et courbes pertinentes ;
- consulter les métriques, journaux et événements importants ;
- recharger une ancienne exécution sans recalcul ;
- dupliquer ses paramètres pour une nouvelle exécution ;
- comparer plusieurs résultats compatibles ;
- exporter ou ouvrir le rapport et les artefacts produits.

Les outils de diagnostic en ligne de commande restent disponibles pour le développement et l'automatisation. QGroundControl conserve les commandes opérationnelles de vol ; le tableau de bord ne remplace ni PX4 ni la station de sécurité.

## 3. État actuel et écart à combler

| Capacité | État actuel | Cible |
|---|---|---|
| Catalogue datasets/algorithmes | opérationnel pour BotanicGarden et trois LIO | catalogue générique par domaine et scénario |
| Paramètres | nombres, bornes et valeurs par défaut | nombres, booléens, listes, fichiers catalogués, profils et dépendances |
| Lancement/arrêt | un benchmark LIO à la fois | tous les runners approuvés avec politique de concurrence |
| Direct 3D/graphiques | LIO et état PX4 | couches déclaratives par simulation |
| Résultats finaux | `metrics.json` du passage courant | schéma commun + métriques spécialisées |
| Historique | répertoire affiché seulement | index, filtres, détails, favoris et notes |
| Rechargement | absent | scène, métriques et événements rechargeables hors ligne |
| Comparaison | absente | 2 à N exécutions compatibles et écarts de configuration |
| Reproductibilité | manifeste LIO partiel | manifeste commun, images, commits, entrées, paramètres et checksums |

## 4. Architecture cible du tableau de bord

```text
Interface desktop Qt 6
├── Lancer
├── Direct
├── Historique
├── Détail d'une exécution
├── Comparer
└── État du banc
        |
        v
API locale versionnée
├── SimulationCatalog     # capacités et paramètres autorisés
├── RunManager            # lancement, arrêt, files et états
├── TelemetryGateway      # ROS 2/pont local C++ et adaptateurs de couches
├── ResultRepository      # manifestes et artefacts immuables
├── ResultIndex           # cache reconstruisible pour recherche
├── ReplayService         # rechargement sans recalcul
└── ComparisonService     # métriques et configurations comparables
        |
        v
Runners headless approuvés
├── benchmark LIO
├── PX4/Gazebo et fautes
├── acquisition/cartographie
├── perception et mission
├── navigation agricole
└── bras et traitement
```

Le catalogue contient uniquement des runners et chemins approuvés. Le navigateur ne peut fournir aucune commande système arbitraire.

## 5. Contrats techniques communs

### 5.1 Définition d'une simulation

Chaque simulation possède un document validé par schéma :

```text
simulation_id, version, domaine, runner_id
entrées compatibles
paramètres et profils
prérequis et ressources
topics/couches de visualisation
métriques attendues
artefacts attendus
critères de succès
classe de sécurité
```

### 5.2 Répertoire d'une exécution

```text
results/<domaine>/<scénario>/<run_id>/
├── run_manifest.json       # identité, état et versions
├── run_request.json        # demande exacte du tableau de bord
├── effective_config/       # configuration réellement appliquée
├── input_manifest.json     # données/cartes/modèles et checksums
├── metrics.json            # métriques finales communes et spécialisées
├── timeseries/             # MCAP et/ou format tabulaire à valider
├── artifacts.json          # inventaire des fichiers visualisables
├── events.jsonl            # chronologie normalisée
├── logs/
└── report/
```

Les répertoires de résultat sont la source de vérité. Un index local, éventuellement SQLite, accélère les recherches mais doit pouvoir être entièrement reconstruit à partir des manifestes. Les résultats historiques ne sont jamais modifiés pour s'adapter à une nouvelle interface ; un adaptateur de lecture assure leur compatibilité.

### 5.3 États normalisés

```text
QUEUED -> PREPARING -> RUNNING -> STOPPING -> ANALYZING
                                  |              |
                                  v              v
                              CANCELLED       COMPLETED
                                  \              /
                                   +--> FAILED <-+
```

Chaque transition est horodatée dans `events.jsonl`. Un redémarrage du serveur doit retrouver les exécutions terminées et marquer explicitement une exécution abandonnée.

## 6. Politique des paramètres

Le maximum de paramètres utiles est exposé, sans transformer l'interface en éditeur dangereux ou incohérent.

| Niveau | Comportement dans le tableau de bord | Exemples |
|---|---|---|
| Principal | toujours visible et modifiable | dataset, scénario, vitesse, voxel, modèle |
| Avancé | modifiable dans des bornes validées | seuils, itérations, fréquences, bruit simulé |
| Structurel | sélection par profil versionné | calibration, repères, image Docker, firmware |
| Sûreté | visible, verrouillé ou confirmation SITL explicite | failsafe, géofence, action de perte Offboard |
| Dérivé | lecture seule | fréquence effective, checksum, budget calculé |

Chaque paramètre déclare type, unité, valeur par défaut, minimum/maximum ou choix, description, effet attendu, nécessité de redémarrage et classe de sécurité. Les dépendances conditionnelles évitent d'afficher des options inapplicables.

Des profils enregistrés permettent de retrouver rapidement une configuration : `baseline`, `smoke`, `qualification`, `stress`, puis profils propres aux capteurs et calculateurs. Le manifeste conserve toujours les valeurs effectives, même si elles proviennent d'un profil.

## 7. Visualisations communes

La scène 3D devient un empilement de couches activables :

- nuages bruts, enregistrés, colorisés ou sémantiques ;
- trajectoires brute, optimisée, commandée, réelle et vérité terrain ;
- modèle du drone, repères TF et incertitudes ;
- terrain, rangs, pieds, poteaux, fils et obstacles ;
- occupation, ESDF, corridor, géofence et zones interdites ;
- plan global, trajectoire locale et consignes PX4 ;
- bras, buses, cibles et couverture de traitement.

Les graphiques suivent un schéma déclaratif et peuvent afficher ressources, erreurs, fréquences, latences, confiance, distances de sécurité, états de mission, débit, pression et dose. Une chronologie commune aligne les événements avec la scène et les courbes.

## 8. Lot T0 — Socle générique du tableau de bord

Ce lot précède B1.

### T0.1 — Schémas et compatibilité

- créer les schémas `SimulationDefinition`, `RunRequest`, `RunManifest`, `Metrics`, `Artifacts` et `Event` ;
- adapter les résultats LIO actuels sans les modifier ;
- importer les résultats PX4 du lot A ;
- versionner les migrations de lecture.

### T0.2 — Catalogue et runners

- remplacer la logique LIO spécifique par une interface de runner ;
- conserver des adaptateurs FAST-LIO2, Point-LIO et LIO-SAM ;
- ajouter les runners PX4 carré et perte Offboard ;
- valider côté serveur tous les paramètres, entrées et chemins ;
- maintenir une seule exécution active au début, puis introduire une file si nécessaire.

### T0.3 — Historique et rechargement

- indexer les manifestes existants ;
- filtrer par domaine, dataset, scénario, algorithme, date, statut et tags ;
- ouvrir une fiche complète ;
- recharger scène, courbes, événements et métriques sans relancer le runner ;
- proposer « Dupliquer cette configuration ».

### T0.4 — Comparaison et rapports

- vérifier la compatibilité des exécutions ;
- comparer métriques, paramètres et versions ;
- superposer les trajectoires/courbes compatibles ;
- ouvrir ou exporter le rapport associé.

### Porte T0

Le lot est accepté lorsque les trois LIO et les deux essais PX4 peuvent être lancés depuis le tableau de bord, que leurs anciens résultats sont rechargeables, et qu'une comparaison LIO existante est reproductible depuis l'historique.

## 9. Lot B1 — Contrats et acquisition cartographe

### Algorithmes et données

- schémas `SurveyMissionPackage`, `SurveyRunPackage` et début de `VineyardMapPackage` ;
- inspection des caméras BotanicGarden, timestamps, fréquences et extrinsèques ;
- contrôles déterministes de synchronisation, pertes, durée, calibration et couverture ;
- génération d'un `SurveyRunPackage` à partir du dataset.

### Tableau de bord

- choix de la séquence et des pipelines capteurs ;
- paramètres de synchronisation, tolérances, fenêtres et sous-échantillonnage ;
- vue chronologique des flux et images synchronisées ;
- repères capteurs et frustums dans la scène 3D ;
- graphiques de fréquence, décalage temporel, pertes et couverture ;
- rapport `PASS/WARN/FAIL` rechargeable.

### Porte B1

Un package reproductible est généré, audité, visualisé et rechargeable ; aucune donnée manquante n'est silencieuse.

## 10. Lot B2 — Géométrie de carte

### Algorithmes

- FAST-LIO2 comme trajectoire initiale ;
- optimisation globale LiDAR–IMU–GNSS et boucles candidates ;
- reconstruction du nuage maître ;
- projection LiDAR–caméra, visibilité et colorisation ;
- première incertitude géométrique.

### Tableau de bord

- sélection trajectoire initiale/optimisée et méthode d'optimisation ;
- paramètres de voxel, facteurs, seuils de boucle, GNSS et projection ;
- comparaison directe des trajectoires et résidus ;
- nuages brut, optimisé et colorisé superposables ;
- ATE/RPE, résidus GNSS, boucles, densité et erreur de reprojection ;
- rechargement d'une carte candidate sans refaire le calcul.

### Porte B2

La géométrie est reproductible, géoréférencée, accompagnée d'une incertitude et supérieure ou égale à la baseline selon les KPI approuvés.

## 11. Lot B3 — Carte métier et sémantique

### Algorithmes

- terrain, pente, rugosité et ruptures ;
- annotations et baseline de segmentation 2D ;
- projection probabiliste des classes en 3D ;
- détection géométrique des rangs, pieds, poteaux, murs et obstacles ;
- représentation conservatrice des fils ;
- graphe de parcelle et scores de confiance.

### Tableau de bord

- sélection modèle, poids, seuils, classes et post-traitements ;
- affichage RGB, masques 2D, nuage sémantique et entités 3D ;
- édition uniquement de labels/validations, jamais de résultat brut silencieux ;
- matrices de confusion, IoU, précision/rappel, confiance et couverture ;
- filtres par classe, confiance et zone ;
- comparaison modèles RTX/Jetson et rechargement des inférences.

### Porte B3

Chaque entité possède géométrie, classe, confiance et provenance ; les zones inconnues ou insuffisamment observées restent explicites.

## 12. Lot B4 — Carte approuvée et mission agricole

### Algorithmes

- assemblage et validation du `VineyardMapPackage` ;
- sélection de cibles et prescription ;
- optimisation de l'ordre des rangs ;
- spline 3D nominale, transitions, corridor et géofence ;
- simulation complète de la mission avant approbation.

### Tableau de bord

- navigateur de versions de carte ;
- workflow `CANDIDATE -> REVIEWED -> APPROVED` avec motif et auteur ;
- éditeur de contraintes et paramètres de mission ;
- affichage carte, graphe, route, corridor et zones interdites ;
- métriques distance, énergie, couverture, marges et incertitude ;
- lancement PX4/Gazebo de la mission et comparaison plan/réel ;
- production du `TreatmentMissionPackage` uniquement après succès.

### Porte B4

Une carte approuvée et une mission simulée peuvent être chargées, visualisées et reproduites par leurs checksums.

## 13. Lot C1 — Localisation du drone agricole

### Algorithmes

- vérification carte/mission ;
- FAST-LIO2 local ;
- initialisation RTK ;
- comparaison NDT/GICP/ICP pour le recalage carte/réel ;
- fusion et gestion des modes dégradés.

### Tableau de bord

- sélection carte, mission, méthode et profil de bruit/perte GNSS ;
- vue des repères `earth/map/odom/base_link` ;
- trajectoires, corrections `map -> odom`, covariance et innovations ;
- injection de perte RTK, biais et décalage initial ;
- métriques de convergence, erreur, disponibilité et sauts ;
- rechargement et comparaison des méthodes.

### Porte C1

Le recalage converge dans les scénarios acceptés, reste continu pour la commande et signale tout échec.

## 14. Lot C2 — Perception, corridor et navigation locale

### Algorithmes

- terrain local, obstacles et suivi ;
- occupation/ESDF roulante ;
- corridor drone + bras ;
- planificateur local et suivi de terrain ;
- ralentissement, arrêt et replanification.

### Tableau de bord

- scénarios `VINEYARD_BENCH_V01`, obstacles et conditions perturbées ;
- paramètres de capteurs, bruit, portée, marges, dynamique et planificateur ;
- occupation, champ de distance, obstacles, corridor et trajectoires ;
- distance minimale, temps de calcul, fréquence, jerk et violations ;
- injection d'obstacle tardif, perception périmée et surcharge calcul ;
- comparaison des planificateurs et profils.

### Porte C2

Aucune collision sur les scénarios approuvés, marges et latences mesurées, arrêt sûr lors d'une information critique périmée.

## 15. Lot C3 — Mission autonome et sécurité

### Algorithmes

- machine à états complète ;
- superviseur indépendant ;
- gestion énergie, reprise, retour et abandon ;
- fautes PX4, ROS 2, réseau, capteurs et calcul.

### Tableau de bord

- état de mission, gardes, transitions et cause des refus ;
- panneau d'injection de fautes réservé au SITL ;
- chronologie synchronisée PX4/ROS 2 ;
- matrice de couverture des défaillances ;
- rechargement pas à pas d'un incident ;
- génération automatique du rapport de sécurité.

### Porte C3

Chaque faute prévue possède une détection, une transition explicite, un état sûr et une preuve rechargeable.

## 16. Lots D1 à D3 — Bras et traitement

### D1 — Bras sans liquide

- jumeau numérique, états, enveloppe, délais, capteurs et blocages ;
- visualisation du bras et de sa marge dans le corridor ;
- paramètres de cinématique et faute actionneur ;
- interdiction de mission si l'état réel du bras est inconnu.

### D2 — Eau et traceur

- association cible, temps avant cible, vanne/pompe, débit et pression ;
- courbes consigne/mesure et carte de couverture ;
- paramètres de latence, vitesse, dose et régulation ;
- comparaison simulation, banc et eau/traceur.

### D3 — Qualification agronomique autorisée

- assistance d'air, vent/downwash et dérive ;
- paramètres physiques verrouillés par protocole ;
- visualisation 3D du dépôt et des zones interdites ;
- traçabilité réglementaire et rapport final.

Chaque sous-lot conserve l'ordre simulation, banc, eau/traceur, puis seulement protocole et produit autorisés.

## 17. Lot E1 — Campagnes système et qualification

- construire des campagnes combinant datasets, cartes, scénarios, versions et profils ;
- mettre en file les exécutions headless ;
- suivre l'avancement et reprendre après interruption ;
- consolider les résultats avec intervalles de répétabilité ;
- comparer PC, Jetson, SITL, HITL et réel ;
- générer la matrice `exigence -> composant -> test -> résultat` ;
- figer les configurations candidates de qualification.

Le tableau de bord fournit une vue « Campagne » séparée de la vue « Exécution » afin de ne pas confondre un essai exploratoire avec une qualification.

## 18. Définition de terminé commune

Un lot n'est terminé que si :

- ses interfaces et schémas sont versionnés ;
- le runner headless possède tests et arrêt propre ;
- les paramètres utiles sont exposés et validés côté serveur ;
- les paramètres effectifs et versions sont archivés ;
- les données directes sont visualisables ;
- les métriques finales sont calculées automatiquement ;
- le résultat se recharge après redémarrage du tableau de bord ;
- au moins deux résultats compatibles peuvent être comparés ;
- les fautes attendues produisent un état explicite ;
- la documentation et la traçabilité sont mises à jour.

## 19. Versions fonctionnelles du tableau de bord

| Version cible | Capacité principale | Lots servis |
|---|---|---|
| V0.3 | runners génériques, schémas, historique, rechargement et comparaison initiale | T0, A et LIO |
| V0.4 | acquisition, chronologie capteurs, calibration et géométrie de carte | B1–B2 |
| V0.5 | sémantique, entités, carte approuvée et mission | B3–B4 |
| V0.6 | localisation, navigation, corridor et fautes | C1–C3 |
| V0.7 | bras, ciblage, débit et couverture | D1–D2 |
| V1.0 | campagnes, qualification et traçabilité système | D3–E1 |

Les numéros décrivent des capacités fonctionnelles, pas un calendrier.

## 20. Ordre immédiat proposé

1. valider le présent plan ; l'ADR-0005 est déjà accepté ;
2. réaliser T0.1 et T0.2 sans casser les trois benchmarks LIO existants ;
3. ajouter T0.3 pour recharger les résultats LIO et PX4 déjà présents ;
4. valider T0 par tests d'interface et de non-régression ;
5. seulement ensuite démarrer B1 avec les contrats et les caméras BotanicGarden.
