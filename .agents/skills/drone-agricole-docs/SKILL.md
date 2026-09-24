---
name: drone-agricole-docs
description: "Maintenir la documentation vivante en français du projet Drone Agricole lors d'un changement d'architecture, d'exigence, de statut, de décision ou de résultat. Ne pas utiliser pour une simple modification de code sans impact documentaire ni pour créer un compte rendu isolé."
---

# Documentation vivante du Drone Agricole

Consolider l'information dans les sources existantes. Ne pas créer de document de décision séparé : une décision structurante et sa justification utile appartiennent au document vivant du domaine concerné.

## Choisir la source

Lire d'abord `docs/INDEX.md`, puis seulement les documents nécessaires :

- `docs/architecture/HLD.md` (`DOC-HLD`) : système complet, scénarios, frontières de sûreté, exigences et validation système ;
- `docs/architecture/ARCHITECTURE_LOGICIELLE.md` (`DOC-SW`) : modules, contrats, déploiement, état d'implémentation et tests logiciels ;
- `docs/architecture/ARCHITECTURE_MECANIQUE.md` (`DOC-MEC`) : architecture mécanique, pièces, assemblages, BOM et vérifications ;
- `docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md` (`DOC-ELEC`) : alimentation, électronique, réseaux, temps et essais ;
- `docs/VALIDATION_QUALIFICATION.md` (`DOC-VAL`) : stratégie, campagnes, résultats, preuves, limites et qualification restante.

Un changement transversal peut nécessiter plusieurs documents, sans recopier le même détail. Utiliser `DOC-HLD` pour la vue système et renvoyer vers le document de domaine.

Lire un `README.md` local uniquement pour comprendre l'usage du répertoire ou de l'artefact voisin. Les manifestes, configurations, schémas et résultats sont des preuves techniques ; les référencer depuis le document vivant approprié au lieu d'en faire un document narratif.

## Mettre à jour

1. Modifier en place la section qui porte déjà le sujet. Si elle n'existe pas, ajouter une section dans le document vivant le plus proche.
2. Pour une décision structurante, consigner dans cette section le choix courant, les raisons encore utiles, les conséquences, les alternatives qui restent pertinentes et le statut. Ne créer ni ADR ni registre de décisions séparé.
3. Mettre à jour la date et le journal de modifications du document touché.
4. Employer exactement les maturités `Planifié`, `Implémenté`, `Qualifié` et **À valider**. Une valeur, une sélection ou une performance non qualifiée reste **À valider**.
5. Maintenir la chaîne `exigence -> composant/algorithme -> test -> résultat/preuve`. Ajouter les identifiants et liens utiles dans les documents concernés.
6. Conserver les sorties détaillées ou volumineuses dans le répertoire de résultats ou de vérification prévu, hors Git quand les règles du dépôt l'exigent ; ne garder dans les documents que la synthèse, le périmètre et le lien vers la preuve.

Ne pas créer de compte rendu pour une discussion, une livraison, une étude ou un essai isolé. Un `README.md` local n'est acceptable que comme guide d'utilisation du répertoire. Un manifeste ou une preuve structurée reste permis lorsqu'il décrit effectivement l'artefact ou l'exécution.

## Contrôler la cohérence

Avant de terminer :

- rechercher les anciennes affirmations, références, nombres de tests et statuts affectés ;
- distinguer explicitement les environnements Windows, Linux, `amd64`, `arm64`, simulation, banc et matériel ;
- ne pas extrapoler une qualification à un autre environnement ou à un vol réel ;
- vérifier les liens, les identifiants d'exigence, la date et le journal des documents modifiés ;
- signaler les validations non exécutées et leur raison.
