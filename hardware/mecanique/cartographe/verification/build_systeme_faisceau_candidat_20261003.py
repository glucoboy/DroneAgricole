"""Infrastructure CAO de revue : équipements cible et chemins déclaratifs.

Ne remplace aucun natif existant. Les routes sont des réservations, pas un
dossier de fabrication. Exécuter avec le Python FreeCAD 1.1.
"""
from pathlib import Path
from etage_batterie_helpers import require_legacy_layout
require_legacy_layout('build_systeme_faisceau_candidat_20261003.py')
import hashlib, json, math
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
VER=MEC/'verification'
RECIPE=VER/'routes_systeme_candidat_20261003.json'
OUT=MEC/'exports/systeme_candidat_20261003'
OUT.mkdir(parents=True,exist_ok=True)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p): return str(Path(p).relative_to(ROOT)).replace('\\','/')
def write(p,data): p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def meta(o,k,v):
    if k not in o.PropertiesList: o.addProperty('App::PropertyString',k)
    setattr(o,k,str(v))
def new(name):
    d=A.newDocument(name);r=d.addObject('App::Part','Reference')
    meta(r,'Etat','À valider');meta(r,'RealisationCAO','Implémenté')
    return d,r
def save(d,folder):
    d.recompute();p=MEC/folder/(d.Name+'.FCStd');d.saveAs(str(p));return p
def load(folder,name):
    p=MEC/folder/(name+'.FCStd')
    d=next((x for x in A.listDocuments().values() if x.FileName and Path(x.FileName)==p),None)
    if d is None:d=A.openDocument(str(p))
    for key in ['Ensemble','Reference','StackCandidate','CarteCA01']:
        if d.getObject(key):return d.getObject(key)
    raise RuntimeError('Racine inconnue : '+str(p))
def link(d,r,name,target,pos=(0,0,0)):
    o=d.addObject('App::Link',name);r.addObject(o);o.setLink(target)
    o.LinkTransform=False;o.LinkPlacement=A.Placement(A.Vector(*pos),A.Rotation())
    return o
def box(d,r,n,dim,pos=(0,0,0)):
    o=d.addObject('Part::Box',n);r.addObject(o)
    o.Length,o.Width,o.Height=dim;o.Placement.Base=A.Vector(*pos);return o

