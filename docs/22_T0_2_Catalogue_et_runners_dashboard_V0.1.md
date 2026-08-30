# DOC-22 — T0.2 — Catalogue et runners du tableau de bord

- Version : V0.1
- Date : 30 août 2026
- Statut : candidat
- Références : DOC-19, DOC-20, DOC-21, ADR-0005

## 1. Objectif

Le lot T0.2 remplace le lancement spécialisé LIO du tableau de bord par une interface commune, pilotée par les contrats T0.1. Il conserve les trois benchmarks existants et ajoute les deux essais PX4 du lot A, sans autoriser le navigateur à fournir une commande système arbitraire.

Le périmètre exécutable est désormais :

| Domaine | Simulation | Variante | Runner approuvé |
|---|---|---|---|
| Localisation | Benchmark LiDAR–IMU | FAST-LIO2 | `lio_fastlio2` |
| Localisation | Benchmark LiDAR–IMU | Point-LIO | `lio_pointlio` |
| Localisation | Benchmark LiDAR–IMU | LIO-SAM | `lio_liosam` |
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

La validation indépendante du moteur Docker a produit les résultats suivants :

| Contrôle | Résultat |
|---|---|
| Contrats et adaptateurs T0.1 | 8 tests réussis |
| Résolution et sécurité des runners T0.2 | 7 tests réussis |
| Compilation des modules Python | Réussie |
| Analyse syntaxique JavaScript | Réussie |
| Analyse syntaxique PowerShell | Réussie |
| Validation de la configuration Compose | Réussie |
| Essai interactif du panneau LIO/PX4 | Réussi, aucune erreur JavaScript |

L'essai interactif confirme :

- les trois variantes FAST-LIO2, Point-LIO et LIO-SAM ;
- les scénarios PX4 carré et perte Offboard ;
- la sélection du profil `botanicgarden_velodyne_xsens` ;
- la génération des paramètres LIO et PX4 ;
- le masquage des sélecteurs dataset en mode PX4 ;
- l'activation du lancement uniquement pour une sélection valide.

## 8. Validation Docker restante

La construction des nouvelles images et la régression ROS complète n'ont pas pu être exécutées le 30 août 2026, car Docker Desktop échoue avant le démarrage du moteur sur son socket Windows local `sailor-ingest.sock`. Le fichier appartient à l'installation Docker hors workspace et reste verrouillé ; aucune réinitialisation destructive de Docker n'a été tentée.

Après redémarrage de Windows ou réparation de Docker Desktop, la qualification à exécuter est :

1. construire `drone-agricole/lio-dashboard:0.3.0` et `drone-agricole/px4-ros:0.2.0` ;
2. lancer le tableau de bord avec `tools/visualization/start_fastlio_dashboard.ps1` ;
3. rejouer le smoke test LIO de 5 s ;
4. rejouer le carré PX4 SITL avec QGroundControl en observation ;
5. rejouer la perte Offboard et confirmer l'atterrissage PX4 ;
6. vérifier les cinq fichiers contractuels natifs dans chaque nouveau résultat.

Le statut restera **candidat** jusqu'à réussite de cette régression intégrée, puis pourra devenir **opérationnel préliminaire**.

## 9. Critères de fin T0.2

| Critère | État |
|---|---|
| Interface commune des runners | Satisfait |
| Adaptateurs FAST-LIO2, Point-LIO et LIO-SAM | Satisfait |
| Runners PX4 carré et perte Offboard | Satisfait côté code et tests purs |
| Validation serveur des entrées, valeurs et chemins | Satisfait |
| Une seule exécution active | Satisfait |
| Interface alimentée par les contrats | Satisfait |
| Écriture native des contrats T0 | Satisfait côté code et tests purs |
| Régression Docker/ROS intégrée | À valider après réparation de Docker Desktop |

## 10. Suite recommandée

Après la régression intégrée T0.2, T0.3 doit ajouter l'index des résultats, les filtres, la fiche d'exécution, le rechargement hors ligne de la scène et des courbes, puis la duplication d'une configuration passée.
