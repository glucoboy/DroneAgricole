# Collecte des interfaces UART du cartographe

Le dossier concerne le prototype sans dock. Vérifier le lot, l’occurrence
et l’état hors tension avec le responsable matériel avant le relevé. Les
preuves existantes et les champs à acquérir figurent dans la
[matrice des mesures](lot_and_measurement_matrix.json).

| Ordre | Relevé à effectuer | Pièces de preuve |
| --- | --- | --- |
| 1 | Identifier JBD, Waveshare, Holybro et les cordons W40/F40 et W41/F41. Distinguer J2/J3, le suffixe et la chimie du BMS, FT232RL/RNL/CH343G et le port USB-A W41/B effectivement utilisé. | Photos d’ensemble, des deux faces, étiquettes et marquages, MPN, variante, révision et lot. Pour W40, identifier la séparation TE cinq voies ou manuelle. Enregistrer la cavité 1, les NC et la continuité des seuls cordons totalement détachés et vérifiés hors tension. |
| 2 | Référencer l’appui de l’isolateur et le porteur P64 ou P66 effectivement accessible. Identifier P72/P73 si leurs appuis ou fixations sont concernés. | Deux datums indépendants, matière, épaisseur, trous, vis et engagement utile, accès d’outil et trajet des efforts. Rattacher les critères de tenue à leur source applicable. |
| 3 | Relever les embases TTL/USB et les fiches engagées à leurs occurrences. Inclure le montage complet et la dépose. | Trièdres distincts, normales, sens de retrait, sortie du fil, surmoulage, ferrite, gabarit de l’outil et gardes avec PDB, CAN1, F31/F35 et P72/P73. |
| 4 | Suivre la course du gabarit batterie inerte. | Positions extrêmes et limitantes, volumes balayés, retenues, longueur libre, accès et rayons disponibles. Joindre les limites statiques et dynamiques applicables au cordon identifié. |

Pour chaque cote, renseigner la méthode, l’instrument, la résolution, la
valeur, l’unité, l’incertitude et le sens de comparaison avec la tolérance.
Indiquer le document applicable au lot, sa révision et l’emplacement de
la tolérance. Donner l’auteur et la date ISO 8601 avec fuseau. Pour les
repères XLink, indiquer le parent, l’origine, deux directions non
colinéaires et le signe de la normale. Renseigner les matrices rigides
4×4 rangées par ligne, en millimètres pour la translation, dans les deux
sens entre le datum et son parent.

Utiliser le [CSV vierge](measurement_form.csv) pour préparer les groupes
de mesures puis renseigner le [paquet JSON](measurement_form.json) sur
une copie privée. Le [schéma](measurement_form.schema.json) reprend le
format de l’import A.4. Une photo montre l’orientation et l’échelle dans
le plan du relevé. Conserver les originaux et les vues annotées séparément
dans le dépôt privé du responsable, avec chemins relatifs et SHA-256.

Le responsable fournit séparément la politique d’import et son empreinte.
Un résultat compatible est `PENDING_AUTHORIZED_REVIEW`. Le paquet vierge
garde `NOT_RUN`. Une décision applicable relève ensuite du
[protocole de revue](review_protocol.md).
