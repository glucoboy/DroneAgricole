---
name: system-electromechanical-architect
description: Explorer et comparer des architectures électromécaniques FreeCAD avec le moteur DroneAgricole, des contraintes indépendantes et un budget de candidats. Utiliser pour les alternatives de corridors, implantation, connectique ou électronique avant la construction native.
---

# Architecture électromécanique

Suivre la [recette du moteur](../../../electromechanical_engine/README.md). Identifier la source de connectivité, le repère commun, les ancrages porteurs, les enveloppes et les réserves. Préparer `system_model.json` et `design_requirements.yaml` depuis ces autorités puis lancer `freeze` dans un dossier neuf. Garder les données inconnues explicites et conserver l’empreinte du référentiel dans chaque variante.

Décrire les alternatives et leurs hypothèses dans `design_space.json`, fixer le budget et prévoir les corrections déclenchées par défaut. Lancer `explore` pour lire les rejets et réserves avant la génération. Une variante de connectique ou de carte sans preuve reste conditionnelle. Réserver la construction aux copies et demander les mesures natives à `electromechanical-integration`.

Lancer `run` pour une campagne bornée puis `compare` à périmètre identique. Décider à partir des défauts et des valeurs mesurées. Le front de Pareto concerne les candidats évalués et admissibles, avec les objectifs effectivement renseignés. Documenter la donnée qui départagerait une décision encore ouverte.
