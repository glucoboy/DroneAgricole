# High Level Design — système Drone Agricole

| Champ | Valeur |
|---|---|
| Référence | `DOC-HLD` |
| Nature | document vivant |
| Dernière mise à jour | 24 septembre 2026 |
| Statut | architecture système préliminaire ; capacités qualifiées indiquées explicitement |

## 1. Objet et périmètre

Le système vise la cartographie puis le traitement ciblé de vignobles à forte
pente, en terrasses ou à géométrie irrégulière. Il comprend deux aéronefs
complémentaires, une station de mission, une infrastructure de positionnement et
les moyens de simulation, de banc et de validation.

- Le **drone cartographe** acquiert LiDAR, images, IMU et GNSS, puis produit un
  paquet d'acquisition traçable.
- La **station de mission** contrôle la qualité des acquisitions, construit et
  fait approuver une carte, prépare les missions, lance les simulations,
  transfère les paquets et compile les résultats.
- Le **drone de traitement** exploite la carte approuvée et sa perception locale
  pour naviguer et appliquer un traitement latéral ciblé.
- Les deux drones ont un fonctionnement nominal **AUTO** embarqué et un mode
  **MANU** de reprise opérateur. QGroundControl assure le suivi du vol ; la
  station Qt prépare et exploite les produits métier.
- **PX4** conserve le vol critique ; **ROS 2** fournit les fonctions avancées et
  des consignes de haut niveau que PX4 peut refuser.

La première phase couvre la simulation, le banc, la cartographie et la
préparation progressive du traitement. Toute pulvérisation suit l'ordre :
simulation, banc, eau/traceur, puis seulement produits autorisés avec protocole
validé.

Le cas d'usage initial précisé le 16 septembre 2026 est celui des coteaux de
Cornas : parcelles en pente, quelques arbres et surfaces à traiter jusqu'à
5 ha. Cette cible opérationnelle ne fixe ni la distance radio maximale, ni
l'autonomie en une sortie, ni une couverture radio garantie. La géométrie des
parcelles, le relief et la position de l'opérateur servent au dimensionnement.

## 2. Vue d'ensemble

```text
 Base RTK locale                         Station de mission Qt 6
 corrections/repère                     cartes, missions, essais, rapports
        |                                          ^        |
        v                                          |        v
 Drone cartographe ---------------- acquisition ---+   paquet de mission
 PX4 + compagnon ROS 2                                      |
 LiDAR + RGB + IMU + GNSS                                   v
                                                    Drone de traitement
                                                    PX4 + compagnon ROS 2
                                                    perception + bras + fluide
                                                             |
                                                             v
                                                    retour et rapport de mission
```

Les quatre descriptions de référence se répartissent ainsi : ce document porte
le système et les scénarios ; `DOC-SW`, `DOC-MEC` et `DOC-ELEC` portent les
détails de leur domaine.

## 3. Responsabilités des sous-systèmes

| Sous-système | Responsabilité principale | État au 10 septembre 2026 |
|---|---|---|
| Drone cartographe | acquisition synchronisée et géoréférencée de la parcelle | matériel et qualification **À valider** ; CAO et chaîne d'essai implémentées partiellement |
| Station de mission | cycle hors vol, simulation, exploitation des acquisitions et résultats | socle C++17/Qt 6 implémenté ; simulation et cartographie d'essai opérationnelles préliminaires |
| Drone de traitement | navigation locale, déploiement du bras et application ciblée | planifié |
| Base RTK locale | référence géodésique et corrections sans abonnement | architecture candidate **À valider** |
| Bancs et simulation | validation reproductible avant essais physiques | bancs logiciels disponibles ; banc matériel **À valider** |

## 4. Scénario opérationnel nominal

### 4.1 Préparer

1. L'opérateur sélectionne la parcelle, la configuration matérielle et les
   versions logicielles.
2. La base RTK et les liaisons sont établies ; repère, position d'antenne et
   hauteur sont enregistrés.
3. PX4 réalise ses contrôles de vol. ROS 2 vérifie capteurs, temps, stockage et
   capacité de calcul sans se substituer aux sécurités PX4.

### 4.2 Cartographier

1. Le cartographe exécute en AUTO une trajectoire de couverture de la surface
   prédéfinie, chargée et validée avant le départ ; PX4 contrôle le vol.
2. Le compagnon enregistre les flux bruts, calibrations, diagnostics et
   identifiants de configuration.
