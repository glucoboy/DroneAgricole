# Matériel

Ce dossier regroupera les interfaces, schémas, nomenclatures, modèles mécaniques, budgets masse/puissance et procédures de banc.

Les fichiers propriétaires ou exportations lourdes seront référencés par manifeste lorsque leur format ne convient pas à Git.

## État au lancement de SW0

Au 2 septembre 2026, aucune baseline matérielle n'est figée. Le projet dispose
d'une architecture système préliminaire et de candidats capteurs/calculateur,
mais ce dossier ne contient encore ni nomenclature, ni schéma électrique, ni
budget masse/puissance/thermique, ni modèle mécanique, ni résultat de banc.
Toute référence de composant, marge ou performance reste donc **À valider**.

## Prochain chantier matériel

| ID d'action | Travail | Preuve attendue | État |
|---|---|---|---|
| `HW-BASE-001` | établir la nomenclature candidate des deux drones et du banc | composants, versions, disponibilité, alternatives et hypothèses | **À valider** |
| `HW-IF-001` | produire la matrice d'interfaces | puissance, données, horloges, repères, débits et responsabilités PX4/ROS 2 | **À valider** |
| `HW-BUD-001` | calculer les budgets | masse, puissance, énergie, thermique et marges explicitement identifiées | **À valider** |
| `HW-SAFE-001` | analyser les dangers initiaux | pertes d'énergie/liaison, fils, bras, liquide, arrêt sûr et moyens de réduction | **À valider** |
| `HW-BENCH-001` | définir puis réaliser un banc sec instrumenté | démarrage, communications, synchronisation, journalisation et retour à l'état sûr | **À valider** |
| `HW-JET-001` | qualifier le calculateur compagnon | image JetPack `arm64`, rejeu à 1×, CPU, RAM, température et stabilité | **À valider** |

La définition des interfaces et des budgets précède les achats structurants.
Les essais suivent obligatoirement l'ordre simulation, banc sec, eau/traceur,
puis seulement produits autorisés avec protocole validé. PX4 reste responsable
du vol critique ; ROS 2 et le calculateur compagnon fournissent les consignes et
fonctions avancées sans accès direct aux moteurs.
