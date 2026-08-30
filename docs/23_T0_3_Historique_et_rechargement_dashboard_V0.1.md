# DOC-23 — T0.3 — Historique et rechargement du tableau de bord

- Version : V0.1
- Date : 30 août 2026
- Statut : opérationnel préliminaire
- Références : DOC-20, DOC-21, DOC-22, ADR-0005

## 1. Objectif

T0.3 rend les résultats LIO et PX4 consultables depuis le tableau de bord sans relancer leurs algorithmes ni modifier les archives existantes. Le lot couvre :

- l'indexation des manifestes natifs et historiques ;
- les filtres par domaine, dataset, scénario, algorithme, date, statut et tag ;
- une fiche d'exécution avec métriques, événements et artefacts ;
- le rechargement hors ligne de la scène et d'une courbe disponible ;
- la duplication contrôlée d'une configuration enregistrée.

La comparaison multi-exécutions et l'export de rapports restent réservés à T0.4.

## 2. Source de vérité et index

Les répertoires sous `results/` restent l'unique source de vérité. `software/visualization/result_history.py` reconstruit un cache mémoire à partir de :

- `t0_run_manifest.json`, `t0_metrics.json`, `artifacts.json` et `events.jsonl` pour les exécutions natives T0 ;
- `run_manifest.json` et `metrics.json` pour les benchmarks LIO historiques ;
- `result.json` pour les essais PX4 du lot A.

Un résultat LIO possédant un manifeste mais aucune métrique reste indexé. Son état est reconstruit comme `abandoned` lorsque l'archive ne fournit aucun état terminal, et ses métriques sont marquées `unavailable`. Cette règle empêche les échecs anciens de disparaître de l'historique.

Les identifiants FAST-LIO2, Point-LIO, LIO-SAM et BotanicGarden sont aussi inférés depuis les chemins et le rosbag d'entrée pour les archives antérieures au tableau de bord. Aucun fichier historique n'est réécrit.

Chaque résultat reçoit un identifiant public stable dérivé de son chemin relatif. Le navigateur ne fournit jamais de chemin absolu. Toute résolution d'artefact reste confinée au répertoire du résultat, lui-même situé sous le workspace.

Le cache est reconstruit au premier accès, sur demande explicite et après une nouvelle exécution. Entre ces opérations, une durée de vie de cinq minutes évite une nouvelle lecture complète à chaque filtre ou ouverture de fiche.

## 3. API de lecture

Le serveur expose trois routes en lecture seule :

| Route | Rôle |
|---|---|
| `GET /api/results` | index, filtres, pagination et facettes |
| `GET /api/results/{result_id}` | fiche complète normalisée |
| `GET /api/results/{result_id}/replay` | scène et courbe hors ligne |

L'index accepte jusqu'à deux cents résultats par page. Les facettes sont calculées sur l'index complet afin que les choix restent disponibles après application d'un filtre. Les erreurs d'une archive sont isolées et remontées sans masquer les résultats valides.

## 4. Interface utilisateur

Le panneau « Résultats enregistrés » ajoute :

- une recherche libre par run, dossier, simulation, variante, dataset ou séquence ;
- neuf contrôles couvrant tous les filtres T0.3 ;
- la reconstruction manuelle de l'index ;
- une liste chronologique avec aperçu des métriques ;
- une fiche détaillée avec état, provenance, métriques, événements et disponibilité des artefacts ;
- les actions « Recharger scène et courbes » et « Dupliquer cette configuration ».

Le mode hors ligne suspend uniquement le rafraîchissement de la scène et des courbes. La connexion au serveur, l'état PX4 et l'état du runner restent suivis. « Revenir au direct » restaure immédiatement la visualisation ROS 2.

## 5. Rechargement hors ligne

### 5.1 LIO

Le serveur relit le rosbag `estimate/` avec `rosbags`, extrait `/Odometry` et `/gt_poses`, associe les poses par timestamp puis aligne l'estimation en SE(3). Il transmet au navigateur :