3. Une perte de qualité critique interrompt l'acquisition utile et déclenche le
   comportement de mission prévu ; la décision de vol reste chez PX4.
4. Les données reviennent sous forme d'un paquet d'acquisition vérifiable.

L'espacement des lignes tient compte de l'empreinte utile des capteurs,
du champ de vue de l'optique, de l'orientation, de la hauteur locale au-dessus
du terrain et du recouvrement demandé. Pour une caméra verticale sur terrain
plan, le repère géométrique est
`largeur = 2 × hauteur × tan(champ transversal / 2)`, puis
`espacement = largeur × (1 − recouvrement latéral)`.
Ce calcul ne qualifie ni la densité LiDAR ni le recouvrement réel en pente.
La cadence d'acquisition et la vitesse déterminent aussi le recouvrement
longitudinal. À Cornas, relief, arbres et ruptures imposent une vérification
de la couverture et des dégagements ; altitude constante par rapport au
départ et hauteur constante au-dessus du terrain ne sont pas équivalentes.

Une mission de couverture préchargée dans PX4 est la voie candidate pour un
balayage prédéfini. Si l'adaptation de trajectoire exige Offboard, les consignes
proviennent du compagnon **embarqué**, jamais d'un flux permanent du PC sol.
La répartition finale Mission/Offboard et le suivi de terrain sont **À valider**.
QGroundControl dispose d'un motif
[Survey](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/plan_view/pattern_survey.html) ;
son usage ne démontre pas la compatibilité de notre caméra, du LiDAR ou de
notre traitement du relief.

### 4.3 Construire et approuver la carte

1. La station importe et contrôle l'intégrité du paquet.
2. Les adaptateurs normalisent les données ; localisation, accumulation 3D,
   colorisation, surface et détection des rangs sont exécutées selon une
   configuration traçable.
3. L'opérateur examine les zones inconnues, obstacles, fils, dégagements et
   indicateurs de qualité.
4. Une carte approuvée devient immuable. Toute correction crée une nouvelle
   version candidate. La preuve d'approbation lie au minimum l'identité de
   l'approbateur, la version du manifeste et l'empreinte du contenu ; signature
   cryptographique et magasin de confiance restent **À valider**.

### 4.4 Préparer et simuler le traitement

1. La station produit des corridors, trajectoires et prescriptions à partir
   d'une carte compatible.
2. La mission est simulée avec les volumes de collision et limites connus.
3. Les portes de validation bloquent tout transfert si carte, configuration,
   trajectoire ou sûreté ne sont pas compatibles.

### 4.5 Exécuter et rendre compte

1. Le drone de traitement reçoit un paquet approuvé et vérifie manifeste,
   empreintes, compatibilité de version, cible et accusé de réception.
2. ROS 2 planifie et fournit les consignes ; PX4 contrôle et protège le vol.
3. Les vannes ne peuvent être ouvertes que dans l'état de traitement autorisé,
   avec localisation, corridor, bras et actionneurs valides.
4. Les données de retour sont compilées en rapport de mission avec couverture,
   événements, quantités appliquées et écarts.

Ce dernier parcours reste planifié ; il ne doit pas être présenté comme une
capacité opérationnelle actuelle.

### 4.6 Modes opérateur et supervision

| Mode | Comportement attendu |
|---|---|
| AUTO | exécution embarquée de la mission cartographique ou de traitement ; station sol et radiocommande ne fournissent pas les consignes indispensables à chaque instant |
| MANU | reprise volontaire avec la radiocommande ; PX4 conserve stabilisation et protections ; le mode PX4 assisté exact reste **À valider** |

AUTO et MANU sont les deux modes présentés à l'opérateur, pas la liste complète
des états internes PX4 : attente, retour, atterrissage et failsafes restent
nécessaires. Une reprise valide est prioritaire sur les consignes de mission.
Le retour en AUTO est une action explicite, avec vérification de la mission et
de son point de reprise. Une reconnexion radio seule ne provoque ni reprise
MANU, ni réarmement, ni reprise du traitement ; la commande et son intention
doivent être réévaluées pour éviter un basculement dû à un interrupteur resté
dans une ancienne position. À la reprise MANU du drone de traitement,
l'application de produit est inhibée ; les essais de traitement restent soumis
aux portes de DOC-VAL.

