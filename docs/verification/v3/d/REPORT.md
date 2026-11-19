# V3-D — Rejouer le diagnostic cartographe en lecture seule

[Résultat dans DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-d) ·
[Admission par opération](admission.json) · [Acceptation](acceptance.json)

Partir du commit de fusion indiqué dans le reçu. Vérifier ses deux parents
et les empreintes des preuves C et A.3. La portée opérationnelle du cartographe
provient de la [matrice A.3](../a3/operation_admission.json). Les résultats
de V3-C établissent la qualification du moteur sur banc.

Dans un nouveau dossier privé, exécuter les commandes de
[régression](regressions.json). `test_v3_a3_authorities.py` vérifie les trois
analyses d’impact et les refus, avec les 142 fichiers du gel V3-A comme
référence. `v3_a2_native` rouvre la référence et les témoins GO3B identifiés
aux empreintes de leurs manifestes. Suivre la [recette A.2](../a2/REPORT.md)
pour préparer les témoins historiques depuis les archives disponibles.
La [recette A.3](../a3/REPORT.md) précise le criblage des gabarits TTL/USB-B
et des parcours temporaires F40/F41. Avec FreeCAD Python, affecter
`PYTHONPATH` à la racine du dépôt pour l’appel direct du script de criblage.

`recheck_v3_d_legacy.py` liste les sept paires rejetées de la couverture
V2.1 B.2, stage la fermeture V3-A, puis lance un inventaire et une mesure
dans des processus FreeCAD distincts. La comparaison conserve les critères
du gel historique. Le [reçu des paires](legacy_pair_comparison.json)
indique la couverture nouvelle et la portée des autres chiffres historiques.
Les [fermetures](native_closures.json) et les
[sources](cad_source_manifest.json) permettent de rattacher l’observation
au bon assemblage et de vérifier l’absence de sauvegarde.

Les dossiers `.runtime/v3-d` contiennent des copies de lecture et des
preuves brutes privées. La recette les régénère à partir des sources et
témoins scellés. Le dossier [de préparation](problem_spec.json) conserve
les inconnues et la frontière d’admission. La [fiche de reprise](measurement_actions.md)
relie les relevés aux futures opérations.
