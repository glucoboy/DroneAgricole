"""Infrastructure FreeCAD : variante inactive berceau fixe, sans modifier l'existant.

Exécuter avec le Python embarqué FreeCAD 1.1. Les dimensions et matériaux sont
candidats ; la cinématique du loquet commercial n'est pas modélisée.
"""
from pathlib import Path
import json, math, hashlib, os
import FreeCAD as A
import Part

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
EXPORT = MEC / 'exports/berceau_fixe_candidat_20261002'
EXPORT.mkdir(parents=True, exist_ok=True)
FILES = []
PARAMS = dict(OuterL=212, OuterW=92, InnerL=204, InnerW=84,
              FloorZ=85, FloorT=4, WallTop=159, CoverZ=160, CoverT=3,
              CoverHoleL=192, CoverHoleW=72, HingeX=-110, HingeZ=161.5,
              AnchorX=36, AnchorY=33.5, HoleD=3.2, WallT=4, Rim=8,
              TraverseW=10, TraverseX=80, AnchorPadL=14, AnchorPadW=13,
              ProtectionT=1, FoamT=2, ShimT=7, ShimSkinT=1,
              ShimL=198, ShimW=78, HingeEarT=4,
              FloorTop='FloorZ+FloorT', ProtectionTop='FloorTop+ProtectionT',
              BatteryBase='ProtectionTop+FoamT', Battery20Base='BatteryBase+ShimT',
              WindowBottom='FloorTop+8 mm', WindowTop='WallTop-8 mm',
              P15Clearance=0.5, P15XMin=92, P15XMax=103,
              P15YMin=-46, P15YMax=-44, P15ZMin=97.6, P15ZMax=102.6)

def sheet(d, values):
    s=d.addObject('Spreadsheet::Sheet','Parametres')
    for i,(k,v) in enumerate(values.items(),1):
        s.set('A'+str(i),k); s.set('B'+str(i),'='+v if isinstance(v,str) else '='+str(v)+' mm'); s.setAlias('B'+str(i),k)
    return s

def doc(name, values=None):
    d=A.newDocument(name)
    root=d.addObject('App::Part','Reference');root.Label=name+' — candidat inactif'
    root.addProperty('App::PropertyString','Etat').Etat='À valider'
    root.addProperty('App::PropertyString','RealisationCAO').RealisationCAO='Implémenté'
    root.addProperty('App::PropertyString','Limites').Limites='Géométrie candidate ; matériaux, masses, tenue, fixation, cinématique loquet, thermique et fabrication À valider.'
    s=sheet(d,values or PARAMS);root.addObject(s)
    return d,root

def expr(obj, prop, value):
    obj.setExpression(prop, 'Parametres.'+value if isinstance(value,str) and value in PARAMS else str(value))

def box(d,root,name,dimensions,position):
    o=d.addObject('Part::Box',name);root.addObject(o)
    for prop,val in zip(['Length','Width','Height'],dimensions):expr(o,prop,val)
    for prop,val in zip(['Placement.Base.x','Placement.Base.y','Placement.Base.z'],position):expr(o,prop,val)
    return o

def fuse(d,root,name,objects):
    o=d.addObject('Part::MultiFuse',name);root.addObject(o);o.Shapes=objects;o.Refine=True
    for p in objects:p.Visibility=False
    return o

def cut(d,root,name,base,tool):
    o=d.addObject('Part::Cut',name);root.addObject(o);o.Base=base;o.Tool=tool;o.Refine=True
    base.Visibility=False;tool.Visibility=False
    return o

def cylinder(d,root,name,radius,height,position,axis=(0,0,1)):
    o=d.addObject('Part::Cylinder',name);root.addObject(o)
    expr(o,'Radius',radius);expr(o,'Height',height)
    o.Placement.Rotation=A.Rotation(A.Vector(0,0,1),A.Vector(*axis))
    for prop,val in zip(['Placement.Base.x','Placement.Base.y','Placement.Base.z'],position):expr(o,prop,val)
    return o

def meta(obj, key, val):
    obj.addProperty('App::PropertyString',key);setattr(obj,key,val)

def bbox(shape):
    b=shape.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]

def save(d,root,out,path):
    out.Label='Solide final — '+d.Name+' — À valider'
    meta(root,'SourceObjet','Reference');d.recompute()
    assert out.Shape.isValid(),d.Name
    assert out.Shape.Volume>0,d.Name
    d.saveAs(str(path));FILES.append((path,d,root,out))
    Part.export([out],str(EXPORT/(d.Name+'.step')))
    out.Shape.exportStl(str(EXPORT/(d.Name+'.stl')))
    return root

