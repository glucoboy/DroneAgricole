"""Infrastructure CAO : références commerciales Southco depuis plans originaux.
Aucune pièce à fabriquer ni cinématique interne reconstruite. Exécuter avec
C:/Program Files/FreeCAD 1.1/bin/python.exe. Sans modifier les assemblages actifs.
"""
from pathlib import Path
import json, hashlib, math
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
SOURCE=MEC/'sources_fabricants/batterie20Ah_20261002'
PROOF=MEC/'verification/construction_latching20Ah_20261002.json'
BOM=MEC/'verification/bom_latching20Ah_20261002.json'
SOURCE_URLS={
 'Southco_R4_catalogue_en.pdf':'https://media.southco.com/media/static/Literature/r4-r.en.pdf',
 'Southco_J-R4-05-10_plan.pdf':'https://media.southco.com/media/static/JDrawing/j-r4-05-10.pdf',
 'Southco_TD-R4-05-J_performance.pdf':'https://media.southco.com/media/static/TestDataSheet/TD-R4-05-J.pdf',
 'Southco_DogAndDrive_micro_rotary_application.pdf':'https://media.southco.com/media/static/en/case-study/2023-cs-dog-and-drive-en.pdf'}
LIMITES="Représentation commerciale simplifiée des interfaces cotées ; pas mécanisme fonctionnel CAO. Cliquet, ressort, détente et cinématique d'engagement non fournis. Profil extérieur gâchette/bouche simplifié ; courses entre premier contact, stage secondaire et primaire inconnues. Masses et charges admissibles inconnues. Ne pas fabriquer ce modèle."
RESULTS=[]

def new(name,mpn,params):
 d=A.newDocument(name)
 r=d.addObject('App::Part','Reference')
 r.Label=mpn+' — interfaces commerciales simplifiées'
 for k,v in {'Etat':'À valider','RealisationCAO':'Implémenté','Fabricant':'Southco','MPN':mpn,'Limites':LIMITES,'Source':'Southco_J-R4-05-10_plan.pdf ; catalogue p.290/291 ; TD-R4-05-J','RepereLocal':'X longueur de face, Y axe gâche, Z hauteur ; bouche côté +X, insertion −X ; montage porté par liens externes.'}.items():
  r.addProperty('App::PropertyString',k);setattr(r,k,v)
 s=d.addObject('Spreadsheet::Sheet','Parametres');r.addObject(s)
 for i,(key,val) in enumerate(params.items(),1):
  s.set('A'+str(i),key);s.set('B'+str(i),str(val)+' mm');s.setAlias('B'+str(i),key)
 return d,r,s

def ex(o,p,s):o.setExpression(p,s)
def box(d,name,dim,pos):
 o=d.addObject('Part::Box',name)
 for p,v in zip(('Length','Width','Height'),dim):ex(o,p,v)
 for p,v in zip(('Placement.Base.x','Placement.Base.y','Placement.Base.z'),pos):ex(o,p,v)
 return o
def cyl(d,name,radius,height,pos,axis=(0,1,0)):
 o=d.addObject('Part::Cylinder',name);ex(o,'Radius',radius);ex(o,'Height',height)
 o.Placement.Rotation=A.Rotation(A.Vector(0,0,1),A.Vector(*axis))
 for p,v in zip(('Placement.Base.x','Placement.Base.y','Placement.Base.z'),pos):ex(o,p,v)
 return o
def fuse(d,name,objects):
 o=d.addObject('Part::MultiFuse',name);o.Shapes=objects;o.Refine=True
 for x in objects:x.Visibility=False
 return o
def cut(d,name,base,tool):
 o=d.addObject('Part::Cut',name);o.Base=base;o.Tool=tool;o.Refine=True
 base.Visibility=False;tool.Visibility=False;return o

