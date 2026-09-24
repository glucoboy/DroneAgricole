# Utiliser le projet CA01

**Attention : ce projet KiCad décrit encore la V0.3 PM02D.** Le
[câblage cible V0.4](../cablage_global.mmd) utilise PM08-CAN et une entrée AUX_IN
qui reste à créer. Retirer le buck 5V_AUX et vérifier les rails 5,3 V avant
raccordement ; ne pas alimenter cette entrée externe sur la carte ancienne.
Voir manifest.json, champ pending_migration, pour les écarts à fermer.

Ouvrir `CA01_Avionique.kicad_pro` avec KiCad 10.0.6, puis le schéma.
Les cinq blocs de la feuille racine ouvrent les sous-feuilles. Conserver
`CA01_Fonctions.kicad_sym` et `sym-lib-table` à côté du projet : la bibliothèque
utilise un chemin relatif au projet.

Le cahier des charges et les décisions sont dans
[DOC-ELEC §4.2](../../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md#42-cahier-des-charges-de-la-carte-avionique-commune-ca01).
La recette et les limites sont dans [DOC-VAL §12.5](../../../../docs/VALIDATION_QUALIFICATION.md#125-pm02d-en-tête-et-câblage-v03-22-septembre-2026).
Consulter `manifest.json` avant toute modification : cette ébauche ne permet
pas de fabriquer une carte.

Depuis PowerShell, lancer le contrôle statique :

```powershell
./verification/verify_ca01.ps1
```

Adapter `-KiCadCli` si KiCad est installé ailleurs. La commande réécrit
`verification/netlist.xml`, `verification/erc.json` et
`verification/controle_statique.json`, avec les empreintes des fichiers.
Un retour sans erreur du script signifie que les invariants de connexion
sont respectés ; lire séparément `erc.passed` et le rapport ERC. Les trois
erreurs de puissance actuellement ouvertes ne sont pas des dérogations.

Les contrôles MCP conservés dans `verification/mcp_controles_20260922.json` décrivent
une exécution datée ; ils ne sont pas régénérés par le script PowerShell.
Pour les réexécuter, le pont local `.runtime/kicad-mcp` doit être disponible
avec la version du manifeste. Ne pas rejouer les appels de création sur un
projet existant.

Les aperçus SVG locaux sont régénérables par KiCad :

```powershell
& 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe' sch export svg CA01_Avionique.kicad_sch -o verification/svg/
```

Les labels globaux relient les feuilles. Les réseaux de part et d'autre d'un
composant DNP figurent dans la netlist, mais sa présence graphique ne crée pas
une connexion physique. Garder les annotations DNP et les valeurs
`A_CALCULER` tant que leur justification n'a pas été validée.


La révision V0.3 utilise J101 uniquement pour la radio (deux contacts).
Le PM02D et le câble POWER1 Pixhawk restent hors CA01. Voir le
[registre de câblage](../cablage_global.json) et le
[schéma global](../cablage_global.mmd).
