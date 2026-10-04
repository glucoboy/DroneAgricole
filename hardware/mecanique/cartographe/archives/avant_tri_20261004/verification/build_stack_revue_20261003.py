"""Infrastructure FreeCAD : revue synchronisée, aucune source/CAO active modifiée.

Pré-requis : export KiCad courant --user-origin 50x50mm --no-dnp dans
exports/stack_avionique_revue_20261003/CA01_placement_courant.step.
Montage candidat fondé sur le dessin Holybro ; aucun faisceau installé.
"""
from pathlib import Path
import json, hashlib
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'; VER=MEC/'verification'
CARD=ROOT/'hardware/electronique/cartographe/carte_avionique'
OUT=MEC/'exports/stack_avionique_revue_20261003'
NEW=['pieces/fabriquees/CA01_PCB_Revue_20261003.FCStd',
     'sous_assemblages/SA03_CA01_Holybro_Revue_20261003.FCStd',
     'assemblages/Integration_Stack_Revue_20261003.FCStd',
     'pieces/fabriquees/P54_Appui_CA01_Holybro_Stack.FCStd',
     'pieces/fabriquees/P55_EntretoiseBasse_Stack.FCStd',
     'pieces/fabriquees/P56_PlaqueBasse_PercagesStack.FCStd',
     'pieces/commerce/EQ_VisM3x65_Stack.FCStd',
     'pieces/commerce/EQ_RondelleM3_Stack.FCStd',
     'sous_assemblages/SA01_Chassis_Stack_Revue_20261003.FCStd']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p):return str(Path(p).relative_to(ROOT)).replace('\\','/')
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def meta(o,k,v):
    if k not in o.PropertiesList:o.addProperty('App::PropertyString',k)
    setattr(o,k,v)
def link(d,r,name,target,pose=None):
    o=d.addObject('App::Link',name);r.addObject(o);o.LinkedObject=target
    o.LinkTransform=False;o.LinkPlacement=pose or A.Placement();return o
def reference(index,material):
    path=MEC/NEW[index];dd=A.newDocument(path.stem);rr=dd.addObject('App::Part','Reference')
    meta(rr,'Statut','À valider');meta(rr,'Materiau',material)
    ss=dd.addObject('Spreadsheet::Sheet','Parametres');rr.addObject(ss)
    dd.saveAs(str(path));return dd,rr,ss
def value(sheet,name,num,unit='mm'):
    row=len(sheet.getNonEmptyCells())//2+1
    sheet.set('A'+str(row),name);sheet.set('B'+str(row),str(num)+' '+unit);sheet.setAlias('B'+str(row),name)
def tube(index,length,outer,inner,material):
    dd,rr,ss=reference(index,material)
    for name,num in [('Longueur',length),('DiametreExterieur',outer),('Passage',inner)]:value(ss,name,num)
    body=dd.addObject('Part::Cylinder','Corps');body.setExpression('Radius','Parametres.DiametreExterieur/2');body.setExpression('Height','Parametres.Longueur')
    hole=dd.addObject('Part::Cylinder','Passage');hole.setExpression('Radius','Parametres.Passage/2');hole.setExpression('Height','Parametres.Longueur+2 mm');hole.Placement.Base.z=-1
    cut=dd.addObject('Part::Cut','Resultat');cut.Base=body;cut.Tool=hole;rr.addObject(cut)
    body.Visibility=False;hole.Visibility=False
    dd.recompute();dd.save();return rr
before={rel(p):sha(p) for p in MEC.rglob('*.FCStd')
        if 'verification' not in p.parts and str(p.relative_to(MEC)).replace('\\','/') not in NEW}