def made(name,builder):
    d,r=doc(name);out=builder(d,r)
    return save(d,r,out,MEC/'pieces/fabriquees'/str(name+'.FCStd'))

def frame(d,r):
    rim=box(d,r,'BaseExterieure',('OuterL','OuterW','FloorT'),('-Parametres.OuterL/2','-Parametres.OuterW/2','FloorZ'))
    opening=box(d,r,'OuvertureFond',('Parametres.OuterL-2*Parametres.Rim','Parametres.OuterW-2*Parametres.Rim','Parametres.FloorT+2 mm'),('-Parametres.OuterL/2+Parametres.Rim','-Parametres.OuterW/2+Parametres.Rim','Parametres.FloorZ-1 mm'))
    parts=[cut(d,r,'CadreFond',rim,opening)]
    for j,x in enumerate(['-Parametres.TraverseX','0 mm','Parametres.TraverseX']):parts.append(box(d,r,'Traverse'+str(j),('TraverseW','InnerW','FloorT'),(x+'-Parametres.TraverseW/2','-Parametres.InnerW/2','FloorZ')))
    # Plattes des quatre ancrages reliées au périmètre, et non trous dans le vide.
    for j,(x,y) in enumerate([(x,y) for x in [-36,36] for y in [-33.5,33.5]]):
        xexpr=('Parametres.AnchorX' if x>0 else '-Parametres.AnchorX')+'-Parametres.AnchorPadL/2'
        yexpr='Parametres.InnerW/2-Parametres.AnchorPadW' if y>0 else '-Parametres.InnerW/2'
        parts.append(box(d,r,'PlatteAncrage'+str(j),('AnchorPadL','AnchorPadW','FloorT'),(xexpr,yexpr,'FloorZ')))
    for j,x in enumerate(['-Parametres.OuterL/2','Parametres.InnerL/2']):parts.append(box(d,r,'ParoiExtremite'+str(j),('WallT','OuterW','Parametres.WallTop-Parametres.FloorTop'),(x,'-Parametres.OuterW/2','FloorTop')))
    for j,y in enumerate(['-Parametres.OuterW/2','Parametres.InnerW/2']):parts.append(box(d,r,'ParoiLaterale'+str(j),('InnerL','WallT','Parametres.WallTop-Parametres.FloorTop'),('-Parametres.InnerL/2',y,'FloorTop')))
    for j,y in enumerate([-39,35]):
        # Sommet arrondi concentrique à l'axe : le coin rectangulaire d'origine
        # interceptait le cadre du capot pendant la rotation.
        parts.append(box(d,r,'PiedOreilleFixe'+str(j),(8,4,7.5),(-114,y,154)))
        parts.append(cylinder(d,r,'SommetOreilleFixe'+str(j),4,4,('HingeX',y,'HingeZ'),(0,1,0)))
    # Fusion par contact plan de l'oreille au dos de la paroi : connexion solide native.
    main=fuse(d,r,'StructureBerceau',parts)
    windows=[]
    for j,y in enumerate([-47,41]):
        for k,x in enumerate([-92,5]):windows.append(box(d,r,'FenetreLaterale'+str(j)+str(k),(87,6,'Parametres.WindowTop-Parametres.WindowBottom'),(x,y,'WindowBottom')))
    for j,y in enumerate([-36,14]):windows.append(box(d,r,'FenetreAvant'+str(j),(6,22,'Parametres.WindowTop-Parametres.WindowBottom'),(101,y,'WindowBottom')))
    windows.append(box(d,r,'FenetreArriere',(6,68,'Parametres.WindowTop-Parametres.WindowBottom'),(-107,-34,'WindowBottom')))
    for j,y in enumerate([-34.5,29.5]):windows.append(box(d,r,'DegagementCharniere'+str(j),(6,5,6),(-107,y,'Parametres.WallTop-5 mm')))
    # Dégagement local du support P15 actif, sans modifier sa référence.
    # Intersection externe relevée : X92..103,Y-46..-44,Z97.6..102.6.
    windows.append(box(d,r,'DegagementSupportP15',(
        'Parametres.P15XMax-Parametres.P15XMin+2*Parametres.P15Clearance',
        'Parametres.P15YMax-Parametres.P15YMin+2*Parametres.P15Clearance',
        'Parametres.P15ZMax-Parametres.P15ZMin+2*Parametres.P15Clearance'),(
        'Parametres.P15XMin-Parametres.P15Clearance',
        'Parametres.P15YMin-Parametres.P15Clearance',
        'Parametres.P15ZMin-Parametres.P15Clearance')))
    main=cut(d,r,'CadreFenetre',main,fuse(d,r,'OutilsFenetres',windows))
    holes=[]
    for j,(x,y) in enumerate([(x,y) for x in [-36,36] for y in [-33.5,33.5]]):holes.append(cylinder(d,r,'PercageAncrage'+str(j),'Parametres.HoleD/2','Parametres.FloorT+2 mm',('Parametres.AnchorX' if x>0 else '-Parametres.AnchorX','Parametres.AnchorY' if y>0 else '-Parametres.AnchorY','Parametres.FloorZ-1 mm')))
    for j,y in enumerate([-40,34]):holes.append(cylinder(d,r,'PercageOreilleFixe'+str(j),'Parametres.HoleD/2',6,('HingeX',y,'HingeZ'),(0,1,0)))
    return cut(d,r,'Resultat',main,fuse(d,r,'OutilsPercage',holes))

