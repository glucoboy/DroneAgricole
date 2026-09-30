param([string]$KiCadCli='C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
$ErrorActionPreference='Stop'
$cardDir=Split-Path -Parent $PSScriptRoot
$schematic=Join-Path $cardDir 'CA01_Avionique.kicad_sch'
$netPath=Join-Path $PSScriptRoot 'netlist.xml'
$ercPath=Join-Path $PSScriptRoot 'erc.json'
& $KiCadCli sch export netlist --format kicadxml -o $netPath $schematic
if($LASTEXITCODE -ne 0){throw 'Export netlist impossible'}
# Export neuf : une panne CLI ne doit jamais recycler une ancienne preuve ERC.
$ercTemp=Join-Path $PSScriptRoot ('erc_'+[Guid]::NewGuid().ToString('N')+'.tmp.json')
try {
 & $KiCadCli sch erc --format json --severity-all --exit-code-violations -o $ercTemp $schematic
 $ercExit=$LASTEXITCODE
 if($ercExit -notin @(0,5)){throw ('Echec technique ERC, code '+$ercExit)}
 if(-not (Test-Path -LiteralPath $ercTemp)){throw 'Rapport ERC neuf absent'}
 $null=Get-Content -LiteralPath $ercTemp -Raw | ConvertFrom-Json
 Move-Item -LiteralPath $ercTemp -Destination $ercPath -Force
} finally {
 if(Test-Path -LiteralPath $ercTemp){Remove-Item -LiteralPath $ercTemp}
}
[xml]$net=Get-Content -LiteralPath $netPath -Raw
$nets=@{}
foreach($n in $net.export.nets.net){$nets[$n.name]=@($n.node | ForEach-Object {$_.ref+'/'+$_.pin})}
$refs=@($net.export.components.comp | ForEach-Object {$_.ref})
$checks=[Collections.Generic.List[object]]::new()
function Check([string]$id,[bool]$ok,[string]$detail){$checks.Add([ordered]@{id=$id;passed=$ok;detail=$detail})}
# Le nom local peut etre prefixe par le chemin de feuille KiCad.
function Has([string]$name,[string]$pin){return @($nets.Keys | Where-Object {($_ -eq $name -or $_.EndsWith('/'+$name)) -and ($nets[$_] -contains $pin)}).Count -eq 1}
function SameNet([string]$a,[string]$b){return @($nets.Keys | Where-Object {($nets[$_] -contains $a) -and ($nets[$_] -contains $b)}).Count -eq 1}
# Une resistance non polarisee peut etre retournee sans changer son circuit.
function ResistorBetween([string]$ref,[string]$a,[string]$b){return (((SameNet ($ref+'/1') $a) -and (SameNet ($ref+'/2') $b)) -or ((SameNet ($ref+'/2') $a) -and (SameNet ($ref+'/1') $b)))}
function Absent([string]$pin){$found=@($nets.Keys | Where-Object {$nets[$_] -contains $pin});return ($found.Count -eq 1 -and $found[0] -like 'unconnected-*')}
function Dnp([string]$ref){$c=@($net.export.components.comp | Where-Object {$_.ref -eq $ref});return ($c.Count -eq 1 -and @($c[0].property | Where-Object {$_.name -eq 'dnp'}).Count -gt 0)}
Check 'legacy_removed' (('J101' -notin $refs) -and ('J102' -notin $refs) -and (-not $nets.ContainsKey('5V2_FLIGHT')) -and (-not $nets.ContainsKey('PM_SCL')) -and (-not $nets.ContainsKey('PM_SDA'))) 'Aucun transit alimentation vol ou I2C PM'
Check 'input_6s' ((Has 'VBAT_PAYLOAD' 'J103/1') -and (Has 'GND' 'J103/2') -and (Has 'VIN_PAYLOAD_PROT' 'Q102/1')) 'Entree 6S, FETs et sortie protegee'
Check 'radio_local_fuse' ((Has '5V_AUX' 'F102/1') -and (Has '5V_RADIO' 'F102/2') -and (Has '5V_RADIO' 'J401/1')) 'Radio depuis 5 V local'
Check 'compute_lidar_outputs' ((Has '12V_COMPUTE' 'J104/1') -and (Has '12V_LIDAR' 'J201/1')) 'Deux rails 12 V distincts'
Check 'gnss_power_isolated' ((Absent 'J503/1') -and (Has 'GND' 'J503/6')) 'GNSS alimente par CAN2, pas CA01'
Check 'camera_grounds_separate' ((Has 'GND' 'J502/6') -and (-not (Has 'GND' 'J502/3')) -and (Has 'BASLER_OPTO_RETURN' 'J502/3')) 'Retour opto distinct de GND GPIO'
Check 'airy_optional_open' ((Has 'AIRY_SYNC_RAW' 'J501/1') -and (SameNet 'J501/1' 'JP501/1') -and (Absent 'JP501/2') -and (Dnp 'J501') -and (Dnp 'JP501')) 'SYNC_OUT1 option DNP'
foreach($ref in @('R401','R402','R530','R531','R532','R533')){Check ($ref+'_dnp') (Dnp $ref) 'Pont non monte avant verification des niveaux et sequencements'}
foreach($n in @(2,3)){
 $u='U'+$n+'01';$boot='C'+$n+'02';$vcc='C'+$n+'04';$l='L'+$n+'01'
 $swOk=(SameNet ($boot+'/2') ($u+'/1')) -and (SameNet ($l+'/1') ($u+'/1'))
 foreach($pin in @(2,3,4,5)){$swOk=$swOk -and (SameNet ($u+'/'+$pin) ($u+'/1'))}
 Check ('buck_'+$n+'_bootstrap') ((SameNet ($boot+'/1') ($u+'/6')) -and $swOk) 'BOOT, SW et inductance LM76003'
 Check ('buck_'+$n+'_vcc') ((SameNet ($vcc+'/1') ($u+'/8')) -and (Has 'GND' ($vcc+'/2')) -and (Has 'GND' ($u+'/31'))) 'VCC decouple et pad expose'
 $rail=if($n -eq 2){'12V_LIDAR'}else{'5V_AUX'};$rb='R'+$n+'03';$cb='C'+$n+'05'
 Check ('buck_'+$n+'_bias') ((Has $rail ($l+'/2')) -and (ResistorBetween $rb ($l+'/2') ($u+'/9')) -and (SameNet ($cb+'/1') ($u+'/9')) -and (Has 'GND' ($cb+'/2'))) 'BIAS depuis VOUT par R et decouplage'
 $rh='R'+$n+'01';$rl='R'+$n+'02'
 Check ('buck_'+$n+'_feedback') ((ResistorBetween $rh ($l+'/2') ($u+'/12')) -and (ResistorBetween $rl ($u+'/12') ($u+'/31')) -and (-not (SameNet ($l+'/2') ($u+'/12')))) 'Diviseur VOUT FB GND'
 foreach($i in @(1,6,7)){
  $c='C'+$n+'0'+$i
  Check ($c+'_input') ((Has 'VIN_PAYLOAD_PROT' ($c+'/1')) -and (Has 'GND' ($c+'/2'))) 'Decouplage entree'
 }
 $cout='C'+$n+'03';$cff='C'+$n+'08'
 Check ($cout+'_polarity') ((Has $rail ($cout+'/1')) -and (Has 'GND' ($cout+'/2'))) 'Polymere sortie positif VOUT negatif GND'
 Check ($cff+'_feedforward') ((SameNet ($cff+'/1') ($l+'/2')) -and (SameNet ($cff+'/2') ($u+'/12'))) 'Cff en parallele resistance haute'
 Check ($u+'_input_ground') ((Has 'VIN_PAYLOAD_PROT' ($u+'/20')) -and (Has 'GND' ($u+'/13'))) 'PVIN et AGND'
}
# Groupes attendus issus de la conception relue, pas copie automatique de la netlist.
$rules=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'connectivity_rules.json') -Raw | ConvertFrom-Json
foreach($rule in $rules.checks){
 $ok=$true
 if($rule.kind -eq 'same'){
  foreach($pin in $rule.pins){$ok=$ok -and (SameNet $rule.pins[0] $pin)}
  if($rule.net){$ok=$ok -and (Has $rule.net $rule.pins[0])}
 }elseif($rule.kind -eq 'nc'){$ok=Absent $rule.pin}
 elseif($rule.kind -eq 'between'){$ok=ResistorBetween $rule.ref $rule.pins[0] $rule.pins[1]}
 elseif($rule.kind -eq 'distinct'){$ok=-not (SameNet $rule.pins[0] $rule.pins[1])}
 elseif($rule.kind -eq 'distinct_all'){
  for($i=0;$i -lt $rule.pins.Count;$i++){for($j=$i+1;$j -lt $rule.pins.Count;$j++){$ok=$ok -and (-not (SameNet $rule.pins[$i] $rule.pins[$j]))}}
 }elseif($rule.kind -eq 'field'){
  $comp=@($net.export.components.comp | Where-Object {$_.ref -eq $rule.ref})[0]
  $actual=if($rule.field -eq 'Value'){$comp.value}elseif($rule.field -eq 'Footprint'){$comp.footprint}else{@($comp.fields.field | Where-Object {$_.name -eq $rule.field})[0].'#text'}
  $ok=$actual -and $actual.Contains($rule.contains)
 }elseif($rule.kind -eq 'included'){
  $comp=@($net.export.components.comp | Where-Object {$_.ref -eq $rule.ref})
  $ok=$comp.Count -eq 1 -and @($comp[0].property | Where-Object {$_.name -in @('exclude_from_bom','exclude_from_board','dnp')}).Count -eq 0 -and [bool]$comp[0].footprint
 }elseif($rule.kind -eq 'pinmap'){
  $comp=@($net.export.components.comp | Where-Object {$_.ref -eq $rule.ref})[0]
  $part=@($net.export.libparts.libpart | Where-Object {$_.lib -eq $comp.libsource.lib -and $_.part -eq $comp.libsource.part})[0]
  foreach($entry in $rule.expected.PSObject.Properties){$pin=@($part.pins.pin | Where-Object {$_.num -eq $entry.Name});$ok=$ok -and $pin.Count -eq 1 -and $pin[0].name -eq $entry.Value}
  $ok=$ok -and @($part.pins.pin).Count -eq @($rule.expected.PSObject.Properties).Count
 }
 else{throw ('Type de controle inconnu '+$rule.kind)}
 Check $rule.id $ok $rule.detail
}
$erc=Get-Content -LiteralPath $ercPath -Raw | ConvertFrom-Json
$violations=@($erc.sheets | ForEach-Object {$_.violations})
$files=@(Get-ChildItem -LiteralPath $cardDir -File | Where-Object {$_.Extension -in @('.kicad_sch','.kicad_pro','.kicad_sym','.kicad_pcb') -or $_.Name -eq 'sym-lib-table'} | ForEach-Object {[ordered]@{file=$_.Name;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()}})
$result=[ordered]@{schema_version=1;date_utc=[DateTime]::UtcNow.ToString('o');scope='CA01 cible V0.5 preliminaire ; aucune qualification materielle';platform='Windows amd64';kicad_version=(& $KiCadCli version | Out-String).Trim();component_count=@($net.export.components.comp).Count;net_count=@($net.export.nets.net).Count;connectivity_checks=$checks;connectivity_passed=(@($checks | Where-Object {-not $_.passed}).Count -eq 0);erc=[ordered]@{exit_code=$ercExit;errors=@($violations | Where-Object {$_.severity -eq 'error'}).Count;warnings=@($violations | Where-Object {$_.severity -eq 'warning'}).Count;passed=($violations.Count -eq 0);report='erc.json'};manufacturing_ready=$false;hardware_tests_executed=$false;qualification='A valider';files=$files}
$result.erc['ignored_checks']=$erc.ignored_checks
$result['recipe_inputs']=@('verify_ca01.ps1','connectivity_rules.json' | ForEach-Object {[ordered]@{file=$_;sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $_) -Algorithm SHA256).Hash.ToLower()}})
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'controle_statique.json') -Encoding utf8
[pscustomobject]$result | Select-Object component_count,net_count,connectivity_passed,erc | ConvertTo-Json -Depth 5
if(-not $result.connectivity_passed){throw 'Au moins un invariant de connexion a echoue'}
if(-not $result.erc.passed){throw 'Au moins une violation ERC subsiste'}

