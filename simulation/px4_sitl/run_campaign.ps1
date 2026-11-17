param(
    [ValidateSet('x500','cartographe')][string]$Model,
    [ValidateSet('square','failsafe','cancel')][string]$Mode,
    [string]$RunId,
    [string]$EvidenceExe = 'build/cartographe/cartographe-evidence.exe'
)
# Test infrastructure: local API invocation and bounded evidence collection.
# Flight state machine, arming, setpoints and failsafes remain in the C++ runner/PX4.
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $workspace
if ($RunId -notmatch '^[a-z0-9][a-z0-9_-]{0,95}$') { throw 'RunId invalide' }
$rawDir = ".runtime/orch_gz_1/20261024/$RunId"
$t0Dir = "results/simulation/orch_gz_1/sitl_20261024/$RunId"
if (Test-Path -LiteralPath $rawDir) { throw 'Répertoire de diagnostic déjà présent' }
New-Item -ItemType Directory -Path $rawDir | Out-Null
function Save-Json([string]$Path, $Value) {
    [IO.File]::WriteAllText((Join-Path $workspace $Path), ($Value | ConvertTo-Json -Depth 35), [Text.UTF8Encoding]::new($false))
}
function Api([string]$Path) {
    # Keep API timestamps as strings: the default DateTime conversion drops
    # trailing millisecond zeroes and breaks exact result.json reconciliation.
    (Invoke-WebRequest -Uri "http://127.0.0.1:8091$Path" -TimeoutSec 3).Content | ConvertFrom-Json -DateKind String
}
function Snapshot { (Invoke-RestMethod -Uri 'http://127.0.0.1:8092/api/snapshot' -TimeoutSec 3).px4_state }
function Fresh($State) {
    $odom = $State.topics_age_s.vehicle_odometry; $status = $State.topics_age_s.vehicle_status
    if ($null -eq $State.bridge_time_ns) { return $false }
    $bridgeAge = ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() * 1000000.0 - [double]$State.bridge_time_ns) / 1000000000.0
    return [double]::IsFinite($bridgeAge) -and $bridgeAge -ge -0.1 -and $bridgeAge -lt 1 -and $null -ne $odom -and $null -ne $status -and $odom -ge 0 -and $odom -lt 0.5 -and $status -ge 0 -and $status -lt 1
}
$preflightArgs = @('-NoProfile','-File','simulation/px4_sitl/preflight.ps1','-OutputPath',"$rawDir/preflight.json",'-ExpectedModel',"gz_$Model",'-RequireReady')
if ($Model -eq 'cartographe') { $preflightArgs += @('-ComposeOverride','simulation/compose.cartographe.yaml') }
& pwsh @preflightArgs
if ($LASTEXITCODE -ne 0) { throw 'Identité SITL refusée, aucune émission autorisée' }
$preflight = Get-Content "$rawDir/preflight.json" -Raw | ConvertFrom-Json
$health = Api '/api/health'
if (-not $health.sitl_locked) { throw 'Verrou SITL API absent' }
$before = Snapshot
if (-not (Fresh $before) -or $before.vehicle.armed) { throw 'Télémétrie initiale périmée ou véhicule déjà armé' }
$sitlId = (docker compose ps -q px4-sitl).Trim()
$rosId = (docker compose ps -q px4-runner-api).Trim()
$sitl = @(docker inspect $sitlId | ConvertFrom-Json)[0]
$ros = @(docker inspect $rosId | ConvertFrom-Json)[0]
$parameters = [ordered]@{}
foreach ($pattern in @('SYS_AUTOSTART','COM_OF_LOSS_T','COM_OBL_RC_ACT','BAT1_*','SIM_BAT*','CA_ROTOR*','SIM_GZ_EC_*','MPC_THR_HOVER','THR_MDL_FAC')) {
    $value = docker compose exec -T px4-sitl /opt/px4-gazebo/bin/px4-param show $pattern
    if ($LASTEXITCODE -ne 0) { throw "Lecture paramètre impossible : $pattern" }
    $parameters[$pattern] = $value -join "`n"
}
$version = docker compose exec -T px4-sitl /opt/px4-gazebo/bin/px4-ver all
$environment = [ordered]@{ identity_verified = $preflight.identity.status -eq 'verified_container'; model = $Model;
    image_ids = @{px4=$sitl.Image;ros=$ros.Image}; preflight=$preflight; px4_parameters=$parameters;
    topic_freshness=$before.topics_age_s; battery=$before.battery; telemetry_before=$before; px4_version=($version -join "`n");
    authorizations=@{DRONE_AGRICOLE_SITL='1';execute=$true;PX4_OFFBOARD_EXECUTE='true';entrypoint='local locked runner API'} }
