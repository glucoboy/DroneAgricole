# Infrastructure : réactiver les contrôles ignorés dans une copie du projet.
# Le PCB et les préférences du projet courant restent inchangés.
$ErrorActionPreference = 'Stop'
$card = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workspace = (Resolve-Path (Join-Path $card '../../../..')).Path
$auditDir = Join-Path $workspace '.runtime/ca01_drc_full'
New-Item -ItemType Directory -Force $auditDir | Out-Null
$pcb = Join-Path $card 'CA01_Avionique.kicad_pcb'
$before = (Get-FileHash -LiteralPath $pcb -Algorithm SHA256).Hash
Copy-Item -LiteralPath $pcb -Destination (Join-Path $auditDir 'CA01_Avionique.kicad_pcb')
$project = Get-Content -LiteralPath (Join-Path $card 'CA01_Avionique.kicad_pro') -Raw | ConvertFrom-Json
foreach($entry in $project.board.design_settings.rule_severities.PSObject.Properties) {
    if($entry.Value -eq 'ignore') { $entry.Value = 'warning' }
}
$project | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath (Join-Path $auditDir 'CA01_Avionique.kicad_pro') -Encoding utf8
$table = Get-Content -LiteralPath (Join-Path $card 'fp-lib-table') -Raw
$table.Replace('${KIPRJMOD}', $card.Replace('\','/')) | Set-Content -LiteralPath (Join-Path $auditDir 'fp-lib-table') -Encoding utf8
$report = Join-Path $PSScriptRoot 'drc_controles_reactives_20261002.json'
& 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe' pcb drc --format json --all-track-errors --severity-all -o $report (Join-Path $auditDir 'CA01_Avionique.kicad_pcb')
if($LASTEXITCODE -ne 0) { throw 'Échec DRC de la copie' }
$result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if($result.violations.Count -or $result.unconnected_items.Count -or $result.ignored_checks.Count) { throw 'Audit des contrôles réactivés non conforme' }
if((Get-FileHash -LiteralPath $pcb -Algorithm SHA256).Hash -ne $before) { throw 'Le PCB courant a changé pendant cet audit' }
'Audit complet : zéro violation, zéro connexion restante, zéro contrôle ignoré ; PCB préservé.'
