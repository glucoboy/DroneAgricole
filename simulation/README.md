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

## ORCH-GZ-1 : dérivés du prototype et outils locaux

### Passerelle intégrée à la station

Ouvrir **Simulations → Modèle 3D**, puis **Préparer pour Gazebo**. La conversion
lit la CAO active du prototype, en conservant ses natifs et les sources fabricant.
Le Python de FreeCAD est détecté sur Windows, ou peut être indiqué avec
`DRONE_AGRICOLE_FREECAD_PYTHON`. L'aperçu est échantillonné pour l'affichage ;
les STL destinés à Gazebo conservent leur résolution d'export.

Les nouveaux dossiers sont créés dans
`results/simulation/model_exports/<identité>/cartographe/` : `model.sdf`,
`model.config`, cinq maillages, collisions/géométrie, scénario physique,
`40000_gz_cartographe`, monde plat, `preview_world.sdf` contenant le modèle,
aperçu et `export_manifest.json`. Les empreintes lient sources et sorties.
Un export n'est pas un résultat de vol T0. Il ne lance ni Docker ni PX4.
Le verrou est commun aux instances UI/CLI ; annulation et budget de 15 minutes
arrêtent la préparation. Une destination existante n'est jamais écrasée.

```powershell
& .\build\desktop-debug\software\cpp\drone-agricole-tools.exe gazebo-model --action inspect
& .\build\desktop-debug\software\cpp\drone-agricole-tools.exe gazebo-model --action export
# Option : réutiliser uniquement des maillages vérifiés, dans un nouveau dossier.
& .\build\desktop-debug\software\cpp\drone-agricole-tools.exe gazebo-model --action export --reuse-meshes --output results/simulation/model_exports/NOUVEL_ID/cartographe
```

Sur une installation Linux de Gazebo Harmonic, exposer le **parent** du dossier
`cartographe` comme ressource, puis ouvrir son monde de visualisation :

```sh
export GZ_SIM_RESOURCE_PATH=/chemin/vers/identite_export
gz sim /chemin/vers/identite_export/cartographe/preview_world.sdf
```

Le monde de visualisation ne démarre pas PX4 ; utiliser la configuration SITL
ci-dessous pour un essai en vol verrouillé. Le profil d'export prend en charge
le prototype actif ; l'import générique STEP/FCStd et la physique identifiée
ne sont pas implémentés par cette passerelle.

Le manifeste est `gazebo/models/cartographe/model_manifest.json` ; les
résultats et limites sont dans DOC-VAL §9.3. Le SDF utilise un scénario
physique synthétique, distinct de la masse inconnue du prototype. Les STL
restent hors Git et doivent être régénérés avant les tests de génération :

```powershell
$env:PATH = 'C:\msys64\ucrt64\bin;' + $env:PATH
& 'C:\Program Files\FreeCAD 1.1\bin\python.exe' simulation/gazebo/tools/cad_export_cartographe.py
& 'C:\Program Files\FreeCAD 1.1\bin\python.exe' simulation/gazebo/tools/cad_export_collisions.py
cmake -S simulation -B build/cartographe -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build build/cartographe -j 2
ctest --test-dir build/cartographe --output-on-failure
```

Pour reconstruire les dérivés sur une copie privée scellée avec V3-SIM.1,
suivre la [recette de reproduction](../docs/verification/v3/sim1/README.md).
La commande `cartographe-model diagnose` inspecte les liens d'empreinte
du modèle historique. `cartographe-model rebuild` utilise le même backend
que la station et laisse le paquet régénéré dans la destination demandée.

Les deux adaptateurs utilisent FreeCAD/Part/MeshPart, lisent les BREP
sauvegardés et ne sauvegardent pas les natifs. Adapter uniquement le chemin
de l'installation FreeCAD et de Qt à l'hôte. Les exports font environ 100 Mo.
Le générateur C++ refuse `--physical` tant que les propriétés réelles ne
sont pas identifiées. Pour régénérer le SDF et l'airframe après les exports :

```powershell
build/cartographe/cartographe-model.exe .
```

Campagne énergie hors ligne, dans des répertoires neufs :

```powershell
$runName = 'energy_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')
build/cartographe/cartographe-evidence.exe execute "results/simulation/orch_gz_1/$runName" "results/simulation/orch_gz_1/t0_$runName"
if ($LASTEXITCODE -ne 0) { throw 'Exécution ou finalisation T0 refusée' }
build/cartographe/cartographe-evidence.exe validate "results/simulation/orch_gz_1/t0_$runName"
```

`execute` valide et archive la requête avant de lancer le CLI, borne son
processus à 60 s réelles puis contrôle la finalisation. Pour le chemin manuel,
utiliser `cartographe-evidence prepare REPERTOIRE_T0`, puis `cartographe-energy`
avec les mêmes configurations et `--cancel-after 3` pour l'annulation, puis
`cartographe-evidence seal FICHIER_BRUT REPERTOIRE_T0`.
Le CLI refuse l'écrasement et
le scellement refuse les empreintes périmées, un CSV incohérent ou une
campagne non finalisée. Les profils représentent des charges, sans vol
observé. Aucun courant batterie n'est injecté dans PX4 ; l'observateur RPM
est un contrat C++ testé, avec conversion du ralentissement Gazebo ×10.

