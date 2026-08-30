# DOC-22 — T0.2 — Catalogue et runners du tableau de bord

- Version : V0.2
- Date : 30 août 2026
- Statut : opérationnel préliminaire
- Références : DOC-19, DOC-20, DOC-21, ADR-0005

## 1. Objectif

Le lot T0.2 remplace le lancement spécialisé LIO du tableau de bord par une interface commune, pilotée par les contrats T0.1. Il conserve les trois benchmarks existants et ajoute les deux essais PX4 du lot A, sans autoriser le navigateur à fournir une commande système arbitraire.

Le périmètre exécutable est désormais :

| Domaine | Simulation | Variante | Runner approuvé |
|---|---|---|---|
| Localisation | Benchmark LiDAR–IMU | FAST-LIO2 | `fast_lio2` |
| Localisation | Benchmark LiDAR–IMU | Point-LIO | `point_lio` |
| Localisation | Benchmark LiDAR–IMU | LIO-SAM | `lio_sam` |
| Vol SITL | Mission Offboard | Carré nominal | `px4_square` |
| Vol SITL | Mission Offboard | Perte Offboard | `px4_failsafe` |

L'ajout d'une simulation, d'une variante ou d'un dataset reste déclaratif, mais son exécution exige toujours un runner explicitement approuvé côté serveur.

## 2. Catalogue et profils

`SimulationDefinition` accepte maintenant des profils dataset–variante. Un profil associe :

- un dataset et ses séquences compatibles ;
- la configuration de base de chaque algorithme ;
- le topic d'instrumentation attendu ;
- d'éventuelles valeurs de paramètres propres au profil.

Le premier profil publié, `botanicgarden_velodyne_xsens`, couvre BotanicGarden `1006-03` pour FAST-LIO2, Point-LIO et LIO-SAM. Les chemins de configuration qui dépendaient auparavant directement des variantes LIO sont donc isolés dans ce profil. Un nouveau dataset pourra être ajouté sans modifier le serveur, à condition de publier sa définition et un profil compatible.

La simulation `px4_offboard` n'exige pas de dataset. Elle déclare les scénarios carré et perte Offboard, leurs paramètres bornés, leurs sorties, leurs métriques et leur classe de sécurité `sitl_confirmed`.

## 3. Interface commune des runners

`software/visualization/runners.py` réalise quatre responsabilités :

1. exposer au tableau de bord les simulations, variantes, profils, paramètres et compatibilités calculés par le registre ;
2. valider une demande d'exécution et rejeter toute entrée, valeur ou clé inconnue ;
3. résoudre uniquement un identifiant de runner présent dans la liste approuvée ;
4. préparer la commande, le répertoire de résultat, les fichiers effectifs et les métadonnées à archiver.

Le runner LIO réutilise les lanceurs headless historiques. Il génère une configuration d'exécution isolée sous `results/runtime_configs/` et traduit les identifiants canoniques vers les clés internes de l'algorithme. La correspondance LIO-SAM est notamment testée afin de préserver ses noms de paramètres YAML.

Le runner PX4 traverse volontairement deux environnements :

```text
Tableau de bord ROS 2 Humble
        |
        | requête interne bornée
        v
Service runner ROS 2 Jazzy
        |
        | commande fixe ros2 run
        v
Pont PX4 + Agent DDS + PX4 SITL
```

Le client distant ne transmet que le scénario, l'identifiant de passage, le répertoire relatif approuvé et les paramètres numériques validés. Le service Jazzy construit lui-même la commande fixe de `offboard_test`.

## 4. Garde-fous

Les protections suivantes sont actives :