def protection(d,r):
    meta(r,'MateriauCandidat','G10 1 mm, qualité/tenue et isolation À valider')
    return box(d,r,'PlaqueG10',('InnerL','InnerW','ProtectionT'),('-Parametres.InnerL/2','-Parametres.InnerW/2','FloorTop'))

def cover(d,r):
    outer=box(d,r,'CadreCapot',('OuterL','OuterW','CoverT'),('-Parametres.OuterL/2','-Parametres.OuterW/2','CoverZ'))
    hole=box(d,r,'OuvertureCapot',('CoverHoleL','CoverHoleW','Parametres.CoverT+2 mm'),('-Parametres.CoverHoleL/2','-Parametres.CoverHoleW/2','Parametres.CoverZ-1 mm'))
    parts=[cut(d,r,'CapotAjoure',outer,hole)]
    # Éviter la paroi arrière : partie basse des oreilles reste à X<=-106.
    for j,y in enumerate([-34,30]):
        parts.append(box(d,r,'OreilleCapot'+str(j),(8,4,8),(-114,y,158)))
        parts.append(box(d,r,'PontOreille'+str(j),(12,4,3),(-114,y,160)))
    main=fuse(d,r,'CapotAvecOreilles',parts)
    holes=[cylinder(d,r,'PercageCharniere'+str(j),'Parametres.HoleD/2',6,('HingeX',y,'HingeZ'),(0,1,0)) for j,y in enumerate([-35,29])]
    return cut(d,r,'Resultat',main,fuse(d,r,'OutilsPercage',holes))

def shim(d,r):
    meta(r,'Usage','Cale rigide 7 mm uniquement pack 20 Ah hauteur nominale 58 mm ; matériaux, isolation, tolérances À valider')
    base=box(d,r,'ContourCale',('ShimL','ShimW','Parametres.ShimT-Parametres.ShimSkinT'),('-Parametres.ShimL/2','-Parametres.ShimW/2','BatteryBase'))
    tool=box(d,r,'OuvertureCale',('Parametres.ShimL-2*Parametres.Rim','Parametres.ShimW-2*Parametres.Rim','ShimT'),('-Parametres.ShimL/2+Parametres.Rim','-Parametres.ShimW/2+Parametres.Rim','Parametres.BatteryBase-1 mm'))
    parts=[cut(d,r,'CalePerimetrique',base,tool)]
    for j,x in enumerate(['-Parametres.TraverseX','0 mm','Parametres.TraverseX']):parts.append(box(d,r,'TraverseCale'+str(j),('TraverseW','ShimW','Parametres.ShimT-Parametres.ShimSkinT'),(x+'-Parametres.TraverseW/2','-Parametres.ShimW/2','BatteryBase')))
    parts.append(box(d,r,'PeauContinue',('ShimL','ShimW','ShimSkinT'),('-Parametres.ShimL/2','-Parametres.ShimW/2','Parametres.Battery20Base-Parametres.ShimSkinT')))
    return fuse(d,r,'Cale20Ah',parts)

P23=made('P23_BerceauFixe_Candidat',frame)
P24=made('P24_ProtectionG10_Candidat',protection)
P25=made('P25_CapotCaptif_Candidat',cover)
P26=made('P26_Cale20Ah_Candidat',shim)

def commerce(name,values,dim,pos,notes):
    d,r=doc(name,{**PARAMS,**values});meta(r,'Definition',notes)
    out=box(d,r,'Enveloppe',dim,pos)
    return save(d,r,out,MEC/'pieces/commerce'/str(name+'.FCStd'))

