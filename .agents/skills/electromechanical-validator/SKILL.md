---
name: electromechanical-validator
description: Revalider indépendamment un candidat FreeCAD sauvegardé et interpréter ses preuves électromécaniques. Utiliser pour un verdict sur un candidat généré et la comparaison de rapports liés au même référentiel gelé.
---

# Validation électromécanique

Prendre le référentiel gelé depuis la source de campagne, séparément du candidat. Suivre la [recette du moteur](../../../electromechanical_engine/README.md) et exécuter `validate` avec un nouveau dossier de preuves. La commande vérifie les empreintes du reçu et remesure le natif dans un processus FreeCAD neuf. Conserver le code retour, le rapport et l’empreinte du natif inspecté.

Lire les défauts par code, objet et mesure. Une spline sans borne certifiée, un port fournisseur inconnu ou un mouvement non mesuré restent ouverts. L’inclusion dans une enveloppe et le contact fonctionnel nécessitent une autorisation dans les exigences gelées. Utiliser les projections pour cibler une vérification, puis revenir aux mesures.

Pour comparer, vérifier le périmètre, la méthode, les valeurs absentes et les deux verdicts. Une validation géométrique vaut pour les seuls critères et configurations exécutés. Les essais physiques gardent leur propre protocole.
