# Conceptions mécaniques

L'architecture, la BOM et l'état de validation sont tenus dans
[DOC-MEC](../../docs/architecture/ARCHITECTURE_MECANIQUE.md). Ce fichier décrit
uniquement l'organisation locale des artefacts CAO.

Utiliser `hardware/` comme répertoire de travail matériel par défaut. Toute CAO suit cette hiérarchie dans `mecanique/<conception>/` :

- `pieces/fabriquees/` : un document natif par référence, avec son arbre de construction.
- `pieces/commerce/` : un document par équipement acheté ou enveloppe provisoire ; un ensemble acheté peut conserver son détail fabricant interne.
- `sous_assemblages/` : sous-systèmes liés aux pièces par liens externes.
- `assemblages/` : assemblage final lié aux sous-systèmes.
- `sources_fabricants/` : originaux inchangés.
- `exports/` : STL et STEP dérivés, à régénérer après modification.
- `verification/` : contrôles et limites connues.

Les occurrences répétées réutilisent une référence. Sauvegarder et transférer toute l'arborescence pour conserver les liens ; les binaires CAO sont exclus de Git.

Application : [cartographe](cartographe/README.md). La convention pérenne et
l'exigence `MEC-ARC-001` sont définies dans [DOC-MEC](../../docs/architecture/ARCHITECTURE_MECANIQUE.md).