B16=commerce('EQ_Tattu6S16Ah_Candidat',{'Longueur':192,'Largeur':76,'Hauteur':65},
    ('Parametres.Longueur','Parametres.Largeur','Parametres.Hauteur'),('-Parametres.Longueur/2','-Parametres.Largeur/2','BatteryBase'),
    'Enveloppe nominale 192x76x65 mm ; maximum publié 197x78x67 mm ; 1988 ±20 g ; https://genstattu.com/ta-30c-16000-6s1p-xt90.html ; câbles et connecteurs absents.')
B20=commerce('EQ_Tattu6S20AhNMC_Candidat',{'Longueur':193,'Largeur':76,'Hauteur':58},
    ('Parametres.Longueur','Parametres.Largeur','Parametres.Hauteur'),('-Parametres.Longueur/2','-Parametres.Largeur/2','Battery20Base'),
    'Enveloppe nominale 193x76x58 mm ; maximum 198x78x60 mm hypothèse non fabricant ; 1950 ±20 g ; SKU TAA200006S5X9S ; câbles/connecteurs absents ; chimie/charge À valider.')
LATCH=commerce('EQ_Southco91_Reservation_Candidat',{'Longueur':58,'Largeur':24,'Saillie':17},
    ('Parametres.Saillie','Parametres.Largeur','Parametres.Longueur'),('Parametres.OuterL/2','-Parametres.Largeur/2','Parametres.CoverZ-Parametres.Longueur/2'),
    'Réservation seulement Southco91-361-52 + 91-634-52 ; masses inconnues ; position/pivot/gâche/perçages non figés ; pas mécanisme fonctionnel ni retenue démontrée ; https://media.southco.com/media/static/Literature/91.en.pdf')
FOAM=commerce('EQ_MousseBasse_Reservation_Candidat',{'Longueur':204,'Largeur':84,'Epaisseur':2},
    ('Parametres.Longueur','Parametres.Largeur','FoamT'),('-Parametres.Longueur/2','-Parametres.Largeur/2','ProtectionTop'),
    'Volume de réservation 2 mm seulement ; compression, feu, vieillissement, adhésif et isolation inconnus.')
d,r=doc('EQ_AxeCharniere_Reservation_Candidat',{'Diametre':3,'Longueur':82})
axis=cylinder(d,r,'AxeReserve','Parametres.Diametre/2','Parametres.Longueur',(-110,-41,161.5),(0,1,0))
meta(r,'Definition','Réserve axe 3 mm ; métal, capture axiale, articulation, visserie et résistance inconnus ; pas pièce à fabriquer.')
AXIS=save(d,r,axis,MEC/'pieces/commerce/EQ_AxeCharniere_Reservation_Candidat.FCStd')

def capot_placement(angle):
    pivot=A.Vector(-110,0,161.5)
    rotation=A.Rotation(A.Vector(0,1,0),-angle)
    return A.Placement(pivot-rotation.multVec(pivot),rotation)

ASSEMBLIES=[]
def assembly(variant):
    name='SA02_BerceauFixe_Candidat'+('_20Ah' if variant==20 else '')
    d,r=doc(name)
    meta(r,'Configuration','Inactive ; batterie seule échangée, capot captif ; aucune sélection finale')
    d.Parametres.set('A50','AngleOuvertureCandidat');d.Parametres.set('B50','=0 deg');d.Parametres.setAlias('B50','AngleOuvertureCandidat')
    path=MEC/'sous_assemblages'/str(name+'.FCStd');d.recompute();d.saveAs(str(path))
    refs=[('Berceau',P23),('ProtectionG10',P24),('MousseBasse',FOAM),('Capot',P25),('AxeReserve',AXIS),('LoquetReservation',LATCH)]
    if variant==20:refs.append(('Cale20Ah',P26))
    refs.append(('Batterie',B20 if variant==20 else B16))
    for objname,ref in refs:
        link=d.addObject('App::Link',objname);link.setLink(ref);r.addObject(link)
        if objname=='Capot':
            link.LinkPlacement=A.Placement(A.Vector(),A.Rotation(A.Vector(0,1,0),1))
            link.setExpression('LinkPlacement.Rotation.Angle','-Parametres.AngleOuvertureCandidat')
            link.setExpression('LinkPlacement.Base.x','Parametres.HingeX*(1-cos(Parametres.AngleOuvertureCandidat))+Parametres.HingeZ*sin(Parametres.AngleOuvertureCandidat)')
            link.setExpression('LinkPlacement.Base.z','Parametres.HingeZ*(1-cos(Parametres.AngleOuvertureCandidat))-Parametres.HingeX*sin(Parametres.AngleOuvertureCandidat)')
    d.recompute();d.save()
    ASSEMBLIES.append((path,d,r,variant))
    Part.export([d.getObject(x) for x,_ in refs],str(EXPORT/(name+'.step')))
    return d

