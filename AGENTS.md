# Instructions de projet

Ce fichier s'applique à l'ensemble du workspace.

## Périmètre et sources de vérité

- Travailler exclusivement dans `D:\ProjetGuillaume\DroneAgricole` pour tout artefact durable du projet.
- Conserver la documentation principale en français.
- Faire évoluer en place les cinq documents vivants définis dans `docs/INDEX.md` : `DOC-HLD`, `DOC-SW`, `DOC-MEC`, `DOC-ELEC` et `DOC-VAL`.
- Intégrer une décision et sa justification utile dans le document vivant concerné. Ne pas créer de document de décision, de compte rendu narratif, d'étude ou de livraison séparé.
- Réserver les `README.md` locaux aux instructions d'utilisation du répertoire ou de l'artefact voisin. Les manifestes, configurations, schémas et preuves de vérification restent autorisés.
- Employer les états **Planifié**, **Implémenté**, **Qualifié** et **À valider** selon `docs/INDEX.md`. Ne jamais présenter une hypothèse, une sélection candidate ou une valeur préliminaire comme une exigence figée.
- Ne pas versionner les rosbags, datasets, modèles lourds, secrets, clés ou résultats volumineux.

## Invariants d'architecture et de sûreté

- PX4 assure le vol critique, les boucles d'asservissement et les mécanismes de sécurité. ROS 2 fournit des consignes de haut niveau et des fonctions avancées ; aucun composant propriétaire ne commande directement les moteurs.
- Écrire toute logique exécutable propriétaire en C++17. Les fichiers déclaratifs et d'infrastructure restent autorisés hors C++ lorsqu'ils ne contiennent pas de logique métier.
- Développer les interfaces desktop avec Qt 6 Widgets et placer le maximum de leur structure dans des fichiers `.ui` éditables.
- Séparer présentation Qt, services applicatifs, domaine, algorithmes et adaptateurs techniques par des dépendances de compilation explicites. L'UI et la CLI partagent les services et règles applicatives.
- Ajouter une capacité par ses contrats, modules et tests plutôt que par des branches métier dans `MainWindow`, les pages Qt, la CLI ou un noyau technique universel.
- Favoriser des environnements Docker reproductibles pour `amd64` et `arm64`. Une qualification obtenue sur une architecture, un système ou un banc ne vaut pas pour une autre cible.
- Les essais de pulvérisation suivent l'ordre : simulation, banc, eau/traceur, puis seulement produits autorisés et protocole validé.

## Validation et traçabilité

- Maintenir la chaîne `exigence -> composant/algorithme -> test -> résultat` dans les documents vivants et les preuves techniques concernées.
- Exécuter des validations proportionnées aux fichiers, comportements et cibles modifiés. Une modification documentaire seule n'impose pas une compilation complète ; une modification logicielle doit être compilée et testée sur les chemins concernés.
- Signaler en fin de tâche les validations exécutées et leurs résultats, ainsi que celles non exécutées et leur raison.
- Ne déclarer **Qualifié** qu'avec des critères d'acceptation et des preuves reproductibles sur la cible annoncée. Distinguer une exécution réussie de la finalisation correcte de son résultat.
- Les essais suivent la progression définie dans `DOC-VAL` ; un niveau ne compense jamais l'absence de validation du niveau précédent.

## Politique agentique

- Commencer par inspecter l'état Git et préserver toutes les modifications existantes non liées à la tâche.
- Considérer une tâche comme complexe lorsqu'elle traverse plusieurs sous-systèmes, modifie une décision structurante, touche à la sûreté ou comporte plusieurs investigations indépendantes.
- Pour une tâche complexe : analyser et découper le problème, paralléliser les investigations indépendantes, attribuer des fichiers distincts aux agents, consolider les analyses avant l'implémentation, puis demander une review indépendante.
- Ne pas créer de sous-agents pour les tâches simples.
- Ne considérer une modification terminée qu'après les validations pertinentes et la mise à jour des documents vivants, contrats, manifestes ou preuves qu'elle affecte.
