# Cartographe — intégration mécanique FreeCAD V0.1

La CAO de travail est désormais organisée en [pièces et assemblages sous hardware/mecanique](../../mecanique/cartographe/README.md). Les fichiers sous `results/` cités ci-dessous constituent l'archive initiale ; les données de sources et réserves restent applicables.

6 septembre 2026 — **À valider : étude d'implantation, sans qualification physique**.
Architecture active : [DOC-MEC](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md).

## Fichiers de travail locaux

- [Assemblage du drone FCStd](../../../results/freecad/cartographe_v0_1/Cartographe_Integration_V01.FCStd).
- [Station au sol FCStd](../../../results/freecad/cartographe_v0_1/StationSol_Cartographe_V01.FCStd).
- [Vue d'ensemble](../../../results/freecad/cartographe_v0_1/Cartographe_vue_ensemble.png).
- [Charge utile isolée](../../../results/freecad/cartographe_v0_1/Cartographe_charge_utile.png).
- [Vue de face](../../../results/freecad/cartographe_v0_1/Cartographe_vue_front.png).
- [Station au sol](../../../results/freecad/cartographe_v0_1/Station_sol.png).
- [STL de prototypes](../../../results/freecad/cartographe_v0_1/STL_prototypes/).
- [STEP des pièces spécifiques](../../../results/freecad/cartographe_v0_1/STEP_pieces/).
- [Contrôle des exports](../../../results/freecad/cartographe_v0_1/controle_exports.json).
- [Implantation et contrôles](../../../results/freecad/cartographe_v0_1/integration_scene.json).

Les modèles lourds, sources fabricants et images restent dans `results/`, hors Git.
Les fichiers FCStd sont autonomes pour consulter la géométrie importée. Conserver
les sources originales pour remplacer une révision ; leurs droits ne sont pas
transférés au projet. Les [empreintes](empreintes_sources.csv) identifient les copies.

## Lecture de la maquette

Repère d'étude : X longitudinal, Y transversal, Z vers le haut, origine au
plateau central inférieur. La désignation « avant » est une convention de CAO,
**À valider** avec le repère PX4 et les extrinsèques des capteurs.

- Gris : châssis et équipements fabricants ; les couleurs ne constituent pas une
  spécification de matière.
- Orange : pièces spécifiques imprimables. Les opérations de construction CSG
  restent dans l'arbre : primitives, unions et soustractions natives éditables.
- Volumes simples légendés « enveloppe » : référence ou détail encore inconnu.
- Groupe `Reserves`, masqué par défaut : champ Airy, volumes balayés des hélices,
  accès batterie, câbles et ventilation. Afficher ses objets individuellement.
- Table `Parametres` : **paramétrage partiel** de l'étude. Elle ne pilote pas tous
  les entraxes et toutes les positions. Une modification impose de revoir les
  perçages, les composants associés et les contrôles ; aucun recalage automatique
  complet n'est revendiqué.

La CAO Holybro contient des équipements illustratifs non retenus : PM06 avec
visserie dédiée et petit mât RTK. Les objets 120–133 et 168–180 restent dans
l'arbre, masqués et exclus des contrôles de configuration. Ne pas les réafficher
comme équipements montés. Le socle de bureau du Jetson est également exclu du
montage de vol ; la source complète est conservée dans les réserves.

## Pièces imprimables

Dimensions nominales en mm et quantités **À valider**. Chaque STL représente
une pièce ; multiplier les exemplaires indiqués. Les STEP conservent la même
orientation de fabrication. Légères différences de quelques centièmes sur les
diamètres tessellés : consulter le solide FreeCAD pour les cotes nominales.

| ID | Pièce | Qté | Encombrement nominal | Orientation du STL |
|---|---|---:|---|---|
| P01 | Platine commune avec équerre caméra et renforts | 1 | 190 ×112 ×25 | Platine retournée, face plane sur plateau |
| P02 | Entretoise capteurs, passage M3 | 4 | Ø12 ×34 | Axe vertical |
| P03 | Adaptateur Jetson ventilé | 1 | 128 ×108 ×4 | À plat |
| P04 | Entretoise Jetson, passage M2.5 | 4 | Ø7 ×10 | Axe vertical |
| P05 | Bac batterie ouvert à sangles | 1 | 184 ×90 ×11 | Fond sur plateau |
| P06 | Platine auxiliaire avec dégagements | 1 | 130 ×118 ×3 | À plat |
| P07 | Support inférieur RTK | 1 | 108 ×65 ×3 | À plat |
| P08 | Entretoise RTK, passage M3 | 4 | Ø9 ×20 | Axe vertical |
| P09 | Interface antenne sur mât | 1 | Ø48 ×4 | À plat |
| P10 | Retenue de câble à collier | 4 | 20 ×10 ×4 | À plat |
| P11 | Boîtier de base RTK au sol | 1 | 120 ×90 ×35 | Fond sur plateau |
| P12 | Couvercle de base RTK | 1 | 120 ×90 ×3 | À plat |

Un plateau utile de 200 ×200 mm est une hypothèse de préparation, **À valider**
avec les marges, la jupe/bordure et la machine. Le profil filament/machine n'est
pas choisi. Vérifier supports éventuels des perçages horizontaux de P01,
compensation des trous, précision, délaminage, fluage et température avant usage.
Les STL ne sont pas des fichiers G-code et n'ont pas été imprimés ni tranchés.

Visserie métallique, rondelles et écrous requis : les trous sont des passages,
pas des filetages imprimés. Les vis M3 Airy et Basler ne doivent pas talonner
leurs taraudages ; profondeur et longueur utile à vérifier sur la révision reçue
(dessin Basler : M3 profondeur 4 mm). Ne pas déduire la longueur de vis uniquement
de l'épaisseur de la pièce imprimée. Les sangles de batterie sont textiles et
indépendantes du bac ; celui-ci ne suffit pas à retenir la batterie.

P01 est un prototype de géométrie/rigidité : une platine métallique demeure une
option si la tenue, la température ou la stabilité de calibration l'exige.
**P04 reste à reprendre avant impression fonctionnelle** : après retrait du socle,
deux entretoises rencontrent encore des éléments périphériques sous la carte
NVIDIA (volumes communs 13,5968 et 6,3761 mm³). Identifier et repositionner ces
accessoires, ou revoir les entretoises, sans supprimer arbitrairement la géométrie.
P09 et P10 nécessitent de terminer la fixation sur le matériel réel. P11 est
une maquette de boîtier avec ouvertures : aucune étanchéité ni classe IP revendiquée.

## Modèles recherchés et provenance

| Équipement | Résultat de recherche et usage |
|---|---|
| Holybro X650 | STEP officiel `x650-frame-2025-0825.stp`, châssis, train, moteurs, accessoires et visserie ; configuration adaptée selon `MEC-INT-001` et DOC-MEC |
| Pixhawk 6X / base v2A | STEP officiel `pixhawk6x-REV8-basev2-A-rc08.stp`, ensemble importé ; module seul aussi archivé, non ajouté en double |
| Jetson Orin Nano | STEP officiel `P3766-P3768SKU4-P3767ENVELOPE.stp` ; révision/Super à confirmer, socle de bureau retiré de la configuration |
| simpleRTK2B | STL historique du dépôt officiel ArduSimple ; révision actuelle Budget et connecteurs **À valider** |
| Airy | STEP `Airy_3D_FOV.STEP` trouvé chez Robotopian ; coques physiques et champ séparés. Fabricant : ZIP proposé derrière formulaire ; révision de cette copie **À valider** |
| Basler | Archive fabricant `Basler ace 2 USB3`, copie publique 51camera ; PDF IB027653 révision 01, mai 2019, dimensions rapprochées du dessin officiel Front II. Téléchargement direct Basler soumis à formulaire, non rempli |
| Objectif, batterie, petites cartes, radios, antennes, matériel opérateur | Enveloppes provisoires ; références absentes ou non arrêtées, pas de CAO fabricant exacte revendiquée |
| Hélices | Volumes de rotation Ø381 mm, plan et marges **À valider** ; pas de géométrie détaillée Gemfan |
| SSD | Réservation 2280 masquée ; vérifier format, dissipateur et si déjà représenté dans la CAO NVIDIA avant d'additionner |

Sources consultées le 6 septembre 2026 :

- [Holybro X650 — téléchargements](https://docs.holybro.com/drone-development-kit/x650-development-kit/download).
- [Holybro baseboards — téléchargements](https://docs.holybro.com/autopilot/pixhawk-baseboards/download).
- [NVIDIA — centre de téléchargement](https://developer.nvidia.com/embedded/downloads), entrée « Jetson Orin Nano Developer Kit 3D CAD STEP model ».
- [ArduSimple — mécanique du dépôt officiel](https://github.com/ardusimple/simpleRTK2B/tree/master/Mechanical).
- [RoboSense — ressources Airy](https://www.robosense.ai/en/resources-161), [manuel](https://robosense-robotics.github.io/product-manual/en/Airy/).
- [Robotopian — copie du modèle Airy](https://robotopian.com/products/robosense-airy-lidar).
- [Basler — référence sélectionnée](https://docs.baslerweb.com/a2a4096-30ucbas), [bibliothèque CAO](https://www.baslerweb.com/en/downloads/documents/2304387854/).
- [51camera — copie publique de l'archive Basler](https://51camera.com.cn/show-17-1509-1.html).

Aucune coordonnée utilisateur n'a été transmise aux formulaires fournisseurs.
