"""Infrastructure : catalogue courant, supersession et guide d'ouverture CAO."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

plan = read(VER / 'plan_tri_sous_assemblages_20261004.json')
controls = {mode: read(VER / f'controle_tri_{mode}_20261004.json')
            for mode in ['courant', 'archive', 'source_stack']}
assert all(c['finalisation_correcte'] for c in controls.values())
archive = Path(plan['archive'])
prefix = 'archives/avant_tri_20261004/'
mapping = {r['fichier']: prefix + r['fichier'] for r in plan['operations']
           if r['operation'] == 'move' and r['fichier'].endswith('.FCStd')}

def relocate(value):
    if isinstance(value, list):
        return [relocate(x) for x in value]
    if isinstance(value, dict):
        return {k: relocate(v) for k, v in value.items()}
    if isinstance(value, str):
        normal = value.replace('\\', '/')
        if normal in mapping:
            return mapping[normal]
        project_prefix = 'hardware/mecanique/cartographe/'
        if normal.startswith(project_prefix) and normal[len(project_prefix):] in mapping:
            return project_prefix + mapping[normal[len(project_prefix):]]
    return value

m = relocate(read(MEC / 'manifest.json'))
catalog = []
for name in plan['sous_assemblages_conserves']:
    catalog.append({'reference': name, 'fichier': f'sous_assemblages/{name}.FCStd',
                    'role': 'construction' if name in ['SA02_Cassette20Ah_Coulissante', 'SA02_Contacts20Ah'] else 'courant',
                    'realisation_CAO': 'Implémenté', 'statut': 'À valider'})
catalog.append({'reference': plan['assemblage_conserve'],
                'fichier': f"assemblages/{plan['assemblage_conserve']}.FCStd",
                'role': 'integration_locale_sans_faisceau',
                'realisation_CAO': 'Implémenté', 'statut': 'À valider'})
m['assemblages'] = [dict(row, nom=row['reference'], courant_catalogue=True,
                        archive_conception=False) for row in catalog]
rows = []
for row in controls['courant']['occurrences']:
    owner = row['assemblage'].removeprefix('hardware/mecanique/cartographe/')
    source = row['source_fichier'].removeprefix('hardware/mecanique/cartographe/')
    rows.append({'assemblage': Path(owner).stem, 'fichier_assemblage': owner,
                 'occurrence': row['occurrence'], 'reference': Path(source).stem,
                 'source_fichier': source, 'source_objet': row['source_objet'],
                 'placement_matrice': row['matrice_placement'], 'LinkTransform': row['LinkTransform'],
                 'courant_catalogue': True, 'statut': 'À valider'})
m['occurrences'] = rows
refs = {str(r.get('fichier', '')).replace('\\', '/'): r for r in m['references']}
for config in ['configuration_systeme_candidate', 'configuration_stack_revue_20261003']:
    for row in m[config].get('references', m[config].get('references_nouvelles', [])):
        path = row['fichier'].removeprefix('hardware/mecanique/cartographe/')
        if path.startswith(prefix):
            continue
        refs[path] = dict(row, fichier=path)
for row in catalog:
    refs[row['fichier']] = dict(row, type='assemblage')
m['references'] = list(refs.values())
for row in m['references']:
    if row.get('quantite_drone_actif') is not None:
        row.setdefault('quantite_historique_drone_avant_tri', row['quantite_drone_actif'])
        row['quantite_drone_actif'] = None
        row['limite_quantite'] = 'Aucun drone complet courant défini par le tri ; quantité historique dans instantané archivé.'
m['date_mise_a_jour'] = '2026-10-04'
m['statut'] = 'Catalogue des dernières CAO implémentées ; qualification physique À valider'
m['configuration_avionique'] = {
    'active': 'SA03_CA01_Holybro_Revue_20261003',
    'statut': 'Implémenté ; qualification mécanique, électrique et thermique À valider',
    'architecture': 'Fixation commune P17/plaque/P55/CA01/P54/pieds OEM ; DOC-MEC§4.4.1.1',
    'verification': 'verification/controle_stack_revue_20261003.json',
    'faisceau_recale': False,
    'configuration_precedente': prefix + 'manifest.json#configuration_avionique'}
m['configuration_dock20Ah']['archive_conception'] = True
m['configuration_systeme_candidate']['archive_conception'] = True
m['configuration_systeme_candidate']['remplace_dans_catalogue_par'] = 'catalogue_courant_20261004'
m['catalogue_courant_20261004'] = {
    'date': '2026-10-04', 'selection': catalog,
    'sous_assemblages_courants': 10, 'montages_construction': 2,
    'assemblage_local': f"assemblages/{plan['assemblage_conserve']}.FCStd",
    'assemblage_drone_complet_courant': None, 'qualification_physique': False,
    'GNSS_sur_plateaux_implante': False, 'faisceau_recale_sur_stack': False,
    'archive_autonome': prefix.rstrip('/'), 'supersession_fichiers': mapping,
    'manifest_avant_tri': prefix + 'manifest.json',
    'manifest_avant_tri_sha256': sha(archive / 'manifest.json'),
    'verification': 'verification/controle_tri_courant_20261004.json',
    'revue': 'verification/revue_independante_tri_20261004.json',
    'verification_archive': 'verification/controle_tri_archive_20261004.json'}
write(MEC / 'manifest.json', m)
c = relocate(read(MEC / 'configuration_cible_20261003.json'))
if c['configuration']['active'] is not None:
    c['configuration']['ancienne_configuration_active_archivee'] = c['configuration']['active']
c['configuration']['active'] = None
c['configuration']['catalogue_courant'] = 'manifest.json#catalogue_courant_20261004'
c['configuration']['assemblage_local_courant'] = f"assemblages/{plan['assemblage_conserve']}.FCStd"
c['configuration']['limite_revue'] = 'Maquette complète antérieure archivée ; catalogue courant des dernières implémentations. Aucune configuration complète nouvellement qualifiée.'
c['configuration']['tri_sous_assemblages'] = 'Implémenté ; GNSS sur plateaux Planifié, faisceau non recalé sur nouvelle stack.'
write(MEC / 'configuration_cible_20261003.json', c)
readme = '''# Cartographe — dernières implémentations FreeCAD

Ouvrir [Integration_Stack_Revue_20261003.FCStd](assemblages/Integration_Stack_Revue_20261003.FCStd)
pour la dernière intégration mécanique locale : châssis, dock20Ah, stack,
bloc capteurs et distribution. GNSS et faisceau restent des sous-assemblages
séparés ; cette étude locale n'est pas un drone complet qualifié.

Le catalogue courant est `manifest.json`, clé `catalogue_courant_20261004`.
Conserver toute l'arborescence pour résoudre les liens externes. Les références
de pièces achetées/fabriquées restent dans `pieces/`.
Les dernières vues natives de la stack sont dans
[la galerie FreeCAD](exports/stack_avionique_revue_20261003/index.html).

## Sous-assemblages à ouvrir

| Fonction | Fichier courant |
|---|---|
'''
labels = ['Châssis et plaque basse reprise', 'Dock batterie20Ah complet',
          'Stack Holybro/CA01 revue', 'Capteurs avec appuis', 'Bloc optique/LiDAR',
          'Appui Sorbothane réutilisé quatre fois', 'GNSS Helical G4 candidat',
          'PM08/PDB candidats', 'Station sol, dernière représentation disponible',
          'Réservations de faisceau, passages À valider',
          'Construction : cassette coulissante', 'Construction : contacts dock']
for name, label in zip(plan['sous_assemblages_conserves'], labels):
    readme += f'| {label} | [{name}.FCStd](sous_assemblages/{name}.FCStd) |\n'
readme += '''
L'antenne GNSS sur le plateau supérieur et le récepteur sous la batterie
restent une option étudiée ; les fichiers conservés gardent leur pose précédente.
Le faisceau système n'est pas recalé sur la stack revue. Les limites physiques,
la BOM et les validations sont dans [DOC-MEC](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md),
[DOC-ELEC](../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md)
et [DOC-VAL](../../../docs/VALIDATION_QUALIFICATION.md).

## Archives et maintenance

Les anciens sous-assemblages, assemblages globaux et sauvegardes sont dans
`archives/avant_tri_20261004/`. Cette archive contient une copie des pièces
et des montages liés sous les mêmes chemins relatifs : ouvrir les natifs
depuis cette arborescence entière. `manifest.json` et `README.md` archivés
sont des instantanés antérieurs au tri ; leur contexte de commandes est historique.
Les recettes historiques du 6 septembre au 3 octobre restent des preuves de
construction ; elles ne constituent pas une commande générale de régénération
du catalogue courant et peuvent recréer des variantes retirées.

Le dock dépend encore des montages de construction `SA02_Cassette20Ah_Coulissante`
et `SA02_Contacts20Ah`, conservés dans le dossier courant.
La recette de stack `verification/build_stack_revue_20261003.py` reprend
le châssis rehaussé archivé et rétablit ses liens vers les pièces courantes
avec `sources_cao_archivees_20261004.py`. La reprise de source a été vérifiée ;
la stack n'a pas été régénérée à l'occasion du tri.

Vérifier le rangement et les liens, dans des processus PythonFreeCAD séparés :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py courant
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py archive
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py source_stack
```

Ces commandes s'exécutent depuis le répertoire cartographe. Le tri et les
contrôles ne modifient aucun placement ni géométrie native.
'''
(MEC / 'README.md').write_text(readme, encoding='utf-8')
assert all((MEC / r['fichier']).exists() for r in catalog)
assert all((MEC / r['source_fichier']).exists() and (MEC / r['fichier_assemblage']).exists() for r in rows)
write(VER / 'controle_catalogue_tri_20261004.json', {
    'date': '2026-10-04', 'finalisation_correcte': True, 'sous_assemblages': 12,
    'assemblages_locaux': 1, 'occurrences': len(rows), 'supersession': mapping,
    'geometrie_et_placements_modifies': False,
    'manifest_sha256': sha(MEC / 'manifest.json'),
    'configuration_cible_sha256': sha(MEC / 'configuration_cible_20261003.json'),
    'README_sha256': sha(MEC / 'README.md'),
    'recette_stack_adaptee_sha256': sha(VER / 'build_stack_revue_20261003.py'),
    'regeneration_stack_executee': False,
    'preuves_historique_regeneration_reinterpretees': False})
print(json.dumps({'catalogue': len(catalog), 'occurrences': len(rows), 'archives': len(mapping)}))
