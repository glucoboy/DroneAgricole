$ErrorActionPreference='Stop'
$root='D:/ProjetGuillaume/DroneAgricole/hardware/electronique/cartographe'
$w=Get-Content "$root/cablage_global.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$ids=@($w.modules.id)
$bad=@($w.connections | Where-Object {$_.from -notin $ids -or $_.to -notin $ids})
$duplicates=@($w.connections | Group-Object id | Where-Object {$_.Count -ne 1})
[xml]$nl=Get-Content "$root/carte_avionique/verification/netlist.xml" -Raw
$pins=@{}
foreach($n in $nl.export.nets.net){foreach($node in $n.node){$pins[$node.ref+'/'+$node.pin]=$n.name}}
$expected=@{'J103/1'='VBAT_PAYLOAD';'J103/2'='GND';'J104/1'='12V_COMPUTE';'J104/2'='GND';'J201/1'='12V_LIDAR';'J201/2'='GND';'MOD401/1'='5V_RADIO';'MOD401/2'='GND';'MOD401/3'='RP_TX';'MOD401/4'='RP_RX';'J402/1'='GND';'J402/2'='FC_RX_RF';'J402/3'='FC_TX_RF';'J501/1'='AIRY_SYNC_RAW';'J501/2'='GND';'J502/3'='BASLER_OPTO_RETURN';'J502/4'='BASLER_EXPOSURE_RAW';'J502/6'='GND';'J503/3'='GNSS_GPRMC_IN';'J503/5'='GNSS_PPS_IN';'J504/1'='PPS_AIRY';'J504/2'='GPRMC_AIRY';'J505/1'='PPS_ORIN';'J506/1'='GPRMC_ORIN';'J507/1'='FCU_AUX1';'J508/1'='FCU_CAP1'}
# Les labels locaux conservent le contrat d'interface, avec prefixe de feuille.
$expected['J509/1']='3V3_ORIN_IO_REF'
$expected['J509/2']='GND'
$pinErrors=@($expected.Keys | Where-Object {
 $actual=$pins[$_];$wanted=$expected[$_]
 -not ($actual -eq $wanted -or ($actual -and $actual.EndsWith('/'+$wanted)))
})
$md=Get-Content 'D:/ProjetGuillaume/DroneAgricole/docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md' -Raw -Encoding UTF8
$diagram=(Get-Content "$root/cablage_global.mmd" -Raw -Encoding UTF8).Trim()
$seriesErrors=@()
$w01=@($w.connections | Where-Object {$_.id -eq 'W01' -and $_.from -eq 'BAT' -and $_.to -eq 'BMS'})
$w05=@($w.connections | Where-Object {$_.id -eq 'W05' -and $_.from -eq 'PM' -and $_.to -eq 'DIST'})
$w06=@($w.connections | Where-Object {$_.id -eq 'W06' -and $_.from -eq 'PM' -and $_.to -eq 'FCU'})
if($w01.Count -ne 1 -or $w05.Count -ne 1 -or $w06.Count -ne 1){$seriesErrors+='PM series / POWER1 incorrect'}
if(@($w.connections | Where-Object {$_.from -eq 'BAT' -and $_.to -ne 'BMS'}).Count){$seriesErrors+='Battery bypass'}
if('MEAS' -in $ids -or @($w.connections | Where-Object {$_.id -eq 'W30'}).Count){$seriesErrors+='Old measurement still active'}
# Baseline actuelle33liaisons : W07/W11/W30 retirées ; sept chemins BMS ajoutés.
$expectedConnections=@(1..43 | Where-Object {$_ -notin @(7,11,30)} | ForEach-Object {'W{0:d2}' -f $_})
if(@(Compare-Object $expectedConnections @($w.connections.id)).Count){$seriesErrors+='Unexpected wiring inventory'}
if(@($w.modules | Group-Object id | Where-Object {$_.Count -ne 1}).Count){$seriesErrors+='Duplicate modules'}
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
if($w08.Count -ne 1 -or $w09.Count -ne 1 -or $w11.Count -ne 0){$seriesErrors+='CA01 or Jetson paths absent / retired W11 active'}
if(@($w.internal_connections | Where-Object {$_.id -eq 'CA01-MOD401' -and $_.from -eq 'CA01' -and $_.to -eq 'RF'}).Count -ne 1){$seriesErrors+='Direct MOD401 radio connection absent'}
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

