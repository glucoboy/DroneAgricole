# Export local du dossier provisoire CA01 ; aucune commande fabricant.
$ErrorActionPreference='Stop'
$card=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cli='C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
$python='C:/Program Files/KiCad/10.0/bin/python.exe'
$pcb=Join-Path $card 'CA01_Avionique.kicad_pcb'
$proof=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'routage_complet_20261002.json') -Raw | ConvertFrom-Json
if($proof.inputs_sha256.'CA01_Avionique.kicad_pcb' -ne (Get-FileHash -LiteralPath $pcb -Algorithm SHA256).Hash.ToLower()) { throw 'PCB différent de la preuve : relancer DRC, revue et vérifications avant export' }
$out=Join-Path $card 'fabrication/exports_provisoires_20261002'
foreach($sub in 'gerber','percages','assemblage') { New-Item -ItemType Directory -Force (Join-Path $out $sub) | Out-Null }
& $cli pcb export gerbers --layers 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts' --subtract-soldermask --use-drill-file-origin --check-zones -o (Join-Path $out 'gerber/') $pcb
if($LASTEXITCODE -ne 0) { throw 'Export Gerber en échec' }
& $cli pcb export drill --format excellon --drill-origin plot --excellon-units mm --excellon-separate-th --generate-map --map-format svg --generate-report -o (Join-Path $out 'percages/') $pcb
if($LASTEXITCODE -ne 0) { throw 'Export perçages en échec' }
& $cli pcb export pos --format csv --units mm --side both --smd-only --exclude-dnp --use-drill-file-origin -o (Join-Path $out 'assemblage/positions_smd_candidates.csv') $pcb
if($LASTEXITCODE -ne 0) { throw 'Export CPL SMD en échec' }
& $cli pcb export pos --format csv --units mm --side both --exclude-dnp --use-drill-file-origin -o (Join-Path $out 'assemblage/positions_toutes_candidates.csv') $pcb
if($LASTEXITCODE -ne 0) { throw 'Export CPL complet en échec' }
& $cli pcb export ipcd356 -o (Join-Path $out 'CA01_Avionique_candidate.d356') $pcb
if($LASTEXITCODE -ne 0) { throw 'Export IPC-D-356 en échec' }
& $python (Join-Path $PSScriptRoot 'verify_fabrication_exports.py')
if($LASTEXITCODE -ne 0) { throw 'Comparaison des exports au PCB non conforme' }
'Dossier provisoire vérifié ; manufacturing_ready=false, aucune commande effectuée.'
