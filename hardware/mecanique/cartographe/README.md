# Cartographe — assemblages FreeCAD

La description d'architecture et la BOM sont consolidées dans
[DOC-MEC](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md) ; l'énergie et
les réseaux dans [DOC-ELEC](../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md).
Ce fichier reste le guide local d'ouverture et de maintenance des assemblages.

Configuration active : `SA02_Energie_EchangeRapide` avec connecteur SBS X-75A
et `SA05_Capteurs_Isoles`. Les variantes `SA02_Energie` et `SA05_Capteurs`
restent des archives de conception. Les contacts locaux de la variante capteurs sont corrigés ; les limites
des contrôles géométriques sont décrites dans DOC-MEC. L'avionique active est
empilée sur les deux plateaux OEM avec P06 et P20–P22. Voir `DOC-MEC`, `DOC-ELEC` et les fichiers de `verification/`.

Référence de travail CAO : ouvrir `assemblages/Systeme_Cartographie.FCStd` pour le drone et la station au sol, ou `assemblages/Drone_Cartographe.FCStd` pour le drone seul.

Chaque sous-système est un document séparé utilisant `App::Link`. Les pièces fabriquées conservent leurs arbres CSG et expressions. Les feuilles de paramètres copiées sont propres à chaque référence : elles ne pilotent pas globalement toutes les cotes.

Les repères des pièces conservent ceux de l'intégration initiale et ne sont pas systématiquement centrés. Les liens répétés portent les décalages. Le châssis X650 reste un ensemble acheté avec son arbre fabricant. Les enveloppes provisoires restent **À valider**.

`manifest.json` décrit les références et occurrences. Sources et exports initiaux sont copiés ici. Les anciens documents dans `results/freecad/cartographe_v0_1/` restent une archive. Régénérer les exports après modification.

Les [sources, dimensions et réserves](../../cad/cartographe_v0_1/README.md) restent applicables : deux contacts aux entretoises Jetson, fixations PX4/antenne et qualification physique **À valider**.

Traçabilité : `MEC-ARC-001` → manifeste des pièces et assemblages →
`verification/hierarchie.json`. Les contrôles historiques copiés concernent la
géométrie initiale ; aucun essai physique n'est impliqué.

Les exports actualisés sont dans `exports/iteration_20260915/` (P16) et
`exports/iteration_20260916/` (P06, P20–P22). Pour examiner la pile seule,
ouvrir `sous_assemblages/SA03_Avionique.FCStd`. Conserver toute l'arborescence
avec les pièces liées. Les fichiers de `verification/sauvegardes_20260915/`
servent à retrouver l'état précédent ; ne pas les ouvrir comme configuration active.
