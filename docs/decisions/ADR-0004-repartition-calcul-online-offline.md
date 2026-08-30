# ADR-0004 — Répartition des calculs entre drones et station

- Statut : accepté
- Date : 28 août 2026

## Contexte

Le catalogue algorithmique du projet décrit les fonctions nécessaires, mais ne distingue pas encore assez clairement les calculs indispensables pendant un vol des traitements pouvant être différés. Sans cette frontière, chaque nouveau module risque d'être conçu simultanément pour le PC, le cartographe et le drone agricole, avec des contraintes incompatibles et des interfaces instables.

## Décision

Maintenir une station de traitement distincte sur le plan logique, même si elle partage le même PC que QGroundControl pendant le prototype.

- Le cartographe embarque l'acquisition, les diagnostics, l'enregistrement, une odométrie LIO locale et le contrôle de couverture.
- La station produit hors ligne la trajectoire optimisée, la carte 3D/sémantique, le graphe de parcelle, la confiance et les missions simulées.
- La carte devient utilisable uniquement après une porte de qualité et une approbation explicite.
- Le drone agricole embarque uniquement les fonctions nécessaires à l'exécution autonome : vérification de carte, localisation, perception locale, corridor, planification locale, interface PX4, supervision et traitement.
- Les modèles IA sont entraînés sur la station et exécutés seulement en inférence optimisée sur le drone. Aucun modèle IA ne ferme directement une boucle de vol ou une chaîne de sécurité.
- PX4 reste l'autorité de vol selon les ADR précédents.

Les échanges entre phases utilisent cinq paquets versionnés : `SurveyMissionPackage`, `SurveyRunPackage`, `VineyardMapPackage`, `TreatmentMissionPackage` et `MissionReportPackage`.

## Conséquences

- le calculateur du cartographe peut être dimensionné pour le temps réel utile, sans absorber toute la reconstruction finale ;
- les traitements lourds peuvent être rejoués et améliorés sans refaire le vol ;
- le drone agricole reste autonome après chargement de sa carte et de sa mission ;
- chaque algorithme peut être développé derrière un contrat stable et validé séparément ;
- une étape explicite de transfert et d'approbation est ajoutée entre cartographie et traitement ;
- l'opérateur doit gérer les versions de carte, de mission et les rapports, ce qui augmente la discipline de configuration mais améliore la sûreté et la traçabilité.

## Alternatives rejetées

- Construire la carte finale uniquement à bord du cartographe : impose la puissance maximale en vol, réduit les possibilités de reprise et rend le contrôle qualité plus difficile.
- Tout traiter sur la station, sans LIO ni contrôle qualité à bord : ne permet pas au cartographe de détecter une acquisition inutilisable ni de disposer d'une odométrie locale complémentaire.
- Faire dépendre le drone agricole d'un calcul distant en temps réel : la liaison radio deviendrait une dépendance de mission et de sécurité.
- Développer d'abord tous les algorithmes puis définir leurs interfaces : crée des dépendances aux formats propres de chaque bibliothèque et rend les comparaisons coûteuses.

## Validation

Le porteur du projet a validé le workflow du DOC-19 le 28 août 2026. Les choix d'implémentation encore marqués **À valider** feront l'objet d'ADR séparés après benchmark.
