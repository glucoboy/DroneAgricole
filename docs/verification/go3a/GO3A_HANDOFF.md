# GO3A — reprise de la configuration H-01

**GO3A_CONDITIONNEL · À valider.** H-01 est la seule configuration retenue pour
l’instruction. Elle conserve le prototype X650 sans dock, ses équipements et
ses protections, avec des corridors séparés, des corrections ciblées
d’interface et un accès de diagnostic passif déporté à démontrer. Le registre
préserve les 71 identités de liaison. L’admission de GO3B reste suspendue à la
fermeture des points critiques ci-dessous. [Décisions et dépendances](GO3A_DECISIONS.json)

## Entrées et reproduction du gel

| Entrée | Usage |
|---|---|
| [Modèle système](GO3A_SYSTEM_MODEL.json) | Baseline active, fermeture XLink et SHA-256, parc BOM, groupes physiques cibles, chemins orientés et jonctions. |
| [Matrice d’interconnexion](GO3A_INTERCONNECTION_MATRIX.csv) | État et contrôle de clôture individuels pour 71 lignes. `liaison_id` est la clé de jointure. |
| [BOM des interfaces](GO3A_CONNECTOR_BOM.csv) | Côtés A/B, références documentées ou candidates, broches, repères, enveloppes et données manquantes. |
| [Recherche](GO3A_RESEARCH.json) | Sources, hypothèses réfutées et questions L1. |
| [Exigences](GO3A_REQUIREMENTS.yaml) | Critères impératifs et métriques communes. |
| [Variantes](GO3A_VARIANTS.md) · [Preuves de criblage](GO3A_VARIANT_EVIDENCE.json) | Mesures comparables par paire, rejeux L3, raisons des rejets et portée des hypothèses. |
| [Reçu de campagne](GO3A_MANIFEST.json) | Versions, commandes, empreintes, contrôles, limites et verrou du moteur. |

Depuis la racine, créer un nouvel espace de travail. Les deux copies
intermédiaires portent les noms qu’attend la commande `freeze`.

```powershell
$go3aPack = 'docs/verification/go3a'
$go3aWork = '.runtime/go3a-rejeu-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
New-Item -ItemType Directory -Path "$go3aWork/entrees" | Out-Null
Copy-Item "$go3aPack/GO3A_SYSTEM_MODEL.json" "$go3aWork/entrees/system_model.json"
Copy-Item "$go3aPack/GO3A_REQUIREMENTS.yaml" "$go3aWork/entrees/design_requirements.yaml"
python -B -m electromechanical_engine freeze --project "$go3aWork/entrees" --output "$go3aWork/gel"
```

Comparer `reference_sha256` et les deux empreintes du reçu au manifeste. Le
champ `frozen_at_utc` dépend de l’exécution. Vérifier aussi les empreintes
SHA-256 de `cad.native_sha256` avant de recréer une copie de la référence.
Un écart exige l’identification des entrées changées et une nouvelle décision
de campagne. L’assemblage racine a la même empreinte que celui du témoin
Action 3, avec six dépendances différentes et P85 uniquement dans le témoin.
Conserver ces deux identités en comparant les mesures.

Le contrôle de fermeture XML du natif actif couvre 137 FCStd et les quatre
auxiliaires déclarés. Le contrôle d’ouverture a complété onze chargements
partiels. L’extraction BRep avec `extract` a expiré dans l’inventaire et
la boucle de sauvegarde puis réouverture n’a pas livré de résultat.
Le contrat v1 sert au gel du dossier. La campagne cible n’utilise pas le
constructeur monodocument à boîtes sur le graphe complet.