- une seule exécution est autorisée simultanément par le tableau de bord ;
- un second verrou interdit aussi deux essais PX4 concurrents ;
- aucun nom de programme, argument libre ou chemin absolu n'est accepté depuis le navigateur ;
- tous les chemins résolus doivent rester sous le workspace ;
- les résultats PX4 doivent rester sous `results/simulation/px4_lot_a/` ;
- les paramètres sont typés, bornés et filtrés par leur définition ;
- PX4 exige à la fois la classe SITL, `DRONE_AGRICOLE_SITL=1` et le verrou `execute:=true` ;
- l'arrêt demande d'abord une interruption propre au nœud Offboard, afin de laisser PX4 reprendre la sécurité et l'atterrissage, avant une terminaison forcée éventuelle ;
- le script d'arrêt coupe le tableau de bord, puis le runner, puis la pile PX4.

Ces runners ne constituent aucune autorisation d'essai sur drone réel. Ils sont limités au banc PX4 SITL actuel.

## 5. Interface graphique

Le panneau de contrôle est maintenant alimenté par `drone_agricole.dashboard_options.v2`. Il permet de choisir :

- la simulation ;
- le dataset et la séquence lorsque la simulation en exige ;
- l'algorithme ou le scénario ;
- le profil capteurs/configuration ;
- les paramètres principaux et avancés générés depuis les contrats.

En mode PX4, les champs dataset et profil sont masqués et les paramètres de mission apparaissent. En mode LIO, BotanicGarden, les trois séquences, les trois algorithmes et le profil Velodyne/Xsens sont restaurés. L'interface refuse de lancer une combinaison indisponible ou incomplète.

Les panneaux 3D, métriques LIO et état PX4 sont conservés. La décomposition complète des couches visuelles par simulation reste un travail ultérieur ; elle n'empêche pas le lancement générique T0.2.

Le nom de service Compose `fast-lio-dashboard` est conservé provisoirement pour ne pas casser les scripts et habitudes existants. L'image fonctionnelle passe à `drone-agricole/lio-dashboard:0.3.0`.

## 6. Résultats écrits par une nouvelle exécution

Après une exécution réussie, le serveur conserve les fichiers historiques utiles et écrit aussi les contrats natifs T0 :

- `run_request.json` ;
- `t0_run_manifest.json` ;
- `t0_metrics.json` ;
- `artifacts.json` ;
- `events.jsonl`.

Pour un benchmark LIO, `metrics.json` et les artefacts déjà produits par l'analyse restent disponibles. Pour PX4, le résultat du test Offboard est importé dans les contrats communs. Les fichiers natifs sont validés avant écriture.

Cette étape prépare T0.3, qui devra indexer et recharger ces résultats depuis le tableau de bord.

## 7. Validation réalisée

La qualification T0.2 a été exécutée après redémarrage de Windows, avec Docker Desktop 4.87.0 et le moteur Docker 29.7.2. Le démarrage initial a révélé deux défauts d'intégration reproductibles : les services Python étaient lancés par chemin de fichier sans exposer la racine du workspace dans `sys.path`, et la commande de diagnostic du lanceur n'activait pas le profil Compose `sim`. Les services sont désormais lancés comme modules Python et le diagnostic active les profils `viz` et `sim`.

Les images suivantes ont été construites et exécutées :

| Image | Identifiant qualifié | Plateforme |
|---|---|---|
| `drone-agricole/lio-dashboard:0.3.0` | `sha256:4123a7f3c20aaf8b46e1d47c403c7abd224bd0eafa397ca0d7f4e93161018887` | `linux/amd64` |
| `drone-agricole/px4-ros:0.2.0` | `sha256:3436b7d74c35a7bfe9545241283c5cede552525c5d8ad95d93885dba8dc3817e` | `linux/amd64` |

| Contrôle | Résultat |
|---|---|
| Contrats et adaptateurs T0.1 | 8 tests réussis |
| Résolution et sécurité des runners T0.2 | 7 tests réussis |
| Suite T0.1 + T0.2 dans l'image du tableau de bord | 15 tests réussis |
| Compilation des modules Python | Réussie |
| Analyse syntaxique JavaScript | Réussie |
| Analyse syntaxique PowerShell | Réussie |
| Validation de la configuration Compose | Réussie |
| Santé du tableau de bord et du runner PX4 | Réussie |
| Essai interactif sur l'interface servie par Docker | Réussi, aucune erreur JavaScript |

