# Intégration FAST-LIO2 et premier benchmark BotanicGarden — V0.1

- Référence : DOC-10
- Date : 19 août 2026
- Statut : opérationnel préliminaire

## 1. Objectif et résultat

FAST-LIO2 est désormais construit dans une image ROS 2 Humble dédiée et exécutable sur les données Velodyne VLP-16 + Xsens de BotanicGarden `1006-03`.

Deux validations ont été réalisées :

| Essai | Durée utile | Trajectoire de référence | Poses estimées | ATE RMSE après alignement SE(3) | Longueur estimée / référence |
|---|---:|---:|---:|---:|---:|
| Smoke test final, début du bag | 4,34 s | 0,122 m | 35 | 0,0092 m | 0,158 / 0,122 m |
| Fenêtre dynamique, décalage 60 s | 29,45 s | 44,135 m | 264 | 0,0259 m | 44,118 / 44,135 m |

Le premier essai valide surtout le démarrage et l'initialisation. La fenêtre dynamique est plus représentative : son ratio de longueur de trajectoire vaut `0,99962`, avec une erreur de position maximale de `0,0729 m` après alignement.

Ces résultats sont encourageants, mais ne constituent pas encore une qualification formelle : l'orientation et la RPE ne sont pas encore évaluées, la séquence complète n'est pas traitée et aucun balayage de paramètres n'a été réalisé.

## 2. Versions figées et licences

| Composant | Révision retenue | Licence |
|---|---|---|
| `hku-mars/FAST_LIO`, branche `ROS2` | `a4743b095409588842a5b30ddfa27e29d2f99164` | GPL-2.0-only |
| sous-module `hku-mars/ikd-Tree` | `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4` | GPL-2.0 |
| définitions de messages Livox compatibles | issues de `Livox-SDK/livox_ros_driver2` | MIT |

La traçabilité machine est conservée dans `software/third_party/fast_lio2.yaml`. L'image produite est `drone-agricole/fast-lio2:0.1.0` et le service Compose est `fast-lio2`.

Pour les essais hors ligne Velodyne, le conteneur fournit uniquement les messages ROS 2 attendus par FAST-LIO2 sous le nom de paquet `livox_ros_driver2`. Le pilote matériel Livox et son SDK ne sont pas installés. Ils seront intégrés séparément lors des essais avec un capteur Livox réel.

## 3. Corrections apportées à l'adaptateur BotanicGarden

La conversion initiale réutilisait directement des messages ROS 1. Le champ `seq` de `std_msgs/Header`, absent de ROS 2, restait alors encodé dans le flux CDR : les outils Python toléraient ce contenu, mais les abonnés C++ ROS 2 ne pouvaient pas le désérialiser correctement.

L'adaptateur utilise maintenant les convertisseurs ROS 1 vers ROS 2 de `rosbags` avec le typestore ROS 2 Humble. Une vérification directe par `rclpy` a confirmé la lecture native de `sensor_msgs/msg/Imu` et `sensor_msgs/msg/PointCloud2`.

Le champ par point `time` du VLP-16 varie dans les sources autour de `-0,0995 s` à `+0,0013 s`. Pour FAST-LIO2, le mode `--velodyne-time-mode start-relative` :

1. ramène les temps de chaque scan à une plage commençant à zéro ;
2. décale l'horodatage du nuage vers le début réel du scan ;
3. conserve l'espacement temporel entre les points.

Le mode `preserve` reste disponible pour produire une conversion fidèle sans normalisation spécifique au LIO.

## 4. Construction et contrôle de l'image

Depuis PowerShell, à la racine du projet :

```powershell
docker compose build fast-lio2
docker compose run --rm fast-lio2 bash -lc "ros2 pkg prefix fast_lio; ros2 pkg executables fast_lio"
```

La configuration BotanicGarden est `configs/lio/fast_lio2/botanicgarden_velodyne_xsens.yaml`. Elle utilise notamment 16 lignes, 10 Hz et la transformation extrinsèque Xsens vers VLP-16 inspectée dans les calibrations du dataset.

## 5. Préparer les données

### Smoke test de cinq secondes

```powershell
docker compose run --rm botanicgarden-adapter prepare `
  --lio-bag datasets/public/botanicgarden/1006-03/raw/1006_03_LIO.bag `
  --ground-truth-bag datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag `
  --output datasets/derived/botanicgarden/1006-03/smoke/velodyne_xsens_fastlio2_5s_ros2 `
  --pipeline velodyne_xsens `
  --velodyne-time-mode start-relative `
  --duration-s 5 `
  --config configs/datasets/botanicgarden/1006-03.yaml
```

### Fenêtre dynamique de trente secondes

```powershell
docker compose run --rm botanicgarden-adapter prepare `
  --lio-bag datasets/public/botanicgarden/1006-03/raw/1006_03_LIO.bag `
  --ground-truth-bag datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag `
  --output datasets/derived/botanicgarden/1006-03/dynamic/velodyne_xsens_fastlio2_30s_offset60_ros2 `
  --pipeline velodyne_xsens `
  --velodyne-time-mode start-relative `
  --start-offset-s 60 `
  --duration-s 30 `
  --config configs/datasets/botanicgarden/1006-03.yaml
```

Les sources ne sont jamais modifiées. Les données dérivées peuvent être supprimées et régénérées avec ces commandes.

## 6. Exécuter et analyser

### Validation courte

```powershell
docker compose run --rm fast-lio2 bash tools/benchmarks/run_fastlio2_botanicgarden_smoke.sh
```

### Fenêtre dynamique

```powershell
docker compose run --rm fast-lio2 bash tools/benchmarks/run_fastlio2_botanicgarden_smoke.sh `
  datasets/derived/botanicgarden/1006-03/dynamic/velodyne_xsens_fastlio2_30s_offset60_ros2 `
  results/benchmarks/fast_lio2/botanicgarden_1006-03/dynamic_v01
```

### Calcul des métriques

```powershell
docker compose run --rm ros-humble python3 tools/benchmarks/analyze_lio_trajectory.py `
  results/benchmarks/fast_lio2/botanicgarden_1006-03/dynamic_v01/estimate `
  --output results/benchmarks/fast_lio2/botanicgarden_1006-03/dynamic_v01/metrics.json
```

L'analyse associe les poses à moins de `0,06 s`, puis applique un alignement rigide positionnel SE(3), sans mise à l'échelle. Les métriques et journaux restent dans `results/`, donc hors Git.

## 7. Suite recommandée

Les quatre premières actions ont été réalisées le 19 août 2026 et sont consignées dans `docs/11_Campagne_FAST_LIO2_complete_sensibilite_Livox_V0.1.md`.

La suite est de qualifier le ratio sorties/scans à vitesse réduite, puis de reproduire exactement le même protocole avec Point-LIO et LIO-SAM.
