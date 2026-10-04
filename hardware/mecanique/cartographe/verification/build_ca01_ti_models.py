"""Recette CAO d'infrastructure : boîtiers TI dérivés des plans, pas des STEP OEM.

Exécuter avec le Python FreeCAD1.1.3. La construction ne modifie pas les
empreintes électriques. Les dimensions nominales et maximales ne remplacent
pas la métrologie des pièces reçues ; les formes non cotées sont omises.
"""
from pathlib import Path
import json, hashlib,sys
import FreeCAD as A
import Import

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
ELEC=ROOT/'hardware/electronique/cartographe'
OUT=MEC/'exports/ca01_modeles3d_20261001'
OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bbox(s):
 b=s.BoundBox
 return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def add_box(doc,part,name,x,y,z,l,w,h,color):
 b=doc.addObject('PartDesign::Body',name)
 part.addObject(b)
 f=b.newObject('PartDesign::AdditiveBox',name+'_Volume')
 f.Length=l;f.Width=w;f.Height=h;f.Placement.Base=A.Vector(x,y,z)
 doc.recompute()
 if b.ViewObject:
  b.ViewObject.ShapeColor=color
  f.ViewObject.ShapeColor=color
 return b

specs=[
 {'name':'TI_Q5A','mpn':'CSD19531Q5A','refs':['Q101','Q102','Q103','Q104'],
  'source':'TI_CSD19531Q5A_datasheet.pdf','page':9,'url':'https://www.ti.com/lit/ds/symlink/csd19531q5a.pdf',
  'body':[5.75,4.9,1.0],'max_total':[6.1,5.0,1.1],'z0':0.25,
  'terminals':[[-2.695,y,0,.61,.41,.25] for y in [1.905,.635,-.635,-1.905]]+
              [[2.695,y,0,.61,.41,.25] for y in [1.905,.635,-.635,-1.905]],
  'thermal':[.65,0,0,3.58,3.81,.25],
  'limits':'Corps E1=5.75,D1=4.9 ; métal E=6.0,L=.61,b=.41. Plaque centrale simplifiée E2×D2, centreX+.65 après miroir de la bottomview : E/2-H-E2/2=3-.56-1.79 ; épaules E3/e1/e2 omises. Pas de forme propriétaire exacte ni détail de puce.'},
 {'name':'LM74800_DRR','mpn':'LM74800QDRRRQ1','refs':['U101'],
  'source':'TI_LM7480_Q1_datasheet.pdf','page':43,'url':'https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf',
  'body':[3,3,.8],'max_total':[3.1,3.1,.8],'z0':.025,
  'terminals':[[x,y,0,.42,.25,.2] for x in [-1.29,1.29] for y in [1.25,.75,.25,-.25,-.75,-1.25]],
  'thermal':[0,0,0,1.3,2.5,.2],
  'limits':'Plan DRR0012E, hauteur maximale0.8, corps nominal3×3, plaque thermique nominale1.3×2.5 ; chanfreins optionnels et arrondis non représentés. L’empreinte existante réserve1.5×2.5, contrôle de fabrication hors cette recette.'},
 {'name':'LM76003_RNP','mpn':'LM76003RNPR','refs':['U201','U301'],
  'source':'TI_LM76002_LM76003_SNVSAK0A_201910.pdf','page':53,'url':'https://www.ti.com/lit/ds/symlink/lm76003.pdf',
  'body':[4,6,.8],'max_total':[4.1,6.1,.8],'z0':.025,
  'terminals':[[x,y,0,.55,.25,.2] for x in [-1.725,1.725] for y in [2.5,2,1.5,1,.5,0,-.5,-1,-1.5,-2,-2.5]]+
              [[x,y,0,.25,.4,.2] for y in [-2.8,2.8] for x in [-.75,-.25,.25,.75]],
  'thermal':[0,0,0,1.8,4.5,.2],
  'limits':'Plan RNP0030B 4222784/B ; corps nominal4×6, hauteur maximale0.8, 30contacts + plaque1.8×4.5. Profil des wettable flanks et arrondis omis ; révision reçue B/G à confirmer.'},
 {'name':'TPD1E05U06_DPY','mpn':'TPD1E05U06DPYR','refs':['D503','D504'],
  'source':'TI_TPD1E05U06_datasheet.pdf','page':34,'url':'https://www.ti.com/lit/ds/symlink/tpd1e05u06.pdf',
  'body':[1,.6,.45],'max_total':[1.1,.7,.45],'z0':.025,
  'terminals':[[x,0,0,.25,.5,.13] for x in [-.325,.325]],'thermal':None,
  'limits':'Plan DPY0002A 4224561/C ; corps nominal.6×1, hauteur maximale.45, contacts.5×.25/pas.65 ; repérage et chanfrein optionnels omis.'}
]
selected=sys.argv[1:] or [s['name'] for s in specs]
proofpath=MEC/'verification/modeles_ti_ca01_20261001.json'
results=[s for s in json.loads(proofpath.read_text(encoding='utf-8'))['models'] if s['name'] not in selected] if proofpath.exists() else []
for s in specs:
 if s['name'] not in selected:continue
 d=A.newDocument('CA01_Modele_'+s['name']+'_Plan')
 part=d.addObject('App::Part','Modele')
 part.Label=s['mpn']+' — dérivé du plan TI'
 for key,val in [('Statut','Implémenté ; dimensions et montage À valider'),('Provenance','Modèle projet reconstruit du plan fabricant ; pas un STEP OEM'),('Source',s['url']),('Limites',s['limits'])]:
  part.addProperty('App::PropertyString',key);setattr(part,key,val)
 l,w,h=s['body'];z=s['z0']
 bodies=[add_box(d,part,'Corps',-l/2,-w/2,z,l,w,h-z,(.10,.10,.10))]
 for i,(x,y,z,dx,dy,dz) in enumerate(s['terminals']):
  bodies.append(add_box(d,part,'Contact'+str(i+1),x-dx/2,y-dy/2,z,dx,dy,dz,(.72,.72,.75)))
 if s['thermal']:
  x,y,z,dx,dy,dz=s['thermal']
  bodies.append(add_box(d,part,'PlaqueExposee',x-dx/2,y-dy/2,z,dx,dy,dz,(.72,.72,.75)))
 d.recompute()
 assert all(b.Shape.isValid() and not b.Shape.isNull() for b in bodies)
 native=MEC/'pieces/commerce'/f'CA01_Modele_{s["name"]}_Plan.FCStd'
 step=OUT/f'{s["name"]}_Plan.step'
 d.saveAs(str(native));Import.export(bodies,str(step))
 import Part
 shape=Part.read(str(step))
 assert shape.isValid()
 results.append({**s,'source_path':str((ELEC/'sources_fabricants'/s['source']).relative_to(ROOT)).replace('\\','/'),
  'source_sha256':sha(ELEC/'sources_fabricants'/s['source']),
  'native':str(native.relative_to(ROOT)).replace('\\','/'),'native_sha256':sha(native),
  'step':str(step.relative_to(ROOT)).replace('\\','/'),'step_sha256':sha(step),
  'bbox_mm':bbox(shape),'solids':len(shape.Solids),'valid':True,'kind':'Dérivé du plan fabricant, non OEM',
  'model_transform':{'offset_mm':[0,0,0],'rotation_deg':[0,0,0],'scale':[1,1,1]},'qualification':'À valider'})
 A.closeDocument(d.Name)
target=MEC/'verification/modeles_ti_ca01_20261001.json'
target.write_text(json.dumps({'date':'2026-10-01','toolchain':'FreeCAD1.1.3 Windows amd64','models':results,
 'oem_step_retrieved':False,'search_limits':'TI propose UltraLibrarian, accès téléchargements sponsorisés non réalisé ; noms de modèles absents dans KiCad installé et dépôts officiels interrogés.',
 'hardware_tests_executed':False,'qualification':'À valider'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{'name':s['name'],'solids':s['solids'],'bbox':s['bbox_mm']} for s in results]))
