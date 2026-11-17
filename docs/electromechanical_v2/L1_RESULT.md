# Reçu de validation L1

**L1_PASS** · `T-EM-ENGINE-L1` · Windows amd64 · 12 novembre 2026

24 tests L1 réussis, également rejoués sur compilation indépendante.
63 tests hors natif du moteur existant réussis. Les 137 empreintes CAO
actives concordent avec L0. Huit rapports hors ligne et un rapport HTTPS
passent le schéma L1. [Preuve structurée](../verification/technical_research_l1.json) ·
[DOC-VAL](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l1)

- [Inventaire des sources et questions](L1_CARTOGRAPHE.json) et [guide API/CLI](../../technical_research_engine/README.md)
- [Axe CAO F16 actif](examples_l1/F16-AXIS-ACTIVE.json) · [Plan USBFireWire A1](examples_l1/F16-PLAN-A1-LENGTH.json) · [Budget de longueur conditionnel](examples_l1/F16-LENGTH-BUDGET-A1.json)
- [Rayon de flexion du cordon monté, UNKNOWN](examples_l1/F16-MOUNTED-BEND-RADIUS.json) · [Borne de masse Basler v138, HTTPS](examples_l1/F16-CAMERA-MASS-BOUND-V138.json)

## Commandes exécutées

```powershell
$build = '.runtime/technical-research-l1/build'
cmake -S technical_research_engine -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $build --parallel 3
ctest --test-dir $build --output-on-failure
python -B -m unittest discover -s electromechanical_engine/tests -v

$bin = "$build/technical_research_core.exe"
$store = '.runtime/technical-research-l1/final'
$catalog = 'docs/electromechanical_v2/L1_CARTOGRAPHE.json'
$client = @('-B','-m','technical_research_engine','--executable',$bin,
            '--root','.','--store',$store,'--catalog',$catalog)
foreach ($id in (Get-Content -Raw -Encoding UTF8 $catalog | ConvertFrom-Json).questions.issue_id) {
    python @client submit $id --output "$store/$id.json"
}
python @client submit F16-AXIS-ACTIVE
python @client get F16-AXIS-ACTIVE
python @client list unknowns

$remoteStore = '.runtime/technical-research-l1/https-replay'
& $bin submit --root . --store $remoteStore --catalog $catalog --issue F16-CAMERA-MASS-BOUND-V138 --online --refresh
python -B -m technical_research_engine --executable $bin --root . --store $remoteStore get F16-CAMERA-MASS-BOUND-V138

$schema = 'docs/electromechanical_v2/RESEARCH_REPORT.schema.json'
Get-ChildItem -File "$store/*.json",'docs/electromechanical_v2/examples_l1/*.json' |
    Where-Object Name -NotLike 'report-*' |
    ForEach-Object { Test-Json -Path $_.FullName -SchemaFile $schema -FetchExternalReference }
Test-Json -Path docs/electromechanical_v2/EXAMPLE.json -SchemaFile docs/electromechanical_v2/DATA_CONTRACTS.schema.json
```

Le rejeu HTTPS natif a abouti avec accès réseau autorisé. La première
exécution, avec résolution DNS indisponible, avait finalisé `UNKNOWN` et
conservé le diagnostic. Les 10 tests natifs v1, les autres cibles et les
essais physiques restent hors de cette validation logicielle. Les rapports
exploitent les PDF et la CAO par leurs transcriptions ou mesures référencées.
