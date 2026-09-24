# Drone Agricole

Workspace maître du projet de système autonome de cartographie et de traitement de vignobles à forte pente.

La documentation active est consolidée dans quatre architectures vivantes et un
registre transversal de validation. Les anciens comptes rendus ont été
consolidés puis supprimés. Voir [`docs/INDEX.md`](docs/INDEX.md).

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

1. [High Level Design](docs/architecture/HLD.md) — fonctionnement du système complet.
2. [Architecture logicielle](docs/architecture/ARCHITECTURE_LOGICIELLE.md) — modules, contrats, déploiement et tests.
3. [Architecture mécanique](docs/architecture/ARCHITECTURE_MECANIQUE.md) — choix, pièces, sous-assemblages, BOM et vérifications.
4. [Architecture électrique et réseaux](docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md) — énergie, électronique, liaisons et synchronisation.
5. [Validation et qualification](docs/VALIDATION_QUALIFICATION.md) — stratégie, campagnes, résultats, preuves et reste à qualifier.

## Préparer le poste de développement

Le poste de référence utilise Windows 11, WSL 2 et Docker Desktop avec son
moteur Linux WSL 2. Installer ou contrôler WSL avec `wsl --install` puis
`wsl --update`, installer Docker Desktop et activer l'intégration de la
distribution Ubuntu. Ne pas installer un second Docker Engine ni un pilote
NVIDIA Linux dans WSL : le pilote Windows expose le GPU aux conteneurs.

QGroundControl Windows est requis pour les travaux PX4/SITL et les futurs
essais matériels. ROS 2, PX4, Gazebo, CUDA et les LIO restent fournis par les
images du projet ; aucune installation globale n'est nécessaire.

Contrôle minimal :

```powershell
wsl --version
wsl -l -v
docker version
docker compose version
```

Références : [WSL](https://learn.microsoft.com/fr-fr/windows/wsl/install),
[Docker Desktop WSL 2](https://docs.docker.com/desktop/features/wsl/) et
[CUDA sur WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

## Démarrage rapide

Le point d'entrée opérateur est une application desktop native, pas un site Web. Cette application constitue la station de mission : acquisitions du cartographe, cartes, missions, transferts, rapports et simulations seront intégrés par modules. Les fonctions autres que la simulation sont encore planifiées. Dans Visual Studio Code, ouvrir **Exécuter et déboguer**, puis choisir `Dashboard Qt 6 — Debug`. La configuration versionnée utilise directement CMake, Ninja et GDB de MSYS2 UCRT64 ; le programme n'est pas lancé par un script PowerShell.

Construction équivalente depuis un terminal MSYS2 UCRT64 ou PowerShell :

La chaîne native requiert notamment Qt 6, `yaml-cpp` et `mingw-w64-ucrt-x86_64-libtiff` ; libtiff assure la lecture sans perte des TIFF multispectraux 16 bits.

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
- Les décisions d'architecture et leur justification utile sont intégrées au document vivant concerné.
- Les données brutes et résultats volumineux restent dans `datasets/` et `results/`, mais ne sont pas ajoutés à Git.
- Les exigences utilisent des identifiants stables afin de relier besoin, algorithme, test et résultat.
- Les valeurs encore incertaines portent la mention **À valider** et ne doivent pas être interprétées comme des spécifications figées.

## Prochaine étape recommandée

SW0 est fermé sur la baseline locale `sw0-v0.1`. Les preuves historiques,
résultats synthétiques et limites sont tenus dans `DOC-VAL` ; la liste et
l'état des tests courants doivent toujours être recalculés sur la révision
active. L'état architectural courant est tenu dans `DOC-SW`.

Démarrer B1 : contrats `SurveyMissionPackage` et `SurveyRunPackage`, réception
des acquisitions et rapport qualité reproductible. Les qualifications ARM
native/Jetson, la CI distante, le rendu OpenGL conteneurisé et les seuils de
navigation restent **À valider** avant les échéances de déploiement associées.
