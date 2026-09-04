# ADR-0006 — C++17 et Qt 6 pour le logiciel propriétaire

- Statut : accepté
- Date : 30 août 2026
- Remplace pour l'interface les choix Web/Python décrits avant T0
- Complète : ADR-0002, ADR-0003 et ADR-0005

## Contexte

Le socle T0 a validé les contrats, les runners, l'historique et la comparaison avec un serveur Python et une interface Web locale. Cette combinaison a permis de qualifier rapidement le workflow, mais elle multiplie les langages, sépare la mise en page de l'application native et ne correspond plus à la contrainte de maintenance retenue pour la suite du projet.

Le projet impose désormais un langage commun pour les composants propriétaires et une interface graphique desktop éditable avec les outils Qt.

## Décision

Toute logique exécutable propriétaire nouvelle ou maintenue est écrite en **C++17**.

L'interface opérateur devient une application desktop **Qt 6 Widgets**. Les fenêtres, dialogues, panneaux, menus et formulaires sont décrits au maximum dans des fichiers `.ui` compatibles avec Qt Designer, Qt Creator et les extensions Qt pour Visual Studio Code. Seuls les widgets de visualisation spécialisés, les modèles de données et les comportements dynamiques sont écrits en C++.

Le projet utilise CMake comme système de construction. Les tests C++ sont intégrés à CTest ; les composants Qt utilisent Qt Test lorsque cela apporte une validation d'interface ou de signaux.

La fermeture de la migration repose sur trois livrables exécutables explicites :

- `drone-agricole-dashboard`, application Qt 6 desktop et client des runners ;
- `drone-agricole-tools`, outil C++17 multi-commandes pour l'adaptation BotanicGarden, l'orchestration LIO, le profilage, l'analyse de trajectoire et les synthèses de campagne ;
- le paquet ROS 2 `drone_agricole_px4_bridge`, construit avec `ament_cmake` et `rclcpp`, qui fournit le pont d'état, l'essai Offboard et le runner réseau SITL.

Les commandes de campagne sont lancées comme processus C++ directs. Les scripts Python, shell ou PowerShell du dépôt ne constituent plus une couche d'orchestration autorisée. Les entrypoints standards fournis par les images ROS restent des dépendances externes ; les environnements des workspaces colcon sont exposés par l'image Docker sans script propriétaire.

Les formats suivants restent autorisés hors C++ parce qu'ils sont déclaratifs ou nécessaires à la construction et à l'intégration :

- fichiers Qt `.ui` et `.qrc` ;
- CMake, manifestes ROS 2, messages et fichiers de configuration ;
- contrats JSON Schema et catalogues JSON/YAML ;
- Dockerfiles et mécanismes déclaratifs d'environnement, sans logique métier propriétaire.

Python, JavaScript, TypeScript, HTML et CSS ne font plus partie de l'architecture cible propriétaire. Le code existant dans ces langages doit être porté vers les bibliothèques et exécutables C++, puis supprimé du chemin d'exécution actif. Une conservation temporaire n'est admise que pendant une migration tracée et ne constitue pas un état final accepté.

Le tableau de bord Qt conserve les propriétés validées par T0 :

- lecture et validation des contrats versionnés ;
- catalogue générique des simulations et runners ;
- validation stricte des paramètres, entrées et chemins ;
- une seule exécution active tant qu'une file n'est pas validée ;
- index reconstruisible depuis les résultats immuables ;
- rechargement, comparaison, superposition et export de rapport ;
- runners headless autonomes et testables sans interface graphique.

Sur un poste desktop natif, le client C++ du runner PX4 vérifie l'API locale avant un essai. Si elle est indisponible, il démarre les services Docker Compose explicitement approuvés du profil SITL, attend leur disponibilité puis transmet la requête au runner. L'API n'est publiée que sur l'interface de boucle locale. Dans un environnement Docker déjà connecté au réseau Compose, cette préparation automatique reste désactivée et l'URL interne est fournie par variable d'environnement.

Cette préparation ne déclenche pas l'essai Offboard à elle seule : le démarrage effectif exige toujours la requête validée du tableau de bord, le runner autorisé et le verrou SITL. Le runner reste autonome et appelable sans l'interface graphique.

La frontière de sûreté ne change pas. PX4 assure le vol critique et les failsafes. ROS 2 fournit des consignes et fonctions avancées. L'application Qt orchestre les essais autorisés et affiche leur état, mais ne commande jamais directement les actionneurs et ne remplace pas QGroundControl.

## Conséquences

- le serveur HTTP et l'interface Web T0 sont remplacés par une application desktop ;
- les contrats et archives T0 restent compatibles et ne sont pas réécrits ;
- les bridges ROS 2, adaptateurs de datasets, runners et outils d'analyse propriétaires migrent vers des paquets et exécutables C++17 ;
- la construction doit rester reproductible pour `amd64` et `arm64` ;
- les widgets spécialisés peuvent être codés en C++, mais leur emplacement et leurs propriétés configurables restent déclarés dans les `.ui` ;
- le lancement depuis le poste Windows ne dépend plus d'un démarrage Docker manuel préalable, tandis que le service réseau PX4 reste isolé sur `localhost` ;
- chaque port conserve la traçabilité `exigence -> composant/algorithme -> test -> résultat` ;
- la parité fonctionnelle T0 doit être démontrée avant suppression définitive de l'ancienne implémentation.

La version minimale précise de Qt 6 supportée sur Windows, Ubuntu `amd64` et Ubuntu `arm64` reste **À valider** par la matrice de construction. Le code cible uniquement les API Qt 6 et C++17.

## Alternatives rejetées

- Conserver le serveur Python avec une coque Qt : maintient deux piles applicatives et ne respecte pas la contrainte C++.
- Embarquer la page existante dans Qt WebEngine : conserve JavaScript/HTML/CSS et rend les fichiers `.ui` secondaires.
- Utiliser QML comme interface principale : puissant pour les vues dynamiques, mais moins conforme à l'objectif d'édition maximale dans Qt Designer avec des fichiers `.ui` Widgets.
- Réécrire les archives T0 lors de la migration : détruit la reproductibilité et la compatibilité historique.
