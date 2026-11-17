# Clôture de la mission B · correctif V2.1 B.2

17 novembre 2026 · Windows `amd64` · Qt 6.11.2 · FreeCAD 1.1.3 · OCCT 7.8.1 · Cables Workbench 0.3.7

**Moteur — `GO_B`.** Le validateur scellé est **Qualifié** pour la couverture des paires XLink du cartographe nominal sur cette cible. Les 1 609 observations ont une provenance vérifiée. La réouverture a reproduit les 14 mesures de l’échantillon, dont les sept interférences.

**Prototype — `NON_CONFORME_GEOMETRIQUEMENT`.** Sept intersections sont constatées selon le référentiel nominal gelé. L’admission du montage reste **À valider**. GO 3A et GO 3B sont restés `NOT_RUN`.

La campagne porte sur le prototype cartographe sans dock, en état nominal sauvegardé. Les critères gelés fixent une garde de 0 mm, une tolérance de distance de 0,000001 mm et un seuil d’intersection de 0 mm³. Le registre des contacts autorisés est vide. [Configuration gelée](../../../.runtime/fix-b/validation_engine/fixtures/xlink_cartographe.json)

## Couverture

| Contrôle | Résultat |
|---|---:|
| Assemblage lié | 137 FCStd et 2 772 occurrences |
| Paires visibles avec au moins un câble | 28 514 |
| Paires exclues par borne AABB vérifiée | 26 905 |
| Paires candidates réconciliées | 1 609 sur 1 609 |
| Mesures authentifiées de la mission B réutilisées | 267 |
| Nouvelles mesures | 1 342 |
| Statuts BRep `PASS` / `FAIL` / `INCONCLUSIVE` / `NOT_RUN` | 1 602 / 7 / 0 / 0 |
| Empreintes des fichiers originaux retrouvées | 202 sur 202 |

L’audit a énuméré les paires et recalculé les bornes AABB à partir des poses sauvegardées. La plus petite marge des 26 905 exclusions au-delà du seuil vaut 0,0093536 mm. L’identité de chaque mesure lie les documents, les occurrences, les transformations, les BRep, l’environnement du validateur et les critères. Le checkpoint B initial et le checkpoint B.2 ont été contrôlés par SHA-256 et par leurs preuves T0. [Audit du checkpoint initial](../../../.runtime/fix-b/.runtime/b2-audit/baseline.json) · [Provenance finale par paire](../../../.runtime/fix-b/.runtime/b2-audit/final-provenance.json)

Le statut `PASS` du manifeste indique un résultat BRep concluant selon les seuils du criblage. La règle gelée `screening_only` conserve les 1 602 résultats sans intersection au statut d’admission `INCONCLUSIVE`. Les critères de dégagement fonctionnel, les révisions et les contacts de connectique, les retenues, la cinématique et les volumes de service restent **À valider**. La couverture liste aussi 564 contrôles autonomes de solides hors du dénominateur des paires, conservés au statut `NOT_RUN`, et la réserve TVS de CA01, un plan 2D sans solide fermé. [Registre des indéterminations](inconclusive.json) · [Détail de la couverture](coverage.json)

## Interférences nominales

Les trois interférences initiales sont localisées à l’éclatement du faisceau AIRY. Les quatre gaines partagent un nœud de routage au référentiel. Celui-ci ne comporte aucune autorisation d’intersection volumique pour ces occurrences.

| Paire | Intersection (mm³) | Distance minimale (mm) | Statut |
|---|---:|---:|---|
| AIRY et AIRY_PWR | 22,56622964 | 0 | `FAIL` |
| AIRY et AIRY_ETH | 16,00606354 | 0 | `FAIL` |
| AIRY et AIRY_SYNC | 1,08506944 | 0 | `FAIL` |
| AIRY_ETH et AIRY_PWR | 17,26828624 | 0 | `FAIL` |
| AIRY_ETH et AIRY_SYNC | 6,57037790 | 0 | `FAIL` |
| AIRY_PWR et AIRY_SYNC | 1,57271806 | 0 | `FAIL` |
| F37_POS et P73_Guide | 0,00000002837 | 0 | `FAIL` au seuil gelé |

Le résultat F37_POS/P73 est proche de zéro. Il conserve le statut produit par le seuil gelé. Sa criticité physique reste **À valider**. Les preuves contiennent les identifiants complets des sept paires. Pour les trois cas initiaux, elles détaillent les documents, occurrences, matrices, mesures et tolérances, et fournissent une vue 3D par intersection. [Interférences initiales et vues 3D](interferences.json) · [Manifeste des paires](pairs.json)

