# Campagne FAST-LIO2 complète, sensibilité et conversion Livox — V0.1

- Référence : DOC-11
- Date : 19 août 2026
- Statut : opérationnel préliminaire

## 1. Périmètre réalisé

Cette campagne couvre les quatre objectifs suivants sur BotanicGarden `1006-03` :

1. exécution de toute la portion synchronisée VLP-16 + Xsens + vérité terrain ;
2. mesure CPU, mémoire, temps réel, ATE, orientation et RPE ;
3. sensibilité aux voxels et aux extrinsèques ;
4. migration explicite `livox_ros_driver/msg/CustomMsg` vers `livox_ros_driver2/msg/CustomMsg`.

Les résultats sont reproductibles, mais restent préliminaires. Ils ne figent ni un paramétrage final ni un critère d'acceptation.

## 2. Traçabilité

| Identifiant | Objectif | Composant / test | Résultat |
|---|---|---|---|
| `VAL-LIO-RT-001` | Séquence complète et ressources | `run_fastlio2_botanicgarden_benchmark.sh` | `full_v01/run_manifest.json` |
| `VAL-LIO-MET-001` | ATE, orientation et RPE | `analyze_lio_trajectory.py` | `full_v01/metrics.json` |
| `VAL-LIO-SENS-001` | Sensibilité paramètres/extrinsèques | configurations `sensitivity/` | `sensitivity_summary.json` |
| `VAL-DATA-LIVOX-001` | Migration du message Livox | adaptateur + tests unitaires + abonné ROS 2 | validé sur 50 scans réels |

Les résultats volumineux sont conservés sous `results/` et les bags dérivés sous `datasets/derived/`. Ces dossiers restent hors Git.

## 3. Définition de la séquence complète utilisable

La vérité terrain couvre `599,715385 s`, mais le flux Xsens commence plus tard et se termine plus tôt. Une mesure LIO ne peut pas être valide sans IMU ; la séquence de référence est donc l'intersection exacte des trois flux nécessaires :

| Élément | Valeur |
|---|---:|
| Début relatif au bag LIO | `12,806102826 s` |
| Durée synchronisée | `581,120665074 s` |
| Nuages VLP-16 | 5 762 |
| Messages Xsens IMU | 232 215 |
| Poses de vérité terrain | 5 762 |
| Total | 243 739 messages |
| Taille MCAP compressée | environ 2,4 Gio |

Le premier bag dérivé de 599,7 s, qui contenait des bords sans IMU, a été supprimé puis régénéré sur cette intersection. Les rosbags sources n'ont jamais été modifiés.

Commande de préparation :

```powershell
docker compose run --rm botanicgarden-adapter prepare `
  --lio-bag datasets/public/botanicgarden/1006-03/raw/1006_03_LIO.bag `
  --ground-truth-bag datasets/public/botanicgarden/1006-03/ground_truth/gt_1006_03_qnew.bag `
  --output datasets/derived/botanicgarden/1006-03/full/velodyne_xsens_fastlio2_full_ros2 `
  --pipeline velodyne_xsens `
  --velodyne-time-mode start-relative `
  --start-offset-s 12.806102826 `
  --duration-s 581.120665074 `
  --config configs/datasets/botanicgarden/1006-03.yaml
```

## 4. Méthode de mesure

### Poste utilisé

- processeur : AMD Ryzen 7 9800X3D, 8 cœurs / 16 threads ;
- mémoire physique Windows : 16 166 277 120 octets, soit environ 15,1 Gio ;
- limite mémoire visible lors du contrôle Docker : environ 7,29 Gio ;
- Docker Desktop client/serveur : `29.7.2` ;
- conteneur : `drone-agricole/fast-lio2:0.1.0`, Linux `amd64`.

PX4/Gazebo a été arrêté pendant les mesures puis relancé à leur issue. Le profileur échantillonne toutes les `0,25 s` le processus FAST-LIO2 et ses enfants. Le pic RSS présenté ci-dessous n'inclut donc pas le lecteur rosbag ni l'enregistreur.

### Métriques de trajectoire

- association temporelle avec la vérité terrain à `±0,06 s` ;
- alignement rigide SE(3) positionnel, sans changement d'échelle ;
- ATE de translation après cet alignement ;
- erreur absolue d'orientation après application de la même rotation d'alignement ;
- RPE translation et rotation entre poses espacées de `1 s` (`±0,06 s`).

## 5. Résultat de la séquence complète

### Temps réel et ressources

| Mesure | Résultat |
|---|---:|
| Durée du bag | `581,1207 s` |
| Durée murale du rejeu | `581,8686 s` |
| Secondes de données par seconde murale | `0,9987×` |
| Durée du processus FAST-LIO2 | `586,5861 s` |
| CPU utilisateur | `176,02 s` |
| CPU système | `26,71 s` |
| CPU total | `202,73 s` |
| CPU moyen équivalent | `0,3456` cœur, soit `34,56 %` d'un cœur |
| Pic RSS FAST-LIO2 | `302,69 Mio` |

Le rejeu respecte pratiquement le mur d'horloge. Cependant, 5 131 odométries ont été publiées pour 5 762 scans, soit `89,05 %`, à environ `8,84 Hz` pour une entrée à `9,92 Hz`. La trajectoire couvre bien `580,55 s`, mais ce ratio interdit encore de conclure à un temps réel sans perte. Un rejeu plus lent devra déterminer si l'écart vient de pertes à `1×` ou du comportement nominal de publication de cette branche FAST-LIO2.

### Précision

