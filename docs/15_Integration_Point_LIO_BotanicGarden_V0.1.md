# Intégration Point-LIO et comparaison FAST-LIO2 — BotanicGarden `1006-03`

| Champ | Valeur |
|---|---|
| Référence | DOC-15 |
| Version | V0.1 |
| Date | 19 août 2026 |
| Statut | Opérationnel préliminaire |
| Dataset | BotanicGarden `1006-03`, VLP-16 + Xsens |
| Algorithme | Point-LIO, port ROS 2 Humble `dfloreaa/point_lio_ros2` |
| Commit figé | `a8e2d0d5090af97ead8dd4fac3d37cf3dbb33ff7` |

## 1. Conclusion

Point-LIO est intégré au socle Docker ROS 2 Humble et passe le protocole demandé à vitesse réelle : test de 5 s, fenêtre dynamique de 30 s et séquence complète de 581,12 s. Le passage complet comparable du 19 août 2026 reçoit et synchronise les `5 762` scans LiDAR, produit `5 758` odométries et termine proprement à un facteur de rejeu effectif de `0,9980×`.

Sur la séquence complète, Point-LIO présente une meilleure précision locale que FAST-LIO2 (`RPE translation = 0,04642 m` contre `0,04825 m`) et une erreur d'orientation absolue légèrement plus faible (`1,556°` contre `1,672°`). En revanche, sa dérive globale est plus élevée : `ATE = 0,4994 m` contre `0,3592 m` pour FAST-LIO2.

L'intégration de Point-LIO est donc acceptée comme **opérationnelle préliminaire**. Elle ne justifie pas encore un remplacement de FAST-LIO2. La comparabilité d'entrée est maintenant rétablie ; le classement final reste **À valider** après le passage complet LIO-SAM et la répétition des candidats proches.

## 2. Intégration réalisée

- image `drone-agricole/point-lio:0.1.0` construite depuis un commit figé ;
- compilation ROS 2 Humble reproductible dans `software/docker/Dockerfile` ;
- configuration VLP-16/Xsens dédiée dans `configs/lio/point_lio/` ;
- utilisation directe de `T_xsens_vlp16`, sans estimation en ligne des extrinsèques ;
- champ temporel PointCloud2 interprété en secondes ;
- une odométrie publiée par scan traité ;
- instrumentation interne sur `/point_lio/pipeline_counters` ;
- profondeur de file LiDAR paramétrable et mode fiable activé pour les rosbags ;
- génération automatique de `resource_profile.json`, `run_manifest.json` et `metrics.json` ;
- Point-LIO sélectionnable dans le tableau de bord 3D multi-algorithme.

Les covariances Point-LIO et les seuils géométriques initiaux sont **À valider** par une campagne de sensibilité. Le QoS fiable est adapté au lecteur rosbag ; il devra être remis en mode best-effort si un futur LiDAR matériel n'offre pas le mode fiable.

## 3. Protocole exécuté

| Étape | Entrée | Vitesse | Résultat |
|---|---|---:|---|
| Compilation Docker | ROS 2 Humble | — | succès |
| Test court | extrait 5 s | 1× | succès, arrêt propre |
| Fenêtre dynamique | 30 s à partir de 60 s | 1× | succès |
| Séquence complète | 581,12 s | 1× | succès |
| Trajectoire | ATE, RPE, orientation, longueur | — | calculée |
| Ressources | CPU total/moyen, RSS maximal | — | mesurées |
| Pipeline | reçus, synchronisés, initialisation, mises à jour, odométries | — | instrumenté |
| Comparaison | passages FAST-LIO2 instrumentés du même dataset | 1× | générée |

Pour éviter de confondre surcharge d'affichage et charge algorithmique, les trois références sont exécutées sans publication du nuage 3D. Le profil visuel séparé active `/cloud_registered` depuis le tableau de bord.

## 4. Résultats Point-LIO

| Mesure | Test 5 s | Dynamique 30 s | Complet 581 s |
|---|---:|---:|---:|
| Scans LiDAR dans l'entrée | 49 | 298 | 5 762 |
| Scans reçus / synchronisés | 49 / 49 | 298 / 298 | 5 762 / 5 762 |
| Odométries | 46 | 295 | 5 758 |
| Sorties / scans reçus | 93,88 % | 98,99 % | 99,93 % |
| Scans sans sortie expliqués | 3 | 3 | 4 |
| ATE translation RMSE | 0,00478 m | 0,02251 m | 0,49940 m |
| ATE orientation RMSE | non interprétable¹ | 14,125° | 1,556° |
| RPE translation RMSE, Δt = 1 s | 0,00786 m | 0,04559 m | 0,04642 m |
| RPE rotation RMSE, Δt = 1 s | 0,0505° | 0,1957° | 0,5898° |
| Ratio longueur estimée / référence | 1,0303 | 0,99909 | 0,99176 |
| CPU total | 3,21 s | 11,69 s | 197,83 s |
| CPU moyen équivalent | 0,281 cœur | 0,320 cœur | 0,337 cœur |
| RSS maximal du processus | 167,9 Mio | 185,5 Mio | 315,7 Mio |
| Facteur de rejeu effectif | 0,821×¹ | 0,963× | 0,9980× |

¹ Le test de 5 s est presque stationnaire : l'alignement d'orientation absolue est mal contraint et les coûts fixes du lecteur dominent le facteur de rejeu. Il sert à valider l'intégration, pas à classer les algorithmes.

