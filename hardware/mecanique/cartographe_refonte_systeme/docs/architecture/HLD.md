# High Level Design — système Drone Agricole

> Copie documentaire de la variante système du cartographe.

| Champ | Valeur |
|---|---|
| Référence | `DOC-HLD` |
| Nature | document vivant |
| Dernière mise à jour | 10 novembre 2026 |
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

<a id="methodologie"></a>
### 1.1 Fondements méthodologiques et décision courante

Les [22 préceptes de décision](#preceptes) fournis par le responsable du
projet sont adoptés comme méthode commune le **8 octobre 2026**. Leur texte
de référence, leurs déclencheurs, leur ordre de raisonnement et leurs règles
de conflit sont conservés au §11. Ils s'appliquent dès que leur déclencheur
est rencontré, sans demande supplémentaire. Ce document en est l'unique
source ; `AGENTS.md` et les procédures spécialisées y renvoient.

**Étoile du Nord proposée à partir du besoin existant — À valider :** rendre
possible une cartographie exploitable et traçable des vignobles de Cornas,
puis un traitement ciblé sûr. Le responsable du projet définit la réussite
d'usage ; les valeurs de §8.6 restent des objectifs de travail, pas des
critères approuvés. Le besoin terrain, le niveau de carte effectivement utile
et le coût acceptable restent à confronter à l'usage.

**Priorité courante — ORCH-CAO-MASSE-1, 25 octobre 2026 :** le responsable
demande de compléter la géométrie et la nomenclature massique du prototype
cartographe actif avant de poursuivre les études de vol, consommation et
autonomie. Les nouvelles fonctionnalités et campagnes Gazebo/PX4 sont
suspendues pendant ce lot ; les capacités et preuves existantes sont conservées.
La configuration reste `prototype_cartographe`, sans dock. Les recherches,
reconstructions documentées et calculs sont autorisés, ainsi que la définition
de grades et procédés **candidats de calcul préliminaire** pour les pièces
fabriquées. Ils ne décrivent pas un matériel reçu ou qualifié.

Le risque prioritaire est une définition incomplète ou un double comptage
d'ensembles et de composants. Le signal de sortie est la chaîne vérifiable
BOM → occurrence physique → source géométrique → source massique → contrôle.
Une inconnue indispensable bloque seulement la clôture du poste concerné ;
les travaux indépendants continuent. La recherche d'un poste est bornée par
l'examen du fabricant, de ses distributeurs officiels et des bibliothèques
traçables, puis par une reconstruction justifiable ou l'information manquante
précise. Aucun achat, fabrication, essai matériel ou raccordement réel n'est
autorisé. DOC-MEC porte les définitions ; DOC-VAL §14 porte la clôture et les
conditions de reprise. L'ancien séquencement ci-dessous conserve son contexte.

**Reprise du 26 octobre :** corriger les interférences constatées, poursuivre
l'attribution des masses et porter chaque manque directement dans la ligne
BOM concernée. Les déplacements, passages de câbles et fixations sont vérifiés
sur les natifs sauvegardés ; une réservation extérieure dégagée ne démontre
pas le raccordement réel. Une masse commerciale dont le périmètre net reste
ambigu demeure conditionnelle, même si sa valeur est publiée. La revue
indépendante vérifie cette distinction avant consolidation. Le travail
indépendant continue jusqu'à ses contrôles et à la documentation finale ;
la suspension des nouvelles campagnes reste applicable tant que les
prérequis de DOC-VAL §14 ne sont pas satisfaits.

À la demande du responsable, la masse publiée du kit d'approvisionnement est
conservée comme référence et les pièces carbone et aluminium sont estimées à partir des
volumes CAO et de densités analogues sourcées. Ces estimations sont distinctes
des masses mesurées ; les différences entre kit complet et montage actif,
ainsi que les variantes de propulsion encore incertaines, restent explicites.

**Priorité explicitement choisie par le responsable du projet le 7 octobre
2026 : valider d'abord la faisabilité physique du drone cartographe et ses
contraintes critiques.** La cible technique actuelle est une hypothèse à
éprouver ; elle ne définit pas, à elle seule, le succès du projet.

| Élément du cadrage | Décision et limite |
|---|---|
| Question prioritaire | Une configuration complète et identifiée du cartographe peut-elle satisfaire simultanément masse/centrage, propulsion/endurance, énergie/protections, structure/thermique et acquisition synchronisée ? |
| Faits disponibles | assemblage prototype reconstruit avec énergie supérieure, caméra conservée et prises coudées, 53 faisceaux Cable Workbench ; liens, placements, collisions nominales et retenues contrôlés selon DOC-MEC §2.2 et DOC-VAL §14.4. Les interfaces réelles et la tenue physique restent À valider. DOC-MEC §6.1 ne démontre pas de marge de masse pour la cible. |
| Inconnues déterminantes | équipements réellement disponibles et révisions, masse complète et inclusions, poussée/courant/endurance à cette masse, températures, tenue mécanique, interfaces et datation réelles. |
| Premier résultat minimum | une seule configuration réconciliée, chaque masse/inclusion sourcée ou explicitement inconnue, un bilan des contraintes et une décision « poursuivre », « revoir la configuration » ou « données insuffisantes », avec la prochaine mesure qui la départage. |
| Action minimale | utiliser la configuration prototype consolidée, inventorier les lots et leurs interfaces réelles, puis lever les réserves matérielles de DOC-MEC et DOC-VAL avant une nouvelle variante ou optimisation locale. Les essais suivent DOC-VAL §2. |
| Limite d'investissement | première passe limitée à une configuration et à la revue de ses contraintes. Aucun achat ni fabrication engagé par ce cadrage ; budget horaire et financier du prochain essai **À valider** avant engagement. Une inconnue ne justifie pas une exploration indéfinie. |
| Réversibilité | correction de documents et calculs traçables : Type 2 avec revue ; fabrication, modification de puissance et essais physiques : coût d'erreur élevé, validation préalable et protocole adapté. |
| Signal et arrêt | arrêter la passe quand le bilan et la décision sont explicités, ou dès qu'une donnée absente empêche de décider ; consigner alors la mesure minimale nécessaire. Revoir le choix si une contrainte applicable est dépassée ou ne peut pas être démontrée. |
| Suite | ordre, preuves attendues et critères de clôture dans [DOC-VAL §14](../VALIDATION_QUALIFICATION.md#recentrage). Les extensions cartographiques, traitement et infrastructure attendent un besoin démontré pour cette priorité ou une nouvelle décision explicite. |

Ce séquencement est **Implémenté** dans le cadre documentaire ; la faisabilité
reste **À valider**. Il ne supprime aucune capacité planifiée et ne vaut ni
autorisation d'achat, ni fabrication, ni essai en vol.

**Orientation retenue pour la définition du prototype les 8–9 octobre 2026 :** séparer deux étapes
successives : un prototype cartographe sur X650 avec la sélection cible actuelle,
sans imposer l'échange rapide de batterie ; puis un produit à mécanique et
porteuse spécifiques, conservant les modules Pixhawk 6X et Jetson, avec échange
rapide étudié dès l'architecture. Le responsable précise que « composants
actuels » désigne la sélection cible documentaire, pas du matériel déjà reçu.
L'accord pour établir sa nomenclature fixe ce périmètre documentaire. Il ne
qualifie pas les composants ni leur intégration. Ce choix soutient la priorité
de faisabilité ; le produit custom
reste conditionné aux mesures et besoins révélés par le prototype. Le périmètre,
les limites et la prochaine décision sont décrits dans
[DOC-MEC §3.1](ARCHITECTURE_MECANIQUE.md#prototype-produit).
La [nomenclature du prototype](ARCHITECTURE_MECANIQUE.md#nomenclature-prototype)
porte désormais cette sélection sans dock, ses fournitures, ses retraits et
ses inconnues. Les natifs et registres du dock existant restent conservés ;
les descriptions d'échange rapide ci-dessous concernent cette étude et le
produit ultérieur, sans imposer cette fonction au prototype. À la demande du
responsable, la reconstruction initiale a réutilisé les
références utiles : **Prototype_Cartographe**, sept sous-assemblages, est
l'assemblage actif décrit dans [DOC-MEC §2.2](ARCHITECTURE_MECANIQUE.md#assemblage-prototype).
La refonte du 22 octobre évolue en place à partir de cet état : énergie
à l'étage supérieur, position de caméra conservée avec prises coudées,
faisceaux longeant la structure et retenus par colliers. Le terminal au sol
reste libre et sans incidence sur la CAO. Sa construction est **Implémenté** ;
les résultats des contrôles numériques et de la revue indépendante sont
référencés dans DOC-VAL §14.4, la faisabilité physique reste **À valider**.
Les supports et réservations de câbles ne valent pas des pièces ni des
faisceaux qualifiés pour fabrication. La passe reste limitée à cette seule
configuration, avec réemploi traçable et conservation des sources fabricant.

Le 10 octobre, cette séparation est rendue lisible dans deux classeurs avec
vue système et détail par sous-système ([DOC-MEC §5.0](ARCHITECTURE_MECANIQUE.md#nomenclature-prototype)).
La nomenclature du produit custom reste fonctionnelle et **Planifiée** ;
sa préparation ne change pas la priorité donnée aux mesures du prototype.

**Choix utilisateur du 10 octobre pour le prototype :** brancher la batterie
met le drone sous tension, la débrancher le met hors tension. Le JETI
MainSwitch100 et sa commande magnétique sont retirés de la nomenclature
prototype. La chaîne retenue pour sa définition est batterie → BMS → connecteur
manuel avec maîtrise de l'appel de courant → PM08-CAN → distribution.
Le QS8-S D-MAX B9310 est choisi pour cette interface ; sa qualification reste
**À valider**. Pour dimensionner le SSD, le responsable demande de conserver
toutes les données brutes LiDAR et caméra pendant la mission, afin de permettre
les traitements et rejeux au sol ; scénario caméra confirmé à 5 images/s sur
20 minutes. Format, budget total et réalisation restent à vérifier dans DOC-ELEC.
Le BMS JBD retenu ne réalise pas une précharge documentée ; la réalisation compacte de cette
fonction, le courant admissible et les protections physiques restent **À valider**
([DOC-ELEC §3](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#3-chaîne-dénergie-candidate-du-cartographe)).
Le branchement s'effectue au sol, désarmé ; le connecteur n'est pas présumé
capable d'interrompre la puissance de propulsion. Les natifs et schémas avec
dock/JETI sont conservés comme définition héritée ; le prototype reconstruit
en est distinct, sans qualification du nouveau montage ni modification du
périmètre du produit custom.

### 1.2 Application proportionnée à chaque évolution

**Demande du 23 octobre 2026 :** le responsable ouvre une refonte de la station
à partir des deux maquettes MagicPath V3 et demande de préparer leurs nouvelles
fonctions. Le périmètre logiciel réversible est défini dans
[DOC-SW §4.6](../../../../../docs/architecture/ARCHITECTURE_LOGICIELLE.md#46-interface-métier-v3--23-octobre-2026) :
six espaces, deux thèmes sélectionnables, services locaux et raccordement aux
capacités existantes. L'inventaire lit la BOM prototype canonique ; la
supervision ne déduit aucun état réel de cette définition. Un brouillon local
n'est ni une mission autorisée ni un transfert vers PX4. Cette demande explicite
autorise ce chantier logiciel sans clôturer les actions physiques de DOC-VAL §14.
L'acceptation opérationnelle et la qualification du matériel restent **À valider**.

**Orientation de simulation précisée le 23 octobre 2026 :** le responsable
demande de réutiliser le modèle 3D du drone pour améliorer les estimations,
avec priorité à l'**autonomie, la consommation et la capacité à voler avec
la charge**. La cible de préparation est le prototype cartographe actif de
DOC-MEC §2.2. La dérivation CAO et les paramètres physiques sont distingués
dans [DOC-MEC §2.3](ARCHITECTURE_MECANIQUE.md#modele-gazebo-prototype) ;
les tâches et critères de validation sont dans
[DOC-VAL §9.3](../VALIDATION_QUALIFICATION.md#fidelite-gazebo-cartographe).
Ce choix soutient la priorité de faisabilité physique ; il ne démontre pas
la portance ni l'endurance. ORCH-GZ-1 implémente la dérivation CAO, un SDF et
airframe d'aperçu, ainsi que le modèle énergétique C++17 hors ligne.
Le moteur Docker est de nouveau disponible le 24 octobre et le banc ROS
reconstruit. Les vols SITL exploratoires sont consignés dans DOC-VAL §9.3 ;
le couplage de la batterie à PX4 et la fidélité physique restent **À valider**.
Le résultat borné, les preuves et les dépendances réelles de la suite sont
dans DOC-VAL §9.3, sans autorisation d'achat ni d'essai matériel.
Le responsable précise ensuite que les trois domaines doivent être réalisés,
dans cet ordre : portance/énergie, stabilité/trajectoires/vent, puis
capteurs/couverture/cartographie. L'énergie est la première étape, sans
abandon des deux suivantes. La réalisation par trois orchestrateurs successifs
et leurs conditions de reprise sont définies dans
[DOC-VAL §9.4](../VALIDATION_QUALIFICATION.md#orchestration-gazebo).

**Demande du 24 octobre :** intégrer la passerelle CAO → Gazebo dans le volet
Simulations de la station. Cette capacité réversible répond à la friction
observée des exports manuels et facilite les prochaines itérations sur la
configuration physique active. Une préparation aboutit à un dossier SDF et
à ses maillages contrôlés, sans modifier les sources ni lancer le vol. Le
signal de sortie est un dossier chargé par Gazebo et un parcours UI testé ;
la passe reste limitée au prototype, à ses formats dérivés et à une revue.
DOC-SW §5.2 porte les contrats/modules, DOC-VAL §10.2 les preuves. La
qualification physique et le couplage énergétique restent À valider.

Pour une tâche non triviale, renseigner dans la section vivante concernée,
ou dans la preuve technique lorsqu'il s'agit d'un essai, seulement les
éléments qui influencent la décision :

- problème, bénéficiaire, résultat utile et lien à la priorité courante ;
- impact et urgence distingués ; faits avec leur source, inférences,
  hypothèses et inconnues explicitement séparés ;
- cause observée ou hypothèse de cause, observation susceptible de la réfuter ;
- Type 1/Type 2, coût d'erreur, coût et délai de récupération, perte maximale
  acceptable, budget d'effort/financier et condition d'arrêt ;
- action minimale, solution existante réutilisable et raison de toute
  abstraction, infrastructure ou variante ajoutée ;
- signal, moyen et moment d'observation, critère de comparaison et décision
  suivante ; pour optimiser, référence avant et mesure après ;
- résultat réel, limites et seul apprentissage utile à conserver.

Un champ inconnu reste **À valider**, avec une observation ou une décision
de report/abandon ; il ne devient pas une valeur inventée. Un petit changement
réversible ne nécessite pas un formulaire ni un document supplémentaire.
Les repères d'information de P07 sont des heuristiques, pas des pourcentages
mesurés ni une dispense de sûreté. La calibration de prompts dépendants d'un
modèle suit P17 ; aucune technique propre à un modèle n'est imposée ici.
P18 s'applique aux usages d'agents : le jugement propose, les contrôles
déterministes et les autorités existantes bornent l'exécution sensible.

`METH-001` : toute évolution non triviale applique les préceptes déclenchés,
conserve la décision utile dans sa source canonique et relie l'exigence au
contrôle puis à son résultat. L'[audit transversal de DOC-VAL §15](../VALIDATION_QUALIFICATION.md#audit-preceptes)
contrôle cette application ; adopter la méthode ne qualifie pas les travaux
antérieurs.

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
| Base RTK locale | référence géodésique et corrections sans abonnement | Holybro H-RTK F9P Base sélectionnée ; implantation et chaîne RTCM **À valider** |
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
La cible transporte les corrections RTK sur ce RF commun via QGroundControl.
Une perte de QGC, du Wi-Fi local ou du RF arrête les corrections et peut faire
passer le rover de RTK Fix à Float ou GNSS autonome. PX4 doit décider selon la
qualité de navigation réellement disponible ; la poursuite AUTO avec cette
dégradation reste **À valider**. La commande physique reste disponible lors de
la seule perte PC/Wi-Fi, sous réserve que le RF Pocket–drone fonctionne.

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
- Chaque batterie 6S 20 Ah du cartographe doit emporter son BMS : sélection
  JBD-SP22S003 A01 100A, réception et qualification **À valider**. La CAO et
  le schéma candidats avec dock/TE et UART isolé sont **Implémentés** dans
  l'étude conservée ; leur adaptation au prototype reste à réaliser. Le BMS surveille/protège
  le pack ; PX4 conserve les décisions de vol. Une protection BMS ouvrant
  la puissance peut supprimer propulsion et avionique simultanément : les
  alertes et la politique PX4 doivent anticiper les dérives progressives
  avec des marges qualifiées. Un court-circuit ou défaut sévère peut exiger
  une protection immédiate, sans délai garanti pour atterrir ; les protections
  du pack ne sont ni inhibées ni retardées pour préserver le vol.
  Le PM08-CAN reste dans la définition du prototype. Son raccordement après
  le BMS utilise un connecteur manuel avec maîtrise de l'appel de courant
  QS8-S D-MAX B9310 choisi, qualification **À valider** (DOC-ELEC §3) ; le JETI en est retiré le 10 octobre.
  La description CAO qui suit concerne l'étude conservée avec dock/JETI,
  pas la sélection prototype : la batterie forme un sous-assemblage mobile
  distinct de son récepteur fixe.
  JETI, PM08-CAN, la PDB, P57, la commande et l’isolateurUART sont directement
  assemblés dans le principal ; cette organisation conserve leurs fonctions
  et leur pose, conservée par la migration et sa réouverture contrôlée
  (DOC-VAL§12.1.10).
  La cassette place le BMS au-dessus du pack sous un plateau rehaussé.
  Le dernier compactage rapproche le TE et remplace la grande chambre de
  raccordement par des protections locales : volume englobant de la cassette
  −10,505 %, ensemble batterie/énergie −2,757 % depuis Git `1ccbad81`.
  L’enveloppe d’intégration locale reste inchangée ; ces gains ne qualifient
  ni un drone équipé complet ni sa masse. Le contrôle numérique BMS et
  l’extraction échantillonnée et le contrôle complet des37 routes sont réussis ;
  la relecture finale confirme l’identité des fichiers enregistrés avec les
  candidats contrôlés. Ports, sertissage, flottement, retenue et thermique
  restent **À valider**.

## 6. Informations échangées

| Information | Producteur | Consommateur | Contrôle attendu |
|---|---|---|---|
| Acquisition capteurs | drone cartographe | station | manifeste, horodatage, source et verrouillage des horloges, offset/incertitude, association image-déclenchement, calibration et empreintes |
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

Le responsable distingue le **terminal de terrain** de son **PC fixe de
traitement**. Le 12 octobre 2026, il précise que le format reste ouvert :
portable, tablette ou téléphone selon l'ergonomie. Le chargeur du terminal
est provisionné à **60 W** comme hypothèse ; aucun modèle n'est imposé pour
poursuivre la CAO du drone. Fonctions de terrain et compatibilité restent
à vérifier lors du choix, sans présumer une station Qt mobile. Le profil
portable antérieur et l'inventaire du poste fixe sont dans
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#pc-sol-prototype).
L'autorité de vol PX4 reste inchangée.

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
encore un kit Orin Nano et une base Pixhawk v2A distincts. Le choix de conception est un **Holybro H-RTK F9P DroneCAN Rover** embarqué et une
**Holybro H-RTK F9P Base** au sol. Pour obtenir un PPS physique en plus du
CAN2 de navigation, la variante **Helical STM32G4** du Rover devient la cible
**Planifiée** ; sa broche 5 UART2/PPS doit être confirmée sur la révision livrée.
La variante S32K1 avec broche 5 non connectée ne satisfait pas cette fonction.
Le montage, le repère de la base, les performances RTK et la distribution du
temps restent **À valider**. La cible d'intégration devient une **liaison RF commune**
à la commande manuelle et à MAVLink/QGroundControl (§4.6–4.7), pour réduire
les modules, antennes et besoins d'alimentation. Elle remplace la présélection
antérieure de deux radios distinctes ; celles-ci restent une solution de repli.
La perte commune est assumée comme hypothèse d'architecture, sans prétendre
à une redondance de liaison. RTCM, commandes QGC ponctuelles et télémétrie
doivent partager le débit MAVLink ; la faisabilité simultanée est **À valider**
par T-RF-06. Les consignes de déplacement continues sont produites à bord
via le compagnon et PX4, pas par une boucle dépendant du poste au sol. La présélection Pocket ELRS EU-LBT + RP4TD en
mode MAVLink, les alternatives et les limites sont portées par
[DOC-ELEC §7.4](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#74-liaison-rf-commune-rc-et-mavlink).
Aucun choix de matériel ou de firmware n'est **Qualifié**.

La carte avionique commune **CA01** possède un schéma et un routage candidats **Implémentés**, avec fabrication et qualification **À valider**, pour regrouper RP4TD,
conversions de charge utile et adaptation de synchronisation. La cible retenue
le 22 septembre 2026 utilise un **PM08-CAN fixé au châssis, près de la
distribution**, hors CA01 et hors cassette batterie. Il remplace le PM02D de
la définition précédente. Pour le prototype sans dock ni JETI, la chaîne de
définition est batterie → BMS → connecteur manuel avec maîtrise de l'appel de
courant → PM08-CAN → toutes les branches, pour la mesure globale.
Les courants admissibles, protections et la couverture de mesure restent
**À valider** sur la configuration réelle (DOC-ELEC §3).

Le **BEC1 du PM08-CAN** alimente **POWER1** et le **BEC2** alimente
**POWER2** du Pixhawk 6X monté sur la porteuse, par deux chemins distincts.
La mesure batterie passe séparément par **DroneCAN vers CAN1**. Ces entrées
forment une redondance candidate au niveau de l'alimentation du contrôleur ;
la batterie, le BMS, le connecteur manuel et le PM08-CAN restent des causes de
défaillance communes dans le prototype.
Brochage de la nouvelle porteuse, isolation entre rails, budgets et comportement
en défaut sont **À valider** selon [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md).

Dans la CAO conservée avec dock/JETI, la batterie 6S 20 Ah, son récepteur et
la rehausse supérieure de45 mm
au total (20 mm historiques puis25 mm pour le BMS) sont implémentés en CAO. L'échange se fait au sol, moteurs arrêtés, après coupure JETI OFF,
avec pales dégagées et contrôle du verrouillage avant remise sous tension.
Le module commute le négatif et mémorise son état : aucun interverrouillage
automatique de puissance avec le loquet n'est revendiqué. Cette intégration locale
historique représente la stack Holybro/CA01 ; les variantes précédentes
d’avionique sont historiques.
La mécanique, les courants et la masse complète restent **À valider** ; voir
DOC-MEC §4.1.3 et DOC-ELEC §6.2.
Le connecteur XT90 de la distribution conservé est annoncé45A sous conditions fabricant ;
la chaîne complète n'est donc pas déclarée85/100A. Le budget partiel avec
provisions connues6,112–6,726kg dépasse déjà la limite publiée6,3kg en
borne haute. Le vol et les anciennes estimations d'autonomie ne sont pas
validés pour cette étude avec dock. Ces chiffres ne sont pas un bilan massique
du prototype reconstruit, dont la masse et le centrage restent à établir.

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

La synchronisation du cartographe repose, en cible **Planifiée**, sur un même
repère de temps GNSS et des événements physiques mesurables. Le Rover fournit
la navigation RTK à PX4 par CAN2 ; sa sortie PPS candidate rejoint CA01, qui
prépare PPS et GPRMC compatibles avec l’Airy et une référence temporelle pour
le Jetson par les accès disponibles de la porteuse. La Jetson sous ROS 2 décide
des captures métier ; PX4 réalise leur déclenchement matériel sur la Basler
par une sortie AUX affectée et CA01 adapte ce signal à son entrée optocouplée ;
le retour ExposureActive de la caméra rejoint une entrée de capture du Pixhawk
réservée à cet effet. Les points Airy continuent par Ethernet et les images
Basler par USB3 vers le Jetson. Les événements PX4 transitent par le lien
compagnon interne candidat TELEM2. Le retour de capture ne remplace pas le PPS
et l’Airy SYNC_OUT1 reste une option ultérieure. La disponibilité de chaque port,
les niveaux électriques et l’offset/incertitude entre horloges GNSS, PX4 et
Jetson sont **À valider** ; cette architecture ne démontre pas encore une
synchronisation acquise. Voir [DOC-ELEC §8](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#8-synchronisation-et-repères-temporels),
[DOC-SW §7.1](../../../../../docs/architecture/ARCHITECTURE_LOGICIELLE.md#71-composants-logiques-cibles) et
[DOC-VAL §12.8](../VALIDATION_QUALIFICATION.md).

Dans cette cible **Planifié / À valider**, `mission_manager` sur la Jetson
décide quand acquérir une image selon la couverture ; `sensor_manager`
coordonne la demande, les diagnostics et l'association des données. PX4
exécute la commande caméra et mesure le retour d'exposition ; CA01 adapte
les signaux sans décider d'une capture. Une seule autorité de capture est
active pendant le relevé : les déclenchements autonomes de mission PX4 ou
les commandes de test QGroundControl doivent être exclus de cette session.
Le GNSS, les IMU et le LiDAR produisent des flux continus : ils ne reçoivent
pas un ordre de nouvelle mesure à chaque photo. La Jetson associe l'image
à la pose et aux points mesurés dans une fenêtre temporelle justifiée,
avec compensation du mouvement ; l'heure de réception n'est pas l'heure
d'acquisition. Le PPS fournit un repère d'horloge, pas une cadence photo.

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
| `MAP-FUN-001` | Coordonner les captures depuis la Jetson/ROS 2, avec une seule autorité active ; acquérir et dater les flux LiDAR, IMU, GNSS RTK et images dans un repère temporel traçable ; associer demande, déclenchement physique, exposition et image, mesurer les offsets et incertitudes, et marquer invalides les données dont la synchronisation est perdue ou indémontrable. |
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
| `SAFE-REQ-011` | Intégrer un BMS dans chaque cassette 6S 20 Ah du cartographe ; coordonner alertes et protections avec PX4, sans voie de puissance ou de communication contournant la coupure. CAO/schéma **Implémentés**, protection physique **À valider** ; DOC-ELEC `ELEC-BMS-001`, DOC-VAL §12.1.9. |

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
| `SYS-FUN-007/008/009`, `SAFE-REQ-010` | PX4, compagnon, RC/MAVLink, RTCM et QGC | `T-RF-01..06`, DOC-VAL §9.1 | **Planifié**, non exécuté |
| `MAP-FUN-009` | planification de couverture et suivi embarqué | `T-MAP-COV-01`, DOC-VAL §9.1 | **Planifié**, non exécuté |
| `SYS-FUN-002/006` | cartographe, station | manifeste, données brutes, calibration et empreintes | contrats de rejeu partiels **Implémentés** ; acquisition sur matériel **À valider** |
| `MAP-FUN-001` | Rover/CA01, PX4, Airy, Basler et `sensor_manager` Jetson | `T-AIRY-SYNC-01`, `T-CA01-09`, DOC-VAL §12.8 : verrouillage, offsets/incertitudes, association exposition/image, pertes et reprise | **Planifié / À valider** ; aucune synchronisation matérielle démontrée |
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

- Détails logiciels : [DOC-SW](../../../../../docs/architecture/ARCHITECTURE_LOGICIELLE.md).
- Détails mécaniques : [DOC-MEC](ARCHITECTURE_MECANIQUE.md).
- Détails électriques et réseaux : [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md).
- Les stratégies, preuves et résultats synthétiques sont consolidés dans
  [DOC-VAL](../VALIDATION_QUALIFICATION.md). Les anciens documents numérotés ont
  été consolidés puis supprimés ; l'historique Git conserve leur contenu.

<a id="preceptes"></a>
## 11. Préceptes de décision — référence canonique

Ces principes ne sont pas des citations ni des recommandations optionnelles.

Ils constituent un **système de décision**.

Chaque principe possède un déclencheur. Lorsqu'un déclencheur correspond à la situation, le principe s'applique sans demande explicite.

Plusieurs principes peuvent s'appliquer simultanément.

Ils ne votent pas entre eux : ils s'appliquent selon l'ordre de raisonnement défini ci-dessous.

---

### Ordre de raisonnement

Pour tout problème non trivial, raisonner dans cet ordre :

1. **Valider le référentiel**
2. **Évaluer l'importance réelle du problème**
3. **Observer le réel disponible**
4. **Distinguer faits, hypothèses et inconnues**
5. **Diagnostiquer la cause**
6. **Évaluer la réversibilité et le coût d'erreur**
7. **Définir le downside acceptable**
8. **Choisir l'action minimale suffisante**
9. **Exécuter**
10. **Observer le résultat**
11. **Corriger à partir du feedback**
12. **Optimiser seulement après signal**
13. **Capitaliser uniquement si le levier est réutilisable**

Une étape ultérieure ne doit pas compenser une erreur non résolue dans une étape antérieure.

Exemple :

> Ne pas optimiser une solution avant d'avoir validé qu'elle résout le bon problème.

---

### Résolution des conflits entre principes

Lorsqu'au moins deux principes conduisent à des actions différentes :

1. Le principe situé le plus tôt dans l'ordre de raisonnement prévaut.
2. La sécurité et l'irréversibilité prévalent sur la vitesse.
3. Une observation prévaut sur une hypothèse.
4. Une contrainte réelle prévaut sur une préférence d'architecture.
5. Une solution plus simple prévaut à résultat équivalent.
6. En cas d'incertitude restante, choisir l'expérience réversible au downside le plus faible.

Un principe ne doit jamais être sélectionné uniquement parce qu'il justifie une décision déjà souhaitée.

---

### Convention d'écriture des principes

```markdown
## Nom du principe

Assertion.

### Déclencheur

Quand il s'applique.

### Application

Comment l'appliquer.
Checklist, questions, étapes ou processus.
```

---

<a id="p01"></a>
### P01 — First Principles

Repartir des contraintes fondamentales plutôt que des solutions existantes.

##### Déclencheur

Lorsqu'un problème paraît complexe, hérité, mal défini ou lorsque le raisonnement tourne autour des solutions existantes sans progresser.

##### Application

- Décomposer le problème jusqu'aux contraintes fondamentales.
- Distinguer ce qui est réellement nécessaire de ce qui est historiquement présent.
- Écarter temporairement conventions, habitudes et analogies.
- Identifier les éléments qui ne peuvent pas être supprimés sans changer le problème.
- Reconstruire la solution à partir de ces éléments.

Question centrale :

> Qu'est-ce qui doit nécessairement être vrai pour que le problème existe ?

---

<a id="p02"></a>
### P02 — Référentiel validé avant engagement

Je challenge le référentiel avant d'optimiser à l'intérieur de celui-ci.

##### Déclencheur

Lorsqu'un problème, une mission, un objectif ou une définition du succès provient d'un cadre préexistant ou défini par quelqu'un d'autre.

##### Application

Vérifier :

- Qui définit le succès ?
- Pourquoi cet objectif existe-t-il ?
- Qui définit les contraintes ?
- Les contraintes sont-elles physiques, réglementaires, économiques ou simplement historiques ?
- Qui bénéficie du référentiel actuel ?
- Quel problème cherche-t-on réellement à résoudre ?
- Ce référentiel reste-t-il aligné avec l'Étoile du Nord ?

Ne pas optimiser un système dont l'objectif lui-même n'a pas été validé.

---

<a id="p03"></a>
### P03 — Classification des problèmes avant action

L'urgence et l'importance sont deux dimensions différentes.

##### Déclencheur

Avant d'engager du temps, de l'argent ou de l'énergie significative sur un nouveau problème.

##### Application

Classer le problème selon deux axes :

| | Peu urgent | Urgent |
|---|---|---|
| **Fort impact** | Planifier et protéger du temps | Traiter prioritairement |
| **Faible impact** | Ignorer, automatiser ou déléguer | Limiter fortement l'énergie investie |

Principe :

> Ne jamais laisser l'urgence d'un problème à faible impact voler les ressources d'un problème à fort impact.

Un problème est à fort impact s'il influence réellement :

- la trajectoire du projet ;
- une contrainte critique ;
- une décision difficilement réversible ;
- la capacité future ;
- l'Étoile du Nord.

---

<a id="p04"></a>
### P04 — Le réel ne se déduit pas

Une question portant sur le réel se résout prioritairement par observation.

Le raisonnement produit des hypothèses. Il ne transforme pas une hypothèse en observation.

##### Déclencheur

Chaque fois qu'une question porte sur :

- ce que fait quelqu'un ;
- ce que veut quelqu'un ;
- ce que paie quelqu'un ;
- le comportement réel d'un système ;
- un usage ;
- une performance ;
- une cause potentiellement observable.

##### Application

1. Identifier où la réponse pourrait déjà exister :
   - logs ;
   - métriques ;
   - conversation ;
   - comportement utilisateur ;
   - expérience ;
   - documentation ;
   - mesure physique.

2. Lire les données existantes avant d'en produire de nouvelles.

3. Si la donnée n'existe pas, créer l'exposition minimale qui permet de l'obtenir.

4. Séparer explicitement :
   - **fait observé** ;
   - **inférence** ;
   - **hypothèse** ;
   - **inconnue**.

5. Utiliser l'inférence pour déterminer quoi observer ensuite, jamais pour remplacer l'observation.

6. Écrire les signaux importants.

> Un signal observé mais non enregistré est difficilement capitalisable.

Une question importante sur le réel qui reste sans exposition doit déboucher sur :

- une observation ;
- une expérience ;
- ou un abandon explicite.

---

<a id="p05"></a>
### P05 — Résoudre à la source

Corriger la cause plutôt que la conséquence.

##### Déclencheur

Lorsqu'un bug, une friction, une anomalie, une dette récurrente ou une exception apparaît.

##### Application

- Identifier le symptôme.
- Remonter jusqu'à la première hypothèse ou condition incorrecte.
- Utiliser les **Five Whys** lorsque pertinent.
- Vérifier la cause avec des observations.
- Éviter qu'un workaround temporaire devienne une architecture permanente.
- Si une exception devient fréquente, revoir le design.
- Supprimer la cause lorsqu'elle peut l'être au lieu de compenser ses effets.

Question :

> Si je supprime ce correctif, quel mécanisme sous-jacent recrée le problème ?

C'est ce mécanisme qui doit être examiné.

---

<a id="p06"></a>
### P06 — Les abstractions représentent une distinction réelle

Une abstraction doit correspondre à une distinction réelle du problème.

##### Déclencheur

Lorsqu'un nouvel état, type, objet, couche, service, règle ou abstraction est introduit.

##### Application

Demander :

- Quelle différence réelle cette abstraction représente-t-elle ?
- Produit-elle une différence de comportement ?
- Porte-t-elle une responsabilité différente ?
- Représente-t-elle une règle métier, une politique, une frontière ou un contrat distinct ?
- Existe-t-il déjà une abstraction capable de porter cette différence ?

Si deux abstractions :

- ont les mêmes règles ;
- produisent les mêmes comportements ;
- ont la même responsabilité ;

elles devraient probablement être fusionnées.

Préférer faire évoluer une abstraction existante plutôt qu'en créer une nouvelle lorsque la distinction métier ne le justifie pas.

---

<a id="p07"></a>
### P07 — Vitesse de décision

La lenteur coûte plus cher que l'erreur lorsque l'erreur est réellement réversible.

##### Déclencheur

Chaque décision engageante, particulièrement lorsqu'une hésitation apparaît entre :

- préparer davantage ;
- ou agir maintenant.

##### Application

Classer la décision.

#### Type 1 — porte à sens unique

Décision :

- irréversible ;
- difficilement réversible ;
- très coûteuse à corriger ;
- ou dont l'erreur a des conséquences importantes.

Application :

- rechercher davantage d'information ;
- challenger les hypothèses ;
- vérifier les dépendances ;
- prendre davantage de temps.

> Mesure deux fois, coupe une fois.

#### Type 2 — porte à double battant

Décision réversible à coût acceptable.

Application :

- décider avec une information suffisante mais incomplète ;
- favoriser l'expérience réelle ;
- corriger ensuite à partir du feedback.

Repère :

- < 40 % d'information : risque de décision aveugle ;
- 40–70 % : zone raisonnable de décision ;
- > 70 % : risque de suranalyse si l'information supplémentaire ne change probablement pas la décision.

Avant une décision Type 2, définir :

- Quel signal pourrait montrer que la décision est mauvaise ?
- Où ce signal sera-t-il observé ?
- Quand sera-t-il observé ?

Une décision supposée réversible sans mécanisme de feedback est une décision Type 1 déguisée.

---

<a id="p08"></a>
### P08 — Budget d'erreur proportionnel à la réversibilité

Plus une erreur est facile à détecter et corriger, moins elle mérite de prévention.

##### Déclencheur

Lorsqu'il faut déterminer :

- le niveau de validation ;
- le niveau de test ;
- le niveau de contrôle ;
- l'autorité accordée à un humain, un agent ou un système.

##### Application

Évaluer :

- probabilité d'erreur ;
- détectabilité ;
- coût maximal ;
- délai de détection ;
- coût de récupération.

Puis adapter la rigueur.

Faible coût d'erreur :

> expérimenter rapidement.

Coût moyen :

> exécuter avec contrôle et feedback.

Coût élevé ou irréversible :

> valider avant exécution.

La sophistication du contrôle doit être proportionnelle au risque réel, pas à la complexité apparente de la tâche.

---

<a id="p09"></a>
### P09 — Test asymétrique

Une initiative intéressante possède un downside connu et acceptable, avec un upside significativement supérieur.

##### Déclencheur

Avant tout engagement significatif de temps, d'argent ou d'énergie dans une initiative au résultat incertain.

##### Application

Définir avant de commencer :

- coût maximal acceptable ;
- budget horaire maximal ;
- budget financier maximal ;
- condition d'arrêt ;
- signal de réussite ;
- date ou événement de revue.

Rechercher :

- pertes limitées ;
- apprentissage réutilisable ;
- gain potentiel disproportionné.

Une initiative est particulièrement intéressante lorsque :

> perdre coûte peu, mais réussir change significativement la trajectoire.

---

<a id="p10"></a>
### P10 — Le minimum suffisant

La meilleure solution est la plus simple qui résout durablement le problème identifié.

##### Déclencheur

Chaque conception ou modification d'un système, produit, prompt, process ou architecture.

##### Application

Avant d'ajouter :

1. Vérifier que le problème est correctement défini.
2. Retirer ce qui n'est pas nécessaire. — **Via Negativa**
3. Ne pas multiplier les éléments sans nécessité. — **Occam**
4. Ne pas construire pour un futur hypothétique. — **YAGNI**
5. Chercher la solution minimale capable de produire le signal recherché.
6. N'ajouter de complexité qu'en réponse à une contrainte observée.

Question :

> Si cet élément disparaît, le système cesse-t-il de remplir son objectif ?

Si non, sa nécessité doit être justifiée.

---

<a id="p11"></a>
### P11 — Gall's Law

Un système complexe qui fonctionne provient généralement d'un système plus simple qui fonctionnait.

##### Déclencheur

Lors de la création d'un nouveau système ou d'une architecture importante.

##### Application

- Identifier le noyau fonctionnel minimal.
- Construire ce noyau.
- Vérifier qu'il fonctionne réellement.
- Ajouter une capacité à la fois.
- Vérifier après chaque évolution.
- Ne jamais construire directement une architecture finale hypothétique.

La complexité doit apparaître en réponse à une contrainte réelle.

Elle ne doit pas être anticipée par défaut.

---

<a id="p12"></a>
### P12 — Séquence de validation avant construction

La construction vient après la validation du problème.

##### Déclencheur

Avant de construire, automatiser ou structurer une nouvelle solution.

##### Application

Respecter la séquence :

1. Observer le réel
2. Identifier la douleur ou la contrainte
3. Vérifier son importance
4. Diagnostiquer la cause
5. Formuler une hypothèse de solution
6. Construire le minimum suffisant
7. Mesurer le résultat
8. Optimiser uniquement après signal

Ne pas inverser cette séquence.

En particulier :

> Construire puis chercher à qui cela pourrait servir est un anti-pattern.

---

<a id="p13"></a>
### P13 — Boucle fermée

Une action sans retour observable n'est pas pilotable.

##### Déclencheur

Chaque fois qu'une action cherche à modifier un système, un comportement ou un résultat.

##### Application

Toute action significative doit former une boucle :

**Action → Signal → Observation → Comparaison → Correction**

Définir :

- ce qui est modifié ;
- le signal attendu ;
- le moyen de mesure ;
- la valeur ou tendance attendue ;
- la prochaine décision possible.

Sans feedback, il n'y a pas de pilotage : seulement une succession d'actions.

---

<a id="p14"></a>
### P14 — Critère d'arrêt

Tout travail non trivial doit posséder une condition indiquant quand arrêter.

##### Déclencheur

Avant une tâche pouvant dériver en :

- recherche ;
- optimisation ;
- refactoring ;
- expérimentation ;
- conception ;
- exploration ;
- debugging.

##### Application

Définir avant ou au début du travail :

- résultat minimum acceptable ;
- critère de réussite ;
- budget maximal ;
- critère d'abandon ;
- événement déclenchant une nouvelle itération.

Arrêter lorsqu'un de ces critères est atteint.

Ne pas confondre :

> améliorable

avec :

> insuffisant.

---

<a id="p15"></a>
### P15 — Avantage cumulatif

Les meilleurs investissements augmentent durablement la capacité à produire de la valeur future.

##### Déclencheur

Lorsqu'un arbitrage de temps, d'argent ou d'énergie est nécessaire.

##### Application

Favoriser les investissements qui :

- améliorent une capacité réutilisable ;
- réduisent plusieurs frictions futures ;
- augmentent la vitesse d'apprentissage ;
- produisent des actifs réutilisables ;
- augmentent la qualité des décisions futures.

Questions :

- Cet investissement sera-t-il encore utile dans un an ?
- Peut-il servir plusieurs situations ?
- Rend-il les prochaines actions plus faciles ?
- Produit-il une capacité ou seulement un résultat ?

Les gains composés sont préférables aux gains ponctuels lorsqu'ils répondent à une friction réelle.

---

<a id="p16"></a>
### P16 — Investissement méta-systémique

Investir dans l'infrastructure uniquement lorsqu'elle résout une friction réelle et récurrente.

##### Déclencheur

Avant un investissement important dans :

- tooling ;
- automatisation ;
- framework interne ;
- architecture générique ;
- infrastructure personnelle ou organisationnelle.

##### Application

Trois conditions sont nécessaires :

1. L'investissement sert plusieurs usages ou possède une probabilité réaliste de réutilisation.
2. La friction qu'il traite a déjà été observée.
3. Le gain produit peut être observé après mise en place.

Condition supplémentaire :

4. Le coût de construction est cohérent avec le coût cumulé de la friction.

Sans ces conditions, l'infrastructure risque d'être une optimisation prématurée ou un mécanisme d'évitement.

---

<a id="p17"></a>
### P17 — Composition de prompts LLM

Un prompt efficace réduit l'ambiguïté du jugement et explicite les contraintes importantes.

##### Déclencheur

Chaque rédaction ou modification d'un contenu destiné à guider un LLM ou un agent.

##### Application

#### Principes

##### Structure > prose

Séparer clairement :

- rôle ;
- contexte ;
- objectif ;
- contraintes ;
- outils ;
- critères de succès ;
- format de sortie ;
- exemples éventuels.

##### Densité informationnelle

Chaque instruction doit apporter une information utile.

Supprimer :

- répétitions inutiles ;
- motivations décoratives ;
- formulations ambiguës ;
- prose qui n'influence pas la décision.

##### Principe pour guider, contrainte pour borner

Utiliser :

- les **principes** pour guider le jugement dans des situations nouvelles ;
- les **contraintes explicites** lorsque certaines actions doivent absolument être autorisées, interdites ou bornées.

Une règle critique n'a pas besoin d'être implicite.

Exemple :

> Ne jamais modifier directement la branche `main`.

est une contrainte valide même si elle découle d'une politique plus générale.

##### Contrat de sortie

Définir lorsque nécessaire :

- ce qui doit être produit ;
- ce qui constitue une réponse correcte ;
- le niveau de détail ;
- le format ;
- les critères de validation.

##### Exemples ciblés

Utiliser des exemples lorsqu'ils réduisent une ambiguïté difficile à exprimer uniquement par une règle.

Ne pas multiplier les exemples lorsqu'ils ne changent pas le comportement.

##### Calibration externe

Pour une tâche LLM importante ou dépendante fortement d'un modèle donné, consulter les recommandations actuelles du fournisseur et l'état de l'art pertinent.

Les techniques de prompting sont des connaissances évolutives, pas des vérités permanentes.

---

<a id="p18"></a>
### P18 — Séparation jugement / mécanique dans les systèmes IA

Le jugement probabiliste propose. Le système déterministe garantit les invariants critiques.

##### Déclencheur

Chaque conception ou modification d'un système intégrant un LLM.

##### Application

Séparer :

#### Jugement

Adapté au LLM :

- interprétation ;
- classification ;
- génération ;
- planification ;
- diagnostic ;
- choix parmi plusieurs possibilités ;
- compréhension d'intention.

#### Mécanique

Adaptée au déterministe :

- validation de schéma ;
- vérification d'autorisation ;
- contraintes de sécurité ;
- calcul exact ;
- gestion de l'état critique ;
- transactions ;
- invariants ;
- exécution sensible.

Principe :

> L'autorité accordée au LLM diminue lorsque le coût potentiel d'une erreur augmente.

Exemples :

##### Faible risque

```text
LLM
→ écrit dans un environnement isolé
→ tests automatiques
→ résultat
```

##### Risque intermédiaire

```text
LLM
→ propose une action structurée
→ validation déterministe
→ exécution
→ feedback
```

##### Risque élevé

```text
LLM
→ propose
→ validation déterministe
→ validation humaine ou politique
→ transaction contrôlée
→ audit
```

Une donnée critique doit idéalement être référencée depuis une source d'autorité plutôt que reconstruite librement par le LLM.

---

<a id="p19"></a>
### P19 — Source d'autorité unique

Une information critique doit posséder une source canonique identifiable.

##### Déclencheur

Lorsqu'une même information existe ou pourrait exister dans plusieurs composants, fichiers, bases ou agents.

##### Application

Identifier :

- qui possède l'état ;
- qui peut le modifier ;
- qui peut seulement le lire ;
- comment les autres composants y font référence.

Éviter les copies indépendantes d'une même vérité métier.

Principe :

> Référencer une vérité est préférable à la recopier lorsque sa cohérence doit être garantie.

---

<a id="p20"></a>
### P20 — Observer avant d'optimiser

Une optimisation sans mesure de référence est une préférence, pas une optimisation.

##### Déclencheur

Avant :

- optimisation de performance ;
- refactoring motivé par la performance ;
- réduction de coût ;
- optimisation d'un workflow ;
- modification destinée à accélérer un système.

##### Application

Définir :

1. métrique actuelle ;
2. valeur de référence ;
3. objectif ;
4. modification ;
5. mesure après modification.

Comparer avant/après.

Sans baseline observable, ne pas déclarer une amélioration.

---

<a id="p21"></a>
### P21 — Une hypothèse doit pouvoir mourir

Une hypothèse utile doit définir ce qui pourrait la réfuter.

##### Déclencheur

Lorsqu'une explication, une prédiction ou une stratégie repose sur une hypothèse incertaine.

##### Application

Formuler :

- l'hypothèse ;
- ce qu'elle prédit ;
- l'observation qui la soutiendrait ;
- l'observation qui la réfuterait.

Éviter les hypothèses capables d'expliquer tous les résultats possibles.

Question :

> Qu'est-ce qui me ferait changer d'avis ?

Si aucune réponse n'existe, ce n'est probablement pas une hypothèse testable.

---

<a id="p22"></a>
### P22 — Capitaliser après apprentissage

Une expérience n'est pleinement utile que si son apprentissage peut influencer une décision future.

##### Déclencheur

Après :

- incident ;
- expérience ;
- décision importante ;
- échec ;
- optimisation ;
- investigation longue.

##### Application

Conserver uniquement ce qui mérite d'être réutilisé :

- faits importants ;
- décision prise ;
- raison ;
- résultat observé ;
- règle éventuellement généralisable.

Ne pas documenter mécaniquement tout ce qui s'est produit.

Transformer une expérience en principe uniquement lorsque le pattern semble suffisamment général pour être réutilisé.

---

### Résumé opérationnel

Lorsqu'une situation nouvelle apparaît :

```text
Est-ce le bon problème ?
        ↓
Est-il réellement important ?
        ↓
Que dit le réel ?
        ↓
Qu'est-ce qui est fait, hypothèse ou inconnu ?
        ↓
Quelle est la cause ?
        ↓
Quelle est la réversibilité ?
        ↓
Quel downside puis-je accepter ?
        ↓
Quelle est l'action minimale ?
        ↓
Quel signal dois-je observer ?
        ↓
Exécuter
        ↓
Observer
        ↓
Corriger
        ↓
Optimiser si nécessaire
        ↓
Capitaliser si réutilisable
```

---

### Règle ultime

La complexité, l'analyse et l'infrastructure ne sont jamais des objectifs.

Elles ne sont justifiées que lorsqu'elles permettent de mieux :

- comprendre le réel ;
- prendre une décision ;
- exécuter une action ;
- limiter le risque ;
- apprendre ;
- ou augmenter durablement la capacité future.

Lorsque deux solutions remplissent également ces objectifs :

> choisir la plus simple.

Provenance : texte fourni par le responsable du projet, version 2, intégré
le 8 octobre 2026 ; contenu conservé, seuls les niveaux de titres et les
identifiants P01–P22 sont adaptés au document vivant. Empreinte SHA-256 de
la pièce jointe : `49872e3caadea148a8ecb2f1edd9953bdd95c1debe26b63b7edb21069aed5bf5`.

<a id="refonte-systeme-cartographe"></a>
### Variante système du cartographe — 10 novembre 2026

La variante système sans dock poursuit la priorité ORCH-CAO-MASSE-1 par la
réconciliation des ports et de leur implantation. PX4 conserve l'autorité
de vol et les interfaces de perception restent inchangées dans A. Le choix
de A concerne l'intégration CAO sur copie. B et C restent des architectures
d'étude avec réservations d'encombrement. Le choix de production reste
**À valider**. Les écarts de masses, de critères physiques et de datation
identifiés dans DOC-VAL §15 restent ouverts.

Le [registre des architectures](../../verification/architectures.json) fixe
les exigences impératives, les critères, leur pondération et les conditions
de bascule. [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#interconnexion-refonte-systeme)
porte le graphe. [DOC-MEC](ARCHITECTURE_MECANIQUE.md#implantation-refonte-systeme)
porte le modèle et la comparaison. [DOC-VAL](../VALIDATION_QUALIFICATION.md#validation-refonte-systeme)
porte les essais et limites.

## Journal de modifications

- **10 novembre 2026** — Choix A sur copie après comparaison d'architectures. Clôture physique ouverte.


| Date | Modification |
|---|---|
| 26 octobre 2026 | Masse du kit d'approvisionnement renseignée ; estimations de pièces X650 par densités analogues et scénarios de propulsion distingués du bilan vérifié (§1.1). |
| 26 octobre 2026 | Reprise ORCH : correction des collisions, attribution poursuivie et problèmes explicites dans chaque ligne BOM ; poids commerciaux ambigus maintenus conditionnels, revue indépendante et suspension des campagnes conservées (§1.1). |
| 25 octobre 2026 | ORCH-CAO-MASSE-1 devient prioritaire : complétude géométrique et massique du prototype, grades/procédés candidats autorisés ; nouvelles capacités et campagnes Gazebo/PX4 suspendues, inconnues bloquantes locales sans arrêt des travaux indépendants (§1.1, DOC-VAL §14). |
| 24 octobre 2026 | Passerelle CAO → Gazebo intégrée à Simulations : service UI/CLI commun, export isolé et contrôlé, aperçu navigable, annulation et tests ; chargement Gazebo réel, physique À valider (DOC-VAL §10.2). |
| 24 octobre 2026 | ORCH-GZ-1 : banc Docker/ROS reconstruit, airframe 40000 et capteurs synthétiques corrigés ; six essais SITL courants carré/perte Offboard/annulation finalisés, T0 et revue indépendante ; batterie forfaitaire observée, fidélité physique et autonomie couplée À valider (DOC-VAL §9.3). |
| 23 octobre 2026 | ORCH-GZ-1 réalisé sur les chemins indépendants du moteur Docker : dérivation, SDF exploratoire, calculs et tests natifs ; essais SITL et autonomie couplée restant ouverts, priorité physique conservée. |
| 23 octobre 2026 | Périmètre Gazebo confirmé sur les trois domaines, séquencés entre orchestrateurs : portance/énergie, dynamique, capteurs/cartographie ; conditions de reprise référencées dans DOC-VAL §9.4. |
| 23 octobre 2026 | Orientation Gazebo précisée : réemploi du prototype 3D actif pour étudier portance, consommation et autonomie ; dérivation et validation Planifiées, précision physique À valider (DOC-MEC §2.3, DOC-VAL §9.3). |
| 23 octobre 2026 | Chantier station V3 explicitement demandé, borné et relié à DOC-SW ; préparation locale des missions distinguée de l'exécution PX4 et des validations physiques encore ouvertes. |
| 22 octobre 2026 | Refonte prototype poursuivie en place : énergie haute, caméra conservée, faisceaux et retenues ; configuration contrôlée référencée dans DOC-MEC/DOC-VAL, priorité aux interfaces des lots et aux essais physiques sans nouvelle fonctionnalité. |
| 12 octobre 2026 | Précision utilisateur : terminal au sol portable/tablette/téléphone, choix selon ergonomie ; chargeur60 W hypothétiques. Deux sélections différées hors CAO,18 compléments embarqués ; aucun natif ni logiciel modifié. |
| 12 octobre 2026 | Reconstruction prototype et contrôles géométriques consolidés ; priorité inchangée : fermer les détails résiduels, inventorier puis mesurer, sans déduire une qualification physique de la CAO (§1.1). |
| 11 octobre 2026 | Reprise CAO demandée après consolidation de la BOM : Prototype_Cartographe devient actif, sept sous-assemblages et références utiles réemployées ; construction Implémenté, vérification finale en cours, faisabilité physique À valider (§1.1). |
| 10 octobre 2026 | Minimum du portable de terrain accepté pour la définition ; matériel et performances À valider, PC fixe de traitement distinct (§7). |
| 10 octobre 2026 | PC au sol du prototype : portable de récupération envisagé pour supervision/RTK/transfert, distinct du PC fixe de traitement existant ; minimum candidat dans DOC-ELEC, aucun portable identifié ou qualifié (§7). |
| 10 octobre 2026 | Prototype : JETI et commande magnétique retirés, marche/arrêt par branchement/débranchement et QS8-S B9310 choisis ; qualification ouverte, définition dock héritée distinguée ; conservation de toutes les données brutes LiDAR/caméra pendant la mission demandée (§1.1, §5, §7). |
| 10 octobre 2026 | Deux nomenclatures séparées prototype/produit custom, avec vues système ; niveau fonctionnel du produit ultérieur et priorité prototype maintenus. |
| 9 octobre 2026 | Périmètre prototype sans échange rapide retenu pour sa nomenclature ; autorité du registre et séparation de l'étude CAO avec dock précisées, faisabilité toujours À valider. |
| 8 octobre 2026 | Proposition de deux étapes prototype sur sélection cible actuelle puis produit custom ; périmètre À valider, sans migration CAO ni changement des exigences existantes. |
| 8 octobre 2026 | Adoption des 22 préceptes comme méthode canonique, priorité donnée à la faisabilité physique du cartographe, cadrage et critères d'arrêt ; statut CA01 distinguant conception et qualification. |
| 5 octobre 2026 | Batterie et récepteur distingués, énergie directement dans le principal ; sûreté conservée, migration et réouverture contrôlées sans déplacement des pièces ni qualification physique. |
| 5 octobre 2026 | Raccordement pack/BMS/TE compact : gain local cassette et énergie depuis1ccbad81, enveloppe d’intégration inchangée ; BMS supérieur, autorité PX4 et limites de qualification conservés. |
| 5 octobre 2026 | Première implantation supérieure historique Git1ccbad81 : BMS placé au-dessus du pack, plateau rehaussé et connecteur rapproché ; compacité CAO mesurée par périmètre, cassette seule plus haute, sans qualification du drone complet ni changement d’autorité PX4. |
| 5 octobre 2026 | BMScommercialJBD/TE/UARTisolé intégrés enCAO etschéma ; diagnosticlogicielPlanifié, PM08 conservé sourcePX4, physiqueÀvalider |
| 5 octobre 2026 | Besoininitial BMS embarqué dans chaque cassette cartographe requis ; protections et alertes coordonnées avec PX4, défaillance d'énergie commune et absence de contournement explicitées ; intégration Planifiée / À valider |
| 3 octobre 2026 | Dock 6S 20 Ah et coupure JETI en tête du PM08 ; causes de défaillance communes et échange au sol explicités, sans changement de l'autorité de PX4 ; CAO historique et cible Holybro/CA01 distinguées |
| 30 septembre 2026 | Responsabilités temporelles clarifiées : décision de capture Jetson/ROS 2, impulsion PX4 et adaptation CA01 ; flux continus associés au temps réel d'exposition, autorité unique et distinction PPS/cadence ; cible Planifié / À valider |
| 25 septembre 2026 | synchronisation cartographe cible : Rover Helical STM32G4 PPS candidat, CA01 distribution du temps, AUX PX4 vers Basler et retour ExposureActive vers capture Pixhawk ; horloges et ports à qualifier |
| 24 septembre 2026 | sélection Rover/Base Holybro F9P ; correction RTCM visée via RF commun, commandes sol ponctuelles et télémétrie sous budget à valider |
| 24 septembre 2026 | cible Pixhawk Jetson Baseboard avec Pixhawk 6X module et Orin NX 16 Go ; BEC1/2 vers POWER1/POWER2, CAN1 séparé, CA01 5 V local protégé et porteuse via XT30/12 V candidat ; CAO et KiCad non migrés |
| 22 septembre 2026 | cible PM08-CAN fixe sur châssis près de la distribution ; BEC1 vers POWER1/vol/radio, BEC2 vers CA01 auxiliaires/synchronisation, mesure DroneCAN CAN1 ; retrait buck 5 V auxiliaire planifié, CAO et circuits KiCad V0.3 non migrés |
| 22 septembre 2026 | PM02D complet en tête de distribution avec faisceau adapté ; BEC conservé hors CA01 ; support sur cassette à étudier ; simulation distincte de qualification électrique |
| 21 septembre 2026 | PM02D retiré du périmètre CA01, support séparé et liaison directe à POWER1 ; radio alimentée depuis le domaine vol via dérivation protégée à définir ; CAO inchangée |
| 17 septembre 2026 | carte avionique commune CA01 planifiée, radio sur branche vol et PM02D rapporté candidat ; renvoi au cahier des charges, limites du schéma et de la CAO existante |
| 16 septembre 2026 | clarification AUTO/MANU des deux drones, balayage sur relief, supervision QGC et pertes ; présélection RF commune et exigences/tests associés |
| 13 septembre 2026 | intégration des décisions actives de déploiement, d'approbation, de transfert et de présélection ; retrait du registre ADR |
| 10 septembre 2026 | création puis consolidation des exigences historiques, performances, environnement et budget système |
