---
name: drone-agricole-px4-sitl
description: "Préparer, modifier, exécuter ou analyser le banc PX4 SITL, Gazebo, uXRCE-DDS et les scénarios Offboard ou failsafe du projet Drone Agricole. Ne pas utiliser pour commander un drone réel ni transférer des paramètres de simulation vers le matériel."
---

# Banc PX4 SITL du Drone Agricole

Conserver la séparation de sûreté : PX4 assure le vol critique ; ROS 2 fournit uniquement des consignes de haut niveau et des fonctions avancées que PX4 peut refuser.

## Lire le banc courant

Avant de proposer une commande ou une modification, lire :

- `simulation/README.md` pour les profils, ports, scénarios et limites du banc ;
- `compose.yaml` pour les services, variables, images et paramètres effectivement configurés ;
- `docs/architecture/HLD.md` (`DOC-HLD`) pour les scénarios et frontières système ;
- `docs/architecture/ARCHITECTURE_LOGICIELLE.md` (`DOC-SW`) pour les modules, contrats et responsabilités ROS 2/PX4 ;
- `docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md` (`DOC-ELEC`) si le changement touche les liaisons, ports, horloges ou interfaces ;
- `docs/VALIDATION_QUALIFICATION.md` (`DOC-VAL`) pour les scénarios officiels, critères, résultats de référence et limites.

Inspecter le code du runner ou du pont uniquement si la tâche le modifie ou si le comportement observé l'exige. Vérifier les manifestes et artefacts du résultat ciblé avant d'en tirer une conclusion.

## Garder les verrous de sûreté

- Limiter l'exécution aux services et profils explicitement SITL.
- Exiger les deux autorisations prévues avant toute émission Offboard : le verrou d'environnement `DRONE_AGRICOLE_SITL=1` dans l'environnement d'exécution et le paramètre explicite `execute:=true`. Respecter en plus le verrou opérateur `PX4_OFFBOARD_EXECUTE=true` lorsque le point d'entrée courant l'utilise.
- Ne jamais publier de commande directe d'actionneur ou de moteur. PX4 conserve asservissement, armement, modes, géofence et failsafes.
- Refuser l'exécution si l'identité SITL, le verrou ou la cible est ambiguë. Ne pas contourner un refus du runner.
- Ne jamais connecter ce workflow à un aéronef réel, même pour un essai jugé équivalent.

Les paramètres de perte Offboard ou d'isolation RC/GCS présents dans Compose sont des réglages de banc headless. Toute modification doit rester confinée au banc et être décrite comme **À valider** pour le matériel ; ne pas la présenter comme configuration finale du drone.

## Modifier ou exécuter un scénario

Réutiliser les profils, services, ports et modes déclarés dans `simulation/README.md` et `compose.yaml` plutôt que d'en inventer. Préserver les interfaces locales existantes et signaler tout conflit de port.

Pour un nouveau scénario ou une injection de faute, définir :

- l'identifiant et le but ;
- l'état initial, la mission et la configuration versionnée ;
- la vérité terrain et les événements attendus ;
- la faute injectée, son instant et son observabilité ;
- les critères d'acceptation automatiques ;
- les artefacts nécessaires à la reproductibilité.

Tester aussi le refus quand un verrou manque si le chemin d'autorisation change. Une simulation réaliste visuellement sans vérité terrain ni critère mesurable ne constitue pas une validation.

## Produire une preuve bornée

Associer chaque exécution à l'environnement, aux versions/images, à la configuration, au scénario, aux timestamps, aux événements PX4, aux métriques et à la conclusion. Conserver les artefacts détaillés dans le répertoire de résultats prévu et reporter la synthèse dans `DOC-VAL` ; mettre à jour `DOC-SW`, `DOC-ELEC` ou `DOC-HLD` seulement si leur contenu change.

Conclure `conforme`, `non conforme`, `préliminaire` ou **À valider** dans le périmètre réellement exécuté. Un succès SITL ne qualifie pas le matériel, le réseau embarqué, les paramètres de vol réels ni une campagne physique. Rapporter les validations réussies, échouées et non exécutées avec leur raison.
