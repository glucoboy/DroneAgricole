# ADR-0011 — Fermeture de SW0 et qualification ARM native

- Statut : accepté
- Date : 5 septembre 2026

## Contexte

SW0 doit fournir une baseline logicielle récupérable avant le lot B1. Les
constructions et tests Windows ainsi que les images Linux `amd64` sont
reproductibles localement. Les scénarios PX4 SITL du carré et de la perte
Offboard produisent leurs preuves rechargeables. La campagne LIO complète de
clôture est exécutée sur BotanicGarden à `1×`, avec au moins trois répétitions
par candidat retenu dans DOC-29.

Le noyau propriétaire C++17/ROS 2 a aussi été construit et exécuté en
`linux/arm64`. En revanche, la construction LIO-SAM complète sous émulation QEMU
a saturé le moteur Docker Windows malgré un parallélisme réduit à un travail.
Une construction émulée ne qualifierait de toute manière ni JetPack, ni les
performances, ni le comportement thermique d'un Jetson. Aucun dépôt distant
n'est configuré et le smoke Qt conteneurisé sans serveur graphique ne démontre
pas le rendu OpenGL réel.

La clôture de SW0 doit donc distinguer une baseline de développement locale
d'une qualification de déploiement embarqué.

## Décision

Fermer SW0 lorsque les critères locaux de DOC-29 sont satisfaits et que la
baseline est organisée en commits Git relus. L'absence de forge distante et la
non-production de l'image LIO/Qt arm64 complète sous QEMU ne bloquent pas le
démarrage de B1, car ces points ne remettent pas en cause la récupérabilité du
socle ni ses preuves `amd64`.

La fermeture est assortie des conditions obligatoires suivantes :

1. construire les images LIO/Qt sur un hôte ARM64 natif ou un Jetson avant de
   déclarer une baseline embarquée candidate ;
2. qualifier séparément JetPack à `1×`, avec CPU, mémoire, température,
   stabilité et marge temps réel ; les seuils restent **À valider** ;
3. exécuter le workflow versionné sur une forge dès qu'un dépôt distant est
   créé, avant toute livraison collaborative ;
4. valider le rendu Qt/OpenGL sur un poste disposant du serveur graphique et du
   GPU appropriés avant de considérer l'affichage conteneurisé comme qualifié ;
5. ne déduire de cette fermeture aucune qualification de vol réel, de matériel
   embarqué ou de pulvérisation.

PX4 demeure responsable des fonctions critiques de vol et des failsafes. ROS 2
reste limité aux consignes de haut niveau et aux fonctions avancées.

## Conséquences

- B1 peut démarrer sur une baseline C++17/Qt 6 récupérable et testée localement ;
- les réserves ARM native, JetPack, CI distante et rendu OpenGL restent visibles
  dans DOC-29 et `PROJECT_CONTEXT.md` ;
- tout résultat ARM émulé est une preuve de portabilité de construction, pas une
  mesure de performance embarquée ;
- le choix définitif du Jetson et les enveloppes CPU/RAM/thermiques restent
  **À valider** ;
- les résultats, rosbags, datasets et autres artefacts volumineux restent hors
  Git, mais leurs chemins et synthèses sont tracés dans la documentation ;
- cette décision pourra être révisée si une qualification native invalide une
  hypothèse de portabilité ou de capacité.

## Alternatives écartées

- Maintenir SW0 ouverte jusqu'à la disponibilité d'une forge : la forge est une
  dépendance organisationnelle externe, tandis que le workflow et ses commandes
  locales équivalentes sont déjà versionnés et vérifiés.
- Poursuivre les builds LIO complets sous QEMU sur le poste actuel : deux essais
  ont reproduit la saturation et l'arrêt de Docker ; ils n'apporteraient pas la
  qualification Jetson recherchée.
- Présenter le noyau ARM64 comme une qualification embarquée complète : il ne
  couvre ni les trois moteurs LIO, ni Qt, ni JetPack, ni les performances.
- Supprimer les réserves de la porte SW0 : cela confondrait clôture de baseline,
  qualification de plateforme et aptitude au vol.

## Preuves de mise en œuvre

Le détail des versions, tests, empreintes d'images, campagnes LIO, résultats PX4
et réserves est maintenu dans DOC-29. La décision est considérée appliquée quand
la matrice de sortie de ce document est complète et que le commit de clôture ne
laisse aucun changement suivi non commité.
