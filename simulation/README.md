# Simulation

Le premier socle exécute PX4 SITL avec Gazebo Harmonic dans un conteneur officiel séparé. Le véhicule par défaut est un `x500`, dans le monde `default`, sans interface graphique native. Le pont du lot A raccorde maintenant PX4 à ROS 2 Jazzy par uXRCE-DDS et transmet son état au tableau de bord 3D.

Le tableau de bord 3D local introduit dans DOC-12 fournit le rendu WebGL, les graphiques temps réel et les commandes de lancement/arrêt pour les rejeux LIO. Il affiche également la pose PX4, sa trajectoire, son mode, son armement, sa batterie et ses états de sécurité. Cette voie évite de dépendre d'une interface graphique Linux à travers Docker Desktop.

Démarrage de PX4, de l'Agent uXRCE-DDS et du pont d'état :

```powershell
docker compose --profile sim up -d micro-xrce-dds-agent px4-state-bridge px4-sitl
docker compose --profile viz up -d fast-lio-dashboard
```

Accès au tableau de bord :

- depuis le PC : `http://127.0.0.1:8080` ;
- depuis le réseau local : `http://192.168.1.25:8080`.

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

Arrêt du socle :

```powershell
docker compose --profile sim stop px4-sitl px4-state-bridge micro-xrce-dds-agent
```

Les réglages `COM_RC_IN_MODE`, `NAV_RCL_ACT`, `NAV_DLL_ACT` et `COM_RCL_EXCEPT` du fichier Compose isolent volontairement la perte Offboard des pertes RC/GCS pendant ce test headless. Ils sont strictement réservés au banc SITL et ne constituent pas une configuration du drone réel.

Le protocole complet, les versions, les résultats et les limites sont consignés dans `docs/18_Integration_PX4_ROS2_Lot_A_V0.1.md`.

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

La définition officielle des dix scénarios se trouve dans `docs/03_Plan_validation_simulation_V0.1.md`. Les mondes doivent fournir une vérité terrain, des paramètres versionnés, des fautes injectables et des critères d'acceptation automatiques, au-delà du seul réalisme visuel.
