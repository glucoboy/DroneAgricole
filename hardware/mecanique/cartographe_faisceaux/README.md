# Ouvrir la copie d'essai

Ouvrir `assemblages/Prototype_Cartographe.FCStd` dans FreeCAD 1.1.3 avec
Cables Workbench 0.3.7. Conserver toute l'arborescence pour les liens externes.
Cet assemblage est la copie conservée de la baseline, pas une reconstruction
globale acceptée. `manifest_essai.json` désigne sa portée et les preuves.

Ouvrir séparément `verification/candidats/F16_ARCS_R23_5.FCStd` pour éditer
le candidat : parcours WireFlex, profil circulaire et objet ArchCable.
Ne pas substituer ce document au F16 de l'assemblage : sa validation complète
reste ouverte. Il ne représente pas une gaine commune.

Le reçu `experiment.json` liste les sources et leurs empreintes.
Le contrôle de préservation se lance depuis la racine du projet :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' -B `
  .agents/skills/electromechanical-integration/scripts/workspace_guard.py verify `
  hardware/mecanique/cartographe_faisceaux/experiment.json
```

Les scripts et preuves de cet essai sont dans
`../cartographe/verification/reconstruction_faisceaux/`. Les générateurs
refusent d'écraser un candidat existant ou une preuve marquée terminée.
Pour une nouvelle expérience, préparer une autre copie isolée et adapter
explicitement ses chemins ; ne pas lancer le constructeur global du prototype.

Le rapport comparatif est intégré à DOC-MEC §2.2.3, les contrôles à
DOC-VAL §12.1.12 ; aucun natif d'ici n'est une configuration active du projet.
