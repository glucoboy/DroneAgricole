"""Infrastructure FreeCAD : références et variantes rehausse20, sources intactes.

P27 G10 dérivée du corps/passage de sangle P20 ; P37 colonne fabriquée6061 ;
P38 plateau OEM309 modifié par arbre Link+Cut, sans sauvegarder l'OEM original.
"""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,'C:/Program Files/FreeCAD 1.1/bin')
import FreeCAD as A, Part
from etage_batterie_helpers import require_legacy_layout
require_legacy_layout('build_rehausse20_avionique_20261002.py')

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
EXPORT=MEC/'exports/rehausse20_candidat_20261002'
EXPORT.mkdir(parents=True,exist_ok=True)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bbox(s):
    b=s.BoundBox
    return [b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax]
def meta(o,key,value):
    o.addProperty('App::PropertyString',key)
    setattr(o,key,value)
def create(name,folder,values=None):
    d=A.newDocument(name);r=d.addObject('App::Part','Reference' if folder=='pieces/fabriquees' else 'Ensemble')
    r.Label=name+' — À valider';meta(r,'Etat','À valider');meta(r,'RealisationCAO','Implémenté')
    s=d.addObject('Spreadsheet::Sheet','Parametres');r.addObject(s)
    for i,(key,value)in enumerate((values or {}).items(),1):
        s.set('A'+str(i),key);s.set('B'+str(i),str(value)+' mm');s.setAlias('B'+str(i),key)
    path=MEC/folder/(name+'.FCStd');d.saveAs(str(path))
    return d,r,path
def box(d,r,name,L,W,H,x,y,z):
    o=d.addObject('Part::Box',name);r.addObject(o)
    for prop,value in [('Length',L),('Width',W),('Height',H),('Placement.Base.x',x),('Placement.Base.y',y),('Placement.Base.z',z)]:o.setExpression(prop,value)
    return o
def cylinder(d,r,name,rad,h,x,y,z):
    o=d.addObject('Part::Cylinder',name);r.addObject(o)
    for prop,value in [('Radius',rad),('Height',h),('Placement.Base.x',x),('Placement.Base.y',y),('Placement.Base.z',z)]:o.setExpression(prop,value)
    return o
def cut(d,r,base,tools):
    if len(tools)==1:u=tools[0];r.addObject(u)
    else:
        u=d.addObject('Part::MultiFuse','Outils');r.addObject(u);u.Shapes=tools
    c=d.addObject('Part::Cut','Resultat');r.addObject(c);c.Base=base;c.Tool=u;c.Refine=True
    for o in [base,u]+tools:o.Visibility=False
    return c
def link(d,r,name,target,placement):
    o=d.addObject('App::Link',name);r.addObject(o);o.LinkedObject=target;o.LinkTransform=False;o.LinkPlacement=placement
    return o
def finish(d,r,out,path):
    d.recompute();assert out.Shape.isValid() and len(out.Shape.Solids)==1,(d.Name,out.Name)
    assert abs(r.Shape.Volume-out.Shape.Volume)<1e-6,(d.Name,'Reference!=final')
    d.save();Part.export([out],str(EXPORT/(d.Name+'.step')));out.Shape.exportStl(str(EXPORT/(d.Name+'.stl')))
    return {'fichier':str(path.relative_to(ROOT)).replace('\\','/'),'source_objet':'Reference','objet_final':out.Name,
            'sha256':sha(path),'volume_mm3':out.Shape.Volume,'bbox_mm':bbox(out.Shape),'forme_valide':True,'Reference_egale_final':True}
def newplacement(old,dx=0,dy=0,dz=0):return A.Placement(A.Vector(dx,dy,dz),A.Rotation()).multiply(old)


oem=A.openDocument(str(MEC/'pieces/commerce/EQ_Chassis_X650.FCStd'))
av=A.openDocument(str(MEC/'sous_assemblages/SA03_Avionique.FCStd'))
old_chassis=A.openDocument(str(MEC/'sous_assemblages/SA01_Chassis.FCStd'))
originals={Path(d.FileName):sha(Path(d.FileName))for d in A.listDocuments().values()if d.FileName}
records=[]

# P27 : quatre trous seulement aux axes réellement disponibles dans311.
d27,r27,p27=create('P27_Interface_Pixhawk_Rehausse20','pieces/fabriquees',
                 {'Longueur':128,'Largeur':98,'Epaisseur':2,'BaseZ':34,'FixX':43,'FixY':29,'TrouD':2.2})
