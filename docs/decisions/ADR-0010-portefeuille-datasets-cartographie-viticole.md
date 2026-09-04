# ADR-0010 — Portefeuille de datasets pour la cartographie viticole

- Statut : proposé
- Date : 3 septembre 2026

## Contexte

BotanicGarden a permis de qualifier l'adaptation ROS 1 vers ROS 2 et de comparer FAST-LIO2, Point-LIO et LIO-SAM. Il ne représente cependant ni un vignoble, ni des rangs, ni des terrasses agricoles. Le projet doit maintenant développer la chaîne hors ligne qui transforme des acquisitions géoréférencées en rangs, corridors, graphe de parcelle et trajectoires de traitement.

Les relevés LaMole/Grospoli sont très proches de l'environnement cible : fortes pentes, murs de pierre, terrasses et rangs irréguliers. Ils sont toutefois constitués principalement de produits cartographiques déjà reconstruits, et leur accès est soumis à autorisation. Aucun dataset unique disponible immédiatement ne couvre à la fois ce cas difficile, une vérité terrain de rangs et des flux LiDAR–IMU bruts.

## Décision proposée

Conserver BotanicGarden uniquement comme baseline de rejeu LIO et utiliser un portefeuille distinct pour B3/B4 :

1. LaMole/Grospoli comme cas difficile prioritaire pour terrasses, pentes, murs et rangs irréguliers, dès obtention écrite de l'accès et des droits ;
2. EscaYard comme baseline quantitative publique grâce aux orthomosaïques, nuages 3D et positions RTK de ceps ;
3. VineLiDAR comme baseline géométrique publique de nuages UAV-LiDAR RGB multi-date ;
4. le futur dataset physique du projet comme seule source capable de qualifier finalement la chaîne complète avec les capteurs, le drone, le bras et les conditions d'exploitation réels.

Créer un importeur géospatial C++17 commun fondé sur GDAL/PROJ et PDAL, avec des profils minces par dataset. Ne pas convertir les cartes statiques en faux flux ROS et ne jamais fabriquer une IMU, une trajectoire ou un timestamp absent.

La carte et la mission restent produites hors ligne sur la station. Le compagnon du drone de traitement reçoit une carte allégée et une mission approuvée, construit son corridor local et fournit uniquement des consignes haut niveau à PX4. PX4 conserve l'autorité de vol critique et les failsafes.

## Conséquences

- le développement de la carte devient représentatif du domaine sans perdre le benchmark LIO déjà acquis ;
- l'accès LaMole ne bloque pas le démarrage, car EscaYard et VineLiDAR sont téléchargeables ;
- les contrats doivent accepter des produits géospatiaux statiques et déclarer explicitement les modalités absentes ;
- GDAL/PROJ et PDAL doivent être ajoutés et qualifiés dans les images `amd64` et `arm64` ;
- une annotation indépendante des rangs, murs et extrémités reste nécessaire ;
- les données, modèles et résultats volumineux restent hors Git ;
- les seuils algorithmiques, marges de navigation et estimations de charge restent **À valider**.

## Alternatives écartées

- Remplacer BotanicGarden dans tous les usages : LaMole ne fournit pas les flux LiDAR–IMU nécessaires au benchmark LIO.
- Attendre l'autorisation LaMole avant de coder : cela place un délai externe sur le chemin critique.
- Utiliser uniquement le LiDAR régional à 1–2 m : utile pour le relief, mais trop grossier pour démontrer des corridors inter-rang précis.
- Entraîner immédiatement un réseau neuronal : les annotations et la séparation multi-parcelle/multi-saison ne sont pas encore suffisantes pour mesurer sa généralisation.
- Générer des lignes parallèles idéales : contraire à `MAP-FUN-007`, qui impose la géométrie réelle des rangs.

## Validation attendue

La décision pourra passer à l'état accepté après :

1. import reproductible d'un sous-ensemble public EscaYard ou VineLiDAR ;
2. rapport de qualité portant CRS, emprise, fichiers, droits et checksums ;
3. extraction mesurée d'au moins un rang courbe et d'un corridor ;
4. génération d'une trajectoire 3D conforme au corridor dans un scénario SITL ;
5. clarification des droits et de l'inventaire LaMole/Grospoli, ou décision explicite de poursuivre sans ce jeu.
