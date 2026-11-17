# Index documentaire

> Copie documentaire de la variante système du cartographe.

Dernière mise à jour : 10 novembre 2026.

## Références actives

Le projet maintient quatre documents d'architecture et un document transversal
de validation. Ils sont modifiés en place : leur nom ne contient volontairement
aucun numéro de version.

| Référence | Document | Contenu |
|---|---|---|
| `DOC-HLD` | [High Level Design](architecture/HLD.md) | méthode et préceptes de décision, priorité courante, fonctionnement du système, frontières et exigences |
| `DOC-SW` | [Architecture logicielle](../../../../docs/architecture/ARCHITECTURE_LOGICIELLE.md) | modules, contrats, déploiement, état d'implémentation et tests logiciels |
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

En cas de contradiction avec un document narratif hérité, les cinq documents
actifs prévalent. Cela ne leur donne pas autorité sur les données canoniques
des manifestes et contrats techniques.

## Autorité et méthode

La [méthode et la priorité courante](architecture/HLD.md#methodologie), puis
les [22 préceptes avec leurs déclencheurs](architecture/HLD.md#preceptes),
sont portés uniquement par DOC-HLD. DOC-VAL porte les
[écarts, preuves et actions de recentrage](VALIDATION_QUALIFICATION.md#audit-preceptes).

| Information | Source d'autorité et règle de modification |
|---|---|
| Objectif et priorité | responsable du projet, décision courante consignée dans DOC-HLD ; un agent ne transforme pas une proposition en objectif approuvé |
| Exigences, choix, raisons et maturité | document vivant du domaine ; actualisé avec la preuve, sans extrapoler le résultat à une autre cible |
| Identité et empreintes des datasets | `datasets/manifests/catalogue_datasets.yaml` et entrée/profil lié ; recettes et résumés les consomment, ne les redéfinissent pas |
| Références, occurrences et placements CAO | manifeste mécanique et configuration explicitement désignés dans DOC-MEC ; les natifs et leurs empreintes permettent de vérifier la réalisation |
| Sélection du prototype cartographe sans dock | `hardware/mecanique/cartographe/nomenclature_prototype.json`, périmètre et réserves dans DOC-MEC §5.0 ; le classeur est un export, les registres propres à CA01 conservent son détail |
| Assemblage actif du prototype | `hardware/mecanique/cartographe/assemblages/Prototype_Cartographe.FCStd` et sept sous-assemblages principaux, section `prototype_cartographe` du manifeste, DOC-MEC §2.2.1 et priorité ORCH-CAO-MASSE-1 de DOC-VAL §14. `verification/controle_orch_cao_masse_1.json` réconcilie les empreintes, contrôles, couverture et exports courants ; `verification/revue_orch_cao_masse_1.json` porte la revue indépendante. Le registre massique dérive de la BOM et ne la remplace pas. Les preuves précédentes sont historiques après modification des dépendances ; aucune qualification physique déduite |
| Périmètre fonctionnel du produit custom | `hardware/mecanique/cartographe/nomenclature_produit_custom.json`, DOC-MEC §5.0.1 ; classeur distinct, fonctions Planifiées et sélections À valider, sans reprise automatique des références prototype |
| Interfaces électriques | schémas et registres désignés dans DOC-ELEC ; une vue ou un export est dérivé, pas une autorité indépendante |
| Contrat attendu / comportement observé | schéma ou interface déclarée / implémentation et contrôle exécuté ; la présence d'un schéma ne prouve pas son application |
| Mesure et résultat | preuve identifiée avec entrées, environnement et empreintes ; DOC-VAL interprète et référence, sans réécrire une preuve historique pour la faire correspondre au présent |

Le contributeur qui modifie une donnée canonique actualise ses consommateurs
ou signale leur obsolescence. Si deux sources actives divergent, rendre
l'écart visible, identifier son propriétaire et le résoudre par observation ;
ne choisir ni la valeur la plus récente ni le résumé le plus commode sans
vérification. Les droits d'écriture suivent le périmètre autorisé de la tâche.

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

## Journal de modifications

- **10 novembre 2026** — Variante système isolée. Documents et preuves référencés sans promotion.


| Date | Modification |
|---|---|
| 26 octobre 2026 | Masse du kit X650 renseignée hors bilan ; estimations de 24 pièces carbone/aluminium et scénarios de propulsion sourcés, intersections internes des bras et booléens non conclus conservés ouverts. |
| 26 octobre 2026 | Reprise ORCH : corrections de collisions et fraisures intégrées ; bilan massique enrichi, chaque manque explicite dans la BOM ; contrôles sauvegardés, exports et revue actualisés. La définition complète reste À valider et les campagnes suspendues. |
| 25 octobre 2026 | Priorité et sources de preuve ORCH-CAO-MASSE-1 référencées ; couverture CAO/masses partielle, défauts d'interface et qualification physique distingués. |
| 22 octobre 2026 | Sources actives conservées en place ; contrôle de réconciliation des natifs, revue indépendante, nomenclature et classeur référencé, qualification matérielle distincte. |
| 12 octobre 2026 | Autorité du manifeste prototype et contrôles DOC-VAL §14.4 actualisés après correction des placements et fixations ; physique toujours À valider. |
| 11 octobre 2026 | Assemblage prototype reconstruit désigné comme actif et distingué de la BOM, de ses exports et de l'étude historique avec dock ; vérification finale en cours, physique À valider. |
| 10 octobre 2026 | Nomenclature fonctionnelle du produit custom et exports par sous-système référencés séparément du prototype. |
| 9 octobre 2026 | Autorité de la nomenclature prototype distinguée de ses exports et du manifeste des natifs avec dock conservés. |
| 8 octobre 2026 | Référence méthodologique centrale dans DOC-HLD, audit dans DOC-VAL et autorité précisée selon la nature des données. |