meta(r27,'Materiau','G10, épaisseur2mm ; propriétés fournisseur et tenue À valider')
meta(r27,'Derivation','Corps128×98×2 et passages8×2 de P20, axes de fixation adaptés à311 ; Pixhawk non tourné')
base=box(d27,r27,'Plateau','Parametres.Longueur','Parametres.Largeur','Parametres.Epaisseur','-Parametres.Longueur/2','-Parametres.Largeur/2','Parametres.BaseZ')
tools=[]
for sx in [-1,1]:
    for sy in[-1,1]:tools.append(cylinder(d27,r27,'TrouM2','Parametres.TrouD/2','Parametres.Epaisseur+2 mm',f'{sx}*Parametres.FixX',f'{sy}*Parametres.FixY','Parametres.BaseZ-1 mm'))
for y in[-26,24]:tools.append(box(d27,r27,'PassageSangle','8 mm','2 mm','5 mm','-4 mm',f'{y} mm','Parametres.BaseZ-1 mm'))
out27=cut(d27,r27,base,tools);records.append(finish(d27,r27,out27,p27))

# P37 : usinage6061-T6, longueur utile70, deux taraudagesM3 simplifiés.
d37,r37,p37=create('P37_Entretoise70_6061_M3','pieces/fabriquees',
                 {'Longueur':70,'DiametreExterieur':6,'TaraudD':3,'TaraudUtile':8,'PercageD':2.5,'PercageProfondeur':10})
meta(r37,'Materiau','Aluminium6061-T6, candidat fabriqué ; tenue/fabrication À valider')
meta(r37,'Filetages','M3×0,5 femelle/femelle, profondeur utile8mm par bout ; préperçageØ2,5 profondeur10mm')
meta(r37,'LimiteModele','Taraudages représentés par cylindres au diamètre nominal3mm, filet hélicoïdal non dessiné')
body=cylinder(d37,r37,'Corps','Parametres.DiametreExterieur/2','Parametres.Longueur','0 mm','0 mm','0 mm')
tools=[cylinder(d37,r37,'TaraudBas','Parametres.TaraudD/2','Parametres.TaraudUtile+0.1 mm','0 mm','0 mm','-0.1 mm'),
       cylinder(d37,r37,'TaraudHaut','Parametres.TaraudD/2','Parametres.TaraudUtile+0.1 mm','0 mm','0 mm','Parametres.Longueur-Parametres.TaraudUtile'),
       cylinder(d37,r37,'PercageBas','Parametres.PercageD/2','Parametres.PercageProfondeur+0.1 mm','0 mm','0 mm','-0.1 mm'),
       cylinder(d37,r37,'PercageHaut','Parametres.PercageD/2','Parametres.PercageProfondeur+0.1 mm','0 mm','0 mm','Parametres.Longueur-Parametres.PercageProfondeur')]
out37=cut(d37,r37,body,tools);records.append(finish(d37,r37,out37,p37))

# P38 : conservation intégrale de309 et quatre nouveaux perçages pour rails.
d38,r38,p38=create('P38_Plateau309_PercagesRails','pieces/fabriquees',{'FixX':40,'FixY':51.5,'TrouD':3.2})
source=oem.getObject('Part__Feature309')
original=link(d38,r38,'PlateauOEM309',source,source.getGlobalPlacement())
meta(r38,'Materiau','Plateau carbone OEM160×160×2 existant, quatre perçagesØ3,2 ajoutés ; usinage carbone À valider')
meta(r38,'SourceOEM','EQ_Chassis_X650.FCStd/Part__Feature309, lien externe intact')
holes=[cylinder(d38,r38,'TrouRail','Parametres.TrouD/2','4 mm',f'{sx}*Parametres.FixX',f'{sy}*Parametres.FixY','30 mm')
       for sx in[-1,1]for sy in[-1,1]]
out38=cut(d38,r38,original,holes);records.append(finish(d38,r38,out38,p38))

# Deux oreillesP41 de2mm : vraie visM2×10, tête relevée2, pointe inchangée.
ds,rs,ps=create('EQ_Vis_M2x10_CHC_Candidat','pieces/commerce',
               {'LongueurSousTete':10,'TeteD':3.8,'TeteH':2,'CleAF':1.5,'ProfondeurEmpreinte':1})
meta(rs,'Specification','ISO4762 M2×10 ; matière, classe et fournisseur À valider')
tige=cylinder(ds,rs,'Tige','1 mm','Parametres.LongueurSousTete','0 mm','0 mm','-Parametres.LongueurSousTete')
tete=cylinder(ds,rs,'Tete','Parametres.TeteD/2','Parametres.TeteH','0 mm','0 mm','0 mm')
union=ds.addObject('Part::MultiFuse','CorpsVis');rs.addObject(union);union.Shapes=[tige,tete]
tige.Visibility=False;tete.Visibility=False
hexagon=ds.addObject('Part::Prism','EmpreinteSixPans');rs.addObject(hexagon);hexagon.Polygon=6
hexagon.setExpression('Circumradius','Parametres.CleAF/sqrt(3)')
hexagon.setExpression('Height','Parametres.ProfondeurEmpreinte+0.1 mm')
hexagon.setExpression('Placement.Base.z','Parametres.TeteH-Parametres.ProfondeurEmpreinte')
outvis=cut(ds,rs,union,[hexagon]);records.append(finish(ds,rs,outvis,ps))