A16=assembly(16);A20=assembly(20)

def collisions(pairs):
    out=[]
    for a,b,sa,sb in pairs:
        if sa.BoundBox.intersect(sb.BoundBox):
            v=sa.common(sb).Volume
            if v>1e-6:out.append({'a':a,'b':b,'volume_mm3':v})
    return out

def validate(assembly_d,variant):
    fixed_names=['Berceau','ProtectionG10','MousseBasse']+(['Cale20Ah'] if variant==20 else [])
    fixed={n:assembly_d.getObject(n).Shape.copy() for n in fixed_names}
    battery=assembly_d.getObject('Batterie').Shape.copy()
    capot=assembly_d.getObject('Capot').Shape.copy()
    angles=list(range(0,111,5))
    motion=[]
    for angle in angles:
        s=capot.copy();s.Placement=capot_placement(angle)
        hits=collisions([(a,'Capot',b,s) for a,b in fixed.items()]+[('Batterie','Capot',battery,s)])
        motion.append({'angle_deg':angle,'capot_bbox_mm':bbox(s),'interferences':hits,'valid':s.isValid()})
    nominal=collisions([('Batterie',n,battery,s) for n,s in fixed.items()])
    maxshape=Part.makeBox(197 if variant==16 else 198,78,67 if variant==16 else 60,A.Vector(-98.5 if variant==16 else -99,-39,92 if variant==16 else 99))
    maxhits=collisions([('BatterieMax',n,maxshape,s) for n,s in fixed.items()]+[('BatterieMax','Capot',maxshape,capot)])
    extraction=[]
    opened=capot.copy();opened.Placement=capot_placement(110)
    targets={n:s for n,s in fixed.items() if n!='Cale20Ah'}
    targets.update({'CapotOuvert110':opened,'LoquetReservation':assembly_d.LoquetReservation.Shape.copy()})
    for kind,pack in [('nominal',battery),('maximum',maxshape)]:
        for dz in [0,5,20,50,100,200]:
            moved=pack.copy();moved.translate(A.Vector(0,0,dz))
            extraction.append({'pack':kind,'offset_z_mm':dz,'interferences':collisions([(kind,n,moved,s) for n,s in targets.items()])})
    return {'variant_ah':variant,'nominal_battery_bbox_mm':bbox(battery),'pack_fixed_interferences':nominal,
            'maximum_pack_bbox_mm':bbox(maxshape),'maximum_pack_interferences':maxhits,
            'motion_samples':motion,'vertical_extraction_samples':extraction,'latch_motion_not_verified':True,'axis_reserved_not_verified':True}

report={'date':'2026-10-02','status':'À valider','realisation_CAO':'Implémenté','active_configuration_modified':False,
        'script':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),
        'toolchain':str(A.Version()),'references':[],
        'assemblies':[validate(A16,16),validate(A20,20)],
        'limits':['Loquet = réservation commerciale fermée, aucune cinématique/accrochage ni perçage commercial validé.',
                  'Géométrie nominale et tolérances candidates ; pack20Ah maximum = hypothèse non fabricant.',
                  'Fixations M3 candidates dans lumières OEM27x3 : rondelles/sous-face/glissement/nonrotation non vérifiés.',
                  'Matériaux/densités/masse installée inconnus ; volumes ne sont pas masses pesées.',
                  'Connecteurs/câbles, gonflement pack, compression mousse, verrouillage, poussière/gants, thermique et tenue non qualifiés.',
                  'Rayons des arêtes de contact avec le pack et protection latérale restent à détailler ; géométrie ne démontre pas absence de détérioration du softpack.',
                  'Ouverture110deg candidate seulement ; angles échantillonnés ne constituent pas preuve continue.'],
        'hinge_ears_adjustment':'Oreilles capot partie basse X-114..-106 et pont X-114..-102 Z160..163 ; dégagements arrière sous oreilles mobiles ; sommet fixe arrondi R4 coaxial, pied Z154..161.5, pour dégager la rotation du cadre.'}
