# Outils du projet

La logique des anciens scripts a été regroupée dans l'exécutable C++17 `drone-agricole-tools`. Son code est dans `software/cpp/src/cli/ProjectTools.cpp` et les implémentations réutilisables dans `software/cpp/src/core/`.

## Commandes disponibles

| Commande | Fonction |
|---|---|
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

Afficher l'aide depuis l'environnement ROS 2 Humble :

```powershell
docker compose --profile lio run --rm botanicgarden-adapter drone-agricole-tools help
```

Le dossier `tools/datasets/` ne contient que des ressources déclaratives utiles aux données. Il n'existe plus de couche d'orchestration Python, shell ou PowerShell propre au projet.