exclusions=json.loads((MEC/'verification/avionique_empilee_20260916.json').read_text(encoding='utf-8'))['protocole']['exclusions_chassis']
d1,r1,p1=create('SA01_Chassis_Rehausse20','sous_assemblages',{'Rehausse':20,'AppuiBasZ':33})
groups={name:d1.addObject('App::Part',name)for name in['OEM_Conserve','Plateaux','FixationsHautes','Colonnes70']}
for g in groups.values():r1.addObject(g)
links_oem=[]
for source in oem.Objects:
    if source.TypeId!='Part::Feature' or not hasattr(source,'Shape')or source.Shape.isNull()or source.Name in exclusions:continue
    if source.Name in[f'Part__Feature{i:03}'for i in range(84,88)]:continue
    category='OEM_Conserve';target=source;pose=source.getGlobalPlacement();dz=0
    if source.Name=='Part__Feature309':target=r38;pose=A.Placement();category='Plateaux'
    elif source.Name=='Part__Feature311':pose=newplacement(pose,dz=20);dz=20;category='Plateaux'
    elif source.Name in[f'Part__Feature{i:03}'for i in range(92,96)]:pose=newplacement(pose,dz=20);dz=20;category='FixationsHautes'
    obj=link(d1,groups[category],source.Name,target,pose)
    if dz:obj.setExpression('LinkPlacement.Base.z',f'{pose.Base.z-dz:.12g} mm + Parametres.Rehausse')
    links_oem.append({'occurrence':obj.Name,'source_objet':target.Name,'source_fichier':Path(target.Document.FileName).name,'delta_Z_mm':dz})
for i,(x,y)in enumerate([(x,y)for x in[-52,52]for y in[-52,52]],1):
    obj=link(d1,groups['Colonnes70'],f'Colonne70_{i}',r37,A.Placement(A.Vector(x,y,33),A.Rotation()))
    obj.setExpression('LinkPlacement.Base.z','Parametres.AppuiBasZ')
d1.recompute();d1.save()

d3,r3,p3=create('SA03_Avionique_Rehausse20','sous_assemblages',{'DeltaHaut':72,'AncienFixX':29,'AncienFixY':43,'FixX':43,'FixY':29,'P41OreilleEp':2})
low=d3.addObject('App::Part','EtageInferieurConserve');high=d3.addObject('App::Part','EtagePixhawkReloge');r3.addObject(low);r3.addObject(high)
meta(high,'Pose','InterfaceZ106..108, isolant108..109, Pixhawk109..152,903, sangle jusqu’à153,6 ; orientation originale conservée')
upper=['P20_Platine_superieure','Isolant_Pixhawk','EQ_Pixhawk6X_Occurrence','Sangle_Pixhawk']
upper +=[f'{prefix}_{i}'for prefix in['P21_Cale','VisHaute','RondelleHaute','EcrouHaut']for i in range(1,5)]
av_records=[]
for source in av.Objects:
    if source.TypeId!='App::Link':continue
    target=source.LinkedObject;pose=source.LinkPlacement;dx=dy=dz=0;name=source.Name;extra_p41=False
    if name in upper:
        dz=72
        if name.startswith(('P21_Cale_','VisHaute_','RondelleHaute_','EcrouHaut_')):
            i=int(name.rsplit('_',1)[1]);sx=-1 if i in[1,2]else 1;sy=-1 if i in[1,3]else 1
            dx=sx*14;dy=-sy*14
        pose=newplacement(pose,dx,dy,dz)
        if name=='P20_Platine_superieure':target=r27;name='P27_Interface_Pixhawk'
        if name in ['VisHaute_1','VisHaute_2']:
            target=rs;pose=newplacement(pose,dz=2);dz+=2;extra_p41=True
        if name in ['RondelleHaute_1','RondelleHaute_2']:
            pose=newplacement(pose,dz=2);dz+=2;extra_p41=True
    obj=link(d3,high if source.Name in upper else low,name,target,pose)
    if source.Name in upper:
        obj.setExpression('LinkPlacement.Base.z',f'{source.LinkPlacement.Base.z:.12g} mm + Parametres.DeltaHaut'+(' + Parametres.P41OreilleEp'if extra_p41 else''))
        if dx:obj.setExpression('LinkPlacement.Base.x',f'{source.LinkPlacement.Base.x:.12g} mm + {sx}*(Parametres.FixX-Parametres.AncienFixX)')
        if dy:obj.setExpression('LinkPlacement.Base.y',f'{source.LinkPlacement.Base.y:.12g} mm + {sy}*(Parametres.FixY-Parametres.AncienFixY)')
    av_records.append({'occurrence':obj.Name,'ancienne_occurrence':source.Name,'delta_mm':[dx,dy,dz],
                       'source_fichier':Path(target.Document.FileName).name,'source_objet':target.Name})
