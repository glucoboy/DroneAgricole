# Résolution autonome d'ingénierie

Lire lors d'une incertitude, d'un échec, d'une contrainte héritée ou d'une liaison mobile. Les classes de données/contraintes sont définies dans [integration-contract.md](integration-contract.md) et les verdicts dans [validation.md](validation.md).

## Boucle de résolution

**INVESTIGATE → DERIVE → DESIGN → SIMULATE → VERIFY → DECIDE** s'applique à chaque inconnue significative, avec profondeur proportionnée à son effet sur la décision. Une étape sans outil ou données suffisantes est explicitement non exécutée ; elle n'est jamais implicitement réussie.

1. **INVESTIGATE.** Rechercher dans le projet et ses dépendances : schémas, nomenclatures, configurations, notes fabricant déjà archivées, modèles et références de pièces. Inspecter occurrences CAO, repères, sections, joints, butées et contraintes effectives. Une cote lue dans une CAO est une mesure du modèle, pas du matériel. Rechercher ensuite, si l'accès existe, plans et notices fabricant de la référence/révision exacte et références applicables. Conserver page, version, conditions et accès infructueux ; une référence voisine n'est qu'une analogie. Résoudre les contradictions entre sources par applicabilité, pas en choisissant la valeur favorable.
2. **DERIVE.** Déduire ce qui est calculable des entrées sourcées : longueurs, courses, enveloppes, sections, résistance, pertes. Conserver formule/modèle, unités, domaine, tolérances, corrélations utiles et recette reproductible. Identifier les degrés de liberté réels, puis séparer inconnues factuelles et paramètres choisis. Une formule exacte appliquée à une hypothèse garde une conclusion conditionnelle.
3. **DESIGN.** Construire des hypothèses réfutables pour les paramètres non déterminés, avec bornes justifiées et observation qui les départage. Comparer baseline et candidats différents sur les paramètres responsables : déplacement de guide, longueur utile, corridor, séparation ou protection. Ne pas transformer automatiquement une station historique en `waypoint` obligatoire. Une contrainte d'origine inconnue s'investigue avant d'être assouplie ; les protections potentiellement critiques restent conservatrices.
4. **SIMULATE.** Exercer les candidats sur les situations discriminantes : positions, tolérances, profils électriques, paramètres de suspension, montage. Utiliser calcul analytique, balayage paramétrique, modèle numérique ou CAO selon les outils réellement disponibles. Enregistrer type de modèle, versions, entrées, budget, couverture et résultats ; une interpolation géométrique ne simule ni rigidité ni fatigue. Les calculs métier exécutables restent en C++17 dans DroneAgricole ; les adaptateurs CAO/infrastructure existants sont réemployés.
5. **VERIFY.** Appliquer A–D aux preuves fraîches, comparer aux seuils applicables, contrôler sensibilité et cas défavorables. Distinguer violation établie, absence de preuve et hypothèse réfutée. Une observation réfutant une hypothèse provoque sa révision et le recalcul des conclusions dépendantes, jamais l'assouplissement opportuniste du critère.
6. **DECIDE.** Écarter les violations impératives, puis choisir la meilleure solution admissible **dans le périmètre et parmi les candidats étudiés**, avec marges et critères quantitatifs comparables. Si aucune admissibilité complète n'est démontrée, retenir pour poursuite la meilleure conception conditionnelle et ses réserves ; un candidat avec violation prouvée reste NON_CONFORME, même archivé comme point de départ. Si les objectifs se contredisent, expliquer le compromis et sa sensibilité sans imposer à l'utilisateur un arbitrage géométrique courant.

## Alternatives, budget et blocage local

Définir avant exploration une baseline, les critères impératifs et objectifs, le budget de calcul/recherche/variantes et le signal de sortie. Pour une petite étude réversible, choisir soi-même un budget local raisonnable, sans inventer d'engagement financier. Les trois candidats internes du planificateur sont une limite de cette heuristique, pas une limite universelle à l'étude de conception.

Après un échec, conserver la cause observée et les métriques (intersection et objets, rayon effectif, déficit de longueur, accès ou donnée inconnue). Si la cause n'est qu'inférée, la nommer ainsi et préparer un contrôle discriminant. Changer les paramètres responsables et tester une autre stratégie ; éviter les variantes équivalentes et conserver le résultat de chacune, y compris les échecs. Revenir à la dernière variante utile si nécessaire.

Arrêter la branche quand un candidat suffit, que le budget est atteint ou que les variantes n'apportent plus d'information. Ne pas arrêter au premier échec ni parce qu'un paramètre peut être mesuré, calculé, recherché, déplacé ou exploré paramétriquement. Un blocage de connectivité, de documentation inaccessible ou d'outil suspend uniquement les opérations qui en dépendent. Terminer les autres liaisons, comparaisons, calculs et preuves. Une demande à l'utilisateur indique recherches faites, information indispensable, décision affectée et mesure/action minimale ; elle ne remplace pas le travail encore possible.

## Équipements suspendus ou mobiles