## Exécution et relecture

Les lots ont été exécutés dans des processus FreeCAD indépendants. Le traitement principal a utilisé jusqu’à six processus et 56 paires par lot. Le superviseur journalise les débuts de mesure, la mémoire maximale, les expirations et les empreintes des requêtes et résultats. Il sauvegarde atomiquement chaque checkpoint de lot et en consigne le SHA-256 dans un journal distinct. Un test de redémarrage a accepté le point scellé, refusé un SHA-256 falsifié et retrouvé les résultats sans nouveau lot. [Journaux et métriques](lots.json) · [Reprise scellée](../../../.runtime/fix-b/.runtime/b2-execution/restart-test.json)

Les 52 lots scellés incluent 19 expirations, récupérées par isolement et rejeu. Les lots achevés donnent en moyenne 36,7 s avant la première paire et 1,14 s par observation, mesurée par l’intervalle entre deux débuts de contrôle. Le pic de mémoire échantillonné atteint 2,20 Gio par processus. La plus longue mesure d’un lot achevé dure 165,35 s. Les tentatives interrompues avant publication d’un sceau d’autorité ont été mesurées de nouveau. [Journaux et métriques](lots.json)

Les reprises ciblées ont isolé les expirations. Pour le composé Holybro de 2 059 solides et le cas CA01 issu du lot expiré, le rejeu réutilise les BRep mondiales de la fermeture authentifiée. Il vérifie les solides du composé, sélectionne avec une borne conservatrice les sous-solides susceptibles d’intersecter le câble, calcule le booléen OCCT et cherche la distance BRep minimale par bornes croissantes. Les méthodes directe et par composants concordent sur les reprises disposant des deux mesures. Le binaire L4 d’origine a vérifié le checkpoint rassemblé et publié le T0 final. [Assemblage des preuves](../../../.runtime/fix-b/.runtime/b2-audit/assembly.json) · [Checkpoint final](../../../.runtime/fix-b/.runtime/fix-b-coverage/prototype-final/run-e12251ac-dad7-4a35-bfd5-0d57a2422e0c/checkpoint.json) · [T0 final](../../../.runtime/fix-b/.runtime/fix-b-coverage/prototype-final/run-e12251ac-dad7-4a35-bfd5-0d57a2422e0c/t0_run_manifest.json)

La réouverture a repris le checkpoint et le natif enregistrés dans un nouveau processus. L’échantillon déterministe comprend les sept interférences, des paires historiques et nouvelles, et un cas mesuré par composants. Les 14 observations concordent exactement. Les cas négatifs du repère décalé de 3 mm et du cache falsifié ont été rejoués. L4 a réussi 7 tests et L5 a réussi 5 tests. Le test `v21_gate` est resté `NOT_RUN` pour respecter le périmètre GO 3A et GO 3B. [Réouverture et observations comparées](../../../.runtime/fix-b/.runtime/b2-audit/independent-reopening.json) · [Non-régression](regressions.json)

## Reproduction et preuves

La racine d’exécution est `.runtime/fix-b`. Elle contient le validateur et les entrées scellés de la mission B. Les recettes B.2 sont placées dans le workspace. Depuis la racine du dépôt, la commande ci-dessous régénère l’inventaire, les journaux consolidés et le JSON à partir des preuves relues.

```powershell
$base = '.runtime/fix-b/.runtime/b2-audit'
$seal = Get-Content "$base/final-seal.json" -Raw | ConvertFrom-Json
python -B validation_engine/tests/publish_v21_b2.py ".runtime/fix-b/$($seal.path)" `
  $base docs/verification/v21_b2
```

Les arguments du L4, les points de reprise par lot et leurs SHA-256 sont archivés avec les preuves. La recette de vérification accepte les chemins et empreintes de ces points via `--progress`. Les échantillons indépendants et l’inventaire ont chacun leurs requêtes, résultats et journaux. [Commande L4 finale](../../../.runtime/fix-b/.runtime/b2-audit/final-argv.json) · [Scellement final](../../../.runtime/fix-b/.runtime/b2-audit/final-seal.json) · [Recette des lots](../../../validation_engine/tests/replay_xlink_batches.py) · [Recette de revalidation](../../../validation_engine/tests/verify_v21_b2.py) · [Rapport JSON de couverture](coverage.json)
