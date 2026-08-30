# Tableau de bord 3D temps réel et supervision des benchmarks

| Champ | Valeur |
|---|---|
| Référence | DOC-12 |
| Version | V0.2 |
| Date | 19 août 2026 |
| Statut | Opérationnel préliminaire |
| Portée validée | FAST-LIO2 sur BotanicGarden `1006-03` |

## 1. Objectif

Ce socle rend les rejeux et futurs scénarios de simulation observables pendant leur exécution. Il fournit dans une page locale :

- un nuage LiDAR 3D temps réel ;
- la trajectoire FAST-LIO2 et la vérité terrain alignée ;
- les indicateurs d'avancement, temps réel, CPU, mémoire, ATE et ratio de sorties ;
- quatre historiques glissants sur 120 secondes.
- un panneau de sélection du dataset, de la séquence et de l'algorithme ;
- le réglage contrôlé des principaux paramètres ;
- les commandes de lancement et d'arrêt de l'essai.

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

Le serveur est contenu dans le service Docker `fast-lio-dashboard`. La page écoute sur le port TCP `8080` de localhost et de l'adresse Wi-Fi locale `192.168.1.25`, sans publication sur les interfaces virtuelles du PC. Aucune donnée n'est envoyée sur Internet et aucun compte externe n'est requis. Le tableau de bord ne possède pas encore d'authentification : toute personne présente sur le même réseau local peut lancer ou arrêter une simulation, le réseau doit donc être de confiance.

Le contrôleur lance le script de benchmark dans le même conteneur, sans exposer le moteur Docker à l'interface Web. Un seul essai peut être actif. Les sélections autorisées proviennent du catalogue versionné `configs/visualization/dashboard_catalog.json` ; aucun chemin ni aucune commande arbitraire ne peut être fourni depuis le navigateur.

## 3. Panneau de commande

### 3.1 Catalogue initial

| Catégorie | Choix disponibles |
|---|---|
| Dataset | BotanicGarden |
| Séquence | `1006-03` rapide 5 s, dynamique 30 s ou complète 581 s |
| Algorithme actif | FAST-LIO2 |
| Algorithmes réservés | Point-LIO puis LIO-SAM, visibles mais désactivés |

L'ajout ultérieur d'un dataset ou d'une séquence consiste à compléter le catalogue. L'activation d'un nouvel algorithme exige aussi un lanceur validé côté serveur ; modifier seulement l'interface ne suffit pas.

### 3.2 Paramètres exposés

| Paramètre | Valeur initiale | Intervalle autorisé | Effet |
|---|---:|---:|---|
| Vitesse de rejeu | 1,0× | 0,2 à 2,0× | rythme de lecture du rosbag |
| Voxel du nuage | 0,50 m | 0,10 à 2,00 m | filtrage LiDAR avant estimation |
| Voxel de la carte | 0,50 m | 0,10 à 2,00 m | résolution de la carte interne |
| Sous-échantillonnage | 4 | 1 à 10 | un point conservé sur N |
| Itérations maximales | 3 | 1 à 10 | optimisation par scan |
| Zone aveugle | 1,0 m | 0,1 à 5,0 m | exclusion des points proches |
| Portée de détection | 100 m | 20 à 200 m | portée utilisée par le mapping |

Ces valeurs sont des paramètres d'essai, **pas des exigences figées**. Chaque demande est validée côté serveur. La configuration YAML réellement utilisée est copiée sous `effective_config.yaml` avec le résultat, et `dashboard_request.json` conserve la sélection et les valeurs demandées.

## 4. Données affichées

### 4.1 Vue 3D

| Élément | Topic | Traitement d'affichage |
|---|---|---|
| Nuage enregistré | `/cloud_registered` | au plus 6 000 points par image, intensité normalisée |
| Trajectoire estimée | `/Odometry` | au plus 1 600 sommets |
| Vérité terrain | `/gt_poses` | alignement rigide SE(3) en ligne, puis au plus 1 600 sommets |

La souris permet de tourner autour de la scène et la molette permet de zoomer. Les commandes **Centrer la vue** et **Nuage visible/masqué** restent disponibles pendant le rejeu.

### 4.2 Indicateurs et graphiques

