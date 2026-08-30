# Outils

Scripts de préparation des données, lancement de campagnes, collecte de métriques, génération de rapports et contrôle de qualité.

Les outils évitent les chemins absolus propres à une machine et fonctionnent depuis la racine du workspace.

## Benchmark FAST-LIO2

- `run_fastlio2_botanicgarden_benchmark.sh` : rejeu, enregistrement et orchestration ;
- `profile_process.py` : temps CPU, durée et pic RSS du processus ;
- `summarize_fastlio_run.py` : manifeste de reproductibilité et facteur temps réel ;
- `analyze_lio_trajectory.py` : ATE translation/orientation, RPE à intervalle fixe et comptabilité du pipeline instrumenté ;
- `summarize_sensitivity.py` : tableaux JSON et CSV multi-configurations ;
- `run_fastlio2_botanicgarden_smoke.sh` : raccourci compatible pour le test court.
- `run_fastlio2_08x_campaign.sh` : qualification 0,8× et trois répétitions des variantes ;
- `summarize_fastlio_08x_campaign.py` : statistiques par variante et contrôle du ratio odométries/scans ;
- `compare_fastlio_08x_to_1x.py` : comparaison reproductible avec la campagne 1×.

Le protocole initial est décrit dans DOC-11 ; la campagne répétée à vitesse réduite et ses limites sont décrites dans DOC-13 ; l'instrumentation et la génération automatique de `metrics.json` sont décrites dans DOC-14.

## Visualisation temps réel

- `visualization/start_fastlio_dashboard.ps1` : démarre le service local et ouvre la console 3D ; le rejeu est ensuite lancé ou arrêté depuis la page ;
- `visualization/stop_fastlio_dashboard.ps1` : arrête le service sans toucher aux autres conteneurs ;
- `benchmarks/profile_process.py` : publie en option les métriques ROS 2 `/benchmark/*` quand `FASTLIO_DASHBOARD=1`.
- Après une exécution réussie, le serveur calcule `metrics.json` et expose le bilan final via le bouton dédié du tableau de bord.

Le mode graphique est documenté dans `docs/12_Tableau_de_bord_3D_temps_reel_V0.2.md`. Il ne remplace pas une campagne headless de référence.
