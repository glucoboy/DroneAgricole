param(
    [string]$SitlService = 'px4-sitl',
    [string]$ExpectedModel = 'gz_x500',
    [string]$ExpectedImage = 'px4io/px4-sitl-gazebo:v1.18.0-beta2@sha256:bcf8278e3321948be2266568528107dbfd94eb6fa703171cb013bc4d54dc8ef8',
    [string]$OutputPath = '.runtime/orch-gz-1/bench_preflight.json',
    [string]$ComposeOverride = '',
    [switch]$RequireReady,
    [switch]$SelfTest
)

# Infrastructure only: does not start containers, arm PX4 or publish ROS data.
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$outputAbsolute = [IO.Path]::GetFullPath((Join-Path $workspace $OutputPath))
if (-not $outputAbsolute.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Le résultat preflight doit rester dans le workspace.'
}
$checks = [Collections.Generic.List[object]]::new()

function Invoke-BoundedCommand([string]$Program, [string[]]$Arguments, [int]$BudgetSeconds = 15) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Program
    $start.WorkingDirectory = $workspace
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        if (-not $process.Start()) { throw "Impossible de démarrer $Program" }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timedOut = -not $process.WaitForExit($BudgetSeconds * 1000)
        if ($timedOut) { $process.Kill($true); $process.WaitForExit() }
        $entry = [ordered]@{ program = $Program; arguments = $Arguments; exit_code = $process.ExitCode;
            timed_out = $timedOut; elapsed_s = [Math]::Round($watch.Elapsed.TotalSeconds, 3);
            stdout = $stdoutTask.GetAwaiter().GetResult(); stderr = $stderrTask.GetAwaiter().GetResult() }
    } catch {
        $entry = [ordered]@{ program = $Program; arguments = $Arguments; exit_code = -1;
            timed_out = $false; elapsed_s = [Math]::Round($watch.Elapsed.TotalSeconds, 3);
            stdout = ''; stderr = $_.Exception.Message }
    } finally { $process.Dispose() }
    $checks.Add($entry)
    return $entry
}

function Test-AirframeIdentity([string]$Model, [string]$AutostartEnvironment,
                              [string]$ParameterOutput, [string[]]$AirframeFiles) {
    $problems = [Collections.Generic.List[string]]::new()
    $expectedId = $null
    if ($AutostartEnvironment -match '^[1-9][0-9]{0,8}$') {
        $expectedId = [int]$AutostartEnvironment
    } else { $problems.Add('sitl_autostart_environment_invalid') }
    $parameterMatches = [regex]::Matches($ParameterOutput,
        '(?m)^\s*(?:[x+*l]\s*)*SYS_AUTOSTART(?:\s+\[[^\]\r\n]*\])?\s*:\s*([0-9]+)\s*$')
    $actualId = $null
    if ($parameterMatches.Count -eq 1) { $actualId = [int]$parameterMatches[0].Groups[1].Value }
    else { $problems.Add('sitl_effective_autostart_unavailable_or_ambiguous') }
    if ($null -ne $expectedId -and $null -ne $actualId -and $expectedId -ne $actualId) {
        $problems.Add('sitl_effective_autostart_differs_from_environment')
    }
    $candidates = @($AirframeFiles | Where-Object {
        $null -ne $expectedId -and $_ -match ('^' + $expectedId + '_') -and -not $_.EndsWith('.post')
    })
    $expectedName = if ($null -ne $expectedId) { "${expectedId}_$Model" } else { $null }
    if ($candidates.Count -ne 1) { $problems.Add('sitl_airframe_id_not_unique') }
    elseif ($candidates[0] -cne $expectedName) { $problems.Add('sitl_airframe_name_differs_from_model') }
    return [ordered]@{ expected_sys_autostart = $expectedId; effective_sys_autostart = $actualId;
        expected_airframe_name = $expectedName; candidate_airframes = $candidates;
        ignored_post_files = @($AirframeFiles | Where-Object { $_.EndsWith('.post') });
        violations = @($problems); verified = $problems.Count -eq 0 }
}

