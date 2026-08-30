# Drone Agricole

Workspace maître du projet de système autonome de cartographie et de traitement de vignobles à forte pente.

## Référence du projet

- Emplacement Windows : `D:\ProjetGuillaume\DroneAgricole`
- Accès WSL2 : `/mnt/d/ProjetGuillaume/DroneAgricole`
- Langue documentaire : français
- Statut : conception préliminaire et premier socle logiciel opérationnel
- Architecture de développement : Windows 11 + WSL2 + Docker Desktop
- Cible embarquée : Jetson Orin + JetPack + conteneurs ARM64
- Contrôle de vol : PX4 sur autopilote dédié
- Calcul avancé : ROS 2 sur ordinateur compagnon

## Documents de référence

1. [`docs/00_Cahier_des_charges_systeme_V0.2.md`](docs/00_Cahier_des_charges_systeme_V0.2.md) — besoins et exigences système.
2. [`docs/01_Architecture_logicielle_algorithmes_V0.2.md`](docs/01_Architecture_logicielle_algorithmes_V0.2.md) — chaînes fonctionnelles et algorithmes.
3. [`docs/02_SAD_V0.2.md`](docs/02_SAD_V0.2.md) — architecture logicielle détaillée.
4. [`docs/03_Plan_validation_simulation_V0.1.md`](docs/03_Plan_validation_simulation_V0.1.md) — jeux de simulation, datasets et critères de validation.
5. [`docs/09_Socle_Docker_ROS_PX4_BotanicGarden_V0.1.md`](docs/09_Socle_Docker_ROS_PX4_BotanicGarden_V0.1.md) — socle exécutable et commandes de validation.
6. [`docs/10_Integration_FAST_LIO2_BotanicGarden_V0.1.md`](docs/10_Integration_FAST_LIO2_BotanicGarden_V0.1.md) — intégration FAST-LIO2 et premier benchmark sur `1006-03`.
7. [`docs/11_Campagne_FAST_LIO2_complete_sensibilite_Livox_V0.1.md`](docs/11_Campagne_FAST_LIO2_complete_sensibilite_Livox_V0.1.md) — séquence complète, ressources, RPE, sensibilité et migration Livox.
8. [`docs/12_Tableau_de_bord_3D_temps_reel_V0.2.md`](docs/12_Tableau_de_bord_3D_temps_reel_V0.2.md) — console d'essai, rendu 3D temps réel et graphiques de benchmark.
9. [`docs/13_Qualification_FAST_LIO2_08x_repetabilite_V0.1.md`](docs/13_Qualification_FAST_LIO2_08x_repetabilite_V0.1.md) — ratio sorties/scans à 0,8× et sensibilité répétée.
10. [`docs/14_Instrumentation_FAST_LIO2_metriques_dashboard_V0.1.md`](docs/14_Instrumentation_FAST_LIO2_metriques_dashboard_V0.1.md) — compteurs internes, `metrics.json` automatique et interprétation des vitesses de rejeu.
11. [`docs/15_Integration_Point_LIO_BotanicGarden_V0.1.md`](docs/15_Integration_Point_LIO_BotanicGarden_V0.1.md) — intégration Point-LIO, protocole complet à 1× et comparaison directe avec FAST-LIO2.
12. [`docs/16_Integration_LIO_SAM_BotanicGarden_V0.1.md`](docs/16_Integration_LIO_SAM_BotanicGarden_V0.1.md) — intégration LIO-SAM, instrumentation, test court et fenêtre dynamique à 1×.
13. [`docs/17_Comparaison_finale_LIO_BotanicGarden_V0.1.md`](docs/17_Comparaison_finale_LIO_BotanicGarden_V0.1.md) — comparaison des trois passages complets à QoS harmonisée et sélection de travail.

Le fichier [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) résume les décisions actives pour reprendre rapidement le projet dans une future session.

## Démarrage rapide

Depuis PowerShell, à la racine du projet :

```powershell
docker compose build ros-humble ros-jazzy-sim
docker compose run --rm ros-humble bash tools/verify/verify_ros2.sh
docker compose run --rm ros-jazzy-sim bash tools/verify/verify_ros2.sh
docker compose --profile sim up -d px4-sitl
docker compose build fast-lio2
docker compose run --rm fast-lio2 bash tools/benchmarks/run_fastlio2_botanicgarden_smoke.sh
docker compose --profile lio build point-lio
docker compose --profile lio run --rm point-lio bash tools/benchmarks/run_pointlio_botanicgarden_benchmark.sh
docker compose --profile lio build lio-sam
docker compose --profile lio run --rm lio-sam bash tools/benchmarks/run_liosam_botanicgarden_benchmark.sh
.\tools\visualization\start_fastlio_dashboard.ps1
```

La dernière commande ouvre le tableau de bord local sur `http://127.0.0.1:8080`. Le dataset, la séquence, l'algorithme, les voxels et les commandes de lancement/arrêt sont ensuite accessibles dans la page. À la fin d'un rejeu réussi, `metrics.json` est calculé automatiquement et le bouton `Afficher les métriques finales` présente ATE, RPE et compteurs instrumentés. Ce mode est destiné à l'observation ; les benchmarks de référence restent exécutés sans rendu.

L'état et les journaux de PX4/Gazebo sont accessibles avec :

```powershell
docker compose ps px4-sitl
docker compose logs -f px4-sitl
```

## Organisation

```text
DroneAgricole/
├── docs/           documentation et décisions d'architecture
├── software/       code ROS 2, images Docker et logiciels métier
├── simulation/     mondes, scénarios, PX4 SITL et Gazebo
├── datasets/       manifestes et données locales non versionnées
├── configs/        paramètres partagés
├── hardware/       mécanique, électronique et interfaces
├── research/       études, articles, brevets et essais
├── tools/          scripts de développement et de validation
└── results/        sorties de benchmark non versionnées
```

## Règles de travail

- Ce dossier est la source de vérité du projet.
- Les changements d'architecture importants sont consignés dans `docs/decisions/`.
- Les données brutes et résultats volumineux restent dans `datasets/` et `results/`, mais ne sont pas ajoutés à Git.
- Les exigences utilisent des identifiants stables afin de relier besoin, algorithme, test et résultat.
- Les valeurs encore incertaines portent la mention **À valider** et ne doivent pas être interprétées comme des spécifications figées.

## Prochaine étape recommandée

Répéter FAST-LIO2 et LIO-SAM pour qualifier la variabilité des deux candidats retenus, puis les mesurer à `1×` sur Jetson. En parallèle, ajouter le pont uXRCE-DDS vers ROS 2 Jazzy afin d'afficher la pose PX4/Gazebo dans la scène 3D et reprendre la construction de `VINEYARD_BENCH_V01`.
