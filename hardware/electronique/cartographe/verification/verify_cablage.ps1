$ErrorActionPreference='Stop'
$root='D:/ProjetGuillaume/DroneAgricole/hardware/electronique/cartographe'
$w=Get-Content "$root/cablage_global.json" -Raw | ConvertFrom-Json
$ids=@($w.modules.id)
$bad=@($w.connections | Where-Object {$_.from -notin $ids -or $_.to -notin $ids})
$duplicates=@($w.connections | Group-Object id | Where-Object {$_.Count -ne 1})
[xml]$nl=Get-Content "$root/carte_avionique/verification/netlist.xml" -Raw
$pins=@{}
foreach($n in $nl.export.nets.net){foreach($node in $n.node){$pins[$node.ref+'/'+$node.pin]=$n.name}}
$expected=@{'J103/1'='VBAT_PAYLOAD';'J103/2'='GND';'J104/1'='12V_COMPUTE';'J104/2'='GND';'J201/1'='12V_LIDAR';'J201/2'='GND';'J401/1'='5V_RADIO';'J401/2'='GND';'J401/3'='RP_TX';'J401/4'='RP_RX';'J402/1'='GND';'J402/2'='FC_RX_RF';'J402/3'='FC_TX_RF';'J501/1'='AIRY_SYNC_RAW';'J501/2'='GND';'J502/3'='BASLER_OPTO_RETURN';'J502/4'='BASLER_EXPOSURE_RAW';'J502/6'='GND';'J503/3'='GNSS_GPRMC_IN';'J503/5'='GNSS_PPS_IN';'J504/1'='PPS_AIRY';'J504/2'='GPRMC_AIRY';'J505/1'='PPS_ORIN';'J506/1'='GPRMC_ORIN';'J507/1'='FCU_AUX1';'J508/1'='FCU_CAP1'}
# Les labels locaux conservent le contrat d'interface, avec prefixe de feuille.
$expected['J509/1']='3V3_ORIN_IO_REF'
$expected['J509/2']='GND'
$pinErrors=@($expected.Keys | Where-Object {
 $actual=$pins[$_];$wanted=$expected[$_]
 -not ($actual -eq $wanted -or ($actual -and $actual.EndsWith('/'+$wanted)))
})
$md=Get-Content 'D:/ProjetGuillaume/DroneAgricole/docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md' -Raw
$diagram=(Get-Content "$root/cablage_global.mmd" -Raw).Trim()
$seriesErrors=@()
$w01=@($w.connections | Where-Object {$_.id -eq 'W01' -and $_.from -eq 'BAT' -and $_.to -eq 'PM'})
$w05=@($w.connections | Where-Object {$_.id -eq 'W05' -and $_.from -eq 'PM' -and $_.to -eq 'DIST'})
$w06=@($w.connections | Where-Object {$_.id -eq 'W06' -and $_.from -eq 'PM' -and $_.to -eq 'FCU'})
if($w01.Count -ne 1 -or $w05.Count -ne 1 -or $w06.Count -ne 1){$seriesErrors+='PM series / POWER1 incorrect'}
if(@($w.connections | Where-Object {$_.from -eq 'BAT' -and $_.to -ne 'PM'}).Count){$seriesErrors+='Battery bypass'}
if('MEAS' -in $ids -or @($w.connections | Where-Object {$_.id -eq 'W30'}).Count){$seriesErrors+='Old measurement still active'}
if($ids.Count -ne 21 -or $w.connections.Count -ne 34){$seriesErrors+='Unexpected inventory'}
$manifest=Get-Content (Join-Path $root 'carte_avionique/manifest.json') -Raw | ConvertFrom-Json
if($manifest.revision -ne '0.5-pre' -or $manifest.target_wiring_revision -ne '0.5'){$seriesErrors+='Manifest implementation/target mismatch'}
$w21=@($w.connections | Where-Object {$_.id -eq 'W21' -and $_.from -eq 'FCU' -and $_.to -eq 'GNSS'})
$w29=@($w.connections | Where-Object {$_.id -eq 'W29' -and $_.from -eq 'BASE' -and $_.to -eq 'GNSS'})
if($w21.Count -ne 1 -or $w29.Count -ne 1 -or -not $w21[0].route.Contains('CAN2') -or -not $w29[0].route.Contains('QGC')){$seriesErrors+='RTK CAN2 or QGC route absent'}
$w31=@($w.connections | Where-Object {$_.id -eq 'W31' -and $_.from -eq 'PM' -and $_.to -eq 'FCU'})
$w32=@($w.connections | Where-Object {$_.id -eq 'W32' -and $_.from -eq 'PM' -and $_.to -eq 'FCU'})
if($w31.Count -ne 1 -or $w32.Count -ne 1){$seriesErrors+='CAN or POWER2 path absent'}
if(@($w.connections | Where-Object {$_.id -eq 'W07'}).Count){$seriesErrors+='Old BEC1 radio derivation still active'}
if($w06[0].type -ne 'Énergie vol'){$seriesErrors+='POWER1 must be power only'}
if(-not $w.power_allocation.power2_connected -or $w.power_allocation.outputs_paralleled){$seriesErrors+='POWER2 absent or BEC outputs paralleled'}
if((@($w.power_allocation.BEC1.routes) -join ',') -ne 'W06' -or (@($w.power_allocation.BEC2.routes) -join ',') -ne 'W32'){$seriesErrors+='BEC routes incorrect'}
if($w.power_allocation.BEC1.max_a -ne 3 -or $w.power_allocation.BEC2.max_a -ne 3 -or $w.power_allocation.BEC1.nominal_v -ne 5.3 -or $w.power_allocation.BEC2.nominal_v -ne 5.3){$seriesErrors+='BEC limits incorrect'}
$pmmap=$w.pm_connector_mapping
if($pmmap.pixhawk_can1.can_h -ne 2 -or $pmmap.pixhawk_can1.can_l -ne 3 -or $pmmap.pixhawk_can1.ground -ne 4){$seriesErrors+='Baseboard CAN1 pin map incorrect'}
if(3 -notin $pmmap.pixhawk_power1.not_connected -or 4 -notin $pmmap.pixhawk_power1.not_connected -or 3 -notin $pmmap.pixhawk_power2.not_connected -or 4 -notin $pmmap.pixhawk_power2.not_connected -or 1 -notin $pmmap.pixhawk_can1.not_connected){$seriesErrors+='CAN and POWER isolation missing'}
if($pmmap.orientation_verified_on_hardware){$seriesErrors+='Hardware orientation falsely marked verified'}
if($w.ca01_migration.ready_for_connection -or $w.ca01_migration.implemented_revision -ne '0.5-pre' -or $w.ca01_migration.target_wiring_revision -ne '0.5'){$seriesErrors+='CA01 migration status incorrect'}
if(-not $md.Contains('POWER2') -or -not $md.Contains('5V_AUX') -or -not $diagram.Contains('BEC2') -or -not $diagram.Contains('CAN1')){$seriesErrors+='Target interfaces not documented'}
$w08=@($w.connections | Where-Object {$_.id -eq 'W08' -and $_.from -eq 'DIST' -and $_.to -eq 'CA01'})
$w09=@($w.connections | Where-Object {$_.id -eq 'W09' -and $_.from -eq 'CA01' -and $_.to -eq 'CPU'})
$w11=@($w.connections | Where-Object {$_.id -eq 'W11' -and $_.from -eq 'CA01' -and $_.to -eq 'RF'})
if($w08.Count -ne 1 -or $w09.Count -ne 1 -or $w11.Count -ne 1){$seriesErrors+='CA01 or Jetson paths absent'}
if(-not $w05[0].route.Contains('PDB') -or -not $w08[0].route.Contains('XT30')){$seriesErrors+='PDB or CA01 XT30 candidate path absent'}
$w17=@($w.connections | Where-Object {$_.id -eq 'W17' -and $_.from -eq 'LID' -and $_.to -eq 'CA01'})
$w23=@($w.connections | Where-Object {$_.id -eq 'W23' -and $_.from -eq 'CA01' -and $_.to -eq 'LID'})
if($w17.Count -ne 1 -or $w23.Count -ne 1 -or -not $w17[0].pins.Contains('10') -or -not $w23[0].open.Contains('RS232')){$seriesErrors+='Airy sync inventory absent'}
$w33=@($w.connections | Where-Object {$_.id -eq 'W33' -and $_.from -eq 'FCU' -and $_.to -eq 'CA01'})
$w34=@($w.connections | Where-Object {$_.id -eq 'W34' -and $_.from -eq 'CAM' -and $_.to -eq 'CA01'})
$w35=@($w.connections | Where-Object {$_.id -eq 'W35' -and $_.from -eq 'CA01' -and $_.to -eq 'FCU'})
if($w33.Count -ne 1 -or $w34.Count -ne 1 -or $w35.Count -ne 1 -or -not $w33[0].pins.Contains('FMU_CH1') -or -not $w34[0].pins.Contains('Line2') -or -not $w35[0].pins.Contains('FMU_CAP1')){$seriesErrors+='Camera timing paths absent'}
$gnss=@($w.modules | Where-Object {$_.id -eq 'GNSS'})
$w36=@($w.connections | Where-Object {$_.id -eq 'W36' -and $_.from -eq 'GNSS' -and $_.to -eq 'CA01'})
$w24=@($w.connections | Where-Object {$_.id -eq 'W24' -and $_.from -eq 'CA01' -and $_.to -eq 'CPU'})
if($gnss.Count -ne 1 -or $w24.Count -ne 1 -or $w36.Count -ne 1 -or -not $gnss[0].name.Contains('STM32G4') -or -not $w36[0].pins.Contains('pin5 PPS') -or -not $w36[0].pins.Contains('pin1 +5 V non raccordé') -or -not $w24[0].route.Contains('PPS')){$seriesErrors+='GNSS time candidate absent'}
if(-not $w24[0].pins.Contains('pin22 VDD3.3') -or -not $w24[0].pins.Contains('J509/1') -or -not $w24[0].pins.Contains('J509/2')){$seriesErrors+='Orin IO reference absent'}
if(-not $w06[0].route.Contains('POWER1') -or -not $w32[0].route.Contains('POWER2') -or -not $w31[0].route.Contains('CAN1') -or -not $w09[0].route.Contains('XT30')){$seriesErrors+='Critical route labels incorrect'}
if(-not $diagram.Contains('W06 BEC1 : 5,3V + GND vers POWER1') -or -not $diagram.Contains('W32 BEC2 : 5,3 V + GND vers POWER2') -or -not $diagram.Contains('W31 : DroneCAN / CAN1') -or -not $diagram.Contains('W09 : 12 V vers XT30')){$seriesErrors+='Critical diagram edges absent'}
if(-not $w06[0].pins.Contains('SCL/SDA 3/4 non raccordés') -or -not $w32[0].pins.Contains('SCL/SDA 3/4 non raccordés') -or -not $w31[0].pins.Contains('contact 1 +5V OUT non raccordé')){$seriesErrors+='Critical contact isolation absent'}
if(-not $w.power_allocation.ca01_aux_source.Contains('W08') -or -not $w.power_allocation.jetson_source.Contains('W09')){$seriesErrors+='CA01 or Jetson source inconsistent'}
$proof=[ordered]@{date_utc=[DateTime]::UtcNow.ToString('o');scope='coherence documentaire cablage cible V0.5 ; CA01 schema V0.5 preliminaire non raccordable';target_revision='0.5';ca01_implemented_revision='0.5-pre';migration_ready=$false;pending_interfaces=@('W06/W32 contacts PM et bascule','W09 XT30 et budget','W11 5V radio','W18 tension trigger','W26 J301 5V local','W31 CAN1 et terminaisons','W21 CAN2/5V/terminaison GNSS','W27/W28 debit RF et Backpack','W29 debit RTCM et pertes RF','W05 PDB liaison PM et montage','W08 XT30 CA01 polarite/protection/courant','W10/W17/W23 Airy alimentation et synchronisation','W36 GNSS vers CA01 PPS/GPRMC et isolation VCC','W24 CA01 vers Orin PPS/GPRMC','W33 AUX1 trigger et W34/W35 retour exposition/FMU_CAP1');series_errors=$seriesErrors;module_count=$ids.Count;connection_count=$w.connections.Count;unknown_endpoints=$bad.Count;duplicate_connection_ids=$duplicates.Count;ca01_pin_checks=$expected.Count;pin_errors=$pinErrors;diagram_matches_doc=(($md -replace '\r\n',[string][char]10).Contains(($diagram -replace '\r\n',[string][char]10)));status='preliminaire';hardware_tests_executed=$false;sources=@('cablage_global.json','cablage_global.mmd','carte_avionique/verification/netlist.xml','carte_avionique/manifest.json') | ForEach-Object {@{file=$_;sha256=(Get-FileHash "$root/$_" -Algorithm SHA256).Hash.ToLower()}}}
$proof | ConvertTo-Json -Depth 8 | Set-Content "$root/verification/cablage_global_v05_20260924.json" -Encoding utf8
$proof | ConvertTo-Json -Depth 3
if($seriesErrors.Count -or $bad.Count -or $duplicates.Count -or $pinErrors.Count -or -not $proof.diagram_matches_doc){throw 'Incoherence cablage'}
