# Préparer le dossier de réception V3-A.7

Faire confirmer par le responsable matériel l’état hors tension du
prototype cartographe sans dock et travailler avec les cordons totalement
détachés. Employer un gabarit de batterie inerte pour relever la course et
ses états limitants. Faire approuver la méthode opérateur avant un relevé de
continuité sur un cordon isolé de ses deux équipements.

## Préparer le relevé

Utiliser la [fiche A.5](../a5/measurement_packet.md), son
[CSV de préparation](../a5/measurement_form.csv), son
[paquet JSON vierge](../a5/measurement_form.json) et la
[matrice A.7](evidence_matrix.json). Créer un paquet distinct pour chaque
porteur observé. Affecter un identifiant de configuration d’assemblage au
paquet privé et garder les identités de lot propres à chaque composant.
Le même identifiant d’assemblage et le même porteur figurent dans les
faits de chaque relevé et dans l’enveloppe.

| Groupe | Pièces à préparer |
|---|---|
| Isolateur | Marquage, fabricant, MPN, révision, lot, photos recto et verso, connecteurs et surfaces d’appui. Confirmer FT232RL, FT232RNL, CH343G ou toute autre variante par les documents de son lot. |
| Appui sur P64 ou P66 | Deux datums distincts et deux originaux distincts, matière, épaisseur, perçages, vis ou inserts, engagement utile, enveloppe d’outil, cas et chemin d’effort. |
| Service TTL et USB | États engagé et séparé avec le cordon détaché de son équipement, volume balayé, axes de sortie, surmoulage, ferrite et garde minimale devant PDB, CAN1, F31, F35, P72 et P73. |
| Guides et gabarit inerte | Course entière, points extrêmes et limitants, retenues, longueur libre des deux cordons, limites et rayons statiques et dynamiques propres à chacun. |
| Réconciliation du câblage | Identifier J2 ou J3 par observation, vérifier la chimie de la révision BMS, les cavités et NC, l’isolement B−/P−, la variante TE cinq voies ou manuelle du W40/F40 et la liaison USB-B vers USB-A W41/F41 jusqu’à la porteuse Holybro Jetson. |

Chaque relevé donne l’auteur, la date ISO 8601 avec fuseau, la méthode,
l’instrument, la résolution et l’étalonnage disponible, la valeur, l’unité
et l’incertitude. Le responsable prépare séparément une politique A.4
`v3.a4.review_policy/1` avec l’identité attestée de chaque sujet,
l’empreinte des notices de cette révision, les datums attendus et
les limites sourcées. L’incertitude est au moins la demi-résolution.
Un contrôle `LE` utilise la borne haute de l’intervalle, et un contrôle
`GE` la borne basse. Un intervalle qui touche ou chevauche la limite
demande une reprise. Pour une limite, une pièce ou un relevé absent,
laisser le relevé non fourni et conserver la lacune.

## Renseigner les fichiers privés

1. Générer la fiche préparatoire du porteur avec `--operator-template`.
   Reprendre dans le paquet A.4 les valeurs de `check_id`, `subject`,
   `issue` et `measurement_kind`. Ajouter dans `facts` les clés
   `carrier` et `assembly_id`, puis les faits propres à chaque contrôle
   selon la matrice. Pour l’appui, garder `subject: carrier` dans le paquet
   et décrire l’identité P64 ou P66 dans l’identité du lot.
2. Renseigner `frame.parent` avec le parent XLink exact de la fiche. Les
   coordonnées des datums et des autres repères, y compris ceux des ports,
   sont exprimées dans ce repère porteur. Noter le datum identifié, l’origine
   en mm et les directions X/Y observées dans le plan. Construire un
   trièdre direct avec X normalisé, Y orthogonal à X et Z = X × Y. La
   normale observée et son signe doivent correspondre à Z. Consigner les
   matrices 4×4 directes et inverses à plat, rangées par ligne, avec
   translation dans la dernière colonne. Conserver les tolérances de
   position et d’orientation sourcées dans la politique.
3. Copier le [gabarit de dépôt](submission.template.json) dans le dossier
   privé et renseigner ses champs à partir du
   [contrat](submission.schema.json). Dans `details`, ajouter une entrée
   par `record_id` avec `origin_mm`, `x_direction`, `y_direction`,
   `observed_normal`, `normal_sign`, `calibration` et `artifacts`. Chaque
   rôle d’artefact de la fiche reçoit un objet `path` et `sha256`. Les
   originaux et les vues annotées restent distincts. Le champ
   `calibration` accepte `null` lorsqu’aucun justificatif n’est disponible.
