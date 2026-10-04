# Utiliser les fichiers de fabrication candidats

Lire [export_manifest.json](export_manifest.json) pour les SHA, contrôles
et limites de l'instantané, [contraintes_fabrication.json](contraintes_fabrication.json)
pour stack/vias/perçages/process, et [assemblage_candidate.json](assemblage_candidate.json)
pour la BOM et les points ouverts. `manufacturing_ready=false` : les fichiers
ne constituent pas une libération de fabrication ou d'assemblage.

`exports_provisoires_20261002/` contient onze tracés Gerber et le job,
deux Excellon PTH/NPTH avec cartes/tableau outils, la netlist IPC-D-356
et ses alias complets, ainsi que les CPL136SMD et141positions totales.
Conserver les fichiers ensemble et comparer leur SHA au manifeste avant
utilisation. La BOM candidate contient les DNP avec quantité0 ; les CPL
les excluent. Les LM76003 à trous EP figurent dans le CPL SMD.

Depuis le répertoire KiCad parent, après DRC/revue actuels :

```powershell
./verification/export_fabrication_candidate.ps1
& 'C:/Program Files/KiCad/10.0/bin/python.exe' verification/verify_fabrication_exports.py
```

Après une modification du PCB, refaire les vérifications et la revue avant
l'export : la recette refuse un PCB différent de la preuve. Les coordonnées
Gerber/Excellon/CPL utilisent l'origine auxiliaire de CAO(50,50)mm avec
X vers la droite et Y opposé au Y de CAO ; les rotations/pin1 restent à
approuver par l'assembleur. L'IPC natif déclare sa propre unité0,0001inch ;
son CSV d'alias évite de confondre les noms abrégés avec les réseaux complets.
Diamètres des fichiers CAO, outils production et trous finis/tolérances
doivent être distingués dans la réponse fabricant. Le contour nominal
126×80mm se lit sur la centreligne Edge.Cuts ; la boîte du job inclut le trait.
