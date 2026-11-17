# API FreeCAD, mesures et repli

Lire cette référence avant génération, recalcul ou contrôle BRep. Les chemins
ci-dessous sont des **observations de l’environnement de référence**, pas des
chemins imposés aux autres projets. Redécouvrir les versions et propriétés à
chaque installation ; les noms des équipements du drone ne sont pas utilisés.

## Installation inspectée le 27 octobre 2026

- FreeCAD **1.1.3**, `C:/Program Files/FreeCAD 1.1/bin/python.exe` (Python 3.11).
- Cables **0.3.7**, dans
  `C:/Users/Utilisateur/AppData/Roaming/FreeCAD/v1-1/Mod/Cables/freecad/cables/`.
- Paquet MCP `freecad-mcp` **0.1.22**, auteur `neka-nat`, confirmé dans le
  `METADATA` installé du cache uv. Ce serveur demande Python >= 3.12 ; son
  interpréteur n’est pas le Python embarqué de FreeCAD.
- Appel réel `get_rpc_status` : connexion refusée, `WinError 10061`. Aucune
  opération de géométrie exécutée par MCP pendant cette création de skill.

Importer `FreeCAD` **avant** `Part` avec le Python embarqué. Le test réel
`Part.makeBox(1, 2, 3).isValid()` a réussi. Dans un processus dédié, définir
`QT_QPA_PLATFORM=offscreen` avant import de `FreeCADGui`, puis appeler
`Gui.showMainWindow(); Gui.getMainWindow().hide()`. Ce repli a effectivement
créé et recalculé des objets natifs synthétiques. Les avertissements OpenGL et
keyboard de Qt n’ont pas empêché les contrôles BRep ; aucun rendu interactif
n’est démontré. Ne jamais masquer ou fermer la fenêtre de l’utilisateur.

Pour MCP, choisir l’exécution synchrone pour créer/modifier le document.
`execute_code_async` interdit précisément les modifications du document et
les appels GUI depuis son thread de fond. Un statut d’outil présent ne prouve
pas la disponibilité RPC. Après un échec borné, tester le repli ; ne pas lancer
plusieurs reconstructions concurrentes sur un même document.

## API Cables inspectées

| Module et point d’entrée | Capacité observée et limite |
|---|---|
| `wireFlex.make_wireflex_from_vectors(vectorlist)` | Crée un parcours natif et son ViewProvider ; initialise un placement à partir du premier vecteur. Les `Points` sont locaux au placement. |
| `WireFlex.PathType` | Enumération exacte `Wire`, `BSpline_P`, `BSpline_K`. Pas de propriété `MinimumRadius`. |
| `WireFlex.FilletRadius` | Sert au mode `Wire` ; caché et non appliqué à la génération des deux modes spline. |
| `BoundarySegmentStart`, `BoundarySegmentEnd` | Longueurs de segments terminaux droits pour les splines ; ne garantissent ni rayon ni obstacle évité. |
| `BoundaryTangents`, `InnerTangents`, `TangencyCoefficient`, `Parameterization` | Paramètres exploités pour `BSpline_K`. `BSpline_P` construit la spline à partir de **pôles**, sans passage garanti par les points internes. |
| `archCable.makeCable(selectlist=None, baseobj=None, profileobj=None, gauge=0, length=0, placement=None, name=None)` | Balayage d’un profil sur une base. `selectlist` prévaut sur les deux objets explicites. Sans profil, certains paramètres par défaut représentent du cuivre/isolant ; ne pas les confondre avec la définition fournisseur d’un câble USB, coaxial ou multiconducteur. |
| `compoundPath.make_compoundpath(plist=None)` | Assemble des objets de trajectoire ; modes `Simple`, `Wire`, `Complex`. Propriété propre `MinimumFilletRadius`, raccords `Arc` ou `Bez`, diagnostic `SmallestBendingRadius`. Ce n’est pas un graphe de connectivité électrique ni un planificateur de faisceaux. |
| `archCableConduit.makeCableConduit(selectlist=None, gauge=0, length=0, placement=None, name=None)` | Le module s’appelle **archCableConduit**, pas cableConduit. Hérite d’ArchPipe ; propriétés `SubConduits`, `MergeSubConduits`, `Gauge`, `InsulationThickness` synchronisée avec `WallThickness`. Le regroupement visuel de formes ne planifie ni remplissage ni compatibilité. |
| `wireutils.getMinimumRadius(wire)` | Retourne `(rayon, numéro_arête)`. Les splines sont approximées par `toBiArcs(0.5)` ; une rupture de tangence renvoie zéro ; une droite utilise la sentinelle `1e10`. Estimation diagnostique, aucune contrainte de génération ni borne globale prouvée. |

`CableConduit.getObjectsForCableConduit` collecte les objets de parcours et
crée éventuellement un CompoundPath. Dans le code inspecté, `subobj_list`
reste vide : aucune génération automatique d’arbre de dérivations n’est
établie. Un essai natif réussi de deux tronçons colinéaires de 50 mm puis d’un
conduit de 100 mm démontre seulement cette composition simple.

### Piège du solide périmé

`ArchCable.makeMainShape` attrape `Part.OCCError` et retourne `None`.
`ArchCable.execute` retourne alors avant réaffectation de `Shape` : un ancien
solide valide peut rester visible. Ainsi `Shape.isValid()` et un état
`Up-to-date` ne prouvent pas la génération sur le nouveau parcours.

Dans la **copie isolée seulement**, appeler
`rebuild_cable_in_isolated_document(doc, cable)` : cette fonction vide le
cache `Shape`, touche base et câble, recalcule, puis vérifie volume, nombre de
solides et états. Un test injectant le retour `None` observé du constructeur
confirme que le solide antérieur n’est pas accepté. Ce test d’échec injecté
n’est pas la reproduction complète de l’erreur OCC du faisceau F16.