| Métrique | RMSE | Médiane | Maximum |
|---|---:|---:|---:|
| ATE translation | `0,4594 m` | `0,2917 m` | `1,1842 m` |
| Erreur absolue d'orientation | `1,6815°` | `1,5881°` | `4,2777°` |
| RPE translation à 1 s | `0,0560 m` | `0,0422 m` | `0,5843 m` |
| RPE rotation à 1 s | `0,5913°` | `0,3130°` | `4,1736°` |

La RPE utilise 4 560 paires. La longueur estimée vaut `681,254 m` contre `684,488 m` pour la référence, soit un ratio de `0,99527` et une sous-estimation de `0,473 %`.

Commande d'exécution :

```powershell
docker compose run --rm fast-lio2 bash tools/benchmarks/run_fastlio2_botanicgarden_benchmark.sh `
  datasets/derived/botanicgarden/1006-03/full/velodyne_xsens_fastlio2_full_ros2 `
  results/benchmarks/fast_lio2/botanicgarden_1006-03/full_v01 `
  configs/lio/fast_lio2/botanicgarden_velodyne_xsens.yaml `
  1.0
```

## 6. Sensibilité sur la fenêtre dynamique de 30 s

Tous les essais utilisent le même bag de `29,997 s` commençant à l'offset `60 s`, à vitesse `1×`. Les trois répétitions de la référence donnent :

- 258 à 266 poses associées ;
- ATE translation RMSE de `0,02386` à `0,02540 m` ;
- RPE translation RMSE de `0,04592` à `0,04747 m` ;
- RPE rotation RMSE de `0,1925` à `0,2097°` ;
- CPU total de `10,66` à `11,30 s` ;
- pic RSS de `172,92` à `174,35 Mio`.

Cette dispersion définit le bruit d'exécution observé : les écarts inférieurs à environ 10 % ne sont pas considérés comme concluants sur un essai unique.

| Variante | ATE trans. RMSE | RPE trans. RMSE | RPE rot. RMSE | CPU total | Pic RSS | Lecture préliminaire |
|---|---:|---:|---:|---:|---:|---|
| Référence, voxels 0,50 m | `0,02386 m` | `0,04605 m` | `0,1943°` | `10,66 s` | `174,35 Mio` | référence |
| Voxels fins 0,25 m | `0,02323 m` | `0,04394 m` | `0,1880°` | `13,20 s` | `208,04 Mio` | précision similaire, coût nettement supérieur |
| Voxels grossiers 1,00 m | `0,04837 m` | `0,06548 m` | `0,2677°` | `9,17 s` | `158,40 Mio` | ATE ×2,03 malgré le gain de ressources |
| Extrinsèque X `+5 cm` | `0,02641 m` | `0,04672 m` | `0,1930°` | `10,62 s` | `172,67 Mio` | dégradation ATE modérée, proche de la variabilité |
| Extrinsèque lacet `+2°` | `0,03016 m` | `0,02816 m` | `0,2094°` | `10,76 s` | `173,86 Mio` | ATE +26 % et RPE rotation +8 % ; RPE translation atypiquement plus faible |

Le gain apparent de RPE translation avec l'erreur de lacet ne doit pas être interprété comme une amélioration globale : l'ATE se dégrade et la RPE de translation dépend des orientations relatives. L'erreur absolue d'orientation sur cette fenêtre presque rectiligne est également mal contrainte par l'alignement positionnel ; la valeur issue de la séquence complète est plus représentative.

Conclusions préliminaires :

- conserver `0,50 m` comme référence de comparaison ;
- ne pas retenir `1,00 m` sans autre étude, car la perte de précision est nette ;
- `0,25 m` n'apporte pas de gain supérieur à la variabilité observée, malgré environ `+24 %` de CPU et `+19 %` de mémoire ;
- la calibration en rotation doit être surveillée plus strictement que cette perturbation de translation de 5 cm.

## 7. Conversion explicite Livox

L'adaptateur enregistre maintenant `/livox/lidar` directement avec le type cible `livox_ros_driver2/msg/CustomMsg`. Il reconstruit explicitement le header ROS 2, les champs du message et chaque `CustomPoint`, au lieu de conserver l'ancien espace de noms ROS 1.

Validation sur un extrait réel de cinq secondes :

| Élément | Résultat |
|---|---:|
| Type source | `livox_ros_driver/msg/CustomMsg` |
| Type cible | `livox_ros_driver2/msg/CustomMsg` |
| Scans Livox | 50 |
| IMU BMI088 | 1 012 messages |
| Vérité terrain | 49 poses |
| Désérialisation ROS 2 native | réussie, `point_num = 24000` |
| Tests automatisés totaux | 6 réussis |

Sortie de validation : `datasets/derived/botanicgarden/1006-03/smoke/livox_bmi088_si_5s_ros2_driver2`.

## 8. Artefacts principaux

- bag complet : `datasets/derived/botanicgarden/1006-03/full/velodyne_xsens_fastlio2_full_ros2` ;
- résultat complet : `results/benchmarks/fast_lio2/botanicgarden_1006-03/full_v01` ;
- sensibilité : `results/benchmarks/fast_lio2/botanicgarden_1006-03/sensitivity_30s_v01` ;
- profils : `resource_profile.json` et `run_manifest.json` dans chaque exécution ;
- métriques : `metrics.json` dans chaque exécution ;
- synthèse : `sensitivity_summary.json` et `sensitivity_summary.csv`.

## 9. Suites recommandées

1. rejouer la fenêtre dynamique puis la séquence complète à `0,8×` pour qualifier le ratio sorties/scans ;
2. répéter chaque variante trois fois ou exécuter la sensibilité à vitesse réduite pour isoler l'effet algorithmique ;
3. appliquer ce protocole identique à Point-LIO puis LIO-SAM ;
4. exécuter les mêmes mesures sur la future cible Jetson Orin.
