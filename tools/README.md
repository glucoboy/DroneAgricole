# Outils du projet

La logique des anciens scripts a été regroupée dans l'exécutable C++17 `drone-agricole-tools`. Son point d'entrée est `software/cpp/src/cli/ProjectTools.cpp`. Les services, calculs et intégrations sont séparés sous `software/cpp/src/application/`, `algorithms/`, `adapters/` et `composition/` ; voir [DOC-SW](../docs/architecture/ARCHITECTURE_LOGICIELLE.md).

## Commandes disponibles

| Commande | Fonction |
|---|---|
| `station-run --request chemin.json` | exécuter une requête T0 avec le cycle partagé de la station, finalisation comprise ; `--workspace` sélectionne le projet |
| `inspect` | inspecter des rosbags ROS 1 et calculer en option leur empreinte |
| `prepare` | convertir un sous-ensemble BotanicGarden en rosbag2 MCAP |
| `export-tum` | exporter la vérité terrain au format TUM |
| `lio-run` | orchestrer un benchmark FAST-LIO2, Point-LIO ou LIO-SAM |
| `analyze` | calculer ATE, orientation, RPE et comptabilité du pipeline |
| `summarize-run` | produire le manifeste et la synthèse d'un essai |
| `summarize-sensitivity` | agréger une étude de sensibilité |
| `summarize-campaign` | agréger les répétitions d'une campagne |
| `compare-runs` | comparer au moins deux résultats |
| `compare-rates` | comparer les campagnes à 1× et 0,8× |
| `fast-lio-campaign` | exécuter la campagne FAST-LIO2 approuvée |
| `vineyard-map-run` | produire une prédiction de rangs figée puis l'évaluer séparément sur une référence optionnelle |
| `friulbot-inspect` | contrôler les topics, les scans synchronisés et les jeux TIFF FriûlBot |
| `friulbot-map-run` | détecter les rangs et trajectoires locales d'un déclenchement LiDAR–caméra |
| `friulbot-prepare` | convertir une fenêtre FriûlBot filtrée en MCAP LiDAR–IMU avec RTK réservé à l'évaluation |

Afficher l'aide depuis l'environnement ROS 2 Humble :

```powershell
docker compose --profile lio run --rm botanicgarden-adapter drone-agricole-tools help
```

Le dossier `tools/datasets/` ne contient que des ressources déclaratives utiles aux données. Il n'existe plus de couche d'orchestration Python, shell ou PowerShell propre au projet.

## Recette de téléchargement EscaYard

La recette CMake d'infrastructure télécharge les fichiers publics sans logique métier et vérifie leurs MD5 officielles. Le lot minimal contient les points RTK et le tableau terrain :

```powershell
cmake -P tools/download_escayard.cmake
```

Ajouter le nuage B7 de la bande verte, d'environ 224 Mo :

```powershell
cmake -DDOWNLOAD_POINT_CLOUD=ON -P tools/download_escayard.cmake
```

L'orthomosaïque multispectrale B7 de 3,4 Go est un produit caméra optionnel. Son téléchargement, contrôlé par le MD5 officiel, n'est jamais activé implicitement :

```powershell
cmake -DDOWNLOAD_ORTHOMOSAIC=ON -P tools/download_escayard.cmake
```

Les sorties sont placées dans `datasets/public/escayard/B7/raw/`, hors Git. Le profil inspecté est `configs/datasets/escayard/B7.yaml`.

Le tableau de bord construit automatiquement la commande cartographique. Pour un diagnostic headless, `--point-cloud` est l'unique entrée du détecteur. L'option `--reference-trunks`, lorsqu'elle est présente, n'est ouverte qu'après l'écriture de `map_prediction.json` et sert uniquement à produire les métriques et la superposition de contrôle.

## Recette de téléchargement FriûlBot

La recette télécharge uniquement le bag brut et les cinq bandes TIFF originales du Test 2 du 22 juillet 2024, vérifie leurs MD5 officielles puis extrait les images. Les bags NDVI, GNDVI et NDRE dérivés restent exclus :

```powershell
cmake -P tools/download_friulbot.cmake
```

Les données sont placées sous `datasets/public/friulbot/`, hors Git. La simulation `Fusion LiDAR–caméra et rangs locaux` est ensuite directement disponible dans le tableau de bord.