4. Placer le dépôt et le paquet A.4 avec les originaux sous `raw`. Employer
   des chemins à barres obliques, relatifs à `raw`, sans redirection.
   Renseigner toutes les empreintes SHA-256 en minuscules. Après validation
   du dépôt courant par le responsable de collecte, prendre l’empreinte de
   ses octets exacts. Tenir cette empreinte dans le registre de collecte
   et la communiquer séparément du dépôt et des originaux. Obtenir de la
   même façon la politique de revue et son empreinte par le canal habilité.
   Les fichiers, données personnelles et empreintes des originaux restent
   dans les dossiers privés du responsable.

Le paquet A.4 réel emploie son champ historique `PHYSICAL_MEASURED` pour
qualifier la nature déclarée des entrées. A.7 restitue
`OPERATOR_SUBMISSION_UNREVIEWED` et garde la décision `DENY`. Les
témoins issus du pilote de test portent `EXAMPLE_NOT_AUTHORITY`.

## Générer et lire le contrôle

Depuis le checkout A.7 et avec le binaire compilé sur sa matrice, créer un
répertoire privé neuf. Sous PowerShell 7.4, la redirection de la sortie
binaire de l’exécutable préserve les octets du reçu. Les variables
`$courant` et `$politiqueSha` proviennent du registre et du responsable.

```powershell
$binaire = '.runtime/b/l5/cartographe_reception.exe'
$matrice = 'docs/verification/v3/a7/evidence_matrix.json'
$dossier = '.runtime/a7/collecte-privee'
New-Item -ItemType Directory -Path $dossier | Out-Null
& $binaire --matrix $matrice --operator-template P64 > "$dossier/fiche-P64.json"
& $binaire --matrix $matrice --operator-template P66 > "$dossier/fiche-P66.json"
& $binaire --matrix $matrice > "$dossier/lacunes-sans-releve.json"
# Passer à la suite après préparation des copies privées.
& $binaire --matrix $matrice --raw-root "$dossier/raw" --submission submission.json `
  --current-sha256 $courant --policy "$dossier/politique.json" --policy-sha256 $politiqueSha `
  > "$dossier/recu.json"
$controleCode = $LASTEXITCODE
```

Un code 2 indique un rejet du dépôt ou un contrôle en échec. Lire le motif
sur stderr pour un rejet global. Le code 0 couvre aussi un dossier incomplet.
Consulter les contrôles de chaque porteur dans le reçu.

| État | Interprétation |
|---|---|
| `PASS` | Critère technique et pièces attendues contrôlés sur ce relevé. |
| `FAIL` | Relevé incohérent, empreinte non conforme ou marge conservatrice insuffisante. |
| `MISSING` | Relevé requis absent du dossier. |
| `NOT_RUN` | Analyse sans relevé ou étape hors du contrôle A.7. |
| `PENDING_AUTHORIZED_REVIEW` | Revue et décision de la personne habilitée encore attendues. |

Le responsable compare les empreintes au dossier publié en privé.
Le rejeu en lecture seule d’une archive sur sa propre empreinte permet
un audit historique. La vérification de fraîcheur compare le dépôt présenté
à l’empreinte du dépôt courant reçue indépendamment. La réutilisation
manuelle d’une ancienne empreinte ne démontre aucune fraîcheur.

Rechercher un écart de données ou de calcul avec le lecteur indépendant
sur les reçus sans échec technique. Le lecteur recalcule les produits
de matrices, la marge et la complétude et donne le SHA-256 des octets
du reçu. Cette empreinte identifie les octets privés contrôlés.

```powershell
python -B convergence_manager/tests/recheck_v3_a7_receipt.py --matrix $matrice `
  --raw-root "$dossier/raw" --submission submission.json --current-sha256 $courant `
  --policy "$dossier/politique.json" --policy-sha256 $politiqueSha --receipt "$dossier/recu.json"
```

Pour préparer D.1 après la collecte, réunir les originaux et l’appui
effectivement applicable, les soumettre au responsable habilité selon
le [protocole de revue A.5](../a5/review_protocol.md) et obtenir une
autorisation distincte. La confiance de production, la reprise durable
avec ancrage monotone externe et la qualification de la transaction
physique privée suivent le [protocole A.6](../a6/protocol.md).