## Réutiliser le constructeur du projet

Le constructeur de référence est
`hardware/mecanique/cartographe/verification/cable_workbench_prototype.py`.
Ses fonctions existantes `bootstrap_paths`, `make_native_cable`,
`effective_wire`, `cable_geometry` restent inchangées. Ne pas les recopier.
`make_native_cable(doc, root, name, points, diameter, bend_radius, color=...)`
crée WireFlex et ArchCable avec profil extérieur circulaire explicite ; exige
GUI initialisée et ne sauvegarde pas. Il contrôle déjà la faisabilité des
raccords de polyligne. `cable_geometry` mesure les arcs et la continuité de
position ; il ne constitue pas un contrôle adaptatif des splines ou des
obstacles. La skill complète cette couverture.

Sur un autre assemblage, fournir le chemin d’un constructeur existant avec
ces fonctions pour les tests natifs, ou adapter l’appel après inspection de
son contrat. Le module de mesures BRep n’importe aucun constructeur et reste
utilisable indépendamment. Ne pas exécuter un constructeur inconnu à l’import
sans avoir vérifié ses effets.

## Contrat des utilitaires de mesure

`scripts/freecad_geometry.py` ne recherche pas de route et ne choisit pas les
règles de compatibilité : il mesure les objets fournis dans un même repère.

- `inspect_route(wire, minimum_radius_mm, start_axis, end_axis, waypoints=(),
  ..., start_position=..., end_position=...)` : un fil ouvert unique.
  Les **deux axes pointent vers l’extérieur de leur connecteur** ; la tangente
  à l’arrivée est donc comparée à l’opposé de `end_axis`. Positions et axes
  manquants rendent le contrôle `unknown`. Un rayon demandé manquant reste
  `unknown`, jamais remplacé par 22 mm. Distances en mm, angles en degrés.
- Lignes et cercles : rayon analytique ; droites notées
  `straight_radius_infinite=true` et rayon JSON `null`, jamais nombre infini.
  Jonctions : continuité de position et tangence selon tolérances explicites.
- Autres courbes : échantillonnage sur tout le domaine de chaque arête et de
  chaque intervalle de nœuds, subdivision adaptative selon variation de
  courbure, profondeur bornée et budget rapporté. Une violation détectée
  échoue ; aucun résultat échantillonné favorable ne devient `pass` pour le
  rayon global. Les extrema de courbure ne sont **pas** résolus par ce module.
  Pour conclure, utiliser une borne indépendante vérifiable, une analyse des
  extrema ou une route analytique acceptable ; ne pas supprimer l’inconnue.
- `inspect_solid(shape, expected_solids=1)` : forme non nulle, valide, volume
  positif et compte de solides attendu. N’atteste pas, seul, la fraîcheur.
- `inspect_pair(a, b, a_id, b_id, clearance_mm=0, relation=None, ...)` :
  booléen volumétrique et distance BRep, puis seuils fournis. Une opération
  impossible donne `unknown`, jamais « aucune collision ».
- Une relation `cable_in_conduit_envelope` exige les identifiants exacts
  `inner_id` et `outer_id`, `outer_representation=occupancy_envelope`, une
  `justification` non vide et l’inclusion géométrique complète. Elle ne permet
  aucune pénétration de la matière réelle de la gaine. Une relation
  `functional_contact` exige `pair=[id_a,id_b]`, justification, distance de
  contact et intersection volumétrique nulle aux tolérances près. Vérifier
  l’autorisation technique de la relation avant de la transmettre.

Les vecteurs d’entrée et les mesures comparées doivent être finis. Les tests
NaN/inf vérifient l’absence de faux `pass` et de valeurs non finies dans les
rapports JSON. Un retour faux de `doc.recompute()` constitue un échec, même
si une forme valide est présente.

Les résultats `pass/fail/unknown` sont des verdicts de **contrôles numériques**,
non des états de maturité projet. Un `pass` ne qualifie jamais CEM, thermique,
vibration, rigidité, montage, maintenance ou tenue physique. Les empreintes
BRep servent à tracer la géométrie ; conserver séparément celles des fichiers,
paramètres, versions et transformations d’occurrences.

## Exécuter les essais synthétiques

Depuis la racine du projet de référence :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' -B `
  '.agents/skills/electromechanical-integration/scripts/tests_freecad.py' `
  --builder 'hardware/mecanique/cartographe/verification/cable_workbench_prototype.py' `
  --output '.runtime/electromechanical-integration/freecad-tests.json'
```

Limiter le processus dédié à 60 secondes depuis le lanceur. Les tests créent
seulement des documents synthétiques en mémoire et les ferment sans sauvegarde.
`--builder` omis : seuls les tests BRep sont exécutés, les tests natifs sont
explicitement ignorés. Le processus dédié termine après écriture/flush du
rapport pour éviter un blocage Qt à la fermeture ; ne pas importer son point
d’entrée dans une session GUI utilisateur. La création initiale de la skill a
exécuté **19 tests réussis**, dont 4 tests natifs, avec les versions ci-dessus.
La preuve locale est `freecad-tests.json` ; la validation interactive et la
validation physique n’ont pas été exécutées.

Les audits historiques F16 (`essai_wireflex/mesures.json`,
`essai_wireflex/comparaison.json`, `essai_routage_f16/mesures.json` et
`statut.json`) justifient le contrôle : rayon candidat 22 mm non fournisseur,
B-spline K à environ 0,006 mm avec échec de génération, B-spline P à environ
23,663 mm mais huit intersections dans le périmètre testé. Ils ne fournissent
aucune qualification réutilisable pour une autre liaison.
