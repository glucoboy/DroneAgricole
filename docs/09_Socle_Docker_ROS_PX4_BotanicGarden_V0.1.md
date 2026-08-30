# Socle Docker, ROS 2, PX4/Gazebo et BotanicGarden — V0.1

- Référence : DOC-09
- Date : 18 août 2026
- Statut : premier socle opérationnel

## 1. Objectif

Établir un environnement reproductible permettant de :

- développer et tester les algorithmes LIO sous ROS 2 Humble ;
- préparer la simulation moderne sous ROS 2 Jazzy et Gazebo Harmonic ;
- exécuter PX4 SITL avec un drone `x500` dans Gazebo ;
- inspecter et convertir BotanicGarden `1006-03` sans modifier les rosbags sources.

## 2. Architecture retenue

| Service Compose | Base | Usage principal | État |
|---|---|---|---|
| `ros-humble` | Ubuntu 22.04 / ROS 2 Humble | Adaptateurs de datasets et futurs LIO | Validé |
| `botanicgarden-adapter` | image `ros-humble` | Conversion reproductible de `1006-03` | Validé |
| `ros-jazzy-sim` | Ubuntu 24.04 / ROS 2 Jazzy | Ponts ROS/Gazebo et simulation moderne | Validé |
| `px4-sitl` | PX4 officiel / Gazebo Harmonic | Contrôleur de vol et dynamique `x500` | Validé en mode headless |

La séparation détaillée et ses conséquences sont consignées dans `docs/decisions/ADR-0002-separation-environnements-ros-simulation-lio.md`.

## 3. Fichiers du socle

- `compose.yaml` : point d'entrée commun ;
- `software/docker/Dockerfile` : images ROS Humble et Jazzy ;
- `tools/verify/verify_ros2.sh` : test de communication ROS 2 ;
- `software/src/drone_agricole_dataset_adapter/` : adaptateur BotanicGarden ;
- `software/tests/test_botanicgarden_adapter.py` : tests unitaires ;
- `configs/datasets/botanicgarden/1006-03.yaml` : topics, fréquences et calibrations retenues.

## 4. Construire et valider ROS 2

Toutes les commandes sont exécutées depuis `D:\ProjetGuillaume\DroneAgricole` dans PowerShell.

```powershell
docker compose build ros-humble ros-jazzy-sim
docker compose run --rm ros-humble bash tools/verify/verify_ros2.sh
docker compose run --rm ros-jazzy-sim bash tools/verify/verify_ros2.sh
```

Le test lance un nœud émetteur et un nœud récepteur, puis exige la réception d'au moins un message `Hello World`.

Résultats du 18 août 2026 :

- ROS 2 Humble : réussi ;
- ROS 2 Jazzy : réussi ;
- tests unitaires de l'adaptateur : 3 tests réussis, dont la normalisation des temps par point Velodyne.

Commande de revalidation des tests :

```powershell
docker compose run --rm ros-humble bash -lc "python3 -m unittest discover -s software/tests -v"
```

## 5. Adaptateur BotanicGarden `1006-03`

### Inspection des sources

```powershell
docker compose run --rm botanicgarden-adapter inspect `
  datasets/public/botanicgarden/1006-03/raw/1006_03_LIO.bag `
  datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag
```

### Sous-ensemble Velodyne VLP-16 + Xsens

```powershell
docker compose run --rm botanicgarden-adapter prepare `
  --lio-bag datasets/public/botanicgarden/1006-03/raw/1006_03_LIO.bag `
  --ground-truth-bag datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag `
  --output datasets/derived/botanicgarden/1006-03/smoke/velodyne_xsens_5s_ros2 `
  --pipeline velodyne_xsens `
  --duration-s 5 `
  --config configs/datasets/botanicgarden/1006-03.yaml
```

Résultat : MCAP compressé ZSTD de 4,997 s, 2 097 messages, lisible et rejouable par ROS 2 Humble.

Depuis le 19 août 2026, la conversion applique explicitement les règles ROS 1 vers ROS 2, notamment la suppression du champ ROS 1 `Header.seq`. Les bags dérivés antérieurs ont été régénérés ; leur désérialisation native par des abonnés C++ ROS 2 est validée.

