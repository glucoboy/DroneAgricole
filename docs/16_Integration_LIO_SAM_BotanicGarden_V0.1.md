# Intégration LIO-SAM — BotanicGarden `1006-03`

| Champ | Valeur |
|---|---|
| Référence | DOC-16 |
| Version | V0.1 |
| Date | 19 août 2026 |
| Statut | Opérationnel préliminaire |
| Dataset | BotanicGarden `1006-03`, VLP-16 + Xsens |
| Algorithme | LIO-SAM, branche ROS 2 officielle |
| Commit figé | `08af3f32f01725372d4269838dc44c19c6d9e76b` |

## 1. Conclusion

LIO-SAM est intégré au socle Docker ROS 2 Humble, instrumenté selon le schéma commun et sélectionnable dans le tableau de bord. La compilation, le test de cinq secondes et la fenêtre dynamique de trente secondes réussissent à `1×`. Le démarrage exact de la séquence complète est également couvert par un test de régression depuis le 19 août 2026.

Le test court reçoit `49 / 49` scans et la fenêtre dynamique `298 / 298`. Dans les deux cas, LIO-SAM conserve trois scans dans son tampon initial, puis publie une odométrie pour chaque scan prétraité : `46 / 46` et `295 / 295`. Le nombre de scans inexpliqués vaut zéro.

La séquence complète réussit à `1×` : `5 762 / 5 762` scans reçus, `5 758` odométries et zéro scan synchronisé inexpliqué. L'ATE vaut `0,41206 m / 1,13826°`, la RPE à une seconde `0,04174 m / 0,57086°` et le facteur effectif `0,99785×`. Le passage est comparable aux passages complets FAST-LIO2 et Point-LIO ; le classement multicritère est consigné dans DOC-17.

## 2. Intégration réalisée

- image `drone-agricole/lio-sam:0.1.0` construite depuis le commit officiel figé ;
- dépendance GTSAM 4.1 installée dans l'image Ubuntu 22.04 ;
- configuration VLP-16/Xsens dédiée dans `configs/lio/lio_sam/` ;
- quatre composants headless : préintégration IMU, projection, extraction de caractéristiques et optimisation de carte ;
- sorties communes `/Odometry`, `/path` et `/cloud_registered` ;
- politique fiable et profondeur 100 pour le rejeu rosbag ;
- compteurs de réception, prétraitement, synchronisation et publication d'odométrie ;
- rejet contrôlé des IMU dont le quaternion d'orientation est nul ou quasi nul ;
- arrêt immédiat du rejeu si l'un des quatre processus LIO-SAM critiques s'arrête ;
- arrêt manuel propre du lecteur, de l'enregistreur, de LIO-SAM et du moniteur ;
- génération automatique de `resource_profile.json`, `run_manifest.json`, `pipeline_drain.json` et `metrics.json` ;
- sélection LIO-SAM et réglage de six paramètres depuis le tableau de bord.

La politique fiable est un profil de benchmark. Sa compatibilité avec le futur pilote LiDAR matériel reste **À valider** ; un capteur uniquement best-effort demandera un profil distinct.

## 3. Calibration et hypothèses

La transformation officielle `T_xsens_vlp16` est appliquée sans estimation en ligne :

- translation LiDAR vers Xsens : `[0,0584868 ; 0,0084042 ; 0,168916] m` ;
- rotation des vecteurs IMU vers le LiDAR : transposée de la rotation officielle ;
- rotation d'orientation Xsens vers LiDAR : rotation officielle ;
- 16 lignes, horizon 1 800, fréquence LiDAR 10 Hz ;
- accélérations et vitesses angulaires Xsens à environ 400 Hz ;
- fermeture de boucle désactivée pour la baseline odométrique comparable aux deux autres LIO ;
- `mappingProcessInterval = 0,0 s` afin de ne pas introduire de décimation cachée.

Les bruits IMU proviennent de la configuration BotanicGarden fournie avec le dataset. Leur optimalité pour ce port ROS 2 ainsi que les voxels et seuils de caractéristiques sont **À valider** par sensibilité.

## 4. Instrumentation

Le correctif reproductible `software/third_party/patches/lio_sam/0001-reliable-qos-and-pipeline-counters.patch` expose quatre compteurs légers :