baseline=json.loads((VER/'inventaire_systeme_20261003.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/f)==h for f,h in baseline['sources_sha256'].items()),'CAO active changée depuis inventaire'
sources=dict(baseline['sources_sha256'])
stack=load('sous_assemblages','SA03_CA01_Holybro_candidat')
for dd in list(A.listDocuments().values()):
    if dd.FileName:sources[rel(dd.FileName)]=sha(dd.FileName)

# Modèles commerciaux dérivés : primitives nominales, sources jamais usinées.
d,pm=new('EQ_PM08_CAN_Enveloppe_Systeme_Candidat')
box(d,pm,'CorpsNominal',(45,41,26))
meta(pm,'MPN','15028 / 15029 / 15030 : variante à confirmer')
meta(pm,'Source','https://holybro.com/products/dronecan-pm08-power-module-14s-200a')
meta(pm,'Limite','Corps nominal hors câbles et prises, 45×41×26 mm. Support, sorties, lot et accouplements à définir.')
save(d,'pieces/commerce')
d,pdb=new('EQ_Holybro_PDB18138_Systeme_Candidat')
original=MEC/'sources_fabricants/systeme_20261003/Holybro_PDB18138_original.stp'
s=Part.read(str(original));b=s.BoundBox
o=d.addObject('Part::Feature','FabricantSTEP');pdb.addObject(o);o.Shape=s
meta(pdb,'MPN','18138');meta(pdb,'SourceSHA256',sha(original))
meta(pdb,'Source','https://cdn.shopify.com/s/files/1/0604/5905/7341/files/pdb-xt90pb-f.stp?v=1741143462')
meta(pdb,'Limite','STEP OEM inchangé, pose sur occurrence. Fixations, prises accouplées et masse nette à valider.')
save(d,'pieces/commerce')
d,gnss=new('EQ_RTK_Helical_G4_Enveloppe_Systeme_Candidat')
box(d,gnss,'CorpsNominal',(51.1,35,22.9),(-25.55,-17.5,0))
o=d.addObject('Part::Cylinder','AntenneHelicoidaleNominale');gnss.addObject(o)
o.Radius=13.75;o.Height=59;o.Placement.Base=A.Vector(0,0,22.9)
meta(gnss,'Source','https://docs.holybro.com/gps-and-rtk-system/f9p-h-rtk-series/dronecan-f9p/specification')
meta(gnss,'Limite','Boîtier et antenne en primitives ; géométrie de jonction et variante STM32G4 non confirmées. Support et coaxial éventuel ouverts.')
save(d,'pieces/commerce')

d,distribution=new('SA07_Distribution_Systeme_Candidat')
save(d,'sous_assemblages')
link(d,distribution,'PM08',pm,(-138,-82,-28))
# La carte PDB est entièrement sous le plateau bas ; prises vers +Z.
link(d,distribution,'PDB18138',pdb,(90-b.XMin,-40-b.YMin,-59-b.ZMin))
meta(distribution,'Limite','Implantation nominale non fixée. Supports isolants et prises accouplées absents ; pas autorisation de montage.')
save(d,'sous_assemblages')
d,rtk=new('SA06_RTK_Helical_Systeme_Candidat')
save(d,'sous_assemblages')
link(d,rtk,'GNSS_Helical_G4',gnss,(10,234,176))
meta(rtk,'Limite','Pose candidate près du mât OEM ; fixation et masque GNSS à concevoir. Ancien RTK patch retiré uniquement de cette variante.')
save(d,'sous_assemblages')

reg=json.loads((ROOT/'hardware/electronique/cartographe/faisceau_systeme_cible_20261003.json').read_text(encoding='utf-8'))
families={f['id']:f for f in reg['familles_cables']}
placement=json.loads((ROOT/'hardware/electronique/cartographe/carte_avionique/placement_mecanique.json').read_text(encoding='utf-8'))
def ca(ref):
    x,y,_=placement['placements'][ref]
    return [x-63,y-40,-81]
routes=[]
def route(name,group,points,diam,radius,section=None,n=None,owner='faisceau ajouté',w=None):
    routes.append({'id':name,'groupe':group,'wxx':w or next(g['wxx'] for g in reg['groupes'] if g['id']==group),
        'points_mm':points,'diametre_enveloppe_mm':diam,'rayon_reservation_mm':radius,
        'section_cuivre_par_fil_mm2':section,'nombre_fils':n,
        'propriete_masse':owner,'longueur_coupe_mm':None,'masse_lineique_g_m':None,
        'endpoints_oem_cotes':False,'statut':'À valider',
        'limite':'Points d’étude, fiches accouplées non cotées. Boucles, bridages et tolérances non qualifiés.'})
route('JETI_OUT_PM','F01-ENERGIE-AMONT',[[-50,0,123.5],[-72,-82,140],[-140,-100,90],[-160,-82,-12],[-138,-72,-12]],11,50,8.37,2,'câbles JETI/PM inclus à réconcilier')
route('PM_OUT_PDB','F05-DISTRIBUTION',[[-93,-62,-12],[-75,-85,-32],[45,-85,-40],[80,-62,-40],[90,-10,-40]],11,50,8.37,2,'câbles PM inclus à réconcilier')
for i,(sx,sy) in enumerate([(1,-1),(1,1),(-1,1),(-1,-1)],1):
    route('PDB_ESC_'+str(i),'F02-PROPULSION-DC',[[120+sx*30,sy*22,-40],[sx*84,sy*72,-12],[sx*108,sy*108,25],[sx*178,sy*178,30]],7,35,None,2,'extension/adaptateur et fils OEM à séparer')
    route('ESC_PHASES_'+str(i),'F03-PHASES-MOTEURS',[[sx*185,sy*185,30],[sx*211,sy*211,33],[sx*230,sy*230,38]],7,35,None,3,'fils kit inclus à réconcilier')
    route('FCU_ESC_'+str(i),'F04-COMMANDE-ESC',[[60,sy*24,-60],[sx*88,sy*90,-32],[sx*128,sy*128,24],[sx*175,sy*175,25]],2.8,14,.129,2,'fils kit inclus ou adaptation à distinguer')
for name,y,w,n in [('POWER1',-20,'W06',4),('POWER2',-8,'W32',4),('CAN1',5,'W31',3)]:
    route('PM_'+name,'F06-PM-FCU',[[-116,y-62,-2],[-94,y-35,-28],[-76,y,-58],[-65,y,-60]],3.4,17,.129,n,'faisceau PM et séparateur à réconcilier',[w])
route('PDB_CA01','F08-CA01-ENTREE',[[120,-40,-40],[-32,-65,-28],[-75,-55,-62],ca('J103')],6.8,34,2.08,2)
route('CA01_JETSON','F09-JETSON-ENERGIE',[ca('J104'),[-75,4,-81],[-86,16,-67],[-66,20,-60]],6.8,34,2.08,2)
# Airy : tronc commun OEM et branches distinctes, jamais trois cordons complets.
route('AIRY_TRONC','F10-AIRY-COMMUN',[[-45,-38,-162],[-78,-76,-161],[-103,-83,-115],[-85,-78,-79]],8,80,None,None,'cordon OEM commun : MPN à sélectionner')
route('AIRY_12V','F10-AIRY-COMMUN',[[-85,-78,-79],[-68,-52,-89],ca('J201')],3.8,19,.52,2,'branche du cordon commun',['W10'])
route('AIRY_ETH','F10-AIRY-COMMUN',[[-85,-78,-79],[-93,-54,-54],[-66,-25,-55]],6,60,None,None,'branche du cordon commun',['W15'])
route('AIRY_TEMPS','F10-AIRY-COMMUN',[[-85,-78,-79],[-49,-61,-95],[42,-54,-94],[74,-32,-88],ca('J504')],3,15,.129,3,'branche du cordon commun',['W23'])
route('CA01_UART_RF','F12-RADIO-UART',[ca('J402'),[-16,-53,-86],[-53,-61,-65],[-63,-31,-60]],3,15,.129,3)
for i,(x,y) in enumerate([(-120,72),(120,-72)],1):
    route('COAX_RF_'+str(i),'F13-ANTENNES-RF',[[-46,-19.5,-82],[-80,(-55 if i==1 else 55),-86],[x,y,-65]],2.5,25,None,None,'coaxial radio livré à confirmer')
route('USB3_CAMERA','F16-USB-CAMERA',[[63,10,-57],[109,39,-74],[130,52,-113],[102,20,-117],[92,10,-107]],6,60,None,None)
route('M8_CAMERA','F18-M8-CAMERA-COMMUN',[ca('J502'),[56,-57,-86],[104,-57,-108],[110,-31,-126],[90,-15,-108]],5.5,55,.205,6,'hypothèse 6 fils physiques, 4 utiles')
route('GNSS_CAN2','F21-GNSS-CAN',[[-63,24,-60],[-91,56,-47],[-85,112,23],[-45,164,111],[8,218,185]],3.4,17,.129,4)
for name,j,y in [('PPS','J505',25),('GPRMC','J506',13),('REF3V3','J509',1)]:
    route('ORIN_'+name,'F24-TEMPS-ORIN',[ca(j),[76,y,-88],[86,y,-66],[63,y,-55]],2.6,13,.129,2,'adaptateur dédié à concevoir')
route('FCU_TRIGGER','F33-TRIGGER-FCU',[ca('J507'),[24,-55,-86],[58,-51,-69],[63,-21,-60]],2.6,13,.129,2)
route('FCU_CAPTURE','F35-CAPTURE-FCU',[ca('J508'),[79,20,-87],[87,30,-67],[63,32,-60]],2.6,13,.129,2)
route('GNSS_PPS_GPRMC','F36-GNSS-TEMPS',[ca('J503'),[11,-54,-91],[-78,-65,-83],[-100,91,3],[-58,162,117],[6,218,185]],3,15,.129,3)
if not RECIPE.exists():
    write(RECIPE,{'date':'2026-10-03','statut':'À valider','repere':'mm, repère global CAO historique',
        'configuration':'Drone_Cartographe_Systeme_Candidat','routes':routes,
        'non_routes':['F20 refroidissement : kit dans STEP, câble OEM à inventorier',
                      'F25 accessoires vol : matériel à identifier',
                      'F-LED-KIT : fils/ports/chaînage OEM à identifier'],
        'limites':['Aucune fixation mécanique nouvelle définie par ces routes.',
                   'Coordonnées de sortie CA01 : points de réservation à Z=-81, pas centres de contacts.',
                   'Sorties OEM des équipements : points d’étude non cotés.',
                   'Une courbe filtrée ou un solide valide ne ferme pas le rayon minimal fournisseur.']})
recipe=json.loads(RECIPE.read_text(encoding='utf-8'));routes=recipe['routes']

def rounded(points,desired):
    pts=[A.Vector(*v) for v in points];edges=[];radii=[];last=pts[0]
    for i in range(1,len(pts)-1):
        p=pts[i];a=pts[i-1]-p;c=pts[i+1]-p
        la,lc=a.Length,c.Length;a.normalize();c.normalize()
        angle=math.acos(max(-1,min(1,a.dot(c))))
        if angle<1e-5:raise ValueError('Rebroussement dans route')
        if abs(angle-math.pi)<1e-5:continue
        t=min(desired/math.tan(angle/2),la*.44,lc*.44)
        rad=t*math.tan(angle/2);direction=a+c;direction.normalize()
        center=p+direction*(rad/math.sin(angle/2))
        start=p+a*t;end=p+c*t;mid=p-center;mid.normalize();mid=center+mid*rad
        if (start-last).Length>1e-7:edges.append(Part.makeLine(last,start))
        edges.append(Part.Arc(start,mid,end).toShape());last=end;radii.append(rad)
    if (pts[-1]-last).Length>1e-7:edges.append(Part.makeLine(last,pts[-1]))
    return Part.Wire(edges),radii

d,harness=new('SA08_Faisceau_Systeme_Candidat');cable_rows=[];references=[]
save(d,'sous_assemblages')
for row in routes:
    name='EQ_Route_'+row['id']+'_Systeme_Candidat';dd,rr=new(name)
    points=row['points_mm'];wire,radii=rounded(points,row['rayon_reservation_mm'])
    path=dd.addObject('Part::Feature','CheminArrondi');rr.addObject(path);path.Shape=wire
    path.addProperty('App::PropertyVectorList','PointsEtude');path.PointsEtude=[A.Vector(*p) for p in points]
    profile=dd.addObject('Part::Feature','SectionEnvelope');rr.addObject(profile)
    tangent=wire.Edges[0].tangentAt(wire.Edges[0].FirstParameter)
    profile.Shape=Part.Wire(Part.makeCircle(row['diametre_enveloppe_mm']/2,A.Vector(*points[0]),tangent))
    sw=dd.addObject('Part::Sweep','ReservationCordon');rr.addObject(sw)
    sw.Sections=[profile];sw.Spine=(path,[]);sw.Solid=True;sw.Frenet=True
    path.Visibility=False;profile.Visibility=False
    meta(rr,'GroupeFaisceau',row['groupe']);meta(rr,'Liaisons',','.join(row['wxx']))
    meta(rr,'Limite',row['limite']);meta(rr,'Recette',rel(RECIPE));meta(rr,'ObjetFinal',sw.Name)
    p=save(dd,'pieces/commerce')
    valid=not sw.Shape.isNull() and sw.Shape.isValid()
    assert valid,'Sweep invalide : '+row['id']
    l=link(d,harness,row['id'],rr)
    copper=None
    if row['section_cuivre_par_fil_mm2'] is not None and row['nombre_fils'] is not None:
        copper=row['section_cuivre_par_fil_mm2']*row['nombre_fils']*wire.Length/1000*8.96
    result={**row,'fichier':rel(p),'objet':'Reference','sha256':sha(p),
            'longueur_route_mm':wire.Length,'rayons_mesures_mm':radii,
            'rayon_reservation_respecte':all(r>=row['rayon_reservation_mm']-1e-6 for r in radii),
            'masse_cuivre_hypothese_g':copper,'masse_cordon_g':None,
            'forme_valide':valid,'solides':len(sw.Shape.Solids)}
    cable_rows.append(result);references.append({'reference':name,'fichier':rel(p),'type':'cordon de réservation',
        'statut':'À valider','realisation_CAO':'Implémenté','sha256':sha(p)})
save(d,'sous_assemblages')

d,root=new('Drone_Cartographe_Systeme_Candidat');root.Label='Cartographe cible — implantation et faisceau À valider'
save(d,'assemblages')
for name in ['SA01_Chassis_Rehausse20','SA02A_Dock20Ah','SA05_Capteurs_Isoles']:
    link(d,root,name,load('sous_assemblages',name))
link(d,root,'Stack_Holybro_CA01',stack,(-63,-40,-65))
link(d,root,'Distribution_PM_PDB',distribution)
link(d,root,'GNSS_Helical',rtk)
link(d,root,'Faisceau_Systeme',harness)
meta(root,'Limite','Variante de revue inactive : supports absents, sorties câble nominales, trois groupes physiques non routés. Pas montage final figé.')
save(d,'assemblages')
for dd in list(A.listDocuments().values()):dd.recompute()
occurrences=[]
new_files=[]
for dd in A.listDocuments().values():
    if not dd.FileName:continue
    if rel(dd.FileName) not in sources:new_files.append({'fichier':rel(dd.FileName),'sha256':sha(dd.FileName)})
    if 'Systeme_Candidat' not in Path(dd.FileName).stem:continue
    for o in dd.Objects:
        if o.TypeId=='App::Link':occurrences.append({'assemblage':rel(dd.FileName),'occurrence':o.Name,
            'reference':Path(o.LinkedObject.Document.FileName).stem,'source_fichier':rel(o.LinkedObject.Document.FileName),
            'source_objet':o.LinkedObject.Name,'LinkTransform':o.LinkTransform,
            'matrice_placement':list(o.LinkPlacement.toMatrix().A)})
assert all(sha(ROOT/f)==h for f,h in sources.items()),'Source existante modifiée'
write(VER/'construction_systeme_faisceau_20261003.json',{'date':'2026-10-03','statut':'À valider',
      'conclusion':'préliminaire','configuration':rel(Path(d.FileName)),
      'version_FreeCAD':A.Version(),'script_sha256':sha(__file__),'recette_sha256':sha(RECIPE),
      'sources_preservees_sha256':sources,'nouveaux_fichiers':new_files,'occurrences':occurrences,
      'references_cordons':references,'routes':cable_rows,'non_routes':recipe['non_routes'],
      'fixations_completes':False,'faisceau_complet':False,'fabrication_ready':False,
      'limites':recipe['limites']})
print(json.dumps({'routes':len(cable_rows),'sources_preservees':len(sources),
                  'rayons_sous_reservation':[r['id'] for r in cable_rows if not r['rayon_reservation_respecte']],
                  'sortie':rel(Path(d.FileName))},ensure_ascii=False),flush=True)
