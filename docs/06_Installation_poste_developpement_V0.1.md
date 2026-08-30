# Installation du poste de développement

| Champ | Valeur |
|---|---|
| Référence | DOC-06 |
| Version | V0.1 |
| Date | 18 août 2026 |
| Statut | Checklist initiale |
| Cible | Windows 11 + WSL 2 + Docker + GPU NVIDIA |

## 1. Déjà présent sur le PC

| Outil | État observé |
|---|---|
| NVIDIA GeForce RTX 5060 Ti | détectée, 16 311 Mio |
| Pilote NVIDIA Windows | version 610.74, accès GPU fonctionnel côté Windows |
| Visual Studio Code | version 1.130.0 |
| Git | version 2.54.0 |
| Python Windows | version 3.14, utilisé seulement pour les utilitaires légers du projet |
| Extensions VS Code C++ et CMake | présentes |

Ces outils n'ont pas besoin d'être réinstallés.

## 2. À installer maintenant

### 2.1 WSL 2 et Ubuntu 24.04 LTS

Ouvrir PowerShell en tant qu'administrateur :

```powershell
wsl --install -d Ubuntu-24.04
```

Si le nom explicite de la distribution n'est pas proposé, utiliser `wsl --install`, qui installe Ubuntu par défaut. Redémarrer Windows si demandé, créer le compte Linux lors du premier lancement, puis exécuter :

```powershell
wsl --update
wsl -l -v
```

La distribution Ubuntu doit apparaître avec la version `2`.

Documentation officielle : [installation de WSL](https://learn.microsoft.com/fr-fr/windows/wsl/install).

### 2.2 Docker Desktop

Installer la version courante de Docker Desktop pour Windows :

- installation par utilisateur recommandée ;
- moteur `WSL 2` ;
- conteneurs Linux ;
- intégration activée pour la distribution Ubuntu.

Dans `Settings > Resources > Advanced`, placer si possible l'image disque Docker sur le disque `D:` afin d'éviter que les images ROS, Gazebo et CUDA remplissent le disque système. Le dossier de runtime du projet sera ignoré par Git.

Documentation officielle : [Docker Desktop pour Windows](https://docs.docker.com/desktop/setup/install/windows-install/) et [backend WSL 2](https://docs.docker.com/desktop/features/wsl/).

### 2.3 Extensions Visual Studio Code

Installer depuis l'onglet Extensions :

| Nom affiché | Identifiant | Utilité |
|---|---|---|
| WSL | `ms-vscode-remote.remote-wsl` | ouvrir et déboguer dans Ubuntu |
| Dev Containers | `ms-vscode-remote.remote-containers` | ouvrir le projet dans son conteneur reproductible |
| Docker | `ms-azuretools.vscode-docker` | voir les images, conteneurs et journaux |

Les extensions Python, C++, CMake et Codex sont déjà présentes.

## 3. À installer au démarrage des simulations de vol

Installer **QGroundControl pour Windows** lorsque nous commencerons PX4 SITL. L'application servira à afficher le véhicule simulé, modifier les paramètres et préparer les missions. Utiliser la version stable depuis la [documentation officielle QGroundControl](https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/getting_started/download_and_install.html).

`usbipd-win` ne sera utile que plus tard si un périphérique USB doit être exposé directement à WSL. Pour le Pixhawk, QGroundControl Windows pourra déjà communiquer directement avec le port série.

## 4. Installé automatiquement dans les conteneurs du projet

Il ne faut pas installer ces composants manuellement sur Windows :

- la base actuelle Ubuntu 22.04 / ROS 2 Humble et un conteneur candidat Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic pour comparer la simulation moderne ;
- PX4 SITL et ses dépendances ;
- les environnements compatibles nécessaires à FAST-LIO2, Point-LIO et LIO-SAM ;
- PCL, Eigen, CMake, colcon, rosdep et les messages Livox ;
- `evo` et les outils d'évaluation ATE/RPE ;
- CUDA, cuDNN, TensorRT et les bibliothèques de perception lorsque cette phase commencera.

Cette séparation nous permettra de figer plusieurs environnements sans conflit, notamment un environnement simulation ROS 2 Jazzy/Gazebo Harmonic et un environnement benchmark compatible avec les implémentations LIO retenues.

## 5. À ne pas installer dans WSL

- aucun pilote graphique NVIDIA Linux ; le pilote Windows expose déjà le GPU à WSL ;
- aucun second Docker Engine installé directement dans Ubuntu si Docker Desktop est utilisé ;
- aucune installation ROS globale nécessaire pour le moment ;
- aucun Gazebo global nécessaire pour le moment.

NVIDIA indique explicitement que le pilote Linux ne doit pas être installé dans WSL : [guide CUDA sur WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

## 6. Architecture logicielle visée

```text
Windows 11
├── VS Code
├── QGroundControl
├── pilote NVIDIA
└── WSL 2 + Ubuntu 24.04
    └── Docker Desktop
        ├── simulation : PX4 + environnement ROS/Gazebo versionné
        ├── benchmark LIO : FAST-LIO2 / Point-LIO / LIO-SAM
        └── perception : CUDA / TensorRT / modèles IA
```

PX4 prend officiellement en charge le développement Windows via WSL 2. Gazebo recommande actuellement la combinaison Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic ; elle sera évaluée dans un conteneur séparé avant toute modification de la base ROS 2 Humble active du projet.

## 7. Contrôle après installation

Une fois WSL et Docker installés, lancer les commandes suivantes dans PowerShell et transmettre le résultat si une erreur apparaît :

```powershell
wsl --version
wsl -l -v
docker version
docker compose version
```

Nous effectuerons ensuite ensemble un test GPU dans un conteneur NVIDIA avant de construire les images du projet.
