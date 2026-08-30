# ADR-0005 — Tableau de bord comme plan de contrôle des simulations

- Statut : accepté
- Date : 28 août 2026

## Contexte

Le projet va multiplier les datasets, cartes, algorithmes, scénarios PX4/Gazebo, injections de fautes et bancs de traitement. Des lanceurs indépendants sans vue commune rendraient les configurations difficiles à retrouver et les résultats difficiles à comparer.

Le tableau de bord existant pilote déjà les trois LIO, valide leurs principaux paramètres, affiche la télémétrie en direct et calcule les métriques finales. Il ne dispose pas encore d'un contrat générique, d'un historique indexé ni du rechargement des exécutions.

## Décision

Le tableau de bord devient le point d'entrée principal de toutes les simulations et campagnes du projet.

Chaque nouveau module doit fournir :

- une définition de simulation versionnée ;
- un runner headless autonome ;
- un schéma de paramètres validé côté serveur ;
- des couches et métriques visualisables ;
- un manifeste et des artefacts rechargeables ;
- la comparaison avec les exécutions compatibles.

Le tableau de bord orchestre les runners mais ne contient pas leur logique algorithmique. Les répertoires de résultat immuables constituent la source de vérité ; l'index de recherche est un cache reconstruisible.

Le maximum de paramètres expérimentaux utiles doit être exposé. Les paramètres structurels ou de sûreté utilisent des profils validés, des bornes, une confirmation SITL ou un affichage en lecture seule. Aucun chemin ou commande arbitraire n'est accepté depuis le navigateur.

QGroundControl et PX4 conservent leurs responsabilités opérationnelles. Le tableau de bord ne commande jamais directement les moteurs et ne remplace pas les mécanismes d'arrêt ou de failsafe.

## Conséquences

- l'intégration au tableau de bord devient un critère de fin de chaque lot ;
- les essais exploratoires et les campagnes de qualification utilisent la même chaîne de traçabilité mais des statuts distincts ;
- les anciens résultats nécessitent des adaptateurs de lecture, sans migration destructive ;
- le serveur doit évoluer d'une logique LIO spécifique vers des plugins/runners déclaratifs ;
- l'interface doit rester utilisable malgré l'augmentation des paramètres grâce aux niveaux principal, avancé, structurel, sûreté et dérivé ;
- le tableau de bord devient lui-même un composant testé, versionné et soumis à des tests de non-régression.

## Alternatives rejetées

- Conserver un tableau de bord uniquement LIO : ne couvre pas le workflow validé.
- Construire une interface différente pour chaque lot : multiplie les technologies et empêche la comparaison globale.
- Mettre toute la logique de lancement dans le navigateur : surface de sécurité et maintenance inacceptables.
- Rendre l'interface obligatoire pour l'automatisation : empêcherait les tests headless et l'intégration continue.