Le rejeu à l’identique du criblage diagnostic dépend du témoin Action 3 et
de l’adaptateur de mesure conservés localement sous `.runtime`. Le rapport
de criblage donne leurs empreintes, les ancrages, les axes, les sections et
les douze cas. Pour reproduire la méthode, isoler la fermeture XLink de ce
témoin, déployer les boîtes depuis les faces déclarées, tester la séparation
de leurs boîtes englobantes puis le volume commun BRep. Exclure uniquement
les deux cordons en reprise et le corps de l’isolateur. Contrôler les
empreintes avant et après. La translation concerne la sonde seule et les
boîtes ne représentent ni le connecteur réel ni son outil.

## Verrous de réception GO3B

| Verrou | Condition à démontrer avant engagement |
|---|---|
| `G3A-01` · retours et broches | Rejouer la réconciliation et identifier les révisions et matrices des interfaces critiques, dont W12/TELEM1. Démontrer, sur témoin autorisé, la méthode de rattachement d’un graphe électrique indépendant à une fermeture XLink. Affectations OEM et données manquantes par liaison dans les deux CSV. |
| `G3A-02`, `G3A-05` · baie | Lever dans une seule réservation F31/CAN1, F35, PM08, isolateur et sorties diagnostic. Mesurer les références précises, puis modéliser sorties, verrou, outil, réserve et séquence de pose. Les 0,120 mm nominaux près de F31 concernent un outil candidat et un geste supposé. L’intersection du gabarit TTL avec la PDB laisse la manœuvre ouverte. Démontrer les accès conjoints et l’isolement dans les situations de maintenance, y compris le raccordement d’un outil référencé à la masse du banc. |
| `G3A-03` · temps | Identifier l’instance physique d’Orin GPIO sur la porteuse, valider la référence IO et décider du peuplement R530–R533. Vérifier continuité et cohérence de W23 (AIRY/AIRY_SYNC) et W24.A/B/C (F24A/B/C). |
| `G3A-04` · F16/M8 | Obtenir un cordon et ses fiches compatibles, une longueur utile couvrant retenues et réserve, la plage de rotations/translations réelle et le rayon de flexion applicable. Cribler l’enveloppe continue des deux cordons avec optique, P10/P17/P73, F25 et F35. |
| `G3A-06`, `G3A-07` · porteur et périphérie | Vérifier montage, charges et chemins d’efforts pour P75/P85/X650, géométrie GNSS G4 et accouplement SMA, câbles de bras, BMS/NTC, FAN et SSD/CSI. Arrêter la décision LED avant mise sous tension et documenter le périmètre de fonctions réellement conservées. |
| `G3A-08` · intégrité et bilan | Démontrer sur témoin la chaîne de validation indépendante des natifs liés et geler les critères de réception pour le périmètre, avec règles massiques et seuils sourcés. |

Pour la réception du futur candidat GO3B, consolider sur une seule copie et
contrôler les poses et dépendances résolues après sauvegarde et réouverture.
Appliquer la revue indépendante A–D et les contrôles bidirectionnels entre
le graphe électrique et la totalité des natifs concernés. Comparer les
mesures au même périmètre et compléter bilan masse/centrage, protections
et maintenabilité.

Si l’un des contrôles réfute H-01, revenir à la décision ou à l’exigence
affectée et geler à nouveau les entrées. Le premier essai discriminant côté
diagnostic est la mesure de la géométrie réelle du bornier isolé et de son
cordon, suivie du criblage de pose avec PDB, PM08, CAN1 et outils présents.

## Mesures matérielles réservées à GO4

Préparer un protocole avec références et révisions inspectées, critères et
répétitions approuvés. Vérifier manipulation réelle des prises, tenue des
retenues et de la structure sous effort/vibration, flexion et fatigue de F16
et du M8, thermique et CEM sous charge, intégrité USB, CAN et datation, puis
mesurer masse et centrage. La continuité, la polarité et l’isolement du BMS
se vérifient selon son contrat avant une mise sous tension. La progression
des preuves reste celle de [DOC-VAL §2](../../VALIDATION_QUALIFICATION.md#2-progression-des-essais).
