# Inspection initiale — BotanicGarden `1006-03`

| Champ | Valeur |
|---|---|
| Référence | DOC-05 |
| Version | V0.1 |
| Date | 18 août 2026 |
| Statut | Inspection initiale terminée |
| Source | [Dépôt officiel BotanicGarden](https://github.com/robot-pesg/BotanicGarden) |

## 1. Résultat synthétique

La séquence `1006-03` est téléchargée et lisible. Les deux fichiers sont des rosbags ROS 1 valides au niveau structurel. Le contenu est adapté à un premier test LIO : deux couples LiDAR/IMU sont disponibles, et la vérité terrain couvre presque toute la séquence utile.

Le dataset n'est pas encore déclaré `ready`. Il reste à inspecter les calibrations et à valider les conditions d'usage. Les empreintes SHA-256 ci-dessous constituent une référence d'intégrité locale ; elles ne peuvent pas être comparées à une empreinte officielle, aucune n'ayant été identifiée sur la page de téléchargement.

## 2. Fichiers locaux

| Fichier | Taille | SHA-256 local |
|---|---:|---|
| `1006_03_LIO.bag` | 6 325 796 540 octets (5,89 Gio) | `482d4b3081264a6e5eaf3c05ea57d45f25cf572e01c1f887d5b598372ab79c68` |
| `gt_1006_03_qnew.bag` | 834 042 octets | `2d507e1344da2dbb8763f96971f9d9ea902e95f7084acc903768a3f8737cf3dd` |

Emplacements :

- `datasets/public/botanicgarden/1006-03/raw/1006_03_LIO.bag` ;
- `datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag` ;
- métadonnées détaillées : `datasets/public/botanicgarden/1006-03/inspection/bag_metadata.json`.

## 3. Vue générale

| Élément | Rosbag LIO | Vérité terrain |
|---|---:|---:|
| Durée enregistrée | 610,003 s | 599,715 s |
| Nombre de messages | 478 023 | 5 947 |
| Début UTC | 2022-10-06 03:24:26,398544 | 2022-10-06 03:24:36,484569 |
| Fin UTC | 2022-10-06 03:34:36,401674 | 2022-10-06 03:34:36,199954 |

La vérité terrain commence 10,086 s après le début du rosbag LIO et se termine 0,202 s avant le flux Velodyne. Il faudra néanmoins utiliser l'intersection propre à chaque couple LiDAR/IMU, car les autres capteurs démarrent plus tard et s'arrêtent plus tôt.

## 4. Flux observés

| Topic | Type | Messages | Fréquence observée | Repère / contenu échantillonné |
|---|---|---:|---:|---|
| `/velodyne_points` | `sensor_msgs/PointCloud2` | 6 049 | 9,915 Hz | `velodyne`, champs `x y z intensity ring time` |
| `/odom` | `nav_msgs/Odometry` | 116 733 | 200,0 Hz | `odom` vers `base_link` |
| `/imu/data` | `sensor_msgs/Imu` | 232 215 | 399,6 Hz | `imu_link`, orientation non fournie |
| `/livox/lidar` | `livox_ros_driver/CustomMsg` | 5 783 | 10,0 Hz | `livox_frame`, 24 000 points dans le premier message |
| `/livox/imu` | `sensor_msgs/Imu` | 117 243 | environ 200 Hz | `livox_frame` |
| `/gt_poses` | `geometry_msgs/PoseStamped` | 5 947 | 9,915 Hz | repère déclaré `/velodyne` |

La présence du champ `time` dans le nuage Velodyne est favorable au deskew. Le message Livox est un type propriétaire : l'environnement ROS devra donc inclure les définitions de `livox_ros_driver`.

## 5. Régularité temporelle

- Velodyne : période médiane de 100,860 ms, aucune coupure supérieure à deux périodes médianes.
- Odométrie : période médiane de 5,000 ms, aucune coupure supérieure à deux périodes médianes.
- IMU Xsens : période médiane de 2,500 ms ; 47 intervalles atteignent environ 5 ms, soit vraisemblablement un échantillon manquant ponctuel sur 232 215 messages.
- Livox LiDAR : période médiane de 99,844 ms, aucune coupure supérieure à deux périodes médianes.
- IMU Livox : période médiane de 4,997 ms, sans coupure supérieure à deux périodes médianes ; quelques intervalles plus courts expliquent une moyenne légèrement supérieure à 200 Hz.
- Vérité terrain : période médiane de 100,860 ms, aucune coupure supérieure à deux périodes médianes.

Cette première lecture ne montre donc pas de rupture temporelle majeure.

## 6. Fenêtres recommandées pour les benchmarks

Les timestamps devront être conservés dans leur précision native. Pour éviter les bords incomplets, l'adaptateur calculera automatiquement l'intersection entre la vérité terrain, le LiDAR sélectionné et son IMU :

- pipeline Velodyne + Xsens : environ 581,1 s disponibles avant ajout d'une marge de stabilisation ;
- pipeline Livox AVIA + IMU Livox : environ 578,2 s disponibles avant ajout d'une marge de stabilisation.

Les valeurs définitives de découpe sont **à valider** après inspection des calibrations et premier passage de l'algorithme.

## 7. Points d'attention

1. Le flux `/odom` est présent mais son origine exacte n'est pas encore établie. Il ne doit pas être utilisé comme vérité terrain sans confirmation documentaire.
2. `/imu/data` annonce une orientation indisponible (`orientation_covariance[0] = -1`) ; les mesures gyroscope et accéléromètre restent celles attendues par un LIO.
3. La vérité terrain est déclarée dans le repère `/velodyne`. Il faudra confirmer la convention de pose, les extrinsèques et l'alignement attendu avant le calcul ATE/RPE.
4. La séquence provient d'un robot terrestre en jardin botanique : elle valide la chaîne logicielle, pas encore la dynamique d'un drone ni la représentativité d'un vignoble.
5. Les conditions d'usage commercial demeurent **à valider**.

## 8. Prochaine étape

Télécharger ou extraire depuis la source officielle les fichiers de calibration et les configurations fournies pour FAST-LIO2, établir l'arbre de repères, puis créer l'adaptateur BotanicGarden et un premier extrait de fumée reproductible.
