# DOC-14 — Instrumentation FAST-LIO2 et métriques finales du tableau de bord

Version : V0.1  
Date : 19 août 2026  
Statut : opérationnel préliminaire

## 1. Objectif

Cette évolution répond à deux besoins :

- expliquer le ratio incomplet entre scans LiDAR et odométries FAST-LIO2 ;
- produire et afficher automatiquement les métriques finales de chaque simulation lancée depuis le tableau de bord.

Elle contribue à `PERF-002` et `SAFE-REQ-003`. Les résultats décrits ici restent **À valider** sur les séquences dynamique et complète.

## 2. Instrumentation du pipeline

La révision amont FAST-LIO2 reste figée à `a4743b095409588842a5b30ddfa27e29d2f99164`. Le patch versionné `0001-pipeline-diagnostics.patch` ajoute les compteurs et le topic de diagnostic. Le patch `0002-configurable-lidar-qos.patch` rend uniquement la livraison LiDAR configurable ; aucun des deux ne modifie l'estimation, les covariances, les voxels ou les extrinsèques.

Le topic `/fast_lio2/pipeline_counters`, de type `std_msgs/msg/String`, transporte un objet JSON versionné. Il est publié quatre fois par seconde et enregistré dans le rosbag de résultat.

Les étapes comptées sont :

```text
scans reçus
  -> scans prétraités
  -> scans synchronisés avec l'IMU
  -> initialisation / rejets documentés / mise à jour d'état
  -> odométries publiées
```

Pour chaque exécution instrumentée, les invariants suivants doivent être contrôlés :

```text
synchronisés
  = initialisation
  + rejet après désentrelacement
  + initialisation de la carte
  + rejet après sous-échantillonnage
  + mises à jour d'état

mises à jour d'état = odométries publiées
```

Tout écart non nul est conservé dans `pipeline_accounting` afin de révéler une branche non instrumentée ou une perte de publication.

## 3. Calcul automatique de `metrics.json`

Après une simulation terminée avec le code zéro, le serveur du tableau de bord exécute automatiquement `tools/benchmarks/analyze_lio_trajectory.py` sur le rosbag `estimate`.

Le dossier de résultat contient désormais :

- `metrics.json` : ATE, orientation, RPE, longueur de trajectoire et compteurs du pipeline ;
- `analysis.log` : sortie complète du calcul ;
- `dashboard_request.json` : état de l'analyse et nom du fichier de métriques ;
- le topic instrumenté dans `estimate/` ;
- le résumé final exact dans `fast_lio2.log` sous le préfixe `FASTLIO_PIPELINE_FINAL`.

Si le calcul échoue, la simulation reste distinguée de l'analyse : son exécution peut être réussie alors que `analysis_state` vaut `failed`.

## 4. Affichage dans le tableau de bord

Pendant le rejeu, la carte `Sorties / référence` affiche également :

- le nombre de scans reçus ;
- le nombre de scans synchronisés ;
- le nombre d'odométries publiées.

Après le calcul final, le bouton `Afficher les métriques finales` ouvre un panneau contenant :

- ATE de translation et d'orientation ;
- RPE de translation et de rotation à une seconde ;
- ratio sorties/scans et ratio de longueur de trajectoire ;
- décomposition complète du pipeline et écarts comptables.

## 5. Validation fonctionnelle

Essai : `TEST-LIO-INSTR-01`  
Dataset : BotanicGarden `1006-03`, fenêtre de cinq secondes  
Vitesse demandée : `1,0×`  
Résultat : `results/benchmarks/fast_lio2/botanicgarden_1006-03/dashboard_20260819T130643Z_ddd9f5b1`

| Étape | Nombre |
|---|---:|
| Scans présents dans le dataset | 49 |
| Scans reçus par FAST-LIO2 | 42 |
| Scans prétraités | 42 |
| Scans synchronisés avec l'IMU | 42 |
| Scan d'initialisation | 1 |
| Rejets après désentrelacement | 2 |
| Initialisation de la carte | 1 |
| Rejets après sous-échantillonnage | 0 |
| Mises à jour d'état | 38 |
| Odométries publiées | 38 |
| Scans synchronisés non expliqués | 0 |
| Mises à jour sans odométrie | 0 |