QGroundControl prépare/supervise le vol : état, position, progression,
énergie, alarmes et demandes d'interruption. Sa fermeture ne supprime pas
l'exécution embarquée ni la commande physique de la radiocommande tant que
la liaison RF fonctionne. Le suivi en direct exige néanmoins une liaison
active ; les données périmées sont signalées et les journaux restent à bord.

### 4.7 Perte de liaison selon le mode

| Événement | AUTO | MANU |
|---|---|---|
| perte de commande RC seule | poursuivre la mission si les conditions embarquées restent valides ; signaler la perte | appliquer le repli PX4 prédéfini ; ne pas conserver indéfiniment la dernière commande |
| perte du PC/QGroundControl ou du lien local PC-radio | poursuivre sous les mêmes conditions ; suivi sol indisponible | commande physique maintenue si la liaison RF demeure valide |
| perte RF commune RC + MAVLink | poursuivre sous les mêmes conditions ; reprise manuelle et suivi sol indisponibles | repli PX4 prédéfini |
| perte de navigation, énergie critique ou consignes Offboard embarquées | réaction propre au défaut, prioritaire sur la poursuite de mission | réaction propre au défaut sous autorité PX4 |

La poursuite en AUTO est le comportement cible **Planifié**, conditionné à une
mission valide, une navigation suffisante, l'énergie, la géofence et les gardes
embarquées ; elle n'autorise pas une poursuite aveugle à tout défaut. Les
conditions métier du traitement restent applicables sans liaison sol.
Si des corrections RTK utilisent le même RF, la coupure peut aussi dégrader la
localisation : cette conséquence doit être évaluée séparément.

