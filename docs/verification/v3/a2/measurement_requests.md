# V3-A.2 — Fiche de relevés des interfaces et ancrages UART

**Exécution physique `NOT_RUN` · 0 révision physique confirmée.**
Cette fiche recueille les entrées manquantes pour une décision d’admission
sur copie puis, après décision distincte, pour un éventuel protocole GO4.
[Matrice des relevés GO3B](../../v21_go3b/interfaces_go4.json)

## Préparer un retour exploitable

- Identifier la configuration, chaque équipement et chaque cordon par fabricant, référence complète, suffixe, révision de carte et identifiant de lot ou de série. Photographier l’étiquette, la sérigraphie et le port dans le même dossier. Si une étiquette est illisible ou inaccessible, conserver la valeur inconnue.
- Pour chaque cote, indiquer le matériel concerné, la face, le sens de vue, les datums, le moyen et sa résolution, la valeur et son incertitude. Dater et signer le relevé au nom de l’opérateur. Joindre des vues orthogonales annotées avec une échelle dans le plan de mesure. Conserver les fichiers bruts et leurs SHA-256. Pour un plan fabricant, fournir l’URL, la révision imprimée, la page ou figure, la date de consultation ainsi que le SHA-256 des octets reçus.
- Cibles de métrologie proposées pour instruire l’incertitude, **À valider avant relevé**. Viser ±0,10 mm pour l’emplacement des faces, sièges et centres de trous, ±0,05 mm pour diamètre et pas de petits connecteurs, ±0,50 mm pour course, passage et longueur, et ±1° pour orientation. Utiliser un comparateur ou un jeu de cales contrôlées pour un jeu de l’ordre de 0,30 mm. Utiliser un projecteur de profil ou une optique étalonnée lorsque les contacts sont inaccessibles au pied à coulisse. Consigner la précision réellement obtenue. Une marge dont l’intervalle d’incertitude atteint zéro reste indéterminée. Ces cibles ne fixent aucune tolérance de montage.
- Réserver l’identification et la continuité aux pièces et cordons dissociés et vérifiés hors tension, suivant le protocole du responsable du matériel. Relever le geste de retrait de la batterie sur gabarit inerte avec ses interfaces et son enveloppe. Les mesures fonctionnelles de niveau, d’isolement et d’énumération USB relèvent d’un protocole ultérieur approuvé sur équipement isolé, sans batterie du drone. Une observation au multimètre peut révéler un pont conducteur et laisse la tenue diélectrique ouverte.

## UART-TOP-001 — Séparation de service W40

- Fournir une photo d’ensemble de l’interface de séparation de la batterie, puis des vues des deux demi-fiches et de leurs détrompeurs. Pointer les pièces et faces portées par la partie mobile et la partie fixe. Relever MPN, numéros de cavité, contacts, verrou, fixation, section des fils et diamètre sur isolant.
- Indiquer quel schéma correspond à la configuration sélectionnée. Le plan W40 décrit un passage par cinq contacts TE, dont trois UART. La boucle de présence TE reste distincte de B− et ses deux voies sont NC côté fixe dans la définition électrique. L’inventaire sans dock porte une déconnexion manuelle de référence et de position inconnues. Le candidat JST JWPF observé dans l’étude de gabarit demande une confirmation propre au montage.
- Pour un cordon détaché, joindre un tableau cavité-à-cavité numéroté depuis les deux faces d’accouplement, avec les trois conducteurs TX, RX et GND brut, les positions NC et la lecture de continuité. Documenter la séquence de service approuvée autour de la coupure, du raccord de puissance protégé et du séparateur de signal, ainsi que la course, le volume de la main et la reprise d’effort. Joindre une vue de la trajectoire sur gabarit inerte et la marge avec les guides.

[Plan W40 et définition des contacts TE](../../../../hardware/electronique/cartographe/cablage_global.json) · [Inventaire sans dock](../../../../hardware/mecanique/cartographe/verification/refonte_faisceaux/inventaire.json) · [Étude JST JWPF](../../../../hardware/mecanique/cartographe/verification/refonte_faisceaux/inventaire_uart_deconnexion.json)

## UART-JBD-001 — J2/J3 et brochage BMS

- Photographier l’étiquette JBD-SP22S003, le suffixe et la révision de la carte, la sérigraphie du port près du connecteur et la fiche face aux cavités. Repérer la broche 1, le verrou et le sens de lecture sur les deux vues. Mesurer au pied à coulisse ou à l’optique le pas, les dimensions guidantes, la profondeur et la course du verrou.
- Demander à Jiabaida la notice ou un erratum rattaché à ce lot, le plan de la paire HY2.0-4P, le brochage par cavité, les niveaux TX/RX et la référence électrique de GND. La notice Li-ion archivée A01 du 19 avril 2022 donne J2 dans la table et J3 dans la remarque. La notice de support A.1 du 20 mai 2022 porte sur la variante LiFePO₄ et désigne J2 dans les deux passages, avec B− comme référence non isolée. L’erratum applicable au lot Li-ion reste à obtenir.
- Fournir le tableau RXD/TXD/GND/VDD du lot et le contrôle de correspondance visuelle et de continuité du seul cordon détaché. Le contrat attend GND relié uniquement au côté TTL isolé, TX JBD vers RX isolateur, RX JBD vers TX isolateur et VDD NC dans le faisceau. Conserver les niveaux inconnus si le fabricant ne les garantit pas. Un protocole ultérieur devra alors préciser le montage de mesure adapté.

