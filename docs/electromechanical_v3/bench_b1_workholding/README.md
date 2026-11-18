# Banc B.1 avec platines et définition partagée

Ce banc reprend la connectique synthétique C4 et ajoute une fermeture de
trois documents, une paire d’occurrences d’une même définition externe,
un repère parent tourné et une chaîne d’appui complète. Les deux variantes
positives déplacent la même occurrence selon deux poses différentes,
reconstruisent le faisceau, déplacent la platine existante et instancient
une platine percée. Le [profil scellé](profile.json) décrit aussi les cas
de collision, de rayon insuffisant, de points dupliqués et d’appui flottant.

La [recette B.1](../../verification/v3/b1/REPORT.md) utilise les natifs
versionnés dans `model/`. Le générateur `make_v3_b1_fixture.py` permet de
refaire la fixture sous `.runtime/` avec FreeCAD Python. Les fichiers
générés à une autre date ont leurs propres empreintes d’archive. La
description du banc est produite par `describe_v3_b1_fixture.py` et son
SHA-256 est épinglé par l’évaluateur avant admission.
