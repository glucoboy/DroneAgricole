# Interfaces et réception des lots L1 à L5

Périmètre `prototype_cartographe` sans dock. La recherche technique L1 et le catalogue, le validateur et le rapprochement documentaire L2 sont **Implémentés**. Le résultat L2 est conditionnel et le gel V2 complet reste **À valider**. Le [lot L3 de décision et d’exploration](L3_RESULT.md) est **Implémenté** sur bancs logiciels. Le [validateur indépendant L4](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l4) est **Implémenté** sur bancs et contrôles historiques ciblés. La [convergence L5](L5_RESULT.md) est **Implémentée** sur banc statique. La réalisation native du prototype reste **Planifiée**. Ces travaux contribuent à la complétude CAO et à la traçabilité des raccordements d’ORCH-CAO-MASSE-1. Les critères du prototype viennent de ses sources applicables. Les seuils synthétiques servent aux régressions des bancs.

## Interface exécutable existante

Depuis la racine, `python -B -m electromechanical_engine --help` décrit le moteur v1. Le [guide L2](../../interconnection_engine/README.md) décrit la CLI qui consomme le graphe V2 et produit la projection native du banc.

| Commande v1 | Entrées et sorties utiles |
|---|---|
| `probe` | `--freecad-python` avant la sous-commande ou `FREECAD_PYTHON`. JSON d’identité et de contrôle Part. Cables se vérifie par les tests natifs. |
| `extract --project ROOT --entry RELATIVE.FCStd --output NEW [--extra RELATIVE]` | Copie la fermeture XLink et les fichiers auxiliaires déclarés, recalcule, sauvegarde et réinspecte quand l’intégrité le permet. `extraction_report.json` et reçu de sources, avec états distincts d’inventaire, sauvegarde et réouverture. |
| `freeze --project INPUT --output NEW` | `system_model.json` et `design_requirements.yaml` v1, copie et reçu `reference_lock.json`. Aucun gel métier du prototype ne découle d’un gel de fixture. |
| `explore --project FROZEN --space SPACE --output NEW` | Espace de recherche v1, variantes et constats préliminaires. |
| `build --project FROZEN --candidate PROPOSAL --output NEW` | Proposition v1 et natif sauvegardé `candidate.FCStd`, reçu et rapport de candidat. La construction générique actuelle porte sur le banc de boîtes. |
| `validate --project FROZEN --candidate CANDIDATE --output NEW` | Candidat v1 monodocument avec reçu. Mesures réexécutées et rapport. Le worker écrit aussi des requêtes, résultats et traces dans le dossier candidat. Fournir une copie isolée lorsqu’il est conservé en lecture seule. |
| `run --project FROZEN --space SPACE --output NEW` | Tentatives et rapport de campagne. Corrections déclenchées par constat et sélection sur les objectifs comparables. |
| `compare --project FROZEN --baseline REPORT --candidate REPORT` | Comparaison sur référence et périmètre communs. La provenance du rapport se confirme en revalidant son natif. |

Les codes v1 sont interprétés avec le JSON finalisé. `0` indique une opération aboutie, `1` une erreur d’entrée ou d’exécution, `2` un natif d’extraction invalide ou un candidat non conforme pour `build`/`validate`, `3` une preuve insuffisante, une comparaison non admissible ou l’absence de candidat admis pour `run`. Pour `extract`, le code `2` peut conserver un inventaire complet. Conserver le statut détaillé de chaque tentative. Les contrats V2 séparent l’état d’exécution, le verdict du contrôle et la décision d’ingénierie.

## Contrats entre lots

Les sorties sont des dossiers versionnés et artefacts identifiés par empreinte. Chaque lot conserve les enregistrements entrants et enrichit les collections dont il a la responsabilité. Une correction d’une source ou d’une exigence donne lieu à une révision explicite. Les entrées incomplètes n’empêchent que les décisions qui en dépendent.

