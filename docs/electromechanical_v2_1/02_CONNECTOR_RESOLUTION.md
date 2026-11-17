# Résolution des interfaces du cartographe V2.1

Cette fiche décrit la recette et les champs des preuves de `T-CARTO-V21-CONNECTORS`.
La décision de réception et ses limites sont dans [DOC-VAL](../VALIDATION_QUALIFICATION.md#preuve-connectique-v21).

## Sources et couverture

La passe porte sur le prototype sans dock du dossier H-01. L2 réconcilie
BOM, registres, sources KiCad et empreintes des axes avec le modèle GO3A
et la couverture GO3B. Le contrôle croisé vérifie les clés dans les deux
sens, le sens de chaque axe, les cordons partagés et les 21 motifs hors axe.
La recherche L1 part du dépôt et des PDF, plans, photos et STEP disponibles.
Elle consulte ensuite les publications fabricant, puis les catalogues et
documents secondaires. Les plans permettent d’instruire des alternatives
et l’inspection CAO sert à mesurer les gabarits applicables. Le registre
trace les recherches, localisateurs, dates, révisions, fiabilité et
empreintes des documents locaux. Les références distantes sans fichier
brut local gardent une empreinte nulle.
[Inventaire des extrémités](../verification/v21_connector_inventory.csv) ·
[Registre des sources](../verification/v21_connector_sources.json) ·
[Catalogue L1](../verification/v21_connector_research_catalog.json)

| Preuve disponible dans l’inventaire | Couverture sur 142 côtés |
|---|---:|
| Côté de liaison et port documentés | 142 (100 %) |
| Référence candidate d’équipement | 134 (94,4 %) |
| Révision documentaire de référence | 54 (38,0 %) |
| Référence d’embase dans la définition CA01 | 15 (10,6 %) |
| Référence candidate de fiche / de contact | 30 (21,1 %) / 25 (17,6 %) |
| Mention documentaire de contacts | 125 (88,0 %) |
| Pose d’équipement relue dans FreeCAD | 108 (76,1 %) |
| Réservation de face / bout d’axe | 39 (27,5 %) / 100 (70,4 %) |
| Gabarit historique partiel d’accouplement / étude partielle de retrait | 5 (3,5 %) / 2 (1,4 %) |
| Révision et lot physiques, chaîne de repères de connecteur complète ou volumes de service qualifiés | 0 (0 %) |

Les colonnes `device_mount_frame` et `reservation_*` portent des observations
de la maquette. Les cellules des corps, plans de contact physiques et
enveloppes de service restent ouvertes quand la définition applicable manque.
L1 résout six questions documentaires et laisse treize questions de réception
en `UNKNOWN`. Les 120 côtés pertinents pour la réception restent `INCONCLUSIVE`.
Les 22 côtés `OUT_OF_SCOPE` conservent leur fonction ou historique dans le
catalogue. Le périmètre de réception et le périmètre des axes sont distincts.

## Cas à instruire pour la réception

| Interface | Observation disponible | Donnée qui conditionne la suite |
|---|---|---|
| W12/F12 | Le port prévu est TELEM1 et l’axe actif aboutit vers GPS2 dans la CAO RC02. Le plan nominal documente TX, RX et GND. | Identifier la révision de la porteuse, orienter le plan des cavités et confirmer le verrou et son accès. |
| W24.A/F24A | La définition vise GPIO_07 et GND. Le port Debug a une autre fonction. | Obtenir la configuration de porteuse et le pinmux, puis mesurer la pose et le retrait près de P75/F13A. |
| W31/F31 | La vue fabricant PM08-CAN et le plan CAN1 précisent le rôle des signaux. La photo PM08 ne numérote pas les cavités. | Identifier l’embase PM08 utilisée, les contacts H/L/GND et l’accès commun à CAN1 et F35 avec outil. |
| W16/F16 | Les variantes Basler droite et coudée documentent des rayons statiques différents. FreeCAD relit le STEP de la fiche Up USBFireWire candidate, avec cinq paires dégagées pour le corps moulé. | Confirmer le cordon, la visserie, la course d’extraction, le rayon en mouvement et le volume de suspension. Le gabarit de retrait recoupe la caméra et le pack et le gabarit d’outil recoupe le pack. |
| W40/W41 | Le plan JBD A01 présente une divergence de nomenclature J2/J3 dans la documentation UART. | Identifier le lot et le port, vérifier la référence électrique TTL, l’isolation, la fiche USB-B et l’accès du déport de diagnostic. |
| W24.C, RF, BMS, FAN et LED | Familles et géométries candidates indexées. | Établir la référence de l’extracteur CSI, les genres et plans RF, les variantes BMS, FAN et LED et les accès propres à leur montage. |

Les termes de recherche, références et questions restantes sont détaillés
dans le [registre des sources](../verification/v21_connector_sources.json).

## Rejeu hors matériel

Depuis la racine, compiler les deux moteurs C++17 avec Qt 6 puis utiliser
FreeCAD 1.1.3 et Cables Workbench 0.3.7. Le dossier de sortie est neuf.

```powershell
$work = '.runtime/v21-connecteurs-rejeu-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
$qt = 'C:/msys64/ucrt64'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
cmake -S technical_research_engine -B "$work/l1" -G Ninja -DCMAKE_PREFIX_PATH=$qt
cmake --build "$work/l1"
ctest --test-dir "$work/l1" --output-on-failure
cmake -S interconnection_engine -B "$work/l2" -G Ninja -DCMAKE_PREFIX_PATH=$qt
cmake --build "$work/l2"
ctest --test-dir "$work/l2" --output-on-failure

$catalog = 'docs/verification/v21_connector_research_catalog.json'
foreach ($question in (Get-Content -Raw -Encoding UTF8 $catalog | ConvertFrom-Json).questions) {
    & "$work/l1/technical_research_core.exe" --root . --store "$work/recherche" `
        --catalog $catalog --issue $question.issue_id --refresh submit | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Échec de $($question.issue_id)" }
}
& "$work/l2/interconnection_core.exe" inspect-cartographe --root . --output "$work/interfaces.json" | Out-Null
& "$work/l2/interconnection_core.exe" validate interconnection_engine/examples/banc_l2.json `
    --output "$work/banc.json" | Out-Null
python -B hardware/mecanique/banc_interconnexion/verification/freecad_adapter.py `
    run "$work/banc.json" "$work/banc-natif" --freecad $freecad
python -B -m electromechanical_engine.connector_native "$work/cartographe" --freecad $freecad
python -B interconnection_engine/tests/check_cartographe_receipts.py `
    "$work/interfaces.json" "$work/cartographe/connector_native.json" `
    "$work/recherche" "$work/l1/technical_research_core.exe"
```

Le contrôle des boîtes L2 distingue corps accouplés, retrait et accès au
verrou. Le cas droit/coudé du banc utilise des valeurs synthétiques.
Le contrôle CAO W16/B utilise le STEP fournisseur et des paramètres de
service candidats. Les 106 bouts WireFlex relus n’ont aucun ancrage de
contact natif constaté. Le détail des contrôles, entrées et empreintes se
trouve dans la [preuve de test](../verification/v21_connector_tests.json).
