---
name: drone-agricole-validation-evidence
description: Concevoir, exécuter ou consigner une validation DroneAgricole avec protocole, critères, artefacts T0, preuves reproductibles, conclusion et traçabilité. Utiliser pour les campagnes, essais, qualifications et résultats ; ne pas utiliser pour une évolution fonctionnelle sans travail de validation.
---

# Preuves de validation DroneAgricole

Produire une conclusion interprétable et strictement limitée au périmètre réellement testé.

## Charger le contexte utile

Lire seulement les sources adaptées au domaine testé :

- `docs/VALIDATION_QUALIFICATION.md`, au minimum les sections « Objet et frontières », « Progression des essais » et « Règles de preuve », puis la campagne et le registre de résultats concernés ;
- le document d'architecture concerné parmi `DOC-HLD`, `DOC-SW`, `DOC-MEC` et `DOC-ELEC` pour l'exigence et le composant vérifiés ;
- `configs/visualization/schemas/` et `configs/README.md` pour une exécution utilisant les contrats T0 ;
- `results/README.md` pour le rangement des résultats ;
- les tests, configurations et preuves existants les plus proches du cas traité.

Ne pas créer de document de décision ni de rapport narratif séparé.

## Cadrer avant d'exécuter

Identifier :

- l'exigence, le composant ou algorithme et le risque couverts ;
- l'environnement exact, l'architecture, les versions et la révision ;
- les entrées, configurations, calibrations, modèles et leurs empreintes ;
- le protocole, les défauts injectés, les répétitions et le critère d'acceptation approuvé ;
- les données réservées à l'évaluation et exclues de la prédiction ;
- les artefacts attendus et la condition d'arrêt sûre.

Si une information manque, la signaler **À valider**. Ne pas inventer un seuil et ne pas transformer une mesure exploratoire en exigence.

## Respecter la progression de sûreté

Suivre l'ordre défini dans `DOC-VAL` : tests et contrats, rejeu/simulation, PX4 SITL et défauts, banc matériel, vols progressifs, puis eau/traceur et enfin produits autorisés sous protocole approuvé. Un niveau réussi ne compense pas l'absence du précédent.

PX4 conserve l'autorité du vol critique. Une preuve cartographique, logicielle ou SITL n'autorise ni un vol réel ni une mission de traitement.

## Produire une preuve reproductible

Pour les nouvelles exécutions logicielles, utiliser et valider les contrats T0 applicables : `run_request.json`, `t0_run_manifest.json`, `t0_metrics.json`, `artifacts.json` et `events.jsonl`. Déclarer toute conversion d'unité, temps, repère ou format. Échouer explicitement lorsqu'une empreinte, une calibration, une vérité terrain, une image ou une entrée attendue ne correspond pas.

Conserver les sorties volumineuses, rosbags, captures et journaux dans `results/`, `datasets/`, `.runtime/` ou le répertoire `verification/` du sous-système ; ne versionner que les configurations, manifestes, empreintes et synthèses légères autorisés.

Conclure avec l'une des catégories du projet : `conforme`, `non conforme`, `préliminaire` ou **À valider**. Mentionner les anomalies et échecs, pas seulement les métriques favorables.

## Consolider

Mettre à jour `DOC-VAL` en place avec les conditions d'interprétation, les mesures synthétiques, le lien vers la preuve, les limites et la date. Mettre aussi à jour la matrice `exigence -> composant/algorithme -> test -> résultat`; actualiser le document d'architecture uniquement si son état ou ses critères changent.

Ne jamais généraliser un résultat à un autre OS, une autre architecture, une autre configuration, un autre dataset, au matériel ou au vol réel. À la livraison, lister ce qui a été exécuté, le résultat, la preuve produite et ce qui reste **À valider**.
