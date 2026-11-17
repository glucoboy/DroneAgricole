# Contrat d’exploration électromécanique V2.1

La décision d’architecture figure dans [DOC-SW](../architecture/ARCHITECTURE_LOGICIELLE.md#porte-v21). Les champs ci-dessous décrivent le contrat du préflight GO3A/GO3B.

## États et transitions

| État | Porte | Effet |
|---|---|---|
| `EXPLORATION_ALLOWED` | `explore` | Plan numérique admissible sur copie privée et hors tension. Une pause interrompt l’ordonnancement et se reprend avec les mêmes entrées. |
| `EXPLORATION_BLOCKED` | `explore` | Destination, type d’essai, garde impérative ou constat de la variante incompatible avec le plan proposé. |
| `CANDIDATE_CONDITIONAL` | `final`, état du candidat | Natif distinct référencé par un reçu L4 cohérent. Des preuves de réception restent à établir. |
| `CANDIDATE_REJECTED` | `final`, état du candidat | Échec L4 rapporté sur la copie ou sa campagne. |
| `FINAL_NO_GO` | `final` | Candidat absent, rejeté ou périmètre de réception insuffisamment démontré. |
| `FINAL_GO`, `FINAL_GO_CONDITIONNEL` | Réservés | Réception d’un candidat intégré. L’activation exige un contrat approuvé qui associe les critères gelés aux mesures requises et, pour une réception conditionnelle, un périmètre et des réserves approuvés. |

`EXPLORATION_ALLOWED` → construction sur copie → `CANDIDATE_CONDITIONAL` ou `CANDIDATE_REJECTED` → réception indépendante. Le préflight seul produit un plan. La terminaison `PLANNED` signifie que la file est publiée. Une anomalie de contrat ou d’empreinte interrompt la commande sans publier de verdict.

## Compatibilité et autorités

| Entrée / appel | Lecture | Sortie |
|---|---|---|
| `historical` | `GO3A_DECISIONS.json` → statut, autorisation et front. `GO3A_MANIFEST.json` → gel. `GO3B_ADMISSION.json` → contrôle d’admission et compteur. | Rejeu du verrou documentaire et `NO_GO_MOTIVE`. Aucun branchement historique correspondant dans le constructeur. |
| `explore` | Demande `drone_agricole.exploration_request.v2.1`, gel historique et activités `drone_agricole.evidence_plan.v2.1`. | `drone_agricole.preflight.v2.1`, garde d’écriture, états observés, registre `evidence_gap`, file et budget. |
| `final` | Gel historique et, si fourni, reçu `drone_agricole.final_reception.v2.1` et campagne L4 T0. | `drone_agricole.preflight.v2.1`, synthèse de réception et écarts. |

Le `.yaml` GO3A est du JSON strict. Le reçu GO3A gèle des critères documentaires et un modèle descriptif. Le gel de L4 identifie quant à lui des entrées et contrôles exécutables. Les identifiants G3A et des empreintes concordantes ne démontrent pas la couverture des critères. Le préflight conserve les rapports V2 et ne modifie ni le gel historique ni le validateur L4.

Les deux SHA-256 des archives GO3B sont épinglés dans l’adaptateur. Les 180 fichiers inventoriés sont vérifiés au début et à la fin de chaque appel. Le replay GO3A de ce workspace comprend ses copies et observations locales sous `.runtime/` ainsi que les archives de mandat. Reprendre avec ces dépendances présentes et leurs empreintes d’origine.

## Demande et preuves

- `exploration_request.v2.1` exige `candidate_id`, `reference_sha256`, `trial`, trois gardes `private_copy`, `unpowered`, `preserve_connectivity`, la garde `constraints_enabled`, `write_target: "candidate"` et l’objet `trial_findings`. La sortie visée est un enfant encore absent du dossier privé du préflight. Les gardes portent sur les déclarations du plan. Un futur appel au constructeur doit vérifier la fermeture XLink, les écritures, les contraintes et le graphe effectivement conservé.
- `PARAMETRIC_ENVELOPE` admet un encombrement hypothétique pour comparer les corridors. `UNPOWERED_LAYOUT` permet de réserver une implantation sans changement de brochage ou de peuplement. `RADIUS_SENSITIVITY` compare des hypothèses étiquetées. Accouplement, continuité électrique et fatigue gardent leurs critères de preuve. Un `FAIL` connu sur la variante, par exemple une collision ou une perte de connexion, ferme l’exploration de ce plan. Les collisions TTL/PDB du témoin Action 3 excluent ses poses en défaut et motivent une autre piste.
- Chaque `evidence_gap` conserve l’identifiant impératif, l’état, la provenance, l’hypothèse ou le constat, le risque, les essais permis, la validation finale, l’activité proposée, son coût en créneaux numériques, la source recherchée et les exigences concernées. Pour G3A-03, la recherche précède l’essai de continuité ou le changement de peuplement. La réservation hors tension et les activités indépendantes restent possibles.
- `UNKNOWN`, `INCONCLUSIVE`, `NOT_RUN`, `FAIL` et `PASS` sont distincts. Les constats d’exploration sont reproduits séparément dans `trial_findings`. Le préflight ne crée aucune mesure ni preuve L4.
- Le reçu de réception facultatif référence `candidate_id`, `reference_sha256`, `authority_sha256`, `native`, `native_sha256`, `l4_terminal`, `l4_terminal_sha256`, `l4_case` et `l4_lock`. La cohérence T0, le rapport du cas, le natif et le rattachement des fichiers GO3A au gel L4 sont vérifiés. La cohérence des empreintes ne remplace pas l’origine indépendante ni une couverture approuvée. Le dépôt ne dispose pas encore de la correspondance approuvée pour H-01.

La publication atomique et verrouillée de `preflight.json` conserve le préfixe validé de la file. Une reprise vérifie l’identité du plan, des autorités et des lignes déjà publiées. Les créneaux sont des estimations. Le nombre de variantes construites reste à zéro pour ce parcours sans constructeur. Le plafond historique de 12 est une borne de référence, pas une consommation ni une autorisation de campagne.

[Commandes](../../convergence_manager/README.md#preflight-go3a--go3b) · [Preuve JSON](../verification/v21_exploration_gate.json)
