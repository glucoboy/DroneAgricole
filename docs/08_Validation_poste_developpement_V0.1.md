# Validation du poste de développement

| Champ | Valeur |
|---|---|
| Référence | DOC-08 |
| Version | V0.1 |
| Date | 18 août 2026 |
| Statut | Validé |

## Résultat

Le poste est prêt pour construire les conteneurs du projet et commencer les simulations.

| Élément | Version ou résultat | État |
|---|---|---|
| WSL | 2.7.11.0 | validé |
| Noyau WSL | 6.18.33.2 | validé |
| Distribution | Ubuntu 24.04.4 LTS | WSL 2 validé |
| Docker Desktop | 4.87.0 | moteur Linux validé |
| Docker Engine | 29.7.2 | validé |
| Docker Compose | 5.4.0 | validé |
| GPU | NVIDIA GeForce RTX 5060 Ti, 16 311 Mio | Windows et WSL validés |
| CUDA dans Docker | image `nvidia/cuda:12.8.1-base-ubuntu24.04` | validé |
| Accès au workspace `D:` | WSL et montage Docker en lecture seule | validé |
| Extensions VS Code | WSL, Dev Containers, Docker | présentes |
| QGroundControl | installation Windows détectée | présent |

## Test GPU reproductible

Le test suivant s'est terminé correctement :

```powershell
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi
```

Image officielle utilisée :

```text
sha256:133c78a0575303be34164d0b90137a042172bdf60696af01a3c424ab402d86e2
```

Le conteneur a détecté la RTX 5060 Ti et la mémoire GPU disponible. Aucun CUDA Toolkit ni pilote NVIDIA Linux supplémentaire n'est nécessaire sur l'hôte.

## Prochaine étape

Construire le socle conteneurisé du projet, puis exécuter successivement :

1. un test ROS minimal ;
2. un test de lecture des métadonnées BotanicGarden ;
3. un premier environnement PX4/Gazebo ;
4. la préparation de l'adaptateur FAST-LIO2 pour `1006-03`.

Le choix entre la base ROS 2 Humble active et un conteneur de simulation ROS 2 Jazzy/Gazebo Harmonic devra être formalisé avant de modifier l'architecture de référence.