Les délais, limites de perte admissibles, choix du repli et paramètres PX4
restent **À valider** en simulation puis sur cible. Les exceptions de perte RC,
de perte GCS et de perte Offboard sont distinctes dans
[PX4](https://docs.px4.io/main/en/config/safety).
Les réglages du banc headless ne sont pas transférables tels quels au drone.

## 5. Frontières de sûreté

| Autorité | Fonctions |
|---|---|
| PX4 / contrôleur de vol | estimation primaire de vol, attitude, position, mixage, moteurs, armement, géofence et failsafes |
| ROS 2 / compagnon | perception, cartographie, localisation avancée, planification, mission applicative, bras, traitement et journalisation |
| Station / opérateur | préparation, revue, approbation, transfert et suivi ; aucune boucle critique de stabilisation |
| QGroundControl / opérateur de vol | préparation et supervision du vol, armement, alarmes et interruption |

Principes non négociables :

- ROS 2 ne commande pas directement les moteurs.
- Une perte du compagnon laisse PX4 appliquer un comportement sûr configuré.
- Après chargement et validation de leur mission, les deux drones exécutent
  l'AUTO sans connexion permanente à la station ; une perte de liaison suit
  la politique du §4.7, sous autorité PX4.
- Une donnée absente ou périmée n'est jamais remplacée par une valeur inventée.
- Les fils de palissage et zones inconnues sont des dangers ; leur franchissement
  ne dépend pas d'un capteur unique.
- En cas de défaut de traitement, fermeture du produit avant les autres actions
  de mission.

## 6. Informations échangées

| Information | Producteur | Consommateur | Contrôle attendu |
|---|---|---|---|
| Acquisition capteurs | drone cartographe | station | manifeste, horodatage, calibration, empreintes |
| Carte candidate/approuvée | station | opérateur puis drone de traitement | version, repère, qualité, compatibilité, approbation |
| Mission de cartographie | préparation sol | cartographe | surface, relief de référence, couverture, contraintes, validation et accusé de réception |
| Mission de traitement | station | drone de traitement | carte liée, contraintes, prescription, expiration |
| Consignes de trajectoire | ROS 2 embarqué | PX4 | fraîcheur, limites, état Offboard, refus possible |
| État de vol | PX4 | ROS 2 et station | qualité, mode, armement, failsafes |
| Rapport de mission | drone puis station | opérateur | configuration, événements, couverture et résultat |

Les formats métier définitifs, le mécanisme de signature et le transport sont
**À valider**. Un transfert n'est jamais considéré terminé sans contrôle du
manifeste et accusé de réception de la cible.

## 7. Déploiement

- Développement : Windows 11, WSL2 et Docker.
- Station : application desktop C++17 / Qt 6 Widgets et outils headless communs.
- Compagnon cartographe cible : Jetson Orin NX 16 Go sur porteuse Holybro Pixhawk Jetson Baseboard, avec JetPack et conteneurs `arm64` ; intégration et exécution sur cible **À valider**.
- Simulation et calcul : images reproductibles `amd64` et `arm64` lorsque les
  dépendances le permettent.
- Contrôle de vol : module Pixhawk 6X dédié exécutant PX4, distinct du module
  Jetson Orin NX mais monté sur la même porteuse ; autorité de vol séparée.

Les versions finales de ROS 2, JetPack, PX4, DDS et des calculateurs embarqués
restent décrites dans les documents de domaine et soumises aux preuves de
qualification de `DOC-VAL`.

### 7.1 Budget matériel de travail

L'enveloppe cartographe + base RTK locale était estimée entre 5 450 et 7 800 EUR
TTC, avec un point de travail proche de 6 500 EUR, hors tablette/PC,
main-d'œuvre et qualification. Elle inclut capteurs, calcul, RTK, plateforme,
deux batteries, chargeur, RC/télémétrie, supports, alimentation et câbles. Ce
n'est ni un devis ni une autorisation d'achat ; elle n'intègre pas encore la
porteuse commune ni l'Orin NX 16 Go. Coût, disponibilité, fiscalité et
compatibilité restent **À valider**.

La cible cartographe étudiée associe un X650, la **Holybro Pixhawk Jetson
Baseboard**, un **Pixhawk 6X module seul** et un **Jetson Orin NX 16 Go**.
La porteuse commune réduit les interfaces mécaniques et les câbles entre
contrôleur de vol et compagnon ; le Pixhawk conserve son autorité de vol
indépendamment du logiciel Jetson. Révisions matérielles, encombrement,
thermique et disponibilité restent **À valider**. La CAO actuelle représente
encore un kit Orin Nano et une base Pixhawk v2A distincts. Le GNSS embarqué reste
à choisir entre une intégration DroneCAN de classe H-RTK et une solution
ArduSimple adaptée. La cible d'intégration devient une **liaison RF commune**
à la commande manuelle et à MAVLink/QGroundControl (§4.6–4.7), pour réduire
les modules, antennes et besoins d'alimentation. Elle remplace la présélection
antérieure de deux radios distinctes ; celles-ci restent une solution de repli.
La perte commune est assumée comme hypothèse d'architecture, sans prétendre
à une redondance de liaison. La présélection Pocket ELRS EU-LBT + RP4TD en
mode MAVLink, les alternatives et les limites sont portées par
[DOC-ELEC §7.4](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#74-liaison-rf-commune-rc-et-mavlink).
Aucun choix de matériel ou de firmware n'est **Qualifié**.

La carte avionique commune **CA01** est **Planifiée** pour regrouper RP4TD,
conversions de charge utile et adaptation de synchronisation. La cible retenue
le 22 septembre 2026 utilise un **PM08-CAN fixé au châssis, près de la
distribution**, hors CA01 et hors cassette batterie. Il remplace le PM02D de
la définition précédente : batterie → PM08-CAN → toutes les branches, pour
la mesure globale. Les courants admissibles, protections et la couverture de
mesure restent **À valider** sur la configuration réelle.

Le **BEC1 du PM08-CAN** alimente **POWER1** et le **BEC2** alimente
**POWER2** du Pixhawk 6X monté sur la porteuse, par deux chemins distincts.
La mesure batterie passe séparément par **DroneCAN vers CAN1**. Ces entrées
forment une redondance candidate au niveau de l'alimentation du contrôleur ;
la batterie et le PM08-CAN restent des causes de défaillance communes.
Brochage de la nouvelle porteuse, isolation entre rails, budgets et comportement
en défaut sont **À valider** selon [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md).

**CA01 conserve un rail local 5 V protégé** depuis un départ batterie aval du
PM08-CAN pour la radio, les auxiliaires et la synchronisation. La radio reste
indépendante de l'alimentation du Jetson. La porteuse Jetson reçoit un rail
**12 V candidat via son entrée XT30** ; l'alimentation 12 V du LiDAR et les
adaptations de synchronisation restent à dimensionner. Aucun courant propulsion
ne traverse CA01. La sélectivité des protections, les budgets de courant et
la tenue thermique restent **À valider**. Gazebo avec modèles identifiés peut
estimer la demande en mission ; la tenue électrique et thermique doit être
confrontée au banc.
Le cahier des charges et le câblage cible sont portés par
[DOC-ELEC §4.2](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#42-cahier-des-charges-de-la-carte-avionique-commune-ca01)
et [§4.3](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#43-câblage-global-du-cartographe).

Cette évolution définit la cible ; **les circuits internes KiCad V0.3 et la
CAO SA03/SA04 ne sont pas migrés**. Le schéma CA01 existant ne démontre pas
encore le rail 5 V local protégé ni les nouvelles interfaces. La CAO conserve
l'empilage du 16 septembre avec Pixhawk/base v2A et kit Orin Nano séparés,
ainsi que son enveloppe PM02D : ni la porteuse commune, ni l'Orin NX 16 Go,
ni le PM08-CAN et son support fixe ne sont démontrés par cette maquette.

## 8. Exigences système et validation

La stratégie, les portes, les campagnes et leurs résultats sont maintenus dans
[DOC-VAL](../VALIDATION_QUALIFICATION.md). Les exigences ci-dessous restent la
référence du comportement attendu au niveau système.

### 8.1 Fonctions communes

| ID | Exigence |
|---|---|
| `SYS-FUN-001` | Séparer le vol critique PX4 des fonctions avancées ROS 2. |
| `SYS-FUN-002` | Horodater et enregistrer les données brutes nécessaires au rejeu. |
| `SYS-FUN-003` | Présenter à l'opérateur mission, navigation, énergie, communications et sûreté. |
| `SYS-FUN-004` | Permettre interruption, abandon et retour à un état sûr depuis la station et l'embarqué. |
| `SYS-FUN-005` | Détecter les données périmées, incohérentes ou absentes et adapter le comportement. |
| `SYS-FUN-006` | Relier mission, logiciel, paramètres, données, essais et résultats. |
| `SYS-FUN-007` | Exécuter les missions des deux drones en AUTO embarqué sans dépendance permanente au sol, sous gardes valides. |
| `SYS-FUN-008` | Permettre une reprise MANU volontaire et un retour AUTO explicite ; ne pas changer d'autorité par simple reconnexion. |
| `SYS-FUN-009` | Assurer le suivi QGroundControl et signaler sa perte sans rendre la commande physique dépendante du PC. |

### 8.2 Drone cartographe

| ID | Exigence |
|---|---|
| `MAP-FUN-001` | Acquérir de manière synchronisée LiDAR, IMU, GNSS RTK et images. |
| `MAP-FUN-002` | Maintenir une estimation de trajectoire pendant une dégradation GNSS temporaire. |
| `MAP-FUN-003` | Produire un nuage 3D géoréférencé de la zone couverte. |
| `MAP-FUN-004` | Segmenter au minimum terrain, végétation, poteaux et obstacles structurants. |
| `MAP-FUN-005` | Identifier pieds, rangs, terrasses, murs, talus et ruptures utiles à la planification. |
| `MAP-FUN-006` | Associer à chaque entité un identifiant, une géométrie, une confiance et une date. |
| `MAP-FUN-007` | Produire un graphe reflétant la géométrie réelle des rangs. |
| `MAP-FUN-008` | Signaler les zones insuffisamment observées ou trop incertaines. |
| `MAP-FUN-009` | Couvrir une surface prédéfinie par une trajectoire tenant compte des champs utiles, hauteur locale, recouvrements, relief et obstacles. |

### 8.3 Drone de traitement

| ID | Exigence |
|---|---|
| `TRT-FUN-001` | Charger et vérifier une carte compatible avant mission. |
| `TRT-FUN-002` | Se recaler par GNSS/IMU, LIO/VIO et perception locale. |
| `TRT-FUN-003` | Construire en continu le corridor libre du drone et du bras. |
| `TRT-FUN-004` | Respecter les distances de sécurité aux vignes, sol, poteaux, fils et obstacles. |
| `TRT-FUN-005` | Suivre et anticiper relief, pentes et ruptures compatibles avec la dynamique. |
| `TRT-FUN-006` | Déployer le bras uniquement avec toutes les gardes valides. |
| `TRT-FUN-007` | Associer chaque cible observée à la carte avec une confiance mesurable. |
| `TRT-FUN-008` | Commander indépendamment les étages permis par l'architecture matérielle. |
| `TRT-FUN-009` | Compenser vitesse et latences pompe/vanne pour aligner application et cible. |
| `TRT-FUN-010` | Calculer ou appliquer la dose selon mission, vitesse, distance et végétation. |
| `TRT-FUN-011` | Interrompre immédiatement l'application hors zone ou en anomalie critique. |
| `TRT-FUN-012` | Produire la carte ou le journal des zones et quantités réellement traitées. |

### 8.4 Station de mission

| ID | Exigence |
|---|---|
| `GCS-FUN-001` | Préparer, visualiser, valider, lancer et interrompre une mission. |
| `GCS-FUN-002` | Présenter carte 2D/3D, rangs, pieds, obstacles, zones interdites et zones traitées. |
| `GCS-FUN-003` | Présenter alarmes, bras, produit et marges de sûreté pertinentes. |
| `GCS-FUN-004` | Exporter journaux et rapports nécessaires à la traçabilité. |

### 8.5 Sûreté

| ID | Exigence |
|---|---|
| `SAFE-REQ-001` | PX4 conserve boucles de vol, moteurs et failsafes ; ROS 2 ne commande pas directement les moteurs. |
| `SAFE-REQ-002` | Toute perte de consigne, communication ou perception critique déclenche un comportement défini. |
| `SAFE-REQ-003` | Fraîcheur, fréquence et cohérence des flux critiques sont surveillées. |
| `SAFE-REQ-004` | Les fils sont un danger multimodal ; aucun capteur seul ne garantit leur détection. |
| `SAFE-REQ-005` | Le bras possède états sûrs, confirmation de position et stratégie de blocage. |
| `SAFE-REQ-006` | Pompe et vannes reviennent fermées lors d'une perte d'énergie, commande ou urgence. |
| `SAFE-REQ-007` | Géofence, limites de vitesse/altitude et zones interdites sont chargées avant mission. |
| `SAFE-REQ-008` | Les essais progressent par portes, de la simulation vers le réel. |
| `SAFE-REQ-009` | Le traitement reste inhibé sans localisation, carte, corridor et bras valides. |
| `SAFE-REQ-010` | Distinguer pertes RC, GCS, RF commune, RTK et Offboard selon AUTO/MANU ; maintenir les protections embarquées et maîtriser la reconnexion. |

### 8.6 Objectifs de performance préliminaires

Ces valeurs servent au dimensionnement des essais et restent toutes
**À valider**.

| ID | Indicateur | Objectif de travail |
|---|---|---|
| `PERF-001` | erreur de localisation locale | compatible avec le corridor ; cible initiale ≤ 10 cm |
| `PERF-002` | disponibilité de l'odométrie | aucune interruption non gérée pendant une séquence qualifiée |
| `PERF-003` | contrôle de trajectoire locale | ≥ 20 Hz |
| `PERF-004` | perception d'obstacles | ≥ 10 Hz avec latence bornée |
| `PERF-005` | décalage longitudinal du traitement | cible initiale ≤ 10 cm à vitesse nominale |
| `PERF-006` | erreur de dose par segment | cible initiale ≤ 10 % sur banc |
| `PERF-007` | collision | zéro sur les scénarios acceptés |
| `PERF-008` | perte non signalée d'un flux critique | zéro |
| `PERF-009` | reproductibilité | configuration identique et résultats comparables archivés |

Une hauteur de 30 m AGL est un plafond d'étude préliminaire, pas une hauteur
nominale. La portée oblique du LiDAR peut la dépasser selon le champ de vue ;
portée, densité, sécurité et réglementation restent **À valider**.

### 8.7 Environnement à qualifier

Le système doit être évalué sur terrain plat et fortes pentes, terrasses,
ruptures, rangs courbes ou discontinus, végétation dense/clairsemée, motifs
répétitifs, vent, poteaux, fils, murs, talus, perte GNSS et variations de
luminosité. Les limites nominales de pente, vent, température, pluie,
visibilité et écartement restent **À valider** sur la plateforme physique.

### 8.8 Traçabilité synthétique actuelle

| Exigence | Allocation principale | Test ou preuve | Résultat actuel |
|---|---|---|---|
| `SAFE-REQ-001/002` | PX4, pont compagnon | perte Offboard et perte compagnon en SITL puis banc | SITL partiel implémenté ; matériel **À valider** |
| `SYS-FUN-007/008/009`, `SAFE-REQ-010` | PX4, compagnon, RC/MAVLink et QGC | `T-RF-01..05`, DOC-VAL §9.1 | **Planifié**, non exécuté |
| `MAP-FUN-009` | planification de couverture et suivi embarqué | `T-MAP-COV-01`, DOC-VAL §9.1 | **Planifié**, non exécuté |
| `SYS-FUN-002/006`, `MAP-FUN-001` | cartographe, station | manifeste, temps, calibration et empreintes | contrats partiels implémentés |
| `MAP-FUN-003/005/008` | chaîne cartographique | jeux synthétiques, rejeu FriûlBot et diagnostics | implémenté préliminaire ; précision **À valider** |
| `TRT-FUN-001`, `GCS-FUN-001` | station | approbation, compatibilité et rejet | planifié |
| `TRT-FUN-003/004` | carte, planificateur, PX4 | relief/obstacles/fils puis vols progressifs | planifié |
| `TRT-FUN-006/011`, `SAFE-REQ-005/006/009` | mission, bras, pompe, vannes | défauts sur banc sec puis eau/traceur | planifié |
| `TRT-FUN-012`, `GCS-FUN-004` | enregistreur, station | rapprochement prescription/réalité | planifié |

La preuve détaillée d'un composant est référencée depuis le document de domaine
correspondant. Les rosbags, datasets et résultats volumineux ne sont pas
versionnés.

## 9. Risques et décisions ouvertes

- géométrie, masse, autonomie et rétraction du drone de traitement ;
- détection fiable des fils et marge de corridor ;
- LiDAR, optique RGB, synchronisation et calibration finales ;
- performances Jetson à 1× et tenue thermique ;
- architecture électrique sélective et comportement aux transitoires ;
- modèles de dose, vent et downwash ;
- cadre réglementaire des essais et des produits ;
- signature, identités et protocole de transfert des paquets ;
- budget de débit RF commun, couverture des parcelles et arbitrage AUTO/MANU ;
- planification du balayage sur relief et politique qualifiée de perte de liaison.

Tous ces éléments restent **À valider** tant qu'un choix documenté et sa preuve
ne sont pas disponibles.

## 10. Références et historique consolidés

- Détails logiciels : [DOC-SW](ARCHITECTURE_LOGICIELLE.md).
- Détails mécaniques : [DOC-MEC](ARCHITECTURE_MECANIQUE.md).
- Détails électriques et réseaux : [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md).
- Les stratégies, preuves et résultats synthétiques sont consolidés dans
  [DOC-VAL](../VALIDATION_QUALIFICATION.md). Les anciens documents numérotés ont
  été consolidés puis supprimés ; l'historique Git conserve leur contenu.

## Journal de modifications

| Date | Modification |
|---|---|
| 24 septembre 2026 | cible Pixhawk Jetson Baseboard avec Pixhawk 6X module et Orin NX 16 Go ; BEC1/2 vers POWER1/POWER2, CAN1 séparé, CA01 5 V local protégé et porteuse via XT30/12 V candidat ; CAO et KiCad non migrés |
| 22 septembre 2026 | cible PM08-CAN fixe sur châssis près de la distribution ; BEC1 vers POWER1/vol/radio, BEC2 vers CA01 auxiliaires/synchronisation, mesure DroneCAN CAN1 ; retrait buck 5 V auxiliaire planifié, CAO et circuits KiCad V0.3 non migrés |
| 22 septembre 2026 | PM02D complet en tête de distribution avec faisceau adapté ; BEC conservé hors CA01 ; support sur cassette à étudier ; simulation distincte de qualification électrique |
| 21 septembre 2026 | PM02D retiré du périmètre CA01, support séparé et liaison directe à POWER1 ; radio alimentée depuis le domaine vol via dérivation protégée à définir ; CAO inchangée |
| 17 septembre 2026 | carte avionique commune CA01 planifiée, radio sur branche vol et PM02D rapporté candidat ; renvoi au cahier des charges, limites du schéma et de la CAO existante |
| 16 septembre 2026 | clarification AUTO/MANU des deux drones, balayage sur relief, supervision QGC et pertes ; présélection RF commune et exigences/tests associés |
| 13 septembre 2026 | intégration des décisions actives de déploiement, d'approbation, de transfert et de présélection ; retrait du registre ADR |
| 10 septembre 2026 | création puis consolidation des exigences historiques, performances, environnement et budget système |
