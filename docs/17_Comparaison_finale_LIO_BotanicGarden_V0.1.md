# Comparaison finale des LIO — BotanicGarden `1006-03`

| Champ | Valeur |
|---|---|
| Référence | DOC-17 |
| Version | V0.1 |
| Date | 19 août 2026 |
| Statut | Candidat |
| Dataset | BotanicGarden `1006-03`, VLP-16 + Xsens |
| Algorithmes | FAST-LIO2, Point-LIO et LIO-SAM |
| Protocole | séquence complète, `1×`, QoS fiable harmonisée |

## 1. Conclusion

Les trois algorithmes terminent la séquence complète en temps réel, reçoivent `5 762 / 5 762` scans et publient `5 758` odométries. La chaîne de benchmark est donc comparable et aucune perte DDS ne biaise le classement.

**FAST-LIO2 est retenu comme baseline principale du prototype embarqué.** Il possède la meilleure ATE en translation, `0,35916 m`, tout en restant proche de Point-LIO en consommation : `0,391` cœur et `306,9 Mio`. C'est le meilleur compromis actuel entre cohérence globale, charge et maturité de l'intégration.

**LIO-SAM est retenu comme candidat de précision complémentaire.** Il obtient la meilleure orientation absolue ainsi que les meilleures RPE en translation et en rotation. En contrepartie, il consomme `4,09×` plus de CPU et `2,01×` plus de mémoire que FAST-LIO2. Il doit être répété puis testé sur Jetson avant toute préférence embarquée.

**Point-LIO reste la référence de sobriété calcul.** Il utilise le moins de CPU, mais son ATE translation est la moins bonne des trois et ses gains locaux sur FAST-LIO2 sont faibles. Il n'est pas prioritaire pour la prochaine campagne, sans être écarté des essais futurs sur d'autres capteurs ou dynamiques.

Ce résultat clôt la comparaison sur BotanicGarden `1006-03`. Il ne constitue pas encore une sélection matérielle définitive : un seul dataset et un passage complet par candidat ne mesurent ni la répétabilité inter-exécution, ni le comportement sur Jetson, ni la robustesse aux scènes viticoles difficiles.

## 2. Protocole comparable

Les trois passages utilisent :

- le même bag de `581,120665 s` et `5 762` scans VLP-16 ;
- la même IMU Xsens et les mêmes extrinsèques officielles ;
- un rejeu demandé à `1×` ;
- une QoS fiable de profondeur 100 ;
- les compteurs internes et la vidange explicite du pipeline ;
- l'ATE alignée en SE(3), sans facteur d'échelle ;
- la RPE à une seconde ;
- le tableau de bord actif pour les trois mesures de référence ;
- la fermeture de boucle LIO-SAM désactivée afin de comparer des odométries LIO.

Les configurations sont les réglages de référence de chaque intégration. Elles ne sont pas supposées avoir reçu le même degré d'optimisation : FAST-LIO2 a déjà fait l'objet d'une campagne de sensibilité, alors que Point-LIO et LIO-SAM restent à qualifier plus finement.

## 3. Résultats principaux

| Mesure | FAST-LIO2 | Point-LIO | LIO-SAM | Meilleur |
|---|---:|---:|---:|---|
| Scans reçus | 5 762 | 5 762 | 5 762 | égalité |
| Odométries publiées | 5 758 | 5 758 | 5 758 | égalité |
| Odométries / scans | 99,9306 % | 99,9306 % | 99,9306 % | égalité |
| ATE translation RMSE | **0,35916 m** | 0,49940 m | 0,41206 m | FAST-LIO2 |
| ATE orientation RMSE | 1,67155° | 1,55623° | **1,13826°** | LIO-SAM |
| RPE translation RMSE, Δt = 1 s | 0,04825 m | 0,04642 m | **0,04174 m** | LIO-SAM |
| RPE rotation RMSE, Δt = 1 s | 0,59370° | 0,58981° | **0,57086°** | LIO-SAM |
| Longueur estimée / référence | 99,2886 % | 99,1774 % | **99,3739 %** | LIO-SAM |
| CPU moyen équivalent | 0,391 cœur | **0,337 cœur** | 1,601 cœur | Point-LIO |
| RSS maximal | **306,9 Mio** | 315,7 Mio | 617,6 Mio | FAST-LIO2 |
| Facteur effectif | **0,99919×** | 0,99802× | 0,99785× | tous temps réel |
| Couverture de trajectoire | 580,653 s | 580,653 s | 580,653 s | égalité |