Les scans sans odométrie sont entièrement expliqués par les états d'initialisation et rejets instrumentés. Le compteur `unaccounted_synchronized_scans` vaut zéro, y compris sur le nouveau passage complet.

## 5. Comparaison directe avec FAST-LIO2

### 5.1 Séquence complète à 1×

| Mesure | FAST-LIO2 | Point-LIO | Écart Point-LIO |
|---|---:|---:|---:|
| Scans reçus par l'algorithme | 5 762 | 5 762 | 0 |
| Odométries | 5 758 | 5 758 | 0 |
| ATE translation RMSE | **0,35916 m** | 0,49940 m | +39,0 % |
| ATE orientation RMSE | 1,6716° | **1,5562°** | −6,9 % |
| RPE translation RMSE | 0,04825 m | **0,04642 m** | −3,8 % |
| RPE rotation RMSE | 0,59370° | **0,58981°** | −0,7 % |
| CPU total | 229,58 s | **197,83 s** | −13,8 % |
| CPU moyen équivalent | 0,391 cœur | **0,337 cœur** | −13,9 % |
| RSS maximal | **307,0 Mio** | 315,7 Mio | +2,9 % |
| Facteur de rejeu effectif | 0,9992× | 0,9980× | équivalent |

Point-LIO est plus léger et légèrement meilleur localement, tandis que FAST-LIO2 conserve nettement mieux la cohérence globale de la trajectoire sur dix minutes.

### 5.2 Fenêtre dynamique à 1×

| Mesure | FAST-LIO2 | Point-LIO |
|---|---:|---:|
| ATE translation RMSE | 0,02481 m | **0,02251 m** |
| ATE orientation RMSE | **13,209°** | 14,125° |
| RPE translation RMSE | 0,04728 m | **0,04559 m** |
| RPE rotation RMSE | **0,1923°** | 0,1957° |
| CPU moyen équivalent | **0,318 cœur** | 0,320 cœur |
| RSS maximal | **174,9 Mio** | 185,5 Mio |

Sur 30 s, les écarts sont faibles et partagés ; cette fenêtre valide le comportement dynamique mais ne départage pas les deux algorithmes.

## 6. Comparabilité rétablie le 19 août 2026

Le profil FAST-LIO2 est maintenant harmonisé : profondeur `100`, livraison fiable, délai DDS de `1,0 s` et contrôle de vidange. Les deux nouveaux passages complets reçoivent et synchronisent `5 762 / 5 762` scans, publient chacun `5 758` odométries et terminent sans scan inexpliqué.

La différence historique de livraison avant callback est donc supprimée du tableau 5.1. Les écarts restants peuvent être attribués aux pipelines et réglages algorithmiques sous réserve de répétabilité. Le classement à trois reste **À valider** après le passage complet LIO-SAM ; chaque candidat proche devra ensuite être répété au moins trois fois.

## 7. Artefacts

- test court validé : `results/benchmarks/point_lio/botanicgarden_1006-03/smoke_reliable_20260819T142000Z/` ;
- fenêtre dynamique : `results/benchmarks/point_lio/botanicgarden_1006-03/dynamic_1x_20260819T143000Z/` ;
- séquence complète : `results/benchmarks/point_lio/botanicgarden_1006-03/full_1x_20260819T140200Z/` ;
- comparaison JSON : `comparison_fast_lio2.json` dans les deux derniers dossiers ;
- lanceur : `tools/benchmarks/run_pointlio_botanicgarden_benchmark.sh` ;
- comparaison générique : `tools/benchmarks/compare_lio_runs.py` ;
- patch amont : `software/third_party/patches/point_lio/0001-pipeline-diagnostics-and-qos.patch` ;
- passage complet Point-LIO comparable : `results/benchmarks/point_lio/botanicgarden_1006-03/dashboard_20260819T173537Z_6feb6ccc/` ;
- passage complet FAST-LIO2 comparable : `results/benchmarks/fast_lio2/botanicgarden_1006-03/dashboard_20260819T171258Z_2a31bc7f/`.

## 8. Traçabilité

| Besoin | Composant | Test | Résultat |
|---|---|---|---|
| LIO reproductible | image Point-LIO figée | construction Docker | succès |
| Fonctionnement temps réel | Point-LIO + BotanicGarden complet | rejeu 581 s à 1× | `0,9980×`, succès |
| Précision locale | analyse RPE | complet, Δt = 1 s | `0,04642 m`, `0,58981°` |
| Précision globale | analyse ATE SE(3), sans échelle | complet | `0,49940 m`, `1,5562°` |
| Charge calcul | profileur de processus | complet | `0,337` cœur, `315,7` Mio |
| Intégrité des scans | compteurs Point-LIO | complet | `5 762 / 5 762` reçus |
| Harmonisation FAST-LIO2 | QoS fiable + contrôle de vidange | complet à 1× | `5 762 / 5 762`, succès |
| Comparaison FAST-LIO2 | comparateur LIO | deux passages complets corrigés | comparable, classement à trois **À valider** |

## 9. Suite recommandée

1. exécuter LIO-SAM sur la séquence complète avec le même protocole et la même politique de livraison ;
2. produire la comparaison finale des trois algorithmes ;
3. répéter au moins trois fois les configurations candidates ;
4. lancer une sensibilité Point-LIO sur voxels, covariances IMU et seuil de planéité ;
5. sélectionner ensuite un candidat embarqué sur précision, stabilité et ressources.
