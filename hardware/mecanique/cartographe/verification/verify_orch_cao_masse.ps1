# Contrôle des artefacts sauvegardés ORCH-CAO-MASSE-1, sans simulation ni écriture CAO.
[CmdletBinding()]
param([switch]$RunTests, [switch]$WriteEvidence, [switch]$CollectFailures)
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..'))
$cad='hardware/mecanique/cartographe/'
$ver=$cad+'verification/'
$checks=[Collections.Generic.List[object]]::new()
$inputs=[ordered]@{}
function Project-Path([string]$p,[string]$base=''){
 if([string]::IsNullOrWhiteSpace($p)){throw 'Chemin de preuve absent'}
 $p=$p.Replace('\','/')
 if(-not [IO.Path]::IsPathRooted($p) -and $p -notmatch '^(hardware|simulation|software|docs|configs|results|scripts|tests|\.runtime|\.agents)/'){$p=$base+$p}
 $absolute=if([IO.Path]::IsPathRooted($p)){[IO.Path]::GetFullPath($p)}else{[IO.Path]::GetFullPath((Join-Path $repo $p))}
 if(-not $absolute.StartsWith($repo+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Chemin hors workspace : $p"}
 $absolute.Substring($repo.Length+1).Replace('\','/')
}
function Hash([string]$p){
 $p=Project-Path $p
 $value=(Get-FileHash -LiteralPath (Join-Path $repo $p) -Algorithm SHA256).Hash.ToLowerInvariant()
 if(-not $inputs.Contains($p)){$inputs[$p]=$value}
 $value
}
function Read([string]$p){$inputs[$p]=Hash $p;Get-Content -LiteralPath (Join-Path $repo $p) -Raw -Encoding UTF8|ConvertFrom-Json}
function Check([string]$id,[bool]$ok,$detail){$checks.Add([ordered]@{id=$id;reussi=$ok;detail=$detail});if(-not $ok -and -not $CollectFailures){throw "Contrôle non finalisé : $id"}}
function Write-Json([string]$p,$value){$value|ConvertTo-Json -Depth 100|Set-Content -LiteralPath (Join-Path $repo $p) -Encoding utf8}
function Check-Hash([string]$id,[string]$p,[string]$expected,[string]$base=''){
 $relative=Project-Path $p $base
 if(-not (Test-Path -LiteralPath (Join-Path $repo $relative) -PathType Leaf)){Check $id $false "Fichier absent : $relative";return}
 $actual=Hash $relative
 Check $id ($expected -match '^[0-9a-fA-F]{64}$' -and $actual -eq $expected) ([ordered]@{fichier=$relative;attendu=$expected;courant=$actual})
}
function Check-HashMap([string]$id,$map,[string]$base=''){
 Check ($id+':present') ($null -ne $map -and @($map.PSObject.Properties).Count -gt 0) 'Fermeture des dépendances explicite'
 foreach($property in $map.PSObject.Properties){Check-Hash ($id+':'+$property.Name) $property.Name $property.Value $base}
}
function Check-SourceIds([string]$id,$ids){
 Check ($id+':sources_presentes') (@($ids).Count -gt 0) $ids
 foreach($sourceId in @($ids)){Check ($id+':source:'+ $sourceId) ($null -ne $sourceId -and $sourceIndex.ContainsKey([string]$sourceId)) 'Source déclarée dans la BOM canonique'}
 Check ($id+':original_conserve') (@($ids|Where-Object {$sourceIndex.ContainsKey([string]$_) -and $sourceIndex[[string]$_].fichier}).Count -gt 0) 'Au moins une source originale conservée pour cette donnée applicable'
}
function Check-InclusionOwner($physical,[string]$owner){
 if($physical.proprietaire_masse_bom){Check ('contenu_proprietaire:'+ $physical.id) ($physical.proprietaire_masse_bom -eq $owner) $owner;return}
 # Le résultat C++ peut résoudre un propriétaire absent de l'extraction quand
 # tous les autres IDs rejoignent ce parent par les inclusions explicites BOM.
 $covered=$owner -in @($physical.bom_ids)
 foreach($other in $physical.bom_ids){
  $parent=$other;$seen=@{}
  while($parent -and $parent -ne $owner -and $bomIndex.ContainsKey($parent) -and -not $seen.ContainsKey($parent)){$seen[$parent]=$true;$parent=$bomIndex[$parent].masse_incluse_dans}
  if($parent -ne $owner){$covered=$false}
 }
 Check ('contenu_proprietaire_par_inclusions:'+ $physical.id) $covered ([ordered]@{proprietaire_publie=$owner;bom_ids=$physical.bom_ids;regle='Parent couvrant les autres ID par inclusion explicite, résolu par le C++'})
}
function Native-LinkCount($references){
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $count=0
 foreach($reference in $references){
  $archive=[IO.Compression.ZipFile]::OpenRead((Join-Path $repo ($cad+$reference.fichier)))
  try{
   $entry=$archive.GetEntry('Document.xml')
   if($null -eq $entry){throw "Document.xml absent : $($reference.fichier)"}
   $reader=[IO.StreamReader]::new($entry.Open())
   try{$document=[xml]$reader.ReadToEnd();$count+=@($document.Document.Objects.Object|Where-Object type -eq 'App::Link').Count}finally{$reader.Dispose()}
  }finally{$archive.Dispose()}
 }
 $count
}
$build=Read ($ver+'construction_prototype.json')
$manifest=Read ($cad+'manifest.json')
$bom=Read ($cad+'nomenclature_prototype.json')
$geo=Read ($ver+'orch_cao_masse_geometrie.json')
$mass=Read ($ver+'controle_masse_prototype.json')
$ledger=Read 'simulation/gazebo/models/cartographe/geometry/mass_ledger.json'
$coverage=Read ($ver+'couverture_bom_cao_prototype.json')
$assembly=Read ($ver+'controle_assemblage_prototype.json')
$factory=Read ($ver+'orch_cao_masse_fabrication.json')
$equipment=Read ($ver+'orch_cao_masse_equipements.json')
$interfaces=Read ($ver+'orch_interfaces_equipements.json')
$structure=Read ($ver+'orch_cao_masse_structure.json')
$xlsx=Read ($ver+'controle_nomenclature_prototype.json')
$render=Read ($ver+'rendu_prototype.json')
$reproduction=Read ($ver+'reproductibilite_masse_prototype.json')
$reprise=Read ($ver+'orch_reprise_collisions.json')
$savedReprise=Read ($ver+'controle_reprise_collisions.json')
$f20=Read ($ver+'orch_reprise_f20_application.json')
$chc=Read ($ver+'orch_reprise_tetes_chc_application.json')
$chcProposal=Read ($ver+'orch_reprise_tetes_chc.json')
# Les recherches et propositions conservent leurs dates/entrées historiques.
# Seules leurs recettes encore adoptées et les preuves finales doivent pointer
# sur les natifs courants ; une ancienne entrée « avant » ne doit pas être blanchie.
foreach($axis in @('structure','fournitures','equipements','visserie_complement')){
 $investigation=Read ($ver+'orch_reprise_masses_'+$axis+'.json')
 Check ('recherche_reprise:'+ $axis) $investigation.finalisation_correcte 'Recherches finalisées ; les inconnues restent dans la BOM'
}
Check-Hash 'construction_script' $build.script_fichier $build.script_sha256 $cad
Check-HashMap 'construction_recettes' $build.recettes_sha256 $ver
Check-Hash 'extraction_script' ($ver+'orch_integrate_cao.py') $geo.script_sha256
Check-Hash 'extraction_lecteur' ($ver+'read_brep_prototype.py') $geo.lecteur_sha256
Check-HashMap 'extraction_natifs' $geo.natifs_sha256 $cad
Check-Hash 'assemblage_script' ($ver+'verify_prototype.py') $assembly.script_sha256
Check-Hash 'assemblage_construction' ($ver+'construction_prototype.json') $assembly.construction_sha256
Check-Hash 'assemblage_natif' $assembly.assemblage $assembly.sha256 $cad
Check-HashMap 'assemblage_natifs' $assembly.natifs_sha256 $cad
$nativeScope=@{};foreach($reference in $build.references){$nativeScope[$reference.fichier]=$true};foreach($property in $build.sources_preservees.PSObject.Properties){$nativeScope[$property.Name]=$true}
foreach($scope in @(@{id='extraction';map=$geo.natifs_sha256},@{id='assemblage';map=$assembly.natifs_sha256},@{id='reprise';map=$savedReprise.natifs_sha256})){
 Check ('fermeture_native:'+ $scope.id) (@($scope.map.PSObject.Properties).Count -eq $nativeScope.Count -and @($nativeScope.Keys|Where-Object {$null -eq $scope.map.PSObject.Properties[$_]}).Count -eq 0) ([ordered]@{fichiers_attendus=$nativeScope.Count;fichiers_declares=@($scope.map.PSObject.Properties).Count})
}
Check-HashMap 'preuves_bom_courantes' $bom.orch_cao_masse_1.preuves_sources_sha256
Check-HashMap 'couverture_entrees' $coverage.sources_sha256
Check-Hash 'couverture_bom' ($cad+'nomenclature_prototype.json') $coverage.bom_sha256
foreach($recipe in @(@{proof=$factory;script='orch_fabrication_cao.py';id='fabrication'},@{proof=$equipment;script='orch_equipements_cao.py';id='equipements'},@{proof=$structure;script='orch_structure_cao.py';id='structure'})){
 $expectedScript=$recipe.proof.script_sha256
 if(-not $expectedScript){$expectedScript=$recipe.proof.recette_sha256}
 if(-not $expectedScript){$expectedScript=$build.recettes_sha256.($recipe.script)}
 Check-Hash ($recipe.id+':script') ($ver+$recipe.script) $expectedScript
 foreach($geometry in $recipe.proof.geometries){Check-Hash ($recipe.id+':geometrie:'+ $geometry.fichier) $geometry.fichier $geometry.sha256 $cad}
}
Check-Hash 'interfaces_script' ($ver+'orch_interfaces_equipements.py') $interfaces.entrees_sha256.($ver+'orch_interfaces_equipements.py')

Check 'reprise_appliquee' ($reprise.application -and $reprise.finalisation_correcte) 'Corrections sauvegardées, sans qualification matérielle'
Check-Hash 'reprise_recette' ($ver+'orch_reprise_collisions.py') $reprise.script_sha256
Check-Hash 'reprise_verificateur' ($ver+'orch_verifier_reprise.py') $savedReprise.script_sha256
Check-Hash 'reprise_correction' ($ver+'orch_reprise_collisions.json') $savedReprise.correction_sha256
Check-Hash 'reprise_construction' ($ver+'construction_prototype.json') $savedReprise.construction_sha256
Check-HashMap 'reprise_natifs_sauvegardes' $savedReprise.natifs_sha256 $cad
$rows=@($build.occurrences|Where-Object parent -ne $build.assemblage)
$rowIndex=@{};foreach($row in $rows){$key=$row.parent+'#'+$row.occurrence;Check ('reprise_occurrence_unique:'+ $key) (-not $rowIndex.ContainsKey($key)) $row.source;$rowIndex[$key]=$row}
$focus=@{};foreach($name in $savedReprise.focus){$focus[$name]=$true;Check ('reprise_focus_present:'+ $name) (@($rows|Where-Object occurrence -eq $name).Count -gt 0) 'Occurrence effectivement sauvegardée'}
$expectedPairs=0
for($i=0;$i -lt $rows.Count;$i++){for($j=$i+1;$j -lt $rows.Count;$j++){if($focus.ContainsKey($rows[$i].occurrence) -or $focus.ContainsKey($rows[$j].occurrence)){$expectedPairs++}}}
Check 'reprise_perimetre_paires' ($savedReprise.occurrences_lues -eq $rows.Count -and $savedReprise.paires_examinees -eq $expectedPairs -and $focus.Count -gt 0) ([ordered]@{occurrences_attendues=$rows.Count;occurrences_lues=$savedReprise.occurrences_lues;paires_attendues=$expectedPairs;paires_examinees=$savedReprise.paires_examinees;focus=@($savedReprise.focus)})
Check 'reprise_collisions_sauvegardees' ($savedReprise.finalisation_correcte -and $savedReprise.natifs_non_modifies -and $savedReprise.correction_geometrique_conforme -and $null -ne $savedReprise.interferences -and @($savedReprise.interferences).Count -eq 0 -and @($reprise.interferences_restantes).Count -eq 0 -and @($reprise.interferences_nouvelles).Count -eq 0) 'Absence d''interférences dans le périmètre BRep déclaré ; raccordements réels encore À valider'
foreach($row in @($reprise.changements_occurrences)+@($reprise.ajouts_occurrences)){
 $key=$row.parent+'#'+$row.occurrence;$current=$rowIndex[$key]
 Check ('reprise_pose_sauvegardee:'+ $key) ($null -ne $current -and ($row.matrice|ConvertTo-Json -Compress) -ceq ($current.matrice|ConvertTo-Json -Compress)) 'Matrice intégrée au registre courant'
 if($row.source){Check ('reprise_source_sauvegardee:'+ $key) ($current.source -eq $row.source -and $current.objet_source -eq $row.objet_source) $row.source}
}
Check 'reprise_f20_appliquee' ($f20.application_root -and $f20.finalisation_correcte) $f20.limite
Check-Hash 'reprise_f20_script' ($ver+'orch_appliquer_f20.py') $f20.script_sha256
Check-Hash 'reprise_f20_proposition' $f20.proposition $f20.proposition_sha256 $cad
Check-Hash 'reprise_f20_natif' $f20.fichier $f20.sha256_apres $cad
# Début du contrôle explicite des têtes CHC : les effectifs attendus viennent
# de la proposition et de son application, pas de compteurs figés du validateur.
Check 'reprise_chc_appliquee' ($chc.application -and $chc.finalisation_correcte -and $chcProposal.finalisation_correcte) 'Correction de diamètre seulement ; aucune qualification physique'
Check-Hash 'reprise_chc_script' ($ver+'orch_appliquer_tetes_chc.py') $chc.script_sha256
Check-Hash 'reprise_chc_proposition' ($ver+'orch_reprise_tetes_chc.json') $chc.proposition_sha256
$chcNativeControls=@($savedReprise.tetes_chc_sauvegardees|Where-Object fichier)
$chcPoseControls=@($savedReprise.tetes_chc_sauvegardees|Where-Object occurrence)
Check 'reprise_chc_couverture_controles' (@($chc.natifs_modifies).Count -gt 0 -and @($chc.natifs_modifies).Count -eq @($chcProposal.corrections_proposees).Count -and @($chc.occurrences_inchangees).Count -gt 0 -and @($chc.occurrences_inchangees).Count -eq @($chcProposal.contre_verification_brep.occurrences).Count -and $chcNativeControls.Count -eq @($chc.natifs_modifies).Count -and $chcPoseControls.Count -eq @($chc.occurrences_inchangees).Count -and @($savedReprise.tetes_chc_sauvegardees).Count -eq ($chcNativeControls.Count+$chcPoseControls.Count)) ([ordered]@{natifs_proposes=@($chcProposal.corrections_proposees).Count;natifs_appliques=@($chc.natifs_modifies).Count;natifs_controles=$chcNativeControls.Count;poses_proposees=@($chcProposal.contre_verification_brep.occurrences).Count;poses_conservees=@($chc.occurrences_inchangees).Count;poses_controlees=$chcPoseControls.Count})
foreach($change in $chc.natifs_modifies){
 Check-Hash ('reprise_chc_natif:'+ $change.fichier) $change.fichier $change.sha256_apres $cad
 $spec=@($chcProposal.corrections_proposees|Where-Object source -eq $change.fichier)
 Check ('reprise_chc_definition:'+ $change.fichier) ($spec.Count -eq 1 -and $change.solides_valides -and $change.rayon_apres_mm -eq $spec[0].apres_mm -and $change.hauteur_inchangee_mm -eq $spec[0].hauteur_inchangee_mm -and $change.longueur_tige_inchangee_mm -eq $spec[0].longueur_tige_inchangee_mm) 'Même correction que la proposition sourcée'
 $observed=@($chcNativeControls|Where-Object fichier -eq $change.fichier)
 Check ('reprise_chc_controle_natif:'+ $change.fichier) ($observed.Count -eq 1 -and $observed[0].placements_locaux_conserves -and $observed[0].rayon_tete_mm -eq $change.rayon_apres_mm -and $observed[0].hauteur_tete_mm -eq $change.hauteur_inchangee_mm -and $observed[0].longueur_tige_mm -eq $change.longueur_tige_inchangee_mm) 'Lecture du natif sauvegardé et placements locaux conservés'
}
foreach($occurrence in $chc.occurrences_inchangees){
 $key=$occurrence.parent+'#'+$occurrence.occurrence;$current=$rowIndex[$key]
 $spec=@($chcProposal.contre_verification_brep.occurrences|Where-Object {$_.parent -eq $occurrence.parent -and $_.occurrence -eq $occurrence.occurrence})
 Check ('reprise_chc_pose_construction:'+ $key) ($null -ne $current -and $current.source -eq $occurrence.source -and @($occurrence.matrice_inchangee).Count -eq 16 -and ($occurrence.matrice_inchangee|ConvertTo-Json -Compress) -ceq ($current.matrice|ConvertTo-Json -Compress)) 'Matrice conservée dans la construction finale'
 Check ('reprise_chc_pose_proposee:'+ $key) ($spec.Count -eq 1 -and ($spec[0].matrice_inchangee|ConvertTo-Json -Compress) -ceq ($occurrence.matrice_inchangee|ConvertTo-Json -Compress)) 'Même occurrence que dans la contre-vérification proposée'
 $observed=@($chcPoseControls|Where-Object {@($_.occurrence).Count -eq 2 -and $_.occurrence[0] -eq $occurrence.parent -and $_.occurrence[1] -eq $occurrence.occurrence})
 Check ('reprise_chc_controle_pose:'+ $key) ($observed.Count -eq 1 -and $observed[0].placement_global_conserve) 'Un contrôle sauvegardé distinct par placement conservé'
}
# Fin du contrôle explicite des têtes CHC.
$nativeLinks=Native-LinkCount $build.references
Check 'comptage_liens_poses_courants' ($assembly.poses_controlees -eq $build.occurrences.Count -and $assembly.liens_controles -eq $nativeLinks) ([ordered]@{poses_attendues=$build.occurrences.Count;poses_controlees=$assembly.poses_controlees;liens_xml=$nativeLinks;liens_controles=$assembly.liens_controles})
$rotorRows=@($rows|Where-Object occurrence -match '^Helice_[0-9]+$');$rotorPairs=0
for($i=0;$i -lt $rotorRows.Count;$i++){for($j=$i+1;$j -lt $rotorRows.Count;$j++){$rotorPairs++}}
Check 'rotors_modeles_controles' (@($assembly.rotors).Count -eq $rotorRows.Count -and @($assembly.controle_helices).Count -eq $rotorRows.Count -and $rotorRows.Count -gt 0 -and @($assembly.separation_rotors).Count -eq $rotorPairs -and @($assembly.controle_helices|Where-Object {-not $_.axe_et_appui_conformes}).Count -eq 0 -and @($assembly.separation_rotors|Where-Object {-not $_.separes_nominalement}).Count -eq 0) $assembly.compatibilite_helices

$sourceIndex=@{};$bomIndex=@{};$physicalIndex=@{};$massIndex=@{}
foreach($item in $bom.items){Check ('bom_id_unique:'+ $item.id) (-not $bomIndex.ContainsKey($item.id)) $item.id;$bomIndex[$item.id]=$item}
foreach($source in $bom.orch_cao_masse_1.sources){
 Check ('source_id_unique:'+ $source.id) (-not [string]::IsNullOrWhiteSpace($source.id) -and -not $sourceIndex.ContainsKey($source.id)) $source.url
 $sourceIndex[$source.id]=$source
 if($source.fichier){Check-Hash ('source_conservee:'+ $source.id) $source.fichier $source.sha256 $cad}
 else{Check ('source_non_capturee_explicite:'+ $source.id) (-not [string]::IsNullOrWhiteSpace($source.limite_capture) -and $null -eq $source.sha256) $source.limite_capture}
}
foreach($physical in $geo.occurrences_physiques){
 Check ('occurrence_physique_unique:'+ $physical.id) (-not $physicalIndex.ContainsKey($physical.id)) $physical.source
 $physicalIndex[$physical.id]=$physical
 if($physical.proprietaire_masse_bom){Check ('proprietaire_physique:'+ $physical.id) ($bomIndex.ContainsKey($physical.proprietaire_masse_bom)) $physical.proprietaire_masse_bom}
}
foreach($item in $mass.items){Check ('masse_id_unique:'+ $item.id) (-not $massIndex.ContainsKey($item.id) -and $bomIndex.ContainsKey($item.id)) $item.counting_mode;$massIndex[$item.id]=$item}
foreach($item in $bom.items|Where-Object perimetre -eq 'embarque'){
 # Les postes de quantité explicitement nulle sont exclus par le calcul C++.
 if($null -ne $item.quantite -and $item.quantite -eq 0){continue}
 $published=$massIndex[$item.id]
 Check ('ligne_embarquee_publiee:'+ $item.id) ($null -ne $published) 'Résultat massique conservé pour la ligne active'
 $incomplete=-not $item.masse_complete_connue_dans_definition
 Check ('completude_bom_registre:'+ $item.id) ($incomplete -eq ($item.id -in @($mass.unknown_or_incomplete_items))) $item.mode_comptage_massique
 if($incomplete){
  $problem=$item.probleme_massique
  Check ('probleme_massique_explicite:'+ $item.id) ($null -ne $problem -and -not [string]::IsNullOrWhiteSpace($problem.statut) -and -not [string]::IsNullOrWhiteSpace($problem.information_manquante) -and -not [string]::IsNullOrWhiteSpace($problem.impact) -and $problem.masse_complete_inconnue) $problem
  Check ('probleme_massique_publie:'+ $item.id) (($problem|ConvertTo-Json -Depth 50 -Compress) -ceq ($published.probleme_massique|ConvertTo-Json -Depth 50 -Compress)) 'Même problème dans la BOM et le résultat C++'
  Check ('masse_complete_inconnue_null:'+ $item.id) ($null -eq $item.masse_unitaire_g) $item.contribution_connue_g
 }
 foreach($sourceId in @($item.donnee_massique.source_ids)){Check ('source_ligne:'+ $item.id+':'+$sourceId) ($sourceIndex.ContainsKey([string]$sourceId)) $sourceId}
 if($item.donnee_massique.applicable -and $null -ne $item.donnee_massique.valeur_g){
  Check-SourceIds ('masse_applicable:'+ $item.id) $item.donnee_massique.source_ids
  Check ('perimetre_masse_applicable:'+ $item.id) (@($item.donnee_massique.inclusions).Count -gt 0 -and @($item.donnee_massique.exclusions).Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($item.donnee_massique.conditions) -and $null -ne $item.donnee_massique.PSObject.Properties['incertitude_g']) 'Contenu, accessoires, conditions et incertitude explicites'
 }
 Check ('mode_comptage_publie:'+ $item.id) ($item.mode_comptage_massique -eq $published.counting_mode -and $item.masse_incluse_dans -eq $published.included_mass_in) 'Inclusion massique indépendante du parent d''achat'
 $seenParents=@{};$parent=$item.masse_incluse_dans
 while(-not [string]::IsNullOrWhiteSpace($parent)){
  $valid=$parent -ne $item.id -and -not $seenParents.ContainsKey($parent) -and $bomIndex.ContainsKey($parent)
  Check ('inclusion_sans_cycle:'+ $item.id+':'+$parent) $valid 'Parent massique déclaré, distinct et sans cycle'
  if(-not $valid){break};$seenParents[$parent]=$true;$parent=$bomIndex[$parent].masse_incluse_dans
 }
 if($published.counting_mode -eq 'incluse'){Check ('inclusion_non_additionnee:'+ $item.id) ($null -eq $published.known_contribution_g -and $null -eq $item.contribution_connue_g -and $null -eq $item.masse_unitaire_g) $item.masse_incluse_dans}
}
$allocated=@{}
foreach($item in $mass.items){
 $local=@{}
 foreach($content in $item.physical_content){
  Check ('contenu_physique_unique:'+ $item.id+':'+$content.occurrence) (-not $local.ContainsKey($content.occurrence) -and $physicalIndex.ContainsKey($content.occurrence)) $content.reference
  $local[$content.occurrence]=$true
  Check-InclusionOwner $physicalIndex[$content.occurrence] $item.id
  if($item.counting_mode -in @('composants_connus_partiels','composants_calcules_complets') -and ($null -ne $content.masse_calculee_candidate_g -or $null -ne $content.masse_documentee_g)){
   Check ('contribution_occurrence_unique:'+ $content.occurrence) (-not $allocated.ContainsKey($content.occurrence)) $item.id
   $allocated[$content.occurrence]=$item.id
  }
 }
 if($item.counting_mode -in @('composants_connus_partiels','composants_calcules_complets') -and @($item.contributions_documentaires_partielles).Count -gt 0){Check ('partiel_sans_recouvrement:'+ $item.id) (@($item.physical_content|Where-Object {$null -ne $_.masse_calculee_candidate_g -or $null -ne $_.masse_documentee_g}).Count -eq 0) 'Aucune addition d''un périmètre documentaire et de sa géométrie calculée'}
}
foreach($property in $bom.orch_cao_masse_1.recettes_composants_documentaires.PSObject.Properties){
 $recipe=$property.Value;$file=$property.Name
 Check-Hash ('recette_documentaire_natif:'+ $file) $file $recipe.sha256_natif $cad
 Check-SourceIds ('recette_documentaire:'+ $file) $recipe.source_ids
 Check ('recette_documentaire_definition:'+ $file) ($recipe.applicable -and $recipe.valeur_g -gt 0 -and $recipe.valeur_g -eq $recipe.masse_unitaire_g -and $recipe.nature -in @('fabricant','mesure','calcul') -and $recipe.qualificatif -in @('nominale','mesuree','calculee') -and -not [string]::IsNullOrWhiteSpace($recipe.conditions) -and -not [string]::IsNullOrWhiteSpace($recipe.objet_source)) $recipe.reference_documentaire_candidate
 Check ('recette_documentaire_perimetre:'+ $file) (@($recipe.inclusions).Count -gt 0 -and @($recipe.exclusions).Count -gt 0 -and $null -ne $recipe.PSObject.Properties['incertitude_g']) 'Masse nette de la pièce ; inclusions/exclusions et incertitude explicites'
 $shapes=@($geo.references|Where-Object {$_.fichier -eq $file -and $_.objet -eq $recipe.objet_source})
 Check ('recette_documentaire_objet:'+ $file) ($shapes.Count -eq 1 -and $shapes[0].sha256 -eq $recipe.sha256_natif) $recipe.objet_source
 Check ('recette_documentaire_sans_double_methode:'+ $file) ($null -eq $bom.orch_cao_masse_1.fabrications_candidates.PSObject.Properties[$file] -and $null -eq $bom.orch_cao_masse_1.faisceaux_calcules_partiels.PSObject.Properties[$file]) 'Une seule méthode de masse par occurrence'
}
$partialIds=@{}
foreach($part in $bom.orch_cao_masse_1.contributions_documentaires_partielles){
 $key=$part.bom_id+'#'+$part.id
 Check ('documentaire_partiel_unique:'+ $key) (-not $partialIds.ContainsKey($key) -and $bomIndex.ContainsKey($part.bom_id) -and $part.quantite_absolue_drone -gt 0 -and $part.donnee_massique.applicable -and $part.donnee_massique.valeur_g -gt 0) 'Quantité absolue pour un drone, sans multiplication par le parent'
 $partialIds[$key]=$true;Check-SourceIds ('documentaire_partiel:'+ $key) $part.donnee_massique.source_ids
}
foreach($property in $bom.orch_cao_masse_1.fabrications_candidates.PSObject.Properties){
 $recipe=$property.Value;$file=$property.Name
 Check-Hash ('fabrication_candidate_natif:'+ $file) $file $recipe.sha256_natif $cad
 Check-SourceIds ('fabrication_candidate:'+ $file) $recipe.source_ids
 Check ('fabrication_candidate_methode:'+ $file) ($recipe.densite_g_cm3 -gt 0 -and $recipe.methode -in @('volume_solide_terminal','tranchage') -and -not [string]::IsNullOrWhiteSpace($recipe.grade) -and -not [string]::IsNullOrWhiteSpace($recipe.procede)) 'Matière/procédé candidats explicites ; aucun volume extérieur assimilé automatiquement à du TPU plein'
 if($recipe.methode -eq 'tranchage'){
  $slice=$recipe.tranchage
  Check ('tranchage_natif:'+ $file) ($slice.retour_processus -eq 0 -and $slice.sha256_natif_source -eq $recipe.sha256_natif -and $slice.reconciliation_source_natif.stl_tranche_identique_au_natif_courant -and $slice.reconciliation_source_natif.sha256_natif_source -eq $recipe.sha256_natif -and $slice.reconciliation_source_natif.sha256_stl_retesselle -eq $slice.stl_sha256 -and $recipe.volume_extrude_piece_mm3 -gt 0 -and $recipe.volume_extrude_piece_mm3 -eq $slice.volume_extrude_mm3) $recipe.nature_volume_extrude
  foreach($kind in @('stl','gcode','log')){Check-Hash ('tranchage_'+$kind+':'+$file) $slice.$kind $slice.($kind+'_sha256')}
 }
}
foreach($profile in $factory.tranchage_tpu.profils){Check-Hash ('profil_tpu:'+ $profile.fichier) $profile.fichier $profile.sha256}
foreach($property in $bom.orch_cao_masse_1.estimations_geometrie_oem.PSObject.Properties){
 $id=$property.Name;$recipe=$property.Value;$physical=$physicalIndex[$id];$owner=$massIndex[$recipe.bom_id]
 $shapes=@($geo.references|Where-Object {$_.fichier -eq $recipe.fichier -and $_.objet -eq $recipe.objet_source})
 $calculated=@($owner.physical_content|Where-Object {$_.occurrence -eq $id})
 Check-Hash ('oem_natif:'+ $id) $recipe.fichier $recipe.sha256_natif $cad
 Check-SourceIds ('oem_densite:'+ $id) $recipe.source_ids
 Check ('oem_identite:'+ $id) ($null -ne $physical -and $physical.source -eq $recipe.fichier -and $physical.objet_source -eq $recipe.objet_source -and $physical.proprietaire_masse_bom -eq $recipe.bom_id -and $shapes.Count -eq 1 -and $shapes[0].valide -and [math]::Abs($shapes[0].volume_mm3-$recipe.volume_reference_mm3) -lt 1e-6) 'Volume BRep et propriétaire propres à cette occurrence'
 Check ('oem_masse_candidate:'+ $id) ($recipe.estimation_candidate_non_mesuree -and $recipe.densite_g_cm3 -gt 0 -and $calculated.Count -eq 1 -and [math]::Abs($calculated[0].masse_calculee_candidate_g-($recipe.volume_reference_mm3*$recipe.densite_g_cm3/1000)) -lt 1e-8 -and $allocated[$id] -eq $recipe.bom_id) 'Analogie de densité comptée une fois, incertitude non publiée'
}
$oemInterferences=Read ($ver+'orch_verifier_interferences_oem.json')
$oemSummary=$bom.orch_cao_masse_1.interferences_internes_oem
Check-Hash 'oem_interferences_script' ($ver+'orch_verifier_interferences_oem.py') $oemInterferences.script_sha256
Check 'oem_interferences_recensees' ($oemSummary.paires_testees -eq $oemInterferences.nombre_paires -and $oemSummary.paires_positives -eq $oemInterferences.nombre_intersections -and $oemSummary.paires_positives -eq @($oemInterferences.intersections).Count -and $oemSummary.paires_non_conclues -eq @($oemInterferences.erreurs).Count -and -not $oemInterferences.finalisation_correcte -and $oemSummary.qualification -eq 'À valider') 'Intersections et booléens non conclus ouverts ; pas de qualification de contact'
Check 'oem_candidats_non_recoupants' (@($oemInterferences.candidats.intersections).Count -eq 0 -and @($oemInterferences.candidats.erreurs).Count -eq 0 -and @($oemInterferences.candidats_contre_tubes.intersections).Count -eq 0 -and @($oemInterferences.candidats_contre_tubes.erreurs).Count -eq 0) 'Candidats aluminium distincts entre eux et des tubes carbone comptés'
foreach($hit in $oemInterferences.intersections){
 $a=@($geo.occurrences_physiques|Where-Object {$_.objet_source -eq $hit.objet_a -and $_.source -eq 'pieces/commerce/EQ_Chassis_X650.FCStd'})
 $b=@($geo.occurrences_physiques|Where-Object {$_.objet_source -eq $hit.objet_b -and $_.source -eq 'pieces/commerce/EQ_Chassis_X650.FCStd'})
 $both=$a.Count -eq 1 -and $b.Count -eq 1 -and $allocated.ContainsKey($a[0].id) -and $allocated.ContainsKey($b[0].id)
 Check ('oem_intersection_sans_double_attribution:'+ $hit.objet_a+':'+$hit.objet_b) ($a.Count -eq 1 -and $b.Count -eq 1 -and $hit.volume_commun_mm3 -gt 0 -and -not $both) 'Aucune paire chevauchante entièrement additionnée ; contact et éléments exclus à résoudre'
}
$kit=$bomIndex['MEC-X650-KIT']
Check 'kit_masse_approvisionnement' ($kit.perimetre -eq 'approvisionnement' -and $kit.masse_unitaire_g -eq 2000 -and $kit.donnee_massique.valeur_g -eq 2000 -and $null -eq $kit.contribution_connue_g -and -not $massIndex.ContainsKey($kit.id)) 'Masse fabricant du kit complet hors batterie ; non additionnée au prototype'
foreach($id in @('MEC-ESC','MEC-HELICE-CW','MEC-HELICE-CCW')){
 $item=$bomIndex[$id];Check ('scenario_propulsion_non_additionne:'+ $id) ($null -ne $item.estimation_conditionnelle -and -not $item.estimation_conditionnelle.comptabilisee_dans_sous_total -and $null -eq $item.masse_unitaire_g) 'Variante ou unité de masse non confirmée ; scénario séparé'
}
$scenario=$mass.scenario_exploratoire_propulsion
$scenarioSum=$bomIndex['MEC-ESC'].estimation_conditionnelle.contribution_g+$bomIndex['MEC-HELICE-CW'].estimation_conditionnelle.contribution_g+$bomIndex['MEC-HELICE-CCW'].estimation_conditionnelle.contribution_g
Check 'scenario_propulsion_reproductible' ($null -ne $scenario -and -not $scenario.comptabilise_dans_sous_total -and -not $scenario.borne_garantie -and $null -eq $scenario.masse_complete_g -and [math]::Abs($scenario.ajout_conditionnel_g-$scenarioSum) -lt 1e-8 -and [math]::Abs($scenario.sous_total_avec_hypotheses_g-($mass.known_subtotal_g+$scenarioSum)) -lt 1e-8) 'Scénario exploratoire partiel ; ne devient ni masse complète ni borne'
foreach($property in $bom.orch_cao_masse_1.faisceaux_calcules_partiels.PSObject.Properties){
 $recipe=$property.Value
 Check-Hash ('faisceau_partiel_natif:'+ $property.Name) $property.Name $recipe.sha256_natif $cad
 Check-SourceIds ('faisceau_partiel:'+ $property.Name) $recipe.source_ids
 Check ('faisceau_partiel_definition:'+ $property.Name) ($recipe.methode -eq 'masse_lineique_parcours' -and $recipe.longueur_parcours_mm -gt 0 -and $recipe.masse_lineique_g_m -gt 0 -and -not [string]::IsNullOrWhiteSpace($recipe.exclusions)) 'Segment matériel seulement ; connecteurs, engagements et protections exclus restent ouverts'
}
Check 'masse_drone_incomplete_explicitement' (@($mass.unknown_or_incomplete_items).Count -eq 0 -or ($null -eq $mass.mass_complete_g -and $null -eq $mass.centre_of_mass_m -and $null -eq $mass.inertia_kg_m2 -and -not $mass.lot_clos)) 'Sous-total connu distinct de la masse complète, du centrage et des inerties du drone'
Check 'configuration_unique' ($manifest.configuration_active -eq 'prototype_cartographe' -and $bom.orch_cao_masse_1.campagnes_gazebo_px4_suspendues) 'Prototype sans dock, nouvelles campagnes suspendues'
Check 'investigations_finalisees' ($factory.finalisation_correcte -and $equipment.finalisation_correcte -and $structure.finalisation_correcte) 'Finalisation des recherches, sans clôture des blocages'
Check 'integration_extraction_finalisees' ($build.finalisation_correcte -and $geo.finalisation_correcte -and $geo.natifs_non_modifies) 'Sauvegarde puis lecture BRep en processus séparé'
foreach($r in $build.references){Check ('natif:'+ $r.fichier) ((Hash ($cad+$r.fichier)) -eq $r.sha256) $r.sha256}
foreach($p in $build.sources_preservees.PSObject.Properties){Check ('source_preservee:'+ $p.Name) ((Hash ($cad+$p.Name)) -eq $p.Value) $p.Value}
foreach($p in $mass.sources_sha256.PSObject.Properties){Check ('entree_masse:'+ $p.Name) ((Hash $p.Name) -eq $p.Value) $p.Value}
Check 'manifeste_construction_occurrences' (($manifest.prototype_cartographe.occurrences|ConvertTo-Json -Depth 25 -Compress) -ceq ($build.occurrences|ConvertTo-Json -Depth 25 -Compress)) $build.occurrences.Count
Check 'ledger_identique_controle' ((Hash 'simulation/gazebo/models/cartographe/geometry/mass_ledger.json') -eq (Hash ($ver+'controle_masse_prototype.json'))) 'Même résultat C++ publié'
Check 'publication_massique_idempotente' ($reproduction.finalisation_correcte -and $reproduction.identiques) 'Cinq artefacts identiques après une seconde publication'
foreach($p in $reproduction.empreintes_apres.PSObject.Properties){Check ('reproduction:'+ $p.Name) ((Hash $p.Name) -eq $p.Value) $p.Value}
Check 'aucune_masse_inconnue_zero' (@($bom.items|Where-Object {$_.perimetre -eq 'embarque' -and $null -ne $_.masse_unitaire_g -and $_.masse_unitaire_g -le 0}).Count -eq 0) 'Inconnues null et valeurs documentaires conditionnelles distinctes'
Check 'inventaire_bidirectionnel' ($coverage.postes.Count -eq $bom.items.Count -and $coverage.inverse_cao_bom.Count -eq $geo.occurrences_physiques.Count) 'Tous les postes et occurrences présents dans les tableaux, écarts conservés'
Check 'reouverture_liens_poses' ($assembly.finalisation_correcte -and @($assembly.erreurs_recalcul_liens).Count -eq 0 -and @($assembly.erreurs_poses).Count -eq 0 -and $assembly.fichiers_non_modifies_par_verification) 'Nouveau processus FreeCAD ; aucun natif modifié par le contrôle'
Check 'collisions_assemblage_courantes' (@($assembly.collisions_equipements).Count -eq 0 -and @($assembly.collisions_structure).Count -eq 0 -and $assembly.sources_non_modifiees) 'Contacts et engagements déclarés séparément dans la preuve ; aucune qualification physique'
Check 'solides_physiques_valides' (@($geo.occurrences_physiques|Where-Object {-not $_.valide}).Count -eq 0) $geo.occurrences_physiques.Count
Check 'rendus_courants' ($render.finalisation_correcte -and $render.fichiers_non_modifies -and $render.construction_sha256 -eq (Hash ($ver+'construction_prototype.json')) -and $render.script_sha256 -eq (Hash ($ver+'render_prototype.py'))) $render.vues.Count
foreach($view in $render.vues){Check ('vue:'+ $view.fichier) ((Hash ($cad+$view.fichier)) -eq $view.sha256) $view.sha256}
Check 'interfaces_equipements_courantes' ($interfaces.sources_inchangees_pendant_controle -and @($interfaces.erreurs).Count -eq 0) $interfaces.formes_lues
foreach($p in $interfaces.entrees_sha256.PSObject.Properties){Check ('interface_entree:'+ $p.Name) ((Hash $p.Name) -eq $p.Value) $p.Value}
Check 'export_bom_courant' ($xlsx.entrees[0].sha256 -eq (Hash ($cad+'nomenclature_prototype.json')) -and @($xlsx.controles|Where-Object {-not $_.reussi}).Count -eq 0) $xlsx.controles.Count
foreach($e in $xlsx.exports){Check ('export:'+ $e.fichier) ((Hash $e.fichier) -eq $e.sha256) $e.sha256}
$historical=@()
foreach($p in @('simulation/gazebo/models/cartographe/geometry/geometry_manifest.json','simulation/gazebo/models/cartographe/model_manifest.json')){
 $old=Read $p
 $historical+= [ordered]@{fichier=$p;sha256=Hash $p;statut='Historique, obsolète pour la CAO ORCH-CAO-MASSE-1';regeneration_executee=$false}
}
$oldGeo=Get-Content (Join-Path $repo 'simulation/gazebo/models/cartographe/geometry/geometry_manifest.json') -Raw|ConvertFrom-Json
$changed=@($oldGeo.sources.dependencies_relative_to_cad_directory.PSObject.Properties|Where-Object {(Hash ($cad+$_.Name)) -ne $_.Value}|ForEach-Object {$_.Name})
Check 'obsolescence_gazebo_visible' ($changed.Count -gt 0 -and $manifest.prototype_cartographe.exports_gazebo.statut -like 'Obsolète*') $changed
$tests=@()
if($RunTests){
 $env:TEMP=Join-Path $repo '.runtime/orch-cao-masse-1/temp';$env:TMP=$env:TEMP
 $env:PATH='C:\msys64\ucrt64\bin;'+$env:PATH
 foreach($t in @(@{directory='.runtime/orch-gz-1/evidence_agent';filter='cartographe_mass_properties|cartographe_bom_mass_contract';log='.runtime/orch-cao-masse-1/tests_mass.log'},@{directory='.runtime/orch-cao-masse-1/station-build';filter='test_gazebo_export|test_gazebo_model_page|test_workspace_service';log='.runtime/orch-cao-masse-1/tests_station.log'})){
  $listed=& ctest --test-dir (Join-Path $repo $t.directory) -R $t.filter -N 2>&1
  Check ('tests_decouverts:'+ $t.filter) ($LASTEXITCODE -eq 0 -and ($listed -join "`n") -match 'Total Tests:\s*[1-9][0-9]*') ($listed -join "`n")
  & ctest --test-dir (Join-Path $repo $t.directory) -R $t.filter --output-on-failure 2>&1|Tee-Object -FilePath (Join-Path $repo $t.log)|Out-Host
  Check ('tests:'+ $t.filter) ($LASTEXITCODE -eq 0) $t.log
  $inputs[$t.log]=Hash $t.log;$tests+=[ordered]@{commande=('ctest --test-dir '+$t.directory+' -R '+$t.filter+' --output-on-failure');code_retour=$LASTEXITCODE;journal=$t.log;sha256=Hash $t.log}
 }
}
foreach($p in @('simulation/mass/BomMass.cpp','simulation/mass/MassProperties.hpp','simulation/mass/TestMass.cpp','software/cpp/src/adapters/LocalGazeboExportBackend.cpp','software/cpp/src/ui/GazeboModelPage.cpp','software/cpp/src/ui/SystemPage.cpp','software/cpp/tests/TestGazeboExport.cpp',($ver+'verify_orch_cao_masse.ps1'))){$inputs[$p]=Hash $p}
$visual=@()
foreach($p in @('exports/prototype/ensemble_brep.png','exports/prototype/connexions_camera.png','exports/verification_nomenclature_prototype/apres-masses-Perception.png','exports/verification_nomenclature_prototype/apres-masses-Énergie.png')){$visual+=[ordered]@{fichier=($cad+$p);sha256=Hash ($cad+$p);controle_empreinte_effectue=$true;inspection_effectuee=$false;statut='Inspection visuelle finale à consigner dans la revue indépendante ; une empreinte ne démontre pas cette inspection.'}}
$result=[ordered]@{
 lot='ORCH-CAO-MASSE-1';date_utc=[DateTime]::UtcNow.ToString('o');statut='Implémenté';qualification='À valider';lot_clos=$false
 conclusion='préliminaire ; définition géométrique et massique incomplète, anomalies détaillées dans les preuves'
 exigences=@('MEC-ARC-001','MEC-INT-001','MEC-MAS-001','CAB-CARTO-001')
 environnement=[ordered]@{os=[Environment]::OSVersion.VersionString;architecture='AMD64';freecad=$geo.environnement.freecad;compilateur='GCC MSYS2 ucrt64, C++17';qt='6.11.2';temp_workspace=$true}
 sources_sha256=$inputs;controles=$checks;tests=$tests
 inspections_visuelles=$visual
 couverture=[ordered]@{postes_bom=$bom.items.Count;postes_embarques=@($bom.items|Where-Object perimetre -eq 'embarque').Count;references_actives=$build.references.Count;occurrences_registre=$build.occurrences.Count;occurrences_physiques=$geo.occurrences_physiques.Count;formes_sources=$geo.references.Count;postes_embarques_sans_rattachement=$coverage.postes_embarques_sans_rattachement_detaille;occurrences_non_attribuees=$mass.unallocated_physical_occurrences}
 masses=[ordered]@{sous_total_disponible_g=$mass.known_subtotal_g;sous_total_documentaire_applicable_g=$mass.documented_applicable_subtotal_g;sous_total_calculs_candidats_g=$mass.candidate_calculated_subtotal_g;masse_complete_g=$mass.mass_complete_g;postes_incomplets=$mass.unknown_or_incomplete_items;centrage_drone=$null;inerties_drone=$null}
 anomalies_assemblage=[ordered]@{collisions_equipements=$assembly.collisions_equipements;collisions_structure=$assembly.collisions_structure;interfaces_fabrication=($ver+'orch_cao_masse_fabrication.json');interfaces_equipements=($ver+'orch_interfaces_equipements.json')}
 interferences_internes_oem=$oemSummary
 reprise_sauvegardee=[ordered]@{preuve=$ver+'controle_reprise_collisions.json';occurrences_lues=$savedReprise.occurrences_lues;paires_examinees=$savedReprise.paires_examinees;interferences=@($savedReprise.interferences).Count;focus=$savedReprise.focus;liens_controles=$assembly.liens_controles;liens_natifs_xml=$nativeLinks;poses_controlees=$assembly.poses_controlees;poses_construction=$build.occurrences.Count;controle_limite_aux_perimetres_declares=$true}
 blocages_recherches=$bom.orch_cao_masse_1.blocages
 exports_historiques=$historical;dependances_gazebo_modifiees=$changed
 non_execute=@('Nouvelle campagne Gazebo/PX4, études de vol/autonomie','Achat, fabrication et mesure de masse physique','Banc, raccordement ou vol réel')
 limites=@('Une exécution numérique finalisée ne qualifie pas le matériel.','Sous-total disponible conditionné aux matières et procédés candidats ; ni masse complète ni borne garantie.','Reprise des simulations physiques après résolution des blocages et définition reproductible des masses/distributions applicables.')
 finalisation_correcte=$true
}
# Une consolidation concurrente ne doit pas être publiée comme un instantané
# cohérent. Aucune écriture du résultat final si une dépendance a changé.
foreach($p in @($inputs.Keys)){Check ('instantane_stable:'+ $p) ((Hash $p) -eq $inputs[$p]) $inputs[$p]}
$failed=@($checks|Where-Object {-not $_.reussi})
if($failed.Count -gt 0){
 [ordered]@{finalisation_correcte=$false;ecriture_preuve=$false;controles=$checks.Count;controles_en_echec=$failed}|ConvertTo-Json -Depth 30
 throw ('Validation non finalisée : '+$failed.Count+' contrôle(s) à rafraîchir ou corriger ; aucune preuve finale écrite.')
}
if($WriteEvidence){Write-Json ($ver+'controle_orch_cao_masse_1.json') $result}
[ordered]@{controles=$checks.Count;references=$build.references.Count;occurrences=$geo.occurrences_physiques.Count;sous_total_g=$mass.known_subtotal_g;masse_complete_g=$mass.mass_complete_g;lot_clos=$false}|ConvertTo-Json
