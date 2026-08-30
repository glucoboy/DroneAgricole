# Tableau de bord 3D temps réel et supervision des benchmarks

| Champ | Valeur |
|---|---|
| Référence | DOC-12 |
| Version | V0.1 |
| Date | 19 août 2026 |
| Statut | Opérationnel préliminaire |
| Portée validée | FAST-LIO2 sur BotanicGarden `1006-03` |

## 1. Objectif

Ce socle rend les rejeux et futurs scénarios de simulation observables pendant leur exécution. Il fournit dans une page locale :

- un nuage LiDAR 3D temps réel ;
- la trajectoire FAST-LIO2 et la vérité terrain alignée ;
- les indicateurs d'avancement, temps réel, CPU, mémoire, ATE et ratio de sorties ;
- quatre historiques glissants sur 120 secondes.

La première intégration est volontairement réalisée sur FAST-LIO2, dont tous les topics nécessaires existent déjà. La même interface recevra ensuite la pose PX4, le modèle du drone et les éléments du monde Gazebo après mise en service du pont uXRCE-DDS/ROS 2.

## 2. Architecture retenue

```text
Rejeu BotanicGarden                Profileur de ressources
  /points_raw, /imu/data              CPU, mémoire, durée
             │                                │
             ▼                                ▼
        FAST-LIO2                         topics ROS 2
 /cloud_registered, /Odometry      /benchmark/*
             │                                │
             └──────────────┬─────────────────┘
                            ▼
                  serveur local ROS 2
                  alignement et réduction
                            │
                    WebSocket JSON, 5 Hz
                            │
                            ▼
                  navigateur Windows local
             WebGL 3D + graphiques Canvas 2D
```

Le serveur est contenu dans le service Docker `fast-lio-dashboard`. La page est exposée uniquement sur `127.0.0.1:8080` : aucune donnée n'est envoyée sur Internet et aucun compte externe n'est requis.

## 3. Données affichées

### 3.1 Vue 3D

| Élément | Topic | Traitement d'affichage |
|---|---|---|
| Nuage enregistré | `/cloud_registered` | au plus 6 000 points par image, intensité normalisée |
| Trajectoire estimée | `/Odometry` | au plus 1 600 sommets |
| Vérité terrain | `/gt_poses` | alignement rigide SE(3) en ligne, puis au plus 1 600 sommets |

La souris permet de tourner autour de la scène et la molette permet de zoomer. Les commandes **Centrer la vue** et **Nuage visible/masqué** restent disponibles pendant le rejeu.

### 3.2 Indicateurs et graphiques

- **Progression** : temps couvert par la vérité terrain divisé par la durée du rosbag ;
- **Temps réel** : secondes de données reçues par seconde murale entre la première et la dernière pose ;
- **CPU FAST-LIO2** : pourcentage instantané d'un cœur logique et temps CPU cumulé ;
- **Mémoire FAST-LIO2** : RSS du processus et de ses descendants ;
- **ATE en ligne** : RMSE de position après alignement rigide sur les associations temporelles disponibles ;
- **Sorties / référence** : nombre de poses estimées divisé par le nombre de poses de référence.

L'ATE affichée pendant le rejeu est une aide au diagnostic. Le calcul hors ligne de DOC-11 demeure la référence, car il applique le protocole complet et produit également les erreurs d'orientation et la RPE.

## 4. Utilisation

Depuis PowerShell, à la racine `D:\ProjetGuillaume\DroneAgricole` :

```powershell
.\tools\visualization\start_fastlio_dashboard.ps1
```

Le lanceur construit l'image si nécessaire, démarre le serveur, vérifie son état, ouvre `http://127.0.0.1:8080`, puis exécute par défaut le sous-ensemble BotanicGarden de 30 secondes.

Exemple avec le jeu court de cinq secondes :

```powershell
.\tools\visualization\start_fastlio_dashboard.ps1 `
  -BagPath datasets/derived/botanicgarden/1006-03/smoke/velodyne_xsens_fastlio2_5s_ros2
```

Arrêt du serveur graphique :

```powershell
.\tools\visualization\stop_fastlio_dashboard.ps1
```

## 5. Séparation entre visualisation et mesure formelle

Le paramétrage graphique publie `/cloud_registered`, ce qui ajoute un coût de calcul, de sérialisation et de rendu. Il utilise le fichier :

```text
configs/lio/fast_lio2/botanicgarden_velodyne_xsens_visual.yaml
```

Les campagnes comparatives formelles conservent la configuration sans publication du nuage. Une exécution graphique ne doit donc pas remplacer les résultats headless de DOC-11 dans une comparaison d'algorithmes ou de matériels.

## 6. Validation réalisée

| Identifiant | Vérification | Résultat du 19 août 2026 |
|---|---|---|
| VAL-VIZ-001 | Construction et démarrage du service Docker | Conforme, contrôle d'état HTTP positif |
| VAL-VIZ-002 | Alignement rigide et réduction des trajectoires | 2 tests unitaires réussis |
| VAL-VIZ-003 | Rejeu BotanicGarden cinq secondes de bout en bout | 37 poses FAST-LIO2, 49 références et 37 nuages reçus |
| VAL-VIZ-004 | Contenu de la dernière scène | 2 841 points 3D, CPU, mémoire et ATE reçus ; facteur temps réel figé à 1,006× après la fin |
| VAL-VIZ-005 | Configuration Compose, syntaxes Python, JavaScript et PowerShell | Conforme |

Les valeurs du jeu court valident le transport et l'affichage ; elles ne constituent pas un résultat de performance scientifique.

## 7. Extensions prévues

1. connecter la pose PX4 et la vérité terrain Gazebo via ROS 2 Jazzy ;
2. ajouter le modèle simplifié du drone, son attitude et sa trace dans la même scène ;
3. superposer les obstacles et rangs du futur `VINEYARD_BENCH_V01` ;
4. ajouter les métriques de mission : écart au corridor, distance aux obstacles, commandes et événements de sécurité ;
5. permettre la sélection du scénario et la comparaison de plusieurs exécutions.

Ces extensions réutilisent le serveur et l'interface actuels ; elles n'imposent pas de changer le socle de visualisation.