d3.recompute();d3.save()

# Dessin de définition régénérable, sans prétention de qualification.
svg='''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="700" viewBox="0 0 1100 700">
<rect width="1100" height="700" fill="white"/><g font-family="Arial" fill="#152230">
<text x="45" y="50" font-size="26">P37 — Entretoise70 aluminium6061-T6 — À valider</text>
<text x="45" y="88" font-size="18">Quantité4 ; longueur70±0,10mm ; diamètre extérieur6±0,05mm</text>
<rect x="130" y="170" width="700" height="60" fill="#dde7ee" stroke="#152230" stroke-width="2"/>
<rect x="130" y="185" width="80" height="30" fill="white" stroke="#152230" stroke-width="2"/>
<rect x="750" y="185" width="80" height="30" fill="white" stroke="#152230" stroke-width="2"/>
<path d="M130 140V270 M830 140V270 M130 260H830" fill="none" stroke="#152230"/>
<text x="440" y="292" font-size="22">70mm</text><circle cx="940" cy="200" r="30" fill="#dde7ee" stroke="#152230" stroke-width="2"/>
<circle cx="940" cy="200" r="15" fill="white" stroke="#152230"/><text x="900" y="265" font-size="20">Ø6mm</text>
<text x="45" y="355" font-size="20">Deux taraudagesM3×0,5 femelles, profondeur utile8mm par extrémité.</text>
<text x="45" y="392" font-size="18">PréperçageØ2,5mm, profondeur10mm ; modèle CAO simplifié auØnominal3mm.</text>
<text x="45" y="429" font-size="18">Faces d’appui planes ; perpendicularité des faces à l’axe0,05mm ; coaxialité à contrôler.</text>
<text x="45" y="466" font-size="18">Ébavurer ; chanfrein d’entrée0,2×45° et arêtes cassées0,2mm à réaliser.</text>
<text x="45" y="510" font-size="18">Appuis assemblés Z33 etZ103 ; axesXY(±52,±52)mm.</text>
<text x="45" y="547" font-size="18">Vis OEM M3×8 conservées ; engagement géométrique vérifié, serrage et tenue à valider.</text>
<text x="45" y="604" font-size="18">Plan candidat : tolérances, taraudage6061, rigidité, vibration et fabrication non qualifiés.</text>
<text x="45" y="645" font-size="16">Source régénérable : verification/build_rehausse20_avionique_20261002.py — 2026-10-02</text>
</g></svg>'''
(EXPORT/'P37_Entretoise70_definition.svg').write_text(svg,encoding='utf-8')
proof={'date':'2026-10-02','statut':'À valider','FreeCAD':list(A.Version()),'script_sha256':sha(Path(__file__)),
       'references':records,'variantes':[{'fichier':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)}for p in[p1,p3]],
       'sources_originales_sha256_avant':{str(p.relative_to(ROOT)).replace('\\','/'):h for p,h in originals.items()},
       'sources_originales_sha256_apres':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p)for p in originals},
       'sources_originales_inchangees':all(sha(p)==h for p,h in originals.items()),
       'liens_chassis':links_oem,'liens_avionique':av_records,'exclusions_historiques':exclusions,
       'dessin_definition':str((EXPORT/'P37_Entretoise70_definition.svg').relative_to(ROOT)).replace('\\','/'),
       'limites':['Variantes candidates ; drone actif inchangé par ce script.',
                  'Colonnes6061 usinées, filetages, tolérances, serrage et rigidité non qualifiés.',
                  'Perçages supplémentairesP38 physiques à réaliser sur plateau OEM ; original numérique intact.',
                  'Rails, cassette, verrou et contacts vérifiés séparément après intégration.']}
assert proof['sources_originales_inchangees']
(MEC/'verification/construction_rehausse20_avionique_20261002.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sources_inchangees':True,'references':len(records),'variantes':2,'P27':bbox(out27.Shape),'P38':bbox(out38.Shape)}),flush=True)
for d in list(A.listDocuments().values()):A.closeDocument(d.Name)


