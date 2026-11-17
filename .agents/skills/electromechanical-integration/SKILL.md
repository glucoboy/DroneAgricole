---
name: electromechanical-integration
description: Concevoir, investiguer, dimensionner, regrouper et vérifier les faisceaux électriques dans FreeCAD avec Cables Workbench, y compris les liaisons mobiles et incertitudes techniques. Utiliser pour leur intégration électromécanique ; pas pour un schéma électrique seul ni une illustration.
---

# Intégration électromécanique des faisceaux

Produire une architecture de faisceaux montable, traçable et vérifiable avant de produire ses solides. **Un regroupement physique ne fusionne jamais les conducteurs et ne change jamais la connectivité électrique.** Une courbe agréable, un solide valide ou un calcul réussi ne démontrent pas une conformité physique.

## Cadrer et préserver

Inspecter Git, les instructions du dépôt, les sources de connectivité et le constructeur existant. Appliquer la méthode du projet sans la recopier. Définir périmètre, baseline, hypothèses réfutables, contraintes impératives, budget de recherche et critère d'arrêt. Dans DroneAgricole, cette capacité soutient la complétude CAO/massique ; elle ne reprend ni les campagnes suspendues ni les essais réels.

Toute reconstruction se fait dans une **copie isolée avec dépendances**. Lire [exécution](references/execution.md) : copie native XLink, empreintes, paramètres, choix du backend et commandes reproductibles. Ne pas ouvrir une source pour la sauvegarder, ne pas modifier un constructeur sans autorisation, ne pas relancer une opération MCP dont l'issue est inconnue. Aucune publication dans l'assemblage original n'est implicite.

## Résoudre les incertitudes et décider