Save-Json "$rawDir/environment.json" $environment
& $EvidenceExe prepare-sitl $t0Dir $Model $Mode
if ($LASTEXITCODE -ne 0) { throw 'Requête T0 refusée' }
$payload = [ordered]@{run_id=$RunId;mode=$(if($Mode -eq 'failsafe'){'failsafe'}else{'square'});
    result_directory="results/simulation/px4_lot_a/$RunId";
    parameters=@{takeoff_altitude_m=2.0;leg_m=2.0;warmup_s=2.0;hover_s=3.0;stage_timeout_s=12.0}}
Save-Json "$rawDir/api_request.json" $payload
$env:PX4_OFFBOARD_EXECUTE = 'true'
$watch = [Diagnostics.Stopwatch]::StartNew()
$stopped = $false; $lastState = ''; $terminal = $false
$tracePath = Join-Path $workspace "$rawDir/telemetry.jsonl"
try {
    $start = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8091/api/run/start' -ContentType 'application/json' -Body ($payload|ConvertTo-Json -Depth 8 -Compress) -TimeoutSec 5
    Save-Json "$rawDir/start.json" $start
    while ($watch.Elapsed.TotalSeconds -lt 235) {
        $status = Api '/api/run/status'
        $snapshot = Snapshot
        [IO.File]::AppendAllText($tracePath, ((@{elapsed_s=$watch.Elapsed.TotalSeconds;state=$snapshot}|ConvertTo-Json -Depth 15 -Compress)+"`n"), [Text.UTF8Encoding]::new($false))
        if ($status.state -ne $lastState) { Write-Output "SITL_RUN=$RunId STATE=$($status.state) ELAPSED=$([Math]::Round($watch.Elapsed.TotalSeconds,1))"; $lastState=$status.state }
        if ($status.state -in @('completed','failed','cancelled')) { $terminal=$true; break }
        $cancelInFlight = $Mode -eq 'cancel' -and $snapshot.vehicle.armed -and $snapshot.px4_odometry.position_ned_m[2] -lt -0.5
        if (-not $stopped -and ($cancelInFlight -or $watch.Elapsed.TotalSeconds -gt 180 -or -not (Fresh $snapshot))) {
            Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8091/api/run/stop' -TimeoutSec 3 | Out-Null
            $stopped=$true; Write-Output "SITL_STOP_REQUESTED=$RunId"
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $terminal) { throw 'Fin superviseur externe sans résultat terminal ; posé non présumé' }
    # The display bridge may trail the runner's direct DDS subscriptions by one
    # publication. Collect its independent disarmed confirmation before return.
    if ($status.result.observations.landing_confirmed) {
        $finalWatch = [Diagnostics.Stopwatch]::StartNew()
        do {
            Start-Sleep -Milliseconds 250
            $snapshot = Snapshot
        } while ($finalWatch.Elapsed.TotalSeconds -lt 5 -and (-not (Fresh $snapshot) -or $snapshot.vehicle.armed))
        if (-not (Fresh $snapshot) -or $snapshot.vehicle.armed) {
            Save-Json "$rawDir/final_confirmation_missing.json" $snapshot
            throw 'Le pont de lecture ne confirme pas encore le désarmement ; résultat brut conservé'
        }
    }
    Save-Json "$rawDir/status.json" $status
    Save-Json "$rawDir/telemetry_after.json" $snapshot
    & $EvidenceExe seal-sitl "$rawDir/status.json" $t0Dir "$rawDir/environment.json"
    if ($LASTEXITCODE -ne 0) { throw 'Finalisation T0 SITL refusée' }
    & $EvidenceExe validate $t0Dir
    if ($LASTEXITCODE -ne 0) { throw 'Contrats T0 SITL invalides' }
    Write-Output "SITL_FINAL=$RunId STATE=$($status.state) LANDED=$($status.result.observations.landing_confirmed) REASON=$($status.result.reason)"
} catch {
    if (-not $terminal) { try { Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8091/api/run/stop' -TimeoutSec 3 | Out-Null } catch {} }
    throw
} finally { $env:PX4_OFFBOARD_EXECUTE = $null }