[Contrat BMS-UART-CARTO-01](../../../../hardware/electronique/cartographe/contrat_uart_bms.json) · [Notice Li-ion Jiabaida A01, §7.1 p. 14–16](https://cdn-files.myshopline.com/file/store/1720492677212/JBD-SP22S003-Li-ion-A01-2.pdf) · [Notice LiFePO₄ Jiabaida A.1, couverture et §7.1](https://cdn.shopify.com/s/files/1/0606/5199/5298/files/JBD-SP22S003_37ea5c42-0b2f-4c30-bb4a-3ba411fcb66e.pdf?v=1664433389)

## UART-ISO-001 — Variante Waveshare et séparation des retours

- Photographier SKU, étiquette et révision du boîtier, faces TTL et USB-B, bornier, marquage des contacts et commutateur TTL. Obtenir la référence du circuit et de la carte auprès du fabricant ou du fournisseur si le marquage est inaccessible. Demander le plan du boîtier et des fixations, les MPN du bornier et de l’embase USB-B, le schéma de retour et de blindage, ainsi que les spécifications électriques et mécaniques applicables à cette variante.
- Relever, par cavité et vue annotée, TXD, RXD, GND et VCC/+5 V selon marquage. Identifier le type de terminaison, l’axe d’entrée du fil et l’axe d’accès de la vis. Le contrat demande VCC/+5 V NC et la séparation de GND TTL/B− brut d’USB GND, du blindage, de la masse avionique et du châssis. Relever les liens éventuels boîtier–blindage–fixations. Soumettre tout pont constaté à une revue électrique avant admission.
- Le manuel FT232RL V1.3 du 8 novembre 2018 liste TXD/RXD/GND dans le tableau TTL. La page archivée du SKU 15817 sélectionne FT232RNL et liste aussi +5 V. Le catalogue présente également une variante CH343G. Identifier le lot, la population et le marquage du commutateur avant de retenir une définition de câble.

[Manuel Waveshare V1.3, p. 1–3](https://files.waveshare.com/wiki/USB-TO-RS232-485-TTL/manual/USB_TO_RS232_485_TTL_-user-manual-en.pdf) · [Catalogue Waveshare SKU 15817](https://www.waveshare.com/usb-to-rs232-485-ttl.htm?sku=15817)

## UART-AXIS-001 — Repères d’interface indépendants de F40/F41

- Situer les faces TTL et USB-B de l’isolateur, J2/J3 et l’USB-A hôte depuis trois références de corps effectivement mesurables. Pour chaque port, relever séparément la face et sa normale signée, l’interface de l’embase et son détrompage, la fiche accouplée ou la terminaison serrée, puis le point et la tangente signée de sortie du câble. Donner l’origine et les trois axes orientés du repère local, la méthode de construction et le contrôle de report vers le repère parent du cartographe.
- Photographier les états séparé, engagé et entièrement accouplé. Relever le jeu, la profondeur d’engagement et l’accès à l’outil en vues latérales étalonnées. Pour le bornier TTL, distinguer entrée conducteur, position du conducteur sous serrage et accès de l’outil. Pour USB, séparer axe de retrait et sortie du câble après le surmoulage.
- Signer le relevé et l’associer à la référence des deux pièces. Pour le retour CAO, vérifier que le repère sourcé se compose dans le monde XLink indépendamment de `Wire/Start` et `Wire/End`. Les distances de face proxy IF-07 servent de témoins de contrôle numérique.

[Comparaison de la référence GO3B, `cases.baseline.diagnostic`](../../v21_go3b/electrical_evidence.json)

## UART-MOUNT-001 — Appui et surface porteuse de l’isolateur

- Relever les pieds, faces portantes et trous utiles du module, puis les faces candidates et perçages existants de P64/P66, dans les datums du support. Fournir plan coté et photos des deux côtés, avec matière, épaisseur, entraxes, diamètres, zones à exclure, obstacles arrière, enveloppe des vis et de l’outil. Identifier le support réel s’il existe et les références des vis, rondelles, inserts et isolants.
- Indiquer les surfaces réellement jointives, le jeu, la planéité et la profondeur d’engagement des vis. Mesurer l’écart à P72/P73 avec les pièces voisines présentes. La donnée discriminante est l’existence d’une reprise d’effort traçable du boîtier vers la structure, avec maintien de l’isolement près des fixations. Documenter masse et centre de gravité du module équipé, efforts de pose, d’entretien, de vibration et directions applicables. Demander au fabricant les efforts admissibles des pattes et des bornes. L’évaluation de tenue attend les cas de charge et les critères du montage.
- IF-03 a historiquement relevé 0,300 mm entre le module et le support candidat, 109,734 mm³ recoupant P72 et 28,018 mm jusqu’à P66. Les trois valeurs concernent la réservation H03. Les empreintes du relevé devront lier modèle, révision et faces avant toute définition d’une zone de pose.

[GO3B, IF-03 et observations H03](../../v21_go3b/interfaces_review.json)

## UART-ACCESS-001 — Dégagement TTL/USB et rayon utilisable

- Fournir l’outillage réel du bornier TTL et les cordons réels, avec photos de la fiche USB-B, du surmoulage droit ou coudé, de la ferrite et de son emplacement. Relever largeur, hauteur, profondeur, course d’engagement/retrait, position de la sortie fil, rayon disponible, réserve de longueur et volumes nécessaires à l’outil et à la préhension. Localiser les mesures par rapport à la PDB, P72 et P77.
- Demander au fournisseur du cordon ses rayons minimaux statique et dynamique, associés à la référence, au diamètre, au profil et aux conditions de mouvement. Relever sur le gabarit inerte l’amplitude et la trajectoire de retrait du pack, la déflexion aux retenues, la réserve de mou et le rayon minimal observable aux états limitants. Le contrôle numérique doit représenter l’ensemble du geste et les accès voisins retenus dans le protocole, avec continuité aux entrées et sorties.
- IF-04 a observé un recoupement PDB sur neuf volumes TTL de criblage. IF-05 a relevé des effets d’orientation USB-B et un recoupement P72 pour tous les profils à portée 50 mm testés. Les douze routes de criblage IF-06 rencontraient au moins deux obstacles. Les volumes du lot et le geste de service restent à relever.

[GO3B, IF-04 à IF-06](../../v21_go3b/interfaces_review.json) · [Étude F41](../../cartographe_action3_f41.json)

## UART-HOST-001 — Port USB-A Jetson réellement affecté à W41

- Montrer la référence 11072, la révision du PCB et la face avec les deux embases USB-A de la porteuse. Pointer l’embase de W41/B, avec l’autre port USB-A et CAN1 visibles. Distinguer les hôtes USB-A des autres ports de la carte sur le plan du lot. Demander la référence du connecteur et la cote de sa face structurante, le détrompage, le dégagement préconisé et la desserte hôte par révision. Identifier l’alimentation du Jetson et du port VBUS dans la configuration sans dock.
- Identifier le cordon W41/B et relever son enveloppe engagée, son axe de retrait, le déport et la tangente de sortie. Avec F31/CAN1 et F35 représentés, relever la garde pendant l’insertion et le retrait et l’accès au verrou CAN1. Vérifier la cartographie USB et blindage du cordon séparé, puis réserver la confirmation d’énumération sur Jetson à un essai ultérieur prévu au protocole.

[Spécifications Holybro, Jetson Orin NX/Nano Connectors](https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/overview-and-specification) · [Brochage Holybro CAN1/CAN2](https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/ports-pinout) · [Inventaire W41/B](../../v21_connector_inventory.csv)

## UART-GUIDES-001 — Déplacement, appuis et voisinage de P72/P73

- Fournir les plans définitifs ou les relevés de P72/P73, des attaches et de leurs interfaces porteuses. Photographier les appuis, centres de trous, passages, vis côté accès et face opposée, avec P64/P66/PDB et les faisceaux voisins représentés. Identifier ce qui est fixe, réglable par la fixation, élastique ou reconfigurable par changement de pièce. Relever chaque course ou rotation possible dans le repère d’appui, avec ses obstructions, butées et incertitudes.
- Documenter la fonction de chaque guide, les cordons repris, les charges et le chemin d’effort de chaque fixation. Pour tout déplacement envisagé, relever avec CAN1/F31/F35, la puissance et la batterie inerte en place la garde, le passage d’outil, l’accès aux verrous, le risque d’abrasion et les rayons statiques/dynamiques. Conserver le volume balayé de la batterie dissociée et les points fixes des faisceaux avec les photos d’ensemble.
- Le jeu mesuré et les contacts de BRep serviront au criblage d’obstacles. Un domaine mécanique exploitable exige une fixation identifiée, le maintien des fonctions de guidage et des dégagements démontrés sur la plage déclarée.

[DOC-MEC, reconstruction GO3B](../../../architecture/ARCHITECTURE_MECANIQUE.md#cartographe-go3b-reconstruction) · [Reprise mécanique IF-NEXT-01](../../v21_go3b/interfaces_go4.json)
