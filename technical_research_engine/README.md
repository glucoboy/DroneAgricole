# Moteur de recherche technique L1

Depuis la racine du dépôt, compiler avec CMake, un compilateur C++17 et Qt 6
Core et Network. Python 3 et sa bibliothèque standard fournissent le client et
les tests. Le moteur n’a besoin ni de FreeCAD ni de son RPC.

```powershell
$build = '.runtime/technical-research-l1/build'
cmake -S technical_research_engine -B $build -G Ninja -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $build
ctest --test-dir $build --output-on-failure
$bin = "$build/technical_research_core.exe"
$store = '.runtime/technical-research-l1/reports'
$catalog = 'docs/electromechanical_v2/L1_CARTOGRAPHE.json'
$client = @('-B', '-m', 'technical_research_engine', '--executable', $bin,
            '--root', '.', '--store', $store, '--catalog', $catalog)
python @client submit F16-AXIS-ACTIVE
python @client get F16-AXIS-ACTIVE --output "$store/F16-AXIS-ACTIVE.json"
python @client submit F16-MOUNTED-BEND-RADIUS
python @client list evidence
python @client list unknowns
python @client submit F16-CAMERA-MASS-BOUND-V138 --online --refresh
```

Sur une autre installation, adapter le chemin Qt, le générateur et le nom de
l’exécutable. `submit` crée le registre. `--output` écrit le JSON UTF-8 dans
un fichier neuf d’un dossier existant. La CLI renvoie aussi le résultat sur
la sortie standard. Le code 0 signifie rapport finalisé, y compris pour une
inconnue. Le code 1 indique une erreur d’entrée, d’intégrité ou d’exécution.
Le code 3 indique une question ou un rapport absent ou des entrées périmées.

## Appeler le service depuis le moteur de décision

```python
from technical_research_engine import ResearchEngine, ResearchEngineError

engine = ResearchEngine(
    root=".",
    store=".runtime/technical-research-l1/reports",
    executable=".runtime/technical-research-l1/build/technical_research_core.exe",
    catalog="docs/electromechanical_v2/L1_CARTOGRAPHE.json",
)
report = engine.submit_issue("F16-AXIS-ACTIVE")
current = engine.get_issue("F16-AXIS-ACTIVE")
if current["outcome"] == "RESOLVED":
    value = current["value"]
else:
    remaining = current["unknown_register"]
```

`ResearchEngineError` expose `returncode` et `response`. Les méthodes
`list_reports()`, `list_evidence()` et `list_unknowns()` renvoient
`items`, `stale_issue_ids` et `invalid_reports`. Appeler
`invalidate_issue(issue_id)` ou `submit_issue(issue_id, refresh=True)` pour
rejouer une investigation. L’empreinte du catalogue et celles des sources
locales rattachent le cache à la configuration et à la définition du
composant. Une modification locale rend le rapport périmé. La fraîcheur d’une
publication distante se vérifie en relançant avec `online=True, refresh=True`.

## Déclarer une investigation

Le [catalogue cartographe](../docs/electromechanical_v2/L1_CARTOGRAPHE.json)
fournit des entrées utilisables. Le catalogue se trouve sous `--root` et
porte `schema_version: "1.0.0"`, `configuration_id`, `questions` et
`sources`. Ajouter une question avec un `issue_id` stable, l’objet
`question` L0 ouvert, le paramètre, l’unité, la criticité, l’identité, le
domaine, l’autorité attendue et une étude paramétrique. Les attributs
d’identité décrivent la variante, la connectique, l’orientation et les
autres différences pertinentes. Les conditions précisent le montage, le
régime et les températures applicables. La comparaison de ces champs est
exacte. Une révision matérielle nulle laisse l’applicabilité ouverte.

Pour une source locale, indiquer le chemin relatif, l’empreinte attendue si
la source est gelée et le localisateur précis. `JSON_POINTER` prélève un
scalaire avec des vérifications dans la branche du composant.
`TEXT_REGEX` prélève une capture unique dans un passage contenant la
référence exacte. Une capture de PDF ou de CAO peut être déclarée via un
registre de transcription ou de mesure qui cite le natif et le
localisateur. La découverte locale bornée peut signaler des pistes par
nom de fichier ou mention dans un texte. Les PDF et natifs CAO découverts
sont signalés par leur nom. Les pistes apparaissent dans les diagnostics
jusqu’à ce qu’une extraction et une provenance soient renseignées.

Pour la recherche distante, ajouter les URL HTTPS de documentation
publique au catalogue et utiliser `--online`. Le moteur examine les sources
locales en premier, puis les URL pertinentes du fabricant avant les
sources secondaires. Le catalogue sert de liste de documents à
interroger. Les pages et documents intégraux restent dans leurs sources.
Un document manquant ou une erreur réseau figure dans les diagnostics.

`LENGTH_DIFFERENCE` calcule `length_difference` en mm avec `available` et
`required`. `CIRCULAR_SECTION_AREA` calcule `circular_section_area` en
mm² avec `diameter`. Déclarer les entrées en mm, leur demi-largeur
d’incertitude, les hypothèses et les limites. Le rapport conserve les
bornes extrêmes et les pointeurs L0 vers les entrées. Un calcul avec ces
hypothèses laisse la question ouverte sous `CONDITIONAL`.

Le [schéma de rapport](../docs/electromechanical_v2/RESEARCH_REPORT.schema.json)
réutilise `ResearchQuestion`, `TechnicalEvidence` et `Value` de L0. Utiliser
la `value` du rapport et son `outcome` pour consommer la conclusion.
`evidence_details` garde aussi les transcriptions hors périmètre et les
révisions contradictoires. La clôture exige au moins une preuve exacte
et l’absence de contradiction comparable. Le rapport ne produit aucun
verdict de validation `PASS`. Voir les [résultats](../docs/electromechanical_v2/L1_RESULT.md).
