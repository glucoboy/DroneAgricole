# Moteur électromécanique

Depuis la racine du dépôt, utiliser Python 3.11 ou supérieur. Le moteur utilise la bibliothèque standard et les utilitaires FreeCAD du dépôt. Le fichier d’exigences d’exemple utilise le sous-ensemble JSON de YAML. Pour les autres syntaxes YAML, utiliser un Python disposant de PyYAML et mettre les dates entre guillemets.

La construction et la mesure natives requièrent le Python de FreeCAD avec Part, les composants Draft et Cables Workbench. Les commandes natives s’exécutent dans des processus dédiés en mode offscreen. Le contrôle MCP se fait séparément dans Codex avec `get_rpc_status`. Si le RPC refuse la connexion, vérifier Part avec `probe`, puis exécuter les tests natifs pour vérifier Cables. Un refus de connexion ou un processus expiré apparaît comme un échec de cette phase. Après un timeout MCP sur une mutation, examiner l’état de la session avant toute relance.

## Rejouer le banc synthétique

```powershell
$env:FREECAD_PYTHON = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$fixture = 'electromechanical_engine/tests/fixtures/banc'
$work = '.runtime/moteur-cablage-demo-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
python -B -m electromechanical_engine probe
python -B -m electromechanical_engine freeze --project $fixture --output "$work/reference"
python -B -m electromechanical_engine explore --project "$work/reference" --space "$fixture/design_space.json" --output "$work/explore"
python -B -m electromechanical_engine run --project "$work/reference" --space "$fixture/design_space.json" --output "$work/run"
python -B -m electromechanical_engine validate --project "$work/reference" --candidate "$work/run/lateral" --output "$work/revalidation"
python -B -m electromechanical_engine compare --project "$work/reference" --baseline "$work/run/lateral-large/candidate_report.json" --candidate "$work/revalidation/candidate_report.json"
```

Utiliser un dossier de travail neuf à chaque reprise. En cas d’interruption, conserver le dossier précédent. Consulter `campaign_context.json`, les tentatives déjà finalisées sous `attempts/` et les rapports individuels. `campaign_report.json` est écrit après la fin du traitement. Relancer avec les mêmes entrées vérifiées dans un dossier neuf.

`build --project <référence> --candidate <explore/variante.json> --output <nouveau-dossier>` construit une variante seule. `extract --project <racine-cao> --entry <assemblage-relatif.FCStd> --output <nouveau-dossier>` copie les dépendances XLink, recalcule et sauvegarde la copie, puis l’inspecte après réouverture. Ajouter `--extra <fichier-relatif>` pour chaque dépendance auxiliaire connue. Limiter ce chemin à des fichiers FreeCAD de confiance, dont les proxies natifs peuvent exécuter du code. La copie conserve la disposition relative des XLinks et refuse une référence hors de la racine. `--timeout` avant la sous-commande règle le délai par processus. Le moteur peut écrire des journaux de mesure dans le dossier du candidat construit.

### Observer les connecteurs du cartographe

Avec le Python embarqué de FreeCAD et Cables 0.3.7, lancer depuis la racine
du dépôt. Choisir un dossier de sortie neuf et disposer du natif du
prototype avec sa fermeture XLink et sa source locale USBFireWire.

```powershell
python -B -m electromechanical_engine.connector_native `
  .runtime/v21-connector-native/rejeu `
  --freecad 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
```

L’option `--reconciliation` accepte un rapport `reconcile` du moteur L2
régénéré pour le même prototype. `copie/experiment.json` liste les
empreintes des entrées. `connector_native.json` relie les axes, les côtés
électriques et les occurrences lues dans cette copie. `freecad.log`
contient les diagnostics du processus dédié. Le modèle candidat de la
fiche USB Micro-B Up est issu du STEP et son déplacement lié à la caméra
est exercé en mémoire. Les mesures du corps, du retrait et de l’accès aux
vis s’interprètent avec les hypothèses et limites du rapport. Le banc
de référence pour les liaisons à des contacts natifs se rejoue avec
[le banc synthétique L2](../hardware/mecanique/banc_interconnexion/README.md).

Si une géométrie invalide empêche la sauvegarde, `extract` renvoie le code 2
et écrit l’inventaire dans `extraction_report.json`. Lire séparément
`inventory_complete`, `save_performed`, `reopened` et `invalid_objects`.

## Rejouer le banc mobile

```powershell
$env:FREECAD_PYTHON = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$fixture = 'electromechanical_engine/tests/fixtures/banc_mobile'
$work = '.runtime/moteur-cablage-mobile-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
python -B -m electromechanical_engine freeze --project $fixture --output "$work/reference"
python -B -m electromechanical_engine run --project "$work/reference" --space "$fixture/design_space.json" --output "$work/run"
python -B -m electromechanical_engine validate --project "$work/reference" --candidate "$work/run/corrige" --output "$work/revalidation"
```

Le référentiel gèle les poses absolues des ports et les translations des
obstacles dans `geometry.motion_states`. Les exigences associent chaque
liaison aux états à contrôler et fixent la tolérance de conservation de la
longueur développée. Le candidat propose seulement ses axes dans
`motion_routes`. Chaque axe est sauvegardé comme câble Cables distinct et
mesuré après réouverture. La réserve géométrique est la longueur développée
moins la corde entre les ports. Le mouvement entre les poses et la réserve
effectivement utilisable sous contrainte demandent d’autres essais.

