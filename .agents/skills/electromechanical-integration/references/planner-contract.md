# Contrat du planificateur hors ligne — version 1

Lire pour préparer les données et interpréter les propositions. Le binaire C++17
ne charge pas FreeCAD et ne décide pas de la conformité physique. Il n'importe
pas automatiquement les registres propres à un projet : l'agent effectue le
mappage explicite depuis les sources existantes sans dupliquer le constructeur.

## Construction et commandes

Prérequis : CMake ≥ 3.20, compilateur C++17, Qt6 Core ≥ 6.2, générateur CMake.
Windows vérifié : MSYS2 UCRT64, GCC 16.2.0, Qt6 Core 6.11.2 ; les DLL Qt/GCC
doivent être dans `PATH`. Le JSON et SHA256 utilisent Qt, sans parseur maison.
Depuis la racine du projet (adapter le dossier de build sur un autre projet) :

```powershell
cmake -S .agents/skills/electromechanical-integration/scripts -B .runtime/electromechanical-integration/planner-build -G Ninja
cmake --build .runtime/electromechanical-integration/planner-build
ctest --test-dir .runtime/electromechanical-integration/planner-build --output-on-failure
.runtime/electromechanical-integration/planner-build/harness-planner.exe plan input.json report.json report.md
.runtime/electromechanical-integration/planner-build/harness-planner.exe validate input.json candidate.json report.json report.md
```

`validate` reçoit un seul candidat `{id,routes,grouping}`. Il recalcule les
regroupements et métriques à partir des routes ; les champs de résultats ne
sont jamais reçus comme preuves. `plan` émet au plus trois candidats.
Codes de retour : **0** proposition topologique disponible (même avec réserves),
**1** tous les candidats rejetés, **2** entrée/commande/IO invalide ou aucun
chemin trouvé dans le budget. Le code 0 ne signifie jamais « faisceau validé ».
Les deux sorties sont finalisées séparément par `QSaveFile` ; si la seconde
échoue, le code 2 exige de reprendre la finalisation, même si le JSON existe.

## Entrée

Voir [synthetic-network.json](synthetic-network.json) pour un cas complètement
exécutable ; les valeurs sont synthétiques et ne sont pas des spécifications.

| Champ | Contrat |
|---|---|
| `schema_version` | entier `1` |
| `connectors[]` | `id` unique, `position_mm` : trois nombres finis ou `null`, `exit_axis` : vecteur non nul ou `null`. Ajouter équipement, repère, orientation complète et provenance dans les données métier ; le noyau n'en déduit aucune pose. |
| `nodes[]` | `id` unique, `connector_id` facultatif unique, `accessible` booléen ; absence assimilée à accès non démontré |
| `links[]` | `id`, `from`, `to` (IDs connecteurs distincts liés aux nœuds), `category`, `outer_diameter_mm`, `min_bend_radius_mm` |
| paramètres de liaison | objets `{value:number positif|null,source:string|null,confidence:supplier|measured|candidate|unknown}`. Source vide, confiance candidate/inconnue ou valeur nulle produisent une réserve, jamais zéro. |
| `edges[]` | `id` unique, `from`, `to` (nœuds), `length_mm` positif, `usable_width_mm` positif ou `null` explicite. Arêtes bidirectionnelles. Largeur utilisable = hypothèse de capacité linéaire locale, pas distance à obstacle. |
| `compatibility[]` | `{categories:[a,b],decision:allow|deny|unknown,source,reason}` ; règle symétrique unique par paire. `allow`/`deny` exigent source et justification non vides. Sans règle : unknown, y compris même catégorie. |
| `settings.fill_ratio` | nombre explicite dans ]0,1], paramètre candidat de prédimensionnement ; aucune valeur fournisseur par défaut |
| `settings.max_paths_per_link` | défaut 8, 1–1000 |
| `settings.max_expansions` | défaut 10000, 1–1000000, visites DFS par liaison |
| `settings.max_candidates` | défaut 3, 1–3 : baseline, pooling ordre des IDs, pooling ordre inverse |
| `settings.objective_order` | ordre lexicographique configurable : `bundle_segments`, `support_sites`, `envelope_mm3`, `cable_length_mm`, `branch_count`, `shared_length_mm`. Le dernier est maximisé, les autres minimisés. Défaut = quatre premiers. |

Chaque contrainte électrique/CEM/thermique/mouvement réelle est analysée avant
de produire une règle de compatibilité locale. Le moteur n'applique aucune
interdiction universelle par nom de catégorie et ne vérifie pas le contenu
technique d'une justification. Une règle d'entrée doit déjà être applicable aux
liaisons de sa catégorie dans le périmètre étudié ; utiliser des catégories
locales plus fines si deux liens exigent des règles différentes.

Les informations additionnelles (courant, tension, blindage, réserve de service,
conditions vibratoires, exigences de séparation, fixations existantes et sources)
restent dans l'entrée JSON empreintée ; elles ne sont pas interprétées par ce
petit noyau. Ne pas croire qu'un champ supplémentaire déclenche un contrôle.

Les six classes `data_class` du [dossier complet](integration-contract.md)
ne remplacent pas l'enum `confidence` v1. Appliquer sa projection conservatrice
et conserver les références au dossier, calculs et hypothèses. Les statuts de
conception enrichis sont agrégés dans la preuve d'expérience après les contrôles
complémentaires ; le binaire ne les émet ni ne les valide automatiquement.

## Méthode réellement implémentée