### Sous-ensemble Livox Avia + BMI088 en unités SI

```powershell
docker compose run --rm botanicgarden-adapter prepare `
  --lio-bag datasets/public/botanicgarden/1006-03/raw/1006_03_LIO.bag `
  --ground-truth-bag datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag `
  --output datasets/derived/botanicgarden/1006-03/smoke/livox_bmi088_si_5s_ros2 `
  --pipeline livox_bmi088 `
  --livox-accel-mode si `
  --duration-s 5 `
  --config configs/datasets/botanicgarden/1006-03.yaml
```

Résultat : MCAP compressé ZSTD de 4,995 s, 1 111 messages. La norme d'accélération contrôlée après conversion vaut environ 9,74 m/s².

### Vérité terrain au format TUM

```powershell
docker compose run --rm botanicgarden-adapter export-tum `
  --ground-truth-bag datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag `
  --output datasets/derived/botanicgarden/1006-03/ground_truth/1006-03.tum
```

Résultat : 5 947 poses exportées. Les données dérivées restent exclues de Git et peuvent être régénérées à partir des sources.

## 6. PX4 SITL et Gazebo

### Démarrage

```powershell
docker compose --profile sim up -d px4-sitl
docker compose logs -f px4-sitl
```

Configuration par défaut :

- véhicule : `gz_x500` ;
- monde : `default` ;
- Gazebo : mode sans interface graphique ;
- MAVLink/QGroundControl : UDP 14550 ;
- MAVSDK/offboard : UDP 14540 ;
- uXRCE-DDS/ROS 2 : UDP 8888.

L'image PX4 officielle détecte Docker Desktop et envoie MAVLink et uXRCE-DDS à `host.docker.internal`. Les ports ne sont donc pas publiés par Compose : Windows doit pouvoir les écouter directement.

### Arrêt

```powershell
docker compose --profile sim stop px4-sitl
```

Les paramètres et journaux de PX4 sont persistés localement sous `.runtime/px4/`, dossier exclu de Git.

### Validation obtenue

Le 18 août 2026 :

- PX4 a chargé l'airframe `SYS_AUTOSTART=4001` ;
- Gazebo 8.14.0 a chargé le monde `default` ;
- le modèle `x500_0` a été créé ;
- le script d'initialisation PX4 s'est terminé avec succès ;
- Windows a reçu une trame MAVLink de 40 octets sur UDP 14550 ;
- Windows a reçu une requête uXRCE-DDS de 16 octets sur UDP 8888.

La couche de transport est donc prête. La connexion visuelle QGroundControl et l'exposition de topics PX4 dans ROS 2 seront les validations fonctionnelles suivantes.

## 7. Version PX4 provisoire

L'image est épinglée à :

```text
px4io/px4-sitl-gazebo:v1.18.0-beta2
sha256:bcf8278e3321948be2266568528107dbfd94eb6fa703171cb013bc4d54dc8ef8
```

Le tag stable `v1.17.0` mentionné par la documentation PX4 n'était pas présent dans le registre Gazebo lors de la construction du socle. Cette bêta convient aux essais préliminaires, mais elle devra être remplacée par une version stable épinglée avant toute campagne formelle.

## 8. Limites et prochaine incrémentation

Le socle ne contient pas encore :

- le Micro XRCE-DDS Agent et les messages `px4_msgs` alignés sur la version PX4 ;
- un monde Gazebo viticole ;
- les intégrations Point-LIO et LIO-SAM ; FAST-LIO2 est opérationnel et décrit dans `docs/10_Integration_FAST_LIO2_BotanicGarden_V0.1.md` ;
- une interface graphique Gazebo validée sous Windows/WSL2.

Ordre recommandé :

1. ouvrir QGroundControl et confirmer l'apparition automatique du `x500` ;
2. ajouter le pont uXRCE-DDS et vérifier les premiers topics PX4 sous ROS 2 Jazzy ;
3. étendre le benchmark FAST-LIO2 à la séquence complète, puis intégrer Point-LIO et LIO-SAM ;
4. créer la première géométrie minimale de `VINEYARD_BENCH_V01`.
