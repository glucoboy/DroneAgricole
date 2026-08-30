# Inspection des calibrations — BotanicGarden

| Champ | Valeur |
|---|---|
| Référence | DOC-07 |
| Version | V0.1 |
| Date | 18 août 2026 |
| Statut | Inspection terminée avec un point d'attention |
| Source | [Dépôt officiel BotanicGarden](https://github.com/robot-pesg/BotanicGarden) |
| Commit inspecté | `84c4806428ca16c154238e263a7f8bf828bf58e1` |

## 1. Résultat synthétique

Les calibrations nécessaires aux deux chaînes LIO sont présentes :

- Velodyne VLP-16 vers IMU Xsens ;
- Livox AVIA vers son IMU BMI088 ;
- transformation Livox vers Velodyne ;
- paramètres de bruit des deux IMU ;
- transformation d'alignement global propre à la séquence `1006-03`.

Les rotations sont proches de matrices orthonormales et les configurations algorithmiques reprennent bien les extrinsèques directes. La chaîne caméra vers BMI088 n'est toutefois pas cohérente avec l'extrinsèque directe Livox/BMI088. Pour le benchmark LIO, nous utiliserons l'extrinsèque directe fournie dans la configuration FAST-LIO2 et nous ne mélangerons pas ces deux chaînes.

Une copie exacte des fichiers inspectés est conservée sous `datasets/public/botanicgarden/1006-03/calibration/official_84c4806428ca/`. Elle n'est pas versionnée avec Git tant que les conditions de réutilisation ne sont pas clarifiées.

## 2. Velodyne VLP-16 et Xsens

La matrice `T_xsens_vlp16` transforme un point du repère VLP-16 vers le repère Xsens :

```text
translation = [0,0584868 ; 0,0084042 ; 0,1689155] m
distance entre origines = 0,178952 m
rotation équivalente = 1,520°
```

La matrice est reprise à l'identique dans la configuration LVI-SAM/LIO-SAM officielle. Sa recomposition via `Xsens <- RGB0 <- VLP16` donne un résidu numérique maximal de `1,33e-15`, ce qui confirme la cohérence de cette partie de la chaîne.

Paramètres IMU officiels :

| Paramètre | Valeur |
|---|---:|
| Fréquence | 400 Hz |
| Bruit accéléromètre | 0,0005 |
| Marche aléatoire accéléromètre | 0,00002 |
| Bruit gyroscope | 0,0002 |
| Marche aléatoire gyroscope | 0,000004 |

Sur 2 000 messages de la séquence, la norme médiane de l'accélération Xsens vaut `9,8057`, ce qui confirme des unités SI proches de m/s².

## 3. Livox AVIA et BMI088

La matrice directe `T_bmi088_livox`, également utilisée par la configuration FAST-LIO2 officielle, est :

```text
translation = [0,04165 ; 0,02326 ; -0,0284] m
distance entre origines = 0,055519 m
rotation = identité
```

Paramètres IMU officiels :

| Paramètre | Valeur |
|---|---:|
| Fréquence | 200 Hz |
| Bruit accéléromètre | 0,002 |
| Marche aléatoire accéléromètre | 0,00005 |
| Bruit gyroscope | 0,0003 |
| Marche aléatoire gyroscope | 0,000005 |

Sur 2 000 messages, la norme médiane de l'accélération vaut `0,99575`. Cela confirme la note officielle : les données brutes sont exprimées autour de `1 g` et non autour de `9,81 m/s²`. La conversion générale vers les unités SI est un facteur `9,8`, mais FAST-LIO2 et R3LIVE peuvent gérer ce cas sans préconversion. Le comportement sera donc configuré par algorithme et validé à l'initialisation.

## 4. Relation entre les deux LiDAR

`T_vlp16_livox` transforme Livox vers VLP-16 :

```text
translation = [0,0788930 ; -0,0066162 ; -0,1764092] m
distance entre origines = 0,193360 m
rotation équivalente = 1,540°
```

La recomposition via la caméra RGB0 donne un résidu maximal de `1,11e-15`. Cette relation pourra être utile pour comparer les deux trajectoires ou pour la future fusion multi-LiDAR.

## 5. Alignement de la séquence `1006-03`

Le fichier `seq_extrinsics.yaml` fournit `T_1008_01_1006_03`. Sa translation vaut environ `[4,2962 ; -0,1652 ; 0,00035] m` et sa rotation équivalente `1,124°`.

Cette matrice sert à replacer plusieurs séquences dans un repère global commun. Elle n'est pas nécessaire au calcul ATE/RPE d'une seule séquence avec alignement de trajectoire. Le sens exact déduit du nom devra être confirmé avant une comparaison multi-séquence.

## 6. Points d'attention détectés

1. Dans `calib_chain.yaml`, les matrices déclarées `T_bmi088_gray0` et `T_bmi088_rgb0` sont identiques alors que les caméras Gray0 et RGB0 ne sont pas confondues. Les recompositions vers `T_bmi088_livox` présentent donc un résidu important. Ce point n'affecte pas notre LIO si nous utilisons directement `T_bmi088_livox`.
2. La configuration FAST-LIO2 officielle active la sauvegarde d'un unique PCD sans limite. Cette option sera désactivée pour le rosbag complet afin d'éviter une consommation mémoire excessive.
3. Le décalage temporel LiDAR/IMU est fixé à zéro et la resynchronisation logicielle est désactivée, conformément à la synchronisation matérielle annoncée. Nous contrôlerons néanmoins le comportement lors du premier passage LIO.
4. La configuration LVI-SAM contient des chemins de sortie propres à la machine des auteurs. Ils seront remplacés par des chemins du workspace.
5. Les bruits IMU mesurés à l'arrêt sont décrits par les auteurs comme optimistes en mouvement. Les valeurs finales de l'algorithme restent **à valider** ; la configuration LVI-SAM applique déjà des valeurs plus conservatrices.

## 7. Fichiers et traçabilité

| Fichier officiel | SHA-256 |
|---|---|
| `calib/extrinsics/calib_chain.yaml` | `1c7915b17cc4e23de80b657289ab3e7537c0d05bdd9d6d43b6791cfb93c1d61f` |
| `calib/extrinsics/seq_extrinsics.yaml` | `455f199e1215d572c1ff6b97c7c220dc266d9cf2d909777b6c9a62ba033e5b6e` |
| `calib/imu_intrinsics/xsens_imu_param.yaml` | `8823b8e0b98598fcff19efb4303f1bc237aae0cefbab683d86dab01f551b23e3` |
| `calib/imu_intrinsics/bmi088_imu_param.yaml` | `5aacd8143f32c64c248233dab30c3ef5454e27ec1e5cd2093ca6aea5b04035b6` |
| `config/Fast-LIO2/avia.yaml` | `e1e80a27fdec4318019e842605c5f1b866350700c4da8dad37f02ce82e3e4bbd` |
| `config/LVI-SAM/BGarden_lidar.yaml` | `c4a50dd67d2de71cdeb61e6fd03c3fb4cc60fb65f7f0903ae57becd404b9f1be` |

La configuration normalisée du projet est enregistrée dans `configs/datasets/botanicgarden/1006-03.yaml`.

## 8. Décision pour le premier benchmark

- FAST-LIO2 / Livox : utiliser directement `T_bmi088_livox`, démarrer avec la configuration officielle et contrôler la norme de gravité avant toute conversion.
- LIO-SAM / Velodyne : utiliser `T_xsens_vlp16` et les champs `ring` et `time` déjà présents dans le nuage.
- Point-LIO : adapter la chaîne Livox en documentant explicitement la gestion du facteur `9,8`.
- Évaluation : utiliser `/gt_poses` dans le repère `/velodyne`, après validation de la convention de pose et découpe sur l'intervalle commun.
