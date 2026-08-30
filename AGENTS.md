# Instructions de projet

Ce fichier s'applique à l'ensemble du workspace.

- Travailler exclusivement dans `D:\ProjetGuillaume\DroneAgricole` pour tout artefact durable du projet.
- Conserver la documentation principale en français.
- Ne jamais présenter une valeur préliminaire comme une exigence figée ; utiliser **À valider**.
- Préserver la séparation de sûreté : PX4 assure le vol critique, ROS 2 fournit des consignes et fonctions avancées.
- Maintenir la traçabilité `exigence -> composant/algorithme -> test -> résultat`.
- Ne pas versionner les rosbags, datasets, modèles lourds, secrets, clés ou résultats volumineux.
- Avant de modifier une décision structurante, ajouter ou mettre à jour un ADR dans `docs/decisions/`.
- Favoriser des environnements Docker reproductibles pour `amd64` et `arm64`.
- Les essais de pulvérisation suivent l'ordre : simulation, banc, eau/traceur, puis seulement produits autorisés et protocole validé.
