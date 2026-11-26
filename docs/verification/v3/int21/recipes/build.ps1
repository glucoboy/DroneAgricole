param(
    [Parameter(Mandatory)][string]$Checkout,
    [Parameter(Mandatory)][string]$Run,
    [ValidateSet('Baseline','Recovery','Dependencies','NoCrypto','L3','L5','T0')]
    [string]$Phase,
    [int]$Jobs=4
)
$ErrorActionPreference='Stop'
$env:Path='C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$cmake='C:/msys64/ucrt64/bin/cmake.exe'
$ctest='C:/msys64/ucrt64/bin/ctest.exe'
$python='C:/msys64/ucrt64/bin/python.exe'
$freecad='C:/Program Files/FreeCAD 1.1/bin/python.exe'
$openssl='C:/msys64/ucrt64/bin/openssl.exe'
Set-Location -LiteralPath $Checkout
$null=New-Item -ItemType Directory -Force -Path "$Run/logs"
$shared=@('-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_STANDARD=17',
          '-DCMAKE_CXX_STANDARD_REQUIRED=ON','-DCMAKE_CXX_EXTENSIONS=OFF',
          '-DCMAKE_PREFIX_PATH=C:/msys64/ucrt64',"-DPython3_EXECUTABLE=$python",
          '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON')
function Invoke-Step($Name,$Exe,[string[]]$Argv,[int]$Expected=0) {
    $started=[datetime]::UtcNow.ToString('o')
    Write-Host "Starting $Name"
    & $Exe @Argv *> "$Run/logs/$Name.log"
    $code=$LASTEXITCODE
    @{
        argv=@($Exe)+$Argv; cwd=(Get-Location).Path; started_utc=$started
        finished_utc=[datetime]::UtcNow.ToString('o'); exit_code=$code
    } | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8NoBOM "$Run/logs/$Name.command.json"
    Write-Host "$Name exited $code"
    if ($code -ne $Expected) {
        Get-Content "$Run/logs/$Name.log" -Tail 45
        throw "$Name exited $code, expected $Expected"
    }
}
function Build-Component($Name,$Source,[string[]]$Options=@(),[string[]]$Targets=@()) {
    Invoke-Step "configure-$Name" $cmake (@('-S',$Source,'-B',"$Run/$Name")+$shared+$Options)
    Invoke-Step "build-$Name" $cmake (@('--build',"$Run/$Name",'--parallel',"$Jobs")+$Targets)
}
function Test-Component($Name,$Log,[string[]]$Filters=@(),[int]$Expected=0) {
    Invoke-Step $Log $ctest (@('--test-dir',"$Run/$Name",'--no-tests=error','--output-on-failure','-V','--output-junit',"$Run/logs/$Log.xml")+$Filters) $Expected
}
function Build-L3 { Build-Component 'l3' 'architecture_decision_engine' }
function Build-L5 {
    Build-Component 'l5' 'convergence_manager' @(
        "-DL5_FREECAD_PYTHON=$freecad","-DL5_L1_EXECUTABLE=$Run/l3/research/technical_research_core.exe",
        "-DL5_L3_EXECUTABLE=$Run/l3/architecture_decision_core.exe","-DL5_L4_EXECUTABLE=$Run/l4/validation_core.exe",
        "-DL5_T0_VALIDATOR=$Run/t0/cartographe-evidence.exe","-DL5_A5_OPENSSL_EXECUTABLE=$openssl",
        '-DL5_A5_PHYSICAL_TRUST_SHA256=')
}
switch ($Phase) {
    'Baseline' {
        Invoke-Step 'checkout' 'git' @('status','--porcelain=v1','--branch')
        Invoke-Step 'revision' 'git' @('rev-parse','HEAD')
        Build-L3
        Test-Component 'l3' 'baseline-l3' @('-R','^(l2_reconcile|technical_research_engine)$') 8
    }
    'Dependencies' {
        Build-Component 'l4' 'validation_engine'
        Build-Component 't0' 'simulation'
    }
    'NoCrypto' {
        Build-Component 'l5-no-crypto' 'convergence_manager' @(
            '-DCMAKE_DISABLE_FIND_PACKAGE_OpenSSL=TRUE','-DBUILD_TESTING=OFF','-DL5_A5_PHYSICAL_TRUST_SHA256='
        ) @('--target','convergence_core')
    }
    'L3' {
        Build-L3
        Test-Component 'l3' 'l3-full'
    }
    'L5' {
        Build-L5
        Test-Component 'l5' 'l5-full'
    }
    'T0' { Test-Component 't0' 't0-contracts' @('-R','^cartographe_(sitl_)?t0_contracts
    'Recovery' {
        Invoke-Step 'checkout' 'git' @('status','--porcelain=v1','--branch')
        Invoke-Step 'revision' 'git' @('rev-parse','HEAD')
        Build-L3
        Test-Component 'l3' 'l3-full'
        Build-Component 'l4' 'validation_engine'
        Build-Component 't0' 'simulation'
        Build-L5
        Test-Component 'l5' 'l5-full'
    }
}
) }
    'Recovery' {
        Invoke-Step 'checkout' 'git' @('status','--porcelain=v1','--branch')
        Invoke-Step 'revision' 'git' @('rev-parse','HEAD')
        Build-L3
        Test-Component 'l3' 'l3-full'
        Build-Component 'l4' 'validation_engine'
        Build-Component 't0' 'simulation'
        Build-L5
        Test-Component 'l5' 'l5-full'
    }
}