Assumer la responsabilité des choix techniques raisonnablement résolubles : **INVESTIGATE → DERIVE → DESIGN → SIMULATE → VERIFY → DECIDE**. Une inconnue déclenche une investigation, un calcul ou une étude paramétrique ; elle n'est pas un motif d'interruption immédiate. Lire [autonomie d'ingénierie](references/engineering-autonomy.md) dès qu'une donnée manque, qu'un choix historique bloque, qu'un candidat échoue ou qu'un équipement est mobile. Cette boucle spécialisée applique le cadrage du projet ; elle ne remplace pas ses préceptes.

Sur la copie isolée, choisir et tester sans arbitrage utilisateur les guides et retenues modifiables, corridors, tronçons et dérivations, longueurs de cordon candidates, gaines, supports/protections et paramètres de chemin. Comparer des architectures et revenir à une variante antérieure après échec. Préserver les contraintes fonctionnelles, électriques et de sécurité justifiées. Les modèles sources originaux, équipements réels et achats restent hors de cette autorisation ; les constructeurs sont réutilisés, les variantes passent par leurs paramètres/adaptateurs autorisés.

Classer les données **MESURÉE, DOCUMENTÉE, CALCULÉE, ESTIMÉE, HYPOTHÈSE, INCONNUE**, et les contraintes **IMPÉRATIVE, MODIFIABLE, HÉRITÉE, INCONNUE**, selon le [contrat d'intégration](references/integration-contract.md). Ne pas confondre un choix historique avec une exigence ni une estimation avec une spécification fournisseur.

Ne solliciter l'utilisateur que si une information indispensable demeure inaccessible et empêche une décision fiable sur le point concerné, ou si une action dépasse les autorisations. Avant cette demande, épuiser les voies proportionnées de recherche, mesure numérique, calcul et variantes ; présenter la décision précise empêchée et les éléments manquants. Continuer les tâches indépendantes et livrer une conception conditionnelle lorsque possible. Arrêter une exploration à son budget ou lorsqu'aucune nouvelle information discriminante n'est obtenue, sans qualifier une solution par défaut.

## Architecturer avant de router

1. Inventorier **toutes les liaisons du périmètre** avec identifiants stables et extrémités. Lire [données et compatibilité](references/integration-contract.md) ; chaque paramètre porte classe, valeur, unité, source et incertitude. Une propriété inconnue reste `null`, une valeur candidate reste candidate ; explorer des hypothèses séparées ne remplit pas artificiellement la donnée source.
2. Séparer explicitement : graphe électrique, groupes physiques, corridors géométriques, gaines/protections, dérivations, fixations et preuves. Relever repères, occurrences et poses globales. Les enveloppes de groupe sont distinctes des volumes individuels.
3. Rechercher des passages partagés, y compris pour des destinations différentes, puis des branches courtes aux connecteurs et des séparations accessibles. Évaluer la cohabitation selon courant, blindage, couplage CEM, thermique, séparation fonctionnelle et montage. Aucune interdiction universelle par catégorie ; une absence de données ne vaut pas autorisation.
4. Comparer une baseline et des topologies candidates bornées : contraintes impératives d'abord ; ensuite moins de faisceaux dispersés, passages/fixations mutualisés, encombrement/accrochage, accès/maintenance, longueurs/masse. Les objectifs sont configurables. Ne pas regrouper si le partage rend le montage ou la compatibilité moins maîtrisables.
5. Pour automatiser les corridors déjà relevés, lire le [contrat du planificateur C++17](references/planner-contract.md). Il inventorie les liaisons, propose des tronçons et vérifie la conservation des connexions. Il ne découvre pas les espaces libres de la CAO et ne route pas automatiquement les solides. Ses propositions restent préliminaires jusqu'aux contrôles ci-dessous.

## Réaliser la géométrie

Pour le moteur de banc, suivre la [recette exécutable](../../../electromechanical_engine/README.md). Utiliser `extract` pour inventorier une copie avec ses XLinks, `build` pour générer une variante dans un dossier neuf et la [skill de validation](../electromechanical-validator/SKILL.md) pour relire le natif et statuer. L’extraction et la construction sur modèle de boîtes ont des périmètres distincts. L’import des ports et des contraintes d’un assemblage demande un mapping explicite.

Lire [API FreeCAD inspectées](references/freecad-api.md) avant d'appeler une API native. Revalider versions, signatures et propriétés installées. Réutiliser les constructeurs du projet ; dans DroneAgricole, `cable_workbench_prototype.py` reste inchangé. Sur un autre assemblage, fournir un adaptateur vers ses objets et ses repères, sans dépendance à des noms de pièces du drone.

Choisir lignes/arcs, `BSpline_P`, `BSpline_K` ou méthode hybride selon les contraintes. `WireFlex` n'a pas de propriété `MinimumRadius` ; `wireutils.getMinimumRadius` est une estimation, jamais une contrainte du générateur. `CompoundPath` et `CableConduit` ne sont pas des planificateurs de regroupement. Préserver axes de sortie, tangences, passages, rayons applicables, dégagements, retenues, réserves et mouvements. Router chaque câble dans l'architecture retenue, sans superposer fictivement tous les axes dans une gaine.

Une B-spline requiert contrôle adaptatif sur tous ses spans et recherche d'extrema/bornes lorsque disponible. Un minimum seulement échantillonné peut réfuter la conformité ; il ne la prouve pas. Si aucune borne fiable n'est disponible, conserver **À valider** ou préférer une géométrie analytique contrôlable. Ne pas assimiler une interpolation à une simulation de rigidité, gravité ou vibration.

## Vérifier et conclure

Appliquer le pipeline [A–D de validation](references/validation.md), dans l'ordre, avec échecs et inconnues explicites : intégrité ; recalcul et géométrie fraîche ; intégration mécanique ; comparaison à la baseline. Ne pas masquer une erreur native derrière un ancien solide valide. Une inclusion câble/enveloppe de gaine exige une relation identifiée et justifiée ; elle n'exempte pas des collisions avec les parois réelles ou les autres objets.

Conserver résultats JSON, journal structuré des décisions, empreintes et paramètres des candidats, avec vue Markdown dérivée. Distinguer **test hors ligne**, **génération**, **recalcul**, **validation interactive** et **validation physique**, avec pour chaque phase exécutée/réussie/échouée/non exécutée et sa portée. Appliquer les statuts de conception définis dans [validation](references/validation.md), sans les confondre avec les maturités du projet. Mettre à jour les documents vivants concernés, sans créer un compte rendu séparé dans les projets qui l'interdisent.

Ne conclure « meilleur » qu'à partir de mesures comparables et de contraintes satisfaites. Livrer les choix, alternatives, preuves, limites, données manquantes et prochaine décision. Cette skill fournit une méthode, un planificateur de corridors et des contrôles réutilisables ; elle ne constitue ni un routeur automatique complet ni un certificat de montage réel.

Pour évaluer une évolution de cette skill, lire les [cas comportementaux d'autonomie](references/evaluation.md) en complément des tests exécutables existants ; ils vérifient les actions et conclusions observées, pas la seule présence d'instructions.
