param([string[]]$Ids = @(), [switch]$VerifierSeulement)
$ErrorActionPreference = 'Stop'
$racineProjet = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$preuvePath = Join-Path $PSScriptRoot 'orch_reprise_masses_equipements.json'
$preuveCollecte = Get-Content -LiteralPath $preuvePath -Raw | ConvertFrom-Json
$repertoireSource = Join-Path $racineProjet 'hardware/mecanique/cartographe/sources_fabricants/orch_reprise_masses_equipements'
[System.IO.Directory]::CreateDirectory($repertoireSource) | Out-Null
$erreursCollecte = @()
foreach ($sourceCollecte in $preuveCollecte.sources) {
    if ($Ids.Count -and $sourceCollecte.id -notin $Ids) { continue }
    $cibleCollecte = [System.IO.Path]::GetFullPath((Join-Path $racineProjet $sourceCollecte.fichier))
    $dansRepertoireDedie = $cibleCollecte.StartsWith($repertoireSource + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
    if (-not $dansRepertoireDedie -and -not $sourceCollecte.archive_originale) { throw 'Cible hors répertoire dédié.' }
    if (-not $cibleCollecte.StartsWith($racineProjet + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Source hors projet.' }
    try {
        if (-not (Test-Path -LiteralPath $cibleCollecte)) {
            if ($VerifierSeulement -or $sourceCollecte.archive_originale -or $sourceCollecte.capture_normalisee) { throw 'Source conservée absente.' }
            Invoke-WebRequest -Uri $sourceCollecte.url -OutFile $cibleCollecte -TimeoutSec 30
        }
        $empreinteCollecte = (Get-FileHash -LiteralPath $cibleCollecte -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($sourceCollecte.sha256 -and $sourceCollecte.sha256 -ne $empreinteCollecte) { throw 'Empreinte de la source originale modifiée.' }
        $sourceCollecte.sha256 = $empreinteCollecte
        if (-not $sourceCollecte.archive_originale -and -not $sourceCollecte.capture_normalisee) { $sourceCollecte.collecte = 'Original conservé' }
        Write-Output ($sourceCollecte.id + ' : ' + (Get-Item -LiteralPath $cibleCollecte).Length + ' octets')
    } catch {
        $sourceCollecte.collecte = 'Échec : ' + $_.Exception.Message
        $erreursCollecte += $sourceCollecte.id
        Write-Output ($sourceCollecte.id + ' : ' + $sourceCollecte.collecte)
    }
    $preuveCollecte | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $preuvePath -Encoding utf8
}
if ($VerifierSeulement -and -not $Ids.Count) {
    $preuveCollecte | Add-Member -NotePropertyName validation_sources -NotePropertyValue ([pscustomobject]@{date_utc=[DateTime]::UtcNow.ToString('o');erreurs=$erreursCollecte;conforme=($erreursCollecte.Count -eq 0);commande='collecte_reprise_masses_equipements.ps1 -VerifierSeulement'}) -Force
    $preuveCollecte | Add-Member -NotePropertyName finalisation_correcte -NotePropertyValue ($erreursCollecte.Count -eq 0 -and $preuveCollecte.propositions_normalisees.Count -gt 0) -Force
    $preuveCollecte | ConvertTo-Json -Depth 50 | Set-Content -LiteralPath $preuvePath -Encoding utf8
    if ($erreursCollecte.Count) { exit 1 }
}