## Reprise du banc cartographe

Le moteur Docker Linux doit répondre. Son échec local du 23 octobre est
consigné dans `px4_sitl/verification/bench_preflight.json`. Ne pas considérer
les commandes ci-dessous comme exécutées ou validées par cette livraison.
Reconstruire d'abord le pont modifié puis charger le véhicule, en conservant
le runtime x500 historique :

```powershell
docker compose --profile sim --profile viz build px4-runner-api
docker compose --profile sim --profile viz stop px4-runner-api px4-sitl px4-state-bridge micro-xrce-dds-agent
docker compose -f compose.yaml -f simulation/compose.cartographe.yaml --profile sim --profile viz up -d --force-recreate px4-runner-api
pwsh -NoProfile -File simulation/px4_sitl/preflight.ps1 -ComposeOverride simulation/compose.cartographe.yaml -ExpectedModel gz_cartographe -RequireReady
if ($LASTEXITCODE -ne 0) { throw 'Identité du banc SITL indisponible : aucune commande Offboard' }
Invoke-RestMethod http://127.0.0.1:8091/api/health
```

La surcharge définit les chemins `PX4_GZ_MODELS/WORLDS`, `gz_cartographe`,
le monde `cartographe_flat`, l'autostart 40000 et `.runtime/px4-cartographe`.
Le socle conserve x500/4001 et `.runtime/px4`. Les deux utilisent les mêmes
ports : un seul banc à la fois. Les ressources et l'airframe sont montés
en lecture seule. Vérifier dans les journaux le chargement du monde et du
modèle, puis les topics ROS versionnés et l'odométrie fraîche avant exécution :

```powershell
docker compose logs --tail 100 px4-sitl px4-state-bridge
docker compose exec px4-state-bridge /bin/bash -lc 'source /opt/ros/jazzy/setup.bash; source /opt/px4_ros_ws/install/setup.bash; ros2 topic list'
```

Rejouer ensuite les commandes `square` et `failsafe` ci-dessus avec la même
surcharge `-f compose.yaml -f simulation/compose.cartographe.yaml`, et seulement
après le préflight réussi. Garder `DRONE_AGRICOLE_SITL=1`, `execute:=true`
et `PX4_OFFBOARD_EXECUTE=true` pour ce point d'entrée. Observer aussi posé,
désarmement, annulation et fichier final ; un timeout ne confirme pas le posé.
Le runner borne armement 10 s, mission 100 s, atterrissage 35 s et supervision
150 s, avec escalade d'arrêt bornée du groupe de processus SITL.
Pour revenir au socle, arrêter le banc puis recréer avec le seul `compose.yaml`.
Ne jamais supprimer les paramètres historiques pour masquer une divergence.

### Campagne bornée avec preuves T0

Le banc a été exécuté le 24 octobre 2026. L'identifiant 4010 est occupé par
un modèle officiel dans l'image : utiliser 40000 pour cartographe. Le
préflight vérifie l'unicité de l'airframe et sa valeur effective. Les
capteurs comportent un bruit synthétique d'intégration non calibré ; la
graine n'est pas fixée. La batterie reçue par PX4 est encore forfaitaire.

Après démarrage du banc voulu et retour d'une odométrie fraîche :

```powershell
$env:PATH = 'C:\msys64\ucrt64\bin;' + $env:PATH
pwsh -NoProfile -File simulation/px4_sitl/run_campaign.ps1 -Model cartographe -Mode square -RunId reprise_carto_square_01
pwsh -NoProfile -File simulation/px4_sitl/run_campaign.ps1 -Model cartographe -Mode failsafe -RunId reprise_carto_failsafe_01
pwsh -NoProfile -File simulation/px4_sitl/run_campaign.ps1 -Model cartographe -Mode cancel -RunId reprise_carto_cancel_01
```

Utiliser un identifiant neuf pour chaque essai ; les résultats existants ne
sont pas écrasés. Pour la référence, démarrer le socle sans surcharge et
remplacer `-Model cartographe` par `-Model x500`. Le script vérifie identité,
verrou API et fraîcheur, prépare la requête avant le vol, observe les états,
attend posé/désarmement, puis scelle et valide les cinq contrats. Les sources
archivées restent vérifiables après évolution du checkout. Les preuves T0
sont sous `results/simulation/orch_gz_1/sitl_20261024/<RunId>/`, les traces
détaillées sous `.runtime/orch_gz_1/20261024/<RunId>/` ; elles restent hors Git.
La synthèse légère est `simulation/px4_sitl/verification/campaign_20261024.json`.
Les variations d'énergie restent hors ligne ; aucun courant PX4 forfaitaire
ne doit servir au calcul d'autonomie.