| Étape | Topic interne | Signification |
|---|---|---|
| Entrée | `/lio_sam/pipeline/scans_received` | callback LiDAR exécuté |
| Projection | `/lio_sam/pipeline/scans_preprocessed` | nuage projeté et désentrelacé |
| Caractéristiques | `/lio_sam/pipeline/scans_synchronized` | nuage transmis à l'optimiseur |
| Sortie | `/lio_sam/pipeline/odometry_published` | odométrie globale publiée |

Le moniteur agrège ces valeurs sur `/lio_sam/pipeline_counters`, au même format que FAST-LIO2 et Point-LIO. Il rend explicites les scans conservés au démarrage dans `scans_input_buffered` — trois sur les extraits usuels, quatre au début exact du passage complet — et permet au lanceur d'attendre la vidange du pipeline.

## 5. Protocole exécuté

| Étape | Entrée | Vitesse | Résultat |
|---|---|---:|---|
| Compilation Docker | ROS 2 Humble + GTSAM 4.1 | — | succès |
| Tests du tableau de bord | 17 tests automatisés | — | succès |
| Test court headless | extrait 5 s | 1× | succès |
| Régression au début du passage complet | extrait 5 s à l'offset 12,806102826 s | 1× | succès, 50 / 50 scans reçus |
| Test court via page web | extrait 5 s | 1× | succès |
| Fenêtre dynamique via page web | extrait 30 s | 1× | succès |
| Séquence complète via page web | 581,12 s | 1× | succès, métriques complètes |

## 6. Résultats LIO-SAM

| Mesure | Test 5 s | Dynamique 30 s | Complet 581 s |
|---|---:|---:|---:|
| Scans LiDAR dans l'entrée | 49 | 298 | 5 762 |
| Scans reçus | 49 | 298 | 5 762 |
| Scans prétraités / synchronisés | 46 / 46 | 295 / 295 | 5 758 / 5 758 |
| Odométries | 46 | 295 | 5 758 |
| Sorties / scans prétraités | 100 % | 100 % | 100 % |
| Scans conservés dans le tampon initial | 3 | 3 | 4 |
| Scans inexpliqués | 0 | 0 | 0 |
| ATE translation RMSE | 0,00532 m | 0,02502 m | 0,41206 m |
| ATE orientation RMSE | non interprétable¹ | 15,505° | 1,13826° |
| RPE translation RMSE, Δt = 1 s | 0,00945 m | 0,02048 m | 0,04174 m |
| RPE rotation RMSE, Δt = 1 s | 0,03743° | 0,16936° | 0,57086° |
| CPU moyen équivalent | 0,508 cœur² | 1,112 cœur | 1,601 cœur |
| RSS maximal | 234,5 Mio² | 278,4 Mio | 617,6 Mio |
| Facteur de rejeu effectif | non représentatif¹ | 0,9765× | 0,99785× |

¹ Le déplacement total du test court ne vaut que quelques millimètres ; l'alignement positionnel SE(3) ne contraint pas l'orientation absolue. La RPE rotation demeure exploitable comme contrôle fonctionnel local.

² Valeurs du passage lancé depuis le tableau de bord ; elles incluent l'abonnement et la publication nécessaires au rendu 3D.

L'erreur absolue d'orientation de `15,505°` sur trente secondes est du même ordre que les fenêtres dynamiques FAST-LIO2 et Point-LIO, respectivement environ `13,2°` et `14,1°`. Cette fenêtre presque rectiligne ne doit pas servir seule au classement d'orientation.

## 7. Correction du démarrage de la séquence complète

Le passage `dashboard_20260819T203147Z_f3a41a2b` a révélé sept messages Xsens initiaux avec le quaternion `(0, 0, 0, 0)`, tous situés dans les quinze premières millisecondes. LIO-SAM les interprétait comme une erreur fatale « IMU 9 axes requise » et arrêtait la projection ainsi que la préintégration. Le superviseur ne détectait pas la mort de ces processus ; le rosbag continuait donc à défiler sans odométrie jusqu'à l'arrêt manuel.

Le correctif conserve les données sources intactes et ignore seulement les IMU dont la norme du quaternion est inférieure à `0,1`. Les messages suivants étant valides, le traitement démarre normalement. Un avertissement limité dans le temps est inscrit dans `lio_sam.log` afin que cette anomalie reste visible.

