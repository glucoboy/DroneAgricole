# GO3B — Résultat du contrôle d’admission

**14 novembre 2026 · `NO_GO_MOTIVE` · Prototype cartographe sans dock, H-01.**
GO3A conserve le statut `GO3A_CONDITIONNEL`, indique `autorisation_go3b: false`
et ne fournit aucun candidat admissible. La campagne s’arrête au contrôle d’admission.
[Décision dans DOC-VAL](../../VALIDATION_QUALIFICATION.md#cartographe-go3b) ·
[Preuve JSON d’admission](GO3B_ADMISSION.json)

| Contrôle | Résultat |
|---|---|
| Gel et intégrité | `PASS`. Référence et fichiers du gel identiques à GO3A. Sur 180 fichiers contrôlés au début et à la fin, aucun écart. La fermeture XML XLink retrouve les 137 natifs attendus. [Empreintes](GO3B_SOURCE_MANIFEST.json) |
| Couverture L2 | `PASS`. Rejeu identique octet pour octet. Les 71 liaisons et 142 côtés A/B concordent avec 53 axes, 56 associations bidirectionnelles et 21 lignes sans axe motivées. Les 142 côtés ne renseignent aucune révision physique ni volume d’accouplement ou d’extraction qualifié. [Matrice](GO3B_INTERCONNECTION_COVERAGE.csv) · [BOM documentaire](../go3a/GO3A_CONNECTOR_BOM.csv) |
| CA01 | `PASS` documentaire. Six feuilles, 43 broches sur 15 références, zéro écart. R530–R533 sont déclarées DNP. |
| Admission GO3A | `FAIL`. Les huit exigences G3A-01 à G3A-08 restent `INCONCLUSIVE` sur les prérequis indiqués sous [Verrous de réception](../go3a/GO3A_HANDOFF.md#verrous-de-réception-go3b). |
| Réception du candidat GO3B | `NOT_RUN` sur les 71 liaisons. Copie consolidée, fusion, sauvegarde, réouverture indépendante, rapport du validateur, BOM de construction, vues et mesures avant/après restent sans résultat de candidat. Les preuves Action 3 concernent un autre périmètre de dépendances. |

GO2bis a testé un graphe indépendant avec la géométrie d’un monodocument,
avec détection de la suppression d’un retour. Le témoin XLink complet
laisse 13 contrôles CAO `NOT_RUN` et le rattachement des contacts et
conducteurs aux occurrences natives reste à démontrer. Sur les témoins
Action 3, la distance minimale nominale entre l’outil candidat et F31
est de 0,120 mm avant tolérances. Le gabarit de sortie TTL recoupe la PDB
aux deux positions de sonde étudiées. L’accès conjoint CAN1 et diagnostic
reste **À valider**.
[Contre-épreuves GO2bis](../go2bis_l3_l5.json) ·
[Variantes et mesures GO3A](../go3a/GO3A_VARIANTS.md)

La preuve JSON associe chaque prérequis ouvert à son contrôle de reprise et
aux éléments consultés. Le budget de reconstruction consommé est nul. Les
essais physiques GO4/GO5 restent au stade des prérequis décrits par GO3A.
[Préparation GO4](../go3a/GO3A_HANDOFF.md#mesures-matérielles-réservées-à-go4)
