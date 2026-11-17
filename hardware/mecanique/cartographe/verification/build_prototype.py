"""Infrastructure CAO FreeCAD : reconstruction du prototype depuis ses références.

Les géométries commerciales simplifiées sont des enveloppes de définition,
pas des plans fabricant. Aucun ancien document n'est modifié par cette recette.
"""
from pathlib import Path
import json, math, hashlib, sys, time
from datetime import datetime, timezone
import FreeCAD as A
import Part, Sketcher
from etage_batterie_helpers import G, save_native, color

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
VER = MEC / 'verification'
if (MEC/'manifest.json').exists() and json.loads((MEC/'manifest.json').read_text('utf-8')) \
        .get('prototype_cartographe', {}).get('orch_cao_masse_1'):
    raise RuntimeError('Recette initiale refusée après ORCH-CAO-MASSE-1 : elle rétablirait des enveloppes et effacerait les définitions courantes. Utiliser les recettes de pièces du lot et orch_integrate_cao.py.')
OUT = MEC / 'exports/prototype'
OUT.mkdir(parents=True, exist_ok=True)
RECORDS, OCCURRENCES, DOCS, SOURCES = [], [], [], {}
GREY, CARBON, BLUE, GREEN, ORANGE = (.70,.73,.76), (.12,.14,.16), (.16,.35,.65), (.08,.42,.23), (.94,.47,.09)
ENERGY_PLATE_TOP = 39.0

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rel(path): return Path(path).relative_to(MEC).as_posix()
def dump(path, value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def meta(obj, name, value):
    if name not in obj.PropertiesList: obj.addProperty('App::PropertyString',name,'Definition')
    setattr(obj,name,str(value))
def bbox(shape):
    b=shape.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def doc(name,folder,label):
    d=A.newDocument(name); r=d.addObject('App::Part','Ensemble')
    r.Label=label
    meta(r,'Statut','Implémenté'); meta(r,'Qualification','À valider')
    meta(r,'Limites','Définition nominale de montage ; fabrication, tolérances et tenue physique non qualifiées.')
    path=MEC/folder/(name+'.FCStd'); d.saveAs(str(path)); DOCS.append(d)
    return d,r
def params(d,r,values):
    s=d.addObject('Spreadsheet::Sheet','Parametres');r.addObject(s)
    for row,(key,val) in enumerate(values.items(),1):
        s.set('A'+str(row),key);s.set('B'+str(row),str(val)+' mm');s.setAlias('B'+str(row),key)
    s.Visibility=False
    return s
def box(d,name,size,pos=(0,0,0)):
    o=d.addObject('Part::Box',name); o.Length,o.Width,o.Height=size
    o.Placement.Base=A.Vector(*pos); return o
def cylinder(d,name,radius,height,pos=(0,0,0)):
    o=d.addObject('Part::Cylinder',name);o.Radius=radius;o.Height=height;o.Placement.Base=A.Vector(*pos);return o
def boolean(d,r,base,tools,name='Resultat'):
    current=base
    for i,t in enumerate(tools):
        c=d.addObject('Part::Cut',name+str(i));c.Base=current;c.Tool=t
        current.Visibility=False;t.Visibility=False;current=c
    r.addObject(current); return current
def save(d,r,ids=(),kind='fabriquee',note=''):
    d.recompute();assert not r.Shape.isNull(), d.Name
    # Les composés fabricant contiennent des milliers de petits solides.
    # Leur contrôle est séparé de celui des pièces fabriquées dans la preuve.
    valid=None if kind in ('sous_assemblage','assemblage_final','commerce_fabricant_derive') else r.Shape.isValid()
    if valid is False:
        failures=[{'objet':o.Name,'type':o.TypeId} for o in r.Group if hasattr(o,'Shape') and not o.Shape.isNull() and not o.Shape.isValid()]
        print(json.dumps({'geometrie_invalide':d.Name,'enfants':failures}),flush=True)
        if kind not in ('sous_assemblage','assemblage_final','commerce_fabricant_derive'):
            raise ValueError('Géométrie nouvellement construite invalide : '+d.Name)
    save_native(d)
    record={'reference':d.Name,'fichier':rel(d.FileName),'objet':'Ensemble','bom_ids':list(ids),
            'type':kind,'statut':'Implémenté','qualification':'À valider','limites':note,
            'sha256':sha(d.FileName),'bbox_mm':bbox(r.Shape),'compose_valide':valid}
    RECORDS.append(record);return r
def source(file,obj=None):
    path=MEC/file
    d=next((x for x in A.listDocuments().values() if x.FileName and Path(x.FileName).resolve()==path.resolve()),None)
    if d is None:d=A.openDocument(str(path))
    SOURCES[file]=sha(path)
    if obj:return d.getObject(obj)
    return next(o for o in d.RootObjects if hasattr(o,'Shape') and not o.Shape.isNull())
def link(d,r,name,target,pose=None,ids=(),note=''):
    o=d.addObject('App::Link',name);r.addObject(o);o.LinkedObject=target;o.LinkTransform=False
    o.LinkPlacement=pose if pose is not None else target.getGlobalPlacement()
    meta(o,'BOM_ID',','.join(ids));meta(o,'Limites',note)
    OCCURRENCES.append({'parent':rel(d.FileName),'occurrence':o.Name,'source':rel(target.Document.FileName),
                        'objet_source':target.Name,'bom_ids':list(ids),'matrice':list(o.LinkPlacement.toMatrix().A)})
    return o
def at(d,r,name,target,xyz,ids=(),rot=None):
    """Place le centre XY et le bas de l'enveloppe source aux coordonnées données."""
    rot=rot or A.Rotation(); s=target.Shape.copy()
    s.Placement=A.Placement(A.Vector(),rot).multiply(s.Placement)
    b=s.BoundBox
    delta=A.Placement(A.Vector(xyz[0]-(b.XMin+b.XMax)/2,xyz[1]-(b.YMin+b.YMax)/2,xyz[2]-b.ZMin),rot)
    return link(d,r,name,target,delta.multiply(target.getGlobalPlacement()),ids)
def plate(name,label,size,holes=(),slots=(),ids=(),tint=GREY,note=''):
    d,r=doc(name,'pieces/fabriquees',label);p=params(d,r,dict(Longueur=size[0],Largeur=size[1],Epaisseur=size[2]))
    b=box(d,'Plaque',size,(-size[0]/2,-size[1]/2,0))
    for prop,expr in [('Length','Parametres.Longueur'),('Width','Parametres.Largeur'),('Height','Parametres.Epaisseur'),('Placement.Base.x','-Parametres.Longueur/2'),('Placement.Base.y','-Parametres.Largeur/2')]:b.setExpression(prop,expr)
    cuts=[cylinder(d,'Percage',h[2]/2,size[2]+2,(h[0],h[1],-1)) for h in holes]
    cuts += [box(d,'Lumiere',(s[2],s[3],size[2]+2),(s[0]-s[2]/2,s[1]-s[3]/2,-1)) for s in slots]
    result=boolean(d,r,b,cuts);color(result,tint);meta(r,'Definition',note)
    return save(d,r,ids,note=note)
def envelope(name,label,size,ids=(),tint=GREY,note=''):
    d,r=doc(name,'pieces/commerce',label);params(d,r,dict(Longueur=size[0],Largeur=size[1],Hauteur=size[2]))
    b=box(d,'Enveloppe',size,(-size[0]/2,-size[1]/2,0));r.addObject(b)
    for prop,expr in [('Length','Parametres.Longueur'),('Width','Parametres.Largeur'),('Height','Parametres.Hauteur'),('Placement.Base.x','-Parametres.Longueur/2'),('Placement.Base.y','-Parametres.Largeur/2')]:b.setExpression(prop,expr)
    color(b,tint);meta(r,'NatureModele','Enveloppe simplifiée');meta(r,'SourceDimensions',note)
    return save(d,r,ids,'commerce_enveloppe',note)
def ring(name,length,outer,inner,ids=(),tint=GREY,kind='pieces/commerce'):
    d,r=doc(name,kind,name);params(d,r,dict(Longueur=length,Diametre=outer,Passage=inner))
    c=cylinder(d,'Corps',outer/2,length);c.setExpression('Radius','Parametres.Diametre/2');c.setExpression('Height','Parametres.Longueur')
    cut=cylinder(d,'Passage',inner/2,length+2,(0,0,-1));cut.setExpression('Radius','Parametres.Passage/2');cut.setExpression('Height','Parametres.Longueur+2 mm')
    result=boolean(d,r,c,[cut]);color(result,tint);return save(d,r,ids)

# La suite de construction est volontairement explicite : une configuration,
# aucun mécanisme permettant de rétablir automatiquement le dock historique.

def compound_piece(name,label,components,ids=(),folder='pieces/fabriquees',tint=GREY,note=''):
    d,r=doc(name,folder,label)
    for i,(typ,dims,xyz) in enumerate(components):
        o=box(d,'Volume'+str(i),dims,xyz) if typ=='box' else cylinder(d,'Volume'+str(i),dims[0],dims[1],xyz)
        r.addObject(o);color(o,tint)
    meta(r,'Definition',note)
    return save(d,r,ids,note=note)

def bolt(name,diameter,length,countersunk=False):
    d,r=doc(name,'pieces/commerce',name+' — filetage simplifié')
    sh=cylinder(d,'Tige',diameter/2,length,(0,0,-length));r.addObject(sh);color(sh,GREY)
    if countersunk:
        h=d.addObject('Part::Cone','Tete');h.Radius1=diameter/2;h.Radius2=diameter;h.Height=diameter*.6;h.Placement.Base.z=-diameter*.6
    else:h=cylinder(d,'Tete',diameter*.92,diameter)
    r.addObject(h);color(h,GREY)
    meta(r,'Limites','Enveloppe de vis ; filet et empreinte non détaillés ; classe, couple et lot À valider.')
    return save(d,r,kind='commerce_enveloppe')

def hexnut(name,diameter,across,height):
    d,r=doc(name,'pieces/commerce',name+' — filetage simplifié')
    prism=d.addObject('Part::Prism','Hexagone');prism.Polygon=6;prism.Circumradius=across/math.sqrt(3);prism.Height=height
    bore=cylinder(d,'Passage',diameter/2,height+2,(0,0,-1))
    result=boolean(d,r,prism,[bore]);color(result,GREY)
    return save(d,r,kind='commerce_enveloppe')

def build():
    # Les natifs sont écrits en place : une interruption ne doit pas laisser
    # l'ancienne preuve annoncée comme finalisée pour des fichiers partiels.
    progress_path=VER/'construction_prototype.json'
    previous=json.loads(progress_path.read_text('utf-8')) if progress_path.exists() else {}
    previous.update(finalisation_correcte=False,construction_en_cours_utc=datetime.now(timezone.utc).isoformat())
    previous.pop('erreur_construction',None)
    dump(progress_path,previous)
    # OEM : repartir du fabricant, retirer équipements étrangers et accessoires associés.
    chassis=source('pieces/commerce/EQ_Chassis_X650.FCStd','X650_FRAME_2024CHU_ASM_73_1_ASM_ASM')
    reject_names={'INTEL_D455_5_1_1_ASM','PCBA_PM06_ASM_3_1_ASM_1_ASM','RTK_ZHIJIA_M8P_ASM_10_1_ASM_1_ASM',
                  'ZHIJIA_30DU_12D_ASM_35_1_ASM_1_ASM','ZHIJIA_30DU_12D_ASM_35_1_ASM_1_ASM001'}
    reject_names.update('HANGER_ZHU_ASM_15_1_ASM_1_ASM'+s for s in ['', '001','002','003'])
    reject_names.update('HANGER_ASM_14_1_ASM_1_ASM'+s for s in ['', '001','002','003'])
    reject_nums=[48,49,74,75,108]+list(range(114,120))+list(range(122,146))+list(range(173,181))
    reject_names.update('Part__Feature%03d'%i for i in reject_nums)
    d1,r1=doc('SA01_Prototype_Structure','sous_assemblages','01 — X650 OEM et propulsion')
    oem90=ring('EQ_X650_Colonne90_Prototype',90,5,2.5,['MEC-OEM-FIXATIONS'])
    retained=[]
    for o in chassis.Group:
        if o.Name in reject_names or not hasattr(o,'Shape') or o.Shape.isNull():continue
        if o.Name in ['Part__Feature%03d'%i for i in range(80,84)]:
            shape=o.Shape.copy();shape.Placement=o.getGlobalPlacement().multiply(o.Placement.inverse()).multiply(shape.Placement)
            b=shape.BoundBox
            at(d1,r1,'OEM_'+o.Name,oem90,((b.XMin+b.XMax)/2,(b.YMin+b.YMax)/2,-90),['MEC-OEM-FIXATIONS'])
        else:link(d1,r1,'OEM_'+o.Name,o,o.getGlobalPlacement(),['MEC-X650-KIT'])
        retained.append(o.Name)
    meta(r1,'Inclusions','Bras, moteurs MN4014 et LED inclus dans les groupes fabricant. Pas de second moteur ajouté.')
    meta(r1,'Retraits','Intel D455, PM06/ancienne distribution, mât RTK, supports SMA et rails de charge utile avec leurs brides/plateau déporté exclus. Plateaux centraux, train et colonnes porteurs conservés.')
    # Hélices : enveloppe native paramétrique, aucun profil aérodynamique certifié.
    props=[]
    for sense in ['CW','CCW']:
        dp,rp=doc('EQ_Gemfan1555_'+sense,'pieces/commerce','Gemfan 1555 '+sense+' — enveloppe')
        hub=cylinder(dp,'Moyeu',10,6)
        hubcut=boolean(dp,rp,hub,[cylinder(dp,'Alesage',2.1,8,(0,0,-1))],'MoyeuPerce');color(hubcut,CARBON)
        for side in [-1,1]:
            sketches=[]
            for x,chord,thick,pitch in [(9,9,2.3,20),(45,17,2,17),(130,13,1.7,10),(196.85,1,0.5,5)]:
                sk=dp.addObject('Sketcher::SketchObject','Profil');sk.addGeometry(Part.Ellipse(A.Vector(0,0,0),chord,thick),False)
                rot=A.Rotation(A.Vector(1,0,0),pitch*(1 if sense=='CW' else -1)).multiply(A.Rotation(A.Vector(1,1,1),120))
                if side<0:rot=A.Rotation(A.Vector(0,0,1),180).multiply(rot)
                sk.Placement=A.Placement(A.Vector(side*x,0,3),rot);sk.Visibility=False;sketches.append(sk)
            loft=dp.addObject('Part::Loft','Pale');loft.Sections=sketches;loft.Solid=True;loft.Ruled=True;rp.addObject(loft);color(loft,CARBON)
        meta(rp,'Limites','Diamètre nominal 15 pouces =393,7 mm. Profil simplifié pour implantation ; ne pas fabriquer cette hélice.')
        props.append(save(dp,rp,['MEC-HELICE-'+sense],'commerce_enveloppe','Profil et fixation OEM à vérifier ; uniquement encombrement.'))
    esc=envelope('EQ_Tekko32_45A_Prototype','Tekko32 45 A — enveloppe candidate',(48,25,10),['MEC-ESC'],GREEN,'Dimensions de réservation 48×25×10 ; lot OEM À valider.')
    motors=[(-229.906638,-229.906638),(229.906638,229.906638),(-229.906638,229.906638),(229.906638,-229.906638)]
    for i,(x,y) in enumerate(motors):
        link(d1,r1,'Helice_'+str(i+1),props[0 if i<2 else 1],A.Placement(A.Vector(x,y,65.5),A.Rotation()),['MEC-HELICE-CW' if i<2 else 'MEC-HELICE-CCW'])
        at(d1,r1,'ESC_'+str(i+1),esc,(x*.66,y*.66,27.5),['MEC-ESC'],A.Rotation(A.Vector(0,0,1),45 if x*y>0 else -45))
    save(d1,r1,['MEC-OEM-PLATEAUX','MEC-OEM-BRAS','MEC-OEM-TRAIN','MEC-OEM-COLONNES','MEC-OEM-FIXATIONS','MEC-MOTEUR','MEC-ESC','KIT-LED'],'sous_assemblage')
    print('Structure enregistrée',flush=True)

    # Batterie sanglée sur semelle ; le BMS et le fusible restent côté batterie.
    holes=[(x,y,3.2) for x in [-60,60] for y in [-37,37]]+[(x,y,3.2) for x in [-105,105] for y in [-29,29]]+[(x,y,3.2) for x in [-80,80] for y in [-43,43]]+[(x,y,3.2) for x,y in [(-88,43),(-96,43),(88,-43),(96,-43)]]
    batplate=plate('P60_Semelle_Batterie_Prototype','Semelle batterie G10',(220,96,3),holes,
        [(x,y,22,4) for x in [-60,50] for y in [-43,43]],['MEC-BATTERIE-SUPPORT'],note='G10 3 mm ; appuis et ancrages partagés avec P17. Sangle droite X50 ; dégagement M8 conditionné à un engagement candidat de 6 mm, aucune fabrication libérée.')
    bd=batplate.Document
    # FreeCAD peut ranger les étapes intermédiaires dans le Part actif.
    # Reprendre le dernier résultat, qui contient tous les passages et lumières.
    base=[o for o in bd.Objects if o.Name.startswith('Resultat') and o.TypeId=='Part::Cut'][-1]
    tools=[]
    for x,y in [(x,y) for x in [-60,60] for y in [-37,37]]:
        c=bd.addObject('Part::Cone','Fraisure');c.Radius1=1.6;c.Radius2=3.1;c.Height=1.8;c.Placement.Base=A.Vector(x,y,1.2);tools.append(c)
    tools.append(box(bd,'DegagementM8Coude',(12,31,5),(68.2,2.1,-1)))
    tools.append(box(bd,'CanalM8Transition',(8.8,7.9,5),(68.6,32.1,-1)))
    tools.append(box(bd,'CanalM8Sortie',(8,9.1,5),(68.6,40,-1)))
    batplate.removeObject(base);final=boolean(bd,batplate,base,tools,'FraisureResultat');color(final,GREY);save_native(bd)
    stop=compound_piece('P61_Butee_Batterie_Prototype','Butée batterie POM',[
        ('box',(10,80,2),(-5,-40,0)),('box',(3,80,8),(-6.5,-40,2))],['MEC-BATTERIE-SUPPORT'],tint=BLUE,note='Butée courte hors softpack, face intérieure à98,5mm du centre ; deux fixations M3 par butée, finition arêtes rayon2mm à réaliser et contrôler.')
    stopdoc=stop.Document;raw=stopdoc.addObject('Part::MultiFuse','BrutUni');raw.Shapes=[o for o in stop.Group if hasattr(o,'Shape')]
    for o in list(stop.Group):stop.removeObject(o);o.Visibility=False
    raw.Visibility=False
    stopfinal=boolean(stopdoc,stop,raw,[cylinder(stopdoc,'Fixation',1.6,4,(0,y,-1)) for y in [-29,29]])
    color(stopfinal,BLUE);save_native(stopdoc)
    pads=[]
    for side,offset in [('Gauche',-8),('Droit',-2)]:
        name='EQ_Pad_Batterie_Prototype' if side=='Gauche' else 'EQ_Pad_Droit_Batterie_Prototype'
        dp,rp=doc(name,'pieces/commerce','Pad batterie adapté '+side.lower()+' — réservation')
        pb=box(dp,'PadBrut',(70,65,2),(-35,-32.5,0))
        cuts=[box(dp,'RainureSangle',(20,67,1.01),(offset-10,-33.5,-.01))]
        if side=='Droit':
            cuts.append(box(dp,'PassageM8Ouvert',(12,32,4),(16.2,2.1,-1)))
        result=boolean(dp,rp,pb,cuts,'PadAdapte');color(result,(.16,.17,.18))
        meta(rp,'Limites','Matière et compression à confirmer ; épaisseur 2 mm, rainure inférieure 1 mm pour sangle. Adaptation candidate, pas une modification du softpack.')
        pads.append(save(dp,rp,['MEC-BATTERIE-PADS'],'commerce_enveloppe',
            'Pad à adapter ou fabriquer selon matériau réceptionné ; rainure sous sangle et dégagement M8 droit ouverts. Tenue, pression et tolérances À valider.'))
    # Une sangle fermée est dessinée avec primitives natives, pas une plaque pleine traversant le pack.
    strap=compound_piece('EQ_Sangle_Batterie_Prototype','Sangle OEM20×400 — position fermée',[
        ('box',(20,82,1),(-10,-41,0)),('box',(20,1,61),(-10,-41,0)),('box',(20,1,61),(-10,40,0)),('box',(20,82,1),(-10,-41,60))],
        ['MEC-BATTERIE-SANGLES'],folder='pieces/commerce',tint=(.10,.10,.10),note='400 mm utiles et recouvrement ≥70 mm à réception ; position nominale enveloppe.')
    shelf=plate('P62_Plateau_BMS_Prototype','Plateforme BMS G10',(170,96,2),
        [(x,y,3.2) for x in [-80,80] for y in [-43,43]],
        slots=[(x,43,6,2) for x in [-23,-15,15,23]],
        ids=['MEC-SUPPORTS-ENERGIE','ELEC-PASSEFILS'],
        note='BMS placé au-dessus pack ; largeur96 pour dégager les colonnes OEM. Quatre colonnes hors sangles et softpack ; quatre lumières de retenue NTC au bord arrière. Arêtes à adoucir, serrage et tenue À valider.')
    meta(shelf,'RetenuesNTC',json.dumps({'stations':[
        {'id':'NTC'+str(i)+'_'+str(x),'cables':['NTC'+str(i)],
         'point_mm':[sign*x,49.1,1],'support':'Chant arrière P62',
         'lumiere_centre_mm':[sign*x,43,1],'lumiere_mm':[6,2],
         'repere':'local','largeur_collier_mm':4.6,'jeu_nominal_mm':.2}
        for i,sign in [(1,-1),(2,1)] for x in [23,15]],
        'colliers_cables':4,'qualification':'À valider',
        'limites':['Ligament de bord nominal4 mm ; résistance et pression de serrage à valider.',
                   'Ébavurer et adoucir les deux faces des lumières et le chant ; ne pas pincer les sondes.']},ensure_ascii=False))
    save_native(shelf.Document)
    column=ring('P63_Colonne_BMS_Prototype',63,6,3.2,['MEC-SUPPORTS-ENERGIE'],kind='pieces/fabriquees')
    d2,r2=doc('SA02_Prototype_Batterie','sous_assemblages','02 — Batterie sanglée, BMS et protection')
    at(d2,r2,'Semelle',batplate,(0,0,-90),['MEC-BATTERIE-SUPPORT'])
    for i,x in enumerate([-105,105]):link(d2,r2,'Butee'+str(i),stop,A.Placement(A.Vector(x,0,-87),A.Rotation(A.Vector(0,0,1),180 if x<0 else 0)),['MEC-BATTERIE-SUPPORT'])
    for i,x in enumerate([-52,52]):at(d2,r2,'Pad'+str(i),pads[i],(x,0,-87),['MEC-BATTERIE-PADS'])
    battery=source('pieces/commerce/EQ_Tattu20Ah6S_Dock.FCStd','Reference')
    at(d2,r2,'Pack6S20Ah',battery,(0,0,-85),['ELEC-BAT'])
    for i,x in enumerate([-60,50]):at(d2,r2,'Sangle'+str(i),strap,(x,0,-87),['MEC-BATTERIE-SANGLES'])
    # Colonnes au-delà des faces Y du pack : entraxe90, plateau élargi en conséquence.
    at(d2,r2,'PlateauBMS',shelf,(0,0,-24),['MEC-SUPPORTS-ENERGIE'])
    for i,(x,y) in enumerate([(x,y) for x in [-80,80] for y in [-43,43]]):at(d2,r2,'ColonneBMS'+str(i),column,(x,y,-87),['MEC-SUPPORTS-ENERGIE'])
    bms=source('pieces/commerce/EQ_JBD_SP22S003_BMS.FCStd','Reference');at(d2,r2,'BMS',bms,(0,0,-22),['ELEC-BMS'])
    qs8=envelope('EQ_QS8S_B9310_Prototype','QS8-S B9310 — paire accouplée',(42,24,15),['ELEC-CONNECTEUR-MANUEL'],ORANGE,'Réservation de connecteur 42×24×15, dimensions exactes du lot à contrôler.')
    at(d2,r2,'QS8_manuel',qs8,(113,-12,-59),['ELEC-CONNECTEUR-MANUEL'],A.Rotation(A.Vector(0,0,1),-90))
    from prototype_guides import build_qs8_cradle
    build_qs8_cradle(sys.modules[__name__],d2,r2)
    fuse=envelope('EQ_MIDI_Prototype','MIDI80 A et porte-fusible — candidat',(55,30,24),['ELEC-PROTECTION-AMONT'],(.22,.22,.24),'Enveloppe de réservation 55×30×24 ; calage et calibre à vérifier sur fiche/lot, aucune sélectivité prouvée.')
    at(d2,r2,'Protection_amont',fuse,(45,-71,-52),['ELEC-PROTECTION-AMONT'])
    ntc=compound_piece('EQ_NTC_JBD_Prototype','Sonde NTC JBD — enveloppe',[('cyl',(2,8),(0,0,0))],['ELEC-NTC'],folder='pieces/commerce',tint=(.2,.2,.2))
    for i,x in enumerate([-30,30]):at(d2,r2,'NTC'+str(i),ntc,(x,40,-42),['ELEC-NTC'])
    washer=ring('EQ_ISO7089_M3_Prototype',.5,7,3.2)
    nut=hexnut('EQ_ISO10511_M3_Prototype',3,5.5,4)
    bscrew=bolt('EQ_ISO4762_M3x12_Prototype',3,12)
    bscrew16=bolt('EQ_ISO4762_M3x16_Prototype',3,16)
    for i,(x,y) in enumerate([(x,y) for x in [-105,105] for y in [-29,29]]):
        at(d2,r2,'RondelleButeeH'+str(i),washer,(x,y,-82 if x>0 else -85),['MEC-BATTERIE-FIXATIONS'])
        at(d2,r2,'RondelleButeeB'+str(i),washer,(x,y,-90.5),['MEC-BATTERIE-FIXATIONS'])
        at(d2,r2,'EcrouButee'+str(i),nut,(x,y,-94.5),['MEC-BATTERIE-FIXATIONS'])
        link(d2,r2,'VisButee'+str(i),bscrew16 if x>0 else bscrew,A.Placement(A.Vector(x,y,-81.5 if x>0 else -84.5),A.Rotation()),['MEC-BATTERIE-FIXATIONS'])
    bmsbolt=bolt('EQ_ISO4762_M3x75_Prototype',3,75)
    for i,(x,y) in enumerate([(x,y) for x in [-80,80] for y in [-43,43]]):
        link(d2,r2,'VisColonneBMS'+str(i),bmsbolt,A.Placement(A.Vector(x,y,-21.5),A.Rotation()),['MEC-SUPPORTS-ENERGIE'])
        for suffix,z in [('H',-22),('B',-90.5)]:at(d2,r2,'RondelleColonneBMS'+suffix+str(i),washer,(x,y,z),['MEC-SUPPORTS-ENERGIE'])
        at(d2,r2,'EcrouColonneBMS'+str(i),nut,(x,y,-94.5),['MEC-SUPPORTS-ENERGIE'])
    save(d2,r2,['ELEC-BAT','ELEC-BMS','ELEC-PROTECTION-AMONT','ELEC-CONNECTEUR-MANUEL'],'sous_assemblage')

    # Énergie à l'étage supérieur. Rehausse de 3,2 mm pour dégager les articulations.
    holes_energy=[(x,y,6.6) for x in [-52,52] for y in [-52,52]]+[(x,y,6.6) for x in [-13.5,13.5] for y in [-76.1,-51.1,51.1,76.1]]+[(80,-56,3.2),(-80,56,3.2)]
    # La bande du pied P78 doit passer devant LED_2 ; le dégagement reste
    # limité au plateau projet et préserve le bord extérieur à Y80.
    slots_energy=[(94,-56,20,42),(-94,56,20,42)]+[
        (x,78.6 if (x,y)==(84,79) else y,6,4.8 if (x,y)==(84,79) else 2)
        for x in [-84,84] for y in [-79,-20,20,79]]
    from prototype_retenues_departs import energy_departure_interfaces
    departs_p64=energy_departure_interfaces()
    slots_energy+=departs_p64['lumieres_P64_mm']
    ep=plate('P64_Plateau_Energie_Prototype','Plateau énergie supérieur G10',(188,176,2.8),holes_energy,
        slots=slots_energy,
        ids=['MEC-SUPPORTS-ENERGIE','ELEC-PASSEFILS'],tint=GREY,
        note='Plateau Z36,2..39, modules à Z39. Rehausse3,2 au-dessus OEM pour dégager les articulations à35,7. Encoches guides et fentes rilsans hors modules. Dimensions nominales et tenue À valider.')
    meta(ep,'RetenuesDepartsBras',json.dumps(departs_p64,ensure_ascii=False))
    save_native(ep.Document)
    d3,r3=doc('SA03_Prototype_Energie','sous_assemblages','03 — Mesure et distribution protégée')
    at(d3,r3,'Isolation',ep,(0,0,36.2),['MEC-SUPPORTS-ENERGIE'])
    spacer=ring('P74_Cale_Energie_Prototype',3.2,10,6.6,['MEC-SUPPORTS-ENERGIE'],kind='pieces/fabriquees')
    for i,(x,y) in enumerate([(x,y) for x in [-52,52] for y in [-52,52]]):
        at(d3,r3,'CaleEnergie'+str(i),spacer,(x,y,33),['MEC-SUPPORTS-ENERGIE'])
    for name,file,xy,ids in [
        ('PM08','EQ_PM08_CAN_Enveloppe_Systeme_Candidat',(-22,-57.5),['ELEC-PM08']),
        ('PDB','EQ_Holybro_PDB18138_Systeme_Candidat',(42,4),['ELEC-PDB']),
        ('UART_isole','EQ_Waveshare15817_UART_Isole',(-33,4),['ELEC-ISO'])]:
        at(d3,r3,name,source('pieces/commerce/'+file+'.FCStd','Reference'),(*xy,ENERGY_PLATE_TOP),ids)
    fbranch=envelope('EQ_Protection_CA01_Prototype','Départ CA01 fusible15 A — candidat',(42,25,19),['ELEC-PROTECTION-W08'],(.22,.22,.24),'Réservation, calibre et courant mission À valider.')
    at(d3,r3,'Fusible_CA01',fbranch,(25,-50,ENERGY_PLATE_TOP),['ELEC-PROTECTION-W08'])
    save(d3,r3,['ELEC-PM08','ELEC-PDB','ELEC-ISO','ELEC-PROTECTION-W08'],'sous_assemblage')
    print('Batterie et énergie enregistrées',flush=True)

    # Capteurs : copier l'arbre utile, sans écraser la pièce historique imprimée.
    oldplate=source('pieces/fabriquees/P16_Platine_capteurs_isolee.FCStd','P01_PlatineRenforcee')
    ds,rs=doc('P65_Platine_Capteurs_Prototype','pieces/fabriquees','Platine Airy/Basler aluminium6061')
    base=ds.copyObject(oldplate,True);base.Label='Arbre P16 repris';base.Visibility=False
    cuts=[]
    for x,y in [(-35,27.5),(-58.8157,-13.75),(-11.1843,-13.75)]:cuts.append(cylinder(ds,'LamageAiry',3,2,(x,y,-127.5)))
    for x,y in [(x,y) for x in [-60,60] for y in [-37,37]]:cuts.append(cylinder(ds,'DegagementAncrage',3.5,8,(x,y,-133)))
    for x in [69.5,90.5]:
        c=cylinder(ds,'LamageBasler',3,1.5,(x,17.5,-144.75));c.Placement.Rotation=A.Rotation(A.Vector(1,0,0),-90);cuts.append(c)
    result=boolean(ds,rs,base,cuts);color(result,GREY)
    meta(rs,'Materiau','Aluminium6061-T6 ; fabrication en plusieurs opérations, tenue À valider')
    meta(rs,'InterfaceAiry','Plaque5mm avec lamages1,5mm ; portée locale3,5mm, M3×8. Piges : positions exactes à relever sur plan/lot avant perçage.')
    meta(rs,'InterfaceBasler','Deux fixations latérales source, portée locale3mm et M3×6. Vérification de tenue requise avec objectif180g.')
    sensorplate=save(ds,rs,['MEC-PLATINE-CAPTEURS','MEC-AIRY-THERMIQUE'],note='Arbre P16 conservé, matière/portées modifiées ; positions piges non libérées, aucun perçage arbitraire.')
    d4,r4=doc('SA04_Prototype_Perception','sous_assemblages','04 — Airy et Basler sur bloc isolé')
    link(d4,r4,'PlatineAluminium',sensorplate,ids=['MEC-PLATINE-CAPTEURS','MEC-AIRY-THERMIQUE'])
    oldblock=source('sous_assemblages/SA05A_Bloc_capteurs.FCStd','Ensemble')
    for o in oldblock.Group:
        if o.TypeId!='App::Link' or o.Name in ['Platine_P16','EQ_Objectif_Occurrence']:continue
        ids=['SEN-LIDAR'] if 'Airy' in o.Name else ['SEN-CAMERA'] if 'Basler' in o.Name else ['MEC-RETENUES-CAPTEURS']
        link(d4,r4,o.Name,o.LinkedObject,o.LinkPlacement,ids)
        SOURCES[rel(o.LinkedObject.Document.FileName)]=sha(o.LinkedObject.Document.FileName)
    cabletab=source('pieces/fabriquees/P10_Retenue_cable.FCStd','P10_AttacheCable1')
    at(d4,r4,'RetenueCable3',cabletab,(-70,43,-126),['MEC-RETENUES-CAPTEURS'])
    at(d4,r4,'RetenueCable4',cabletab,(90,-51,-126),['MEC-RETENUES-CAPTEURS'])
    appui=source('sous_assemblages/SA05B_Appui_Sorbothane.FCStd','Ensemble')
    oldsupports=source('sous_assemblages/SA05_Capteurs_Isoles.FCStd','Ensemble')
    for o in oldsupports.Group:
        if o.TypeId=='App::Link' and o.Name.startswith('Appui_'):
            link(d4,r4,o.Name,appui,o.LinkPlacement,['MEC-SUPPORT-ISOLATION','MEC-MANCHON','MEC-RONDELLE-CAPTURE','MEC-SORBOTHANE-BAS','MEC-SORBOTHANE-HAUT','MEC-VIS-ISOLATION','MEC-ECROU-ISOLATION'])
    dl,rl=doc('EQ_Fujinon_CF8ZA1S','pieces/commerce','Fujinon CF8ZA-1S Ø54×67 — enveloppe fabricant')
    rear=cylinder(dl,'MontureC',12.7,4);rl.addObject(rear);color(rear,GREY)
    barrel=cylinder(dl,'Corps',19.5,50,(0,0,4));rl.addObject(barrel);color(barrel,CARBON)
    front=cylinder(dl,'Front',27,13,(0,0,54));rl.addObject(front);color(front,CARBON)
    glass=cylinder(dl,'Verre',24,0.5,(0,0,67));rl.addObject(glass);color(glass,(.10,.23,.29))
    lens=save(dl,rl,['SEN-LENS','MEC-OBJECTIF-RETENUE'],'commerce_enveloppe','Source Fujinon Ø54×67 mm ; bagues/verre simplifiés, monture et intrusion à contrôler.')
    link(d4,r4,'ObjectifFujinon',lens,A.Placement(A.Vector(80,0,-153.57026),A.Rotation(A.Vector(1,0,0),180)),['SEN-LENS','MEC-OBJECTIF-RETENUE'])
    visairy=bolt('EQ_ISO4762_M3x8_Prototype',3,8)
    for i,(x,y) in enumerate([(-35,27.5),(-58.8157,-13.75),(-11.1843,-13.75)]):link(d4,r4,'VisAiry'+str(i),visairy,A.Placement(A.Vector(x,y,-127.5),A.Rotation()),['MEC-AIRY-VIS'])
    ancrage=bolt('EQ_ISO10642_M3x40_Prototype',3,40,True)
    for i,(x,y) in enumerate([(x,y) for x in [-60,60] for y in [-37,37]]):
        link(d4,r4,'Ancrage'+str(i),ancrage,A.Placement(A.Vector(x,y,-87),A.Rotation()),['MEC-ANCRAGES-CAPTEURS'])
        at(d4,r4,'RondelleAncrage'+str(i),washer,(x,y,-121.674),['MEC-ANCRAGES-CAPTEURS'])
        at(d4,r4,'EcrouAncrage'+str(i),nut,(x,y,-125.674),['MEC-ANCRAGES-CAPTEURS'])
    baslerbolt=bolt('EQ_ISO4762_M3x6_Prototype',3,6)
    for i,x in enumerate([69.5,90.5]):
        link(d4,r4,'VisBasler'+str(i),baslerbolt,A.Placement(A.Vector(x,17.5,-144.75),A.Rotation(A.Vector(1,0,0),-90)),['MEC-BASLER-FIXATIONS'])
    save(d4,r4,['SEN-LIDAR','SEN-CAMERA','SEN-LENS'],'sous_assemblage')
    print('Perception enregistrée',flush=True)

    # Porteuse fabricant dérivée : conserver Orin/6X, retirer uniquement le refroidissement générique identifié.
    holy=source('pieces/commerce/EQ_Holybro_Pixhawk_Jetson_Baseboard_candidat.FCStd','PorteuseFabricant')
    assert sha(holy.Document.FileName)=='2cade6f15f64465ef031ff52a14f7328d2acbe05b04614fecd60dd3327be299d','Source Holybro modifiée : refaire extraction'
    dh,rh=doc('EQ_Holybro11072_Prototype','pieces/commerce','Holybro11072 avec6X/Orin — source dérivée')
    component=dh.addObject('Part::Feature','FabricantSansRefroidissement')
    removed=set([1727,1728,1729,1730,1731,1732,2043,2044,2045,2046,2047,2048]+list(range(2049,2057)))
    assert len(holy.Shape.Solids)==2079,'Révision source changée, refaire extraction'
    component.Shape=Part.makeCompound([s for i,s in enumerate(holy.Shape.Solids) if i not in removed]);rh.addObject(component);color(component,GREEN)
    meta(rh,'Source',rel(holy.Document.FileName));meta(rh,'SourceSHA256',sha(holy.Document.FileName))
    meta(rh,'Limites','Orin et6X déjà inclus ; doublons de géométrie de source conservés sans compter de masse.12solides refroidissement et8solides entretoises/écrous nylon OEM remplacés retirés selon inventaire.')
    meta(rh,'SolidesSourceRetires',json.dumps(sorted(removed)))
    carrier=save(dh,rh,['AVI-CARRIER','AVI-CPU','AVI-FCU'],'commerce_fabricant_derive')
    ap=plate('P66_Platine_Avionique_Prototype','Interface avionique G10',(140,94,3),[(x,y,3.2) for x in [-60,60] for y in [-37,37]]+[(x,y,2.2) for x in [-43,43] for y in [-29,29]]+[(x,y,3.2) for x in [-66,66] for y in [-43,43]],ids=['MEC-SUPPORT-AVIONIQUE'],note='Fixations OEM M2 aux axes43×29 et porteuse M3 aux axes60×37 ; quatre ancrages fraisés sous face pour P75, dont deux partagés avec P72/P73.')
    ad=ap.Document;base=[o for o in ad.Objects if o.TypeId=='Part::Cut'][-1];cuts=[]
    for x in [-66,66]:
        for y in [-43,43]:
            cone=ad.addObject('Part::Cone','FraisureGuide');cone.Radius1=3.1;cone.Radius2=1.6;cone.Height=1.8;cone.Placement.Base=A.Vector(x,y,0);cuts.append(cone)
    ap.removeObject(base);final=boolean(ad,ap,base,cuts,'FraisuresGuides');color(final,GREY);save_native(ad)
    ac=ring('P67_Entretoise_Avionique_Prototype',10,6,3.2,['MEC-SUPPORT-AVIONIQUE'],kind='pieces/fabriquees')
    cc=ring('P68_Entretoise_CA01_Prototype',28.4,6,3.2,['MEC-SUPPORT-AVIONIQUE'],kind='pieces/fabriquees')
    d5,r5=doc('SA05_Prototype_Avionique','sous_assemblages','05 — Holybro6X/Orin, CA01 et refroidissement')
    at(d5,r5,'Interface',ap,(0,0,85),['MEC-SUPPORT-AVIONIQUE'])
    for i,(x,y) in enumerate([(x,y) for x in [-60,60] for y in [-37,37]]):
        at(d5,r5,'AppuiCA01_'+str(i),ac,(x,y,88),['MEC-SUPPORT-AVIONIQUE'])
        at(d5,r5,'ColonnePorteuse_'+str(i),cc,(x,y,99.6),['MEC-SUPPORT-AVIONIQUE'])
    card=source('pieces/fabriquees/CA01_PCB_Revue_20261003.FCStd','CarteCA01')
    link(d5,r5,'CA01',card,A.Placement(A.Vector(-63,40,98),A.Rotation()),['AVI-CA01','AVI-PCB'])
    link(d5,r5,'Holybro6XOrin',carrier,A.Placement(A.Vector(-63,-40,128),A.Rotation()),['AVI-CARRIER','AVI-FCU','AVI-CPU'])
    stackbolt=bolt('EQ_ISO4762_M3x55_Prototype',3,55)
    for i,(x,y) in enumerate([(x,y) for x in [-60,60] for y in [-37,37]]):
        link(d5,r5,'VisStack'+str(i),stackbolt,A.Placement(A.Vector(x,y,130.52232),A.Rotation()),['MEC-SUPPORT-AVIONIQUE'])
        for suffix,z in [('H',130.02232),('B',82.5)]:at(d5,r5,'RondelleStack'+suffix+str(i),washer,(x,y,z),['MEC-SUPPORT-AVIONIQUE'])
        at(d5,r5,'EcrouStack'+str(i),nut,(x,y,78.5),['MEC-SUPPORT-AVIONIQUE'])
    df,rf=doc('EQ_Waveshare_OrinFanPWM','pieces/commerce','Waveshare24076 — enveloppe d’intégration')
    b=box(df,'Base',(58,39,3),(-29,-19.5,0))
    relief=[cylinder(df,'DegagementVis',2.6,5,(x,y,-1)) for x in [-21.6,21.6] for y in [-15.09,13.71]]
    bcut=boolean(df,rf,b,relief);color(bcut,GREY)
    for x in range(-27,29,4):
        f=box(df,'Ailette',(1.2,39,10),(x,-19.5,3));rf.addObject(f);color(f,GREY)
    fan=cylinder(df,'Rotor',15,5,(0,0,13));rf.addObject(fan);color(fan,CARBON)
    cooling=save(df,rf,['MEC-REFROIDISSEMENT-JETSON'],'commerce_enveloppe','Réservation58×39×18 ; forme approximative avec passages Ø5,2 pour têtesmodule. Interface thermique, passages réels et bride à contrôler avec Waveshare24076, aucune retouche fabricant autorisée par ce modèle.')
    at(d5,r5,'OrinFan',cooling,(-34.5,0.1,141.3),['MEC-REFROIDISSEMENT-JETSON'],A.Rotation(A.Vector(0,0,1),90))
    dssd,rssd=doc('EQ_Samsung990EVOPlus_1To','pieces/commerce','Samsung990EVOPlus M.2 2280 — enveloppe PCB et composants')
    sb=box(dssd,'PCB',(80,22,.8),(-40,-11,1.6))
    sbcut=boolean(dssd,rssd,sb,[cylinder(dssd,'EncocheFixation',1.75,3,(39.98,0,1))]);color(sbcut,GREEN)
    sc=box(dssd,'Composants',(71,20,1.6),(-31,-10,0));rssd.addObject(sc);color(sc,CARBON)
    ssd=save(dssd,rssd,['AVI-SSD'],'commerce_enveloppe','Réservation2280 ; PCB0,8mm et composants côté inférieur simplifiés. Engagement dans KEY M 1-2199230-5, pas KEY E 2199230-4. EncocheR1,75 candidate, contacts et épaisseur réelle à contrôler ; aucune modification du SSD commercial prescrite.')
    at(d5,r5,'SSD',ssd,(-1.68,28,122.63),['AVI-SSD'])
    sd=envelope('EQ_Kingston_SDCE32GB','Kingston microSD32Go',(15,11,1),['AVI-SD'],CARBON,'FormatmicroSD ; réservation hors contact, engagement connecteur à contrôler.')
    at(d5,r5,'microSD',sd,(21.8,-6.1,134.7),['AVI-SD'],A.Rotation(A.Vector(0,0,1),90))
    save(d5,r5,['AVI-CARRIER','AVI-CPU','AVI-FCU','AVI-CA01','AVI-SSD','AVI-SD'],'sous_assemblage')

    # Navigation et sécurité séparées pour accès et examen de la portée des coaxiaux.
    d6,r6=doc('SA06_Prototype_Navigation','sous_assemblages','06 — GNSS, radio et sécurité')
    gnss=source('pieces/commerce/EQ_RTK_Helical_G4_Enveloppe_Systeme_Candidat.FCStd','Reference')
    at(d6,r6,'GNSS_Helical',gnss,(0,110,91),['SEN-GNSS'])
    navmount=plate('P69_Support_GNSS_Prototype','Réservation supportHolybro31153',(65,50,3),[(x,y,3.2) for x in [-25,25] for y in [-18,18]],ids=['MEC-SUPPORT-GNSS'],note='Adaptation de fixation et cotes support31153 À valider ; réservation locale.')
    extension=box(navmount.Document,'BrasAppui',(25,75,3),(-12.5,-95,0));navmount.addObject(extension);color(extension,GREY)
    from prototype_fixations_equipements import finish_navigation_mount, extend_radio_mount, build_navigation_fasteners
    finish_navigation_mount(sys.modules[__name__],navmount.Document,navmount,'gnss')
    save_native(navmount.Document)
    link(d6,r6,'SupportGNSS',navmount,A.Placement(A.Vector(0,110,88),A.Rotation()),['MEC-SUPPORT-GNSS'])
    antenna=compound_piece('EQ_Antenne_RP4TD_Prototype','AntenneT2,4GHz OEM',[
        ('cyl',(1.6,60),(0,0,0)),('box',(8,4,6),(-4,-2,27))],['RF-ANT'],folder='pieces/commerce',tint=CARBON,note='Dipôle de réservation ; coaxial65mm inclus modélisé dans faisceaux.')
    # Le collier traverse dans le plan XZ ; sa largeur4,6 est suivantY.
    rfs=plate('P70_Support_Radio_Prototype','SupportTPU95A antenne',(18,12,3),slots=[(-5,0,3,4.8),(5,0,3,4.8)],ids=['MEC-SUPPORTS-RF'],tint=BLUE,
        note='Deux passages3×4,8 mm pour bande T50R4,6×1,2 ; boucle autour du dipôle et du ligament central. Serrage/adhérence TPU et ancrage réel À valider.')
    extend_radio_mount(sys.modules[__name__],rfs.Document,rfs,
        next(o for o in rfs.Group if hasattr(o,'Shape') and not o.Shape.isNull()))
    save_native(rfs.Document)
    for i,(x,y,rot) in enumerate([(-76,28,A.Rotation()),(-76,-15,A.Rotation(A.Vector(1,0,0),90))]):
        # Conserver l'origine de la plaque initiale : la languette déporte
        # sa boîte globale et ne doit pas recentrer le support sous l'antenne.
        link(d6,r6,'SupportRF'+str(i),rfs,A.Placement(A.Vector(x,y,103),A.Rotation()),['MEC-SUPPORTS-RF'])
        at(d6,r6,'AntenneRF'+str(i),antenna,(x,y,106),['RF-ANT'],rot)
    safe=envelope('EQ_CUAV_USL_Prototype','CUAV C-RTK USL — réservation',(35,25,15),['AVI-SAFE'],ORANGE,'Dimensions de réservation et interfaceHolybro à vérifier ; aucun raccordement direct présumé.')
    sp=plate('P71_Support_Securite_Prototype','Support commandeG10',(55,30,2),[(-20,0,3.2),(20,0,3.2)],ids=['MEC-SUPPORTS-SECURITE'])
    extension=box(sp.Document,'BrasAppui',(20,65,2),(-10,0,0));sp.addObject(extension);color(extension,GREY)
    finish_navigation_mount(sys.modules[__name__],sp.Document,sp,'securite')
    save_native(sp.Document)
    link(d6,r6,'SupportSecurite',sp,A.Placement(A.Vector(0,-100,88),A.Rotation()),['MEC-SUPPORTS-SECURITE']);at(d6,r6,'BoutonBuzzerLED',safe,(0,-100,90),['AVI-SAFE'])
    build_navigation_fasteners(sys.modules[__name__],d6,r6)
    save(d6,r6,['SEN-GNSS','RF-ANT','AVI-SAFE'],'sous_assemblage')
    print('Avionique et navigation enregistrées',flush=True)
    assemblies=[(d1,r1),(d2,r2),(d3,r3),(d4,r4),(d5,r5),(d6,r6)]
    build_routes(assemblies)
    top,root=doc('Prototype_Cartographe','assemblages','Prototype cartographe X650 — définition sans dock')
    for d,r in assemblies:link(top,root,d.Name,r,A.Placement())
    meta(root,'Configuration','BOM-CARTO-PROTOTYPE ; pas de dock, JETI, TE ou échange sous tension.')
    meta(root,'Limites','Modèle de définition nominale. Interférences et interfaces résiduelles voir controle_assemblage_prototype.json ; aucune fabrication ou vol qualifié.')
    save(top,root,kind='assemblage_final')
    # Actualiser les empreintes après les changements paramétriques locaux.
    for rec in RECORDS:
        rec['sha256']=sha(MEC/rec['fichier'])
        rec['bbox_mm']=bbox(A.getDocument(rec['reference']).getObject(rec['objet']).Shape)
    newfiles={r['fichier'] for r in RECORDS}
    for loaded in A.listDocuments().values():
        if loaded.FileName and rel(loaded.FileName) not in newfiles:
            SOURCES[rel(loaded.FileName)]=sha(loaded.FileName)
    used=set(o['source'] for o in OCCURRENCES)
    recipes=['build_prototype.py','prototype_routage.py','prototype_guides.py',
             'cable_workbench_prototype.py','configuration_faisceau_haut_prototype.json',
             'prototype_retenues.py','prototype_connecteurs.py','connecteurs_coudes_camera_prototype.json',
             'prototype_retenues_puissance.py','prototype_retenues_capteurs.py','prototype_retenues_locales.py',
             'prototype_retenues_bras.py','prototype_retenues_basses.py',
             'prototype_retenues_hautes.py','prototype_retenues_reserves.py',
             'prototype_retenues_departs.py','prototype_fixations_equipements.py',
             'etage_batterie_helpers.py']
    evidence={'date':datetime.now().date().isoformat(),'date_utc':datetime.now(timezone.utc).isoformat(),'freecad':A.Version(),'script_sha256':sha(__file__),
        'recettes_sha256':{name:sha(VER/name) for name in recipes},
        'configuration':'BOM-CARTO-PROTOTYPE','assemblage':rel(top.FileName),'references':RECORDS,'occurrences':OCCURRENCES,
        'sources_preservees':SOURCES,'tri_chassis':{'conserves':retained,'exclus':sorted(reject_names)},
        'derivation_holybro':{'solides_source_retires':sorted(removed),'motif':'12 solides de refroidissement générique et8 fixations nylon OEM remplacées par les nouvelles références ; source inchangée'},
        'limites':['Cotes de réservation signalées dans les objets','Piges Airy non posées sans coordonnées constructeur','Masse, centrage, efforts et thermique non qualifiés',
                  'Support QS8/fusible, berceaux énergie, fixations BMS/avionique/radio/GNSS et protections des bornes restent des interfaces à détailler ; les enveloppes ne prouvent pas leur montage',
                  'Faisceaux Cable Workbench : terminaisons, matières, accès, serrage et tenue physiques À valider'],
        'finalisation_correcte':False}
    dump(VER/'construction_prototype.json',evidence)
    for file,h in SOURCES.items():assert sha(MEC/file)==h,('Source modifiée',file)
    A.setActiveDocument(top.Name);G.setActiveDocument(top.Name)
    view=G.activeDocument().activeView();view.viewAxonometric();view.fitAll();G.updateGui()
    # Les vues natives lancent une animation ; laisser la boucle GUI atteindre
    # la position finale avant capture évite des projections intermédiaires.
    def settle():
        for _ in range(15):G.updateGui();time.sleep(.1)
    for name,method in [('isometrique','viewAxonometric'),('dessus','viewTop'),('face','viewFront')]:
        getattr(view,method)();settle();view.fitAll();settle()
        view.saveImage(str(OUT/(name+'.png')),1800,1300,'White')
    view.viewAxonometric();settle();view.fitAll();settle();save_native(top)
    for rec in RECORDS:rec['sha256']=sha(MEC/rec['fichier'])
    evidence['finalisation_correcte']=True
    evidence['vues']=[{'fichier':rel(OUT/(n+'.png')),'sha256':sha(OUT/(n+'.png'))} for n in ['isometrique','dessus','face']]
    dump(VER/'construction_prototype.json',evidence)
    print(json.dumps({'assemblage':str(top.FileName),'references':len(RECORDS),'liens':len(OCCURRENCES)}),flush=True)
    # Tous les documents et preuves sont écrits ; éviter la destruction GUI
    # implicite de centaines de wrappers avant la sortie du processus isolé.
    import os
    os._exit(0)

def build_routes(assemblies):
    from prototype_routage import build_routes as create_routes
    create_routes(sys.modules[__name__], assemblies)

if __name__=='__main__':
    import os, traceback
    try:
        build();sys.stdout.flush();os._exit(0)
    except Exception:
        failure=traceback.format_exc()
        path=VER/'construction_prototype.json'
        state=json.loads(path.read_text('utf-8')) if path.exists() else {}
        state.update(finalisation_correcte=False,erreur_construction=failure)
        dump(path,state)
        traceback.print_exc();sys.stderr.flush();os._exit(1)
