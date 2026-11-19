# Relevés nécessaires à la reprise V3-D

Reporter chaque observation dans le [formulaire A.3 à signer](../a3/measurement_form.json)
ou dans la [grille de saisie](../a3/measurement_form.csv). La
[fiche opérateur hors tension](../a3/measurements_required.md) définit les
vues, instruments, datums, pièces à préparer et champs de provenance.
Utiliser les identifiants exacts de la [matrice par occurrence](admission.json).

| Opération envisagée | Preuve minimale à rattacher à l’occurrence |
|---|---|
| Poser l’isolateur ou créer son support | Identité du lot, repères d’accouplement séparés, datums du porteur et de l’isolateur, engagement utile des fixations, chemin d’effort et volumes d’accès avec CAN1 en place. |
| Reprendre F40 | Références JBD et isolateur, identification J2/J3 et de la séparation batterie, continuité du cordon détaché, départs orientés, longueur libre et rayons applicables au geste. |
| Reprendre F41 | Références des ports USB-B et hôte réellement retenus, fiches accouplées, surmoulage, sortie de fil, passage de l’outil, garde CAN1/F31/F35 et course de retrait. |
| Déplacer P72/P73 ou intervenir sur les retenues | Cotes et datums de porteur, gorge effectivement engagée, fixations, chemin d’effort et gabarit batterie inerte sur la course complète. |
| Changer variante de connecteur ou topologie | Applicabilité et preuves électriques par lot, puis capacité moteur et autorité spécifiques pour l’opération. |

La collecte initiale porte l’identification des pièces, les appuis, les
interfaces TTL/USB et le geste batterie. Pour le premier essai numérique,
préparer le dossier du support isolateur au titre de `CREATE_SUPPORT(iso)`.
La décision de reprise exige un relevé applicable signé, un domaine borné
et un reçu L5 par occurrence et opération. La matrice d’autorité A.3
conserve les contraintes de séparation, NC, brochage, protection et service.