Pour une portée sans retenue, le référentiel identifie les ports retenus et
les stations dans `geometry.anchors[].retentions`. Il fixe le point,
l’enveloppe, l’épaisseur `capture_wall_mm` et leur source. Le contrôle mesure
le contact, la fermeture de la couronne de matière, l’ancrage au porteur et
l’enveloppe d’accès. La portée suit l’axe natif entre stations, en comptant
les extrémités. Le banc emploie une boîte percée selon X
(`through_bore_x`) pour représenter la retenue fermée.

## Préparer une campagne

- Décrire objets, ports, liaisons et corridors dans `system_model.json`. Préparer `design_requirements.yaml` depuis les sources autorisées. Utiliser `null` pour une valeur inconnue et distinguer données mesurées, documentées, calculées, estimées et hypothèses. Les dimensions du banc sont des valeurs de test.
- Geler ces deux fichiers avec `freeze`. Le reçu contient les SHA-256 des octets et l’heure UTC. Donner aux rôles de construction et de validation le chemin explicite de cette référence. Conserver son empreinte par un canal indépendant si les auteurs des candidats ont accès en écriture au même système de fichiers. Une révision des exigences nécessite un nouveau gel.
- Définir le budget, les variantes et les corrections dans `design_space.json`. Les corrections associent une variante antérieure à des codes de défaut. Le constructeur réalise les routes sur le référentiel géométrique de boîtes et les relit comme objets Cables natifs. L’extraction d’un assemblage lié fournit un inventaire. L’import métier des ports, corridors et contraintes de cet assemblage demande un mapping explicite.
- Examiner `campaign_report.json`, les `candidate_report.json`, les observations et les vues SVG. Les SVG projettent des axes et des enveloppes englobantes sur un cadre partagé. Les mesures de zones et de quantile d’altitude peuvent rester inconnues sur certains parcours courbes. Utiliser `compare` avec les rapports issus du moteur et un même référentiel. Les SHA-256 du reçu contrôlent la cohérence des entrées et du natif. Ils ne sont pas des signatures d’auteur.
- Pour `validate`, le natif du banc doit tenir dans un seul document. Tout solide doit correspondre à un objet inventorié ou à une pose mobile déclarée et vérifiée. Un lien de propriété vers un autre objet ne dispense pas ce dernier du contrôle. Utiliser `extract` pour inventorier les assemblages historiques liés.
- Pour classer deux candidats, `compare` exige leurs constats de réouverture, recalcul, intégrité des solides et liens, et couverture des paires. Les écarts de métriques restent consultables quand les rapports ont un périmètre commun. Pour vérifier leur provenance, relancer `validate` sur chaque natif avec le référentiel gelé.

Les commandes renvoient du JSON. Le code `0` signale l’opération aboutie, avec un candidat admissible pour `run`, `build` et `validate`. Le code `1` indique une erreur d’entrée ou d’exécution, `2` un candidat non conforme ou une extraction native invalide, et `3` une preuve ou une comparaison insuffisante. Le rapport de campagne conserve les échecs intermédiaires même en présence d’un candidat admissible.

## Exécuter les tests

Les tests hors ligne s’exécutent avec le Python système. Le chemin ci-dessous
active aussi les tests d’intégration, lesquels démarrent le Python FreeCAD
dans des processus dédiés. Sans cette variable, les tests natifs sont ignorés.

```powershell
python -B -m unittest discover -s electromechanical_engine/tests -p 'test_contracts.py' -v
python -B -m unittest discover -s electromechanical_engine/tests -p 'test_validation.py' -v
python -B -m unittest discover -s electromechanical_engine/tests -p 'test_search.py' -v
$env:ELECTROMECHANICAL_FREECAD_PYTHON = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
python -B -m unittest discover -s electromechanical_engine/tests -p 'test_freecad.py' -v
```

## Rejouer la qualification indépendante

Activer `ELECTROMECHANICAL_FREECAD_PYTHON` comme ci-dessus, puis exécuter la
suite complète et les deux recettes de banc. Pour comparer deux réouvertures
du même candidat, relancer `validate` dans deux dossiers de sortie neufs et
comparer leurs `candidate_report.json`.

```powershell
python -B -m unittest discover -s electromechanical_engine/tests -v
$work = '.runtime/go2-natifs-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
python -B -m electromechanical_engine.qualification.native_replay $env:ELECTROMECHANICAL_FREECAD_PYTHON $work
```

Le rejeu historique vérifie les dépendances et travaille sur des copies
privées. Un code 3 indique une preuve partielle ou non reproductible.
Consulter les erreurs de paire, les rapports et les journaux par passage.
Voir les [résultats de qualification](../docs/VALIDATION_QUALIFICATION.md#qualification-moteur-go2)
pour les entrées et limites de la campagne.

Les mesures électriques, la cinématique continue, le passage de connecteurs préassemblés, le regroupement avec packing, la tenue des retenues, la fatigue, la vibration, la thermique et la CEM demandent des données ou des contrôles complémentaires. Le verdict géométrique couvre le référentiel, les objets et les états observés. Consulter l’[état de développement](DEVELOPMENT_STATUS.md) pour les preuves et travaux ouverts.
