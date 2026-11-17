# GO2bis — Matrice de qualification du moteur électromécanique V2

| Champ | Preuve |
|---|---|
| Exécution | `T-EM-ENGINE-GO2BIS` · 14 novembre 2026 · Windows amd64 |
| Verdict | **GO conditionnel** après correction · [Décision et périmètre dans DOC-VAL](../VALIDATION_QUALIFICATION.md#qualification-moteur-go2bis) |
| Exigences du projet | `CAB-CARTO-001`, `MEC-INT-001`, `METH-001` |
| Identification | Contrat L0 `2.0.0`, validateur L4 `2.0.0`, convergence L5 `1.0.0`. Sources et binaires par SHA-256. [Reçu de campagne](go2bis_results.json), [manifest T0 validé](../../.runtime/go2bis/t0/t0_run_manifest.json) |
| Environnement | GCC 16.2, Qt 6.11.2, Python 3.14.4, FreeCAD 1.1.3, Python FreeCAD 3.11.14, OCCT 7.8.1, Cables 0.3.7 |

| Exigence | Composant et essai | Résultat | Preuve |
|---|---|---|---|
| `G2B-00` — référentiel et contrats | L0, vérification de la baseline et régressions FreeCAD | 383 empreintes conformes. Fermetures actives et consolidées de 137 et 138 fichiers. 76 tests Python/FreeCAD, 19 tests Cables, 6 tests d’isolation et 41 assertions du planificateur réussis. | [L0–L2](go2bis_l1_l2.json), [journaux d’outillage et réouvertures](go2bis_results.json) |
| `G2B-01` — investigation | L1, six cas indépendants | Donnée locale F16 sourcée à 425,174 mm. Mauvaise révision, contradiction, HTTPS indisponible sur loopback, inconnue et référence sans preuve conservent le résultat ouvert. 24 tests L1 réussis. | [Oracles gelés](go2bis_l1_l2_plan.json), [résultats L1](go2bis_l1_l2.json) |
| `G2B-02` — interconnexion | L2 et relecture FreeCAD | Deux embases, deux fiches, seize contacts, quatre conducteurs et quatre circuits. Deux témoins positifs, quatre défauts détectés et deux inconnues conservées après correction. Sur le gabarit à course axiale de 8 mm, le corps droit balayé intersecte l’obstacle de 4 mm³. Le corps coudé à 90° conserve 3 mm de jeu. La référence commerciale et le geste physique restent **À valider**. | [Matrice et mesures L2](go2bis_l1_l2.json), [cas natif L2 dans L4](go2bis_l4.json) |
| `G2B-03` — décisions d’architecture | L3, conflit PM08/CAN1/F31 et diagnostic F40/F41 | 15 verdicts indépendants concordants. Deux échecs de routage avant changement de famille. Le déplacement voisin et la rupture du retour de diagnostic dégradent le verdict. | [Oracles et preuves L3](go2bis_l3_l5.json) |
| `G2B-04` — rétrovalidation et gel | L4, bancs et historiques sur copies | 100 attentes concordantes sur 29 cas et 71 constats. Relevés F12, F16/P73 et F31 reproduits. F24A, réserve F41 et tenue P85 ouvertes. Le gel altéré et l’artefact modifié sont refusés. | [Matrice L4 et mesures par défaut](go2bis_l4.json), [fermetures de documents](go2bis_results.json) |
| `G2B-05` — convergence | L5, pause, reprise, budget, rollback et fusion | `L5_PASS` sur banc monodocument. Reprise avec le même gel, sept variantes construites et deux fusions essayées. La première fusion est rejetée. `lateral-service` passe 13 contrôles L4 et couvre L1 et L2, pour 221,416 mm de longueur totale et une hauteur maximale de 10,993 mm. Les 3 suites, dont 14 scénarios CLI, réussissent. | [Rejeu L5 et preuves T0](go2bis_l3_l5.json), [reprise du gel](go2bis_results.json) |
| `G2B-06` — couverture et faux résultats | Rapprochement L2, comptages L4 et L5, oracles adversariaux | 71 lignes, 53 axes et 56 associations. Ensemble nominal L4 à 3 paires mécaniques, dont 2 BRep et une exclue par la borne de séparation. Sur la réception L4, 39 `PASS`, 21 `FAIL`, 11 `INCONCLUSIVE`, zéro `NOT_RUN`. Sans FreeCAD, 69 attentes `NOT_RUN`. Pour F31 bas, 349 paires, dont 311 exclues par séparation et 38 BRep, avec un calcul OCC inconclu. | [Lignes L2](go2bis_l1_l2.json), [paires et contrôles L4](go2bis_l4.json), [métriques consolidées](go2bis_results.json) |
| `G2B-07` — CAO liée et électricité | L4, même natif consolidé monodocument et deux projections électriques | 15 contrôles `PASS` au nominal, puis 14 `PASS` et un `FAIL` après retrait du retour électrique. Le graphe fourni et la géométrie native sont évalués sous le même gel. La correspondance broche–câble 3D reste ouverte. Le natif à XLink est refusé pour les mesures d’admission monodocument, avec 13 contrôles `NOT_RUN`. | [Cas mixte et contre-épreuves XLink](go2bis_l3_l5.json) |

## Corrections et témoins

| Lot | Entrée adversariale | Initial | Corrigé |
|---|---|---|---|
| L2 | Cordon 72 mm, polyligne 112 mm | `PASS` | `FAIL` |
| L2 | Broche de paire différentielle déclarée au potentiel opposé | `PASS` | `FAIL` |
| L4 | Port renommé GPIO sans identité indépendante | `PASS` | `INCONCLUSIVE` |
| L4 | Cordon de 0,1 A pour 1 A requis | `PASS` | `FAIL` |
| L4 | Cordon déclaré à 20 A avec provenance insuffisante | `PASS` | `INCONCLUSIVE` |
| L5 | Reprise avec verdict de succès et aucune copie consolidée | `L5_PASS`, T0 valide | Refus, aucun manifeste terminal |
| L5 | Reprise du gel après substitution du fichier mécanique | Gel accepté | Refus avant publication du manifeste. Le reçu intact de contrôle reprend. |

Dans ces témoins, un faux négatif est un défaut réel accepté. Un faux
positif est un défaut signalé à tort sur le témoin conforme. Une acceptation
indue d’un cas dont la preuve est indéterminée est comptée à part. Les matrices
par lot conservent les dénominateurs et les cas ouverts.

## Traces de réouverture et reproduction

| Copie historique | Fichiers pleinement chargés | Liens résolus | Processus |
|---|---:|---:|---:|
| A | 141 | 360 | 2 |
| Par faces | 145 | 364 | 2 |
| Consolidée | 138 | 376 | 2 |

Les empreintes avant et après concordent pour ces fermetures. Sur la copie
consolidée, l’inventaire BRep intégral a dépassé deux fois 180 s. Les
réouvertures légères comptent les documents et liens sans calcul BRep intégral.
Les observations ciblées et les inconnues sont tracées séparément dans la
preuve L4. Les guides des modules décrivent les commandes de compilation et
de rejeu. Le reçu structuré référence les manifestes, binaires, journaux et
mesures brutes conservés sous `.runtime/`.
[L1](../../technical_research_engine/README.md) · [L2](../../interconnection_engine/README.md) ·
[L3](../../architecture_decision_engine/README.md) · [L4](../../validation_engine/README.md) ·
[L5](../../convergence_manager/README.md) · [Reçu de campagne](go2bis_results.json)