Le calcul de `metrics.json`, son exposition par l'API et les onze tests ciblés sont validés. La fenêtre de cinq secondes est trop courte et trop peu mobile pour qualifier les erreurs d'orientation ou la tenue du temps réel ; elle valide uniquement la chaîne logicielle.

Le premier enseignement est que les sept premiers scans manquants se situent avant le callback FAST-LIO2, et non dans l'optimisation. Leur cause exacte reste **À valider** : établissement DDS au démarrage, QoS, profondeur de file ou ordonnancement du callback.

### 5.1 Validation courte après correction QoS

Essai : `TEST-LIO-QOS-01`  
Dataset : BotanicGarden `1006-03`, fenêtre de cinq secondes  
Vitesse demandée : `1,0×`  
Résultat : `results/benchmarks/fast_lio2/botanicgarden_1006-03/dashboard_20260819T162657Z_6ebf48d8`

Le profil de benchmark utilise désormais une profondeur de `100`, une fiabilité `reliable` et un délai de découverte DDS de `1,0 s`. Le lanceur attend ensuite que le nombre de scans reçus atteigne celui du rosbag et que les compteurs soient stables pendant une seconde. Cette attente est tracée dans `pipeline_drain.json`.

| Contrôle | Résultat |
|---|---:|
| Scans présents dans le dataset | 49 |
| Scans reçus | 49 |
| Scans synchronisés | 49 |
| Scans manquants | 0 |
| Odométries publiées | 46 |
| État de vidange | `complete` |

Ce test valide la correction sur la chaîne réelle du tableau de bord. La tenue de `100 %` sur la fenêtre dynamique et la séquence complète reste **À valider**.

## 6. Interprétation des vitesses de rejeu

Un rejeu à `0,8×` conserve les horodatages capteurs mais donne 25 % de temps processeur supplémentaire entre deux messages. Il ne représente pas une capacité disponible sur le drone en fonctionnement temps réel.

En exploitation, les capteurs arrivent au rythme physique. Retarder leur traitement sans ralentir le monde accumulerait une latence incompatible avec la navigation. Les références opérationnelles sont donc :

1. rejeu à `1,0×` sur le PC pour la qualification de développement ;
2. rejeu à `1,0×` sur la cible Jetson avec la charge logicielle représentative ;
3. validation sur capteurs réels, puis en vol.

Le rejeu ralenti reste utile comme diagnostic et comme estimation d'une limite algorithmique hors contrainte de calcul. Réduire réellement la vitesse de vol peut aussi améliorer l'observation, mais ce n'est pas équivalent à ralentir artificiellement le flux logiciel : les fréquences capteurs, la dynamique IMU et le nombre de scans par mètre changent.

## 7. Traçabilité

| Exigence | Composant | Test | Résultat |
|---|---|---|---|
| `PERF-002` | compteurs FAST-LIO2 et `pipeline_accounting` | `TEST-LIO-INSTR-01` | chaîne comptable cohérente, qualification complète **À valider** |
| `SAFE-REQ-003` | topic `/fast_lio2/pipeline_counters` | `TEST-LIO-INSTR-01` | fraîcheur et compteurs disponibles dans le tableau de bord |
| Plan DOC-03, métriques LIO | analyse automatique | test court depuis le tableau de bord | `metrics.json` créé et exposé |
| `PERF-002` | QoS LiDAR fiable, profondeur 100 et contrôle de vidange | `TEST-LIO-QOS-01` | `49 / 49` scans, séquence complète **À valider** |

## 8. Suite recommandée

1. exécuter depuis le tableau de bord la fenêtre dynamique à `1,0×` ;
2. exécuter la séquence complète à `1,0×` ;
3. confirmer `missing_scans = 0` dans `pipeline_drain.json` et `5 762 / 5 762` dans `metrics.json` ;
4. répéter les candidats retenus avant le classement final ;
5. conserver `1,0×` comme critère de passage pour le PC puis pour la Jetson.
