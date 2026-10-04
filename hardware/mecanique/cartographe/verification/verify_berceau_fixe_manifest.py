"""Contrôle natif/manifeste et conservation de la configuration active, sans save.

Python FreeCAD 1.1 ; après construction et synchronisation du manifeste.
Les empreintes initiales sont reprises de la preuve précédente ou du snapshot
de première exécution. Ce contrôle ne qualifie aucune pièce physique.
"""
from pathlib import Path
import json
import hashlib
import copy
import FreeCAD as A

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
OUT = MEC / 'verification/controle_berceau_fixe_manifest_20261002.json'
BACKUP = ROOT / '.runtime/batterie_reprise_20261002/avant'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

manifest_path = MEC / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
construction_path = MEC / 'verification/construction_berceau_fixe_candidat_20261002.json'
construction = json.loads(construction_path.read_text(encoding='utf-8'))
for variant in construction['assemblies']:
    assert not variant['pack_fixed_interferences']
    assert not variant['maximum_pack_interferences']
    assert all(not step['interferences'] for step in variant['motion_samples'])
    assert all(not step['interferences'] for step in variant['vertical_extraction_samples'])
if OUT.exists():
    active_before = json.loads(OUT.read_text(encoding='utf-8'))['actifs_sha256_avant']
else:
    baseline = json.loads((BACKUP/'empreintes_actifs.json').read_text(encoding='utf-8-sig'))
    active_before = {str(Path(x['Path']).relative_to(ROOT)).replace('\\','/'):x['Hash'].lower() for x in baseline}
active_after = {p:sha(ROOT/p) for p in active_before}
assert active_before == active_after, 'Une CAO active a changé'

references = {r['reference']:r for r in manifest['references']}
candidate_ids = {Path(r['file']).stem for r in construction['references']}
assemblies = [a for a in manifest['assemblages'] if a['nom'].startswith('SA02_BerceauFixe_Candidat')]
assert len(assemblies) == 2 and len(candidate_ids) == 9
assert manifest['configuration_energie']['active'] == 'SA02_Energie_EchangeRapide'
assert not manifest['configuration_energie']['variante_berceau_fixe']['actif_drone']
checks, hashes, errors = [], {}, []
for assembly in assemblies:
    assert assembly['actif_drone'] is False
    path = MEC / assembly['fichier']
    hashes[assembly['fichier']] = sha(path)
    d = A.openDocument(str(path))
    for loaded in A.listDocuments().values():
        loaded.recompute()
    assert abs(d.Parametres.get('B50').Value) < 1e-9
    occurrences = [o for o in manifest['occurrences'] if o['assemblage'] == assembly['nom']]
    links = [o for o in d.Objects if o.TypeId == 'App::Link']
    assert {o.Name for o in links} == {o['occurrence'] for o in occurrences}
    for occurrence in occurrences:
        ref = references[occurrence['reference']]
        assert ref['quantite_drone_actif'] == 0 and ref['actif_drone'] is False
        link = d.getObject(occurrence['occurrence'])
        target = link.LinkedObject
        assert target and target.Name == ref['source_objet']
        assert Path(target.Document.FileName).resolve() == (MEC/ref['fichier']).resolve()
        assert target.Document.getObject('Parametres') is not None
        assert link.Shape.isValid() and len(link.Shape.Solids) == 1
        expected = next(r for r in construction['references'] if r['file'] == ref['fichier'])
        assert abs(link.Shape.Volume-expected['volume_mm3']) < 1e-6
        matrix = link.LinkPlacement.toMatrix().A
        delta = max(abs(a-b) for a,b in zip(matrix,occurrence['placement_matrice']))
        assert delta < 1e-9
        checks.append({'assemblage':assembly['nom'],'occurrence':link.Name,
                       'reference':occurrence['reference'],'volume_mm3':link.Shape.Volume,
                       'solide_valide':True,'erreur_matrice_max':delta,'lien_conforme':True})
        hashes[ref['fichier']] = sha(MEC/ref['fichier'])
    for loaded in A.listDocuments().values():
        errors.extend({'document':loaded.Name,'objet':o.Name,'etat':list(o.State)}
                      for o in loaded.Objects if 'Invalid' in o.State)
