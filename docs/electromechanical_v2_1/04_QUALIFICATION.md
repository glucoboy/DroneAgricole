# Matrice de qualification indépendante V2.1

**T-CARTO-V21-QUAL · 15 novembre 2026 · Windows amd64**

**Verdict d’architecture `V21_EXPLORATION_NO_GO`** pour le pilotage
d’une campagne sur copies par la livraison intégrée. Le statut des tests
est indépendant des verdicts rendus par les moteurs. Un test de défaut
est `PASS` si le moteur observe le défaut attendu. `FAIL` indique un
écart à l’oracle, `INCONCLUSIVE` une preuve insuffisante et `NOT_RUN`
un contrôle qui n’a pas été atteint ou exécuté.

Le périmètre couvre H-01 en préflight, des bancs synthétiques et des
relectures du prototype actif et de témoins historiques sur copies.
Les oracles ont été fixés avant les nouveaux candidats. Les 27 entrées
du gel transversal et les deux fermetures historiques L0 de 137 et 138
natifs ont été revérifiées. Les nouveaux dossiers de revalidation
reçoivent leurs critères de la campagne et remesurent les fichiers
sauvegardés dans des processus FreeCAD distincts. L’essai adversarial
sur la reprise XLink a vérifié l’effet d’un cache modifiable sur ce
mécanisme. [Décision dans DOC-VAL](../VALIDATION_QUALIFICATION.md#qualification-integree-v21) ·
[Résultats, commandes et empreintes](../verification/v21_qualification_results.json).

## Q1 à Q4

| Cas | Attente gelée | Statut du test et résultat observé |
|---|---|---|
| Q1 · H-01 sur la livraison courante | Rejouer `NO_GO_MOTIVE` à 0/12, puis produire `EXPLORATION_ALLOWED` avec huit écarts ouverts et `FINAL_NO_GO` sans preuve | `FAIL` d’intégration. Les trois modes sortent avec le code 1 avant le verdict. Le SHA-256 de `freecad_worker.py` est le seul écart parmi les 180 fichiers gelés. Aucun candidat ni rapport d’admission publié. |
| Q1 · Gardes de perte de liaison, collision et écriture | Refuser les défauts connus, la destination d’origine et l’absence de copie privée | `PASS` au niveau de la fonction de décision compilée, qui signale ces quatre motifs. Contrôles et comptabilité de bout en bout `NOT_RUN` derrière la garde d’intégrité. Le test isolé n’établit pas qu’une copie physique a été créée. |
| Q1 · Promotion d’une hypothèse | Refuser une déclaration de preuve impérative issue d’une hypothèse | `FAIL` au niveau de la garde isolée, qui ne renvoie aucun motif de refus pour le plan injecté. Les données de preuve imposées dans la demande sont ignorées, et un `PASS` déclaré dans les constats du plan reste un constat d’essai. Réemploi en réception et reprise de la file `NOT_RUN` sur H-01 courant. La fonction de réception sans reçu rend `FINAL_NO_GO`. |
| Q2 · Positif nominal | Deux cartes, deux embases, deux fiches, quatre contacts par interface, continuité, détrompage, corps accouplés, repères et retrait | `PASS` L2 et réouverture indépendante du banc. Quatre conducteurs, huit paires de contacts, sorties à x = 14 et 86 mm. |
| Q2 · Interfaces et géométrie | Mauvais port F12, inversion, clé incompatible, sortie incohérente et retrait obstrué détectés | `PASS` pour les injections isolées. `FAIL` si le faux repère est déplacé de 3 mm dans la fiche et que l’axe est ajusté au même point. L2 et l’adaptateur natif rendent alors `PASS`. L’oracle indépendant rejette la pose. |
| Q2 · Identité et preuves | MPN non vérifié, révision contradictoire, contact absent et modèle approximatif conservent un état ouvert. La CAO seule ne valide pas la provenance fournisseur | `PASS` pour les quatre états `INCONCLUSIVE`. `FAIL` pour la provenance locale, où un fichier CAO étiqueté comme source fournisseur obtient `PART_PROVENANCE PASS`. Le verdict global du prototype reste `INCONCLUSIVE`. |
| Q3-01 à Q3-02 · Banc XLink | Sélectionner les instances répétées par occurrence et invalider la preuve si une dépendance change | `PASS`. Le banc L4 est relu séparément et la mutation d’une dépendance est détectée avec les mêmes octets de racine. |
| Q3-03 à Q3-05 · Témoin réel et reprise | Rejouer la fermeture du cartographe, rapprocher les lignes et les axes, vérifier la reprise, signaler les exclusions et les inconnues | `PASS` dans le périmètre exécuté. 137 FCStd, 71 lignes, 53 axes, 56 associations dont 11 inverses, 21 lignes hors axe, 142 côtés et zéro contact joint. Après timeout, 510 mesures reprises. Sur 28 514 paires, 26 905 exclusions AABB, 103 mesures BRep dont cinq interférences de criblage, et 1 506 `NOT_RUN`. OEM X650 simplifié `INCONCLUSIVE`. Verdict du prototype `V21_XLINK_CONDITIONAL`. |
| Q3-06 · Intégrité de la reprise | Refuser ou remesurer une observation XLink altérée | `FAIL`. Sur banc, la collision de 7,653 mm³ devient 0 mm³ avec 5 mm de jeu déclaré, et l’état géométrique devient `PASS` sans remesure. Le T0 est accepté. Le verdict de ce banc demeure `V21_XLINK_CONDITIONAL`. |
| Q4 · Convergence des parcours | Deux échecs de service, changement de famille, rejet des fusions incompatibles et mesure du consolidé | `PASS` sur le banc L5 monodocument. Deux intersections avec le volume de service D1 à ≈31,416 mm³. Conflit d’affectations rejeté, premier portefeuille construit en échec puis retour arrière. Le second portefeuille satisfait 14 constats L4. Longueur totale 221,416 mm et jeu de service minimal 4 mm. |
| Q4 · Pause et budget | Reprendre sous le même gel et retrouver le résultat du scénario continu | `PASS`. Pause à un détail et zéro fusion, puis six variantes détaillées et deux fusions. Le terminal `L5_PASS` est reproductible et le point de reprise reste stable une fois la campagne terminée. |
| Q4 · Chaîne intégrée | Consommer le préflight et mettre en œuvre une décision de connectique, d’implantation ou de diagnostic, puis revalider la copie consolidée | `FAIL`. La CLI historique ne consomme pas la file V2.1. L3 crible des changements d’implantation et de diagnostic. Le constructeur L5 ne matérialise que les affectations de parcours de ce banc. La fusion n’a pas été exécutée sur un assemblage XLink avec continuité démontrée. |

## Q5 · Témoins historiques

| Cas | Statut du test | Observation et portée |
|---|---|---|
| F16 BSpline_K | `PASS` | Rayon local échantillonné à 4,95 × 10⁻⁸ mm, inférieur à l’oracle diagnostique historique de 22 mm. Le BRep en cache paraît valide. La régénération à cache vide redonne une gaine invalide. |
| F16 BSpline_P et P73 | `PASS` | Intersection reproduite de 704,630 mm³. Le témoin initial donne 0 mm³ et 0,200 mm de jeu. |
| F12 | `PASS` | Les extrémités natives reproduisent la projection GPS2 dans A et TELEM1 dans Faces selon les repères du dossier. Révision et compatibilité montées `INCONCLUSIVE`. |
| F31 et CAN1 | `PASS` | F31 croise le gabarit d’outil vertical +X de 73,526 mm³. L4 reproduit 0,0518 mm³ d’intersection entre F35 et le volume d’approche CAN1. Le trajet bas garde un booléen OCC non résolu. Accès et retrait complets `INCONCLUSIVE`. |
| F24A | `INCONCLUSIVE` | Extrémité de Faces relue à (−59,825, 15, 120,7) mm. L’identité de la porteuse et le pinmux GPIO restent ouverts. |
| F40/F41 | `INCONCLUSIVE` | Axes F41 relus à 1 180,942 mm et 340,408 mm dans les deux états historiques. Réserve utile non mesurée. Le cas d’accès simultané TTL/USB de F40 est cité dans la preuve Action 3, son rejeu natif est `NOT_RUN`. |
| P85 | `INCONCLUSIVE` | Jeux reproduits de 0,050 mm à P66 et de 0,307 mm à F25. Tenue physique non testée. |

Six cas historiques ont été relus deux fois avec observations identiques et
empreintes d’origine et de copie concordantes. Deux processus supplémentaires
ont relevé les paires ciblées F31 et P85. Les statuts ouverts expriment la
portée des preuves historiques, sans créer de nouvelle hypothèse de montage.

## Régressions et conditions de reprise

- L0 et moteur historique. 77 tests Python, six contrôles d’isolation,
  19 contrôles Cables et le planificateur passent. Deux revalidations du
  banc statique sur dossiers neufs sont équivalentes. Sur 108 références
  L0, trois fichiers ont évolué depuis le gel historique, dont le worker
  qui bloque H-01.
- L1–L4. 4/4 suites L1–L3 et 7/7 suites du validateur passent. Le rejeu
  de réception GO 2 bis couvre 29 cas, 71 constats et 100 attentes
  concordantes. Verdict de réception `L4_CONDITIONAL`, T0 valide.
- L5. 3/4 suites passent, dont les 14 scénarios de la CLI historique.
  La suite `v21_gate` échoue sur l’écart d’empreinte de Q1. Les deux
  contre-épreuves de sortie fictive et de cache altéré reproduisent
  les défauts de qualification. Aucun faux rejet du témoin nominal
  n’a été relevé dans ces contre-épreuves.
- Reprise du moteur intégré. Réconcilier l’autorité H-01 avec les outils
  actuels sous un gel vérifiable. Rattacher sortie physique et provenance
  à des oracles indépendants du candidat. Authentifier ou remesurer les
  observations reprises. Exécuter et revalider de bout en bout une
  action V2.1 sur copie consolidée en liant électricité et géométrie,
  puis rejouer les contre-épreuves.
- Réception finale du prototype **À valider**. Campagnes GO3A/GO3B,
  essais physiques et autres plateformes `NOT_RUN`, hors périmètre
  de cette mission.
