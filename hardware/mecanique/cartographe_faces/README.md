# Cartographe · implantation par faces

Ouvrir [Prototype_Cartographe.FCStd](Candidat/assemblages/Prototype_Cartographe.FCStd)
avec FreeCAD 1.1.3 et Cables Workbench 0.3.7. Garder l'arborescence de
la copie pour résoudre les liens externes. Les gabarits accouplés et
la retenue locale sont dans le groupe InterfacesFaces de SA07.

Le [F31 sous P66](Candidat/verification/candidats/F31_Sous_P66.FCStd)
s'ouvre séparément. Sa pose est donnée dans le même repère. Consulter la
[matrice des variantes](verification/decision_faces.json) pour les
conditions d'interprétation.

Les vues à échelle commune sont dans [exports/vues](exports/vues).
Les documents de la variante sont accessibles depuis [l'index](docs/INDEX.md).
Les chemins d'entrée et de preuve figurent dans le [manifeste](manifest.json).

Depuis la racine du dépôt, reproduire les mesures et les vues sur les
natifs sauvegardés.

```powershell
$b = 'hardware/mecanique/cartographe_faces'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
& $freecad -B "$b/verification/comparer_faces.py"
& $freecad -B "$b/verification/controle_sauvegarde.py"
& $freecad -B 'hardware/mecanique/cartographe/verification/refonte_faisceaux/controles_geometrie.py' "$b/Candidat" "$b/verification/validation_natifs.json" --metadata "$b/verification/roles_validation.json" --fresh --without-pairs
& $freecad -B "$b/verification/visualiser_faces.py"
```
