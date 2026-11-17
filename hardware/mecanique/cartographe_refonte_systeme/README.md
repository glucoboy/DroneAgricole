# Variante système du cartographe

Ouvrir [la variante A](A/assemblages/Prototype_Cartographe.FCStd) avec
FreeCAD 1.1.3 et Cables Workbench 0.3.7. Conserver toute l'arborescence A
pour résoudre les liens externes. Les sous-assemblages et les fichiers
individuels des 53 parcours se trouvent dans cette copie.

Les fichiers [B](B/assemblages/Reservations_interfaces.FCStd) et
[C](C/assemblages/Reservations_interfaces.FCStd) contiennent des
enveloppes conceptuelles dans le repère d'assemblage A. Utiliser les
coordonnées et les remplacements spécifiés dans
[le contrôle d'encombrement](verification/enveloppes_BC.json).

Consulter les [documents de la variante](docs/INDEX.md), la
[matrice d'interconnexion](verification/matrice_interconnexion.json), le
[schéma fonctionnel](verification/schema_fonctionnel.svg) et le
[registre des architectures](verification/architectures.json).

Pour vérifier la géométrie sauvegardée, lancer les adaptateurs depuis la
racine de DroneAgricole. Le script d'installation demande une copie de
travail neuve correspondant au reçu `A/experiment.json`.

```powershell
$base = 'hardware/mecanique/cartographe_refonte_systeme'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
& $freecad -B "$base/verification/comparer_A.py"
& $freecad -B "$base/verification/controle_mecanique_A.py"
& $freecad -B 'hardware/mecanique/cartographe/verification/refonte_faisceaux/controles_geometrie.py' "$base/A" "$base/verification/validation_A.json" --metadata "$base/verification/roles_validation_A.json" --fresh --without-pairs
```