report['p15_local_clearance']={'source':'Contrôle externe BRep.common Berceau/P15 actuel',
    'original_intersection_mm3':110,'original_intersection_bbox_mm':[92,-46,97.6,103,-44,102.6],
    'candidate_clearance_mm':0.5,'notch_bbox_mm':[91.5,-46.5,97.1,103.5,-43.5,103.1],
    'active_p15_modified':False,'strength_not_verified':True}
for path,d,r,out in FILES:
    d.recompute()
    report['references'].append({'file':str(path.relative_to(MEC)).replace('\\','/'),'source_objet':'Reference',
        'final_shape_object':out.Name,'valid':out.Shape.isValid(),'solids':len(out.Shape.Solids),
        'volume_mm3':out.Shape.Volume,'reference_shape_volume_mm3':r.Shape.Volume,'reference_matches_final':abs(r.Shape.Volume-out.Shape.Volume)<1e-6,'bbox_mm':bbox(out.Shape),
        'parameter_sheet':True,'feature_types':sorted(set(o.TypeId for o in r.Group))})
report['native_angle_command']=[]
for path,d,r,var in ASSEMBLIES:
    results=[]
    for angle in [0,45,110,0,110]:
        d.Parametres.set('B50','='+str(angle)+' deg');d.recompute()
        actual=d.Capot.LinkPlacement.toMatrix().A
        expected=capot_placement(angle).toMatrix().A
        error=max(abs(a-b) for a,b in zip(actual,expected))
        assert error<1e-9,(var,angle,error)
        results.append({'angle_deg':angle,'placement_matrix_max_error':error,'valid':d.Capot.Shape.isValid()})
    d.Parametres.set('B50','=0 deg');d.recompute()
    report['native_angle_command'].append({'variant_ah':var,'parameter':'Parametres.AngleOuvertureCandidat','cell':'B50','samples':results})
# Réouverture et recalcul dans le même processus, références externes conservées.
for path,d,r,var in ASSEMBLIES:A.closeDocument(d.Name)
for path,d,r,out in reversed(FILES):A.closeDocument(d.Name)
reopened=[]
for path,_,_,var in ASSEMBLIES:
    d=A.openDocument(str(path));d.recompute()
    links=[o for o in d.Objects if o.TypeId=='App::Link']
    reopened.append({'file':str(path.relative_to(MEC)).replace('\\','/'),
        'links':len(links),'all_linked':all(o.LinkedObject is not None for o in links),
        'all_shapes_valid':all(o.Shape.isValid() and o.Shape.Volume>0 for o in links),
        'object_errors':[o.Name for o in d.Objects if 'Invalid' in o.State]})
report['reopening']=reopened
# Maillages dérivés temporaires, pour aperçu fidèle sans modifier les modèles.
meshdir=ROOT/'.runtime/batterie_reprise_20261002';meshdir.mkdir(parents=True,exist_ok=True)
colors={'Batterie':'#3569d0','Berceau':'#d98032','Capot':'#999da5',
        'ProtectionG10':'#659d61','Cale20Ah':'#659d61','MousseBasse':'#47594d',
        'LoquetReservation':'#e0c43e','AxeReserve':'#696a6c'}
states=[]
for variant,path in [(16,ASSEMBLIES[0][0]),(20,ASSEMBLIES[1][0])]:
    d=A.openDocument(str(path));d.recompute()
    for angle in [0,110]:
        parts=[]
        for link in [o for o in d.Objects if o.TypeId=='App::Link']:
            shape=link.Shape.copy()
            if link.Name=='Capot':shape.Placement=capot_placement(angle)
            vertices,facets=shape.tessellate(0.5)
            parts.append({'name':link.Name,'color':colors[link.Name],
                'vertices':[[v.x,v.y,v.z] for v in vertices],
                'faces':[list(f) for f in facets]})
        states.append({'variant_ah':variant,'angle_deg':angle,'parts':parts})
(meshdir/'maillages.json').write_text(json.dumps({'source':'Shapes finales natives','deflection_mm':0.5,'states':states}),encoding='utf-8')
proof=MEC/'verification/construction_berceau_fixe_candidat_20261002.json'
proof.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'references':len(FILES),'variants':[
    {'ah':a['variant_ah'],'motion_hits':sum(len(s['interferences']) for s in a['motion_samples']),
     'extraction_hits':sum(len(s['interferences']) for s in a['vertical_extraction_samples'])} for a in report['assemblies']],
     'reopening':reopened},ensure_ascii=False))
