# ADR-0001 — Sélection initiale des datasets

- Statut : proposé
- Date : 18 août 2026

## Contexte

Le projet doit comparer FAST-LIO2, Point-LIO et LIO-SAM avant l'achat des capteurs. Aucun dataset unique ne combine actuellement accessibilité immédiate, vérité terrain de haute qualité, environnement viticole, changement saisonnier et capteur Livox Mid-360.

## Décision

Utiliser un portefeuille progressif : BotanicGarden pour le test de fumée naturel, Newer College comme référence LIO, ARD-VO pour une première séquence viticole avec RTK, BLT pour les changements saisonniers, puis TEMPO-VINE comme benchmark principal dès sa publication effective.

M2DGR et Hilti sont différés jusqu'à stabilisation du banc.

## Conséquences

- plusieurs adaptateurs de formats seront nécessaires ;
- les métriques devront être strictement normalisées ;
- certaines archives nécessitent un formulaire rempli par l'utilisateur ;
- les licences non commerciales ou ambiguës devront être clarifiées avant tout usage produit ;
- le premier téléchargement peut rester limité à environ 6 Go avec BotanicGarden `1006-03`.

## Alternatives rejetées

- Uniquement Newer College : vérité terrain solide, mais représentativité viticole insuffisante.
- Uniquement M2DGR : trop volumineux et trop éloigné du domaine.
- Attendre TEMPO-VINE : bloque inutilement le développement du banc.
- Télécharger tous les datasets agricoles : coût de stockage et de préparation disproportionné avant validation de l'infrastructure.
