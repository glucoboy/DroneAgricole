$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $projectRoot
try {
    # Le serveur principal interrompt d'abord son client de runner. Le runner
    # Jazzy dispose ensuite de son propre délai d'atterrissage avant l'arrêt de PX4.
    docker compose --profile viz --profile sim stop fast-lio-dashboard
    if ($LASTEXITCODE -eq 0) {
        docker compose --profile viz --profile sim stop px4-runner-api
    }
    if ($LASTEXITCODE -eq 0) {
        docker compose --profile viz --profile sim stop px4-state-bridge micro-xrce-dds-agent px4-sitl
    }
    if ($LASTEXITCODE -ne 0) {
        throw "L'arrêt du tableau de bord a échoué."
    }
}
finally {
    Pop-Location
}