before.update({rel(p):sha(p) for p in [CARD/'CA01_Avionique.kicad_pcb',CARD/'placement_mecanique.json']})
step=OUT/'CA01_placement_courant.step'
shape=Part.read(str(step));assert shape.isValid()
substrate=max(shape.Solids,key=lambda s:s.Volume)
components=Part.makeCompound([s for s in shape.Solids if not s.isSame(substrate)])
# KiCad10 exporte ici un substrat1,46mm sans les deux cuivres externes70µm.
# La CAO mécanique conserve l'épaisseur totale déclarée1,6mm et porte les
# composants à sa face supérieure. Conversion explicite, jamais cote fabricant.
substrate_h=substrate.BoundBox.ZLength
assert abs(substrate_h-1.46)<1e-6
component_z_correction=1.6-substrate_h
components.Placement.Base.z+=component_z_correction
d=A.openDocument(str(MEC/'pieces/fabriquees/CA01_PCB_Preplacement.FCStd'))
board=d.getObject('PCB');original_volume=board.Shape.Volume
assert sum(o.TypeId=='PartDesign::AdditiveBox' for o in board.Group)==1
assert sum(o.TypeId=='PartDesign::SubtractiveCylinder' for o in board.Group)==8
comp=d.getObject('ComposantsKiCad');comp.Shape=components
comp.SourceFile=str(step);comp.SourceSHA256=sha(step)
card=d.getObject('CarteCA01');card.Label='CA01 — placement PCB courant, montage À valider'
meta(card,'SourcePCB',rel(CARD/'CA01_Avionique.kicad_pcb'))
meta(card,'SourcePCBSHA256',sha(CARD/'CA01_Avionique.kicad_pcb'))
meta(card,'Limites','Révision de revue du placement courant ; PCB paramétrique conservé. Fiches, câbles, cuivre, sous-face/broches RP4TD et fixations hors modèle.')
d.recompute();assert abs(board.Shape.Volume-original_volume)<1e-8
# Le natif historique ne perçait que les quatre fixations et quatre broches radio.
# Ajouter les trous de connecteurs et pads thermiques du PCB courant, sans aplatir.
holes=json.loads((VER/'percages_ca01_stack_20261003.json').read_text(encoding='utf-8'))
assert holes['pcb_sha256']==sha(CARD/'CA01_Avionique.kicad_pcb')
added=[]
for i,h in enumerate(holes['holes']):
    if h['ref'] in ['H1','H2','H3','H4','MOD401']:continue
    assert abs(h['drill_mm'][0]-h['drill_mm'][1])<1e-8,'Perçage oblong non implémenté'
    o=board.newObject('PartDesign::SubtractiveCylinder','PercagePad'+str(i))
    o.Label=h['ref']+' pad '+h['pad']+' — perçage KiCad'
    o.Radius=h['drill_mm'][0]/2;o.Height=1.8
    o.Placement.Base=A.Vector(*h['xy_mm'],-.1)
    added.append(o.Name)
d.recompute()
normalized_volume=substrate.Volume*1.6/substrate_h
print(json.dumps({'volume_natif':board.Shape.Volume,'volume_STEP_normalise':normalized_volume,'perçages_ajoutes':len(added)}),flush=True)
assert abs(board.Shape.Volume-normalized_volume)<1e-4
d.saveAs(str(MEC/NEW[0]))
# Pièces fabriquées candidates : faces d'appui exactes du STEP conservé.
ring=tube(3,2,5.5,3.2,'G10 usiné candidat ; compression et tenue À valider')
column=tube(4,24,6,3.2,'G10 usiné candidat ; rigidité, compression et tenue À valider')
washer=tube(7,.5,7,3.2,'Acier, rondelle nominale M3 ; référence fournisseur À valider')
bd,br,bs=reference(6,'Acier, vis CHC nominale M3×65 ; classe/fournisseur/serrage À valider')
for name,num in [('LongueurSousTete',65),('TeteDiametre',5.5),('TeteHauteur',3),('DiametreFilet',3)]:value(bs,name,num)
shaft=bd.addObject('Part::Cylinder','Tige');shaft.setExpression('Radius','Parametres.DiametreFilet/2');shaft.setExpression('Height','Parametres.LongueurSousTete')
head=bd.addObject('Part::Cylinder','Tete');head.setExpression('Radius','Parametres.TeteDiametre/2');head.setExpression('Height','Parametres.TeteHauteur');head.setExpression('Placement.Base.z','-Parametres.TeteHauteur')
union=bd.addObject('Part::Fuse','CorpsVis');union.Base=shaft;union.Tool=head
hexagon=bd.addObject('Part::Prism','Empreinte');hexagon.Polygon=6;hexagon.Circumradius=2.5/(3**.5);hexagon.Height=1.5;hexagon.Placement.Base.z=-3.1
final=bd.addObject('Part::Cut','Resultat');final.Base=union;final.Tool=hexagon;br.addObject(final)
for o in [shaft,head,union,hexagon]:o.Visibility=False
meta(br,'Filetage','M3×0,5 nominal, cylindre enveloppeØ3 sans hélice ; recouvrement géométrique dans taraudage OEM intentionnel')
bd.recompute();bd.save()
bolt=br
old_chassis=A.openDocument(str(MEC/'sous_assemblages/SA01_Chassis_Rehausse20.FCStd'))
plate_occurrence=old_chassis.getObject('Part__Feature312')
original_plate=plate_occurrence.LinkedObject
pd,pr,ps=reference(5,'Plaque carbone OEM2mm dérivée ; reperçage quatre trousØ3 versØ3,2 candidat')
source=link(pd,pr,'SourcePlaqueOEM',original_plate,A.Placement(plate_occurrence.LinkPlacement))
pr.removeObject(source);source.Visibility=False
value(ps,'TrouDiametre',3.2)
tools=[]
for x in [-60,60]:
    for y in [-37,37]:
        o=pd.addObject('Part::Cylinder','RepriseM3');o.setExpression('Radius','Parametres.TrouDiametre/2');o.Height=4;o.Placement.Base=A.Vector(x,y,-93);tools.append(o)
