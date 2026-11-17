# Exécution, isolation et recette

## Préparer sans reconstruire l'original

Cette skill est découverte dans `.agents/skills/electromechanical-integration` du projet. L'invocation explicite est `$electromechanical-integration` ; la sélection implicite reste autorisée. Sur un autre projet, transférer le dossier complet et adapter les chemins de travail, les sources de connectivité et le constructeur. Aucun nom de pièce du drone n'est requis par les utilitaires.

Lire les sources locales avant de les importer : un script Python peut avoir des effets à l'import. Inventorier les références natives et les fichiers auxiliaires effectivement lus par les proxies, macros et constructeurs. Ne pas lancer le constructeur complet du drone pour obtenir une seule fonction réutilisable.

`scripts/workspace_guard.py` est de l'infrastructure filesystem, exécutable avec Python ≥ 3.10. Il ne charge pas FreeCAD. La commande `stage` ferme récursivement les liens XML `XLink` des fichiers FCStd, conserve l'arborescence relative, copie les fichiers explicitement ajoutés et écrit un reçu SHA-256/paramètres. Source et destination doivent être disjointes ; destination nouvelle, sans écrasement. Les liens absolus, dépendances hors racine/manquantes et liens filesystem sont refusés. Un refus nécessite de préparer un remappage **sur copie** et de l'auditer, pas de modifier l'original.

```powershell
python -B .agents/skills/electromechanical-integration/scripts/workspace_guard.py stage `
  --root 'chemin/du/projet-cao-source' `
  --entry 'assemblages/Ensemble.FCStd' `
  --extra 'configuration.json' `
  --parameters 'parametres-experience.json' `
  --target '.runtime/essai-faisceaux'
python -B .agents/skills/electromechanical-integration/scripts/workspace_guard.py verify `
  '.runtime/essai-faisceaux/experiment.json'
```

La fermeture automatique porte uniquement sur les `XLink` natifs. Ajouter tous les fichiers auxiliaires via `--extra`, préserver les versions/hashes des ateliers et constructeurs, puis **vérifier dans FreeCAD que chaque référence résolue est dans la copie** avant de générer. Un chemin absolu caché dans un proxy n'est pas automatiquement remappé par cet utilitaire. Les empreintes de source sont vérifiées après copie et de nouveau en fin d'expérience ; un reçu ne garantit pas à lui seul l'isolation d'un constructeur arbitraire.

## Choisir le backend sur observation

1. Découvrir les outils MCP disponibles et appeler une fois leur contrôle de disponibilité. Une erreur contenue dans un résultat outil vaut erreur même si `isError` vaut false. Capturer le résultat réel ; un paquet installé ne prouve pas une connexion.
2. Si MCP fonctionne, exécuter les modifications de documents sur le chemin synchrone supporté, dans la copie. Après timeout à issue inconnue, contrôler l'état avant tout rejeu ; ne pas lancer un second écrivain. Les outils asynchrones réservés aux calculs sans mutation ne conviennent pas.
3. Sinon, localiser le Python embarqué de FreeCAD puis exécuter :

```powershell
python -B .agents/skills/electromechanical-integration/scripts/workspace_guard.py probe-python `
  'C:/Program Files/FreeCAD 1.1/bin/python.exe'