# Contrats BMS/TE et isolation : topologie déclarative, sans qualification physique.
$uart=Get-Content (Join-Path $root 'contrat_uart_bms.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$harness=Get-Content (Join-Path $root 'faisceau_systeme_cible_20261003.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$paths=@(@('W37','BMS','TE'),@('W38','TE','JETI'),@('W39','JETI','PM'),@('W40','BMS','BMS_ISO'),@('W41','BMS_ISO','CPU'),@('W42','TE','PRESENCE_RESERVE'),@('W43','CHARGE_EXTERNE','TE'))
foreach($path in $paths){if(@($w.connections | Where-Object {$_.id -eq $path[0] -and $_.from -eq $path[1] -and $_.to -eq $path[2]}).Count -ne 1){$seriesErrors+=('BMS route absent: '+$path[0])}}
if(@($w.connections | Where-Object {$_.to -eq 'PM' -and $_.from -ne 'JETI'}).Count -or @($w.connections | Where-Object {$_.to -eq 'DIST' -and $_.from -ne 'PM'}).Count){$seriesErrors+='Power bypass around JETI/PM'}
$bi=$w.battery_interface
if(-not $bi.common_port -or $bi.negative_power_terminal -ne 'P_MINUS_PROTEGE' -or $bi.raw_ground_bypass_allowed -or -not $bi.raw_uart_ground_only_to_isolated_side){$seriesErrors+='BMS common negative path or isolation incorrect'}
if($bi.signal_count -ne 5 -or $bi.cavity_map.Count -ne 5 -or $bi.signal_cavity_numbers_confirmed -or @($bi.cavity_map | Where-Object {$null -ne $_.cavity_number}).Count){$seriesErrors+='TE candidate cavity status incorrect'}
$contactMap=@{'S_GND'='1650161-1';'S_TX'='1650155-1';'S_RX'='1650155-1';'S_PRESENT_A'='1650162-2';'S_PRESENT_B'='1650162-2'}
foreach($key in $contactMap.Keys){$c=@($bi.cavity_map | Where-Object {$_.logical_id -eq $key});if($c.Count -ne 1 -or $c[0].pin_mpn -ne $contactMap[$key] -or $c[0].socket_mpn -ne '1648325-1'){$seriesErrors+=('TE contact function incorrect: '+$key)}}
if(-not $bi.presence_isolated_from_raw_ground -or $bi.presence_operational_connection -or -not $bi.balance_taps_internal_to_cassette -or -not $bi.bms_cutoff_removes_propulsion_and_both_becs -or $bi.px4_preemptive_thresholds_qualified -or $bi.precharge_implemented -or $bi.swap_power_current_a_required -ne 0){$seriesErrors+='BMS safety status incorrect'}
if($w.manufacturing_ready -or $uart.manufacturing_ready -or $harness.fabrication_autorisee_par_ce_registre){$seriesErrors+='Candidate falsely released for manufacturing'}
if($uart.bms.mpn -ne 'JBD-SP22S003' -or $uart.bms.can_supported -or $uart.bms.uart_isolated_in_bms -or $uart.bms.revision_confirmed_on_hardware){$seriesErrors+='BMS model or protocol incorrectly claimed'}
if($uart.isolator.sku -ne 15817 -or -not $uart.isolator.data_isolation -or -not $uart.isolator.power_isolation_dc_dc -or $uart.isolator.ttl_gnd -ne 'BAT_MOINS_BRUT_ISOLE' -or $uart.isolator.ttl_5v_connection -ne 'NC' -or $uart.isolator.bms_vdd_connection -ne 'NC'){$seriesErrors+='UART data/supply isolation or NC missing'}
if(-not $uart.read_only -or $uart.write_commands_allowed -or $uart.software_implemented -or $uart.px4_adapter.implemented -or $uart.px4_adapter.dronecan_bms_claim -or $uart.px4_adapter.motor_command_allowed){$seriesErrors+='BMS diagnostic scope incorrect'}
$up=@($uart.bms.pins)
if($up.Count -ne 4 -or @($up | Where-Object {$_.pin -eq 1 -and $_.net -eq 'BAT_MOINS_BRUT_ISOLE'}).Count -ne 1 -or @($up | Where-Object {$_.pin -eq 2 -and $_.connect_to -eq 'TXD_ISO'}).Count -ne 1 -or @($up | Where-Object {$_.pin -eq 3 -and $_.connect_to -eq 'RXD_ISO'}).Count -ne 1 -or @($up | Where-Object {$_.pin -eq 4 -and $_.connection -eq 'NC'}).Count -ne 1){$seriesErrors+='JBD RX/TX/GND/VDD candidate contract incorrect'}
if($uart.safety.charge_negative -ne 'P_MINUS_PROTEGE' -or $uart.safety.raw_ground_bypass_allowed -or $uart.safety.balance_taps_external_blindmate -or $uart.cell_adapter.bulk_charge_or_discharge_allowed){$seriesErrors+='Charge or cell-tap path incorrect'}
foreach($src in $uart.sources){if($src.file){$sourcePath=Join-Path $root $src.file;if(-not (Test-Path $sourcePath) -or (Get-FileHash $sourcePath -Algorithm SHA256).Hash.ToLower() -ne $src.sha256){$seriesErrors+='JBD source hash mismatch'}}}
if($uart.serial.baud -ne 9600 -or $uart.serial.data_bits -ne 8 -or $uart.serial.parity -ne 'none' -or $uart.serial.stop_bits -ne 1 -or (@($uart.allowed_read_commands.hex) -join ',') -ne '03,04,05'){$seriesErrors+='UART read command contract incorrect'}
foreach($c in $uart.allowed_read_commands){$b=@($c.request_hex.Split(' ') | ForEach-Object {[Convert]::ToInt32($_,16)});$sum=($b[2]+$b[3]) -band 65535;$chk=((65536-$sum) -band 65535);if($b.Count -ne 7 -or $b[0] -ne 221 -or $b[1] -ne 165 -or $b[3] -ne 0 -or ($b[4]*256+$b[5]) -ne $chk -or $b[6] -ne 119){$seriesErrors+='Invalid JBD read request checksum/frame'}}
$hids=@($harness.groupes | ForEach-Object {$_.wxx} | ForEach-Object {$_})
if($harness.nombre_liaisons_actives_attendu -ne $w.connections.Count -or @(Compare-Object @($w.connections.id) $hids).Count -or @($hids | Group-Object | Where-Object {$_.Count -ne 1}).Count){$seriesErrors+='Harness wiring coverage incorrect'}
$f01=@($harness.groupes | Where-Object {$_.id -eq 'F01-ENERGIE-AMONT'})
if($f01.Count -ne 1 -or (@($f01[0].wxx) -join ',') -ne 'W01,W37,W38,W39' -or -not $f01[0].description.Contains('aucun XT90-S')){$seriesErrors+='Old XT90-S power harness retained'}
if(@($harness.familles_cables | Where-Object {$_.id -eq 'FIL-DOCK-AWG10'}).Count -or @($harness.budget_cuivre.segments_dock_mesurables).Count){$seriesErrors+='Obsolete mobile AWG10 route/mass retained'}
foreach($label in @('W01','W37','W38','W39','W40','W41','W42','W43','P− protégé','isolation données +DC/DC','fixeNC')){if(-not $diagram.Contains($label)){$seriesErrors+=('BMS diagram contract absent: '+$label)}}

$proof=[ordered]@{date_utc=[DateTime]::UtcNow.ToString('o');scope='coherence schéma système BMS/TE/UART et netlist CA01 courante, aucune qualification matérielle';target_revision='0.6-bms-candidat';ca01_implemented_revision='0.5-pre';migration_ready=$false;pending_interfaces=@('W06/W32 contacts PM et bascule','W09 XT30 et budget','W18 tension trigger','W26 J301 5V local','W31 CAN1 et terminaisons','W21 CAN2/5V/terminaison GNSS','W27/W28 debit RF et Backpack','W29 debit RTCM et pertes RF','W05 PDB liaison PM et montage','W08 XT30 CA01 polarite/protection/courant','W10/W17/W23 Airy alimentation et synchronisation','W36 GNSS vers CA01 PPS/GPRMC et isolation VCC','W24 CA01 vers Orin PPS/GPRMC','W33 AUX1 trigger et W34/W35 retour exposition/FMU_CAP1','W01/W37-W43 lot BMS, bornes, mapping cellules, cavités TE, UART et isolation','Courant/thermique100A, précharge et seuils PX4 avant coupure ultime');series_errors=$seriesErrors;module_count=$ids.Count;connection_count=$w.connections.Count;unknown_endpoints=$bad.Count;duplicate_connection_ids=$duplicates.Count;ca01_pin_checks=$expected.Count;pin_errors=$pinErrors;diagram_matches_doc=(($md -replace '\r\n',[string][char]10).Contains(($diagram -replace '\r\n',[string][char]10)));status='Planifié / À valider';manufacturing_ready=$false;hardware_tests_executed=$false;uart_parser_tests_executed=$false;document_alignment_pending= (-not (($md -replace '\r\n',[string][char]10).Contains(($diagram -replace '\r\n',[string][char]10))));checks_passed=($seriesErrors.Count -eq 0 -and $bad.Count -eq 0 -and $duplicates.Count -eq 0 -and $pinErrors.Count -eq 0);mermaid_render_executed=$false;mermaid_render_limitation='Moteur Mermaid local absent ; connexions/labels structuraux contrôlés, rendu visuel à vérifier';harness_covered_connection_count=$hids.Count;bms_read_frames_checked=$uart.allowed_read_commands.Count;sources=@('cablage_global.json','cablage_global.mmd','faisceau_systeme_cible_20261003.json','contrat_uart_bms.json','verification/verify_cablage.ps1','carte_avionique/verification/netlist.xml','carte_avionique/manifest.json') | ForEach-Object {@{file=$_;sha256=(Get-FileHash "$root/$_" -Algorithm SHA256).Hash.ToLower()}}}
$proof | ConvertTo-Json -Depth 8 | Set-Content "$root/verification/cablage_global_bms.json" -Encoding utf8
if(Test-Path "$root/verification/rendu_cablage_bms.json"){
 $render=Get-Content "$root/verification/rendu_cablage_bms.json" -Raw -Encoding UTF8 | ConvertFrom-Json
 $digest=(Get-FileHash "$root/cablage_global.mmd" -Algorithm SHA256).Hash.ToLower()
 if($render.finalisation_correcte -and $render.source_sha256 -eq $digest){
  $proof.mermaid_render_executed=$true
  $proof.mermaid_render_limitation='Rendu local Mermaid10.9.3/Chromium produit ; vérification visuelle indépendante de la qualification matérielle'
  $proof | ConvertTo-Json -Depth 8 | Set-Content "$root/verification/cablage_global_bms.json" -Encoding utf8
 }
}
$proof | ConvertTo-Json -Depth 3
if($seriesErrors.Count -or $bad.Count -or $duplicates.Count -or $pinErrors.Count){throw 'Incoherence cablage'}
