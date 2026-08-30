# Qualification FAST-LIO2 à 0,8× et répétabilité

| Champ | Valeur |
|---|---|
| Référence | DOC-13 |
| Version | V0.1 |
| Date | 19 août 2026 |
| Statut | Opérationnel préliminaire |
| Dataset | BotanicGarden `1006-03` |
| Algorithme | FAST-LIO2 ROS 2, commit `a4743b095409588842a5b30ddfa27e29d2f99164` |

## 1. Objectifs

Cette campagne traite les deux suites ouvertes par DOC-11 :

1. rejouer la fenêtre dynamique puis la séquence complète à `0,8×` pour déterminer si le ratio odométries/scans est limité par la charge temps réel ;
2. exécuter trois répétitions de la référence et de chaque variante sur la fenêtre dynamique à vitesse réduite, afin de séparer l'effet algorithmique de la variabilité d'exécution.

Les résultats restent préliminaires. Ils ne constituent pas des exigences figées pour le produit final.

## 2. Protocole

### 2.1 Isolement du banc

- tableau de bord 3D arrêté ;
- PX4 SITL et Gazebo arrêtés ;
- exécutions séquentielles, sans campagnes concurrentes ;
- configuration headless, sans publication de `/cloud_registered` ;
- même dataset, même commit FAST-LIO2 et mêmes extrinsèques que DOC-11 ;
- profileur à `0,25 s` et vitesse de rosbag demandée `0,8×`.

La première fenêtre dynamique a été mesurée correctement, mais son analyse postérieure a révélé que l'image FAST-LIO2 ne contenait pas `rosbags`. L'image a été reconstruite avec `rosbags==0.11.3`, sans modification du code FAST-LIO2 ni de sa configuration. La trajectoire existante a ensuite été analysée sans rejeu. La campagne est désormais autonome et reprenable.

### 2.2 Comptage du ratio

Le ratio utilise maintenant le nombre exact de messages du topic d'entrée :

```text
ratio sorties/scans = poses /Odometry enregistrées
                      ----------------------------
                      messages /velodyne_points du bag
```

Le manifeste de chaque essai est passé au schéma 2 et contient `input_topic_message_counts`. Le ratio ne dépend donc pas d'une approximation par la vérité terrain enregistrée.

### 2.3 Matrice d'essais

| Portée | Variante | Répétitions |
|---|---|---:|
| Fenêtre dynamique 30 s | référence, voxels 0,50 m | 3 |
| Fenêtre dynamique 30 s | voxels fins 0,25 m | 3 |
| Fenêtre dynamique 30 s | voxels grossiers 1,00 m | 3 |
| Fenêtre dynamique 30 s | extrinsèque X `+5 cm` | 3 |
| Fenêtre dynamique 30 s | extrinsèque lacet `+2°` | 3 |
| Séquence complète 581 s | référence, voxels 0,50 m | 1 |

Total : **16 exécutions complètes**, chacune avec manifeste, configuration effective et métriques ATE/orientation/RPE.

## 3. Qualification du ratio sorties/scans

### 3.1 Fenêtre dynamique répétée

| Vitesse | Répétitions | Ratio moyen | Écart-type | Minimum | Maximum |
|---:|---:|---:|---:|---:|---:|
| `1×` | 3 | `87,70 %` | `1,40 point` | `86,58 %` | `89,26 %` |
| `0,8×` | 3 | `87,47 %` | `2,02 points` | `85,57 %` | `89,60 %` |

L'écart moyen vaut `−0,22 point`. Sur cette fenêtre, ralentir le rejeu ne change donc pas le ratio de manière mesurable.

### 3.2 Séquence complète

| Mesure | `1×` | `0,8×` | Écart |
|---|---:|---:|---:|
| Scans d'entrée | 5 762 | 5 762 | 0 |
| Odométries | 5 131 | 5 214 | +83 |
| Ratio sorties/scans | `89,05 %` | `90,49 %` | `+1,44 point` |
| Couverture temporelle de trajectoire | environ `99,90 %` | `99,88 %` | comparable |

Le ralentissement récupère 83 odométries, mais 548 scans restent sans sortie, soit `9,51 %` des entrées. La chaîne n'est donc pas qualifiée pour produire une odométrie par scan, même à `0,8×`.

### 3.3 Conclusion sur la cause

La baseline dynamique répétée est inchangée entre `1×` et `0,8×`, tandis que la séquence complète ne gagne que `1,44 point`. La saturation CPU brute n'explique donc pas l'essentiel de l'écart. Les causes prioritaires à instrumenter sont :

- scans reçus mais ignorés pendant l'initialisation IMU ;
- scans vides ou rejetés par le prétraitement ;
- cadence propre de publication de la branche ROS 2 de FAST-LIO2 ;
- éventuels écrasements dans les files ROS 2 avant traitement.

## 4. Précision et ressources sur la séquence complète

| Mesure | `1×` | `0,8×` | Variation |
|---|---:|---:|---:|
| ATE translation RMSE | `0,4594 m` | `0,3639 m` | `−20,8 %` |
| Erreur orientation RMSE | `1,6815°` | `1,6634°` | `−1,1 %` |
| RPE translation RMSE à 1 s | `0,0560 m` | `0,0490 m` | `−12,5 %` |
| RPE rotation RMSE à 1 s | `0,5913°` | `0,5867°` | `−0,8 %` |
| CPU total FAST-LIO2 | `202,73 s` | `216,34 s` | `+6,7 %` |
| CPU moyen équivalent | `0,3456` cœur | `0,2958` cœur | `−14,4 %` |
| Pic RSS | `302,69 Mio` | `296,69 Mio` | `−2,0 %` |