if ($SelfTest) {
    $fixtures = @(
        @{ name='cartographe_unique'; model='gz_cartographe'; env='40000'; actual='40000';
            files=@('40000_gz_cartographe','40000_gz_cartographe.post'); accepted=$true },
        @{ name='x500_unique'; model='gz_x500'; env='4001'; actual='4001';
            files=@('4001_gz_x500'); accepted=$true },
        @{ name='cartographe_4010_stock_name'; model='gz_cartographe'; env='4010'; actual='4010';
            files=@('4010_gz_x500_mono_cam'); accepted=$false },
        @{ name='cartographe_4010_collision'; model='gz_cartographe'; env='4010'; actual='4010';
            files=@('4010_gz_x500_mono_cam','4010_gz_cartographe'); accepted=$false },
        @{ name='effective_parameter_mismatch'; model='gz_cartographe'; env='40000'; actual='4010';
            files=@('40000_gz_cartographe'); accepted=$false },
        @{ name='airframe_missing'; model='gz_cartographe'; env='40000'; actual='40000';
            files=@(); accepted=$false },
        @{ name='environment_missing'; model='gz_cartographe'; env=''; actual='40000';
            files=@('40000_gz_cartographe'); accepted=$false }
    )
    $outcomes = @($fixtures | ForEach-Object {
        $observed = Test-AirframeIdentity $_.model $_.env "x +   SYS_AUTOSTART [1028,1640] : $($_.actual)`n" $_.files
        [ordered]@{ name=$_.name; expected_acceptance=$_.accepted; observed=$observed;
            passed=$observed.verified -eq $_.accepted }
    })
    $proof = [ordered]@{ schema='drone_agricole.sitl_airframe_identity_tests.v1';
        created_at_utc=[DateTime]::UtcNow.ToString('o'); commands_published=$false;
        script_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
        fixtures=$outcomes; success=@($outcomes | Where-Object { -not $_.passed }).Count -eq 0 }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputAbsolute)) | Out-Null
    [IO.File]::WriteAllText($outputAbsolute, ($proof | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
    Write-Output "SITL_AIRFRAME_SELF_TEST=$outputAbsolute SUCCESS=$($proof.success)"
    if (-not $proof.success) { exit 1 }
    exit 0
}

$revision = Invoke-BoundedCommand 'git' @('rev-parse', 'HEAD')
$docker = Invoke-BoundedCommand 'docker' @('version', '--format', '{{json .}}')
$compose = Invoke-BoundedCommand 'docker' @('compose', 'version')
$composeArgs = @('compose', '-f', 'compose.yaml')
if ($ComposeOverride) { $composeArgs += @('-f', $ComposeOverride) }
$composeArgs += @('--profile', 'sim', '--profile', 'flight-test')
$configImages = Invoke-BoundedCommand 'docker' ($composeArgs + @('config', '--images'))
$engine = Invoke-BoundedCommand 'docker' @('info', '--format', '{{json .}}')
$identity = [ordered]@{ status = 'unavailable'; expected_service = $SitlService; expected_model = $ExpectedModel;
    expected_image = $ExpectedImage; source = 'docker_container_and_image_inspect'; commands_published = $false }
$violations = [Collections.Generic.List[string]]::new()
$available = $engine.exit_code -eq 0 -and -not $engine.timed_out
if ($available) {
    $containers = Invoke-BoundedCommand 'docker' ($composeArgs + @('ps', '-q', $SitlService))
    $containerId = $containers.stdout.Trim()
    if ($containerId -match '^[a-f0-9]{12,64}$') {
        $inspection = Invoke-BoundedCommand 'docker' @('inspect', $containerId)
        $imageInspection = Invoke-BoundedCommand 'docker' @('image', 'inspect', $ExpectedImage)
        if ($inspection.exit_code -eq 0 -and $imageInspection.exit_code -eq 0) {
            $container = @($inspection.stdout | ConvertFrom-Json)[0]
            $expected = @($imageInspection.stdout | ConvertFrom-Json)[0]
            $modelEnvironment = @($container.Config.Env | Where-Object { $_ -like 'PX4_SIM_MODEL=*' })
            if (-not $container.State.Running) { $violations.Add('sitl_container_not_running') }
            if ($container.Image -ne $expected.Id) { $violations.Add('running_image_differs_from_expected') }
            if ($modelEnvironment.Count -ne 1 -or $modelEnvironment[0] -ne "PX4_SIM_MODEL=$ExpectedModel") {
                $violations.Add('sitl_model_ambiguous_or_mismatched')
            }
            $autostartEnvironment = @($container.Config.Env | Where-Object { $_ -like 'PX4_SYS_AUTOSTART=*' })
            $expectedAutostart = if ($autostartEnvironment.Count -eq 1) {
                $autostartEnvironment[0].Substring('PX4_SYS_AUTOSTART='.Length)
            } else { '' }
            if ($autostartEnvironment.Count -ne 1) { $violations.Add('sitl_autostart_environment_ambiguous') }
            $parameter = Invoke-BoundedCommand 'docker' @('exec', $containerId,
                '/opt/px4-gazebo/bin/px4-param', 'show', 'SYS_AUTOSTART')
            $airframeFiles = @()
            if ($expectedAutostart -match '^[1-9][0-9]{0,8}$') {
                $listScript = 'for file in /opt/px4-gazebo/etc/init.d-posix/airframes/"$1"_*; do [ -f "$file" ] && printf "%s\n" "${file##*/}"; done'
                $listing = Invoke-BoundedCommand 'docker' @('exec', $containerId, 'sh', '-c', $listScript, 'sh', $expectedAutostart)
                if ($listing.exit_code -ne 0 -or $listing.timed_out) {
                    $violations.Add('sitl_airframe_listing_failed')
                }
                $airframeFiles = @($listing.stdout -split '\r?\n' | Where-Object { $_ -ne '' })
            }
            $parameterOutput = if ($parameter.exit_code -eq 0 -and -not $parameter.timed_out) { $parameter.stdout } else { '' }
            $airframeIdentity = Test-AirframeIdentity $ExpectedModel $expectedAutostart $parameterOutput $airframeFiles
            foreach ($problem in $airframeIdentity.violations) { $violations.Add($problem) }
            $mappedDevices = @($container.HostConfig.Devices | Where-Object { $null -ne $_ })
            if ($container.HostConfig.Privileged -or $mappedDevices.Count -ne 0) {
                $violations.Add('hardware_device_or_privileged_container_refused')
            }
            if ($container.HostConfig.NetworkMode -eq 'host') { $violations.Add('host_network_refused') }
            $identity.status = if ($violations.Count -eq 0) { 'verified_container' } else { 'refused' }
            $identity.container_id = $container.Id
            $identity.actual_image_id = $container.Image
            $identity.expected_image_id = $expected.Id
            $identity.repo_digests = $expected.RepoDigests
            $identity.model_environment = $modelEnvironment
            $identity.autostart_environment = $autostartEnvironment
            $identity.airframe = $airframeIdentity
            $identity.mounts = @($container.Mounts | Select-Object Source, Destination, RW)
            $identity.network_mode = $container.HostConfig.NetworkMode
            $identity.ports = $container.NetworkSettings.Ports
            $processes = Invoke-BoundedCommand 'docker' @('exec', $containerId, 'pgrep', '-a', '-x', 'px4')
            if ($processes.exit_code -ne 0 -or [string]::IsNullOrWhiteSpace($processes.stdout)) {
                $violations.Add('px4_process_not_observed'); $identity.status = 'refused'
            }
        } else { $violations.Add('image_or_container_inspection_failed') }
    } else { $violations.Add('single_sitl_container_not_available') }
} else { $violations.Add('docker_engine_unavailable') }

$sourceHashes = [ordered]@{}
foreach ($relative in @('compose.yaml', 'simulation/compose.cartographe.yaml', 'software/docker/Dockerfile', 'simulation/README.md',
    'simulation/px4_sitl/preflight.ps1', 'simulation/px4_sitl/airframes/40000_gz_cartographe',
    'simulation/gazebo/models/cartographe/model.sdf', 'simulation/gazebo/models/cartographe/dynamics_preview.json',
    'software/src/drone_agricole_px4_bridge/src/OffboardTest.cpp',
    'software/src/drone_agricole_px4_bridge/src/RunnerServer.cpp',
    'software/src/drone_agricole_px4_bridge/include/drone_agricole_px4_bridge/OffboardSafety.hpp')) {
    $sourceHashes[$relative] = (Get-FileHash -LiteralPath (Join-Path $workspace $relative) -Algorithm SHA256).Hash.ToLowerInvariant()
}
$evidence = [ordered]@{
    schema = 'drone_agricole.sitl_preflight.v1'; created_at_utc = [DateTime]::UtcNow.ToString('o');
    host = [ordered]@{ os = [Runtime.InteropServices.RuntimeInformation]::OSDescription;
        architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString();
        powershell_version = $PSVersionTable.PSVersion.ToString() };
    git_revision = $revision.stdout.Trim(); sources_sha256 = $sourceHashes;
    docker_available = $available; identity = $identity; violations = @($violations);
    limits = @('Container identity does not prove ROS telemetry freshness; inspect state and odometry before emission.',
        'No hardware devices or host network are accepted.', 'No container, parameter or historical runtime was modified.');
    commands = @($checks)
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputAbsolute)) | Out-Null
$temporary = $outputAbsolute + '.tmp'
[IO.File]::WriteAllText($temporary, ($evidence | ConvertTo-Json -Depth 30), [Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $temporary -Destination $outputAbsolute -Force
Write-Output "SITL_PREFLIGHT_RESULT=$outputAbsolute"
Write-Output "SITL_IDENTITY=$($identity.status)"
if ($RequireReady -and ($identity.status -ne 'verified_container' -or $violations.Count -gt 0)) { exit 2 }
exit 0
