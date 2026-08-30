param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $projectRoot
try {
    docker compose --profile viz --profile sim up -d --build `
        micro-xrce-dds-agent px4-state-bridge px4-sitl px4-runner-api fast-lio-dashboard
    if ($LASTEXITCODE -ne 0) {
        throw "La construction ou le démarrage du tableau de bord a échoué."
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8080/api/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) {
        docker compose --profile viz --profile sim logs --tail 100 fast-lio-dashboard
        throw "Le tableau de bord ne répond pas sur http://127.0.0.1:8080."
    }

    Write-Host "Tableau de bord : http://127.0.0.1:8080" -ForegroundColor Cyan
    try {
        $lanAddress = Get-NetIPConfiguration |
            Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
            ForEach-Object { $_.IPv4Address.IPAddress } |
            Select-Object -First 1
        if ($lanAddress) {
            Write-Host "Réseau local   : http://${lanAddress}:8080" -ForegroundColor Cyan
        }
    }
    catch {
        Write-Host "Réseau local   : http://<adresse-IP-du-PC>:8080" -ForegroundColor DarkGray
    }
    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:8080"
    }
    Write-Host "Sélectionnez la simulation, son entrée, sa variante et ses paramètres dans la page." -ForegroundColor Green
    Write-Host "Les scénarios PX4 sont strictement limités au SITL et conservent PX4 comme contrôleur critique." -ForegroundColor DarkGray
    Write-Host "Arrêt du serveur : .\tools\visualization\stop_fastlio_dashboard.ps1"
}
finally {
    Pop-Location
}