Toutes les métriques sont finies. Les `5 758` poses sont associées à la vérité terrain dans chaque passage et la couverture temporelle est identique.

## 4. Lecture des écarts

### 4.1 Cohérence globale

FAST-LIO2 possède l'ATE translation la plus faible. LIO-SAM est `14,7 %` moins bon sur cette mesure, mais reste `17,5 %` meilleur que Point-LIO. Point-LIO est `39,0 %` au-dessus de FAST-LIO2.

LIO-SAM obtient en revanche l'ATE orientation la plus faible. L'erreur de Point-LIO est `36,7 %` supérieure et celle de FAST-LIO2 `46,9 %` supérieure à celle de LIO-SAM.

### 4.2 Précision locale

LIO-SAM gagne les deux RPE :

- Point-LIO présente `11,2 %` de RPE translation supplémentaire ;
- FAST-LIO2 présente `15,6 %` de RPE translation supplémentaire ;
- les écarts de RPE rotation sont plus faibles : `+3,3 %` pour Point-LIO et `+4,0 %` pour FAST-LIO2.

Le gain local de LIO-SAM est réel sur ce passage, mais devra être comparé à la variabilité de trois répétitions avant d'être considéré comme statistiquement stable.

### 4.3 Ressources

Point-LIO utilise le moins de CPU, suivi de FAST-LIO2. LIO-SAM demande :

- `4,09×` le CPU moyen de FAST-LIO2 ;
- `4,75×` le CPU moyen de Point-LIO ;
- `2,01×` la mémoire maximale de FAST-LIO2 ;
- `1,96×` la mémoire maximale de Point-LIO.

LIO-SAM tient néanmoins le rejeu à `1×` sur le PC. Cette réussite ne garantit pas encore la tenue simultanée avec perception visuelle, cartographie sémantique et planification sur une Jetson Orin.

## 5. Décision de travail

| Rôle | Candidat | Justification |
|---|---|---|
| Baseline principale | FAST-LIO2 | meilleure ATE translation et faible charge |
| Candidat précision | LIO-SAM | meilleures orientation et RPE, coût calcul élevé |
| Référence sobriété | Point-LIO | CPU minimal, précision globale moins favorable |

La prochaine campagne LIO doit donc concentrer les répétitions sur FAST-LIO2 et LIO-SAM. Point-LIO reste disponible dans le tableau de bord pour les nouveaux datasets et les essais de capteurs, mais ne bloque plus l'avancement vers la simulation viticole.

## 6. Artefacts de référence

- FAST-LIO2 : `results/benchmarks/fast_lio2/botanicgarden_1006-03/dashboard_20260819T171258Z_2a31bc7f/` ;
- Point-LIO : `results/benchmarks/point_lio/botanicgarden_1006-03/dashboard_20260819T173537Z_6feb6ccc/` ;
- LIO-SAM : `results/benchmarks/lio_sam/botanicgarden_1006-03/dashboard_20260819T205649Z_7f42a0fa/` ;
- synthèse machine : `results/benchmarks/comparison/botanicgarden_1006-03/full_1x_qos_harmonized_20260819.json` ;
- outil : `tools/benchmarks/compare_lio_runs.py`.

## 7. Prochaines validations

1. répéter FAST-LIO2 et LIO-SAM trois fois à `1×` sur la séquence complète ou sur des fenêtres dynamiques représentatives ;
2. exécuter les deux candidats à `1×` sur la Jetson retenue et mesurer la marge disponible pour la perception ;
3. rejouer les candidats sur au moins un second dataset et dans `VINEYARD_BENCH_V01` ;
4. vérifier la QoS avec les pilotes réels des LiDAR cibles ;
5. ne créer un ADR de sélection définitive qu'après ces validations.