L'ATE et la RPE translation s'améliorent sur le passage long à `0,8×`. Comme chaque vitesse ne possède qu'une répétition complète, l'amplitude exacte doit encore être confirmée avant d'être considérée comme un effet déterministe. L'orientation et la RPE rotation restent pratiquement inchangées.

Le CPU total augmente légèrement parce que le processus reste actif plus longtemps ; son occupation moyenne diminue nettement, ce qui confirme l'absence de saturation d'un cœur complet.

## 5. Sensibilité répétée à 0,8×

Les valeurs sont les moyennes de trois répétitions. Le symbole `±` représente l'écart-type d'exécution.

| Variante | Sorties/scans | ATE RMSE | RPE trans. | RPE rot. | CPU total | RSS |
|---|---:|---:|---:|---:|---:|---:|
| Référence 0,50 m | `87,47 ± 2,02 %` | `0,02614 ± 0,00144 m` | `0,04613 m` | `0,2021°` | `11,36 s` | `172,92 Mio` |
| Voxel fin 0,25 m | `86,58 ± 2,04 %` | `0,02348 ± 0,00019 m` | `0,04371 m` | `0,1860°` | `13,50 s` | `208,77 Mio` |
| Voxel grossier 1,00 m | `87,92 ± 1,78 %` | `0,05003 ± 0,00435 m` | `0,06585 m` | `0,2664°` | `9,67 s` | `157,61 Mio` |
| Extrinsèque X `+5 cm` | `89,15 ± 0,70 %` | `0,02505 ± 0,00077 m` | `0,04618 m` | `0,1991°` | `11,35 s` | `173,92 Mio` |
| Extrinsèque lacet `+2°` | `88,81 ± 3,12 %` | `0,02770 ± 0,00014 m` | `0,02826 m` | `0,2001°` | `11,43 s` | `173,68 Mio` |

### 5.1 Effets par rapport à la référence 0,8×

- **Voxel 1,00 m** : ATE `+91 %`, RPE translation `+43 %`, RPE rotation `+32 %`, pour environ `−15 %` de CPU et `−9 %` de mémoire. La dégradation algorithmique est robuste et confirme son rejet comme réglage de référence.
- **Voxel 0,25 m** : ATE `−10 %`, RPE translation `−5 %`, RPE rotation `−8 %`, mais CPU `+19 %` et mémoire `+21 %`. Le gain modeste apparaît plus cohérent que dans l'essai unique de DOC-11, sans justifier encore un changement de baseline.
- **Translation +5 cm** : écarts de précision faibles et dans la variabilité de cette fenêtre. Ce résultat ne démontre pas que la calibration de translation est sans importance.
- **Lacet +2°** : ATE `+6 %` et RPE translation artificiellement plus faible (`−39 %`). Cet effet atypique se répète, ce qui confirme une interaction entre la métrique, l'alignement positionnel et la géométrie presque rectiligne ; il ne doit pas être interprété comme une amélioration.
- **Ratio sorties/scans** : aucune variante ne produit un changement supérieur à la dispersion observée de façon convaincante.

Le choix de référence reste donc `0,50 m`. Le voxel `0,25 m` demeure un candidat de précision à retester sur une portion plus longue et sur Jetson, sous contrainte de ressources.

## 6. Limites

- une seule répétition complète par vitesse, en raison de la durée du dataset ;
- les variantes de DOC-11 hors baseline ne possédaient qu'une répétition à `1×` ; leurs différences directes `1×/0,8×` ne sont donc pas statistiquement qualifiées ;
- la fenêtre dynamique de 30 s est presque rectiligne et contraint mal certaines erreurs d'orientation/extrinsèques ;
- le ratio mesure les publications `/Odometry`, sans compteur interne distinguant réception, traitement, rejet et publication.

## 7. Traçabilité et artefacts

| Identifiant | Objectif | Résultat |
|---|---|---|
| `VAL-LIO-RT-002` | Ratio dynamique à 0,8× | 3 répétitions, `87,47 ± 2,02 %` |
| `VAL-LIO-RT-003` | Ratio complet à 0,8× | 5 214 / 5 762, `90,49 %` |
| `VAL-LIO-SENS-002` | Sensibilité répétée à 0,8× | 5 variantes × 3 répétitions |
| `VAL-LIO-MET-002` | ATE, orientation et RPE à 0,8× | métriques présentes pour 16/16 essais |
| `VAL-LIO-REP-001` | Agrégation et comparaison 1×/0,8× | rapports JSON et CSV générés |

Racine des résultats :

```text
results/benchmarks/fast_lio2/botanicgarden_1006-03/qualification_08x_v01/
```

Artefacts principaux :

- `campaign_summary.json` et `campaign_runs.csv` ;
- `comparison_1x_vs_08x.json` et `comparison_1x_vs_08x.csv` ;
- `dynamic/<variante>/repeat_01..03/` ;
- `full/baseline/repeat_01/` ;
- `effective_config.yaml`, `run_manifest.json`, `resource_profile.json` et `metrics.json` dans chaque essai.

## 8. Suite recommandée

Avant de passer à Point-LIO, ajouter des compteurs internes à FAST-LIO2 pour distinguer :

```text
scans reçus → scans prétraités → scans rejetés → mises à jour d'état → odométries publiées
```

Une fenêtre dynamique instrumentée devrait suffire à localiser l'origine des 10 à 12 % de sorties manquantes. La comparaison Point-LIO/LIO-SAM pourra ensuite utiliser le même ratio explicite et les mêmes statistiques de répétabilité.
