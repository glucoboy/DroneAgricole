# Simulation

Le premier socle exécute PX4 SITL avec Gazebo Harmonic dans un conteneur
officiel séparé. Le véhicule par défaut est un `x500`, dans le monde `default`,
sans interface graphique native. Le pont du lot A raccorde PX4 à ROS 2 Jazzy
par uXRCE-DDS et transmet son état à l'application desktop Qt 6.

Le point d'entrée opérateur est `drone-agricole-dashboard`. L'application
affiche la pose PX4, sa trajectoire, son mode, son armement, sa batterie et ses
états de sécurité. Elle lance le client C++ verrouillé et démarre le banc Docker
SITL local lorsqu'il n'est pas déjà disponible. Il n'existe plus de dashboard
Web ni de service sur le port 8080.

Démarrage manuel équivalent du banc et de l'API locale :

```powershell
docker compose --profile sim --profile viz up -d px4-runner-api
Invoke-RestMethod http://127.0.0.1:8091/api/health
```

L'API de lancement est publiée uniquement sur `127.0.0.1:8091`. Le pont de
télémétrie LIO utilise séparément `127.0.0.1:8092`.

QGroundControl écoute le flux MAVLink de PX4 sur le port UDP 14550 de Windows. Le port UDP 8888 est réservé à l'Agent uXRCE-DDS conteneurisé.

Essai de trajectoire carrée, uniquement en SITL :

```powershell
$env:PX4_OFFBOARD_EXECUTE = "true"
$env:PX4_OFFBOARD_MODE = "square"
docker compose --profile flight-test run --rm --no-deps px4-offboard-test
$env:PX4_OFFBOARD_EXECUTE = $null
```

Essai de perte Offboard et d'atterrissage automatique :

```powershell
$env:PX4_OFFBOARD_EXECUTE = "true"
$env:PX4_OFFBOARD_MODE = "failsafe"
docker compose --profile flight-test run --rm --no-deps px4-offboard-test
$env:PX4_OFFBOARD_EXECUTE = $null
```

Le nœud refuse d'émettre des commandes si le verrou d'environnement `DRONE_AGRICOLE_SITL=1` ou le paramètre explicite `execute:=true` manque. Il ne publie aucune commande d'actionneur : PX4 conserve l'asservissement, l'armement, les modes et les actions de sécurité.

Arrêt du socle PX4 :

```powershell
docker compose --profile sim --profile viz stop px4-runner-api px4-sitl px4-state-bridge micro-xrce-dds-agent
```

Les réglages `COM_RC_IN_MODE`, `NAV_RCL_ACT`, `NAV_DLL_ACT` et `COM_RCL_EXCEPT` du fichier Compose isolent volontairement la perte Offboard des pertes RC/GCS pendant ce test headless. Ils sont strictement réservés au banc SITL et ne constituent pas une configuration du drone réel.

Le protocole, les versions, les résultats et les limites sont consolidés dans
`docs/VALIDATION_QUALIFICATION.md`, y compris la reprise des deux scénarios avec
le port C++ actif de SW0.

Structure cible :

```text
simulation/
├── px4_sitl/
├── gazebo/
│   ├── models/
│   └── worlds/
├── scenarios/
│   └── VINEYARD_BENCH_V01/
├── fault_injection/
└── tests/
```

La définition officielle des dix scénarios se trouve dans `docs/VALIDATION_QUALIFICATION.md`. Les mondes doivent fournir une vérité terrain, des paramètres versionnés, des fautes injectables et des critères d'acceptation automatiques, au-delà du seul réalisme visuel.
