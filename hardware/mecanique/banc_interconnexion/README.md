# Banc FreeCAD synthétique L2

Ouvrir [Banc_Interconnexion.FCStd](assemblages/Banc_Interconnexion.FCStd) avec
FreeCAD et Cables Workbench. Les composants transparents exposent les contacts et
les quatre conducteurs. Les deux volumes verts représentent les réservations
de retrait. Activer les objets « Accès outillage » dans l'arbre pour voir leurs
volumes. L'identité logique des occurrences est portée par leurs propriétés
« Interconnexion L2 ». Les fils sont attachés aux sommets de terminaux natifs
et la gaine est attachée aux repères de sortie.

Depuis la racine du dépôt, fournir le rapport JSON de validation C++ L2 du banc
(`configuration_id = banc-l2`) qui contient `native_plan`. Utiliser un dossier de
sortie neuf et le Python embarqué de FreeCAD.

```powershell
$report = '.runtime/l2/rapport-banc.json'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
python -B hardware/mecanique/banc_interconnexion/verification/freecad_adapter.py `
    run $report .runtime/l2/native/rejeu --freecad $freecad
```

`run` sauvegarde le natif, le rouvre et le recalcule dans un autre processus,
applique les défauts en mémoire, puis écrit `native_l2.json`. Les deux journaux
et les mesures de chaque processus restent dans le répertoire de sortie.
Le [manifeste](manifest.json) référence le natif et sa preuve de réouverture.
