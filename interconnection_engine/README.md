# Catalogue et validation d’interconnexion L2

Compiler depuis la racine avec CMake, Qt 6 Core et un compilateur C++17.
Les tests CLI utilisent Python 3. Le moteur s’exécute indépendamment de
FreeCAD. Les chemins des preuves locales sont relatifs à la racine courante.

```powershell
$build = '.runtime/l2/build'
cmake -S interconnection_engine -B $build -G Ninja -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $build
ctest --test-dir $build --output-on-failure
$bin = "$build/interconnection_core.exe"
$fixture = 'interconnection_engine/examples/banc_l2.json'
& $bin mates $fixture embase
& $bin validate $fixture --output .runtime/l2/rapport-banc.json
& $bin validate $fixture --state equipement-tourne
& $bin reconcile --root . --output .runtime/l2/rapprochement.json
& $bin inspect-cartographe --root . --output .runtime/l2/interfaces-cartographe.json
```

`validate` renvoie `0` pour `PASS`, `2` pour `FAIL` et `3` pour
`INCONCLUSIVE`. Une erreur d’entrée ou d’exécution donne `1`. `mates` est un
criblage et `reconcile` publie les associations et les anomalies constatées.
La sortie JSON va sur stdout, avec publication atomique supplémentaire par
`--output`. Le [banc FreeCAD](../hardware/mecanique/banc_interconnexion/README.md)
utilise le rapport nominal et sauvegarde un nouvel assemblage dans le dossier
de rejeu.

`inspect-cartographe` vérifie le rapprochement L2 et le gel GO3A/GO3B.
`line_interfaces` et `axes` donnent les associations directes et inverses.
`port_record_id` identifie une entrée documentaire de GO3A. Le port fonctionnel
peut être commun à plusieurs lignes. Un code 0 indique un rapport documentaire
finalisé avec réception `INCONCLUSIVE`. Pour le croiser avec les observations
FreeCAD et les rapports L1, suivre la
[recette V2.1](../docs/electromechanical_v2_1/02_CONNECTOR_RESOLUTION.md).

## Entrées

Le dossier L2 porte `schema_version: 1.0.0` et contient `model`, un dossier
[L0 V2](../docs/electromechanical_v2/DATA_CONTRACTS.schema.json), ainsi que les
champs d’intégration décrits ci-dessous. Le mode `SYNTHETIC_BENCH` accepte
les hypothèses de banc avec preuve dédiée. Le mode `PROTOTYPE_CANDIDATE`
conserve l’applicabilité fournisseur ouverte et contrôle l’empreinte des
documents locaux invoqués comme preuves. Une URL seule est une piste.

| Champ | Rôle |
|---|---|
| `catalog.parts` | Identité et révision sous forme de `Value` L0, origine, rôle et propriétés. Les rôles permettent de distinguer fiche, embase, contacts, câble, cordon OEM, coque, verrou, presse-étoupe et reprise d’effort. Le genre `PERMANENT` représente un raccord indémontable dans le catalogue. |
| `catalog.pairs` | Références et révisions des deux pièces, déclaration explicite d’accouplement et table de cavités. |
| `interfaces` | Une relation entre une extrémité de câble, sa fiche ou terminaison et le port exigé. Les rôles d’accessoires requis sont indépendants de la liste des pièces installées. Les repères d’équipement, de montage, d’accouplement et de sortie sont référencés dans L0. Le +Z local de sortie pointe hors de la fiche. |
| `interfaces[].receptacle_pinout` | `Value` L0 en unité `1` contenant le plan cavité d’embase → numéro de broche. La table d’accouplement embase → fiche reste dans `catalog.pairs[].cavity_map`. |
| `interfaces[].physical_geometry` | Références `receptacle_frame_id` et `plug_frame_id`, puis `receptacle_body`, `plug_body`, `extraction_sweep` et `tool_access_envelope`. Chaque volume porte `geometry_class` et `dimensions` (`Value` L0 en mm). |
| `cable_parts`, `signal_groups` | Sélections de câble et spécifications additionnelles en `Value` L0. Groupes `DIFFERENTIAL`, `MULTIDROP` ou `COAX` référençant les circuits distincts. Les conducteurs, bornes, retours et blindages sont dans le graphe L0. |
| `geometry` | Obstacles, tolérances, couverture déclarée et boîtes d’enveloppe `[xmin, ymin, zmin, xmax, ymax, zmax]` en mm. Le contrôle des boîtes est borné aux orientations alignées du banc. |
| `research_issue_ids` | Questions L1 à suivre. `--research RAPPORT` est répétable et conserve la conclusion, les inconnues et l’empreinte de chaque rapport. Une recherche résolue ne transforme pas une référence candidate en matériel identifié. |

`validate` calcule les poses et la continuité pour l’état demandé. Il traite
un dossier en lecture seule et réévalue toutes ses interfaces, y compris après
un changement de repère. Les verdicts électrique, compatibilité et géométrie
sont distincts. `continuity` permet de suivre chaque conducteur jusqu’aux
contacts et signaux. `candidate_bom` garde les quantités, références et preuves.

Dans `physical_geometry`, les boîtes des corps sont locales à leurs repères.
Le dossier exprime le retrait (+Z), `extraction_sweep.travel` en mm et
`tool_access_envelope.lock_access_point` en mm dans le repère d’accouplement.
Les deux dernières valeurs portent leurs preuves L0. Les boîtes des corps
atteignent le datum d’accouplement, celle de la fiche atteint la sortie et
celle de l’outil atteint le point d’actionnement sur la fiche. Le test de
dégagement par boîtes porte sur le banc aux orientations alignées. Les classes
`SUPPLIER`, `MEASURED`, `CONSERVATIVE_ENVELOPE`, `APPROXIMATION` et `UNKNOWN`
conservent l’origine des dimensions. Une approximation sans intersection
produit un contrôle de réception `INCONCLUSIVE`.

## Rejouer les recherches L1

Compiler le [moteur L1](../technical_research_engine/README.md), puis utiliser
un répertoire de rapports neuf. Les commandes ci-dessous réutilisent son
exécutable existant et les sources gelées.

```powershell
$l1bin = '.runtime/technical-research-l1/build/technical_research_core.exe'
$reports = '.runtime/l2/recherche'
New-Item -ItemType Directory -Force $reports | Out-Null
$l1 = @('-B','-m','technical_research_engine','--executable',$l1bin,'--root','.','--store',$reports)
$f12 = 'interconnection_engine/examples/recherche_f12.json'
$f16 = 'docs/electromechanical_v2/L1_CARTOGRAPHE.json'
python @l1 --catalog $f12 submit F12-ACTIVE-GEOMETRY --output "$reports/f12-geometrie.json"
python @l1 --catalog $f12 submit F12-TELEM1-REVISION --output "$reports/f12-revision.json"
python @l1 --catalog $f16 submit F16-MOUNTED-BEND-RADIUS --output "$reports/f16-rayon.json"
& $bin validate interconnection_engine/examples/cartographe_candidats.json `
    --research "$reports/f12-geometrie.json" --research "$reports/f12-revision.json" `
    --research "$reports/f16-rayon.json" --output .runtime/l2/cartographe-candidat.json
```

Le candidat cartographe attendu est `INCONCLUSIVE`. Voir les
[preuves L2](../docs/electromechanical_v2/L2_RESULT.md).
