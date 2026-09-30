---
name: hw-design-schematique
description: "Créer, reprendre ou relire les schémas électroniques du projet DroneAgricole, notamment sous KiCad, avec des circuits compacts, des connexions visibles et une validation de topologie. Utiliser pour la conception schématique et ses références de composants ; pas pour le routage PCB seul, la CAO mécanique ou un simple diagramme d'architecture."
---

# HW Design schématique

## Forme attendue

La préférence du projet est un schéma compact que l'on peut suivre visuellement.
Prendre les retouches utilisateur existantes comme référence de mise en page.

- Regrouper chaque circuit avec ses passifs, protections, alimentation et interfaces proches. Éviter de disperser une même fonction sur plusieurs zones ou sous-feuilles.
- Placer autant que possible les entrées à gauche et les sorties à droite. Identifier clairement le sens des liaisons bidirectionnelles et des retours qui ne suivent pas ce sens de lecture.
- Si les broches, textes ou connexions d'un IC deviennent trop serrés, agrandir son symbole et espacer ses broches plutôt que forcer une mise en page trop compacte. Conserver les numéros et fonctions électriques des broches.
- Relier les composants d'un circuit par des fils orthogonaux directs. Ne pas remplacer les liaisons locales de feedback, bootstrap, découplage ou polarisation par une collection de labels.
- Réserver les labels nommés aux rails partagés, interfaces réelles entre fonctions ou feuilles et signaux utiles à l'identification. Préférer des labels locaux lorsque leur portée suffit ; un label global est une connexion électrique, pas une annotation décorative.
- Représenter les alimentations par un symbole à tige verticale et barre horizontale en haut, toujours orienté vers le haut ; employer le symbole GND pour les masses. Conserver les noms et la portée des réseaux lors du remplacement des labels. Garder les labels pour les signaux et les retours distincts de GND.
- Garder les feuilles par fonction lorsqu'elles améliorent la lecture. Ne pas multiplier les sous-feuilles pour des passifs ou petits sous-circuits ; une grande feuille unique n'est pas imposée par cette préférence.
- Compacter sans superposer textes, fils et symboles. Rendre les jonctions et croisements non reliés explicites, utiliser la grille KiCad et un format papier adapté. La lisibilité à l'écran et dans l'export prime sur le nombre de labels supprimés.

## Reprendre un schéma existant

Inspecter Git, le schéma et ses dernières preuves avant toute édition.
Préserver les modifications utilisateur, repères, choix de composants et sens de lecture.
Pour un lot complexe, suivre la politique agentique du projet et attribuer des fichiers distincts.

Avant une réorganisation graphique, exporter une netlist de référence hors des preuves actives.
Comparer ensuite les connexions par ensemble de broches et par chemin de circuit :
un réseau automatiquement nommé ou une résistance retournée ne constitue pas une régression.
Ne pas restaurer des labels inutiles pour satisfaire un test trop lié à la mise en page.
En revanche, conserver une orientation de broches significative pour les composants polarisés,
diodes, transistors, IC, connecteurs et interfaces constructeur.

## Concevoir les circuits

Partir des domaines de tension, charges, variantes et limites réellement connus.
Vérifier brochages et recommandations dans les sources primaires du fabricant.
Distinguer repères de connecteurs logiques, contacts OEM et vues côté accouplement.
Calculer les passifs et marges avec hypothèses explicites ; une référence ou une valeur
candidate reste À valider tant que son enveloppe et ses preuves ne sont pas fermées.

Représenter les circuits avec des composants réels quand les données le permettent.
Un bloc fonctionnel ou une valeur A_CALCULER est un manque de conception, pas un circuit terminé :
l'identifier clairement, conserver manufacturing_ready=false et ne pas lui attribuer une performance.
Utiliser un indicateur de puissance KiCad seulement pour une source physique identifiable,
avec justification ; il ne doit pas masquer un convertisseur, une protection ou un retour absent.

## Contrôler et livrer

- Exporter la netlist et l'ERC KiCad. Pour une modification graphique, vérifier l'équivalence électrique ; pour une modification de circuit, vérifier les chemins et isolements affectés.
- Contrôler les séparations d'alimentation, no-connect, DNP, retours de masse, polarités et risques de réalimentation concernés.
- Exporter les pages et inspecter leur rendu : circuits regroupés, fils suivables, textes lisibles, contenu dans le cadre.
- Adapter les recettes existantes à des invariants électriques stables plutôt qu'aux noms des réseaux internes ou à l'orientation de passifs non polarisés.
- Actualiser le manifeste et les preuves. Consigner les décisions et résultats dans DOC-ELEC et DOC-VAL conformément à la skill drone-agricole-docs.
- Rapporter les contrôles réussis, les violations ouvertes et les validations non exécutées. Un ERC vierge ne prouve ni le dimensionnement, ni la fabricabilité, ni la qualification matérielle.