Le test de régression `regression_fullstart_20260819T205000Z` utilise les cinq premières secondes du passage complet et inclut les sept messages fautifs. Il reçoit `50 / 50` scans, en prétraite et synchronise `46`, publie `46` odométries, produit des valeurs finies et génère `metrics.json`. Les quatre premiers scans restent dans le tampon de démarrage ; aucun scan synchronisé n'est inexpliqué.

Le lanceur surveille désormais les quatre processus critiques pendant le rejeu. Si l'un d'eux s'arrête, le lecteur rosbag est interrompu et l'essai remonte immédiatement en échec. Un arrêt demandé depuis le tableau de bord termine aussi proprement tous les processus sans lancer une analyse de trajectoire incomplète.

## 8. Tableau de bord

LIO-SAM apparaît avec FAST-LIO2 et Point-LIO dans la liste des algorithmes. Les paramètres exposés sont :

- voxel de surface d'odométrie ;
- voxels de carte pour arêtes et surfaces ;
- seuils de caractéristiques d'arêtes et de surfaces ;
- intervalle de traitement de la carte.

Les accès actifs sont `http://127.0.0.1:8080` sur le PC hôte et `http://192.168.1.25:8080` sur le réseau local. Le bouton d'affichage des métriques finales présente ATE, RPE, orientation et comptabilité du pipeline après chaque réussite.

## 9. Artefacts

- manifeste amont : `software/third_party/lio_sam.yaml` ;
- image : cible `ros-humble-liosam` du `software/docker/Dockerfile` ;
- configuration : `configs/lio/lio_sam/botanicgarden_velodyne_xsens.yaml` ;
- lanceur : `tools/benchmarks/run_liosam_botanicgarden_benchmark.sh` ;
- extrait de régression : `datasets/derived/botanicgarden/1006-03/smoke/velodyne_xsens_liosam_fullstart_5s_ros2/` ;
- passage fautif diagnostiqué : `results/benchmarks/lio_sam/botanicgarden_1006-03/dashboard_20260819T203147Z_f3a41a2b/` ;
- passage de régression validé : `results/benchmarks/lio_sam/botanicgarden_1006-03/regression_fullstart_20260819T205000Z/` ;
- passage complet validé : `results/benchmarks/lio_sam/botanicgarden_1006-03/dashboard_20260819T205649Z_7f42a0fa/` ;
- fenêtre dynamique validée : `results/benchmarks/lio_sam/botanicgarden_1006-03/dashboard_20260819T200339Z_5b7048d4/` ;
- test web validé : `results/benchmarks/lio_sam/botanicgarden_1006-03/dashboard_20260819T200313Z_bcd9ab6e/`.

## 10. Traçabilité

| Besoin | Composant | Test | Résultat |
|---|---|---|---|
| Construction reproductible | image LIO-SAM figée | compilation Docker | succès |
| Intégrité des scans | QoS fiable + compteurs | séquence complète | 100 % reçus, zéro perte inexpliquée |
| Précision locale | analyse RPE | complet, Δt = 1 s | `0,04174 m / 0,57086°` |
| Précision globale | analyse ATE SE(3), sans échelle | séquence complète | `0,41206 m / 1,13826°` |
| Charge calcul | profileur du processus complet | complet avec affichage | `1,601` cœur, `617,6 Mio` |
| Temps réel | lecteur rosbag à 1× | complet avec affichage | `0,99785×` |
| Commande opérateur | tableau de bord multi-LIO | test lancé par API web | succès |
| Tolérance aux IMU initiales invalides | filtre de norme + avertissement | extrait du début exact du passage complet | succès, 7 IMU ignorées et 46 odométries |
| Défaillance d'un composant | garde de processus + arrêt du rosbag | supervision intégrée au lanceur | échec immédiat au lieu d'un rejeu à vide |

## 11. Suite recommandée

1. utiliser DOC-17 comme comparaison de référence des trois passages complets à QoS harmonisée ;
2. répéter FAST-LIO2 et LIO-SAM au moins trois fois pour mesurer la variabilité des deux meilleurs compromis de précision ;
3. valider les candidats à `1×` sur Jetson avec leurs capteurs cibles avant de figer la sélection embarquée.
