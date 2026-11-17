# Contrôle documentaire uniquement ; aucun natif ni équipement n'est modifié.
[CmdletBinding()]
param([switch]$WriteEvidence)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
$bomPath = 'hardware/mecanique/cartographe/nomenclature_prototype.json'
$xlsxPath = 'hardware/mecanique/cartographe/exports/Nomenclature_Prototype_Cartographe.xlsx'
$evidencePath = 'hardware/mecanique/cartographe/verification/controle_nomenclature_prototype.json'
$checks = [Collections.Generic.List[object]]::new()
function Read-Json([string]$relative) { Get-Content -LiteralPath (Join-Path $repoRoot $relative) -Raw -Encoding UTF8 | ConvertFrom-Json }
function Hash-File([string]$relative) { (Get-FileHash -LiteralPath (Join-Path $repoRoot $relative) -Algorithm SHA256).Hash.ToLowerInvariant() }
function Check([string]$id, [bool]$ok, $detail) {
    $checks.Add([ordered]@{ id=$id; reussi=$ok; detail=$detail })
    if (-not $ok) { throw "Contrôle échoué : $id — $detail" }
}

$bom = Read-Json $bomPath
$ids = @($bom.items.id)
$links = @($bom.liaisons.id)
$embarked = @($bom.items | Where-Object perimetre -eq 'embarque')
$cfg = Read-Json 'hardware/mecanique/cartographe/configuration_cible_20261003.json'
$wiring = Read-Json 'hardware/electronique/cartographe/cablage_global.json'
Check 'identifiants' ($ids.Count -eq @($ids | Select-Object -Unique).Count -and $links.Count -eq @($links | Select-Object -Unique).Count) 'Unicité des postes et liaisons'
Check 'selection' (@(Compare-Object @($cfg.bom.id) @($bom.couverture_selection.id_source)).Count -eq 0) 'Chaque poste de la sélection source possède un rapprochement'
Check 'rapprochements' (@($bom.couverture_selection.items_prototype | Where-Object { $_ -notin $ids }).Count -eq 0) 'Tous les postes de rapprochement existent'
Check 'liaisons_source' (@($wiring.connections.id | Where-Object { $_ -notin $links }).Count -eq 0) 'Tous les Wxx de cablage_global sont couverts'
Check 'parents' (@($bom.items | Where-Object { ($_.parent -and $_.parent -notin $ids) -or ($_.masse_incluse_dans -and $_.masse_incluse_dans -notin $ids) }).Count -eq 0) 'Parentage et inclusion massique résolus'
Check 'quantites' (@($bom.items | Where-Object { ($null -ne $_.quantite -and $_.quantite -lt 0) -or ($_.perimetre -eq 'exclu' -and $_.quantite -ne 0) }).Count -eq 0) 'Quantités positives ou inconnues, retraits à zéro'
Check 'perimetre' (-not $bom.configuration.fast_swap -and -not $bom.configuration.hot_swap -and -not $bom.configuration.achat_libere -and -not $bom.configuration.fabrication_liberee -and $null -eq $bom.configuration.masse_complete_g -and $null -eq $bom.configuration.budget_complet_eur) 'Prototype sans dock ; migration CAO autorisée, achat/fabrication et bilan physique complet non présumés'
if ($bom.configuration.natifs_migres) {
 Check 'migration_tracable' ($bom.configuration.preuve_migration -and (Test-Path -LiteralPath (Join-Path $repoRoot $bom.configuration.preuve_migration))) 'Migration déclarée seulement avec une preuve locale identifiée'
}
$f22=$bom.items | Where-Object id -eq 'ELEC-F22'; $w22=$bom.liaisons | Where-Object id -eq 'W22'
Check 'antenne_gnss_directe' ($f22.quantite -eq 0 -and $f22.perimetre -eq 'exclu' -and $w22.quantite_faisceaux -eq 0 -and $w22.perimetre -eq 'exclu') 'Antenne GNSS montée directement ; aucune rallonge F22 installée'
$active=@($bom.items | Where-Object perimetre -in @('embarque','sol'))
Check 'definitions_actives' (@($active | Where-Object { -not $_.reference_fabricant -or $null -eq $_.quantite }).Count -eq 0) 'Références de définition et quantités de postes renseignées ; les détails candidats ne sont pas une qualification'
Check 'details_ouverts_explicites' (@($bom.resolution_definition.details_encore_a_terminer | Where-Object { $_ -notin $ids }).Count -eq 0 -and -not $bom.resolution_definition.fermeture_qualifiee) 'Compléments de définition identifiés ; fermeture qualifiée non revendiquée'
$openDetails=@($bom.items | Where-Object definition_detaillee_a_terminer | Select-Object -ExpandProperty id)
Check 'details_ouverts_coherents' (@(Compare-Object $openDetails @($bom.resolution_definition.details_encore_a_terminer)).Count -eq 0) 'Liste de compléments identique aux indicateurs portés par les postes'
$categorizedDetails=@($bom.resolution_definition.details_categories.PSObject.Properties.Value | ForEach-Object { $_ })
Check 'details_ouverts_classes' ($categorizedDetails.Count -eq @($categorizedDetails | Select-Object -Unique).Count -and @(Compare-Object $openDetails $categorizedDetails).Count -eq 0) 'Compléments répartis sans omission ni doublon entre contenu OEM, intégration, interfaces et matériel récupéré'
$jetiRetires=@($bom.items | Where-Object id -in @('ELEC-JETI','ELEC-COMMANDE-JETI','ELEC-F39'))
Check 'retrait_jeti' ($jetiRetires.Count -eq 3 -and @($jetiRetires | Where-Object { $_.quantite -ne 0 -or $_.perimetre -ne 'exclu' -or $_.achat -ne 'exclu' -or $_.sous_systeme -ne 'Options et retraits' }).Count -eq 0 -and @($bom.presentation.principaux | Where-Object { $_ -in $jetiRetires.id }).Count -eq 0) 'JETI, commande et cordon aval exclus de la sélection et de la synthèse'
$w38=$bom.liaisons | Where-Object id -eq 'W38'
Check 'raccord_direct_pm08' ($w38.vers -ceq 'PM08-CAN IN' -and $w38.de -ceq 'Connecteur manuel côté drone' -and $w38.groupe_physique -eq 'ELEC-F38' -and $w38.quantite_faisceaux -eq 1 -and @($bom.items | Where-Object { $_.id -eq 'ELEC-F38' -and $_.designation -ceq 'Faisceau connecteur manuel côté drone → PM08-CAN IN' -and $_.perimetre -eq 'embarque' -and $_.quantite -eq 1 }).Count -eq 1) 'W38 et ELEC-F38 portent une seule liaison du connecteur au PM08-CAN IN'
$jetilinks=@($bom.liaisons | Where-Object id -in @('W39','W-JETI-COMMANDE'))
Check 'liaisons_jeti_exclues' ($jetilinks.Count -eq 2 -and @($jetilinks | Where-Object { $_.quantite_faisceaux -ne 0 -or $_.perimetre -ne 'exclu' -or $_.groupe_physique -notin $jetiRetires.id }).Count -eq 0) 'Identifiants source gardés, aucun cordon JETI à monter'
Check 'fonctions_energie_conservees' (@($embarked | Where-Object id -in @('ELEC-BMS','ELEC-PM08','ELEC-PDB','ELEC-ISO','ELEC-PROTECTION-AMONT','ELEC-PROTECTION-W08','ELEC-CONNECTEUR-MANUEL')).Count -eq 7 -and $bom.configuration.commande_marche_arret -ceq 'Branchement = marche ; débranchement = arrêt' -and $bom.configuration.connecteur_maitrise_appel_reference_figee -and @($embarked | Where-Object { $_.id -eq 'ELEC-CONNECTEUR-MANUEL' -and $_.reference_fabricant -ceq 'QS8-S D-MAX B9310 (paire)' -and $_.quantite -eq 1 -and $_.unite -eq 'jeu' -and $_.statut -eq 'À valider' }).Count -eq 1) 'Fonctions BMS, PM, distribution, isolation et protections maintenues ; un jeu QS8-S choisi, qualification À valider'
foreach ($source in $bom.sources_techniques) { Check ('source:'+$source.fichier) ((Hash-File $source.fichier) -eq $source.sha256) $source.sha256 }
$localSources = @($bom.items.sources | Where-Object { $_ -notmatch '^https?://' } | ForEach-Object { ($_ -split '#')[0] } | Select-Object -Unique)
Check 'sources_accessibles' (@($localSources | Where-Object { -not (Test-Path -LiteralPath (Join-Path $repoRoot $_)) }).Count -eq 0) $localSources.Count
$ca = $bom.sous_nomenclatures[0]
$csv = @(Import-Csv -LiteralPath (Join-Path $repoRoot $ca.export_assemblage) -Encoding UTF8)
Check 'ca01_empreintes' ((Hash-File $ca.fichier) -eq $ca.sha256_fichier -and (Hash-File $ca.export_assemblage) -eq $ca.sha256_export_assemblage) 'JSON et CSV identifiés séparément'
$mounted = ($csv | Measure-Object quantite_candidate -Sum).Sum
Check 'ca01_comptages' ($csv.Count -eq $ca.reperes -and $mounted -eq $ca.quantite_montee_candidate -and @($csv | Where-Object dnp_bom -eq 'true').Count -eq $ca.dnp.Count -and @($csv | Where-Object { $_.quantite_candidate -ne '0' -and -not $_.mpn_bom }).Count -eq $ca.mpn_manquants_montes.Count) 'Export CA01 cohérent avec le registre'