L'essai interactif confirme :

- les trois variantes FAST-LIO2, Point-LIO et LIO-SAM ;
- les scénarios PX4 carré et perte Offboard ;
- la sélection du profil `botanicgarden_velodyne_xsens` ;
- la génération des paramètres LIO et PX4 ;
- le masquage des sélecteurs dataset en mode PX4 ;
- l'activation du lancement uniquement pour une sélection valide ;
- l'affichage dans la page des métriques finales d'un résultat PX4.

## 8. Régression Docker/ROS intégrée

Trois exécutions ont été lancées par l'API du tableau de bord dans la pile Docker complète :

| Essai | Résultat principal | Verdict |
|---|---|---|
| FAST-LIO2, BotanicGarden `1006-03`, fenêtre 5 s | 49 scans reçus et synchronisés, 45 odométries, ATE translation `0,00850 m`, sortie avec code 0 | Réussi |
| PX4 carré nominal | Offboard et armement confirmés, altitude maximale `1,998 m`, quatre segments atteints, atterrissage et désarmement confirmés, aucun failsafe | Réussi |
| PX4 perte Offboard | Perte Offboard et failsafe observés, mode d'atterrissage automatique observé, altitude maximale `2,004 m`, atterrissage confirmé | Réussi |

Les répertoires de preuve sont :

- `results/benchmarks/fast_lio2/botanicgarden_1006-03/dashboard_20260830T094943Z_8d72a2b0` ;
- `results/simulation/px4_lot_a/square_20260830T095019Z_cc67b758` ;
- `results/simulation/px4_lot_a/failsafe_20260830T095104Z_82fd560b`.

Dans les trois résultats, `run_request.json`, `t0_run_manifest.json`, `t0_metrics.json`, `artifacts.json` et `events.jsonl` sont présents, valides et indiquent une exécution terminée. Le smoke test LIO contient dix métriques synthétiques et deux événements ; chaque essai PX4 contient sept métriques et vingt-cinq événements.

L'ATE d'orientation du smoke test LIO vaut environ `158°`. Cette valeur n'est pas interprétable comme une mesure de précision de FAST-LIO2 : une fenêtre de cinq secondes ne permet pas une observation ni un alignement global d'orientation suffisants. Elle sert ici uniquement à vérifier la chaîne d'intégration ; le classement reste fondé sur les passages complets déjà qualifiés.

Docker Desktop a été remis en service en supprimant uniquement cinq sockets temporaires obsolètes de son répertoire d'exécution local. Aucune image, aucun volume, aucune configuration et aucune donnée du projet n'ont été supprimés.

QGroundControl n'était pas ouvert pendant cette régression automatisée. Son observation manuelle du `x500` reste donc une qualification séparée, sans bloquer le lot logiciel T0.2.

## 9. Critères de fin T0.2

| Critère | État |
|---|---|
| Interface commune des runners | Satisfait |
| Adaptateurs FAST-LIO2, Point-LIO et LIO-SAM | Satisfait |
| Runners PX4 carré et perte Offboard | Satisfait, régression SITL réussie |
| Validation serveur des entrées, valeurs et chemins | Satisfait |
| Une seule exécution active | Satisfait |
| Interface alimentée par les contrats | Satisfait |
| Écriture native des contrats T0 | Satisfait sur les trois exécutions intégrées |
| Régression Docker/ROS intégrée | Satisfaite |

## 10. Suite recommandée

T0.3 doit maintenant ajouter l'index des résultats, les filtres, la fiche d'exécution, le rechargement hors ligne de la scène et des courbes, puis la duplication d'une configuration passée. L'observation manuelle du véhicule dans QGroundControl reste inscrite dans la liste de qualification PX4.
