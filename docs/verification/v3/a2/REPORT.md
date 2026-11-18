# V3-A.2 — Recette des preuves d’interfaces et d’ancrages

Le verdict et les limites d’admission sont consignés dans
[DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-a2).
Le [registre](evidence_register.json) couvre les huit issues du graphe A
sur le prototype sans dock. La branche A2 part de `2b83b17`, qui intègre
A et A.1. L’investigation s’arrête après la confrontation des notices
et la lecture des natifs disponibles. L’obtention d’un dossier de lot,
de datums d’interface et d’ancrages signés motive une nouvelle décision.

## Rejeu natif

Depuis la racine, avec le Python embarqué de FreeCAD 1.1.3 sur Windows
amd64. Exécuter dans un nouveau dossier privé sous `.runtime`.

```powershell
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$run = ".runtime/v3-a2/rejeu-$([Guid]::NewGuid().ToString('N'))"
python -B -m electromechanical_engine.v3_a2_native --freecad-python $freecad --work "$run/native"
```

La recette vérifie la fermeture de l’actif contre le reçu A et les
fermetures de H03-A, H03-B et de la consolidée contre le manifeste GO3B.
Ce dernier indique les emplacements des archives locales. La recette
essaie également la copie `.runtime/v21-go3b/<cas>/cad`. Un témoin
GO3B sans fermeture disponible et conforme est étiqueté `NOT_RUN`.
Les observations sont écrites dans `measurements.json`, avec un reçu de
copie et un journal par cas. Les documents ouverts sont privés et en
lecture seule. La comparaison du témoin `reference` porte sur les
octets du gel, dont les auxiliaires du reçu A.

Comparer les résultats et les contrôles IF-03 à IF-07 au
[reçu natif publié](cad_interface_measurements.json). Les versions,
entrées, commandes des criblages et limites numériques sont portées
par le reçu. IF-03 et IF-07 reposent sur les mesures natives
indépendantes. IF-04 à IF-06 rejouent le criblage historique sur une
copie du gel avec des gabarits et, pour IF-06, des routes d’essai en
mémoire. Pour la comparaison des poses, utiliser le repère XYZ
de l’assemblage et les matrices 4×4 lues par lignes. L’origine d’une
face ORCH est une mesure de représentation. Le choix des enveloppes
TTL/USB de criblage est **À valider** avec les terminaisons et les
outils du lot.

## Rapprochement des notices

Comparer les empreintes des archives indiquées par le registre fabricant
V2.1 et le contrat UART, puis consulter les localisateurs dans le
[registre A2](evidence_register.json). Pour rejouer le contrôle du PDF
Jiabaida de la variante LiFePO₄ A.1, exécuter les commandes suivantes
avec accès réseau au CDN du fabricant.

```powershell
$docsRun = "$run/notices"
New-Item -ItemType Directory -Path $docsRun -Force | Out-Null
$notice = "$docsRun/JBD-SP22S003-LiFePO4-A1.pdf"
$url = 'https://cdn.shopify.com/s/files/1/0606/5199/5298/files/JBD-SP22S003_37ea5c42-0b2f-4c30-bb4a-3ba411fcb66e.pdf?v=1664433389'
curl.exe --fail --silent --show-error --location --output $notice $url
if ($LASTEXITCODE -ne 0) { throw 'Notice Jiabaida indisponible' }
Get-FileHash -Algorithm SHA256 -LiteralPath $notice
```

Vérifier le modèle et la chimie en couverture, puis la révision et la
section 7.1. Un document d’une autre variante ou révision est écarté
comme preuve d’acceptation du lot. Le plan de contrôle du matériel est
dans la [fiche de relevés](measurement_requests.md).

## Intégrité et non-régression

La construction de `convergence_core` et les contrôles de référence
suivent [la recette A.1](../a1/REPORT.md). Avec ses dépendances
reproductibles présentes, rejouer les trois demandes A.1 de lecture
sur une nouvelle copie privée à partir du dossier A2.

```powershell
$core = '.runtime/v3-a1/build/convergence_core.exe'
python -B convergence_manager/tests/verify_v3_a2_evidence.py --core $core --out "$run/integrity"
```

Les préconditions des six mutations sont décrites dans le
[dossier par opération](operation_scopes.json). Les seules demandes
L5 issues de ce dossier sont ses trois analyses virtuelles,
reconstruites par le test depuis le tronc commun, les effets distincts
et la fermeture attestée dans le reçu A.

Le contrôle Q2 vérifie le rejet d’une autre révision de matériel et d’un
repère de face artificiellement translaté de +3 mm. Le test A2 vérifie
les champs obligatoires du relevé et détecte une signature, une source
brute ou une identité de lot absentes. L’authentification d’une
signature relève du dossier de métrologie réel. Les cas, commandes,
résultats et périmètres sont dans la
[preuve de non-régression](regressions.json).

La porte L5 conserve `BENCH_TEST_ONLY` pour les effets scellés A.1.
Transactions de construction B.1 et cartographe, V3-C, V3-D et réception
GO4 sont `NOT_RUN` dans cette campagne. Aucune inspection du matériel
n’a été effectuée.
