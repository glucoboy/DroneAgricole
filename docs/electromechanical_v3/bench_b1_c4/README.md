# Banc XLink C4 pour V3 B.1

Le [profil](profile.json) décrit la séquence `c4-move`, `c4-route` admise
sur le banc numérique C4. Le modèle de départ contient l’assemblage
`model/Banc_Interconnexion.FCStd` et la pièce externe
`model/parts/Obstacle.FCStd`. Les deux occurrences d’obstacle gardent leur
définition partagée. Préparer une copie privée des deux fichiers en
conservant leurs chemins relatifs et les empreintes du profil.

Les octets proviennent de la fermeture initiale du [rejeu historique C4](../../verification/v21_fix_c_qualification.json).
Le contrôle de provenance local compare les deux empreintes au champ
`closure_sha256` de
`.runtime/fix-c/.runtime/q4-relocation-final/run/setup-oyUBCB/baseline/prepared.json`.
Le reçu historique `.runtime/fix-c/.runtime/q4-relocation-final/evidence.json`
porte le SHA-256 `9f85607ce91e963f7c02a2b0e05d0dad6dc37d1ef5489e4550126b8b9bb7e8c6`.

Le [graphe](graph.json) relie les occurrences, les repères, les contacts,
le chemin de câble et les volumes de service. Son empreinte et celles de
ses sources sont reprises dans le profil. L’[autorité du banc](interface_authority.json)
donne les repères et la continuité sur quatre conducteurs et huit paires de
contacts. Les [critères historiques](criteria.json) fixent les tangentes
signées, un rayon de 5 mm et un dégagement de service de 2 mm. La section
unitaire de 0,2 mm² est une donnée synthétique du modèle L2 du C4.

Le témoin de départ présente un recouvrement volumique entre le câble
et l’obstacle de service. La réimplantation prévue translate de 12 mm
l’équipement B et ses deux volumes de service et redéfinit le chemin du
cordon. Le résultat s’évalue dans une réouverture indépendante de la
fermeture sauvegardée. La recette L5 et les sorties B.1 figurent dans
les [preuves de campagne](../../verification/v3/b1/REPORT.md).
