# Index documentaire

Dernière mise à jour : 13 septembre 2026.

## Références actives

Le projet maintient quatre documents d'architecture et un document transversal
de validation. Ils sont modifiés en place : leur nom ne contient volontairement
aucun numéro de version.

| Référence | Document | Contenu |
|---|---|---|
| `DOC-HLD` | [High Level Design](architecture/HLD.md) | fonctionnement du système complet, scénarios, frontières, exigences et validation système |
| `DOC-SW` | [Architecture logicielle](architecture/ARCHITECTURE_LOGICIELLE.md) | modules, contrats, déploiement, état d'implémentation et tests logiciels |
| `DOC-MEC` | [Architecture mécanique](architecture/ARCHITECTURE_MECANIQUE.md) | choix mécaniques, pièces, sous-assemblages, BOM et vérifications |
| `DOC-ELEC` | [Architecture électrique et réseaux](architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md) | alimentation, électronique, liaisons de données, synchronisation et tests |
| `DOC-VAL` | [Validation et qualification](VALIDATION_QUALIFICATION.md) | stratégie, campagnes, résultats synthétiques, preuves et qualification restante |

Le présent index définit la politique documentaire. Les décisions et leur
justification encore utile sont intégrées directement au document vivant
concerné ; les procédures de travail spécialisées sont portées par les skills
du projet sous `.agents/skills/`.

## Règle d'évolution

1. Chercher d'abord la section correspondante dans l'un des cinq documents.
2. Mettre à jour cette section, sa date et son journal de modifications.
3. Intégrer toute décision structurante, ses alternatives utiles et ses
   conséquences dans le document vivant concerné ; ne pas créer de registre de
   décisions séparé.
4. Placer les mesures, journaux et sorties volumineuses dans les répertoires de
   vérification ou de résultats prévus, puis les référencer depuis le document.
5. Ne pas créer de compte rendu documentaire pour une discussion, une livraison
   ou un essai isolé.

Les `README.md` locaux expliquent uniquement comment utiliser le répertoire ou
l'artefact voisin. Les manifestes, configurations, schémas et résultats de test
sont des preuves techniques, pas des documents d'architecture supplémentaires.

## Documents hérités

Les anciens documents narratifs numérotés et les anciens fichiers de décision
ont été audités, consolidés puis supprimés. Les éléments qui avaient été
versionnés restent accessibles dans l'historique Git ; les informations utiles
des fichiers non versionnés ont été intégrées aux documents vivants avant leur
suppression. Leurs identifiants peuvent encore apparaître dans une preuve
historique immuable ; ils ne désignent plus une source active.

En cas de contradiction, les cinq documents actifs prévalent.

## Décisions et règles de travail

Les décisions actives sont décrites dans la section du document vivant qui
porte le domaine concerné. Les invariants transversaux nécessaires à toutes les
tâches sont résumés dans `AGENTS.md` ; les procédures conditionnelles sont
décrites dans les skills du projet. Une proposition non qualifiée est toujours
marquée **À valider** et ne devient pas acquise sans validation explicite.

## Convention de maturité

- **Planifié** : capacité ou composant décrit, non implémenté.
- **Implémenté** : présent dans le logiciel ou la CAO, sans qualification
  complète.
- **Qualifié** : critères définis et preuves de validation disponibles.
- **À valider** : hypothèse, valeur ou sélection qui ne doit pas être interprétée
  comme une exigence figée.
