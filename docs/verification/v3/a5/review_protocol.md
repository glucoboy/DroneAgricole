# Revue habilitée et décision L5 V3-A.5

## Rôles et autorité de confiance

L’opérateur prépare le paquet privé avec les originaux et leurs empreintes.
Le responsable matériel vérifie la lisibilité des sources, leur applicabilité au lot,
le montage, la tolérance, l’incertitude et les limites de l’opération. Un
administrateur du registre authentifie le cycle d’émission et de révocation
avec une clé distincte. Les identités et les clés publiques viennent de la
configuration indépendante `v3.a5.trust/1`. Le déploiement doit associer
cette configuration au responsable matériel habilité. Les clés privées
sont détenues par leurs propriétaires dans leur dépôt privé.

Le binaire de la campagne utilise une racine et un registre jetables
`TEST_ONLY`, dont les droits se limitent à `SYNTHETIC_BENCH`. La valeur de
`L5_A5_PHYSICAL_TRUST_SHA256` de la livraison reste vide. Une configuration
réelle devra provenir du canal habilité de déploiement. La demande ne porte
ni clé, ni configuration de confiance, ni empreinte de confiance réelle.
[Schéma de la demande et des charges utiles](admission_contract.schema.json)

## Parcours de décision

1. L’import A.4 vérifie l’identité, les documents et leurs SHA-256,
   les datums aller et retour, les unités et l’intervalle d’incertitude.
   Le résultat technique `PENDING_AUTHORIZED_REVIEW` permet une revue.
   L’autorité de l’import reste `DENY`.
2. Le responsable décide sur le paquet et l’applicabilité des mesures.
   Pour une décision positive, l’enveloppe `v3.a5.signed_review/1`
   transporte en base64 les octets JSON UTF-8 exacts de la décision et
   leur signature Ed25519. La décision identifie le dossier, la politique,
   le lot, le profil, la fermeture XLink, la configuration, la version du
   modèle, l’occurrence, l’opération, le support borné, les contrôles et
   les dates UTC. L’ordre ou l’encodage des octets signés est conservé.
3. Le registre signé garde l’identifiant, le SHA-256 de la revue et la date
   de chaque émission ou révocation. Publier une nouvelle version en
   conservant l’historique des événements. Retirer une décision via un
   événement de révocation lié à son identifiant et à son empreinte.
4. L5 vérifie les signatures contre les deux clés publiques de confiance,
   les empreintes du paquet et de la politique, la fermeture XLink et le
   couple occurrence–opération. Il vérifie les bornes de la transformation
   et la disponibilité des contrôles exigés. L’état de consommation est
   privé à la racine de confiance, verrouillé pendant l’enregistrement.
   Un dossier déjà consommé, révoqué ou hors période est refusé.

Avant le premier usage, le responsable du déploiement initialise sous la
racine de confiance `a5-consumption.json` au schéma `v3.a5.consumption/1`.
L’état contient `registry_events=0`, `registry_prefix_sha256` égal au
SHA-256 des octets UTF-8 `[]`, `last_seen_utc` en UTC et `consumed={}`.
L’absence d’état ferme l’admission. Le registre, son état et le verrou
restent accessibles en écriture aux seuls services habilités. Toute mise à
jour du registre prend le même verrou `a5-consumption.lock`.

L5 enregistre la consommation avant de publier l’admission. Un reçu
perdu après cette écriture exige une nouvelle décision avec un nouvel
identifiant. Les préfixes historiques signés et les décisions consommées
restent dans le domaine de confiance.

## Premier couple cartographe

`CREATE_SUPPORT` sur `anchor:iso-carrier` demande un porteur P64 ou P66
identifié, un appui, une visserie, une garde d’accès et un domaine démontrés.
Les gardes à exécuter sur la copie privée figurent dans le
[dossier préalable](create_support_iso_readiness.json). Les contrôles de
construction et de réception restent des étapes distinctes. Avec les
données présentes, l’analyse du cartographe reste `READ_ONLY_IMPACT`.
