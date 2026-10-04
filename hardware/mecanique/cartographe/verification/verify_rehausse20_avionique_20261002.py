"""Réouverture indépendante des variantes rehausse20, sans sauvegarde de CAO."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,'C:/Program Files/FreeCAD 1.1/bin')
import FreeCAD as A,Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bounds(s):
 b=s.BoundBox;return [b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax]
def common_if_close(a,b):
 return a.common(b).Volume if a.BoundBox.intersect(b.BoundBox)else 0
construction=json.loads((MEC/'verification/construction_rehausse20_avionique_20261002.json').read_text(encoding='utf-8'))
c=A.openDocument(str(MEC/'sous_assemblages/SA01_Chassis_Rehausse20.FCStd'))
a=A.openDocument(str(MEC/'sous_assemblages/SA03_Avionique_Rehausse20.FCStd'))
for d in A.listDocuments().values():d.recompute()
hashes={Path(d.FileName):sha(Path(d.FileName))for d in A.listDocuments().values()if d.FileName}
errors=[{'document':d.Name,'objet':o.Name,'etat':list(o.State)}for d in A.listDocuments().values()for o in d.Objects if 'Invalid'in o.State]
links=[o for d in[c,a]for o in d.Objects if o.TypeId=='App::Link']
assert all(o.LinkedObject is not None and not o.LinkTransform for o in links)
native=[]
for name in['P27_Interface_Pixhawk_Rehausse20','P37_Entretoise70_6061_M3','P38_Plateau309_PercagesRails']:
 d=next(d for d in A.listDocuments().values()if Path(d.FileName).stem==name)
 out=d.getObject('Resultat');r=d.getObject('Reference')
 native.append({'reference':name,'forme_valide':out.Shape.isValid(),'solides':len(out.Shape.Solids),
                'volume_mm3':out.Shape.Volume,'bbox_mm':bounds(out.Shape),'volume_lien_minus_final_mm3':r.Shape.Volume-out.Shape.Volume,
                'operations_natives':sum(o.TypeId in['Part::Box','Part::Cylinder','Part::Cut','Part::MultiFuse']for o in d.Objects)})
oem=next(d for d in A.listDocuments().values()if Path(d.FileName).stem=='EQ_Chassis_X650')
plate=c.getObject('Part__Feature311').Shape
p38=c.getObject('Part__Feature309').Shape
p27=a.getObject('P27_Interface_Pixhawk').Shape
holes=[]
for x in[-43,43]:
 for y in[-29,29]:holes.append({'axe_mm':[x,y],'OEM311_libre_Z104':not plate.isInside(A.Vector(x,y,104),1e-7,False),
                               'P27_libre_Z107':not p27.isInside(A.Vector(x,y,107),1e-7,False)})
railholes=[]
for x in[-40,40]:
 for y in[-51.5,51.5]:railholes.append({'axe_mm':[x,y],'P38_libre_Z32':not p38.isInside(A.Vector(x,y,32),1e-7,False)})
collisions=[]
for aa in a.Objects:
 if aa.TypeId!='App::Link':continue
 for bb in c.Objects:
  if bb.TypeId!='App::Link':continue
  vol=common_if_close(aa.Shape,bb.Shape)
  if vol>1e-6:collisions.append({'avionique':aa.Name,'chassis':bb.Name,'volume_mm3':vol})
internal=[]
for name in['Isolant_Pixhawk','EQ_Pixhawk6X_Occurrence','Sangle_Pixhawk']:
 internal.append({'a':'P27_Interface_Pixhawk','b':name,'volume_commun_mm3':common_if_close(p27,a.getObject(name).Shape)})
columnchecks=[]
for col in[o for o in c.Objects if o.Name.startswith('Colonne70_')]:
 cs=col.Shape
 contacts=[]
 for name in['Part__Feature309','Part__Feature311']+[f'Part__Feature{i:03}'for i in list(range(92,96))+list(range(104,108))]:
  volume=common_if_close(cs,c.getObject(name).Shape)
  if volume>1e-6:contacts.append({'objet':name,'volume_mm3':volume})
 columnchecks.append({'colonne':col.Name,'bbox_mm':bounds(cs),'intersections_volumiques':contacts})
pack=Part.makeBox(198,78,60,A.Vector(-99,-39,40))
packchecks=[{'avionique':o.Name,'volume_mm3':common_if_close(pack,o.Shape)}for o in a.Objects if o.TypeId=='App::Link']
upperbbox={o.Name:bounds(o.Shape)for o in a.Objects if o.TypeId=='App::Link' and o.Name in
           ['P27_Interface_Pixhawk','EQ_Pixhawk6X_Occurrence','Sangle_Pixhawk','VisHaute_1','EcrouHaut_1']}
originals_unchanged=all(sha(ROOT/path)==h for path,h in construction['sources_originales_sha256_avant'].items())
report={'date':'2026-10-02','statut':'À valider','FreeCAD':list(A.Version()),'script_sha256':sha(Path(__file__)),
        'erreurs_recalcul':errors,'liens_resolus':len(links),'LinkTransform_false_partout':True,
        'natives':native,'axes_avionique_verifies':holes,'axes_rails_verifies':railholes,
        'avionique_vs_chassis_intersections':collisions,'P27_vs_equipements':internal,
        'colonnes_vs_plateaux_vis':columnchecks,'pack_max_vs_avionique':packchecks,'bbox_avionique_superieure':upperbbox,
        'sources_originales_inchangees':originals_unchanged,'fichiers_CAO_inchanges_par_verification':all(sha(p)==h for p,h in hashes.items()),
        'sha256_avant_verification':{str(p.relative_to(ROOT)).replace('\\','/'):h for p,h in hashes.items()},
        'sha256_apres_verification':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p)for p in hashes},
        'limites':['Contrôle géométrique seulement ; rigidité, serrage, taraudages et tenue carbone non qualifiés.',
                   'VisM2 descendantes jusqu’àZ100,5 et écrousZ101,4 : couvercle mobile101..102 à dégager sur tout le trajet.',
                   'AxesM3 rails et têtes sous-face vérifiés ensuite contre géométrie définitiveSA02.',
                   'Plateaux/colonnes/avionique candidats ; drone actif non modifié par ces scripts.']}
assert not errors and originals_unchanged and report['fichiers_CAO_inchanges_par_verification']
assert all(x['forme_valide'] and x['solides']==1 and abs(x['volume_lien_minus_final_mm3'])<1e-6 for x in native)
assert all(x['OEM311_libre_Z104']and x['P27_libre_Z107']for x in holes)
assert all(x['P38_libre_Z32']for x in railholes)
assert not collisions and all(x['volume_commun_mm3']<1e-6 for x in internal)
assert all(not x['intersections_volumiques']for x in columnchecks)
assert all(x['volume_mm3']<1e-6 for x in packchecks)
(MEC/'verification/reouverture_rehausse20_avionique_20261002.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'erreurs':len(errors),'liens':len(links),'collisions':len(collisions),'originaux_inchanges':originals_unchanged}),flush=True)
for d in list(A.listDocuments().values()):A.closeDocument(d.Name)