- Identifier corps fixes/mobiles, liaisons cinématiques, axes, degrés de liberté couplés, butées et jeux, y compris rotations et torsion. Rechercher raideur, précharge, charge, amortissement, compression admissible et conditions des suspensions. Ne pas déduire la course réelle du seul nom d'un élastomère ou de sa hauteur libre.
- Si la cinématique est définie, calculer les poses accessibles et l'enveloppe balayée des équipements, prises et faisceaux. Par exemple un point à rayon `r` d'un pivot parcourt une corde `2r sin(|Δθ|/2)` entre deux poses ; cette distance n'est pas la longueur de cordon requise. Pour un modèle linéaire approprié, `Δx = ΔF/k` exige raideur effective, unités et domaine de validité, et reste distinct de la course limitée par butées.
- Distinguer déplacement statique sous charge, vibration autour de l'équilibre et mouvement répétitif avec cycles. Ne pas assimiler l'enveloppe cinématique accessible à l'amplitude de vibration en service. Si l'amplitude réelle manque, explorer des bornes issues de butées, jeux, données fabricant ou modèles justifiés. Sans borne défendable, utiliser des scénarios exploratoires explicitement hypothétiques ; aucune garantie de couverture du mouvement réel.
- Définir tronçons fixes, retenues et zone flexible/service loop. Étudier la route aux positions extrêmes et intermédiaires pertinentes, y compris combinaisons de degrés de liberté. Une paire de poses extrêmes ne démontre pas le dégagement continu : chercher les extrema, contrôler les volumes balayés ou conserver cette couverture inconnue.
- Vérifier à chaque situation longueur utile, rayon statique/dynamique, tangentes aux sorties, torsion, dégagements, accrochage, abrasion et accès. Confronter les efforts aux limites de traction des prises/serrages si un modèle ou essai les fournit. Du mou ne démontre pas un effort nul ; une distance entre extrémités n'est qu'une borne inférieure de longueur.
- Adapter cordon, réserve, guides et points de retenue dans la copie. Un cordon plus long exige de recontrôler pertes électriques, limites de liaison, volume de réserve, masse, montage et comportement de boucle. Sans données dynamiques, forces ou endurance appropriées, conserver ces contrôles ouverts et **VALIDATION_PHYSIQUE_REQUISE**. Aucune qualification de fatigue par CAO seule.

## Groupes et protections : calculer avant d'autoriser

Retrouver pour chaque groupe fonctions, départs **et retours**, tension, courant continu/crête/profil, section, blindage/terminaisons, liaisons sensibles et indépendance fonctionnelle. Rechercher les valeurs manquantes avant de classer la cohabitation ; l'absence d'information ne vaut ni zéro courant ni compatibilité.

Quand les données le permettent, calculer `Rboucle = Σ(ρ(T) L/S) + ΣRcontacts`, `ΔV = I Rboucle` et `P = Irms² Rboucle` selon le profil applicable ; contrôler unités, température et longueurs aller/retour sans double comptage. Une chute admissible exige un critère sourcé. Les pertes Joule ne donnent pas seules la température : utiliser déclassements fabricant ou modèle thermique justifié (ambiance, échanges, gaine, voisinage, simultanéité), sinon chiffrer les pertes et maintenir l'échauffement non vérifié. Ne pas transformer un courant impulsionnel en courant continu sans modèle.

Examiner CEM (fronts, retours, blindages, couplages, impédances), séparation fonctionnelle, échauffement cumulé et montage du groupe entier. Les règles empiriques de distance ou de remplissage ne garantissent pas la compatibilité. En incertitude CEM/thermique significative, retenir une architecture conservatrice (corridors distincts, séparation, protection adaptée) et poursuivre les contrôles démontrables ; la prudence n'autorise pas à écrire `allow` sans justification.

Comparer gaines/protections avec le dimensionnement existant : diamètre intérieur utile et packing, passage des prises, paroi, abrasion, rayon, température, masse, démontage et disponibilité de références applicables. Documenter les compromis (par exemple gaine fermée contre fendue) ; aucune matière ou protection universelle. Le planificateur ne calcule ni température, ni effort, ni CEM : ces preuves restent dans le dossier complet relié à sa projection.

## Journal structuré de conception

Ajouter une collection `design_decisions` au dossier/preuve d'expérience existant. Pour chaque décision significative, conserver :

| Champ | Contenu |
|---|---|
| `id`, `problem`, `scope` | problème utile, liaisons/objets/exigences et périmètre |
| `data_refs`, `constraint_refs`, `hypothesis_refs` | sources/version/empreintes et classes du dossier, hypothèses et conditions de réfutation |
| `variants` | IDs, différences avec baseline, paramètres modifiés, raisons des rejets et résultats conservés |
| `calculations`, `simulations` | modèles/formules, entrées référencées, commandes/outils/versions, unités, couverture et limites |
| `results`, `decision`, `selected_candidate_id` | métriques/marges comparables, choix et justification, périmètre d'admissibilité ou réserves |
| `confidence` | faible/moyenne/élevée avec justification ; aucun pourcentage inventé ni assimilation à la classe d'une donnée |
| `statuses`, `remaining_checks` | verdict par domaine, validations restantes, critère/mesure qui peut changer le choix |
| `budget`, `stop_reason` | effort borné, arrêt et prochaine décision |

Référencer les données canoniques plutôt que recopier leurs valeurs critiques. Conserver les variantes techniques dans l'espace isolé avec manifestes/empreintes ; pas de nouveaux natifs datés dans les sources projet. Dans DroneAgricole, le journal est une preuve structurée, **pas un nouveau document narratif ni un ADR** : décision et apprentissage réutilisables dans DOC-MEC/DOC-ELEC, résultats dans DOC-VAL, vue Markdown dérivée dans la section vivante concernée. Les maturités du projet restent celles de `docs/INDEX.md`.
