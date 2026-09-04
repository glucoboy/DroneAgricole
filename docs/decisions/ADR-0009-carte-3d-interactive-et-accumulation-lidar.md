# ADR-0009 — Carte 3D interactive et accumulation LiDAR bornée

- Statut : accepté
- Date : 2 septembre 2026
- Complète : ADR-0008

## Contexte

La vue opérationnelle Qt affiche actuellement les trajectoires et le dernier
nuage `/cloud_registered` avec une projection orthographique simplifiée. Son
centre et son échelle sont recalculés à chaque rafraîchissement. La caméra
saute donc lorsque l'étendue des données évolue, les variations en altitude
sont difficiles à lire et chaque nouveau nuage remplace le précédent. Cette
représentation ne permet pas d'observer la construction progressive d'une
carte LiDAR.

## Décision

`TrajectoryView` devient une carte 3D interactive native Qt 6. Elle conserve
une caméra explicite, avec :

- rotation orbitale au bouton gauche ;
- déplacement dans le plan de la carte au bouton droit, au bouton central ou
  avec `Maj` + bouton gauche ;
- zoom à la molette ;
- cadrage des données et vue de dessus accessibles depuis des contrôles
  déclarés dans `main_window.ui` ;
- grille métrique adaptative, axes, échelle, légende, départ et position
  courante des trajectoires.

Le service C++ ROS 2 accumule les messages `/cloud_registered` dans une carte
de voxels. Un voxel déjà observé n'ajoute pas un doublon. La carte en mémoire,
le nombre de points transmis et la réponse JSON restent bornés. Lorsque le
plafond est atteint, la taille du voxel est doublée et tous les représentants
déjà conservés sont réindexés. Cette compaction adaptative libère de la place
sur toute l'étendue de la carte ; elle ne doit jamais privilégier le début du
trajet en refusant simplement les points suivants. La taille effective du
voxel et le nombre de compactions sont exposés dans les métriques.

Le réglage initial de 8 cm par voxel, le plafond de 250 000 voxels mémorisés et
les 16 000 points affichés sont **À valider** sur les séquences longues et sur
la cible Jetson.

L'accumulation est remise à zéro au début de chaque exécution. Elle reste une
donnée d'observation : elle ne commande ni le vol ni le traitement. PX4
conserve les fonctions critiques de vol et les failsafes.

## Conséquences

- la caméra ne dépend plus implicitement de chaque nouvel instantané après
  une interaction opérateur ;
- la carte LiDAR se complète pendant le rejeu au lieu d'afficher uniquement
  le dernier scan ;
- le rendu utilise la profondeur et l'altitude pour distinguer les points,
  avec un halo contrasté autour des trajectoires ;
- la mémoire, le transport local et le coût de dessin restent contrôlés ;
- une exécution longue conserve des représentants spatiaux du début, du
  milieu et de la fin, même après une ou plusieurs compactions ;
- les archives LIO historiques ne gagnent pas artificiellement un nuage qui
  n'a pas été enregistré : cette décision concerne le direct ;
- les métriques `map_point_count`, `cloud_frame_count`,
  `map_voxel_size_m` et `map_compaction_count` rendent l'accumulation
  observable et testable.

## Alternatives rejetées

- Conserver uniquement le dernier scan : ne produit pas une carte exploitable
  pendant la progression du drone.
- Accumuler sans voxel ni limite : consommation mémoire non maîtrisée et
  transport JSON croissant sans borne.
- Réintroduire une carte Web : contraire à l'architecture desktop Qt 6.
- Dépendre immédiatement de VTK ou RViz : alourdit le déploiement Windows et
  réduit l'éditabilité de l'interface sans nécessité démontrée à ce stade.