```

Ce probe exige import FreeCAD/Part et boîte de volume 6 mm³ avec un solide valide. Timeout 30 s. Il valide **Part uniquement** ; il ne certifie ni l'atelier Cables ni sa GUI. `select_backend(False, probe)` distingue repli vérifié et indisponibilité totale, sans marquer une génération exécutée.

4. Pour le natif Cables, exécuter le probe synthétique décrit dans [freecad-api.md](freecad-api.md). Le processus indépendant initialise une GUI cachée/offscreen ; ne pas masquer une fenêtre utilisateur. Le Python MCP et le Python FreeCAD peuvent être différents. Si ni MCP ni repli ne sont vérifiés, terminer les tâches hors ligne et laisser génération/recalcul non exécutés.

## Utiliser les capacités livrées

Dans la copie, faire varier configurations, placements de guides modifiables,
corridors, longueurs et protections sans solliciter un arbitrage pour chaque
essai. Conserver paramètres/empreintes et résultats par candidat ; réutiliser
le constructeur existant sans modifier sa source. Les essais et retours arrière
restent isolés, aucune promotion dans les natifs originaux n'est implicite.

Le noyau métier est C++17/Qt6Core ; les scripts Python sont les adaptateurs de mesure FreeCAD et l'infrastructure de copie/test. Ils ne réécrivent pas le constructeur existant. Le [contrat du planificateur](planner-contract.md) donne compilation et commandes `plan`/`validate`, ainsi qu'une fixture sans noms de pièces spécifiques.

Après compilation, un premier essai autonome :

```powershell
.runtime/electromechanical-integration/planner-build/harness-planner.exe plan `
  .agents/skills/electromechanical-integration/references/synthetic-network.json `
  .runtime/electromechanical-integration/topology.json `
  .runtime/electromechanical-integration/topology.md
```

`baseline_separate` est une référence calculée sur le graphe donné, **pas une mesure automatique de l'assemblage initial**. Pour comparer au réel, inventorier la topologie existante et ses routes dans le même graphe, l'évaluer par `validate`, puis comparer aux propositions avec mesures CAO à périmètre égal. Si le graphe change, recalculer les deux côtés. Conserver l'enregistrement de connectivité complet ; le planificateur vérifie sa projection uniquement.

Le résultat propose des corridors et des groupes ; il ne fournit pas les points/offsets des câbles. Les réaliser avec les constructeurs natifs inspectés, puis passer les formes transformées dans le repère commun à `inspect_route`, `inspect_solid` et `inspect_pair`. `rebuild_cable_in_isolated_document` modifie seulement le cache du câble fourni : l'appelant doit avoir vérifié l'isolation. Les verdicts ne remplacent pas le pipeline A–D complet.

## Rejouer les tests et valider la skill

Vérifier `CMAKE_HOME_DIRECTORY` du cache avant de réutiliser un build : il doit
pointer vers les sources actuelles de la skill, pas une ancienne copie de test.
Sinon configurer un nouveau répertoire depuis `scripts/` selon le contrat du
planificateur. Pour les changements d'autonomie, compléter ces régressions par
les [évaluations comportementales](evaluation.md) ; les deux preuves ont des
portées distinctes.

```powershell
python -B .agents/skills/electromechanical-integration/scripts/tests_workspace.py
ctest --test-dir .runtime/electromechanical-integration/planner-build --output-on-failure
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' -B `
  .agents/skills/electromechanical-integration/scripts/tests_freecad.py `
  --builder hardware/mecanique/cartographe/verification/cable_workbench_prototype.py `
  --output .runtime/electromechanical-integration/freecad-tests.json
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' -X utf8 `
  'C:/Users/Utilisateur/.codex/skills/.system/skill-creator/scripts/quick_validate.py' `
  .agents/skills/electromechanical-integration
```

Les chemins absolus sont ceux vérifiés sur le poste de référence ; adapter à l'installation. Le validateur officiel nécessite PyYAML (présent dans le Python FreeCAD de référence). Les tests de copie utilisent par défaut un sous-dossier de `.runtime`, modifiable par `--temp-root`. Ils créent des archives XML de test ; ces archives ne sont pas des assemblages géométriques validés. Les tests FreeCAD utilisent de vrais BRep et objets natifs en mémoire, jamais les FCStd du drone.

Limiter le processus FreeCAD dédié à 60 secondes ; une expiration est un échec/non-finalisation, pas un succès de test. Enregistrer sortie, code retour, rapport écrit, empreintes des helpers et versions. Ne déclarer un test passé qu'après vérification du rapport final. Refaire ensuite les liens Markdown et `quick_validate.py` après toute correction de la skill. Les preuves synthétiques de sa création sont référencées dans DOC-VAL du projet ; elles ne remplacent pas les preuves de la mission qui l'utilisera.