Add-Type -AssemblyName System.IO.Compression.FileSystem
function Verify-Workbook($data, [string]$relative) {
 $archive=[IO.Compression.ZipFile]::OpenRead((Join-Path $repoRoot $relative))
 function Xml([string]$entry) {$rd=[IO.StreamReader]::new($archive.GetEntry($entry).Open());try{[xml]$rd.ReadToEnd()}finally{$rd.Dispose()}}
 try {
  $names=@((Xml 'xl/workbook.xml').SelectNodes('//*[local-name()="sheet"]')|ForEach-Object{$_.GetAttribute('name')})
  Check ($data.reference+':onglets') (($names -join '|') -ceq ((@('Vue système')+@($data.presentation.sous_systemes.feuille)) -join '|')) $names
  $strings=@();if($archive.GetEntry('xl/sharedStrings.xml')){$strings=@((Xml 'xl/sharedStrings.xml').SelectNodes('//*[local-name()="si"]')|ForEach-Object{$_.InnerText})}
  function Cell($xml,[string]$a) {
   $n=$xml.SelectSingleNode('//*[local-name()="c"][@r="'+$a+'"]');if($null -eq $n){return ''}
   if($n.GetAttribute('t') -eq 'inlineStr'){return $n.SelectSingleNode('*[local-name()="is"]').InnerText}
   $v=$n.SelectSingleNode('*[local-name()="v"]');if($null -eq $v){return ''};if($n.GetAttribute('t') -eq 's'){return $strings[[int]$v.InnerText]};return $v.InnerText
  }
  function Same-Cells($xml,[int]$row,$expected) {
   foreach($col in $expected.Keys){$actual=Cell $xml ($col+$row);$want=if($null -eq $expected[$col]){''}elseif($expected[$col] -is [ValueType]){[Convert]::ToString($expected[$col],[Globalization.CultureInfo]::InvariantCulture)}else{[string]$expected[$col]};if($actual -cne $want){throw "Export divergent $relative / $col$row : $actual != $want"}}
  }
  $positions=@{};$seen=@();$summary=Xml 'xl/worksheets/sheet1.xml'
  for($i=1;$i -lt $names.Count;$i++) {
   $sheet=$names[$i];$xml=Xml ('xl/worksheets/sheet'+($i+1)+'.xml');$rows=@($data.items|Where-Object sous_systeme -eq $sheet)
   $pane=$xml.SelectSingleNode('//*[local-name()="pane"]')
   Check ($data.reference+':volets:'+ $sheet) ($pane.GetAttribute('xSplit') -eq '1' -and $pane.GetAttribute('ySplit') -eq '7') 'ID et en-têtes figés'
   Check ($data.reference+':erreurs:'+ $sheet) ($xml.SelectNodes('//*[local-name()="c"][@t="e"]').Count -eq 0 -and $xml.InnerText -notmatch 'not implemented') 'Aucune erreur exportée'
   for($j=0;$j -lt $rows.Count;$j++){
    $r=$rows[$j];$n=$j+8;$seen+=$r.id;$positions[$r.id]=@{sheet=$sheet;row=$n}
    $notes=@();if($r.estimation_cao_candidate){$e=$r.estimation_cao_candidate;$notes+=('ESTIMATION CAO À VALIDER : '+$e.contribution_g+' g pour '+$e.quantite_absolue_drone+' pièces ; '+$e.condition+' Contribution comprise dans le sous-total candidat.')};if($r.estimation_conditionnelle){$e=$r.estimation_conditionnelle;$notes+=('ESTIMATION À VALIDER : '+$e.masse_unitaire_g+' g × '+$e.quantite+' = '+$e.contribution_g+' g ; '+$e.perimetre+' '+$e.condition+' Non additionnée au sous-total.')};if($r.probleme_massique){$notes+=('MASSE À COMPLÉTER : '+$r.probleme_massique.information_manquante)};$notes+=@($r.reserves)
    Same-Cells $xml $n @{A=$r.id;B=$r.designation;C=$(if($r.reference_fabricant){$r.reference_fabricant}else{'À définir'});D=$r.quantite;E=$r.unite;F=$r.statut;G=($notes -join ' ');H=$r.perimetre;I=$(if($r.choix){$r.choix}else{$r.achat});J=$r.parent;K=$r.masse_unitaire_g;L=$r.masse_nature;M=$r.masse_incluse_dans;N=$(if($r.fabricant){$r.fabricant}else{'À définir'});P=($r.sources -join "`n")}
    if($data.orch_cao_masse_1){Same-Cells $xml $n @{O=$r.contribution_connue_g}}
   }
   Check ($data.reference+':detail:'+ $sheet) ((Cell $xml 'D5') -eq [string]$rows.Count) 'Toutes les lignes source et leur comptage sont fidèles'
   if($sheet -eq 'CA01'){
    $h=7+$rows.Count+6
    for($j=0;$j -lt $csv.Count;$j++){$r=$csv[$j];Same-Cells $xml ($h+1+$j) @{A=$r.reference;B=$r.valeur_bom;C=$(if($r.mpn_bom){$r.mpn_bom}else{'À définir'});D=$r.quantite_candidate;H=$(if($r.dnp_bom -eq 'true'){'Oui'}else{'Non'});I=$r.ecarts_sources;J=$r.mpn_netlist;K=$r.valeur_pcb;L=$r.empreinte_bom}}
    Check 'ca01_detail' ((Cell $xml ('D'+(7+$rows.Count+3))) -eq [string]$mounted) '151 repères et somme des composants montés'
   }
   if($sheet -eq 'Faisceaux'){
    $h=7+$rows.Count+5
    for($j=0;$j -lt $data.liaisons.Count;$j++){$r=$data.liaisons[$j];Same-Cells $xml ($h+1+$j) @{A=$r.id;B=$r.fonction;C=$r.connectique;D=$r.quantite_faisceaux;E=$r.longueur_m;F=$r.statut;G=$r.adaptation_prototype;H=$r.de;I=$r.vers;J=$r.groupe_physique;P=$r.source}}
    Check 'liaisons_detail' $true '43 identifiants de liaisons tracés ; exclusions à zéro explicites'
   }
  }
  Check ($data.reference+':couverture_export') ($seen.Count -eq $data.items.Count -and @($seen|Select-Object -Unique).Count -eq $data.items.Count) 'Chaque poste une seule fois dans le détail'
  $main=@($data.presentation.principaux)
  Check ($data.reference+':principaux') ($main.Count -eq @($main|Select-Object -Unique).Count -and @($main|Where-Object{$_ -notin $data.items.id}).Count -eq 0) 'Principaux IDs uniques et résolus'
  for($j=0;$j -lt $main.Count;$j++){
   $r=$data.items|Where-Object id -eq $main[$j];$n=$j+8;$p=$positions[$r.id];$ref="'"+$p.sheet.Replace("'","''")+"'"
   Same-Cells $summary $n @{A=$r.sous_systeme;B=$r.designation;C=$(if($r.reference_fabricant){$r.reference_fabricant}else{'À définir'});D=$(if($null -eq $r.quantite){'À définir'}else{$r.quantite});E=$r.unite;G=($p.sheet+' · '+$p.row)}
   foreach($col in @('B','C','E')){$f=$summary.SelectSingleNode('//*[local-name()="c"][@r="'+$col+$n+'"]/*[local-name()="f"]');if($f.InnerText -cne ($ref+'!'+$col+$p.row)){throw "Synthèse non liée : $col$n"}}
   $f=$summary.SelectSingleNode('//*[local-name()="c"][@r="D'+$n+'"]/*[local-name()="f"]');$expected='IF(ISNUMBER('+$ref+'!D'+$p.row+'),'+$ref+'!D'+$p.row+',"À définir")';if($f.InnerText -cne $expected){throw "Quantité de synthèse non liée : D$n"}
  }
  Check ($data.reference+':synthese') ($summary.SelectNodes('//*[local-name()="c"][@t="e"]').Count -eq 0 -and $summary.InnerText -notmatch 'not implemented') 'Synthèse liée aux détails, inconnues préservées'
  $tables=@($archive.Entries|Where-Object FullName -match '^xl/tables/table\d+\.xml$');$expectedTables=$names.Count+$(if($data.reference -eq 'BOM-CARTO-PROTOTYPE'){2}else{0})
  Check ($data.reference+':tables') ($tables.Count -eq $expectedTables -and @($tables|Where-Object{(Xml $_.FullName).SelectNodes('//*[local-name()="autoFilter"]').Count -eq 0}).Count -eq 0) 'Tables filtrables présentes'
  return [ordered]@{fichier=$relative;sha256=(Hash-File $relative);onglets=$names;postes=$data.items.Count;principaux=$main.Count;tables=$tables.Count}
 }finally{$archive.Dispose()}
}
$protoExport=Verify-Workbook $bom $xlsxPath
$customPath='hardware/mecanique/cartographe/nomenclature_produit_custom.json';$custom=Read-Json $customPath
Check 'custom_unicite' ($custom.items.Count -eq @($custom.items.id|Select-Object -Unique).Count) 'IDs custom uniques'
Check 'custom_parents' (@($custom.items|Where-Object{($_.parent -and $_.parent -notin $custom.items.id) -or ($_.masse_incluse_dans -and $_.masse_incluse_dans -notin $custom.items.id)}).Count -eq 0) 'Inclusions entre postes explicites'
Check 'custom_modules' ((@($custom.items|Where-Object reference_fabricant|ForEach-Object id) -join '|') -eq 'CUS-AVI-01|CUS-AVI-02') 'Seuls 6X et Jetson explicitement conservés'
Check 'custom_limites' ($custom.configuration.fast_swap_prevu -and -not $custom.configuration.hot_swap_decide -and -not $custom.configuration.achat_libere -and @($custom.items|Where-Object{$null -ne $_.masse_unitaire_g -or $null -ne $_.prix_unitaire_eur}).Count -eq 0) 'Échange rapide planifié, dimensionnement et achat non acquis'
$customExport=Verify-Workbook $custom 'hardware/mecanique/cartographe/exports/Nomenclature_Produit_Custom_Cartographe.xlsx'
$evidence=[ordered]@{
 reference='T-CARTO-BOM-PROTO-01';date_utc=[DateTime]::UtcNow.ToString('o');presentation_version=2;resultat='Réussi';qualification_physique='À valider'
 portee='Deux nomenclatures et leurs exports hiérarchiques ; aucune qualification matérielle'
 environnement=[ordered]@{os=[Environment]::OSVersion.VersionString;powershell=$PSVersionTable.PSVersion.ToString();methode='JSON/CSV, SHA-256 et XML OpenXML ; sans Excel natif'}
 commande='pwsh -NoProfile -File hardware/mecanique/cartographe/verification/verify_nomenclature_prototype.ps1 -WriteEvidence'
 entrees=@([ordered]@{fichier=$bomPath;sha256=(Hash-File $bomPath)},[ordered]@{fichier=$customPath;sha256=(Hash-File $customPath)},[ordered]@{fichier='hardware/mecanique/cartographe/verification/verify_nomenclature_prototype.ps1';sha256=(Hash-File 'hardware/mecanique/cartographe/verification/verify_nomenclature_prototype.ps1')})
 exports=@($protoExport,$customExport);controles=@($checks.ToArray())
 comptages=[ordered]@{prototype=$bom.items.Count;prototype_embarque=$embarked.Count;prototype_exclu=@($bom.items | Where-Object perimetre -eq 'exclu').Count;principaux_prototype=$bom.presentation.principaux.Count;custom=$custom.items.Count;ca01_reperes=$csv.Count;ca01_montes=$mounted;liaisons=$links.Count;liaisons_exclues=@($bom.liaisons | Where-Object { $_.quantite_faisceaux -eq 0 }).Count;quantites_embarquees_inconnues=@($embarked|Where-Object{$null -eq $_.quantite}).Count;references_embarquees_inconnues=@($embarked | Where-Object { -not $_.reference_fabricant }).Count;postes_actifs_initialement_incomplets=$bom.resolution_definition.postes_initialement_incomplets.Count;postes_repris=$bom.resolution_definition.postes_repris.Count;details_encore_a_terminer=$bom.resolution_definition.details_encore_a_terminer.Count;longueurs_faisceaux_inconnues=@($bom.liaisons|Where-Object{$_.quantite_faisceaux -gt 0 -and $null -eq $_.longueur_m}).Count;materiel_pc_identifie=$false}
 non_executes=@('Recalcul dans Excel natif','Recalcul CAO ou schémas','Essais physiques ; aucune modification de matériel')
 conclusion='Exports cohérents ; produit custom au niveau fonctionnel Planifié, faisabilité physique À valider.'
}
if($WriteEvidence){[IO.File]::WriteAllText((Join-Path $repoRoot $evidencePath),($evidence|ConvertTo-Json -Depth 15)+"`n",[Text.UTF8Encoding]::new($false))}
[ordered]@{resultat=$evidence.resultat;controles=$checks.Count;exports=@($protoExport,$customExport);preuve_ecrite=[bool]$WriteEvidence}|ConvertTo-Json -Depth 6
