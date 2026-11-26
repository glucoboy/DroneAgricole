param(
    [Parameter(Mandatory)][string]$Checkout,
    [Parameter(Mandatory)][string]$Run,
    [ValidateSet('T1','T2','T3','Boundaries','Collect','A5','T0')]
    [string]$Phase,
    [string]$Perturbation,
    [string]$HelperDirectory=$PSScriptRoot
)
$ErrorActionPreference='Stop'
$env:Path='C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$python='C:/msys64/ucrt64/bin/python.exe'
$freecad='C:/Program Files/FreeCAD 1.1/bin/python.exe'
$openssl='C:/msys64/ucrt64/bin/openssl.exe'
$ctest='C:/msys64/ucrt64/bin/ctest.exe'
$helpers=(Resolve-Path -LiteralPath $HelperDirectory).Path
Set-Location -LiteralPath $Checkout
$core="$Run/l5/convergence_core.exe"
$l3="$Run/l3/architecture_decision_core.exe"
$t0="$Run/t0/cartographe-evidence.exe"
$campaign="$Run/c2"
function Invoke-Step($Name,$Exe,[string[]]$Argv) {
    $started=[datetime]::UtcNow.ToString('o')
    Write-Host "Starting $Name"
    & $Exe @Argv *> "$Run/logs/$Name.log"
    $code=$LASTEXITCODE
    @{
        argv=@($Exe)+$Argv; cwd=(Get-Location).Path; started_utc=$started
        finished_utc=[datetime]::UtcNow.ToString('o'); exit_code=$code
    } | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8NoBOM "$Run/logs/$Name.command.json"
    Get-Content "$Run/logs/$Name.log" -Tail 16
    if ($code -ne 0) { throw "$Name exited $code" }
}
$common=@('--core',$core,'--l3',$l3,'--freecad',$freecad,'--t0',$t0)
switch ($Phase) {
    {$_ -in 'T1','T2','T3'} {
        $command=@('-B','convergence_manager/tests/replay_v3_c2.py')+$common+
            @('--python',$python,'--output',$campaign,'--phase',$Phase)
        if ($Phase -eq 'T2') {
            $restriction=(Resolve-Path -LiteralPath $Perturbation).Path
            $sha=(Get-FileHash -LiteralPath $restriction -Algorithm SHA256).Hash.ToLowerInvariant()
            $command+=@('--perturbation',$restriction,'--perturbation-sha256',$sha)
        }
        Invoke-Step "c2-$Phase" $python $command
    }
    'Boundaries' {
        Invoke-Step 'c2-boundaries' $python (@('-B','convergence_manager/tests/test_v3_c2_boundaries.py')+
            $common+@('--t1',"$campaign/t1",'--output',"$Run/c2-boundaries"))
        $retained=(Get-Content "$campaign/t1/summary.json" -Raw | ConvertFrom-Json).retained.candidate_id
        Invoke-Step 'c2-native-faults' $python @('-B','convergence_manager/tests/test_v3_c2_native_faults.py',
            '--freecad',$freecad,'--profile','docs/electromechanical_v3/bench_c2_multiharness/profile.json',
            '--transaction',"$campaign/t1/T1/candidates/$retained/construction/transaction",
            '--output',"$Run/c2-native-faults")
        Invoke-Step 'integration-boundaries' $python @('-B',"$helpers/integration_boundaries.py",$Run,$freecad,$core)
    }
    'Collect' {
        Invoke-Step 'c2-review' $python @('-B','convergence_manager/tests/collect_v3_c2_evidence.py',
            '--campaign',$campaign,'--t0',$t0,'--output',"$Run/c2-review")
        $review=Get-Content "$Run/c2-review/independent_review.json" -Raw | ConvertFrom-Json -AsHashtable
        if ($review.checks.Values -contains $false) { throw 'Revue C.2 incomplète' }
    }
    'A5' {
        Invoke-Step 'a5-adversarial' $python @('-B','convergence_manager/tests/test_v3_a5_authority.py',
            '--core',$core,'--openssl',$openssl,'--out',"$Run/a5-adversarial.json")
        Invoke-Step 'a5-no-crypto' $python @('-B',"$helpers/a5_no_crypto.py",
            $core,"$Run/l5-no-crypto/convergence_core.exe",$openssl,"$Run/a5-no-crypto.json")
    }
    'T0' {
        Invoke-Step 't0-sitl-direct' $t0 @('self-test-sitl')
        Invoke-Step 't0-contracts' $ctest @('--test-dir',"$Run/t0",'--no-tests=error',
            '-R','^cartographe_(sitl_)?t0_contracts$','--output-on-failure')
    }
}
