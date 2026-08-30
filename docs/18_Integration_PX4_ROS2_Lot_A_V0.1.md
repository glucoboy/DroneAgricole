# Intégration PX4–ROS 2 et validation SITL — Lot A

| Champ | Valeur |
|---|---|
| Référence | DOC-18 |
| Version | V0.1 |
| Date | 20 août 2026 |
| Statut | Opérationnel préliminaire |
| Périmètre | PX4 SITL, Gazebo Harmonic, ROS 2 Jazzy, uXRCE-DDS, QGroundControl et tableau de bord |
| Véhicule | `gz_x500`, monde Gazebo `default` |

## 1. Conclusion

Le lot A est opérationnel sur le poste de développement. PX4 SITL communique avec ROS 2 Jazzy par uXRCE-DDS, le pont publie une odométrie ROS en ENU et le tableau de bord affiche l'état et la trajectoire du véhicule en temps réel.

Deux essais contrôlés ont été validés :

- une trajectoire carrée de 2 m de côté à environ 2 m d'altitude, suivie d'un atterrissage et d'un désarmement propres ;
- une coupure volontaire du flux Offboard, détectée par PX4 après 1,099 s, puis traitée par un passage autonome en `AUTO_LAND` jusqu'au posé.

Cette validation prouve l'architecture logicielle et le mécanisme de sécurité dans le banc SITL. Elle ne qualifie pas encore un drone réel, un capteur physique, un environnement viticole ni une liaison QGroundControl observée manuellement.

## 2. Architecture validée

```text
QGroundControl sous Windows
          ↕ MAVLink UDP 14550
PX4 SITL + Gazebo Harmonic
          ↕ uXRCE-DDS UDP 8888
Micro XRCE-DDS Agent 2.4.3
          ↕ DDS, domaine ROS 42
ROS 2 Jazzy
  ├── state_bridge, lecture seule
  │     ├── odométrie ENU, TF et chemin
  │     ├── état de vol et batterie
  │     └── diagnostics
  ├── tableau de bord 3D
  └── offboard_test, profil isolé et doublement verrouillé
          ↓ consignes de position NED
        PX4
```

PX4 conserve les boucles d'asservissement, les modes, l'armement et les actions de sécurité. ROS fournit l'observation et, uniquement pendant un essai explicite, des consignes de position de haut niveau.

## 3. Versions gelées

| Composant | Version ou révision |
|---|---|
| Image PX4 SITL Gazebo | `v1.18.0-beta2` |
| Digest de l'image | `sha256:bcf8278e3321948be2266568528107dbfd94eb6fa703171cb013bc4d54dc8ef8` |
| Révision PX4 embarquée | `83c4f4e580558816f0e398918f66358988004696` |
| `px4_msgs`, branche `release/1.18` | `598c7aad7b2386f9406ebd2a2f841619fddc3c78` |
| Micro XRCE-DDS Agent | `2.4.3`, révision `73622810d984349b80bbac0ef55fc0b694d62222` |
| ROS 2 | Jazzy, Ubuntu 24.04 |
| Domaine ROS | `42` |

Les 64 types référencés par le fichier `dds_topics.yaml` du firmware ont été comparés aux types `px4_msgs` épinglés : 64 sur 64 sont identiques au niveau source. Les sorties versionnées observées, notamment `vehicle_status_v4`, `battery_status_v1` et `vehicle_command_ack_v1`, sont prises en charge explicitement.

La version PX4 utilisée est une bêta. Son remplacement par une version stable et le nouveau gel des trois révisions sont obligatoires avant une campagne formelle.

## 4. Interfaces ROS du lot A

| Interface | Rôle | Repère ou format |
|---|---|---|
| `/drone/px4/odometry` | pose, orientation et vitesses | ENU / FLU |
| `/drone/px4/path` | trajectoire bornée pour affichage | ENU |
| `/drone/px4/state_json` | état synthétique du tableau de bord | JSON versionné par le pont |
| `/diagnostics` | disponibilité et fraîcheur des topics PX4 | messages ROS de diagnostic |
| `/tf` | transformation `map` vers `base_link` | ENU / FLU |
| `/fmu/in/offboard_control_mode` | activation de la consigne de position | natif PX4 |
| `/fmu/in/trajectory_setpoint` | consigne Offboard | NED |
| `/fmu/in/vehicle_command` | changement de mode, armement et désarmement de test | natif PX4 |

Le pont d'état a été observé à environ 100 Hz sur l'odométrie. L'état, la batterie, les informations de sécurité et la trajectoire étaient présents avec une fraîcheur inférieure à une seconde.

## 5. Repères et conversions

PX4 expose la navigation en NED avec un corps FRD. ROS et le tableau de bord utilisent ENU avec un corps FLU. Le pont applique :

```text
position : (x_enu, y_enu, z_enu) = (y_ned, x_ned, -z_ned)
vitesse  : même permutation et inversion verticale
attitude : conversion complète NED/FRD vers ENU/FLU par matrices de rotation
```

Six tests unitaires couvrent les axes, positions, vecteurs, quaternion identité, rotations autour de l'axe vertical et normalisation.

## 6. Sécurité de l'essai Offboard

Le service `px4-offboard-test` appartient uniquement au profil `flight-test`. Son exécution exige simultanément :

1. l'environnement interne `DRONE_AGRICOLE_SITL=1`, fixé uniquement dans le service d'essai ;
2. le paramètre ROS `execute:=true`, issu de `PX4_OFFBOARD_EXECUTE=true`.

