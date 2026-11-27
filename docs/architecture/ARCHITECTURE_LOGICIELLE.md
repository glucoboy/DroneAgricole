# Architecture logicielle

| Champ | Valeur |
|---|---|
| Référence | `DOC-SW` |
| Nature | document vivant |
| Dernière mise à jour | 27 novembre 2026 |
| Statut | station C++17/Qt 6 implémentée partiellement ; logiciel embarqué cible **À valider** |

## 1. Objet

Ce document décrit l'ensemble du logiciel du système : station desktop, outils
headless, adaptateurs de données et de calcul, environnements ROS 2, intégration
PX4, déploiement et tests. Il distingue systématiquement les capacités
**planifiées**, **implémentées** et **qualifiées**.

Le fonctionnement système est défini dans [DOC-HLD](HLD.md). Les interfaces
physiques sont détaillées dans [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md).

## 2. Principes d'architecture

- Toute logique exécutable propriétaire est écrite en C++17.
  L’action 1 prescrit un moteur de banc électromécanique en Python pour
  exploiter l’environnement embarqué de FreeCAD et le Workbench Cables.
  Ce moteur est un outil de conception autonome, hors station et chaîne de
  vol. Voir son [périmètre dans DOC-MEC](ARCHITECTURE_MECANIQUE.md#moteur-electromecanique).
- L'interface desktop utilise Qt 6 Widgets ; sa structure est placée au maximum
  dans des fichiers `.ui`.
- Présentation, application, domaine, algorithmes et adaptateurs sont séparés par
  des dépendances de compilation explicites.
- L'UI appelle les services ; elle ne contient ni logique métier, ni lancement
  concret de processus, ni finalisation de résultat.
- Les mêmes règles applicatives sont utilisables par l'UI et la CLI.
- Les variantes de datasets, runtimes et algorithmes sont des adaptateurs, pas
  des branches ajoutées dans `MainWindow`.
- Les fonctions critiques de vol restent dans PX4. ROS 2 publie des consignes
  avancées et supervise leur validité.
- Configuration, résultats et interfaces sont versionnés ; les files et délais
  critiques sont bornés.

Ces principes constituent la référence active pour les évolutions logicielles.

<a id="recherche-technique-l1"></a>
### 2.1 Recherche technique électromécanique — L1

`technical_research_engine` est **Implémenté** pour instruire les inconnues
documentaires d’ORCH-CAO-MASSE-1. Le moteur C++17/Qt 6 et son client Python
permettent au décideur de soumettre et de relire une recherche par `issue_id`.
Le moteur s’exécute hors FreeCAD. Il confronte les sources locales en premier,
puis, sur demande, les URL HTTPS du catalogue. Le catalogue identifie les
autorités et les localisateurs d’extraction. Une découverte de fichiers
alimente les pistes à instruire.

Le [contrat de rapport](../electromechanical_v2/RESEARCH_REPORT.schema.json)
réutilise les types L0 pour la question, les preuves et les valeurs. Il porte
en plus la correspondance d’identité, de révision et de domaine, le registre
des inconnues et la trace du cache. Une divergence entre preuves comparables
garde la question ouverte. Les calculs à entrées hypothétiques fournissent
équation, unités et bornes pour une étude conditionnelle. Le moteur publie
atomiquement par identifiant et vérifie les empreintes locales à la relecture.
Les consommateurs utilisent la conclusion et sa portée pour leurs propres
contrôles. Le gel complet du graphe et des exigences V2 reste **Planifié**.
[Guide d’utilisation](../../technical_research_engine/README.md) ·
[Vérification L1](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l1)

### 2.2 Catalogue et validation d’interconnexion — L2

`interconnection_engine` est **Implémenté** en C++17/Qt 6 Core. La CLI
réutilise le graphe L0 et consomme les rapports L1 par configuration et
identifiant. Elle calcule des verdicts distincts de compatibilité,
continuité et géométrie. Les identités des pièces, leurs révisions et la
table de cavités de la paire sont vérifiées avant le rapprochement des
conducteurs et circuits. Une modification de pose déclenche une nouvelle
évaluation sur l’état demandé. La longueur utile déclarée est comparée à
la longueur développée de la polyligne. Une broche désignant explicitement
le potentiel opposé d’une paire différentielle produit un défaut de polarité.

Le rapport conserve la table broche–contact–conducteur, la nomenclature
candidate et les empreintes des entrées. Le convertisseur des lignes vers
les axes vérifie les relations dans les deux sens et conserve les anomalies
par source. L’adaptateur FreeCAD reçoit une projection du banc. L’application
au graphe complet du prototype reste **À valider**.
[Recette](../../interconnection_engine/README.md) ·
[Vérification L2](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l2)

<a id="exploration-architecture-l3"></a>
### 2.3 Exploration d’architectures électromécaniques — L3

`architecture_decision_engine` est **Implémenté** en C++17/Qt 6 Core.
Il instruit les blocages de service qui subsistent après correction locale.
Le banc identifie le blocage et ses objets, donne la marge observée et
déclare les variables et inconnues. Un intervalle affine borne la faisabilité
sur le domaine déclaré. Le moteur déclenche des variantes paramétrées selon
le constat et le budget du banc. Il recalcule les contrôles applicables,
y compris ceux des liaisons incidentes aux équipements modifiés.

Le validateur L2 est lié en bibliothèque pour le banc F31. La CLI L1
instruit une `ResearchQuestion` L0 et le rapport conserve la piste et sa
provenance. En cas d’inconnue, le banc réexécute les contrôles géométriques
sur trois hypothèses de course. Le candidat conserve la valeur inconnue.
Le banc F40/F41 compare un changement d’implantation et une interface
déportée. Le contrat électrique de l’interface spécifie le graphe autorisé.
Les fonctions et les contraintes communes sont évaluées après chaque
changement et à nouveau lors d’une consolidation.

Les exigences et les entrées sont empreintées séparément des candidats.
Le front de Pareto utilise les objectifs numériques comparables des
variantes admissibles et publie les objectifs indisponibles. Le contrat
de sortie L3 porte le cycle de vie des décisions de banc et les références
de preuves. Les portes de passage restent décrites par le contrat L0.
Le moteur publie les artefacts T0 et le manifeste terminal. Les valeurs
physiques, les références réelles et les solutions CAO restent **À valider**.
[Recette](../../architecture_decision_engine/README.md) ·
[Vérification L3](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l3)

<a id="validation-electromecanique-l4"></a>
### 2.4 Validation électromécanique indépendante — L4

`validation_engine` est **Implémenté** en C++17/Qt 6 Core. L’autorité de
campagne fige les exigences, la recette, les références L0 à L3, les scripts
de mesure et l’identité du validateur avant l’évaluation. La CLI reçoit
l’empreinte du gel par un canal distinct du candidat. La bibliothèque
réconcilie les circuits et contacts avec les critères L2 et vérifie les
chemins fonctionnels définis par L3. Elle évalue les constats géométriques
sur les mesures brutes de l’adaptateur FreeCAD. Chaque fermeture native
est copiée puis mesurée deux fois dans des processus neufs. Les originaux
et les mesures sont empreintés. Les projections servent à cibler des
inspections quantifiées.

La sortie porte `ValidationReport`, `ValidationFinding` et
`TechnicalEvidence` L0, les tolérances et valeurs structurées, les liens
de preuve, la couverture et la finalisation T0. L5 vérifie le manifeste
terminal, les artefacts, l’identité du natif et le gel commun avant de
comparer des fusions. Un rapport `FAIL` ou
un contrôle obligatoire ouvert empêche l’admission sur le périmètre évalué.
Les verdicts historiques portent sur des critères ciblés. Le rapprochement
entre les références montées et un graphe du prototype complet reste
**À valider**.
Un identifiant annoncé sans définition dans le gel laisse le port ouvert.
Les caractéristiques de cordon fournies sont évaluées contre la demande
gelée. Une divergence de sélection ou de spécification qui ne donne pas
d’écart établi empêche de conclure à la compatibilité.
[Recette](../../validation_engine/README.md) ·
[Vérification L4](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l4)

La commande `validation_core xlink` gère la fermeture et le calcul par
lots d’un assemblage FreeCAD multi-documents. Le Python embarqué mesure
les formes et les placements des occurrences dans des processus dédiés.
Le cœur C++17 rapproche le graphe L2, calcule le périmètre des paires et
assemble la couverture T0. Le cache de tâche est indexé par la racine
sauvegardée, les dépendances, les critères et l’environnement de mesure.
Un lot expiré laisse des contrôles `NOT_RUN` que le prochain lot peut reprendre.
[Recette XLink](../electromechanical_v2_1/03_XLINK_VALIDATION.md)

<a id="convergence-electromecanique-l5"></a>
### 2.5 Convergence électromécanique — L5

`convergence_manager` est **Implémenté** en C++17/Qt 6 Core. L’API de
campagne et la CLI partagent la machine d’états. Le manifeste fige
configuration, fichiers et binaires. Le checkpoint atomique conserve
transitions, décisions, opérations réservées, reçus et budgets. Après
interruption, une opération sans reçu est isolée et reprise dans un
nouveau dossier dans la limite configurée. La publication T0 se termine
par le manifeste terminal.
La reprise vérifie les rôles, chemins et empreintes de tous les fichiers du
gel L4 contre la recette déclarée. Pour publier une consolidation, la CLI
recontrôle les preuves L4 finalisées, l’identité du natif et la couverture
des liaisons exigées. Le dossier de campagne contient les reçus du moteur
et relève de l’environnement de confiance du validateur.

L’empreinte des affectations appliquées et de la topologie élimine les
équivalents sur une grille déclarée. Le diagnostic d’un défaut récurrent
groupe les constats par objet et état, déclenche L1 et utilise le criblage
L3 pour ouvrir les alternatives déclarées. Une inconnue fournisseur reste
attachée aux variantes dépendantes, avec traces de recherche, répétitions
et prochaine vérification.

Les portefeuilles assemblent les affectations de décisions locales
admissibles. Le contrôle de fusion applique dépendances, exclusions,
propriété des affectations et conflits d’écriture. La réalisation native
de ce banc couvre les routes sur une topologie fixe. Une modification de
connecteur, brochage, plaque ou cordon demande un constructeur et des
contrôles applicables avant admission. L4 reçoit le seul natif sauvegardé et
la référence indépendante. La copie est retenue après couverture des
liaisons concernées et contrôles communs. Le front de Pareto des fusions
admissibles utilise les objectifs mesurés sous le même gel. Le jalon
physique reste **À valider**.
L’admission native L5 porte sur un seul document FreeCAD. La co-évaluation
de critères géométriques et électriques a été exercée via L4 sur banc.
L’admission d’une fusion à dépendances XLink et la traçabilité entre broches,
conducteurs et géométrie native restent **À valider**.

[Recette](../../convergence_manager/README.md) ·
[Vérification L5](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l5)

### 2.6 Graphe électromécanique XLink V3-A — Implémenté

Le pont FreeCAD réutilise la fermeture et la réouverture L0/L4 sur copies.
Le module C++17/Qt 6 Core projette les occurrences, les autorités et le
rapprochement L2 dans le contrat `v3.graph/1`. Il vérifie les identités,
les chemins de liaison ordonnés, les preuves et les contraintes. La clé
d’occurrence reste liée à la chaîne de liens. Plusieurs occurrences
peuvent partager la même définition et présenter des poses distinctes.
L’API et la CLI calculent la fermeture orientée à partir d’une cible typée.
Une arête terminale expose un voisin pour relecture et arrête la
propagation par ce chemin. L’opération filtre le type admissible de cible.
Pour une cible commune la fermeture reste conservatrice.
[Contrat et recette](../electromechanical_v3/README.md) ·
[Réception](../VALIDATION_QUALIFICATION.md#cartographe-v3-a)

#### Admission des opérateurs XLink V3-A.1 — Implémenté

`convergence_core v3-admission` entre dans `ProcessBackend::buildV3`.
Le service C++17 `evaluateAdmissionScope` vérifie le contrat
`v3.admission_scope/1` avant le dispatch. Il lie l’autorisation au domaine,
à l’identité du modèle, au sceau, à la fermeture XLink, à une occurrence,
à un effet et aux contrôles de l’opération. Les contraintes et autorités
utilisées pour le banc sont vérifiées contre des artefacts épinglés par
SHA-256, dont le reçu natif rattaché au sceau. Le CLI rejette les clés JSON
dupliquées avant le dispatch et produit le reçu de décision après évaluation.
Le chemin de campagne historique est distinct.

Les quatre opérations du banc atteignent la frontière de dispatch
`BENCH_TEST_ONLY`. Le reçu A.1 consigne l’admission seule. Le chemin de
construction est disponible via `v3-build` à partir de B.1.
L’admission virtuelle du cartographe exige une copie fermée en lecture
seule. L’exploration native et l’admission de conception restent **À valider**.
[Schéma](../electromechanical_v3/admission_scope.schema.json) ·
[Validation et recette](../VALIDATION_QUALIFICATION.md#cartographe-v3-a1)

#### Construction transactionnelle XLink V3 B.1 — Implémenté

`convergence_core v3-build` passe par `ProcessBackend::buildV3` puis
`runV3Mutation`. Le CLI vérifie l’identité du plan et sa composition.
La politique A.1 compare chaque action à un profil de banc épinglé par
SHA-256. Le profil porte les paramètres, la portée et les autorités.
L5 appelle le moteur V3-A pour fermer l’impact de chaque action avant
la copie et revalide les empreintes des documents natifs.

Le worker FreeCAD applique les opérateurs à un document d’entrée possédé
par la transaction. Les définitions XLink partagées sont référencées par
leurs octets d’origine. Un autre processus recalcule les documents depuis
une seconde copie et mesure les repères, les contacts, les conducteurs,
les solides, les rayons, les appuis et les volumes de service. L5 publie
la transaction par renommage après validation T0 indépendante. Une
interruption laisse un dossier privé journalisé et permet une reprise
dans un dossier de travail neuf. Les cas géométriques mesurés et rejetés
restent inspectables.

Le dispatch couvre les quatre opérateurs du banc. Les changements de
variante de connecteur et de topologie ont un contrat et rendent
`UNSUPPORTED`. Le domaine d’exécution est `SYNTHETIC_BENCH`.
[Schéma](../electromechanical_v3/mutation_plan.schema.json) ·
[Qualification](../VALIDATION_QUALIFICATION.md#cartographe-v3-b1)

#### Contre-validation XLink V3 B.2 — Implémenté

`v3-build` vérifie que les contrôles natifs obligatoires sont uniques et
que leurs statuts justifient le verdict agrégé. La recette de qualification
rouvre une copie distincte dans `v3_cross_measure.py`. Elle confronte les
observations géométriques aux critères scellés et au reçu de transaction,
avec une validation T0 à l’emplacement de publication. Les comparaisons
L2/L4 portent chacune leur contrat et leur périmètre.
[Résultats et recette](../VALIDATION_QUALIFICATION.md#cartographe-v3-b2)

Le schéma [`v3.candidate_result/1`](../electromechanical_v3/candidate_result.schema.json)
identifie le candidat, la proposition, le modèle source, les mesures, les
outils de validation et les écarts. Un reçu `PASS` exige une transaction,
une mesure indépendante et un T0 valides. La quarantaine et le rollback
sont représentés explicitement. L’orchestration de ces étapes par L5 est
prévue pour V3-C.

#### Convergence paramétrique XLink V3-C — Implémenté

`architecture_decision_core v3-problem` publie le problème L3 lié au
domaine, au modèle et à l’observation. `convergence_core v3-converge`
vérifie ces entrées et recalcule la fermeture de référence. Le solveur
produit les translations et parcours dans le domaine autorisé. Le criblage
utilise les enveloppes des obstacles mesurés. Les contraintes actives
guident la poursuite dans une famille de détour.

La campagne L5 appelle la transaction XLink pour chaque proposition admise.
Le contrat `v3.mutation_plan/2` fournit des valeurs brutes. L5 construit les
actions avec les opérateurs et la composition scellés, puis fait relire
les copies par B.2. La sélection applique les contraintes dures avant
le front de Pareto et l’ordre des objectifs. Les plans exacts B.1 et la
voie historique `route:*` restent accessibles par leurs entrées propres.
[Qualification et CLI](../VALIDATION_QUALIFICATION.md#cartographe-v3-c)

#### Ports mobiles et supports couplés V3-C.1 — Implémenté

Le mode `NATIVE_PORT` du domaine paramétrique lie le moteur aux repères
natifs du port fixe et du port mobile. Le profil scellé rattache le datum
au corps dans la définition XLink ou par une attache rigide à l’équipement.
L5 développe la translation en repère monde, le parcours et la pose attendue
du support. Le plan garde l’ordre corps, câble, support. La contre-validation
B.2 reprend les datums, l’axe WireFlex et l’appui du support sur la face nommée
dans un processus distinct. Les volumes de service suivent les occurrences
déclarées et la définition externe est vérifiée par SHA.

La recherche peut varier le cheminement d’une même famille selon les
diagnostics mesurés. Les métriques de Pareto utilisent le câble rouvert et
les dégagements BRep. Le déplacement est borné dans le plan du corridor
avec une orientation fixe. La rotation variable est `UNSUPPORTED`.
[Preuves et portée](../VALIDATION_QUALIFICATION.md#cartographe-v3-c1)

#### Import préliminaire de relevés V3-A.4 — Implémenté

`cartographe_material_evidence` lit un paquet de mesures et vérifie ses
sources brutes, sa cohérence d'identité, les repères dans les deux sens et
les intervalles d'incertitude. La politique de revue et son empreinte
proviennent du responsable, hors du dossier de collecte. Un calcul
compatible reste `PENDING_AUTHORIZED_REVIEW` tant que l'approbation
authentifiée manque. Le résultat d'import n'ouvre aucune transaction L5 ni
aucun droit pour une autre occurrence ou opération. [Contrat et rejeu](../verification/v3/a4/REPORT.md)

#### Jonction V3-INT.1 — Implémenté

Le build CMake de `convergence_manager` produit les deux exécutables
`convergence_core` et `cartographe_material_evidence`. Le premier conserve
l'orchestration du plan typé, le profil de banc scellé et la réouverture
B.2 avant publication T0. Le second contrôle un paquet et rend un résultat
d'import qui conserve `authority=DENY`. Le verdict de l’import ne figure
pas parmi les entrées autorisant une transaction L5. Le contrôle du domaine
cartographe demeure à l'entrée du constructeur, avant le lancement FreeCAD.

Le passage vers des contraintes multi-faisceaux et une revue authentifiée
consomme la même base intégrée, dans les périmètres définis pour C.2 et A.5.
[Contrat de passage](../verification/v3/int1/next_stage_contract.md) ·
[Qualification](../VALIDATION_QUALIFICATION.md#cartographe-v3-int1)

#### Convergence multi-faisceaux V3-C.2 — Implémenté

Le domaine `v3.parametric_domain/2` décrit les câbles par occurrence,
leurs ports natifs, leur identité électrique, les bornes de route et le
catalogue des appuis. Le problème `v3.problem_spec/2` fixe les objectifs,
leurs tolérances et les budgets. Le plan `v3.mutation_plan/3` développe
une pose, un parcours par câble et un appui dans une transaction
atomique. L'autorité scellée lie la fermeture XLink au périmètre
`SYNTHETIC_BENCH`.

Le criblage distingue `SCREEN_PASS`, `SCREEN_REJECT` et
`NEEDS_NATIVE_CHECK`. Une réserve de criblage requiert une mesure native
avant le classement. B.2 rouvre toute la candidate, contrôle les liaisons
électriques et mesure les dégagements, l'appui, le service et les rayons.
La classification conserve les contacts attendus et les engagements
mesurés. Une interférence interdite bloque la candidate complète. Le
front de Pareto compare les mesures arrondies au quantum de chaque
objectif. C.1 conserve ses domaines `/1` et ses plans `/2`.
[Qualification et rejeu](../VALIDATION_QUALIFICATION.md#cartographe-v3-c2)

#### Revue authentifiée et préadmission V3-A.5 — Implémenté

L'entrée `v3-admission` reconnaît le contrat `v3.a5.admission_request/1`.
Elle réexécute l'import technique A.4, puis vérifie avec OpenSSL les
signatures Ed25519 de la revue et du registre sous deux clés de confiance
distinctes. La décision lie la preuve et sa politique au lot, à la
configuration, au profil, à la fermeture XLink et à un couple
occurrence–opération. Le contrôle borne la translation, la rotation et
le porteur. Le verrou local protège les préfixes de registre et la
consommation d'un identifiant. Une reprise détecte la révocation et la
double utilisation.

L'admission qualifiée concerne `CREATE_SUPPORT` en `TEST_ONLY`. La racine
de confiance physique est absente du build livré. Le prochain couple réel
à instruire reste `CREATE_SUPPORT` sur `anchor:iso-carrier`, avec P64 ou
P66, un lot identifié et sa preuve de montage. `v3-build` n'exécute pas
de construction issue de la préadmission A.5. [Contrat A.5](../verification/v3/a5/admission_contract.schema.json) ·
[Résultat](../VALIDATION_QUALIFICATION.md#cartographe-v3-a5)

#### Consolidation C.2 et A.5 V3-INT.2 — Implémenté

L5 réunit le domaine multi-faisceaux et la préadmission signée dans un
même binaire. Les plans C.2 passent par l’autorité de banc scellée
`SYNTHETIC_BENCH`. Le contrat A.5 reste une préadmission `TEST_ONLY`.
Le registre, les signatures et le calcul C.2 ont été exercés sur le
même commit. Sans OpenSSL, la demande signée de test est refusée.
Le pin matériel reste vide et le point d’entrée de construction
refuse la mutation du cartographe.

Au commit de fusion, la suite large révèle des écarts d’empreinte des
références historiques sur checkout.
[Qualification et limites](../VALIDATION_QUALIFICATION.md#cartographe-v3-int2)

#### Rejeu des entrées historiques V3-INT.2.1 — Implémenté

CTest lance les suites L1 et L2 depuis des racines temporaires. Pour L2,
le gel V3-A rattache les sources d’inspection et d’admission au reçu
L2, qui identifie les entrées de réconciliation. Pour L1, la preuve
L1 épingle le catalogue qui porte les empreintes des sources locales.
Le dépôt distribue certaines entrées texte en LF alors que la capture
historique est en CRLF. Le préparateur de tests accepte une autre
représentation des fins de ligne uniquement si les octets obtenus
reproduisent exactement le SHA-256 publié. Il refuse tout autre écart.
Les exécutables L1 et L2 appliquent leurs contrôles d’origine. Les
assertions historiques et les références actives gardent leurs octets.

Le test L1 utilise le paquet du checkout via `PYTHONPATH` et garde
la découverte complète de la suite dans la racine temporaire. La
fiche fabricant hors Git est signalée en cas d’absence. L’inconnue
du rayon de flexion du câble monté reste explicite.
[Validation et limites](../VALIDATION_QUALIFICATION.md#cartographe-v3-int21)

#### Recherche volumique V3-C.3 — Qualifié sur banc

Les schémas `v3.parametric_domain/3`, `v3.problem_spec/3` et
`v3.mutation_plan/4` décrivent deux câbles, leurs longueurs, rayons et
diamètres propres, les polycorridors XYZ et les zones d’ancrage scellées.
Les profils de banc constituent l’autorité des enveloppes de connecteur,
des volumes de service et des contacts autorisés. L’orientation native
est verrouillée et la pose est échantillonnée dans les bornes du domaine.
Les ports et les réservations mobiles suivent leur équipement dans le
repère racine à partir de mesures de la fermeture XLink.

Le générateur propose des parcours longitudinaux à tangentes signées,
avec décalages transversaux et verticaux échantillonnés à partir des
volumes du domaine et des obstacles observés. Il combine les variantes
des deux câbles et change de stratégie sous budget. Le criblage vérifie
l’appartenance des segments et des arcs à l’union des boîtes. Il avance le
retour tangent si l’arc dépasse la transition vers la bande nominale et
priorise les parcours sans alerte d’obstacle. L’axe arrondi et les solides
sont vérifiés après sauvegarde dans des processus FreeCAD distincts. Ces vérifications
incluent la longueur d’axe hors corridor, les appuis, les distances
entre câbles, les interférences et le service. Le classement utilise
les mesures natives et les tolérances des objectifs.

Une boîte externe peut être ajoutée à une copie de banc T2 après
invalidation BRep du candidat T1 au rejeu. Les familles de support
restent celles du profil scellé. Les contrats C.1 et C.2 et la
préadmission A.5 gardent leurs points d’entrée. Les deux hiérarchies
éprouvées relèvent des bancs synthétiques Windows amd64.
[Qualification](../VALIDATION_QUALIFICATION.md#cartographe-v3-c3)

#### Transaction privée autorisée V3-A.6 — Implémenté

L’entrée L5 `v3-build` reconnaît le contrat A.6. La revue lie les octets de
l’effet, la confiance, le lot, le profil, la fermeture XLink et les preuves
attendues. `checkRegistry()` réserve la décision dans un journal durable
authentifié avant lancement. Une décision réservée reste consommée après
interruption, révocation ou perte du reçu. La compatibilité A.5 est conservée.

Le constructeur B.1 reçoit un effet calculé par L5 à partir du profil scellé
Workholding et de la pose signée. Il construit sur un clone privé. La
réouverture indépendante contrôle la géométrie native et la topologie.
Après validation T0, L5 recontrôle sous verrou le registre, l’expiration et
les empreintes avant `COMMITTED_PRIVATE`. Le reçu A.6 porte l’état publié.
Le contrat de recherche C.2 conserve son entrée propre.

La portée livrée est `TEST_ONLY / SYNTHETIC_BENCH` sur P64 de banc. La racine
de production reste vide. Le raccordement matériel reste **À valider**
avec confiance provisionnée, stockage et preuve de reprise qualifiés, lot
observé et domaine P64 ou P66 authentifié. [Protocole](../verification/v3/a6/protocol.md) ·
[Validation](../VALIDATION_QUALIFICATION.md#cartographe-v3-a6)

#### Coexistence C.3 et A.6 dans V3-INT.3

L5 dirige les plans v3.mutation_plan/4 de C.3 vers la portée
BENCH_TEST_ONLY des deux profils spatiaux scellés. Le contrat volumique
et l’obstacle indépendant alimentent le job de construction et la mesure
des deux câbles. La voie v3.a6.admission_request/1 réserve d’abord la revue
TEST_ONLY, puis transmet au même constructeur un effet signé unique
CREATE_SUPPORT(anchor:iso-carrier) sur le Workholding P64. Ses chemins
d’outils proviennent du déploiement et son contrat d’effet demeure interne.

Le vérificateur relit la fermeture et les géométries enregistrées. A.6
lie le reçu et les empreintes du natif au journal après le second contrôle
d’autorité. A.5 conserve sa préadmission. L’état de la jonction est
**Qualifié** sur bancs synthétiques Windows amd64 (`V3_INT3_GO`).
Le rejeu de clôture exerce les gardes des deux portées et le refus de la
demande physique. Le cartographe reste en `DENY` avec une racine de
confiance de production vide.
[Matrice de frontières](../verification/v3/int3/integration/boundary_matrix.json) ·
[Validation](../VALIDATION_QUALIFICATION.md#cartographe-v3-int3-cloture)

#### Réception documentaire V3-A.7 — Implémenté

`cartographe_reception` réutilise le lecteur métrologique A.4 et les
formulaires A.5. Sa matrice empreintée au build définit les relevés du
couple `CREATE_SUPPORT / anchor:iso-carrier` pour P64 et P66. Il vérifie
le dépôt courant contre une empreinte transmise séparément et la politique
d’import contre son empreinte. Les pièces privées, les repères et les
intervalles conservateurs donnent une complétude par occurrence.
La sortie documentaire est en lecture seule, avec décision `DENY`.
La revue habilitée et l’admission continuent sur les autorités A.5/A.6.
[Guide opérateur](../verification/v3/a7/operator_guide.md) ·
[Validation](../VALIDATION_QUALIFICATION.md#cartographe-v3-a7)

## 3. Contexte et déploiement

```text
 Application Qt / CLI sur la station
        |
        +-- services applicatifs et domaine C++17
        +-- adaptateurs stockage, processus, HTTP, ROS 2 et cartographie
        +-- Docker Compose : LIO, télémétrie, PX4 SITL, Gazebo
                           |
                           v
 Jetson Orin NX 16 Go / ROS 2 -- uXRCE-DDS/MAVLink -- Pixhawk 6X / PX4
        |                                    même porteuse Holybro
        +-- capteurs, localisation, perception, mission, traitement
```

| Cible | Organisation | État |
|---|---|---|
| Windows 11 | station Qt 6 et outils C++17 natifs | implémenté et testé localement |
| Docker `amd64` | ROS 2 Humble/Jazzy, LIO et PX4/Gazebo isolés | implémenté préliminaire |
| Jetson Orin NX 16 Go `arm64` | JetPack, pilotes hôte et conteneurs ROS 2 sur porteuse Holybro Pixhawk Jetson | déploiement **Planifié** ; exécution et thermique **À valider** |
| Pixhawk 6X module seul | PX4 et failsafes indépendants du compagnon sur la même porteuse | SITL partiel ; intégration matérielle **À valider** |

**Déploiement sol proposé le 10 octobre 2026.** Un portable de récupération
est envisagé pour QGroundControl, base RTK, préparation/revue légère et
transfert des données ; le PC fixe existant assure les traitements lourds.
La configuration minimale acceptée pour la définition est dans
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#pc-sol-prototype).
Windows 11 x64 est la première cible proposée pour le portable, selon les
essais locaux déjà disponibles ; ces essais ne qualifient pas ce matériel
encore non identifié. La fenêtre actuelle impose 1200 × 760 au minimum dans
[`main_window.ui`](../../software/cpp/ui/main_window.ui). Affichage, ressources,
copie des données et déploiement sur le portable restent **À valider**.
Aucune modification logicielle ni compilation nouvelle dans cette passe.

Compose sépare trois environnements : Ubuntu 22.04 / ROS 2 Humble pour données,
LIO et télémétrie ; Ubuntu 24.04 / ROS 2 Jazzy pour les ponts et la simulation ;
et l'image PX4/Gazebo épinglée dans `compose.yaml`. Les données brutes sont
montées en volume et ne sont jamais incorporées aux images. Le banc utilise
actuellement PX4 `v1.18.0-beta2`, uniquement à titre expérimental ; une version
stable épinglée est requise avant qualification formelle. Le domaine ROS de
banc est `42`.

La cible matérielle réunit le module Pixhawk 6X et le Jetson Orin NX 16 Go
sur la **Holybro Pixhawk Jetson Baseboard**. Le partage de porteuse ne modifie
pas la frontière d'autorité : PX4 reste autonome pour le vol critique, et ROS 2
ne transmet que des consignes de haut niveau. L'interface physique retenue pour
uXRCE-DDS ou MAVLink, ses ports, débits, redémarrages et pertes restent
**À valider**. Le PM08-CAN alimente POWER1 et POWER2 par deux BEC distincts,
avec mesure DroneCAN séparée sur CAN1 ; CA01 possède son 5 V local protégé
pour la radio et la porteuse reçoit un 12 V candidat par XT30. Les brochages,
protections et essais de défaut relèvent de
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md). Une perte ou un redémarrage
du Jetson ne doit pas empêcher les failsafes PX4 ; ce comportement doit être
démontré sur la configuration matérielle finale.

### 3.1 Acheminement RTK et partage de la liaison RF

La sélection matérielle étudiée est un **Holybro H-RTK F9P DroneCAN Rover
Helical STM32G4** sur le drone, dont la sortie UART2/PPS doit être vérifiée sur
la révision livrée, et un **Holybro H-RTK F9P Base (SKU 12022)** au sol. Statut
de leur intégration logicielle : **Planifié / À valider**. La base se raccorde en
USB à QGroundControl, qui encapsule les corrections RTCM dans des messages
MAVLink 2 `GPS_RTCM_DATA`. Le chemin candidat est : QGroundControl → Wi-Fi local
du TX Backpack de la Pocket ELRS → RF ELRS commune → RP4TD en mode MAVLink →
UART Pixhawk 6X → PX4 → rover DroneCAN. Le port CAN, la configuration PX4 et
la continuité effective jusqu'au rover sont définis dans
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md) et restent **À valider**.

Cette même liaison doit transporter les commandes **ponctuelles** de la station
(mission, mode, repositionnement autorisé) vers PX4 et le retour de télémétrie
essentielle. Les manches de la Pocket empruntent la voie RC du même système
ELRS ; leur disponibilité lorsque QGroundControl ou le Wi-Fi local s'arrête
doit être démontrée. Le flux de corrections est continu et occupe la montée
sol → drone : la référence PX4 d'environ 300 octets/s sous MAVLink 2 n'est
pas une mesure de la base F9P sélectionnée. À 333 Hz Full, ExpressLRS annonce
environ 735 octets/s montants avec RC et 1470 descendants, **avant pertes,
réémissions et effet du profil EU-LBT** ; à 250 Hz, la montée annoncée est
environ 300 octets/s. Les volumes F9P, les débits utiles et la marge pour les
commandes sont donc **À valider** sur le matériel. Les transferts volumineux
de missions ou paramètres doivent être planifiés hors phase critique et la
télémétrie PX4 limitée aux messages réellement requis.

Les consignes Offboard dynamiques restent générées localement par le Jetson
vers PX4 selon la frontière du §2. Une boucle de déplacement pilotée en continu
depuis la station n'est pas couverte par le partage RF candidat : PX4 exige
un signal Offboard continu supérieur à 2 Hz et déclenche un repli si ce signal
disparaît. Sa latence, sa fraîcheur et sa coexistence avec RTCM/RC exigeraient
une qualification distincte. La perte des corrections RTK ne doit pas être
confondue avec une perte RC ou une perte Offboard ; les réactions associées
relèvent de PX4 et des scénarios de [DOC-VAL](../VALIDATION_QUALIFICATION.md).
La correction de position via CAN2 et la distribution PPS/GPRMC pour la
synchronisation sont deux fonctions distinctes : une position RTK fixe ne
prouve pas que les horloges Airy, PX4 et Jetson sont alignées.

Sources de capacité et de protocole :
[ExpressLRS MAVLink](https://www.expresslrs.org/software/mavlink/),
[PX4 RTK](https://docs.px4.io/main/en/advanced/rtk_gps),
[PX4 Offboard](https://docs.px4.io/main/en/flight_modes/offboard).

## 4. Architecture de la station

### 4.1 Couches et sens des dépendances

```text
 presentation (Qt Widgets/.ui)
          |
          v
 application --------> domain/ports
          ^                 ^
          |                 |
 composition ------ adapters/process/storage/runtime/mapping/runners
          |
       support
```

Le point de composition construit les implémentations concrètes. Les services
applicatifs ne dépendent pas des classes techniques. `Qt Widgets` reste confiné
à la présentation ; `Qt Network` reste dans les adaptateurs réseau.

### 4.2 Modules compilés et tests associés

| Cible CMake | Responsabilité | Dépendances principales | Tests directs |
|---|---|---|---|
| `drone_agricole_station` | description des capacités et modules de la station | Qt Core | `test_station_architecture` |
| `drone_agricole_support` | types communs, JSON, métriques de benchmark | Qt Core/Gui | `test_benchmark_support` |
| `drone_agricole_algorithms` | carte de points, trajectoire, rangs, projection caméra, reconstruction | support | `test_adaptive_point_map`, `test_trajectory_analysis`, `test_row_detection`, `test_camera_color_fusion`, `test_scan_reconstruction` |
| `drone_agricole_storage` | résultats, rosbag ROS 1 et normalisation des datasets | support | `test_ros1_bag` et tests de dépôts |
| `drone_agricole_mapping` | modèle viticole et adaptation/reconstruction FriûlBot | storage, algorithms, TIFF, YAML | `test_vineyard_map` et tests cartographiques d'intégration |
| `drone_agricole_runtime` | télémétrie, orchestration LIO, accès ROS 2 ou adaptateurs HTTP/stubs | storage, algorithms, Qt Network | `test_telemetry_bridge` |
| `drone_agricole_catalog` | contrats et catalogue des définitions | support | `test_contract_registry` |
| `drone_agricole_runners` | résolution des runners et commandes approuvées | catalog, YAML | `test_runner_registry` |
| `drone_agricole_data_services` | dépôt de résultats et comparaison | catalog, mapping, runtime | `test_result_repository`, `test_comparison_service` |
| `drone_agricole_application` | cycle commun de tâche, brouillons, préférences et inventaire via ports | Qt Core | `test_run_service`, `test_workspace_service` |
| `drone_agricole_workspace_storage` | état local atomique et lecture de la BOM prototype | application, Qt Core | `test_workspace_service` |
| `drone_agricole_process` | exécution et annulation de processus derrière un port | application | `test_process_backend` |
| `drone_agricole_composition` | assemblage des services et commandes UI/CLI | services, runners, process | tests station et dashboard |
| `drone_agricole_presentation` | navigation, pages, rendu trajectoire/3D et interactions | application, support, Qt Widgets | `test_trajectory_view`, `test_dashboard_mapping`, `test_station_navigation`, `test_dashboard_smoke` |

`drone_agricole_core` est une cible de compatibilité sans source propre. Elle ne
doit pas redevenir un noyau universel.

### 4.3 Exécutables

VS Code peut ouvrir la racine ou `software/cpp`. Dans ce dernier cas,
`software/cpp/.vscode/settings.json` fixe la racine CMake à `../..` ; les tâches
et le lancement utilisent les profils centraux et le même répertoire `build/`.
Il n'y a pas de deuxième projet CMake autonome ni de copie des profils.

| Exécutable | Rôle | UI |
|---|---|---|
| `drone-agricole-dashboard` | station de mission desktop | Qt 6 Widgets |
| `drone-agricole-tools` | accès headless aux mêmes capacités applicatives | CLI |
| `drone-agricole-px4-client` | diagnostic du service PX4 distant | CLI |

Le client PX4 desktop vérifie l'API locale avant un essai et peut démarrer les
services Compose explicitement approuvés du banc s'ils sont absents. Les API
restent publiées sur la boucle locale. Cette préparation ne déclenche jamais
l'essai Offboard : requête validée, runner autorisé et verrou SITL restent
obligatoires.

### 4.4 Paquets ROS 2 implémentés

| Paquet/cible | Fonctionnement | Test |
|---|---|---|
| `drone_agricole_px4_bridge/px4_bridge_support` | conversions de repères, plan Offboard et contrat du runner | `test_frames`, `test_offboard_plan`, `test_runner_contract` |
| `drone_agricole_px4_bridge/state_bridge` | traduit l'état PX4 vers les messages ROS 2 et diagnostics, sans commander le vol | scénarios SITL et intégration **À valider** au-delà des tests de support |
| `drone_agricole_px4_bridge/offboard_test` | exécute uniquement le scénario Offboard SITL doublement verrouillé | carré et perte Offboard historiques ; régression active **À valider** |
| `drone_agricole_px4_bridge/runner_server` | expose le lancement contrôlé des scénarios au service local de station | contrat unitaire et test d'intégration du runner |
| `livox_ros_driver2_msgs_compat` | fournit les messages officiels nécessaires au rejeu Livox hors ligne | construction ROS 2 et rejeu ; pas de logique métier |

### 4.5 Navigation

La navigation est organisée autour des activités et objets métier. Les pages
actuelles couvrent les six espaces V3 ci-dessous et le détail d'un résultat.
Une nouvelle fonction n'ajoute pas automatiquement une
destination principale : elle fournit contrats, services, actions contextuelles
et vues spécialisées. Une tâche active reste observable lors d'un changement de
page. La fermeture de la station demande l'annulation d'un traitement actif et
attend sa fin ; aucun détachement implicite n'est autorisé. Une reprise après
fermeture n'est pas présumée.

Les formulaires principaux sont :

- `ui/main_window.ui` ;
- `ui/execution_page.ui` ;
- `ui/results_page.ui` ;
- `ui/comparison_page.ui` ;
- `ui/result_view_page.ui`.

### 4.6 Interface métier V3 — 23 octobre 2026

**Cadrage.** Le responsable demande explicitement la refonte selon ses deux
maquettes MagicPath et la préparation des nouvelles fonctions. Cette passe
logicielle réversible est bornée aux parcours visibles, à la réutilisation
des bancs existants et aux services locaux nécessaires. Elle ne clôt ni ne
remplace la priorité de faisabilité physique du cartographe. Aucun achat,
déploiement embarqué ni essai physique n'est inclus. Le signal de fin est
une compilation Windows, des tests de parcours/persistance et une revue des
captures ; la qualification terrain reste **À valider**.

Les deux maquettes ont le même code fonctionnel : seul le thème diffère.
Leurs identifiants et révisions exactes sont conservés dans
[`magicpath_reference.json`](../../configs/station/magicpath_reference.json).
La transposition conserve C++17/Qt Widgets, les formulaires `.ui`, les vrais
résultats locaux et les garde-fous des runners. Les nombres, cartes illustrées,
scores et états « Connecté » fictifs de la maquette ne sont pas importés.

| Espace | Rubriques et comportement |
|---|---|
| Accueil | Dashboard, Récents et Favoris ; compteurs locaux, raccourcis, activité et résultats épinglés |
| Missions | Préparation de brouillons persistants, Supervision des données disponibles du pont, Journal des résultats de banc |
| Données | Catalogue déclaré, Acquisitions et Import / Export ; recherche, détails des sources et export des métadonnées |
| Simulations (routes `bench` conservées) | Configuration et Exécution partagent la même page et le même `RunService` ; Résultats, Comparaison et Modèle 3D pour préparer le prototype Gazebo |
| Analyse | Cartes et Trajectoires réelles, Métriques et Rapports issus des archives, export Markdown ; absence d'artefact explicite |
| Système | Paramètres des deux thèmes, Matériel lu dans la BOM, Diagnostics et réserves de Maintenance |

`MissionsPage`, `DataPage`, `SystemPage` et `AnalysisPage` possèdent leurs
formulaires. Le shell compose les pages et les routes ; les brouillons,
préférences et favoris sont gérés par `WorkspaceService`, partagé avec
`drone-agricole-tools station-workspace`. Les interfaces `IWorkspaceStore`
et `IHardwareInventory` isolent le stockage. `JsonWorkspaceStore` écrit
atomiquement `results/station/workspace.json`, avec verrou et contrôle de
modification concurrente. Un fichier corrompu est signalé et conservé.
`BomHardwareInventory` relit la nomenclature canonique du prototype sans
la modifier ; quantité et masse inconnues restent inconnues. La définition
matérielle n'est jamais interprétée comme un état de connexion.

Le thème « Clair professionnel » bleu ou « Clair premium sobre » vert
est choisi dans Système → Paramètres et conservé dans l'état local.
La navigation conserve la configuration du bench et son traitement actif.
Les brouillons ont un identifiant, une parcelle, une opération, un drone,
un dataset/séquence, des notes et contrôles déclaratifs ; altitude/vitesse
inconnues restent nulles. `execution_allowed=false` et `status=draft`
interdisent de les confondre avec un paquet de mission exécutable. L'import
crée une identité locale distincte. Le transfert réel, la géofence validée,
la planification qualifiée, l'approbation de carte, les pilotes et la commande
de mission demeurent **Planifiés / À valider**, avec prérequis visibles.

Traçabilité : `UI-V3-001` → shell, routes et thèmes → `test_station_navigation`
et `test_workspace_pages` ; `UI-V3-002` → service/stockage/BOM →
`test_workspace_service` ; `UI-V3-003` → archives, comparaison et analyse →
`test_workbench_pages`. Résultats et limites dans
[DOC-VAL §10](../VALIDATION_QUALIFICATION.md#station-v3).

## 5. Contrats et données

Le catalogue décrit séparément datasets, simulations et runners. Les schémas
JSON sous `configs/visualization/schemas/` définissent les structures attendues.
Leur présence et leur chargement ne démontrent pas leur application : la
validation actuelle est partielle, avec des contrôles codés dans le registre,
la préparation et la finalisation. La validation intégrale et la cohérence
croisée des identifiants restent **À valider** ; le message de succès T0 ne
doit pas être interprété comme une conformité intégrale aux schémas
([AUD-010](../VALIDATION_QUALIFICATION.md#aud-010)). Les adaptateurs historiques
normalisent les résultats LIO et PX4 en lecture seule.

Objets métier cibles :

| Objet | Rôle | État |
|---|---|---|
| définition de dataset/simulation | paramètres, capacités et provenance | implémenté |
| exécution et résultat | cycle, état, artefacts, métriques et erreurs | implémenté |
| `SurveyMissionPackage` | demande et configuration d'acquisition | planifié |
| `SurveyRunPackage` | acquisition reçue et contrôlée | planifié |
| `VineyardMap` | carte versionnée, repère, géométrie et qualité | modèle partiel implémenté |
| paquet de mission de traitement | carte liée, trajectoires et prescription | planifié |
| rapport de traitement | réalisé, événements et écarts | planifié |

Une carte approuvée est immuable. Toute édition produit une nouvelle version.
La preuve d'approbation lie au minimum identité, version du manifeste et
empreinte du contenu. Le transfert vérifie manifeste, empreintes, compatibilité,
cible et accusé de réception. Signature cryptographique, identités, transport
et migrations restent **À valider**.

Les paquets inter-étapes contiennent au minimum :

- `SurveyMissionPackage` : parcelle, repère, couverture, géofence, trajectoire
  de relevé, configuration attendue, critères qualité et empreinte ;
- `SurveyRunPackage` : manifeste, calibrations, données brutes, aperçu de
  trajectoire non autoritatif, santé, événements et empreintes ;
- `VineyardMapPackage` : géoréférence, trajectoire optimisée, géométrie, terrain,
  sémantique, entités, topologie, données de navigation, qualité et empreintes ;
- `TreatmentMissionPackage` : carte exacte, prescription, ordre des rangs,
  trajectoire, corridor, paramètres autorisés, résultat de simulation et état ;
- `MissionReportPackage` : trajectoires commandée/réelle, localisation, sûreté,
  obstacles, bras, débits, zones traitées, événements PX4 et configuration.

Le modèle de carte représente terrain, terrasses, rangs, pieds, poteaux, fils,
murs, obstacles, zones interdites et confiance. Les géométries lourdes peuvent
être référencées par URI et empreinte plutôt qu'imbriquées dans les messages.

### 5.1 Outils de simulation du cartographe — ORCH-GZ-1

Le CMake autonome [simulation/CMakeLists.txt](../../simulation/CMakeLists.txt)
compile en C++17 les modules masse et énergie, `cartographe-model`,
`cartographe-energy` et `cartographe-evidence`, indépendamment de la station.
Les algorithmes masse/énergie utilisent la bibliothèque standard ; Qt Core
assure JSON, empreintes et écritures atomiques dans les exécutables. Les
adaptateurs Python FreeCAD ne portent que l'extraction BREP/maillage et les
contrôles de dérivation ; aucune logique de vol ou d'énergie n'y est ajoutée.

Le validateur dédié applique les cinq schémas T0 canoniques et les mots-clés
qu'ils utilisent, puis contrôle identifiants, paramètres/entrées communs,
empreintes réelles, chemins confinés, dates et événement terminal. Il refuse
les mots-clés non supportés. Le scellement contrôle également la campagne
brute, ses configurations, son binaire effectivement exécuté et son CSV.
Les cas négatifs sont exécutés, sans prétendre corriger tous les producteurs
historiques de la station : AUD-010 reste ouvert pour ceux-ci.

Le runner Offboard borne armement, mission, atterrissage et supervision.
Un résultat écrit sans erreur et une observation fraîche posé/désarmé sont
nécessaires au succès ou à l'annulation ; crash ou dépassement ne confirment
jamais un posé. Les tests de politique et la compilation native du serveur
réussissent. Le 24 octobre, le pont et les runners sont reconstruits sous
ROS 2 Jazzy/Linux amd64 ; les quatre exécutables CTest de ce paquet passent.
Le runner exige une odométrie de moins de 0,5 s et un statut de moins de
1 s avant chaque émission de consigne ; valeurs négatives ou non finies
refusées. La perte de fraîcheur déclenche l'atterrissage borné.
Le préflight vérifie aussi l'identifiant effectif et l'unicité de l'airframe
dans l'image : 4010 entrait en collision avec `gz_x500_mono_cam`, d'où
l'identifiant cartographe 40000. Les capteurs constants sont rejetés par
PX4 ; une fixture de bruit synthétique permet l'intégration sans désactiver
ses contrôles. Elle ne calibre pas les capteurs matériels.
Versions, limites et preuves sont dans DOC-VAL §9.3 et le
[manifeste du véhicule](../../simulation/gazebo/models/cartographe/model_manifest.json).
Les commandes d'utilisation sont dans `simulation/README.md`.

### 5.2 Passerelle CAO → Gazebo dans la station — 24 octobre 2026

**Implémenté**, profil du prototype cartographe actif uniquement. La demande
utilisateur supprime la succession de commandes manuelles du §5.1 en ajoutant
**Simulations → Modèle 3D**, route `bench-model`. La page possède son formulaire
`.ui`, un aperçu navigable métrique échantillonné, le choix du Python fourni
avec FreeCAD, une préparation depuis la CAO ou depuis les maillages contrôlés,
la progression, l'annulation et l'ouverture du dossier final. Le contexte et
la progression restent accessibles pendant la navigation. Les STL complets
sont destinés à Gazebo ; l'aperçu par points n'est pas un nouveau modèle physique.

`GazeboExportService` dépend du port `IGazeboExportBackend` et de Qt Core.
`LocalGazeboExportBackend` porte fichiers/processus et choisit les adaptateurs
FreeCAD existants. Le générateur C++17 SDF/airframe est partagé entre la station
et `cartographe-model`, par la cible `drone_agricole_gazebo_model` ; les contrôles
de dépendances CMake restent effectifs. La composition injecte le backend ;
UI et `drone-agricole-tools gazebo-model` consomment le même service. Aucun
calcul de masse, d'énergie ou de vol n'est déplacé dans la page ou le shell.

La conversion s'effectue dans un dossier temporaire du projet, hors du thread
UI, avec budget total de 15 minutes et annulation vérifiée par tranches de
lecture ou attente de processus. Le processus Python est directement détenu
et arrêté avant publication d'un état terminal. Un verrou interdit deux
exports simultanés entre instances ; une destination existante est refusée.
La publication finale renomme le dossier préparé après contrôle des empreintes,
des sources restées inchangées et des propriétés du scénario. Le signal
`completed` vient après la fin du worker et permet une nouvelle préparation.

Le dossier `results/simulation/model_exports/<identité>/cartographe` contient
SDF/config, cinq STL, géométrie/collisions, scénario, airframe 40000, monde,
aperçu et `export_manifest.json` (`drone_agricole.gazebo_export.v1`). Ce manifeste
d'artefact référence sources et empreintes ; il ne remplace ni BOM ni manifeste
CAO. La préparation n'est pas une exécution de mission : aucun T0 de vol n'est
fabriqué, aucun Docker/PX4 n'est démarré. Import arbitraire STEP/FCStd, édition
des paramètres physiques et pilotage de Gazebo depuis cette page restent hors
de ce profil. Tests et limites : DOC-VAL §10.2, `UI-GZ-001` et `T-CARTO-GZ-01`.

### 5.3 Réconciliation CAO et masses — ORCH-CAO-MASSE-1, 25 octobre 2026

La nouvelle priorité suspend les extensions et campagnes Gazebo/PX4. Les
adaptations logicielles de ce lot servent uniquement la fiabilité des données
existantes. `cartographe-bom-mass`, en C++17/Qt Core, lit la BOM canonique,
les sources conservées et l'extraction BRep FreeCAD. Il vérifie les empreintes
des natifs et des extracteurs, la fermeture conforme au manifeste, les couples
fichier/objet, les propriétaires physiques et le graphe des inclusions.
`--publish` actualise en place la BOM, le registre massique et leurs preuves.
Les adaptateurs Python restent limités à FreeCAD et à la synchronisation
déclarative ; les sommes, contributions et propriétés massiques sont en C++.

La somme disponible est indépendante de la connaissance du centrage et des
inerties. Les masses conditionnelles ou maximales ne deviennent pas des masses
nominales installées ; un enfant d'un ensemble de masse inconnue peut contribuer
au sous-total sans fermer son parent. Une occurrence sans propriétaire reste
bloquante. Les fabrications candidates et les ensembles documentés sont
distingués dans les résultats. Le centrage calculé d'un sous-ensemble homogène
ne devient pas celui du drone.

La reprise du 26 octobre ajoute les masses documentaires par composant et
les contributions partielles de périmètre explicite, par exemple le corps
d'un moteur sans ses cordons. Un parent n'est calculé complet que si son
contenu est déclaré exhaustif, non vide et entièrement connu. Les inclusions
sont résolues indépendamment de l'ordre des lignes. Les doublons de
contributions et le recouvrement entre masse partielle et composants déjà
comptés sont refusés. Chaque ligne incomplète reçoit `probleme_massique`
dans la BOM ; une ancienne masse unitaire ne subsiste pas après invalidation
de ses conditions. Le classeur reprend le problème en clair dans ses notes.
Les tests couvrent ces cas, les quantités corrigées et les sous-totaux ;
la publication est vérifiée par une seconde exécution identique sur les cinq
artefacts dérivés. Les réserves géométriques restent distinctes et ne sont
pas effacées par la connaissance d'une masse commerciale.

Les estimations OEM peuvent être définies par occurrence physique et objet
source dans un même fichier CAO : le calcul vérifie propriétaire BOM, fichier,
objet, empreinte, volume et densité avant addition. Les densités analogues
restent candidates et ne ferment pas la masse réelle de la ligne. La masse du
kit d'approvisionnement reste visible hors du total embarqué ; les scénarios
de propulsion non confirmés restent distincts des contributions additionnées.

La passerelle conserve les exports historiques et signale `preview_stale`
quand leurs sources ont changé, y compris après rafraîchissement d'un aperçu
déjà chargé. Son scénario synthétique de 6 kg reste distinct d'une masse
issue de la BOM. L'inventaire affiche la nature et les réserves de masse.
Les tests ciblés, les cas négatifs et les limites sont dans
[la preuve ORCH](../../hardware/mecanique/cartographe/verification/controle_orch_cao_masse_1.json).
Ces adaptations sont **Implémenté** ; aucune fidélité physique ou campagne
de simulation nouvelle n'est qualifiée.

## 6. Chaîne cartographique

```text
 adaptateur capteurs
   -> synchronisation et calibration
   -> localisation LiDAR/IMU
   -> accumulation de points colorisés
   -> reconstruction de surface
   -> scène viticole versionnée
   -> détection de rangs et étude de trajectoire
```

État actuel : l'adaptateur FriûlBot, la projection caméra, une odométrie ICP
LiDAR bornée, l'accumulation et une triangulation locale sont implémentés à un
niveau préliminaire. Ils publient diagnostics et état partiel en cas d'échec.
Ils ne constituent ni un LIO qualifié, ni une carte globale qualifiée pour les
collisions. EscaYard est conservé comme régression historique, pas comme nouveau
parcours actif.

La composition RGB issue de bandes visibles multispectrales reste un diagnostic,
pas une couleur radiométriquement calibrée. Le sol demeure dans la scène ; le
masque de végétation sert uniquement à la détection des rangs. Le rendu courant
reste un `QWidget` natif. Pour toute simulation future, enveloppe visuelle,
géométrie de collision et paramètres physiques sont des modèles distincts.

Les poses de référence, RTK, roues ou SLAM d'un dataset ne sont pas utilisées
comme entrées cachées de prédiction. Une absence de pose n'est jamais compensée
par une trajectoire inventée.

### 6.1 Détection des rangs et trajectoires hors ligne

La baseline reste géométrique et explicable : contrôle CRS/unités, estimation
du sol, normalisation des hauteurs, sélection de végétation/structures,
projection 2D, composantes ou densité locale, estimation robuste des axes puis
ajustement de courbes/splines. Les axes sont ordonnés dans un graphe de parcelle ;
les limites observées et zones inconnues contraignent le corridor. La trajectoire
nominale est issue du centre libre, lissée avec courbure, pente, vitesse et
accélération bornées.

Une baseline par lignes droites peut servir au test initial, mais ne satisfait
pas `MAP-FUN-007` sur rangs courbes ou irréguliers. Les métriques attendues sont
erreur latérale des axes, rappel des rangs, ruptures, topologie, largeur libre,
distance aux obstacles et respect dynamique. LaMole/Grospoli reste le cas
difficile sous autorisation ; EscaYard sert de baseline géospatiale publique et
FriûlBot de baseline temporelle LiDAR–caméra.

### 6.2 Assemblage des scans et surface observée

Dans **Essais → Cartographie 3D LiDAR–caméra**, la variante
**Assemblage des scans et surface 3D** (`scan_surface_v1`) utilise le même
service UI/CLI que la capture locale. Les paramètres sont l'instant de départ,
la durée, l'intervalle entre scans, la portée, la cellule de fusion et la
longueur maximale des arêtes. Les réglages initiaux sont **À valider**.

`algorithms/ScanReconstruction` fournit le recalage rigide ICP à six degrés de
liberté, la triangulation du voisinage angulaire des anneaux LiDAR et la fusion
des sommets. `adapters/mapping/FriulBotReconstruction` décode les scans,
applique la sélection temporelle, associe les captures caméra et archive les
produits. La variante traite une fenêtre de 1 à 60 s ; les limites de travail
sont 350 scans réguliers, 400 scans avec captures, 256 Mio de messages,
100 000 sommets et 150 000 faces. Atteindre la capacité de surface interrompt
l'accumulation avec résultat partiel explicite.

Le premier scan définit le repère de carte. Les poses expriment
`p_carte = R_carte_lidar × p_lidar + t_carte_lidar`. Les horodatages du bag
sont conservés en nanosecondes sous forme de chaînes, sans perte de précision.
Les scans caméra proches remplacent le scan régulier dans la sélection ; leurs
couleurs ne sont projetées qu'avec leurs propres images. Un désaccord entre
nombres de déclenchements et jeux d'images désactive la couleur.

L'ICP emploie deux résolutions et des correspondances tronquées. Les contrôles
préliminaires comprennent convergence, recouvrement ≥ 50 %, résidu ≤ 0,25 m,
translation ≤ 2 m et rotation ≤ 20° entre scans. Une géométrie colinéaire, une
interruption temporelle ou un recalage insuffisant ne génère pas de pose de
remplacement. Avec moins de deux scans acceptés, le traitement échoue ; sinon
la portion acceptée est archivée comme carte partielle. Ces seuils ne sont pas
une qualification de précision absolue et restent **À valider**.

La surface conserve les discontinuités : arêtes trop longues, triangles
dégénérés et cellules angulaires sans mesure sont exclus. Les faces observées
des différents scans sont recalées et dédupliquées par sommets voxelisés.
L'espace inconnu n'est pas fermé artificiellement. Le résultat est une surface
triangulée ouverte, avec une couleur grise là où aucune image n'est projetée.

Chaque archive contient `map_prediction.json`, `map_replay.json`,
`estimated_poses.json` (poses et diagnostics par recalage) et `surface.ply`.
Le contrat de rejeu ajoute un objet `surface` (sommets, triplets d'indices et
couleurs), en conservant la lecture des archives antérieures. L'UI affiche la
surface ou le nuage, et peut masquer la trajectoire d'acquisition superposée.
Cette superposition ne constitue pas un contrôle de collision.

Limites : odométrie LiDAR sans fusion IMU, correction intra-scan ni fermeture
de boucle ; appariement temporel/calibration à qualifier, dérive possible et
triangulation locale des mesures. L'assemblage complet d'une parcelle, la
surface qualifiée pour les collisions et la simulation dynamique du drone de
traitement restent à valider ou à développer.

## 7. Logiciel embarqué cible

| Domaine ROS 2 | Responsabilité | État |
|---|---|---|
| acquisition/calibration | pilotes, timestamps, diagnostics et extrinsèques | planifié/intégrations tierces |
| localisation | LIO/VIO/GNSS et état autoritatif | benchmarks réalisés ; sélection embarquée **À valider** |
| perception/cartographie | végétation, terrain, obstacles, fils et carte locale | planifié, briques station préliminaires |
| navigation | route, corridor, trajectoire et interface PX4 | SITL partiel puis planifié |
| mission/sûreté | machines à états, gardes, abandon applicatif | planifié |
| traitement | bras, ciblage, pompe, vannes, débit et air | planifié |
| journalisation | manifeste, événements et données nécessaires au rapport | planifié |

Les processus critiques sont isolés initialement. Le superviseur doit détecter
la disparition d'un processus sans dépendre de celui-ci. La composition
intra-processus des flux lourds n'est admise qu'après mesure.

### 7.1 Composants logiques cibles

| Composant | Responsabilité | Validation principale |
|---|---|---|
| `sensor_manager` | pilotes, acquisition, contrat d’horloge et diagnostics de synchronisation | `T-AIRY-SYNC-01` puis offsets/incertitudes, association image-exposition, pertes et redémarrages sur banc |
| `calibration_manager` | calibrations versionnées et arbre de repères | cohérence, empreintes et reprojection |
| `px4_bridge` | état PX4 et consignes bornées | SITL, perte Offboard et conversions de repères |
| `lio_adapter` | normaliser l'odométrie du moteur LIO retenu | ATE/RPE, complétude, ressources et rejeu |
| `localization_manager` | état local continu et correction globale | perte GNSS, sauts, covariance et fraîcheur |
| `semantic_perception` | classes, objets et confiances | précision/rappel/IoU, calibration et latence |
| `terrain_model` | surface, pente, rugosité et ruptures | erreur d'altitude et détection des ruptures |
| `obstacle_tracker` | obstacles locaux et prédiction | rappel, distance, faux libres et latence |
| `map_builder` | géométrie 3D, fusion et qualité | cohérence des surfaces, couverture et incertitude |
| `map_server_vineyard` | versions de carte et tuiles embarquées | compatibilité, immutabilité et migration |
| `route_planner` | ordre global des segments | coût, atteignabilité et contraintes |
| `local_planner` | corridor et trajectoire locale | collisions, marges, dynamique et temps réel |
| `trajectory_controller` | convertir la trajectoire en consignes PX4 | cadence, bornes, expiration et refus PX4 |
| `arm_controller` | déploiement, rétraction et défauts du bras | banc, timeouts, blocages et état sûr |
| `treatment_targeter` | associer cible, carte et fenêtre temporelle | erreur d'association et décalage temporel |
| `spray_controller` | débit, pompe, vannes et mesure | banc eau/traceur, dose et fermeture sûre |
| `airflow_controller` | assistance d'air et compensation | banc puis essais agronomiques autorisés |
| `mission_manager` | machine à états applicative | transitions, annulation, reprise et défauts |
| `safety_supervisor` | invariants et inhibition applicative | injection de chaque défaut critique |
| `logger_recorder` | manifeste, événements et toutes les données brutes LiDAR/caméra acquises pendant la mission, avec horodatages pour rejeu | intégrité, compteurs d'acquisition, débit soutenu à chaud, stockage plein et rejeu déterministe |
| `benchmark_runner` | campagnes reproductibles hors vol | contrats, empreintes et comparaison multi-runs |

**Besoin d'enregistrement du prototype retenu le 10 octobre :** conserver
toutes les données brutes LiDAR et caméra pendant toute la mission ; le
scénario de dimensionnement choisi est caméra à 5 images/s sur 20 minutes.
Le SSD Samsung MZ-V9S1T0BW 1 To est retenu dans `AVI-SSD` ; le format brut,
le budget complet et la qualification du stockage restent ouverts dans
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#stockage-prototype).
Cette décision ne prouve pas l'implémentation de `logger_recorder` : acquisition,
pertes explicites, stockage plein, arrêt propre et rejeu restent **Planifiés / À valider**.

#### 7.1.1 Contrat temporel du cartographe — **Planifié / À valider**

La décision métier de capture appartient à `mission_manager` sur la Jetson
sous ROS 2. `sensor_manager` vérifie la disponibilité des capteurs et du
temps, coordonne la demande et assemble les données ; l'adaptateur PX4
traduit la demande en commande caméra compatible avec le firmware retenu.
PX4 génère l'impulsion physique, CA01 adapte les signaux et la Basler expose.
Le transport exact de commande (MAVLink local ou `VehicleCommand` via un
pont ROS 2 exposant les topics requis) reste **À valider** ; ROS 2 ne garantit
ni l'instant du front AUX ni une exposition simultanée des périphériques.
Pendant un relevé, un seul producteur de commandes caméra est actif ; les
déclenchements autonomes de mission PX4 et les tests QGroundControl sont
désactivés ou exclus du relevé. Les flux GNSS, IMU et Airy restent continus.

Le contrat de capture cible conserve la session, un identifiant de demande,
la cible, la date de demande et sa limite de validité. Il distingue demande
émise, acceptation/refus, déclenchement observé, exposition mesurée, image
reçue, puis association complète ou échec explicite. Un acquittement de
commande ne prouve pas l'exposition. La stratégie initiale sérialise les
demandes ponctuelles ; après une réponse perdue, aucune répétition aveugle
n'est admise tant que le résultat précédent reste indéterminé. Vérifier les
doublons, les demandes périmées et la remise à zéro des séquences au banc.
La limite de validité côté Jetson ne garantit pas que PX4 rejette un ordre
déjà en transit : le protocole, les délais et la politique de purge/reprise
doivent être établis avant implémentation. Aucun identifiant applicatif
n'est supposé transmis par le fil AUX : la correspondance
`session/demande -> séquence PX4 -> ExposureActive -> Frame ID`
doit être démontrée, y compris après pertes et redémarrages. Ces contrats
sont **Planifiés** ; leur implémentation et leur qualification restent ouvertes.

La chaîne candidate exploite le Rover Helical STM32G4 pour la navigation RTK
par CAN2 vers PX4 et, sous réserve de vérification matérielle, pour le PPS
physique. La sortie GPRMC sur UART2 exige une configuration vérifiée et
persistante ; elle n'est pas présumée active. Les messages GNSS binaires
DroneCAN ne sont pas des phrases NMEA. Serial Forwarding est un tunnel
d'octets distinct, exploitable si le nœud et le port interne le supportent ;
son accès par GUI/u-center ne prouve ni un proxy PX4 disponible ni une
passerelle nominale vers l'Airy. Un tunnel permanent ou une reconstruction
RMC demanderait un adaptateur explicite, des diagnostics et une qualification
de l'association au PPS physique. Ces alternatives restent **À valider**
selon [DOC-ELEC §8.1](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#81-référence-gnss-commune-étudiée).
Dans la voie directe candidate, CA01 adapte et répartit PPS/GPRMC vers l’Airy et une référence de
temps vers le Jetson. PX4 émet un déclenchement caméra par une sortie AUX
réservée à la demande de la Jetson ; CA01 adapte ce signal à l’entrée
optocouplée Basler. Le retour
ExposureActive est routé en cible vers FMU_CAP1 (AD&IO, broche 2 du Pixhawk
6X). La capture effective par `camera_capture`, sa configuration `Camera_Capture`
et les groupes de timers des sorties AUX sont **À valider** sur le firmware
retenu et au banc. FMU_CAP1 reste réservé au retour d’exposition et ne peut
pas recevoir simultanément le PPS. Airy Ethernet et Basler USB3 restent des voies
de données ; le lien interne TELEM2 Pixhawk–Jetson transporte les événements
PX4. SYNC_OUT1 de l’Airy n’est pas la source du déclenchement dans cette cible.
Ports, firmwares, caractéristiques électriques et mécanisme réel de capture
restent **À valider** dans [DOC-ELEC §8](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#8-synchronisation-et-repères-temporels).

Le contrat de `sensor_manager` et de l’enregistreur distingue pour chaque
mesure l’horodatage du capteur, l’heure UTC reconstruite, le temps monotone de
l’hôte à la réception, et l’événement matériel associé lorsque disponible.
Chaque conversion explicite son époque, sa source de temps, l’état de
verrouillage, l’offset et l’incertitude mesurés ; elle conserve l’original sans
remplacer silencieusement un temps absent par l’heure de réception. La relation
entre PPS/GPRMC, horloge du Jetson et horloge PX4 est calibrée et surveillée :
les messages reçus par TELEM2 seuls ne garantissent pas un horodatage physique
commun. Les identifiants de déclenchement, exposition et image, les numéros de
scan, ainsi que les pertes de paquets et de fronts sont enregistrés. Une fois la
capture FMU_CAP1 qualifiée, le front ExposureActive horodaté prime sur la
date de la commande AUX pour l’association de la frame Basler ; l’association doit rester vérifiable même
lorsque des images sont manquées ou réordonnées.

Pour chaque image, l'association utilise le temps d'exposition corrigé de
la latence mesurée du retour, puis le milieu d'exposition selon la convention
retenue. La pose provient d'un historique horodaté GNSS/IMU/PX4 et d'une
interpolation dont les limites sont explicites ; les points LiDAR gardent
leurs temps propres pour la compensation du mouvement. Ni une lecture de
la dernière position reçue ni un appariement par ordre d'arrivée ne suffisent.
La fenêtre, l'incertitude et les références d'échantillons sont conservées
dans le résultat. Les filtres ROS 2 peuvent rapprocher des messages déjà
datés ; ils ne synchronisent pas les horloges ni les expositions physiques.
Voir [message_filters ROS 2](https://github.com/ros2/message_filters/blob/rolling/doc/index.rst).

À la perte du verrouillage, d’un PPS, d’un retour ExposureActive, d’un flux
capteur ou après redémarrage d’un équipement, `sensor_manager` signale la
donnée comme temporellement invalide ou dégradée, suspend l’association
intercapteurs incertaine et conserve le diagnostic brut. La reprise exige une
nouvelle preuve de verrouillage et d’offset/incertitude dans les limites
approuvées avant de réactiver la fusion. Les seuils chiffrés, la latence
d’exposition, la datation par point Airy et le comportement sous chaque défaut
sont **À valider** par `MAP-FUN-001` et `T-AIRY-SYNC-01` de
[DOC-VAL §12.8](../VALIDATION_QUALIFICATION.md).

#### 7.1.2 Diagnostic BMS de cassette — Planifié / À valider, 5 octobre 2026

La conception électrique représente JBD-SP22S003 A01 via TE, UART isolé
Waveshare15817 et USB Jetson. Le décodeur et son intégration restent
**Planifiés** : aucune nouvelle logique embarquée n'est implémentée par
la modification CAO. Contrat déclaratif :
[UART BMS](../../hardware/electronique/cartographe/contrat_uart_bms.json).

Un futur adaptateur C++17 devra vérifier longueur, checksum JBD, unités,
courant signé, nombre de cellules, délais et fraîcheur. Les lectures03/04/05
préparent tension, SOC, capacité, cycles, cellules, NTC, protections et MOS ;
commandes d'écriture et modification des seuils interdites dans le diagnostic.
PM08 conserve la mesure batterie utilisée par PX4. Identifier et arbitrer
les producteurs avant publication, sans compter deux batteries pour un
seul pack. Aucun protocole DroneCAN n'est supposé et aucun moteur commandé.
Jeux de trames, corruption, perte de port, retard et identité seront testés
hors ligne puis au banc avant intégration PX4. DOC-ELEC§6.2, DOC-VAL§12.1.9.

### 7.2 Allocation algorithmique

| Étape | Baseline/candidat | Statut et test attendu |
|---|---|---|
| odométrie cartographe | FAST-LIO2 derrière `lio_adapter` | baseline PC ; Jetson et multi-scènes **À valider** |
| trajectoire globale | graphe LiDAR–IMU–GNSS avec boucles, LIO-SAM/GTSAM candidat | ATE, boucles et covariance **À valider** |
| fusion LiDAR–caméra | projection calibrée, visibilité et association temporelle | tests synthétiques implémentés ; matériel **À valider** |
| terrain | normales, voisinage local, grille 2,5D/maillage robuste | oracle terrain et ruptures **À valider** |
| poteaux/murs/talus | classes visuelles et primitives 3D robustes | précision, rappel et erreur 3D **À valider** |
| fils | fusion vision, géométrie et relation aux poteaux | non-détection prioritaire ; aucun capteur seul |
| rangs/pieds | végétation, axes locaux et graphe spatial | baseline géométrique partielle implémentée |
| carte de navigation | occupation 3D/ESDF, `nvblox` ou équivalent candidat | mémoire, latence et marges **À valider** |
| mission nominale | graphe, splines 3D et corridor conservatif | simulation et revue opérateur **À valider** |
| recalage carte/réel | initialisation RTK puis NDT/GICP/ICP robuste | multi-scènes et pertes GNSS **À valider** |
| plan local | suivi de spline, évitement borné, MPC/optimisation à comparer | ≥20 Hz et scénarios d'obstacles **À valider** |
| ciblage/dose | anticipation des latences, feedforward et PID | banc sec puis eau/traceur **À valider** |

Les baselines restent simples et explicables. Une solution plus complexe n'est
introduite que si une mesure démontre l'insuffisance de la baseline.

### 7.3 Classes temporelles et IA

1. **Vol critique** : PX4 et ses capteurs, hors ROS 2.
2. **Temps réel compagnon borné** : localisation, obstacles, corridor,
   trajectoire et sûreté avec files bornées et watchdog.
3. **Temps réel souple** : sémantique, visualisation et journalisation ; une
   perte ne commande jamais directement le drone.
4. **Hors ligne** : optimisation globale, entraînement, reconstruction dense,
   carte finale et rapports.

Un modèle neuronal produit une observation et une confiance, jamais une commande
directe de moteur. Son cycle est : annotation, entraînement station, validation
séparée, export ONNX, optimisation TensorRT pour une cible JetPack/Jetson,
benchmark embarqué et paquet versionné avec classes, prétraitement, seuils et
empreinte.

### 7.4 Machines à états cibles

```text
Cartographe : BOOT -> SELF_TEST -> READY -> TAKEOFF -> MAPPING
                                                   -> PAUSE/RETURN/ABORT -> LAND

Traitement : BOOT -> SELF_TEST -> READY -> TAKEOFF -> TRANSIT -> APPROACH
          -> DEPLOY_ARM -> TREATMENT -> RETRACT_ARM -> NEXT_ROW/RETURN
          -> PAUSE/ABORT selon les gardes
```

Le produit n'est autorisé que dans `TREATMENT`. Les transitions exactes et leur
répartition PX4/ROS 2 restent **À valider**.

## 8. Interfaces PX4 et ROS 2

PX4 produit l'état de vol et applique les consignes autorisées. Le compagnon
porte perception, planification et mission applicative. Les échanges cibles
comprennent :

- états PX4, mode, armement et failsafes ;
- odométrie/localisation avec covariance et fraîcheur ;
- trajectoire ou consigne de haut niveau avec durée de validité ;
- états des capteurs, du bras, de la pompe et des vannes ;
- diagnostics et événements horodatés.

uXRCE-DDS est l'interface retenue pour le lot expérimental. Le banc emploie le
domaine ROS `42` et l'Agent Micro XRCE-DDS sur UDP 8888. `px4_msgs` doit
rester compatible avec la version du firmware. Le pont convertit explicitement
NED/FRD vers ENU/FLU sans altérer les données natives PX4. Port embarqué, débit,
QoS, fréquences et définitions finales `.msg/.srv/.action` sont **À valider**
sur le matériel exact.

### 8.1 Interfaces logiques préliminaires

| Interface | Producteur | Consommateurs | Cadence de travail |
|---|---|---|---:|
| points LiDAR / IMU / GNSS / images | adaptateurs capteurs | localisation, perception, enregistreur | capteur, **À valider** |
| `/localization/odom` et état | localisation | navigation, sûreté, pont PX4 | 20–100 Hz **À valider** |
| carte sémantique et terrain local | cartographie | planification, station | selon produit / ≥10 Hz local **À valider** |
| obstacles | perception | planificateur, sûreté | ≥10 Hz **À valider** |
| trajectoire | planificateur local | contrôleur/PX4 | ≥20 Hz **À valider** |
| états bras/pulvérisation | contrôleurs dédiés | mission, sûreté, station | cadence actionneur **À valider** |
| événements et diagnostics | tous composants | superviseur, enregistreur, station | événementiel + heartbeat |

Les flux continus utilisent des topics, les opérations longues et annulables des
actions, et les opérations atomiques des services. Toute commande d'actionneur
porte mission, origine, horodatage et durée de validité.

### 8.2 Repères

```text
earth -> map -> odom -> base_link
                          +-- fcu_link
                          +-- imu_link
                          +-- lidar_link
                          +-- camera_front_link
                          +-- gnss_link
                          +-- arm_base_link -> arm_tool_link -> buses
```

`map -> odom` porte la correction globale et ne doit pas créer un saut de
consigne dangereux ; `odom -> base_link` reste continu. Les extrinsèques sont
versionnées par configuration matérielle.

## 9. Configuration, observabilité et résultats

- Les configurations partagées résident dans `configs/` et utilisent unités SI
  et noms explicites.
- Un lancement archive commit, image, paramètres, calibrations, modèles et
  empreintes utiles.
- Un composant critique publie état, fraîcheur, fréquence, latence, identifiant
  de configuration et code défaut.
- Les résultats volumineux et rosbags restent hors Git ; leurs manifestes et
  empreintes assurent la traçabilité.
- Les secrets et clés ne sont jamais stockés dans le dépôt.

Le pont local de télémétrie expose `/api/health`, `/api/snapshot`, `/api/reset`
et `/api/replay` sur `127.0.0.1:8092`. Qt interroge au plus quatre fois par seconde
avec une seule requête active ; réponses obsolètes, invalides ou surdimensionnées
sont rejetées. Le contrat `drone_agricole.telemetry_snapshot.v1` borne
trajectoires, nuage, métriques, état PX4 et horodatage. Le rejeu est en lecture
seule et n'accepte que des chemins relatifs résolus sous `results/`, sans
traversée ni lien symbolique sortant. Ce pont n'arme ni ne lance aucune mission ;
`/api/reset` vide uniquement les buffers d'affichage et ne modifie ni PX4, ni les
résultats archivés.

La carte LiDAR directe est remise à zéro pour chaque exécution. Elle compacte
adaptativement l'ensemble des voxels au lieu d'abandonner la fin du trajet, puis
publie taille de voxel et nombre de compactions. Les repères initiaux de 8 cm,
250 000 voxels mémorisés et 16 000 points affichés restent **À valider**.

Chaque composant critique publie au minimum `STARTING`, `OK`, `DEGRADED`,
`ERROR` ou `STALE`, l'instant de sa dernière donnée valide, sa fréquence, sa
latence, l'identifiant de configuration et un code défaut borné. Le superviseur
évalue localisation, état PX4, fraîcheur de trajectoire, corridor, carte, bras,
actionneurs et géofence avant d'autoriser une action.

## 10. Stratégie de test

Les campagnes, mesures et statuts de qualification transversaux sont tenus dans
[DOC-VAL](../VALIDATION_QUALIFICATION.md). La présente section définit comment
les modules logiciels doivent être testés.

### 10.1 Niveaux

| Niveau | But | Exemples |
|---|---|---|
| unitaire | règle ou algorithme déterministe | projection, rangs, reconstruction, cycle de tâche |
| contrat | schémas, compatibilité et erreurs | catalogue, runners, résultats historiques |
| intégration | assemblage des modules | cartographie dashboard, télémétrie, processus |
| interface | navigation et rendu hors écran | pages Qt, fumée de l'exécutable |
| simulation | comportement ROS 2/PX4 et défauts | Offboard, perte liaison, délais, surcharge |
| embarqué | temps réel, ressources et thermique | rejeu 1× sur Jetson, capteurs réels |
| système | mission et retour à l'état sûr | simulation, banc sec, eau/traceur, vol progressif |

### 10.2 Règles

- Un module nouveau déclare ses entrées, sorties, erreurs, dépendances et tests.
- Les tests UI vérifient l'orchestration et la présentation, pas les calculs
  métier déjà testés en headless.
- Les campagnes sont reproductibles et liées à une configuration précise.
- Les tests d'architecture vérifient les dépendances de compilation interdites.
- Une réussite de processus et une finalisation correcte du résultat sont deux
  états distincts.
- La qualification `amd64` ne vaut pas qualification `arm64`.

### 10.3 Traçabilité active

| Exigence | Composant/algorithme | Test | Résultat |
|---|---|---|---|
| `SW-ARC-001` séparer UI et orchestration | application, process, presentation | `test_run_service`, `test_process_backend`, `test_station_navigation` | implémenté sous Windows |
| `SW-EXT-001` ajouter une capacité par contrat | catalog, runners, composition | `test_contract_registry`, `test_runner_registry` | implémenté |
| `SW-MAP-001` projeter la couleur sans masquer les erreurs | camera color fusion | `test_camera_color_fusion` | implémenté préliminaire |
| `SW-MAP-002` reconstruire avec diagnostics bornés | scan reconstruction, adaptateur FriûlBot, rejeu | `test_scan_reconstruction`, `test_vineyard_map`, `test_dashboard_mapping:surface` | 23 scans / 61 903 triangles sur une fenêtre réelle ; préliminaire, voir DOC-VAL |
| `SW-SAFE-001` ne pas usurper l'autorité PX4 | pont PX4/ROS 2 sur porteuse commune | scénarios SITL perte Offboard/compagnon, puis banc perte/redémarrage Orin NX et défaut d'alimentation selon DOC-ELEC | SITL partiel ; cible matérielle **À valider** |
| `SW-TIM-001` coordonner les captures Jetson et conserver une datation intercapteurs traçable | `mission_manager`, `sensor_manager`, adaptateur PX4, enregistreur, PX4, Airy et Basler | `T-AIRY-SYNC-01` et `T-CA01-09` : autorité unique, demande/commande/exposition/image, offsets/incertitudes, pertes et reprise sur banc | **Planifié / À valider** ; aucun essai sur capteurs cible |
| `SW-RTK-001` acheminer les corrections sans saturer la commande ou la télémétrie | QGroundControl, TX Backpack, ELRS, RP4TD, PX4, H-RTK F9P Base/Rover | `T-RF-06` tri-flux et pertes ciblées, DOC-VAL §9.1 | sélection matérielle retenue ; débit et continuité **À valider** |
| `SW-PORT-001` construire et exécuter sur ARM | conteneurs et runtime Orin NX 16 Go | CI `arm64`, rejeu 1×, ressources et thermique sur porteuse cible | **À valider** |

### 10.4 Portefeuille de données de validation

| Dataset | Usage | État |
|---|---|---|
| BotanicGarden `1006-03` | pipeline LIO et compatibilité historique | téléchargé, inspecté ; licence commerciale **À valider** |
| Newer College | référence LIO/SLAM extérieure | accès et licence non commerciale à traiter |
| ARD-VO | vignoble avec LiDAR/IMU/RTK | séquence et licence **À valider** |
| BACCHUS Long-Term | évolution saisonnière | accès et licence **À valider** |
| TEMPO-VINE | futur benchmark viticole Mid-360 | publication des données en attente |
| LaMole/Grospoli | pentes, terrasses, murs et rangs irréguliers | autorisation requise |
| EscaYard B7 | rangs et évaluation RTK sur produits géospatiaux | baseline intégrée ; historique pour les nouveaux parcours |
| FriûlBot Test 2 | fusion temporelle LiDAR–multispectral en vigne | baseline active de perception/cartographie |
| VineLiDAR | géométrie UAV LiDAR multi-date | public, non téléchargé |

M2DGR et Hilti restent différés jusqu'à stabilisation du banc. Les futurs
imports géospatiaux pourront s'appuyer sur GDAL, PROJ et PDAL derrière un
adaptateur explicite. Aucun flux, timestamp, repère ou pose manquant ne doit être
fabriqué pour rendre un dataset compatible. Les droits LaMole/Grospoli, les
rangs courbes, les corridors et les critères SITL restent **À valider**.

Le catalogue machine-lisible `datasets/manifests/catalogue_datasets.yaml` porte
URLs, licences, empreintes, sous-ensembles et politiques d'isolation. Il prévaut
sur ce résumé. Un dataset n'est `ready` que si source, droits, taille,
empreinte, capteurs, calibration, vérité terrain et préparation reproductible
sont connus.

## 11. Extension d'une capacité

Avant toute évolution, appliquer les [préceptes et le cadrage courant](HLD.md#methodologie) :
besoin observé, distinction réelle portée par la capacité, action minimale,
réversibilité, coût, arrêt et signal. La priorité est la faisabilité physique
du cartographe ; un développement de station doit justifier son utilité pour
la contrainte retenue. Les écarts logiciels sont dans
[DOC-VAL AUD-010 à AUD-016](../VALIDATION_QUALIFICATION.md#aud-010).
Le contrat `IStationModule` sans consommateur actuel trouvé et le test de
booléens de `StationArchitecture` ne constituent pas une preuve de sûreté
([AUD-013](../VALIDATION_QUALIFICATION.md#aud-013)).

Une évolution justifiée suit ensuite ce chemin :

1. compléter le besoin et le scénario dans `DOC-HLD` si le comportement système
   change ;
2. mettre à jour le module, ses contrats et ses tests dans ce document ;
3. intégrer les choix structurants, alternatives utiles et conséquences dans le
   document vivant concerné ;
4. implémenter domaine/service/adaptateur puis présentation ;
5. lier l'exigence au test et au résultat ;
6. actualiser l'état `planifié`, `implémenté` ou `qualifié` ici, sans créer un
   compte rendu séparé.

Une extension n'introduit pas de plugin dynamique, bus global ou service réseau
supplémentaire sans besoin démontré. Une exécution réussie et la finalisation
correcte de son archive restent deux états distincts.

## 12. Feuille de route capacitaire

Ce tableau décrit le portefeuille cible, pas un engagement de réalisation ni
une priorité concurrente à [DOC-VAL §14](../VALIDATION_QUALIFICATION.md#recentrage).
B1 peut fournir le minimum nécessaire au banc cartographe ; ses autres
fonctions, B2–E1 et toute infrastructure nouvelle attendent un besoin observé
et une décision bornée. Les garanties de provenance des nouvelles exécutions
restent partielles : voir [AUD-014](../VALIDATION_QUALIFICATION.md#aud-014).

| Lot | Résultat attendu | État |
|---|---|---|
| T0 | contrats génériques, runners, historique, comparaison et rapports | implémenté préliminaire |
| B1 | `SurveyMissionPackage`, `SurveyRunPackage`, synchronisation et qualité d'acquisition | Planifié ; périmètre minimal à justifier pour le banc cartographe |
| B2 | trajectoire globale, nuage maître et fusion LiDAR–caméra | briques locales préliminaires |
| B3 | terrain, sémantique, entités, graphe et confiance | planifié |
| B4 | carte approuvée, mission, planification et simulation | planifié |
| C1 | chargement carte, LIO et recalage du drone de traitement | planifié |
| C2 | terrain local, obstacles, ESDF, corridor et plan local | planifié |
| C3 | mission autonome, transitions, reprise et défauts | planifié |
| D1 | bras sans liquide, déploiement et blocage | planifié |
| D2 | ciblage, eau/traceur, débit, dose et compte rendu | planifié |
| D3 | protocole agronomique autorisé et compensation air/downwash | planifié |
| E1 | campagnes système et qualification | planifié |

Chaque lot franchit une porte mesurable : acquisition intègre, géométrie
reproductible, sémantique qualifiée, carte cohérente, mission sans collision,
temps réel Jetson, puis traitement sûr. Les critères détaillés et résultats de
campagne relèvent de [DOC-VAL](../VALIDATION_QUALIFICATION.md).

## 13. Références et historique consolidés

- Les principes d'évolutivité et de navigation sont définis aux sections 2, 4
  et 11 ; la chaîne cartographique et la scène 3D le sont à la section 6.
- Les résultats et limites des anciennes campagnes sont consolidés dans
  [DOC-VAL](../VALIDATION_QUALIFICATION.md).
- La configuration de compilation effective dans `software/cpp/CMakeLists.txt`
  prévaut sur les anciennes arborescences décrites dans les documents gelés.

<a id="porte-v21"></a>
### Porte d’exploration électromécanique V2.1

**Implémenté pour la planification de H-01.** Le gestionnaire de convergence
publie un préflight séparé de la réception. Dans GO3B, l’autorisation
documentaire était nécessaire avant de construire le candidat qui devait
produire certaines des preuves d’admission. Un plan réversible sur copie
peut être admis pour comparer des corridors, étudier une implantation hors
tension ou tester la sensibilité à un rayon candidat. Une violation connue
ferme l’essai concerné. Les recherches et études indépendantes sont mises
en file avec un coût estimé et une reprise liée au gel.

Le parcours conserve les critères impératifs et l’indépendance de L4.
La réception de H-01 reste **À valider**, avec une copie intégrée et une
correspondance approuvée entre les critères GO3A et les mesures exigées.
[Contrat, états et entrées](../electromechanical_v2_1/01_EXPLORATION_POLICY.md)
· [Contrôles](../VALIDATION_QUALIFICATION.md#preuve-porte-v21).

La livraison isolée de la [requalification C](../VALIDATION_QUALIFICATION.md#requalification-v21-c)
ajoute l’action `RELOCATE_EQUIPMENT` au parcours `convergence_core integrate`.
L3 sélectionne une translation latérale sur le banc synthétique lié. Le
constructeur FreeCAD déplace la pose du composant, ses repères et ses volumes
de service et régénère le cordon. La réouverture L2 vérifie les contacts et
les volumes contre les obstacles liés. L4 remesure le candidat sous les
critères gelés, avec la seule position d’ancrage autorisée adaptée à la
pose. La réception du banc reste conditionnelle et le contrôle de H-01
rend `FINAL_NO_GO`.

## Journal de modifications

- **27 novembre 2026** — Réception documentaire V3-A.7 par porteur et réemploi du validateur A.4 (§2.6).
- **27 novembre 2026** — Clôture V3-INT.3 sur bancs synthétiques Windows amd64 après rejeu des frontières et contrats sur le merge de revue (§2.6).
- **27 novembre 2026** — V3-INT.3 réunit les interfaces C.3 et A.6 avec séparation vérifiée des portées et rejeu des protections (§2.6).
- **26 novembre 2026** — V3-C.3 qualifie la recherche volumique bornée sur deux bancs après criblage des arcs et correction du retour tangent (§2.6).

- **26 novembre 2026** — V3-A.6 relie la revue signée à une construction privée sur banc avec réservation persistante, contre-validation et reçu audité (§2.6).
- **26 novembre 2026** — V3-INT.2.1 prépare les entrées scellées des suites L1/L2 dans des racines de test temporaires (§2.6).
- **25 novembre 2026** — V3-INT.2 réunit le solveur C.2 et la préadmission A.5 dans le même build (§2.6).

- **25 novembre 2026** — V3-C.2 ajoute les plans multi-faisceaux atomiques, la sélection d’appui et la classification indépendante des contacts sur banc (§2.6).
- **25 novembre 2026** — A.5 introduit la revue et le registre signés, avec préadmission bornée vérifiée en `TEST_ONLY` (§2.6).
- **25 novembre 2026** — V3-INT.1 réunit l'orchestration C.1 et l'import A.4 dans le même build, avec leurs gardes d'admission et régressions (§2.6).
- **24 novembre 2026** — V3-C.1 ajoute le mode à repères natifs, un support dépendant de la pose et un classement issu des mesures B.2 (§2.6).
- **24 novembre 2026** — Ajout de l'import de relevés V3-A.4 en lecture seule et de la vérification de leur provenance.

- **19 novembre 2026** — Ajout du problème L3, de l’admission paramétrique par domaine et du rejeu L5 avec contre-validation (§2.6).
- **19 novembre 2026** — V3 B.2 vérifie l’agrégat natif, compare les mesures après une réouverture indépendante et versionne le reçu candidat (§2.6).
- **18 novembre 2026** — Contrat, import et analyse d’impact du graphe V3-A, avec reprise ciblée des gardes V2.1 (§2.6).
- **19 novembre 2026** — Constructeur XLink B.1 et validation indépendante raccordés à L5 sur profils de banc scellés (§2.6).
- **18 novembre 2026** — Admission V3-A.1 intégrée au point de construction L5 sur banc XLink scellé (§2.6).

| Date | Modification |
|---|---|
| 17 novembre 2026 | Réimplantation latérale sur banc XLink dans la livraison isolée de la mission C. [Validation](../VALIDATION_QUALIFICATION.md#requalification-v21-c). |
| 15 novembre 2026 | Jointure d’occurrences XLink, fermeture isolée et validation par lots reprenables (§2.4). |
| 14 novembre 2026 | GO2bis, contrôles de longueur et de polarité L2, provenance de port et de cordon L4, intégrité du gel et publication reprise L5. [Validations et limites](../VALIDATION_QUALIFICATION.md#qualification-moteur-go2bis). |
| 15 novembre 2026 | Préflight V2.1 pour le dossier H-01 et séparation de sa réception. [Contrat](#porte-v21). |
| 13 novembre 2026 | Convergence L5, reprise par checkpoint, fusion bornée et admission d’un natif par L4 (§2.5). |
| 13 novembre 2026 | Validateur indépendant L4, réouverture FreeCAD, projections L0, preuves T0 et interface prévue pour L5 (§2.4). |
| 13 novembre 2026 | Exploration L3 sur bancs, réemploi L1/L2, consolidation, Pareto et preuve T0 (§2.3). |
| 12 novembre 2026 | Catalogue, continuité, géométrie et rapprochement L2 en C++17 (§2.2). |
| 12 novembre 2026 | Moteur de recherche technique L1 C++17, API Python et rapport compatible L0 (§2.1). |
| 10 novembre 2026 | Périmètre de l’outil Python FreeCAD demandé pour le banc électromécanique de l’action 1 (§2). |
| 26 octobre 2026 | Calcul massique C++17 étendu aux recettes OEM par occurrence et contrôles de propriétaire (§5.3). |
| 26 octobre 2026 | Reprise massique : recettes documentaires par composant, contributions partielles, clôture calculée sous condition de contenu exhaustif, inclusions indépendantes de l'ordre et problème explicite dans chaque ligne incomplète ; tests négatifs et publication reproductible (§5.3). |
| 25 octobre 2026 | ORCH-CAO-MASSE-1 : calcul et couverture C++17 liés à la BOM, inclusions et distributions séparées, détection d'exports obsolètes dans la passerelle existante ; nouvelles capacités et campagnes suspendues (§5.3). |
| 24 octobre 2026 | Passerelle CAO → Gazebo intégrée à Simulations : service UI/CLI commun, export isolé et contrôlé, aperçu navigable, annulation et tests ; chargement Gazebo réel, physique À valider (DOC-VAL §10.2). |
| 24 octobre 2026 | ORCH-GZ-1 : banc Docker/ROS reconstruit, airframe 40000 et capteurs synthétiques corrigés ; six essais SITL courants carré/perte Offboard/annulation finalisés, T0 et revue indépendante ; batterie forfaitaire observée, fidélité physique et autonomie couplée À valider (DOC-VAL §9.3). |
| 23 octobre 2026 | ORCH-GZ-1 : modules/outils de simulation C++17 autonomes, validation T0 effective dédiée et bornes/finalisation Offboard ; tests natifs exécutés, intégration ROS/Gazebo restante (§5.1). |
| 23 octobre 2026 | Transposition MagicPath V3 en Qt Widgets, six espaces, deux thèmes persistants ; brouillons/favoris/BOM via services communs UI/CLI, distinction des capacités futures et traçabilité §4.6. |
| 10 octobre 2026 | Configuration minimale du portable acceptée pour la définition ; cible et déploiement matériel restent À valider, aucune modification du logiciel (§3). |
| 10 octobre 2026 | Déploiement sol : portable de récupération envisagé pour QGC/RTK/revue légère/transfert, PC fixe existant pour traitement ; minimum candidat DOC-ELEC, cible Windows 11 x64 proposée et fenêtre 1200 × 760 constatée, déploiement matériel À valider (§3). |
| 10 octobre 2026 | Prototype : conservation de toutes les données brutes LiDAR/caméra pendant la mission demandée ; scénario 5 images/s sur 20 minutes et SSD Samsung MZ-V9S1T0BW 1 To retenus ; réalisation de logger_recorder et qualification ouvertes (§7.1). |
| 8 octobre 2026 | Préceptes et priorité physique reliés aux évolutions ; validation JSON Schema déclarative distinguée des contrôles effectifs, portefeuille et limites de preuve explicités. |
| 5 octobre 2026 | Contrat UART JBD via TE et interface isolée ; décodeur C++17 en lecture seule Planifié, identité/fraîcheur à tester et PM08 conservé comme source batterie PX4 (§7.1.2) |
| 30 septembre 2026 | Flux GNSS standard, NMEA direct et tunnel série distingués ; configuration GPRMC UART2 et alternatives de passerelle explicites, aucune disponibilité PX4 ni synchro PPS déduite du GUI |
| 30 septembre 2026 | Contrat de capture planifié : Jetson/ROS 2 décide, PX4 exécute ; session/demande et états distincts, autorité unique, absence de répétition aveugle, association aux flux continus et limites du transport à qualifier |
| 25 septembre 2026 | contrat temporel cartographe planifié : PPS/GPRMC GNSS vers Airy/Jetson, trigger AUX PX4 et retour ExposureActive candidat sur FMU_CAP1 à qualifier, correspondance UTC/monotone/événements avec incertitude et états invalides |
| 24 septembre 2026 | H-RTK F9P Base/Rover retenus ; chemin RTCM via QGroundControl et RF commune candidat, budget tri-flux et séparation Offboard local documentés, validation matérielle ouverte |
| 24 septembre 2026 | cible de déploiement Orin NX 16 Go et Pixhawk 6X module sur porteuse Holybro ; frontière PX4/ROS 2 maintenue, interface et défauts à valider sur matériel |
| 13 septembre 2026 | consolidation des décisions actives de déploiement, contrats, télémétrie, PX4, cartographie et extension ; retrait du registre ADR |
| 10 septembre 2026 | configuration VS Code pour ouvrir `software/cpp` directement ; configuration et compilation Debug vérifiées via les tâches locales |
| 10 septembre 2026 | consolidation des architectures, contrats, algorithmes, modules/tests, datasets et feuille de route historiques |
| 10 septembre 2026 | variante d'assemblage et surface : contrats, limites, contrôles ICP, export PLY et parcours de rejeu documentés après essai réel |
