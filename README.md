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
14. [`docs/25_Migration_CPP17_Qt6_dashboard_desktop_V0.1.md`](docs/25_Migration_CPP17_Qt6_dashboard_desktop_V0.1.md) — application desktop C++17/Qt 6, interface `.ui` et état de la migration globale.
15. [`docs/26_Cloture_migration_CPP17_Qt6_V0.1.md`](docs/26_Cloture_migration_CPP17_Qt6_V0.1.md) — arborescence active, commandes C++, traçabilité et validations de clôture.
16. [`docs/27_Refonte_UI_et_fiabilisation_simulation_V0.1.md`](docs/27_Refonte_UI_et_fiabilisation_simulation_V0.1.md) — nouvelle interface à contraste renforcé et lancement PX4 depuis l'application native.
17. [`docs/28_Architecture_station_mission_unifiee_V0.1.md`](docs/28_Architecture_station_mission_unifiee_V0.1.md) — rôle complet de la station, modules C++ et règles d'extension.
18. [`docs/29_Etat_des_lieux_et_consolidation_SW0_V0.1.md`](docs/29_Etat_des_lieux_et_consolidation_SW0_V0.1.md) — état vérifié du projet, risques de baseline et portes de consolidation avant B1.

Le fichier [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) résume les décisions actives pour reprendre rapidement le projet dans une future session.

## Démarrage rapide

Le point d'entrée opérateur est une application desktop native, pas un site Web. Cette application constitue la station de mission : acquisitions du cartographe, cartes, missions, transferts, rapports et simulations seront intégrés par modules. Les fonctions autres que la simulation sont encore planifiées. Dans Visual Studio Code, ouvrir **Exécuter et déboguer**, puis choisir `Dashboard Qt 6 — Debug`. La configuration versionnée utilise directement CMake, Ninja et GDB de MSYS2 UCRT64 ; le programme n'est pas lancé par un script PowerShell.

Construction équivalente depuis un terminal MSYS2 UCRT64 ou PowerShell :

```powershell
C:\msys64\ucrt64\bin\cmake.exe --preset desktop-debug
C:\msys64\ucrt64\bin\cmake.exe --build --preset desktop-debug --parallel
& .\build\desktop-debug\software\cpp\drone-agricole-dashboard.exe --workspace .
```

Les outils headless sont regroupés dans `drone-agricole-tools`. Les environnements ROS 2 et les algorithmes LIO restent reproductibles dans Docker :

```powershell
docker compose build telemetry-bridge fast-lio2 point-lio lio-sam qt-dashboard-toolchain
docker compose --profile lio run --rm botanicgarden-adapter drone-agricole-tools help
```

Lors d'un lancement LIO depuis l'application, Compose démarre automatiquement
le pont de télémétrie C++ `telemetry-bridge`. Il écoute uniquement sur
`127.0.0.1:8092` et transmet à Qt les trajectoires, le nuage, les compteurs et
les ressources pendant le rejeu. Son diagnostic manuel est :

```powershell
docker compose --profile lio up -d telemetry-bridge
Invoke-RestMethod http://127.0.0.1:8092/api/health
```

Depuis le dashboard natif, le premier lancement PX4 vérifie l'API locale et démarre automatiquement le banc Docker SITL si nécessaire. Pour contrôler ou démarrer manuellement ce banc :

```powershell
docker compose --profile sim --profile viz up -d px4-runner-api
docker compose --profile sim --profile viz ps
Invoke-RestMethod http://127.0.0.1:8091/api/health
```

L'essai Offboard reste doublement verrouillé et réservé à SITL. PX4 conserve le vol critique et les failsafes ; ROS 2 ne fournit que les consignes avancées.

## Organisation

```text
DroneAgricole/
├── docs/           documentation et décisions d'architecture
├── software/cpp/   application Qt 6, bibliothèque et outils C++17
├── software/src/   paquets ROS 2 C++ et messages
├── software/docker images reproductibles amd64/arm64
├── simulation/     mondes, scénarios, PX4 SITL et Gazebo
├── datasets/       manifestes et données locales non versionnées
├── configs/        paramètres partagés
├── hardware/       mécanique, électronique et interfaces
├── research/       études, articles, brevets et essais
├── tools/          documentation des commandes et ressources de données
└── results/        sorties de benchmark non versionnées
```

## Règles de travail

- Ce dossier est la source de vérité du projet.
- Les changements d'architecture importants sont consignés dans `docs/decisions/`.
- Les données brutes et résultats volumineux restent dans `datasets/` et `results/`, mais ne sont pas ajoutés à Git.
- Les exigences utilisent des identifiants stables afin de relier besoin, algorithme, test et résultat.
- Les valeurs encore incertaines portent la mention **À valider** et ne doivent pas être interprétées comme des spécifications figées.

## Prochaine étape recommandée

Terminer SW0 selon DOC-29 : consolider les changements Git, raccorder et exécuter
la CI distante, qualifier Qt/LIO `linux/arm64` sur un hôte ARM natif et exécuter
les campagnes LIO longues. Les tests Windows, les images Linux `amd64`, les
répétitions LIO courtes et les deux scénarios PX4 du port C++ sont disponibles
localement. Le lot B1 peut
préparer ses contrats en parallèle, mais sa baseline reste **À valider** tant
que la porte SW0 n'est pas fermée.
