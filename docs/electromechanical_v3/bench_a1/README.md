# Rejouer le banc XLink V3-A.1

Le [sceau](seal.json) référence deux fichiers FreeCAD, les repères et la
[géométrie de référence](geometry.json), ainsi que les
[contraintes définies pour le banc](authority.json). Les identifiants
`bench:*` désignent des occurrences synthétiques. Les embases, nets et
protections sont des données d’essai numériques. Le [reçu natif](native_receipt.json)
liste les mesures, les empreintes et les limites du contrôle.

Depuis la racine du dépôt, lancer l’inspection dans un répertoire neuf.

```powershell
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$source = 'docs/electromechanical_v3/bench_a1'
$run = ".runtime/v3-a1/bench-replay-$([Guid]::NewGuid().ToString('N'))"
python -B -m electromechanical_engine.v3_native --freecad-python $freecad --source $source --entry model/assemblies/Root.FCStd --work "$run/native" --output "$run/native.json"
```

Le contrôle doit retrouver deux documents chargés, huit liens relatifs
vers `../parts/Assets.FCStd`, neuf poses résolues et les mêmes entrées dans
deux processus de lecture distincts. Les copies sont disponibles dans
`$run/native/staged` et `$run/native/transfer/cad`. Leurs chemins
`model/…` sont les mêmes que dans le sceau. Le rapport natif indique les
empreintes avant et après inspection, le résultat du transfert et l’état
des fichiers sources.

Toute construction sur ce banc exige une copie de travail indépendante
et les contrôles prescrits par l’admission L5 pour l’opération. La lecture
native vérifie la fermeture et l’état de référence. Les résultats
géométriques et électriques d’un candidat sont à mesurer après
construction dans la mission B.1.
