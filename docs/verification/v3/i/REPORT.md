# V3-I — Rejeu des preuves d’intégration

[Résultat et périmètre dans DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-i) ·
[Parents, sources, écarts et résolutions](merge_manifest.json) ·
[Matrice des portées](scope_matrix.json) · [Reçu](acceptance.json)

Les commandes et leurs codes de sortie figurent dans [la matrice de
régression](regressions.json). Les chemins d’artefacts y sont relatifs à la
racine du dépôt. Sous Windows amd64, utiliser les outils indiqués dans cette
matrice. Les résultats sous `.runtime/v3-i` sont locaux. Un rejeu utilise un
nouveau répertoire et produit ses propres journaux et archives FreeCAD.

1. Extraire le commit de fusion indiqué dans le manifeste et suivre les
   [recettes A.1](../a1/REPORT.md) et [B.1](../b1/REPORT.md) de compilation.
   Rejouer le filtre CTest et conserver les traces d’admission. Les gardes
   de chemins demandent la création de liens physiques et de jonctions sur
   copies temporaires Windows. Examiner les états détaillés des traces.
2. Exécuter les deux scripts B.1 avec les profils versionnés et le T0 de la
   matrice. Les sorties `replay.json` et `checks.json` indexent les cas. Les
   rapports `t0-crosscheck.json` et les natifs sont sous chaque transaction.
3. Appliquer la [recette A.2](../a2/REPORT.md) aux copies historiques scellées.
   Utiliser le build V3-I pour le test d’intégrité A.2, puis passer le dossier
   d’intégrité au test `test_v3_i_scope.py`. Celui-ci conserve les demandes et
   reçus de refus dans le dossier de sortie. Pour le rejeu natif, préparer les
   archives GO3B aux empreintes publiées et examiner `measurements.json`.
4. Comparer les fermetures et autorités des trois bancs dans deux extractions
   Git du même commit. Comparer chaque fichier à l’empreinte du profil ou du
   sceau. Pour L2 et Q1 historiques, employer les témoins byte-exacts décrits
   par A.1 et B.1. Conserver le manifeste mécanique actif à son empreinte LF.