u=pd.addObject('Part::MultiFuse','OutilsPercage');u.Shapes=tools
cut=pd.addObject('Part::Cut','Resultat');cut.Base=source;cut.Tool=u;pr.addObject(cut)
for o in tools+[u]:o.Visibility=False
pd.recompute()
assert abs(cut.Shape.BoundBox.ZMin+92)<1e-6 and abs(cut.Shape.BoundBox.ZMax+90)<1e-6
assert abs(cut.Shape.BoundBox.XMin+64)<1e-6 and abs(cut.Shape.BoundBox.YMin+60)<1e-6
pd.save()
old_chassis.getObject('Part__Feature312').LinkedObject=pr
old_chassis.getObject('Part__Feature312').LinkTransform=False
old_chassis.getObject('Part__Feature312').LinkPlacement=A.Placement()
old_chassis.recompute();old_chassis.saveAs(str(MEC/NEW[8]))
holy_doc=A.openDocument(str(MEC/'pieces/commerce/EQ_Holybro_Pixhawk_Jetson_Baseboard_candidat.FCStd'))
holy=next(o for o in holy_doc.Objects if hasattr(o,'Shape') and not o.Shape.isNull())
s=A.newDocument('SA03_CA01_Holybro_Revue_20261003')
s.saveAs(str(MEC/NEW[1]))
root=s.addObject('App::Part','StackRevue')
root.Label='Stack synchronisée — montage M3 candidat'
meta(root,'Statut','Implémenté');meta(root,'Qualification','À valider')
meta(root,'Limites','Plan Holybro :4M3, appuis8mm. Fixation commune P17/plaque/stack par vis65 ; charge, compression/fluage P17, serrage et thermique À valider. Déposer bloccapteurs SA05A pour accès outil. DimensionsSTEPnominales, aucun faisceau final.')
meta(root,'SourcePlan','sources_fabricants/Holybro_PixhawkJetson_Orin_Dimensions.jpg')
p=s.addObject('App::FeaturePython','ParametresStack')
p.addProperty('App::PropertyLength','EcartPCB').EcartPCB=10.0554
p.addProperty('App::PropertyLength','SousFaceHolybro').SousFaceHolybro=.03
link(s,root,'Holybro',holy)
c=link(s,root,'CA01',card,A.Placement(A.Vector(0,0,-10.0254),A.Rotation(A.Vector(1,0,0),180)))
c.setExpression('LinkPlacement.Base.z','ParametresStack.SousFaceHolybro-ParametresStack.EcartPCB')
for i,(x,y) in enumerate([(x,y) for x in [3,123] for y in [3,77]],1):
    for name,target,z in [('AppuiHaut',ring,-10.0254),('EntretoiseBasse',column,-35.6254),('Rondelle',washer,-67.2994),('VisM3x65',bolt,-67.2994)]:
        link(s,root,name+'_'+str(i),target,A.Placement(A.Vector(x,y,z),A.Rotation()))
s.recompute();s.saveAs(str(MEC/NEW[1]))
t=A.newDocument('Integration_Stack_Revue_20261003')
t.saveAs(str(MEC/NEW[2]))
tr=t.addObject('App::Part','IntegrationRevue');tr.Label='Étude locale de stack montée — sans faisceau'
meta(tr,'Statut','À valider')
meta(tr,'Limites','Comparaison géométrique statique. Ancien faisceau volontairement non repris : ses routes ne sont pas recalées sur cette étude. Pas configuration drone finale.')
pp=t.addObject('App::FeaturePython','ParametresIntegration')
pp.addProperty('App::PropertyDistance','PoseHolybroZ').PoseHolybroZ=-54.3746
pp.addProperty('App::PropertyString','Nature').Nature='Pose dérivée des appuisL24/L2 et piedOEMSTEP ; pas cote de montage approuvée'
for name in ['SA01_Chassis_Rehausse20','SA02A_Dock20Ah','SA05_Capteurs_Isoles','SA07_Distribution_Systeme_Candidat']:
    dd=old_chassis if name=='SA01_Chassis_Rehausse20' else A.openDocument(str(MEC/'sous_assemblages'/(name+'.FCStd')))
    rr=dd.getObject('Reference') or dd.getObject('Ensemble')
    assert rr is not None,name
    link(t,tr,name,rr)
