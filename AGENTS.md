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
- Faire évoluer les fichiers de pièces, sous-assemblages et assemblages en place, sans suffixe de date ou de révision supplémentaire. Utiliser Git pour les retours arrière ; les petits natifs CAO explicitement suivis peuvent être versionnés avec leurs dépendances, les sources fabricant lourdes et exports restant exclus.

## Méthodologie de décision

- Avant toute tâche non triviale, lire le [cadrage courant de DOC-HLD](docs/architecture/HLD.md#methodologie) et appliquer les [22 préceptes](docs/architecture/HLD.md#preceptes) selon leurs déclencheurs, leur ordre et leurs règles de conflit. Ils constituent la source canonique ; ne pas en créer une copie dans les skills.
- Cadrer avant de concevoir ou déléguer : problème utile, impact/urgence, observations disponibles, hypothèses réfutables, réversibilité et coût d'erreur, action minimale, budget et arrêt, signal de résultat et prochaine décision. Adapter l'effort au risque ; ne pas imposer une fiche aux petites corrections réversibles.
- Consigner seulement la décision et l'apprentissage réutilisables dans le document vivant concerné. Référencer les manifestes, contrats et preuves qui possèdent les données ; ne pas reconstruire une vérité critique à partir d'un résumé.
- Reprendre la priorité et les actions de [DOC-VAL §14](docs/VALIDATION_QUALIFICATION.md#recentrage), puis les écarts de l'[audit des préceptes](docs/VALIDATION_QUALIFICATION.md#audit-preceptes). Une nouvelle capacité ou optimisation doit justifier son utilité pour la priorité courante, ou expliciter le changement de priorité.

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
