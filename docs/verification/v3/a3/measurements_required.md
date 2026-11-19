# Relevés d’autorité V3-A.3

`LOT_NOT_INSPECTED`. Utiliser [le formulaire JSON](measurement_form.json) pour conserver le triplet occurrence, identité du lot et observation. Le [CSV](measurement_form.csv) sert à la saisie au poste, avec une ligne par cote, vue ou contrôle. Reporter les lignes CSV dans le dossier JSON en gardant les fichiers bruts hors Git.

## Collecte minimale discriminante

| Ordre | Observation et pièces à préparer | Vues et datums | Mesure discriminante et conséquence |
|---|---|---|---|
| 1 | JBD, isolateur, séparation W40 et paire de contacts associée | Photo d’ensemble cassette/partie fixe, chaque étiquette et sérigraphie. Vue normale à chaque face, verrou vers le haut, broche 1 et sens gauche-droite indiqués. | Identifier chimie/révision, J2 ou J3, FT232RL/RNL ou CH343G, choix TE ou manuel. Relever pas, cavités, position des NC et continuité du seul cordon détaché. Éliminer immédiatement toute variante incompatible. |
| 2 | Boîtier isolateur, P64, P66, P72, P73 et visserie réellement retenue | Deux faces de chaque porteur et vue en contexte avec PDB. Fixer l’origine au centre d’un trou identifié, +X vers un second centre et +Z selon la normale sortante. Pour un porteur sans deux trous, justifier un datum équivalent par plans d’appui. | Relever entraxes, diamètres, épaisseur disponible, jeu, engagement utile à l’exclusion de la pointe et des rondelles, vis/outils, matériau, chemin d’effort et séparation électrique. Choisir si un ancrage P64 ou P66 mérite une première hypothèse. |
| 3 | Ports TTL/USB-B de l’isolateur, W41 et porteuse Holybro 11072 avec CAN1 | Photos porteuse révision et port W41/B pointé, fiche séparée/engagée, vue outil TTL, profils droit et latéral du surmoulage/ferrite, repère local lié au boîtier. | Mesurer l'embase, la fiche engagée, la sortie du fil, le passage de l’outil et la course séparément. Relever la garde dans le geste avec PDB, P72/P73 et le verrou CAN1 en place. |
| 4 | Gabarit batterie inerte, retenues et cordons identifiés, voisins F31/F35 | Vues d’ensemble axiale puis latérale de l’entrée, de la course et des états limitants, règle dans le plan de la cote. Identifier les points fixes et les pièces déplacées ensemble. | Relever course, volumes balayés, longueur libre, rayon disponible et position de la ferrite. Rapprocher les rayons statique et dynamique des documents du cordon identifié. Vérifier accès CAN1 et garde F31/F35 sur la course. |

Les photos gardent une échelle dans le plan mesuré et un repère d’orientation. Pour les embases, fiches, fils et outils, établir des trièdres droits séparés et consigner leur transformation vers le parent CAO. Les axes F40/F41 décrivent les chemins nominaux. Relever au minimum l’origine, deux axes non colinéaires, la normale et le signe de retrait.

Les observations 1 à 3 conditionnent l’instruction d’un **premier support isolateur**. L’observation 4 conditionne son impact sur le retrait de la batterie et le routage, même si le support est fixe. Une preuve d’ancrage comprend aussi les cas de charge et leurs critères applicables. Si le porteur, le geste ou l’identité restent ambigus, garder la ligne bloquée et conserver le relevé incomplet. Les huit demandes détaillées d’A.2 restent applicables. [Fiche A.2](../a2/measurement_requests.md)

## Hors tension

Suivre la procédure de mise en sécurité du responsable matériel. Examiner les pièces libres, gabarits inertes et cordons entièrement séparés de tout équipement et vérifiés hors tension. La continuité au multimètre est réservée aux cordons totalement détachés et permet de renseigner les correspondances cavité à cavité. Documenter toute impossibilité de dissociation et suspendre le contrôle concerné. Un BMS raccordé au pack reste hors périmètre des mesures. Toute mise sous tension, énumération USB, mesure de niveau ou essai diélectrique requiert un protocole distinct approuvé.

Pour chaque résultat, renseigner fabricant, MPN, variante, révision et lot/série, méthode, instrument et résolution, unité, tolérance applicable et sa source, incertitude obtenue, date, datums, sens de vue, identité et attestation de l’opérateur. Associer une photo et le fichier brut par chemin et SHA-256. Une observation sans auteur, lot, tolérance applicable ou donnée brute conserve `INCONCLUSIVE`. [Matrice des occurrences](operation_admission.json)