Sans le second verrou, l'essai s'arrête avant toute publication de commande avec un code d'erreur. Le profil de simulation normal ne démarre pas ce service.

Les paramètres du banc neutralisent volontairement les pertes RC et GCS afin d'isoler la réaction à la seule perte Offboard. `COM_OF_LOSS_T=1.0` et `COM_OBL_RC_ACT=4` demandent à PX4 d'attendre une seconde puis d'atterrir. Cette configuration est réservée au SITL headless. Les paramètres de perte RC, de perte liaison de données et d'exception Offboard devront être redéfinis et validés pour le drone réel.

## 7. Résultats mesurés

### 7.1 Trajectoire carrée

| Mesure | Résultat |
|---|---:|
| Mode Offboard accepté | oui |
| Armement accepté | oui |
| Altitude maximale | 1,998 m |
| Erreurs aux quatre coins | 0,330 à 0,345 m |
| Carré terminé | environ 19,3 s |
| Atterrissage et désarmement | réussis |
| État failsafe | faux |

Preuve : `results/simulation/px4_lot_a/square_20260820T194220.119340Z/result.json`.

### 7.2 Perte Offboard

| Événement | Temps écoulé |
|---|---:|
| Arrêt du flux Offboard | 18,852 s |
| Passage autonome PX4 en `AUTO_LAND` | 19,951 s |
| Latence mesurée | **1,099 s** |
| Fin de l'essai, véhicule posé | 24,551 s |
| Altitude maximale | 1,992 m |

Le nœud de test n'a pas envoyé de commande d'atterrissage de secours : le changement de mode et le failsafe proviennent bien de PX4. Il n'a émis le désarmement qu'une fois le posé observé.

Preuve : `results/simulation/px4_lot_a/failsafe_20260820T194435.644693Z/result.json`.

## 8. Traçabilité exigences–composants–tests–résultats

| Exigence | Composant | Vérification | Résultat |
|---|---|---|---|
| `SYS-FUN-001` — estimer et exposer l'état du drone | `state_bridge` | topics ROS, diagnostics et tableau de bord | réussi, odométrie observée à environ 100 Hz |
| `SYS-FUN-004` — fournir une trajectoire au contrôleur | `offboard_test` + PX4 | carré SITL de 2 m | réussi, quatre coins atteints et véhicule posé |
| `SAFE-REQ-001` — PX4 conserve la commande critique | architecture uXRCE-DDS et topics d'entrée limités | revue d'interface et absence de topic actionneur | réussi pour le lot A |
| `SAFE-REQ-002` — réaction sûre à la perte Offboard | paramètres PX4 et watchdog interne | coupure réelle du flux de consignes | réussi, `AUTO_LAND` en 1,099 s puis posé |
| `QUAL-REQ-001` — banc reproductible | Dockerfile, Compose et révisions gelées | construction, tests unitaires et démarrage des services | réussi sur le poste de développement |

Les identifiants ci-dessus reprennent la logique du cahier des charges préliminaire. Ils restent à consolider lors de sa prochaine révision formelle.

## 9. Utilisation

Démarrer le socle :

```powershell
docker compose --profile sim up -d micro-xrce-dds-agent px4-state-bridge px4-sitl
docker compose --profile viz up -d fast-lio-dashboard
```

Ouvrir `http://127.0.0.1:8080` sur le poste, ou `http://192.168.1.25:8080` depuis le réseau local.

Lancer le carré :

```powershell
$env:PX4_OFFBOARD_EXECUTE = "true"
$env:PX4_OFFBOARD_MODE = "square"
docker compose --profile flight-test run --rm --no-deps px4-offboard-test
$env:PX4_OFFBOARD_EXECUTE = $null
```

Lancer la perte Offboard :

```powershell
$env:PX4_OFFBOARD_EXECUTE = "true"
$env:PX4_OFFBOARD_MODE = "failsafe"
docker compose --profile flight-test run --rm --no-deps px4-offboard-test
$env:PX4_OFFBOARD_EXECUTE = $null
```

## 10. Limites et validations restantes

- Le firmware est une version bêta, suffisante pour le banc expérimental mais non qualifiable.
- Gazebo utilise encore le monde générique et des capteurs simulés idéalisés ; le dataset BotanicGarden n'est pas encore injecté dans cette chaîne.
- QGroundControl est configuré par le port MAVLink 14550, mais sa connexion visuelle n'a pas été observée pendant cette campagne automatisée : **À valider** manuellement.
- Les tests ne couvrent pas encore la perte de l'Agent DDS, la latence réseau, les sauts d'horloge, le redémarrage de nœud ou les trajectoires issues d'une carte.
- Aucun résultat du lot A ne doit être extrapolé à un matériel réel sans une analyse de sécurité et un profil de paramètres distinct.

## 11. Suite recommandée

Le lot suivant peut commencer par la chaîne du drone cartographe : extraction et synchronisation des caméras BotanicGarden, calibration caméra–LiDAR–IMU, colorisation du nuage puis carte topographique. En parallèle seulement après définition de l'interface de carte, PX4 pourra recevoir une trajectoire générée à partir de cette carte, d'abord dans le monde SITL générique puis dans le monde viticole `VINEYARD_BENCH_V01`.

## 12. Références

- PX4, mode Offboard : `https://docs.px4.io/v1.17/en/flight_modes/offboard` ;
- PX4, configuration des failsafes : `https://docs.px4.io/main/en/config/safety` ;
- PX4, simulation des failsafes : `https://docs.px4.io/main/en/simulation/failsafes` ;
- ADR-0002 et ADR-0003 dans `docs/decisions/`.
