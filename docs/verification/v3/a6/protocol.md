# Protocole technique V3-A.6

## Demande et autorité

Le point d’entrée est `convergence_core v3-build` avec une demande
`v3.a6.admission_request/1`. Le canal de confiance de banc fournit séparément
`--a5-trust` et `--a5-trust-sha256`. Les exécutables FreeCAD et T0 et le
checkout de banc sont fixés à la compilation. Les options d’exécutables de
V3-B.1 sont refusées à cette entrée. Les appels A.5 gardent leur contrat et leur
comportement de préadmission.

Deux clés Ed25519 distinctes authentifient la revue et le registre A.5. La
revue signe les octets UTF-8 exacts de `v3.a6.review/1`, dont l’identifiant,
l’empreinte de la confiance, les dates d’émission et d’expiration, les
empreintes du paquet et de la politique, l’identité du lot par empreinte, la
version du modèle, le profil et sa fermeture XLink, le couple
`anchor:iso-carrier / CREATE_SUPPORT`, le porteur, les bornes et l’effet exact
en millimètres et quaternion XYZW. Elle signe aussi la liste ordonnée des
contrôles et le format `v3.a6.private_evidence/1`. L5 valide l’import A.4,
la concordance du porteur dans le relevé synthétique, les signatures, le
registre et sa consommation via `checkRegistry()`. Une recherche ne transmet
aucun plan mutable dans ce parcours.

La seule traduction native implémentée associe le P64 de banc au porteur
`carrier` et `anchor:iso-carrier` à l’ancre de banc `anchor-new` du profil
scellé B.1 Workholding. Le domaine natif fixe la rotation à l’identité et
`y=z=0`, autorise `x∈[-1,0]` mm et une taille
`[largeur∈[7,9;8], 8, 3]` mm. La pose monde découle de l’ancre sauvegardée.
Le contrôle de service suit la pose locale signée. P66 reste sans traduction
native A.6 sur ce banc. Le contrat décrit la syntaxe et L5 vérifie le domaine.

## États persistés

| État | Condition d’écriture durable |
|---|---|
| `REQUESTED` | La revue, le registre et la disponibilité de l’outillage ont passé la porte initiale. L’identifiant et les empreintes de la revue et de la demande sont inscrits. L’identifiant ne peut plus être utilisé. |
| `AUTHORIZED_RESERVED` | Réservation par le journal A.6 sous le verrou de registre, avant écriture de la consommation de compatibilité A.5 et avant lancement FreeCAD. |
| `BUILDING_PRIVATE` | Référence, copie et réouverture de référence vérifiées. Le constructeur reçoit un travail interne borné. |
| `BUILT` | Sauvegarde achevée, documents fermés, reçu du constructeur cohérent et fermeture résultante mesurée. Seul le fichier d’entrée peut changer. |
| `INDEPENDENTLY_VALIDATED` | Réouverture dans un nouveau processus, mesures exigées `PASS`, validation T0 indépendante et intégrité des entrées. Les artefacts restent privés. |
| `COMMITTED_PRIVATE` | Seconde vérification complète de l’autorité, de l’expiration, de la demande, des entrées et du paquet, avec journalisation du reçu et de son SHA-256 sous le verrou du registre. |
| `QUARANTINED` | Échec après réservation ou transaction non terminale détectée en reprenant l’accès exclusif au journal. Aucun nouvel essai avec cet identifiant. |
| `ABORTED` | État terminal reconnu par le format. Le parcours livré emploie la quarantaine pour les interruptions et n’expose aucune commande de réactivation. |

