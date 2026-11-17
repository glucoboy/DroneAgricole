# Preuve de réception L2

**L2_CONDITIONAL** — le banc numérique d’interconnexion est **Qualifié** pour
deux équipements, deux interfaces droites et un cordon à quatre contacts
sur Windows amd64. Le rapprochement documentaire de l’actif sans dock est
reproductible. L’accouplement et le brochage réels du cartographe restent
**À valider**. [DOC-VAL](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l2)

| Exigence | Exécution et couverture | Résultat |
|---|---|---|
| `CAB-CARTO-001` — accouplement et continuité | C++17/Qt 6 Core. Deux embases, deux fiches, seize contacts, quatre conducteurs et quatre circuits, dont les deux potentiels d’une paire. La table de continuité relie signal, broche, contacts et conducteur. | `PASS` nominal pour la compatibilité et la continuité déclarées. [Entrée](../../interconnection_engine/examples/banc_l2.json) · [Rapport et BOM du banc](proofs_l2/banc_cpp.json) |
| `CAB-CARTO-001` — défauts injectés | Mauvais port F12/TELEM1–GPS2, permutation de conducteurs, clé incompatible à nombre de voies égal, terminaison sur point générique. Tests supplémentaires sur la couverture de broches, la provenance et les limites de câble. | `FAIL` pour un écart établi. Référence, brochage ou preuve fournisseur absents donnent `INCONCLUSIVE`. [Tests](../../interconnection_engine/tests/test_interconnection.py) |
| `MEC-INT-001` — pose, sortie et retrait | Mauvaise rotation de fiche, réorientation d’équipement, sortie manquante, point de sortie décalé et enveloppes obstruées ou détachées. Recalcul FreeCAD 1.1.3/Cables 0.3.7 dans un processus distinct. | Repères et volumes nominaux conformes au banc. Obstacle et sommet générique coïncident rejetés dans le natif. [FCStd](../../hardware/mecanique/banc_interconnexion/assemblages/Banc_Interconnexion.FCStd) · [Preuve native](../../hardware/mecanique/banc_interconnexion/verification/native_l2.json) |
| `CAB-CARTO-001` — rapprochement actif | 71 lignes, 53 natifs d’axes et 56 associations bidirectionnelles. 4 lignes conducteur, 37 fonction, 2 bus, 7 cordon, 21 hors périmètre d’axe embarqué. Les axes partagés AIRY et F_M8, les six lignes multiaxes et les motifs d’absence sont conservés. | 108 empreintes locales vérifiées. F12 actif `FAIL` géométrique, compatibilité `INCONCLUSIVE`. F16 seul diffère par son empreinte de la copie du 8 novembre, où neuf lignes restent ouvertes. [Rapprochement](L2_RECONCILIATION.json) |
| `CAB-CARTO-001` — références réelles et recherches | L1 établit le constat géométrique F12. L’identité montée de TELEM1 et le rayon dynamique F16 applicable restent `UNKNOWN`. | BOM réelle candidate `INCONCLUSIVE`. Référence W12 inconnue et cordon USBFireWire RR-ASMUK-20GRHF cité comme candidat F16. [BOM et recherches consommées](proofs_l2/cartographe_candidats.json) |

Les deux suites CTest L2 couvrent 19 tests d’interconnexion et 6 tests de
rapprochement. Les deux modèles d’exemple passent le schéma L0. La suite L1
passe et trois rapports L1 sont consommés. Le rapprochement rejoué est
identique octet pour octet. Le FCStd publié a été rouvert une seconde fois
dans un processus neuf, sur copie et avec la même empreinte. L’adaptateur
rejette le rapport de pose réorientée avant de construire. La recette est
dans les guides locaux. [CLI et tests](../../interconnection_engine/README.md) ·
[Rejeu FreeCAD](../../hardware/mecanique/banc_interconnexion/README.md)

L’adaptateur a exercé `ElectricalDevice`, `CableConnector`, `CableTerminal`,
l’import STEP et les liens d’extrémités `WireFlex` vers des sommets de
terminaux. Le RPC `freecad-mcp` 0.1.22 a renvoyé `WinError 10013`. La preuve
native vient du Python embarqué dans FreeCAD. Le banc utilise des géométries
synthétiques et des retraits axiaux. La validation interactive et les essais
physiques, CEM, de flexion et de signal haut débit restent ouverts.

| Interfaces réelles à documenter | Information attendue |
|---|---|
| F12/W12, CA01 J402 et Pixhawk TELEM1 | Révision montée de la porteuse, fiche et contacts exacts, TX/RX/GND, niveaux et verrouillage. Vérifier le port du natif actif. [Holybro](https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/ports-pinout) · [Recherche L1](proofs_l2/F12-TELEM1-REVISION.json) |
| F16 USB 3, caméra et hôte | Marquage du cordon, orientation Micro-B, fixation, dégagement et rayon dynamique du lot. [Recherche L1](proofs_l2/F16-MOUNTED-BEND-RADIUS.json) |
| F24A GPIO et interfaces CSI/MIPI | Porteuse et pinmux applicables, référence de fiche, polarité et plan de contacts du câble ou de la nappe. |
| F31 CAN1/PM08 et branches CAN | Prise, verrou, course, brochage CAN H/L et alimentations, terminaison du bus et accès PM08. |
| RF/GNSS, W22 SMA et interfaces directes | Genre, polarité et impédance, référence du cordon/embase, attache de blindage, espace de serrage et de retrait. |
| F40/JWPF, W20/W24.C/W25 et kit LED | Révisions et brochages des branches, terminaison et retenue du cordon, données des lignes encore ouvertes sur la copie. |
| AIRY, M8, POWER1/POWER2, W05/W38 et autres cordons d’énergie | Plans de broches et références montées, sections, courant par voie, retours, branches, blindages et efforts admissibles. |

Les lignes, sources et anomalies restantes sont consultables par identifiant
dans le [rapprochement](L2_RECONCILIATION.json). Le gel du graphe complet et
la réception des terminaisons permanentes, fiches coudées et liaisons
multidrop/coaxiales sur des matériels identifiés restent **À valider**.