| Lot et dépendance | Entrées et sorties de contrat | Réemploi et tests de réception |
|---|---|---|
| **L1 — recherche technique.** L0. | [Catalogue](L1_CARTOGRAPHE.json) adossé aux sources du [manifeste L0](BASELINE_MANIFEST.json). `ResearchQuestion`, `TechnicalEvidence` et `Value` L0 dans un [rapport versionné](RESEARCH_REPORT.schema.json) avec registre des inconnues et recherche par `issue_id`. | [API et CLI](../../technical_research_engine/README.md), preuve exacte, variante refusée, révisions contradictoires, calcul conditionnel, fonctionnement hors ligne et parcours F16. [Résultat](L1_RESULT.md) |
| **Prérequis de L2/L3 — rapprochement et gel V2.** L0 et preuves L1 applicables. | Dossier V2 sourcé, rapprochement réversible lignes ↔ broches/circuits/cordons ↔ axes, repères, manifeste gelé et artefact d’exigences séparé. Gel distinct de l’actif et de la référence corrigée. | Réutiliser `FreeCADAdapter.extract`, `workspace_guard`, l’inventaire interconnexions et les règles de `freeze`. Couvrir 71 lignes et 53 axes, y compris absences légitimes de géométrie et cas AIRY/M8/W38. Tester XLink manquant, échappement, empreinte modifiée et embase contradictoire. Vérifier la fermeture réouvrable et son admission avant les contrôles géométriques. |
| **L2 — interconnexion et accouplement.** L0, L1 et graphe du périmètre contrôlé. | Révisions, preuves, continuité par contact, compatibilité, repères, dégagements et BOM candidate. Le [convertisseur](L2_RECONCILIATION.json) rapproche les lignes et axes existants. | [CLI](../../interconnection_engine/README.md), défauts injectés et réouverture du banc synthétique. `L2_CONDITIONAL` sur le prototype, dont les références montées et le graphe par broche restent ouverts. [Preuve](L2_RESULT.md) |
| **L3 — décision et exploration.** L0–L2 sur bancs synthétiques. | Conflits, marges, variantes, décisions, consolidation et objectifs comparables. | [Moteur et recette](../../architecture_decision_engine/README.md), [réception L3](L3_RESULT.md) et [périmètre dans DOC-VAL](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l3). |
| **Réalisation native — portée planifiée.** Graphe gelé, preuves L1 et verdicts d’interface L2 applicables. | Segments/corridors, poses, rayons, volumes de service et règles de compatibilité sourcés. Sorties `Candidate`, `HarnessSegment`, `Route`, artefacts natifs et reçu de construction isolée. Les hypothèses conditionnent l’admission. | Réutiliser le planificateur C++17 pour un graphe déclaré et les constructeurs Cables éprouvés pour l’adaptateur natif. Démontrer que toute dérivation conserve les circuits, que `unknown` n’autorise pas un partage et qu’une gaine commune ne duplique ni conducteur ni masse. Réception sur banc simple puis cas ciblé du prototype. Vérifier XLinks, repères, accouplement et passage du cordon préassemblé. Un calcul de section ou un échantillonnage de spline donne une borne ou un constat dans sa portée documentée. |
| **L4 — validation indépendante.** L0 à L3 et candidat sauvegardé. | Exigences, recette et outils gelés hors candidat. Rapports JSON avec projections L0, tolérances, couverture, matrice des preuves, empreintes et manifeste terminal T0. | [Recette](../../validation_engine/README.md) et [périmètre démontré](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l4). La course et le montage physiques, la réserve F41 et la cinématique continue F16 gardent des domaines de preuve ouverts. |
| **L5 — convergence et décision.** L0–L4. | Configuration, modèle et exigences gelés, budget et objectifs déclarés. Checkpoint, historique, rapport de sélection, verdict et au plus un natif consolidé avec preuve indépendante. | [CLI et API](../../convergence_manager/README.md), [preuve](L5_RESULT.md) et [périmètre validé](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l5). |

Garder les scripts Python FreeCAD éprouvés comme adaptateurs de l’outillage existant. Le moteur L1 utilise C++17 et Qt Core/Network, avec un client Python standard. Les échanges utilisent JSON, SHA-256 et des processus séparés.

## Reprise de L1

Pour rejouer L1, utiliser le [guide](../../technical_research_engine/README.md) et le [catalogue](L1_CARTOGRAPHE.json). Si une source gelée diffère, identifier la révision applicable et établir un nouveau référentiel pour le périmètre touché.

### Reprendre le rapprochement et le gel V2

Avant les contrôles natifs, vérifier `probe` et les contrôles Cables avec le Python FreeCAD local. Pour refaire l’inventaire natif de l’actif, utiliser cette commande existante sur un dossier neuf.

```powershell
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$work = '.runtime/electromechanical_v2-freeze-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
python -B -m electromechanical_engine --freecad-python $freecad probe
if ($LASTEXITCODE -ne 0) { throw 'Probe FreeCAD/Part en échec' }
python -B -m electromechanical_engine --freecad-python $freecad --timeout 180 extract `
  --project hardware/mecanique/cartographe `
  --entry assemblages/Prototype_Cartographe.FCStd --output "$work/extraction-active"
```

Examiner `extraction_report.json`, en particulier `inventory_complete`, `invalid_objects`, `save_performed` et `reopened`. Les quatre solides OEM invalides sont documentés sur l’actif d’après les preuves d’extraction existantes. Une copie consolidée réouvrable existe localement. Son emploi pour une mesure ciblée exige de conserver sa fermeture propre, sa provenance et la limite des réservations OEM. Aucun résultat L0 ne clôt GO 3 ou ne déclenche une opération sur le matériel.