assert not errors

# La preuve initiale du manifeste conserve les modifications préexistantes.
preserved = None
baseline_manifest = BACKUP/'hardware__mecanique__cartographe__manifest.json'
if baseline_manifest.exists():
    old = json.loads(baseline_manifest.read_text(encoding='utf-8-sig'))
    restored = copy.deepcopy(manifest)
    restored['references'] = [r for r in restored['references'] if r['reference'] not in candidate_ids]
    names = {a['nom'] for a in assemblies}
    restored['assemblages'] = [a for a in restored['assemblages'] if a['nom'] not in names]
    restored['occurrences'] = [o for o in restored['occurrences'] if o['assemblage'] not in names]
    restored['configuration_energie'].pop('variante_berceau_fixe')
    restored['date_mise_a_jour'] = old['date_mise_a_jour']
    preserved = restored == old
    assert preserved, 'Modification du manifeste en dehors de la variante'

exports = MEC / 'exports/berceau_fixe_candidat_20261002'
for p in sorted(exports.iterdir()):
    if p.suffix.lower() in ('.step','.stl'):
        hashes[str(p.relative_to(MEC)).replace('\\','/')] = sha(p)
for ah in (16,20):
    p = MEC/f'verification/berceau_fixe_{ah}Ah_candidat_20261002.png'
    hashes[str(p.relative_to(MEC)).replace('\\','/')] = sha(p)
volumes = {Path(r['file']).stem:r['volume_mm3']/1000 for r in construction['references']}
result = {'date':'2026-10-02','statut':'À valider','conclusion':'préliminaire',
          'realisation_CAO':'Implémenté','environnement':{'OS':'Windows','architecture':'amd64','FreeCAD':list(A.Version())},
          'exigences':['MEC-ARC-001','MEC-BAT-001','HW-BAT-SWAP-01','HW-BAT-SWAP-04'],
          'protocole':'Réouverture/recalcul dans un processus neuf, 15 liens comparés au manifeste, forme et volume comparés à la preuve de construction, aucune sauvegarde',
          'actifs_sha256_avant':active_before,'actifs_sha256_apres':active_after,
          'CAO_active_inchangee':True,'contenu_manifest_preexistant_preserve':preserved,
          'manifest_sha256':sha(manifest_path),'construction_sha256':sha(construction_path),
          'script_sha256':sha(Path(__file__)),'sources_exports_apercus_sha256':hashes,
          'occurrences_verifiees':checks,'erreurs_recalcul':errors,
          'volumes_cm3':volumes,
          'hypothese_masse':{'densite_polymere_g_cm3':1.25,
              'P23_P25_16Ah_g':(volumes['P23_BerceauFixe_Candidat']+volumes['P25_CapotCaptif_Candidat'])*1.25,
              'P23_P25_P26_20Ah_g':(volumes['P23_BerceauFixe_Candidat']+volumes['P25_CapotCaptif_Candidat']+volumes['P26_Cale20Ah_Candidat'])*1.25,
              'limite':'Volumes pleins et densité hypothétique ; G10, mousses, visserie, axe, loquet, gâche, connecteur/support et faisceau exclus ; aucune masse installée ni gain en autonomie établi.'},
          'limites':['Cinématique/accrochage du loquet non modélisés, fixation réelle et protection du pack À valider.',
                     'Contrôle CAO sans essai physique, résistance, vibration, thermique, cycles ni vol.']}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for d in list(A.listDocuments().values()):
    A.closeDocument(d.Name)
print(json.dumps({'occurrences':len(checks),'references':len(candidate_ids),'actifs_inchanges':True,'manifest_preexistant_preserve':preserved}))