stack=link(t,tr,'Stack_Holybro_CA01',root,A.Placement(A.Vector(-63,-40,-54.3746),A.Rotation()))
stack.setExpression('LinkPlacement.Base.z','ParametresIntegration.PoseHolybroZ')
t.recompute();t.saveAs(str(MEC/NEW[2]))
assert abs(pp.PoseHolybroZ.Value+54.3746)<1e-8
assert abs(stack.LinkPlacement.Base.z+54.3746)<1e-8
occ=[]
for dd in [s,t,old_chassis,pd]:
    for o in dd.Objects:
        if o.TypeId=='App::Link':occ.append({'assemblage':rel(dd.FileName),'occurrence':o.Name,
            'source_fichier':rel(o.LinkedObject.Document.FileName),'source_objet':o.LinkedObject.Name,
            'LinkTransform':o.LinkTransform,'matrice_placement':list(o.LinkPlacement.toMatrix().A)})
assert all(sha(ROOT/f)==h for f,h in before.items()),'Source modifiée'
write(VER/'construction_stack_revue_20261003.json',{'date':'2026-10-03','statut':'À valider',
    'script_sha256':sha(__file__),'version_FreeCAD':A.Version(),'step':rel(step),'step_sha256':sha(step),
    'pcb_sha256':sha(CARD/'CA01_Avionique.kicad_pcb'),'sources_preservees_sha256':before,
    'nouveaux_fichiers':[{'fichier':rel(MEC/f),'sha256':sha(MEC/f)} for f in NEW],
    'occurrences':occ,'composants_solides':len(components.Solids),'PCB_arbre_natif_preserve':True,
    'perçages_pads_ajoutes':added,'substrat_STEP_difference_volume_normalise_mm3':abs(board.Shape.Volume-normalized_volume),
    'conversion_STEP':{'substrat_exporte_mm':substrate_h,'epaisseur_totale_PCB_mm':1.6,
        'translation_composants_Z_mm':component_z_correction,
        'raison':'STEP sans cuivre extérieur : restitution face mécanique à épaisseur nominale totale ; stack fabricant À valider'},
    'sources_plans':[{'fichier':rel(MEC/'sources_fabricants'/f),'sha256':sha(MEC/'sources_fabricants'/f)} for f in ['Holybro_PixhawkJetson_Dimensions.jpg','Holybro_PixhawkJetson_Orin_Dimensions.jpg']],
    'montage':{'axes_globaux_mm':[[x,y] for x in [-60,60] for y in [-37,37]],
        'entretoise_basse_longueur_mm':24,'appui_haut_longueur_mm':2,
        'vis_M3_longueur_mm':65,'rondelle_epaisseur_mm':.5,'engagement_nominal_mm':5.726,
        'pose_Holybro_Z_mm':-54.3746,'marge_fond_taraudage_STEP_mm':1.274,
        'fixation_commune':'P17/plaque basse/P55/CA01/P54/pied OEM ; pas de deuxième fixation M3 P17 présente dans CAO initiale',
        'acces_outil':'Déposer bloccapteursSA05A pour montage/maintenance ; accès obstrué avec P16 montée',
        'tenue_limites':'Compression/fluage P17 et G10, charge carte/isolateurs, effort vis et couple non qualifiés',
        'engagement_limite':'Cote de forme du STEP, pas profondeur filetée garantie ou validation résistance',
        'plaquebasse_reprise_percages_mm':3.2,'quincaillerie_ajoutee_occurrences':16},
    'pose_comparaison_electronique_z_mm':[-65,-54.3746],'configuration_active_modifiee':False,
    'chaine_appuis_CAO_implantee':True,'fixations_qualifiees':False,'faisceau_recale':False,'fabrication_ready':False})
print(json.dumps({'sources_preservees':len(before),'nouveaux_natifs':len(NEW),'composants_solides':len(components.Solids)}))
