# GO3A V2.1 — préparation de GO3B

**`GO3A_EXPLORATION_READY`** — 17 novembre 2026. Trois familles **À valider**
sur copies privées hors tension du prototype sans dock. L’ordre retenu est
H-03, H-02, H-01. La réception indépendante renvoie `FINAL_NO_GO`. Les
conditions de réception et les décisions actives sont dans DOC-VAL,
DOC-MEC et DOC-ELEC. [Portefeuille machine](../verification/v21_go3a_candidates.json) ·
[Verrous et nomenclature candidate](../verification/v21_go3a_evidence_gaps.json) ·
[Décision courante](../architecture/HLD.md#methodologie) ·
[Résultats et limites](../VALIDATION_QUALIFICATION.md#cartographe-go3a-revise)

## Données communes

Copier l’actif byte-identique, racine `87eec083…`, à partir du gel
`3fc42609…`. La fermeture compte 137 fichiers FCStd et quatre auxiliaires.
La relecture native a résolu 2 772 occurrences. La matrice établit une
jointure double sens de **71 lignes, 53 axes et 56 associations**. Cinquante
lignes ont au moins un axe. Les 21 autres portent chacune leur motif et
restent dans le dénominateur documentaire. La BOM gelée contient 142
côtés. L’inventaire des circuits, les schémas CA01 et le contrat UART
servent de références électriques indépendantes. La relecture CAO fournit
des occurrences et des poses. La jointure au contact monté reste
**À valider**. [Rejeu des entrées](../verification/v21_go3a_reference_replay.json) ·
[Matrice complète](../verification/go3a/GO3A_INTERCONNECTION_MATRIX.csv) ·
[BOM des côtés](../verification/go3a/GO3A_CONNECTOR_BOM.csv)

Les zones `bay`, `above` et `sous_P66_emprise_stricte` sont celles du
modèle GO3A, dans son repère XYZ. Elles peuvent se recouvrir. Les valeurs
observées portent sur les axes, en mm. Chaque écart est calculé au sein
de son couple. L’actif est le seul point de départ des essais suivants.

| Couple | Longueur totale | En baie | Au-dessus | Sous P66 stricte | Z max gaine |
|---|---:|---:|---:|---:|---:|
| A → par faces | 10 885,079 → 10 788,378 | 4 221,879 → 3 860,643 | 2 051,213 → 1 802,043 | 451,202 → 451,202 | 170,278 → 170,278 |
| Actif → Consolidation Action 3 | 12 125,900 → 12 213,156 | 4 341,486 → 4 257,244 | 2 421,421 → 2 316,430 | 451,202 → 451,202 | 173,278 → 173,278 |

La consolidation diffère sur six FCStd communs et possède un P85
supplémentaire. Ses marges locales servent de témoins, avec leurs
tolérances et obstacles propres. [Zones](../verification/go3a/GO3A_SYSTEM_MODEL.json) ·
[Mesures des deux couples](../verification/go3a/GO3A_VARIANT_EVIDENCE.json)

## Essais autorisés

Chaque essai reprend les corrections documentées TELEM1, F35 au sud et
la réservation F25/P85. Il garde les fonctions, les références électriques,
les protections et la stabilité du porteur. Le registre G3A-01 à G3A-08
précise ce qu’il faut connaître avant un essai, ce que la copie peut
démontrer et ce qui relève du banc physique. Toute affectation GPIO/CSI,
population CA01 ou activation LED attend la preuve applicable. Les
sondes de connectique portent leur source, leur régime et leurs limites.
[Critères impératifs gelés](../verification/go3a/GO3A_REQUIREMENTS.yaml) ·
[Registre des preuves](../verification/v21_go3a_evidence_gaps.json)

| Famille et budget | Décision à matérialiser | Effet attendu et risque à mesurer |
|---|---|---|
| **H-03**, 5 h | Déplacer le lien de l’isolateur Waveshare sur un support indépendant réversible au chant P66. Accès direct aux deux ports, avec deux orientations dans une zone hors du balayage Action 3. PM08, PDB, CA01 et porteuse à la pose de référence. | Gain potentiel sur le service conjoint TTL/USB et CAN1. Vérifier les appuis, les reprises d’effort, le volume balayé par l’outil, la réserve et le nouvel axe des branches F40/F41. Le support ajoute du travail de conception et un poste massique. |
| **H-02**, 4 h | Comparer les sorties documentées de F16/M8 et l’USB-B coudé de F41. Fixer les portions stables par faces, comparer chant et chant/dessous, isoler les parties mobiles. L’isolateur conserve sa pose et le TTL reçoit une réservation de préconnexion. | Gain potentiel sur l’occupation supérieure et le retrait USB. Étudier le passage du cordon et de la ferrite ainsi que la disponibilité d’une référence de longueur et de régime adaptés. Si le gabarit TTL préconnecté avec son outil rencontre la PDB, arrêter cette configuration. |
| **H-01**, 3 h | Conserver les équipements et corridors retenus. Réserver le déport passif F40/F41 au chant ouest avec séparation des côtés, pose locale et accès courant. | Risque de raccordements et de réserve supplémentaires. Les deux sondes locales TTL/PDB déjà en collision sont exclues. Réserver l’USB et le TTL au même état de pose, mesurer l’effort sur les prises et vérifier l’isolement. |

Ces familles ne se combinent qu’après une nouvelle comparaison. La
combinaison réimplantation/déport modifie les volumes d’accès et le résultat
de service. La PDB 18139 latérale a recoupé F02_2 au témoin. Une
réimplantation de PM08 ou CA01 élargirait le périmètre à la chaîne d’énergie
ou de datation. Un adaptateur CAN1 sans paire documentée est écarté.
L’étude d’un PCB H-04 attend un défaut qui démontre une fonction
impossible avec ces trois approches.

Les volumes occupés, hauteurs avec fiches, marges, longueurs utiles,
masses, supports, opérations de maintenance et coûts des trois familles
restent inconnus. Les effets ci-dessous fixent les hypothèses à comparer
sur le périmètre commun.

| Mesure | H-03 | H-02 | H-01 |
|---|---|---|---|
| Congestion, volume, hauteur | Le module et le support occupent une zone latérale. Mesurer leur saillie ainsi que les volumes et axes dégagés en baie. | Le corridor inférieur peut dégager le dessus. Mesurer aussi l’emprise du coude, de la ferrite et des retenues. | Le module reste en place et le service sort au chant. Mesurer la place consommée par les terminaisons déportées. |
| Accès et maintenance | Accès direct visé, avec outillage et support à définir. | Accès USB à tester avec la préconnexion TTL locale et les gestes F16/M8. | Accès courant déporté, avec contrôle du montage et du remplacement des raccords locaux. |
| Longueur, masse et supports | Mesurer F40/F41 et la masse nette du support et des attaches. | Mesurer les longueurs utiles des cordons orientés et le coût massique des nouvelles retenues. | Mesurer les longueurs, les réserves et la masse des jonctions et retenues du déport. |
| Risque et coût d’intégration | Conception de support et validation des incidences après déplacement. | Sélection de cordons et validation caméra, fixation et accès local. | Conception des raccords, vérification pin à pin, isolement et intégrité du signal. |

Après filtre impératif, comparer d’abord l’accès conjoint
et l’absence de régression, puis le front de Pareto des objectifs communs
mesurés. En cas d’égalité, privilégier le plus petit nombre de
raccordements et de dépendances, puis le risque et le coût relatifs. La
priorité de construction favorise l’essai qui peut départager le plus
directement les causes d’obstruction. Le portefeuille fixe deux
configurations par famille, au plus un natif retenu par famille, 12 heures
et 0 € d’achat. Un échec sur les deux configurations arrête la famille.
[Méthode et mesures attendues](../verification/v21_go3a_candidates.json)

## Mise en œuvre sur copie

1. Vérifier les dépendances du portefeuille. Rejouer les demandes exactes
   sous la racine corrigée C avec le binaire scellé. Le champ `candidate_id`
   de V2.1 désigne le gel H-01. Le portefeuille lie chaque
   `portfolio_candidate_id` à ses décisions et au SHA-256 de la demande.
   Exiger le code 0, un reçu `EXPLORATION_ALLOWED` / `PLANNED`, huit écarts
   ouverts et le SHA de la demande. Une réponse de porte autorise la
   préparation de l’essai et vérifie ses gardes déclarées.
2. Préparer un témoin depuis l’actif et une copie indépendante pour
   chaque construction. Utiliser `workspace_guard.py stage` et `verify`
   avec la fermeture et les quatre auxiliaires de la preuve de référence.
   Relever support, pose, obstacles et cheminement effectifs avant toute
   édition. Les gabarits incertains sont des objets de criblage isolés.
   Le constructeur automatique `integrate` couvre le banc synthétique lié.
   Sur le cartographe, appliquer les mutations FreeCAD de façon explicite,
   avec les objets et les deux configurations du portefeuille.
3. Après tout déplacement, mettre à jour équipement → repères de ports →
   extrémités → axes et retenues. Vérifier aussi câble → occurrence →
   port/contact → conducteur et net après recalcul, sauvegarde et
   réouverture indépendante. Avec H-03, appliquer une même transformation
   aux deux ports de l’isolateur et aux volumes d’outil. Les autres
   extrémités de F40/F41 restent à leur équipement de référence.
4. Rejouer L2 `reconcile` et `inspect-cartographe` sur la référence.
   Produire la projection électrique indépendante de la copie et la
   soumettre à L2 `validate`. Pour L4 XLink, renseigner chemins, SHA et
   repères attendus de la copie dans la projection. Exécuter les tests
   communs et propres à la famille. Avec L4 XLink,
   conserver le périmètre B.2 et inclure les nouvelles paires. Les six
   intersections des enveloppes Airy et la paire F37_POS/P73 restent
   ouvertes. Pour chaque paire, produire la correction ou la preuve
   applicable du contact fonctionnel. Préserver les critères pendant
   la comparaison. Vérifier les reçus T0 du moteur et les SHA des copies.
   [Recette L4 B.2](../verification/v21_b2/coverage.json) ·
   [Jointure de connectique](02_CONNECTOR_RESOLUTION.md) ·
   [Contrat XLink](03_XLINK_VALIDATION.md)

Le passage en
réception exige la preuve indépendante attachée à un candidat intégré,
les critères impératifs couverts et l’admission versionnée. Les essais
physiques relèvent de GO4. [Contrat de porte](01_EXPLORATION_POLICY.md)

### Rejouer le préflight

Depuis la racine du dépôt sous Windows, avec Qt UCRT64 dans le `PATH`,
vérifier d’abord les SHA du portefeuille et de l’exécutable C qualifié.
Le rejet d’empreinte du worker dans l’arbre principal impose d’utiliser
la racine du gel corrigé C. Les sorties sont privées et distinctes.

```powershell
$release = (Resolve-Path '.runtime/fix-c').Path
$core = Join-Path $release '.runtime/build-l5-c2/convergence_core.exe'
$run = Join-Path $release ('.runtime/go3a-' + (Get-Date -Format yyyyMMddHHmmssfff))
New-Item -ItemType Directory -Path $run | Out-Null
foreach ($id in 'H-03', 'H-02', 'H-01') {
    $request = Join-Path $run "$id.json"
    Copy-Item -LiteralPath "docs/verification/v21_go3a/$id.json" -Destination $request
    & $core preflight --root $release --source-release v2.1 --mode explore `
        --plan $request --output (Join-Path $run $id)
    if ($LASTEXITCODE -ne 0) { throw "Préflight $id refusé" }
}
& $core preflight --root $release --source-release v2.1 --mode final `
    --output (Join-Path $run 'final')
if ($LASTEXITCODE -ne 2) { throw 'Résultat de réception inattendu' }
```

Vérifier `plan_sha256` et le verdict dans les reçus `preflight.json`.
Les opérations sont décrites par la version du portefeuille. Le binaire
C contrôle la demande V2.1 et ses gardes. La vérification de
`portfolio_candidate_id` et du SHA de `construction` incombe au
consommateur du portefeuille. [Requalification C](../VALIDATION_QUALIFICATION.md#requalification-v21-c)
