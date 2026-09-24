# Matériel

Répertoire de travail par défaut pour le matériel. L'architecture courante est
tenue dans [DOC-MEC](../docs/architecture/ARCHITECTURE_MECANIQUE.md) et
[DOC-ELEC](../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md). La CAO suit
la [hiérarchie pièces et assemblages](mecanique/README.md), appliquée au
[cartographe](mecanique/cartographe/README.md).

Ce dossier regroupera les interfaces, schémas, nomenclatures, modèles mécaniques, budgets masse/puissance et procédures de banc.

Les fichiers propriétaires ou exportations lourdes seront référencés par manifeste lorsque leur format ne convient pas à Git.

## État actuel

Une nomenclature candidate, une première intégration FreeCAD et des bilans
préliminaires de masse, batterie, connecteur et isolation sont disponibles.
Aucune baseline matérielle n'est qualifiée : schéma électrique fabricable,
faisceau, pesée, thermique, rigidité, vibrations et résultats de banc restent
**À valider**. `DOC-MEC` et `DOC-ELEC` sont les références à mettre à jour ; les
notes locales conservent les calculs et preuves historiques.

## Prochain chantier matériel

Les choix, alternatives, budgets et états sont consolidés dans `DOC-MEC` et
`DOC-ELEC`. La [CAO FreeCAD](mecanique/cartographe/README.md) et son
[`manifest.json`](mecanique/cartographe/manifest.json) portent les références et
placements ; les JSON de `verification/` portent les contrôles détaillés.

| ID d'action | Travail | Preuve attendue | État |
|---|---|---|---|
| `HW-BASE-001` | fermer la nomenclature des deux drones et du banc | composants, versions, disponibilité, alternatives et hypothèses | cartographe préliminaire ; traitement **À valider** |
| `HW-IF-001` | produire la matrice d'interfaces | puissance, données, horloges, repères, débits et responsabilités PX4/ROS 2 | **À valider** |
| `HW-BUD-001` | qualifier les budgets | masse, puissance, énergie, thermique et marges mesurées | calculs préliminaires ; mesures **À valider** |
| `HW-SAFE-001` | analyser les dangers initiaux | pertes d'énergie/liaison, fils, bras, liquide, arrêt sûr et moyens de réduction | **À valider** |
| `HW-BENCH-001` | définir puis réaliser un banc sec instrumenté | démarrage, communications, synchronisation, journalisation et retour à l'état sûr | **À valider** |
| `HW-JET-001` | qualifier le calculateur compagnon | image JetPack `arm64`, rejeu à 1×, CPU, RAM, température et stabilité | **À valider** |

La définition des interfaces et des budgets précède les achats structurants.
Les essais suivent obligatoirement l'ordre simulation, banc sec, eau/traceur,
puis seulement produits autorisés avec protocole validé. PX4 reste responsable
du vol critique ; ROS 2 et le calculateur compagnon fournissent les consignes et
fonctions avancées sans accès direct aux moteurs.