1. Vérification des identifiants, références, paramètres et limites de recherche.
2. Énumération DFS déterministe des chemins simples dans le budget par liaison,
   tri des chemins trouvés par longueur puis IDs, conservation des K premiers.
   Ce n'est pas une garantie de K plus courts chemins en cas de budget atteint.
3. Baseline : première route trouvée pour chaque liaison, sans gaine partagée.
   Deux candidats de mutualisation utilisent les mêmes chemins disponibles :
   coût d'une arête déjà utilisée multiplié par 0,1 seulement si toutes les
   paires de câbles concernés ont une règle `allow`. Ce coefficient fixe sert
   à proposer une alternative, pas à établir la fonction objectif finale.
4. Sur chaque arête, partition gloutonne déterministe des câbles en groupes
   pairwise `allow`. `deny` et `unknown` restent séparés. Un `deny` dans le même
   corridor exige encore une preuve spatiale de séparation : réserve explicite.
5. Vérification de conservation de toutes les liaisons, absence de duplication,
   chemin ordonné contigu sans cycle, arrivée au connecteur électrique prévu.
6. Dérivations candidates : nœuds de degré utilisé ≥ 3 dont les ensembles de
   câbles diffèrent entre arêtes. Dérivation inaccessible = rejet.
7. Un câble isolé conserve son diamètre extérieur comme largeur et enveloppe
   physiques : aucune gaine n'est ajoutée implicitement. Son champ
   `inner_diameter_estimate_mm` vaut `null`, `required_width_mm` porte le diamètre
   du câble et `dimensioning_status` vaut `individual_cable`.
   Pour un groupe de ≥ 2 câbles, prédimensionnement par aire :
   `D_int >= sqrt(sum(d_i²)/fill_ratio)` ; `required_width_mm` porte cette borne
   et `dimensioning_status` vaut `preliminary_area_bound`.
   Cette borne n'est ni un packing démontré, ni un diamètre de fourniture choisi.
   Vérifier ensuite épaisseur de gaine, occupation réelle, passage des prises,
   assemblabilité, réserve, thermique, références et mécanismes d'ouverture.
   Sur une arête, somme des largeurs requises des groupes et câbles isolés > largeur utile
   = rejet ; largeur ou diamètre inconnu = réserve. Cette comparaison n'est pas
   un test de collision ni une démonstration de séparation CEM.
8. Exclusion des candidats ayant une violation impérative ; candidats sans
   réserve hors ligne préférés aux candidats avec réserves, puis comparaison
   lexicographique selon les objectifs. Les métriques inconnues sont ignorées
   pour le classement, jamais remplacées par zéro. À égalité : ordre stable.

## Sortie et limites des métriques

`candidates[]` contient `id`, `routes`, `grouping`, `segments`, `branches`,
`metrics`, `errors`, `unknowns`, `decision` : `rejected`, `unresolved` ou
`candidate`. Tous restent préliminaires, même le dernier état.
`selected_candidate_id` recommande une proposition à étudier ou vaut `null`.
`execution` garde geometry/recompute/interactive/physical à `not_executed`.
`optimality_proven:false`, budgets et `search_truncated` rendent la borne visible.

Les `segments` sont ici les couples **arête × groupe compatible**. Le noyau
ne fusionne pas encore les chaînes d'arêtes de même membership. Ainsi :

- `bundle_segments` compte ces couples, **pas** le nombre de faisceaux complets ;
- `shared_segments` et `shared_length_mm` comptent les groupes de ≥ 2 câbles ;
- `cable_length_mm` somme les longueurs de chaque câble, sans réserve de service ;
- `support_sites` compte les nœuds utilisés, **pas** des fixations conçues ;
- `envelope_mm3` somme les cylindres droits de diamètre extérieur pour les câbles
  isolés, de diamètre intérieur préliminaire pour les groupes, sans matière de
  gaine ni packing ; la masse reste `null`.

Ces métriques sont des proxies pour comparer le même graphe. Ne pas comparer
deux découpages de graphe différents avec `bundle_segments`/`support_sites`.
Les objectifs complets de la méthode (risque d'accrochage, accessibilité réelle,
maintenabilité, nombre de faisceaux physiques, fixations et masse ajoutée)
exigent la revue et les contrôles CAO séparés ; ils ne sont pas simulés ici.

Le SHA256 canonique porte le JSON parsé sérialisé compact par Qt ; le CLI ajoute
le SHA256 des octets exacts du fichier d'entrée. Conserver aussi les empreintes
du binaire, sources FreeCAD, dépendances externes et paramètres de génération
dans le manifeste de l'expérience. Ce noyau ne copie ni n'ouvre l'assemblage.

## Tests inclus

`harness-planner-tests` vérifie des propriétés observables : deux liens qui
mutualisent 100 mm, trois liens avec dérivations et destinations distinctes,
interdiction explicite de regroupement, absence de règle conservatrice,
paramètre fournisseur manquant, perte/duplication de connexion, continuité et
extrémité, capacité corridor, accessibilité, borne de gaine, déterminisme,
budget et ordre des objectifs. Les rayons, solides et collisions réels sont
testés par l'adaptateur FreeCAD séparé ; un test JSON ne les remplace pas.
Les régressions vérifient aussi un câble isolé de 3 mm dans des corridors de
4 mm (admis) et 2 mm (rejeté), l'absence de gaine implicite, le schéma strict et
les dépassements numériques. Toute longueur, aire, diamètre, score ou enveloppe
calculé non fini interrompt le calcul avec erreur ; il ne devient pas `null`
ou une preuve admissible.
