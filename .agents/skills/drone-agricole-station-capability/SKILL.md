---
name: drone-agricole-station-capability
description: Ajouter ou refondre une capacité de la station DroneAgricole en C++17/Qt 6, avec contrats, couches applicatives, adaptateurs, composition, UI/CLI, CMake et tests. Utiliser pour une évolution fonctionnelle de la station ; ne pas utiliser pour une modification ROS/PX4 isolée, une tâche matérielle ou une simple correction documentaire.
---

# Capacité de la station DroneAgricole

Faire évoluer la station sans déplacer la logique métier dans l'interface ni créer un noyau technique universel.

## Charger le contexte utile

Lire seulement les sources nécessaires à l'évolution :

- `docs/architecture/ARCHITECTURE_LOGICIELLE.md`, en priorité les sections sur les principes, les modules, la navigation, les contrats, les tests et l'extension d'une capacité ;
- `software/README.md` et les `CMakeLists.txt` concernés pour l'organisation et les commandes effectives ;
- l'implémentation et les tests de la capacité existante la plus proche ;
- `docs/architecture/HLD.md` si le comportement du système change ;
- `docs/VALIDATION_QUALIFICATION.md` seulement si la tâche produit ou modifie une preuve, un statut de qualification ou une campagne.

Ne pas créer de document de décision séparé. Intégrer la justification encore
utile au document vivant concerné.

## Concevoir l'évolution

1. Définir le besoin, le scénario, l'état de maturité et la chaîne de traçabilité `exigence -> composant/algorithme -> test -> résultat`.
2. Rechercher les contrats et modules existants avant d'en ajouter. Une nouvelle fonction ne justifie pas à elle seule une nouvelle destination principale ni une branche métier dans `MainWindow`.
3. Placer les règles métier et algorithmes hors de Qt Widgets. Les services applicatifs dépendent de ports abstraits ; les détails de stockage, processus, réseau, ROS 2 et cartographie restent dans les adaptateurs. La composition choisit les implémentations concrètes.
4. Faire consommer les mêmes services et règles par l'UI et la CLI. Préserver le contexte de navigation et l'observation des traitements actifs.
5. Préserver la lecture des archives et contrats existants. Toute migration ou rupture doit être explicite, testée et documentée.

Maintenir PX4 comme seul responsable du vol critique ; une capacité de station ou ROS 2 ne commande pas directement les actionneurs de vol.

## Implémenter

- Écrire la logique exécutable propriétaire en C++17.
- Construire la structure des écrans au maximum dans les fichiers `.ui`; conserver dans le C++ les widgets spécialisés et le raccordement aux services.
- Matérialiser les frontières par des cibles CMake et des dépendances explicites. Ne pas remettre de sources dans la cible de compatibilité `drone_agricole_core`.
- Étendre les contrats, registres, runners et adaptateurs par capacité plutôt que par cas particuliers dispersés.
- Marquer **À valider** toute valeur, sélection ou limite non qualifiée.

## Vérifier et documenter

Choisir les contrôles proportionnés au changement : tests unitaires de domaine/algorithme, tests de contrat, intégration de la composition, test UI hors écran, fumée d'exécutable et contrôles de dépendances. Lire `CMakePresets.json` avant d'utiliser un profil et lancer les commandes `--preset` depuis la racine du dépôt.

Mettre à jour en place :

- `DOC-SW` pour modules, contrats, dépendances, parcours, tests et maturité ;
- `DOC-HLD` si le scénario ou le comportement système change ;
- `DOC-VAL` uniquement pour les preuves et limites effectivement observées.

Ne pas créer de compte rendu narratif ni de document de décision séparé. À la livraison, distinguer les validations réussies, échouées et non exécutées, et ne jamais extrapoler une qualification entre Windows, Linux, `amd64`, `arm64`, simulation et matériel.