- la trajectoire estimée alignée ;
- la vérité terrain ;
- la courbe d'ATE cumulée ;
- les métriques et événements normalisés de la fiche.

La lecture ne démarre aucun nœud LIO et ne rejoue aucun dataset. Les trajectoires sont sous-échantillonnées uniquement pour l'affichage.

Les anciens résultats n'archivent pas le nuage LiDAR affiché en direct. T0.3 recharge donc la scène de trajectoires, mais aucun nuage n'est inventé. L'ajout d'un artefact de nuage décimé pour les nouvelles exécutions reste **À valider** dans un lot ultérieur.

### 5.2 PX4

Le parcours est reconstruit depuis les origines et consignes `target_ned` des événements. Les points sont ramenés à l'origine puis convertis NED vers ENU. La scène affiche le parcours et la dernière pose ; la courbe présente l'altitude cible. Aucun PX4 SITL, agent DDS ou runner Offboard n'est redémarré.

## 6. Duplication d'une configuration

La duplication est proposée uniquement lorsqu'une requête ou un manifeste de tableau de bord contient les entrées et paramètres nécessaires. Elle recharge :

- la simulation et la variante ;
- le dataset et la séquence, lorsqu'ils sont requis ;
- le profil capteurs/configuration ;
- les paramètres enregistrés.

L'action ne lance jamais automatiquement la simulation. L'utilisateur doit vérifier les valeurs puis utiliser le bouton normal de lancement. Les archives trop anciennes pour garantir une duplication fidèle conservent leur fiche, mais le bouton reste désactivé.

## 7. Validation

L'image qualifiée est :

| Image | Identifiant | Plateforme |
|---|---|---|
| `drone-agricole/lio-dashboard:0.4.0` | `sha256:2d9c0e3c2dde9ef57c3caa0a3addb82aa4f3dc4eb938a92b84a5b5724e9fb770` | `linux/amd64` |

| Contrôle | Résultat |
|---|---|
| Tests T0.1, T0.2 et T0.3 dans Docker | 21 réussis |
| Résultats indexés | 59 |
| Résultats LIO / PX4 | 52 / 7 |
| États reconstruits | 53 terminés, 2 annulés, 4 abandonnés |
| Archives invalides | 0 |
| Filtre BotanicGarden + FAST-LIO2 | 39 résultats |
| Fiche FAST-LIO2 native | 10 métriques, 2 événements |
| Rechargement smoke FAST-LIO2 | 45 poses estimées, 49 poses de référence, 45 points de courbe |
| Rechargement carré PX4 | 6 points de parcours et 6 points de courbe |
| Interface servie par Docker | filtres, fiches, duplication, deux rechargements et retour au direct réussis |
| Console JavaScript | aucune erreur |

Le test graphique a aussi rechargé le passage FAST-LIO2 complet retenu pour la comparaison finale. Après construction de l'index, l'ouverture d'une fiche et l'application d'un filtre ont chacune demandé environ une demi-seconde sur le poste de développement. Ces temps restent indicatifs et **À valider** sur Jetson si cette fonction y est déployée.

## 8. Critères de fin T0.3

| Critère | État |
|---|---|
| Index reconstruisible depuis les archives | Satisfait |
| Archives natives, historiques et incomplètes visibles | Satisfait |
| Filtres domaine/dataset/scénario/algorithme/date/statut/tags | Satisfait |
| Fiche complète | Satisfaite |
| Métriques et événements rechargeables | Satisfait |
| Scène et courbe LIO sans recalcul | Satisfait pour les trajectoires ; nuage non archivé |
| Scène et courbe PX4 sans relance SITL | Satisfait |
| Duplication sans lancement automatique | Satisfaite lorsque la configuration exacte est archivée |
| Non-régression T0.1/T0.2 | Satisfaite |

## 9. Suite recommandée

T0.4 doit vérifier la compatibilité des exécutions, comparer métriques, paramètres et versions, superposer les trajectoires compatibles, puis ouvrir ou exporter le rapport associé. La porte T0 pourra alors être fermée avec une comparaison LIO reproductible depuis l'historique.
