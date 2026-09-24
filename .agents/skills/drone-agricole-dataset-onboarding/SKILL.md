---
name: drone-agricole-dataset-onboarding
description: Évaluer, sélectionner et intégrer un dataset DroneAgricole avec provenance, droits, empreintes, capteurs, repères, calibrations, vérité terrain, manifeste, configuration et recette reproductible. Utiliser pour l'onboarding ou l'évolution d'un dataset ; ne pas utiliser pour un simple rejeu d'un dataset déjà intégré.
---

# Intégration d'un dataset DroneAgricole

Rendre un dataset exploitable et reproductible sans contaminer la prédiction par les références d'évaluation.

## Charger le contexte utile

Lire :

- `datasets/README.md` pour la politique de stockage ;
- l'entrée concernée dans `datasets/manifests/catalogue_datasets.yaml`, qui prévaut sur les résumés documentaires ;
- la section « Registre des datasets » de `docs/VALIDATION_QUALIFICATION.md` et le portefeuille de données de `docs/architecture/ARCHITECTURE_LOGICIELLE.md` ;
- le profil voisin sous `configs/datasets/`, la définition voisine sous `configs/visualization/datasets/` et leurs schémas seulement si l'intégration logicielle les concerne ;
- l'adaptateur, le runner, les tests et la recette de téléchargement les plus proches seulement si ces éléments doivent être créés ou modifiés.

Ne pas créer de document de décision séparé. Intégrer la justification encore
utile au document vivant concerné.

## Évaluer avant d'acquérir

Établir, sans supposer les informations absentes :

- source officielle, version ou commit, URL stable et conditions d'utilisation ;
- finalité dans le projet et représentativité réelle ;
- taille, format, sous-ensemble utile et empreinte publiée ou calculée ;
- capteurs, topics ou champs, unités, horloges, timestamps et repères ;
- intrinsics, extrinsics, synchronisation et état des calibrations ;
- nature, précision et indépendance de la vérité terrain ;
- CRS horizontal, datum vertical ou mention explicite qu'il est inconnu pour les données géoréférencées ;
- recette de préparation reproductible et limites connues.

Marquer **À valider** toute licence, calibration, convention ou qualité non confirmée. Un dataset terrestre peut qualifier une chaîne de perception sans qualifier la dynamique de vol ni le montage final des capteurs.

Ne pas télécharger de données volumineuses, accepter des conditions, demander un accès ou contacter un fournisseur sans demande explicite. Ne jamais ajouter au Git les archives, rosbags, images, modèles ou dérivés lourds.

## Séparer prédiction et évaluation

Définir une allowlist des données autorisées pour la prédiction et réserver la vérité terrain, les poses publiées, annotations ou autres références à l'évaluation. Documenter les exclusions dans le manifeste et vérifier qu'elles ne déterminent ni la zone d'intérêt, ni les paramètres, ni la sortie prédite.

Déclarer chaque transformation d'unité, de temps, de repère, de format ou de message. Refuser explicitement les entrées dont l'identité, l'empreinte ou la calibration ne correspond pas au profil attendu.

## Intégrer proportionnellement

Mettre à jour l'entrée machine-lisible de `datasets/manifests/catalogue_datasets.yaml`. Selon le périmètre demandé, compléter ensuite :

- un profil versionné sous `configs/datasets/` ;
- une définition et les capacités sous `configs/visualization/datasets/` ;
- une recette reproductible légère sous `tools/` ;
- les contrats, adaptateurs, runners et tests C++17 nécessaires.

Ne créer que les éléments réellement utilisés. Les fichiers déclaratifs et d'infrastructure peuvent rester hors C++ ; toute logique métier propriétaire est en C++17.

## Vérifier et consolider

Contrôler schémas, empreintes, fichiers requis, topics/champs, temporalité, repères, calibrations et isolation de la vérité terrain. Commencer par un sous-ensemble borné avant une exécution complète, puis appliquer le skill de validation si le travail doit produire une preuve qualifiante.

Distinguer explicitement les états : catalogué, sélectionné, téléchargé, inspecté, intégré et qualifié. Mettre à jour `DOC-VAL` pour le registre, les preuves et les limites ; mettre à jour `DOC-SW` seulement si la couverture logicielle ou les contrats changent. Ne pas créer de compte rendu séparé et ne jamais conclure « qualifié » sur la seule présence des fichiers ou la réussite d'une inspection structurelle.
