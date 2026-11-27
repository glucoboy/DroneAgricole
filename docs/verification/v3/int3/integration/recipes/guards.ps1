param(
    [Parameter(Mandatory)][ValidateSet('T1','T2','T3','Collect','Boundaries','A5','Sealed')][string]$Phase,
    [string]$Perturbation
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$python = 'C:/msys64/ucrt64/bin/python.exe'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$openssl = 'C:/msys64/ucrt64/bin/openssl.exe'
$checkout = (Resolve-Path -LiteralPath "$PSScriptRoot/../..").Path
$build = Join-Path $checkout '.runtime/b'
$run = $PSScriptRoot
$helpers = Join-Path $checkout 'docs/verification/v3/int21/recipes'
$core = "$build/l5/convergence_core.exe"
$l3 = "$build/l3/architecture_decision_core.exe"
$t0 = "$build/t0/cartographe-evidence.exe"
$campaign = "$run/c2"
Set-Location -LiteralPath $checkout

function Invoke-Step($Name, $Exe, [string[]]$Arguments) {
    $started = [datetime]::UtcNow.ToString('o')
    Write-Host "Exécution $Name"
    $log = "$run/logs/$Name.log"
    & $Exe @Arguments *> $log
    $code = $LASTEXITCODE
    @{
        argv = @($Exe) + $Arguments
        cwd = (Get-Location).Path
        started_utc = $started
        finished_utc = [datetime]::UtcNow.ToString('o')
        exit_code = $code
        log = ".runtime/r/logs/$Name.log"
        log_sha256 = (Get-FileHash -LiteralPath $log).Hash.ToLowerInvariant()
    } | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8NoBOM "$run/logs/$Name.command.json"
    Get-Content -LiteralPath $log -Tail 18
    if ($code -ne 0) { throw "$Name a retourné $code" }
}

$common = @('--core', $core, '--l3', $l3, '--freecad', $freecad, '--t0', $t0)
switch ($Phase) {
    { $_ -in 'T1', 'T2', 'T3' } {
        $command = @('-B', 'convergence_manager/tests/replay_v3_c2.py') + $common +
            @('--python', $python, '--output', $campaign, '--phase', $Phase)
        if ($Phase -eq 'T2') {
            $restriction = (Resolve-Path -LiteralPath $Perturbation).Path
            $sha = (Get-FileHash -LiteralPath $restriction).Hash.ToLowerInvariant()
            $command += @('--perturbation', $restriction, '--perturbation-sha256', $sha)
        }
        Invoke-Step "c2-$Phase" $python $command
    }
    'Collect' {
        Invoke-Step 'c2-review' $python @('-B', 'convergence_manager/tests/collect_v3_c2_evidence.py',
            '--campaign', $campaign, '--t0', $t0, '--output', "$run/c2-review")
        $review = Get-Content -LiteralPath "$run/c2-review/independent_review.json" -Raw | ConvertFrom-Json -AsHashtable
        if ($review.checks.Values -contains $false) { throw 'Revue C.2 incomplète' }
    }
    'Boundaries' {
        Invoke-Step 'c2-boundaries' $python (@('-B', 'convergence_manager/tests/test_v3_c2_boundaries.py') +
            $common + @('--t1', "$campaign/t1", '--output', "$run/c2-boundaries"))
        $retained = (Get-Content -LiteralPath "$campaign/t1/summary.json" -Raw | ConvertFrom-Json).retained.candidate_id
        Invoke-Step 'c2-native-faults' $python @('-B', 'convergence_manager/tests/test_v3_c2_native_faults.py',
            '--freecad', $freecad, '--profile', 'docs/electromechanical_v3/bench_c2_multiharness/profile.json',
            '--transaction', "$campaign/t1/T1/candidates/$retained/construction/transaction",
            '--output', "$run/c2-native-faults")
        New-Item -ItemType Directory -Path "$run/t0" | Out-Null
        Copy-Item -LiteralPath $t0 -Destination "$run/t0/cartographe-evidence.exe"
        if ((Get-FileHash -LiteralPath $t0).Hash -ne (Get-FileHash -LiteralPath "$run/t0/cartographe-evidence.exe").Hash) {
            throw 'Copie de lancement T0 divergente'
        }
        Invoke-Step 'integration-boundaries' $python @('-B', "$helpers/integration_boundaries.py", $run, $freecad, $core)
    }
    'A5' {
        Invoke-Step 'a5-adversarial' $python @('-B', 'convergence_manager/tests/test_v3_a5_authority.py',
            '--core', $core, '--openssl', $openssl, '--out', "$run/a5-adversarial.json")
        Invoke-Step 'a5-no-crypto' $python @('-B', "$helpers/a5_no_crypto.py",
            $core, "$build/l5-no-crypto/convergence_core.exe", $openssl, "$run/a5-no-crypto.json")
    }
    'Sealed' {
        Invoke-Step 'sealed-proofs' $python @('-B', "$run/regressions.py", 'sealed',
            "$build/l3/research/technical_research_core.exe", "$build/l3/interconnection/interconnection_core.exe")
    }
}
