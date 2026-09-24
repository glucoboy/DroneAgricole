param([string]$KiCadCli = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
$ErrorActionPreference = 'Stop'
$cardDir = Split-Path -Parent $PSScriptRoot
$schematic = Join-Path $cardDir 'CA01_Avionique.kicad_sch'
$netPath = Join-Path $PSScriptRoot 'netlist.xml'
$ercPath = Join-Path $PSScriptRoot 'erc.json'
& $KiCadCli sch export netlist --format kicadxml -o $netPath $schematic
if ($LASTEXITCODE -ne 0) { throw 'Export netlist impossible' }
& $KiCadCli sch erc --format json --severity-all --exit-code-violations -o $ercPath $schematic
$ercExit = $LASTEXITCODE
if (-not (Test-Path -LiteralPath $ercPath)) { throw 'Rapport ERC absent' }
[xml]$net = Get-Content -LiteralPath $netPath -Raw
$nets = @{}
foreach ($n in $net.export.nets.net) { $nets[$n.name] = @($n.node | ForEach-Object { $_.ref + '/' + $_.pin }) }
$checks = [Collections.Generic.List[object]]::new()
function Check([string]$id, [bool]$ok, [string]$detail) { $checks.Add([ordered]@{id=$id;passed=$ok;detail=$detail}) }
function Exact([string]$name,[string[]]$pins) { return (@(Compare-Object ($nets[$name] | Sort-Object) ($pins | Sort-Object)).Count -eq 0) }
Check 'basler_return' (Exact 'BASLER_OPTO_RETURN' @('J502/3','Q501/3')) 'Retour opto uniquement au collecteur, sans pont GND'
Check 'basler_supply' (Exact '5V_SYNC' @('F501/2','J502/2')) 'Entree Line1 sur rail trigger protege ; pas alimentation camera'
Check 'airy_open' ((Exact 'AIRY_SYNC_RAW' @('J501/1','JP501/1')) -and (Exact 'AIRY_SYNC_IN' @('JP501/2','U501/1'))) 'Deux nets distincts de part et autre du cavalier ouvert'
Check 'buffer_input_pulldown' (($nets['SYNC_LOGIC_3V3'] -contains 'R503/1') -and ($nets['GND'] -contains 'R503/2')) 'Rappel entree buffer present'
Check 'trigger_chain' ((Exact 'BASE_TRIG' @('Q501/1','R501/2','R502/1')) -and (Exact 'TRIG_BUFFER' @('R501/1','U502/4'))) 'Buffer, resistance de base et transistor sans bypass'
Check 'radio_flight_input' (Exact '5V2_FLIGHT' @('F102/1','J101/1')) 'Entree domaine vol reservee a la radio'
Check 'pm_transit_absent' ((-not $nets.ContainsKey('PM_SCL')) -and (-not $nets.ContainsKey('PM_SDA')) -and (@($net.export.components.comp | Where-Object {$_.ref -eq 'J102'}).Count -eq 0)) 'PM vers Pixhawk direct hors CA01 : aucun transit I2C ni J102'
Check 'flight_aux_distinct' (($nets['5V_AUX'] -notcontains 'J101/1') -and (Exact '5V_RADIO' @('C401/1','C402/1','F102/2','J401/1'))) 'Nets positifs vol/aux distincts ; masse commune conservee'
foreach ($n in @(2,3)) {
 $u = 'U' + $n + '01'; $cboot='C'+$n+'02'; $cvcc='C'+$n+'04'
 Check ('buck_'+$n+'_bootstrap') ((Exact ('BOOT_'+$n) @(($cboot+'/1'),($u+'/6'))) -and ($nets['SW_'+$n] -contains ($cboot+'/2'))) 'Bootstrap entre BOOT et SW'
 Check ('buck_'+$n+'_vcc') ((Exact ('VCC_'+$n) @(($cvcc+'/1'),($u+'/8'))) -and ($nets['GND'] -contains ($u+'/31'))) 'VCC decouple et pad expose sur GND'
}
$radioText = Get-Content (Join-Path $cardDir '04_radio.kicad_sch') -Raw
foreach($ref in @('R401','R402')) {
 $component = @($net.export.components.comp | Where-Object {$_.ref -eq $ref})[0]
 $dnp = @($component.property | Where-Object {$_.name -eq 'dnp'}).Count -gt 0
 Check ($ref+'_dnp') $dnp 'Pont UART non monte avant validation niveaux'
}
$erc = Get-Content -LiteralPath $ercPath -Raw | ConvertFrom-Json
$violations = @($erc.sheets | ForEach-Object {$_.violations})
$files = @(Get-ChildItem -LiteralPath $cardDir -File | Where-Object {$_.Extension -in @('.kicad_sch','.kicad_pro','.kicad_sym','.kicad_pcb') -or $_.Name -eq 'sym-lib-table'} | ForEach-Object {[ordered]@{file=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()}})
$result = [ordered]@{
 schema_version=1;date_utc=[DateTime]::UtcNow.ToString('o');scope='Revue statique CA01 V0.3, pas de qualification materielle'
 platform='Windows amd64';kicad_version=(& $KiCadCli version | Out-String).Trim()
 component_count=@($net.export.components.comp).Count;net_count=@($net.export.nets.net).Count
 connectivity_checks=$checks;connectivity_passed=(@($checks | Where-Object {-not $_.passed}).Count -eq 0)
 erc=[ordered]@{exit_code=$ercExit;errors=@($violations | Where-Object {$_.severity -eq 'error'}).Count;warnings=@($violations | Where-Object {$_.severity -eq 'warning'}).Count;passed=($violations.Count -eq 0);report='erc.json'}
 manufacturing_ready=$false;hardware_tests_executed=$false;qualification='A valider';files=$files
}
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'controle_statique.json') -Encoding utf8
[pscustomobject]$result | Select-Object component_count,net_count,connectivity_passed,erc | ConvertTo-Json -Depth 5
if (-not $result.connectivity_passed) { throw 'Au moins un invariant de connexion a echoue' }

