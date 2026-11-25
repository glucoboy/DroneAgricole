# Collecte opérateur V3-A.4

Suivre la procédure du responsable matériel. Préparer les pièces isolées, les
cordons entièrement détachés et vérifiés hors tension, et le gabarit batterie
inerte. Réserver tout contrôle électrique sous énergie, toute connexion USB
active et tout essai diélectrique à leur protocole séparé et approuvé.

| Ordre | Lot et issues | Livrable minimal |
| --- | --- | --- |
| 1 | Identité et connectique · UART-TOP-001, UART-JBD-001, UART-ISO-001, UART-HOST-001 | Une vue d'ensemble et une vue de chaque étiquette/sérigraphie JBD, Waveshare et Holybro. Identifier MPN, révision, lot, J2/J3, marquage du bornier, port USB-A retenu et cavité 1. Photographier les deux faces de W40/W41 et la jonction TE ou manuelle. Cartographier chaque cavité, y compris NC, sur les seuls cordons détachés et vérifiés hors tension. |
| 2 | Ancrage · UART-MOUNT-001, UART-GUIDES-001 | Commencer par le porteur P64 ou P66 effectivement accessible. Identifier l'appui de l'isolateur, deux datums indépendants, perçages, matière, épaisseur, vis et insert, engagement utile, accès de l'outil et trajet des efforts. Relever P72/P73 lorsqu'ils sont concernés. Identifier la source des efforts et critères acceptables. |
| 3 | Ports et sorties · UART-AXIS-001, UART-ACCESS-001, UART-HOST-001 | Prendre séparément les vues de l'embase, de la fiche engagée et de la sortie du cordon. Consigner trièdre, normale, sens de retrait, passage de l'outil TTL, surmoulage et ferrite USB, avec PDB, CAN1, F31/F35 et P72/P73 en place. |
| 4 | Service batterie · UART-TOP-001, UART-ACCESS-001, UART-GUIDES-001 | Photographier entrée, fin et états limitants de la course du gabarit inerte. Relever volumes balayés, retenues, longueur libre, angles et rayon disponible. Rattacher les limites de cintrage statique et dynamique à la référence du cordon effectivement retenu. |

Réutiliser les observations signées déjà applicables au même lot et au même
datum, puis ajouter les états et champs manquants. Un axe CAO F40/F41 sert de
référence d'itinéraire nominal et les datums d'accouplement sont relevés sur les
faces indépendantes. Montrer l'origine, deux directions non colinéaires et le
signe de la normale. Renseigner les transformations rigides XYZ en millimètres,
matrices 4×4 rangées par ligne, dans les deux sens entre datum et parent XLink.

Pour chaque cote, joindre valeur et unité, résolution et instrument, méthode,
incertitude, tolérance et sens de comparaison, document et emplacement de la
tolérance, datum, orientation, auteur, date et identité du lot. Utiliser une
date ISO 8601 avec fuseau. La photo en contexte montre le repère et une échelle
dans le plan de mesure. Les photos et les fichiers bruts restent dans le dépôt
privé sous `.runtime/v3-a4/releves/<lot>/<issue>/`. Conserver les originaux,
identifier les vues annotées séparément et référencer chemins relatifs et
SHA-256. Utiliser un identifiant d'opérateur convenu avec le responsable
matériel.

Démarrer avec le [CSV](measurement_form.csv), puis transcrire les lignes et les
références dans le [paquet JSON](measurement_form.json). La configuration de
revue et son empreinte viennent du responsable hors du dépôt des relevés. Un
résultat numérique compatible passe en attente de revue habilitée. La décision
d'autorité requiert un enregistrement authentifié portant exactement le lot,
l'occurrence et l'opération. Les vérifications de réception s'ajoutent ensuite.
[Schéma](measurement_form.schema.json) · [Exemple sans autorité](example_not_authority.json)