- **Progression** : temps couvert par la vérité terrain divisé par la durée du rosbag ;
- **Temps réel** : secondes de données reçues par seconde murale entre la première et la dernière pose ;
- **CPU FAST-LIO2** : pourcentage instantané d'un cœur logique et temps CPU cumulé ;
- **Mémoire FAST-LIO2** : RSS du processus et de ses descendants ;
- **ATE en ligne** : RMSE de position après alignement rigide sur les associations temporelles disponibles ;
- **Sorties / référence** : nombre de poses estimées divisé par le nombre de poses de référence.

L'ATE affichée pendant le rejeu est une aide au diagnostic. Le calcul hors ligne de DOC-11 demeure la référence, car il applique le protocole complet et produit également les erreurs d'orientation et la RPE.

## 5. Utilisation

Depuis PowerShell, à la racine `D:\ProjetGuillaume\DroneAgricole` :

```powershell
.\tools\visualization\start_fastlio_dashboard.ps1
```

Le lanceur construit l'image si nécessaire, démarre le serveur, vérifie son état et ouvre `http://127.0.0.1:8080`. Il ne démarre plus automatiquement un rejeu : le choix et le lancement sont effectués depuis le panneau.

Le lanceur affiche également l'adresse utilisable depuis un autre appareil du réseau, sous la forme `http://<adresse-IP-du-PC>:8080`. Si l'adresse Wi-Fi du PC change, la valeur publiée dans `compose.yaml` doit être adaptée.

Dans la page :

1. sélectionner le dataset et la séquence ;
2. sélectionner l'algorithme disponible ;
3. régler les voxels et, si nécessaire, ouvrir les paramètres avancés ;
4. utiliser **Lancer la simulation** ;
5. utiliser **Arrêter** pour interrompre proprement l'essai actif.

Arrêt du serveur graphique :

```powershell
.\tools\visualization\stop_fastlio_dashboard.ps1
```

## 6. Séparation entre visualisation et mesure formelle

Le paramétrage graphique publie `/cloud_registered`, ce qui ajoute un coût de calcul, de sérialisation et de rendu. Il utilise le fichier :

```text
configs/lio/fast_lio2/botanicgarden_velodyne_xsens_visual.yaml
```

Les campagnes comparatives formelles conservent la configuration sans publication du nuage. Une exécution graphique ne doit donc pas remplacer les résultats headless de DOC-11 dans une comparaison d'algorithmes ou de matériels.

## 7. Validation réalisée

| Identifiant | Vérification | Résultat du 19 août 2026 |
|---|---|---|
| VAL-VIZ-001 | Construction et démarrage du service Docker | Conforme, contrôle d'état HTTP positif |
| VAL-VIZ-002 | Alignement rigide et réduction des trajectoires | 2 tests unitaires réussis |
| VAL-VIZ-003 | Rejeu BotanicGarden cinq secondes de bout en bout | 37 poses FAST-LIO2, 49 références et 37 nuages reçus |
| VAL-VIZ-004 | Contenu de la dernière scène | 2 841 points 3D, CPU, mémoire et ATE reçus ; facteur temps réel figé à 1,006× après la fin |
| VAL-VIZ-005 | Configuration Compose, syntaxes Python, JavaScript et PowerShell | Conforme |
| VAL-VIZ-006 | Catalogue et validation des paramètres | 1 dataset, 3 séquences, 3 algorithmes dont 1 actif ; 5 tests unitaires réussis |
| VAL-VIZ-007 | Lancement depuis l'API du panneau | Essai 5 s terminé avec succès ; voxels 0,25/0,75 m conservés dans `effective_config.yaml` |
| VAL-VIZ-008 | Arrêt depuis l'API du panneau | Essai 30 s arrêté proprement après réception de 11 poses de référence |
| VAL-VIZ-009 | Traçabilité de la demande | `dashboard_request.json`, configuration effective, profil de ressources et manifeste présents |

Les valeurs du jeu court valident le transport et l'affichage ; elles ne constituent pas un résultat de performance scientifique.

## 8. Extensions prévues

1. connecter la pose PX4 et la vérité terrain Gazebo via ROS 2 Jazzy ;
2. ajouter le modèle simplifié du drone, son attitude et sa trace dans la même scène ;
3. superposer les obstacles et rangs du futur `VINEYARD_BENCH_V01` ;
4. ajouter les métriques de mission : écart au corridor, distance aux obstacles, commandes et événements de sécurité ;
5. ajouter une vue de comparaison de plusieurs exécutions et leurs configurations.

Ces extensions réutilisent le serveur et l'interface actuels ; elles n'imposent pas de changer le socle de visualisation.