Le service provisionne une clé HMAC aléatoire de 32 octets, son SHA-256 dans
la confiance signée par empreinte, et un journal commençant par un événement
`GENESIS` authentifié. Le fichier `a6-journal.jsonl` reçoit uniquement des
ajouts sous accès exclusif du système. Sous Windows, le handle interdit les
ouvertures concurrentes en écriture et le remplacement du fichier. Chaque
ligne contient les octets de l’événement en base64 et un HMAC-SHA256 calculé
sur ces octets. Le numéro de séquence, le HMAC précédent, le schéma, l’état,
l’horodatage UTC et les données de l’état sont authentifiés. Le premier
événement a la séquence zéro, un HMAC précédent de 64 zéros, un identifiant
vide et un objet `detail` vide. Chaque ajout est synchronisé sur le support
avant que l’exécution continue. Toute lecture ou écriture incertaine ferme
l’admission.

Le registre est mis à jour exclusivement sous `a5-consumption.lock` par son
administrateur. Une observation authentifiée conserve le nombre d’événements
et l’empreinte JSON compacte du préfixe. L’heure UTC du dernier événement
bloque un retour d’horloge. Le journal conserve son propre historique même si
la copie de compatibilité A.5 est restaurée. La possession du journal durant
la construction limite à une transaction active par racine de confiance.
L’acquisition initiale du journal échoue immédiatement s’il est occupé. La
finalisation détient le journal et attend le verrou A.5 au plus trois secondes.

Les copies XLink, dossiers de travail et artefacts sont disjoints des entrées
et scellés sous `.runtime`. L5 contrôle les chemins canoniques, rejette les
traversées, redirections et liens multiples aux frontières et vérifie les
octets aux changements d’étape. La construction, la réouverture et T0
s’exécutent séparément. Les fichiers de travail internes B.1 n’emportent
aucune admission A.6. Le reçu `admission.json` est une copie publiée
atomiquement après `COMMITTED_PRIVATE`. L’événement authentifié porte la
liste des artefacts vérifiés et l’empreinte du reçu exact.

## Reprise administrateur

1. Suspendre les écritures du service sur la racine concernée et relever les
   empreintes du journal, du registre signé et du dossier privé. Préserver
   les octets originaux et les horodatages. Identifier d’éventuels processus
   FreeCAD encore actifs dans l’espace privé.
2. Vérifier sur une copie l’empreinte de la clé et de la confiance, puis
   recalculer pour chaque ligne le HMAC des octets décodés, la séquence et
   le lien précédent. Vérifier UTC, transitions, identifiants et préfixe
   du registre. Le lecteur du test A.6 reproduit le calcul d’authentification.
   Un journal absent, déchiré ou illisible entraîne la quarantaine
   administrative de la racine et un refus de l’exécutable.
3. Pour une chaîne valide, l’ouverture suivante sous verrou marque les
   transactions inachevées `QUARANTINED`. Pour un reçu externe perdu,
   retrouver l’événement `COMMITTED_PRIVATE` et vérifier les empreintes des
   artefacts privés avant restitution du reçu et vérification de son SHA-256.
   Si une preuve manque, conserver le journal et traiter le dossier comme
   indisponible. Une nouvelle construction demande un nouvel identifiant
   signé. Conserver l’historique d’origine, sans effacer ni réinitialiser les
   décisions consommées.
4. Si toute la racine est compromise ou restaurée sans témoin indépendant,
   retirer cette racine du service. Une reprise habilitée exige une
   réconciliation avec un ancrage monotone indépendant avant tout
   reprovisionnement.

La campagne couvre les interruptions de processus et une sauvegarde privée
artificiellement tronquée. Aucun essai de coupure électrique, de restauration
cohérente de toute la racine ni de déploiement Linux n’a été exécuté. Le
service doit contrôler les droits du checkout, des binaires, modules
FreeCAD, dépendances et dossiers privés. Les empreintes de l’outillage
qualifient les exécutions observées. La voie physique est fermée dès l’entrée
par `PHYSICAL_ADMISSION_NOT_CONFIGURED`. Le canal de déploiement habilité
devra fournir la confiance hors requête et qualifier le stockage et la reprise
avant un essai réel.
