$ErrorActionPreference='Stop'
$root='D:/ProjetGuillaume/DroneAgricole/hardware/electronique/cartographe'
$w=Get-Content "$root/cablage_global.json" -Raw | ConvertFrom-Json
$ids=@($w.modules.id)
$bad=@($w.connections | Where-Object {$_.from -notin $ids -or $_.to -notin $ids})
$duplicates=@($w.connections | Group-Object id | Where-Object {$_.Count -ne 1})
[xml]$nl=Get-Content "$root/carte_avionique/verification/netlist.xml" -Raw
$pins=@{}
foreach($n in $nl.export.nets.net){foreach($node in $n.node){$pins[$node.ref+'/'+$node.pin]=$n.name}}
$expected=@{'J101/1'='5V2_FLIGHT';'J101/2'='GND';'J103/1'='VBAT_PAYLOAD';'J103/2'='GND';'J104/1'='12V_COMPUTE';'J104/2'='GND';'J201/1'='12V_LIDAR';'J201/2'='GND';'J301/1'='5V_AUX';'J301/2'='GND';'J401/1'='5V_RADIO';'J401/2'='GND';'J401/3'='RP_TX';'J401/4'='RP_RX';'J402/1'='GND';'J402/2'='FC_RX_RF';'J402/3'='FC_TX_RF';'J501/1'='AIRY_SYNC_RAW';'J501/2'='GND';'J502/2'='5V_SYNC';'J502/3'='BASLER_OPTO_RETURN'}
$pinErrors=@($expected.Keys | Where-Object {$pins[$_] -ne $expected[$_]})
$md=Get-Content 'D:/ProjetGuillaume/DroneAgricole/docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md' -Raw
$diagram=(Get-Content "$root/cablage_global.mmd" -Raw).Trim()
$seriesErrors=@()
$w01=@($w.connections | Where-Object {$_.id -eq 'W01' -and $_.from -eq 'BAT' -and $_.to -eq 'PM'})
$w05=@($w.connections | Where-Object {$_.id -eq 'W05' -and $_.from -eq 'PM' -and $_.to -eq 'DIST'})
$w06=@($w.connections | Where-Object {$_.id -eq 'W06' -and $_.from -eq 'PM' -and $_.to -eq 'FCU'})
if($w01.Count -ne 1 -or $w05.Count -ne 1 -or $w06.Count -ne 1){$seriesErrors+='PM series / POWER1 incorrect'}
if(@($w.connections | Where-Object {$_.from -eq 'BAT' -and $_.to -ne 'PM'}).Count){$seriesErrors+='Battery bypass'}
if('MEAS' -in $ids -or @($w.connections | Where-Object {$_.id -eq 'W30'}).Count){$seriesErrors+='Old measurement still active'}
if($ids.Count -ne 21 -or $w.connections.Count -ne 29){$seriesErrors+='Unexpected inventory'}
$manifest=Get-Content (Join-Path $root 'carte_avionique/manifest.json') -Raw | ConvertFrom-Json
if($manifest.revision -ne '0.3'){$seriesErrors+='Manifest revision mismatch'}
$proof=[ordered]@{date_utc=[DateTime]::UtcNow.ToString('o');scope='coherence documentaire cablage V0.3, pas validation de faisceau';series_errors=$seriesErrors;module_count=$ids.Count;connection_count=$w.connections.Count;unknown_endpoints=$bad.Count;duplicate_connection_ids=$duplicates.Count;ca01_pin_checks=$expected.Count;pin_errors=$pinErrors;diagram_matches_doc=$md.Contains($diagram);status='preliminaire';hardware_tests_executed=$false;sources=@('cablage_global.json','cablage_global.mmd','carte_avionique/verification/netlist.xml') | ForEach-Object {@{file=$_;sha256=(Get-FileHash "$root/$_" -Algorithm SHA256).Hash.ToLower()}}}
$proof | ConvertTo-Json -Depth 8 | Set-Content "$root/verification/cablage_global_20260922.json" -Encoding utf8
$proof | ConvertTo-Json -Depth 3
if($seriesErrors.Count -or $bad.Count -or $duplicates.Count -or $pinErrors.Count -or -not $proof.diagram_matches_doc){throw 'Incoherence cablage'}