def save(d,r,out):
 r.addObject(out);out.Label='Interfaces cotées — solide simplifié final'
 for o in d.Objects:
  if o.TypeId.startswith('Part::') and o!=out:o.Visibility=False
 out.Visibility=True;d.recompute()
 assert out.Shape.isValid() and out.Shape.Volume>0,d.Name
 assert abs(r.Shape.Volume-out.Shape.Volume)<1e-6,(d.Name,'Reference inclut des outils')
 path=MEC/'pieces/commerce'/(d.Name+'.FCStd');d.saveAs(str(path))
 before=out.Shape.Volume;A.closeDocument(d.Name)
 rd=A.openDocument(str(path));rd.recompute()
 rr=rd.getObject('Reference');ro=rd.getObject('Resultat')
 assert ro.Shape.isValid() and abs(ro.Shape.Volume-before)<1e-6
 errors=[o.Name for o in rd.Objects if 'Invalid' in o.State]
 assert not errors,errors
 b=ro.Shape.BoundBox
 row={'fichier':str(path.relative_to(ROOT)).replace('\\','/'),'source_objet':'Reference','solide_final':'Resultat','volume_mm3_representation':ro.Shape.Volume,'volume_masse_utilisable':False,'bbox_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],'solides':len(ro.Shape.Solids),'natif':True,'expressions':sum(len(o.ExpressionEngine) for o in rd.Objects),'reouverture_recalcul':'Réussi','forme_valide':ro.Shape.isValid(),'volume_reference_egale_final':abs(rr.Shape.Volume-ro.Shape.Volume)<1e-6,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 RESULTS.append(row);return rd,rr,ro

d,r,s=new('EQ_SouthcoR405','R4-05-40-405-10',
 {'BodyX':21.2,'BodyY':10,'BodyZ':46,'HoleX':11.85,'HoleZLow':10.3,'HolePitch':25.4,'HoleD':4.5,'StrikerZ':23,'MouthR':4,'HandleProjection':24,'HandleStroke':7,'HandleT':3,'HandleY':3.2,'HandleZ':35.7,'HandleH':4})
housing=box(d,'BoitierInterface',('Parametres.BodyX','Parametres.BodyY','Parametres.BodyZ'),('0 mm','0 mm','0 mm'))
# Bouche simplifiée, cercle nominal et dégagement latéral coté : le profil du cliquet est volontairement absent.
mouth_round=cyl(d,'FondBouche','Parametres.MouthR','Parametres.BodyY+2 mm',('Parametres.HoleX','-1 mm','Parametres.StrikerZ'))
mouth_side=box(d,'EntreeBouche',('Parametres.BodyX-Parametres.HoleX+1 mm','Parametres.BodyY+2 mm','2*Parametres.MouthR'),('Parametres.HoleX','-1 mm','Parametres.StrikerZ-Parametres.MouthR'))
base=cut(d,'BoucheInterface',housing,fuse(d,'OutilBouche',[mouth_round,mouth_side]))
holes=[cyl(d,'TrouFixation'+str(i),'Parametres.HoleD/2','Parametres.BodyY+2 mm',('Parametres.HoleX','-1 mm','Parametres.HoleZLow'+('' if i==0 else '+Parametres.HolePitch'))) for i in range(2)]
base=cut(d,'BoitierPerce',base,fuse(d,'OutilsPercage',holes))
# Gâchette au repos : forme externe simplifiée, course publiée consignée, aucun réglage de mouvement fictif.
handle=box(d,'GachetteManuelleSimplifiee',('Parametres.HandleProjection','Parametres.HandleT','Parametres.HandleH'),('Parametres.HoleX','Parametres.HandleY','Parametres.HandleZ'))
out=cut(d,'Resultat',fuse(d,'BoitierEtGachette',[base,handle]),fuse(d,'PercagesTraversantsFinal',holes))
latch,lr,lo=save(d,r,out)

d,r,s=new('EQ_SouthcoGacheR490','R4-90-0521-10',
 {'TotalL':28.2,'HeadT':2.5,'HeadD':10,'BarrelD':6,'ToWasher':18.4,'ThreadD':5,'HexAF':8})
# Axe local +Y ; tête à Y=0, épaulement nominal de rondelle Y=18,4.
head=cyl(d,'TeteEnveloppe','Parametres.HeadD/2','Parametres.HeadT',('0 mm','0 mm','0 mm'))
# Enveloppe Ø10 conservatrice : le catalogue mentionne hex8, sans séparer
# complètement le profil de tête et la rondelle. Ne pas perdre le Ø10 publié.
barrel=cyl(d,'TigeCapture','Parametres.BarrelD/2','Parametres.ToWasher-Parametres.HeadT',('0 mm','Parametres.HeadT','0 mm'))
thread=cyl(d,'FiletageEnveloppeM5','Parametres.ThreadD/2','Parametres.TotalL-Parametres.ToWasher',('0 mm','Parametres.ToWasher','0 mm'))
# Rondelle/O-ring montrés au catalogue mais épaisseurs non cotées : ne pas inventer de solides.
out=fuse(d,'Resultat',[head,barrel,thread])
gd,gr,go=save(d,r,out)

# Interface nominale : gâche centre Z23 et X11,85, cylindre Ø6 dans bouche Ø8.
# Barillet Y2,5..18,4 doit traverser corps Y0..10 ; translation Y−3 place tête hors boîtier.
placed=go.Shape.copy();placed.translate(A.Vector(11.85,-3,23))
overlap=lo.Shape.common(placed).Volume
# Le modèle de gâchette simplifié déborde mais reste loin de l'axe capturé.
assert overlap<1e-6,overlap
sources=[{'fichier':name,'url':url,'taille_octets':(SOURCE/name).stat().st_size,'sha256':hashlib.sha256((SOURCE/name).read_bytes()).hexdigest(),'original_inchange':True} for name,url in SOURCE_URLS.items()]
manifest={'schema_version':1,'date_utc':'2026-10-02','fabricant':'Southco','sources':sources,'licence':'Documents fabricants, droits réservés ; consultation/intégration technique. Pas de droit de redistribution générale inféré.','step_fabricant_archive':False,'plan_cote_fabricant_archive':True,'limite_acces_CAD':'Lien CAD Download annoncé ; WAF/429 et CUA indisponible, pas de contournement. Géométrie native dérivée du plan distincte des sources.'}
(SOURCE/'provenance_latching_Southco.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
bom={'schema_version':1,'date_utc':'2026-10-02','status':'À valider','lignes':[
 {'quantite':1,'fabricant':'Southco','mpn':'R4-05-40-405-10','fichier':RESULTS[0]['fichier'],'source_objet':'Reference','description':'Micro deux stages, bumper EPDM et gâchette manuelle intégrés','masse_kg':None},
 {'quantite':1,'fabricant':'Southco','mpn':'R4-90-0521-10','fichier':RESULTS[1]['fichier'],'source_objet':'Reference','description':'Gâche acier, tige Ø6, filetage M5×0,8','masse_kg':None},
 {'quantite':2,'fabricant':None,'mpn':None,'description':'Vis M4 candidates dans trous Ø4,5, longueur/classe selon support','statut':'À valider','couple_max_fabricant_Nm':4,'source':'J-R4-05-10 ; diamètre nominal M4 déduit du trou, pas MPN fabricant'},
 {'quantite':2,'fabricant':None,'mpn':None,'description':'Retenue M4 et rondelles candidates selon fixation traversante','statut':'À valider','source':'Choix intégration, non prescrit Southco'},
 {'quantite':1,'fabricant':None,'mpn':None,'description':'Support taraudé M5×0,8 ou écrou freiné M5 candidat pour gâche','statut':'À valider','source':'Filetage fabricant ; engagement et visserie non dimensionnés'}],
 'note':'BOM commerciale exacte pour loquet et gâche. Aucune longueur ni référence de visserie n’est publiée dans les sources récupérées ; elles restent explicitement ouvertes. Aucun câble/actionneur séparé nécessaire avec cette gâchette intégrée.'}
BOM.write_text(json.dumps(bom,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
proof={'schema_version':1,'date_utc':'2026-10-02','status':'À valider','realisation_CAO':'Implémenté','recette':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'references':RESULTS,'interface_nominale':{'gache_translation_local_latch_mm':[11.85,-3,23],'axe_gache':'Y','bouche':'Face +X ; insertion −X','collision_mm3':overlap,'portee':'Montage géométrique nominal simplifié, sans fonction de capture interne ni assertion de verrouillage'},'provenance':str((SOURCE/'provenance_latching_Southco.json').relative_to(ROOT)).replace('\\','/'),'bom':str(BOM.relative_to(ROOT)).replace('\\','/'),'limites':[LIMITES,'Aucune masse calculée à partir des volumes : représentation simplifiée, matériaux multiples, ressort et internes absents.','Aucun essai cinématique ni force d’insertion établi ; ne pas déduire butée de fin de contacts du seul dessin.','Enveloppe tête Ø10 conservée ; hexagone AF8 consigné seulement, rondelle/O-ring et filet détaillé absents, dimensions non cotées.'],'controle_actif':'Aucun assemblage actif, document vivant ou manifeste principal modifié par cette recette.'}
PROOF.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'references':RESULTS,'collision_interface_nominale_mm3':overlap},ensure_ascii=False))

