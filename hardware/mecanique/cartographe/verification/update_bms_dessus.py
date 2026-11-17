"""Infrastructure FreeCAD : BMS supérieur et raccordement TE compact, natifs conservés."""
from garde_hierarchie_batterie import require_monolithic_layout
require_monolithic_layout('update_bms_dessus.py')
from pathlib import Path
import argparse, hashlib, json, math
import FreeCAD as A
import Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
SAVING=False;CHANGED=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bb(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def meta(o,k,v):
 if k not in o.PropertiesList:o.addProperty('App::PropertyString',k)
 setattr(o,k,str(v))
def load(folder,name,root='Reference'):
 p=MEC/folder/(name+'.FCStd');d=next((q for q in A.listDocuments().values() if q.FileName and Path(q.FileName)==p),None) or A.openDocument(str(p));return d.getObject(root)
def color(o,rgb):
 if SAVING:
  m=A.Material();m.DiffuseColor=rgb;o.ViewObject.ShapeAppearance=[m]
def changed(d):
 if d not in CHANGED:CHANGED.append(d)
def final(d,r,o,rgb,one_solid=True):
 meta(r,'ObjetFinal',o.Name);meta(r,'Etat','À valider');meta(r,'RealisationCAO','Implémenté')
 for q in d.Objects:
  if q.TypeId.startswith('Part::'):q.Visibility=q==o;color(q,rgb)
 d.recompute();assert o.Shape.isValid() and (not one_solid or len(o.Shape.Solids)==1),d.Name;o.Shape.check(True);changed(d)
def clear(d):
 for o in reversed(d.Objects):
  if o.TypeId.startswith(('Part::','PartDesign::')):d.removeObject(o.Name)
def box(d,r,n,dim,pos):
 o=d.addObject('Part::Box',n);r.addObject(o);o.Length,o.Width,o.Height=dim;o.Placement.Base=A.Vector(*pos);return o
def fuse(d,r,n,parts):
 if len(parts)==1:return parts[0]
 o=d.addObject('Part::MultiFuse',n);r.addObject(o);o.Shapes=parts;o.Refine=True
 for p in parts:p.Visibility=False
 return o
def cut(d,r,n,base,tools):
 o=d.addObject('Part::Cut',n);r.addObject(o);o.Base=base;o.Tool=fuse(d,r,n+'Outils',tools);o.Refine=True;base.Visibility=False;o.Tool.Visibility=False;return o
def shift(o,delta):
 p=o.Placement;p.Base+=delta;o.Placement=p
def set_alias(d,name,value):d.Parametres.set(d.Parametres.getCellFromAlias(name),str(value)+' mm')
def placement(o,pos,rot=None):
 rotation=rot if rot is not None else o.LinkPlacement.Rotation;o.LinkPlacement=A.Placement(A.Vector(*pos),rotation)
 if getattr(o,'Mobile','non')=='oui':o.setExpression('LinkPlacement.Base.x',str(pos[0])+' mm + Parametres.ExtractionX')
def source_rot(name):
 name=name.removeprefix('Conn_')
 if name in ['HousingSocket','ContactSocket39Plus','ContactSocket40Moins']:return A.Rotation(A.Vector(0,1,0),-90)
 if name.startswith(('VisLogementMobile','RondelleLargeMobile','RondelleM4Mobile','EcrouM4Mobile')):return A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0))
 if name.startswith(('VisFondMobile','VisFraiseePiedFixe')):return A.Rotation(A.Vector(0,0,1),A.Vector(0,0,-1))
 if name.startswith('EcrouSousFondMobile'):return A.Rotation(A.Vector(0,0,1),30)
 if name.startswith('VisM5ContactMobile'):return A.Rotation(A.Vector(0,0,1),A.Vector(-1,0,0))
 if name.startswith('RondelleM5ContactMobile'):return A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0))
 return None

def supports(delta):
 for name,panel,bottom,arm in [('P39_SupportFixeContacts20Ah',-172.,39.,'Pied'),('P40_SupportMobileContacts20Ah',-142.65,45.,'Bras')]:
  r=load('pieces/fabriquees',name);d=r.Document
  for o in d.Objects:
   if o.TypeId in ['Part::Box','Part::Cylinder','Part::Cone','Part::Feature'] and not o.Name.startswith(('TrouPiedM3','FraisureM3','TrouFondM3')):
    for expr,_ in list(o.ExpressionEngine):
     if expr.lstrip('.').startswith('Placement'):o.setExpression(expr,None)
    shift(o,delta)
  for i in range(2):
   montant=d.getObject('Montant'+str(i));montant.Placement.Base=A.Vector(panel,(-55.1535 if i==0 else 34.8465) if arm=='Pied' else (-43.1535 if i==0 else 22.8465),bottom);montant.Height=110.255-bottom
   foot=d.getObject(arm+str(i))
   if arm=='Pied':ys=(-55.1535,-43.) if i==0 else (34.8465,49.);end=-114.
   else:ys=(-43.1535,-29.) if i==0 else (22.8465,37.);end=-101.
   foot.Placement.Base=A.Vector(panel,ys[0],bottom);foot.Length=end-panel;foot.Width=ys[1]-ys[0];foot.Height=3
  set_alias(d,'PanelX',panel);set_alias(d,'CentreZ',90.255)
  meta(r,'EvolutionBMS','Raccord compact : bride déplacée, pieds/bras et montants rejoignent les ancrages existants ; rigidité/vibration À valider');final(d,r,d.Resultat,(.78,.62,.33))

def arc_wire(start,mid,end):return Part.Wire([Part.Arc(A.Vector(*start),A.Vector(*mid),A.Vector(*end)).toShape()])
def one_arc(p,q):
 p=A.Vector(*p);q=A.Vector(*q);u=A.Vector(0,p.y-q.y,p.z-q.z);D=u.Length;u.normalize();L=p.x-q.x;R=(L*L+D*D)/(2*D);theta=2*math.atan2(D,L);mid=q+A.Vector(R*math.sin(theta/2),0,0)+u*(R*(1-math.cos(theta/2)));return Part.Wire([Part.Arc(p,mid,q).toShape()])
def s_route(start,end,R=50.,lead_fraction=0):
 p=A.Vector(*start);q=A.Vector(*end);f=A.Vector(1 if q.x>p.x else -1,0,0);u=A.Vector(0,q.y-p.y,q.z-p.z);D=u.Length;u.normalize();theta=math.acos(1-D/(2*R));span=2*R*math.sin(theta);straight=(abs(p.x-q.x)-span)*lead_fraction;assert straight>=-1e-8;edges=[]
 if straight>1e-6:edges.append(Part.makeLine(p,p+f*straight));p+=f*straight
 p1=p+f*(R*math.sin(theta))+u*(R*(1-math.cos(theta)));edges.append(Part.Arc(p,p+f*(R*math.sin(theta/2))+u*(R*(1-math.cos(theta/2))),p1).toShape())
 p2=p1+f*(R*math.sin(theta))+u*(R*(1-math.cos(theta)));edges.append(Part.Arc(p1,p1+f*(R*(math.sin(theta)-math.sin(theta/2)))+u*(R*(math.cos(theta/2)-math.cos(theta))),p2).toShape())
 if (p2-q).Length>1e-6:edges.append(Part.makeLine(p2,q))
 return Part.Wire(edges)
def wire_ref(name,wire,radius,rgb,limit):
 r=load('pieces/commerce',name);d=r.Document;p=d.Chemin;section=d.Section;sw=d.Cordon;p.Shape=wire;start=wire.Edges[0].Vertexes[0].Point;section.Shape=Part.Wire(Part.makeCircle(radius,start,wire.Edges[0].tangentAt(wire.Edges[0].FirstParameter)));sw.Sections=[section];sw.Spine=(p,[]);sw.Solid=True;sw.Frenet=True;sw.touch();d.recompute();p.Visibility=False;section.Visibility=False;sw.Visibility=True;color(sw,rgb);sw.Shape.check(True);assert sw.Shape.isValid() and len(sw.Shape.Solids)==1,name;meta(r,'LongueurChemin_mm',wire.Length);meta(r,'Limite',limit);changed(d);return r

def protection(dock):
 r=load('pieces/fabriquees','P43_ProtectionConducteurs20Ah');d=r.Document;clear(d)
 body=box(d,r,'CoffretDessus',(170,76,19),(-99,-38,104));shell=cut(d,r,'CoffretEvide',body,[box(d,r,'VideInterieur',(166,72,19),(-97,-36,106)),box(d,r,'PassagePuissance',(32,30,16),(-102,-27,103)),box(d,r,'PassageDonnees',(32,25,16),(-102,6,103))])
 feet=[box(d,r,'Pied_'+str(i),(10,5,4),(x,y,102)) for i,(x,y) in enumerate([(-65,-38),(55,-38),(-65,33),(55,33)])]
 plus=box(d,r,'ProtectionCossePlus',(21.5,25.5,17),(-132.2548,-1.5,73.5));plus=cut(d,r,'ProtectionPlusEvidee',plus,[box(d,r,'VideCossePlus',(25.5,21.5,13),(-134.2548,.5,75.5))])
 minus=box(d,r,'ProtectionCosseMoins',(21.5,17,25.51),(-132.2548,7,90));minus=cut(d,r,'ProtectionMoinsEvidee',minus,[box(d,r,'VideCosseMoins',(25.5,13,21.51),(-134.2548,9,92))])
 stem=box(d,r,'AttacheLocaleMontant',(3,2,8.49),(-115,22,113.51));beam=box(d,r,'AttacheLocaleHaut',(19,2,2),(-115,22,119));result=fuse(d,r,'Resultat',[shell,plus,minus,stem,beam]+feet)
 # Dégagements natifs suivant les gaines réellement construites, avec jeu0.5mm.
 tools=[]
 for name,rad in [('EQ_BMS_UART_TE20A',1.9),('EQ_BoucleEquilibragePack20Ah_Reservation',2.25)]:
  src=dock.getObject(name).LinkedObject.Document;wire=src.Chemin.Shape.copy()
  path=d.addObject('Part::Feature','CheminDegagement_'+name);r.addObject(path);path.Shape=wire
  profile=d.addObject('Part::Feature','SectionDegagement_'+name);r.addObject(profile);profile.Shape=Part.Wire(Part.makeCircle(rad,wire.Edges[0].Vertexes[0].Point,wire.Edges[0].tangentAt(wire.Edges[0].FirstParameter)))
  sweep=d.addObject('Part::Sweep','DegagementGaine_'+name);r.addObject(sweep);sweep.Sections=[profile];sweep.Spine=(path,[]);sweep.Solid=True;sweep.Frenet=True;tools.append(sweep)
 result=cut(d,r,'ResultatDegage',result,tools)
 meta(r,'Limite','Protection locale des deux cosses, parois2mm et jeu étude0.5mm ; extrémités ouvertes aux raccords, attache au coffret supérieur. Tenue,touchsafe,retenue,thermique etlot À valider.');final(d,r,result,(.28,.34,.40))

def main(sauver=True):
 global SAVING
 SAVING=sauver;CHANGED.clear()
 if sauver:
  from etage_batterie_helpers import save_native
 proof_path=VER/'compactage_raccord_bms_te.json';proof=json.loads(proof_path.read_text(encoding='utf-8'));assert proof['reference_git']=='1ccbad81' and proof['avant']['nombre_sources']==147
 dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document;contacts=load('sous_assemblages','SA02_Contacts20Ah','Ensemble').Document;assert abs(dock.BMS_JBD.Shape.BoundBox.ZMin-107)<1e-6,'Implantation supérieure prérequise'
 delta=A.Vector(-149,-6.1535,90.255)-dock.Conn_HousingPin.LinkPlacement.Base;supports(delta)
 for d,prefix in [(dock,'Conn_'),(contacts,'')]:
  for o in d.Objects:
   if o.TypeId!='App::Link' or (prefix and not o.Name.startswith(prefix)):continue
   key=o.Name[len(prefix):]
   if key.startswith(('Support','VisFond','EcrouSousFond','VisFraiseePied')):
    rot=source_rot(o.Name)
    if rot is not None:placement(o,tuple(o.LinkPlacement.Base),rot)
    continue
   placement(o,tuple(o.LinkPlacement.Base+delta),source_rot(o.Name))
  changed(d)
 for o in dock.Objects:
  if o.TypeId!='App::Link':continue
  if o.Name.startswith(('CosseMobileDirecte','VisM5ContactMobile','RondelleM5ContactMobile','EntretoiseCuFixe','CosseFixe','RondelleBorneFixe','VisBorneFixe','VisProtectionFixe','RondelleProtectionFixe','EcrouProtectionFixe')):placement(o,tuple(o.LinkPlacement.Base+delta),source_rot(o.Name))
  if o.Name.startswith(('VisCapFixe','EcrouCapFixe')) or o.Name in ['ProtectionFixeTE','CapotProtectionFixeTE']:placement(o,tuple(o.LinkPlacement.Base+A.Vector(delta.x,delta.y,0)))
 placement(dock.CosseMobileDirecte0,(-130.2548,15.5,82),A.Rotation());placement(dock.CosseMobileDirecte1,(-130.2548,15.5,98.51),A.Rotation(A.Vector(1,0,0),-90))
 guard=load('pieces/fabriquees','P49_ProtectionFixeTE20Ah');gd=guard.Document
 for o in gd.Objects:
  if o.TypeId in ['Part::Box','Part::Cylinder','Part::Feature'] and o.Name.startswith(('Pont','Bras','Bride','PassageArc','FixationSupport','DegagementTeteSupport','TunnelBorne','SortieFil','VideTunnel','PassageEtage')):
   for expr,_ in list(o.ExpressionEngine):
    if expr.lstrip('.').startswith('Placement'):o.setExpression(expr,None)
   shift(o,A.Vector(0,0,delta.z))
 # Bras continus autour du dégagement des têtes de vis : corps retenu
 # par les brides, sans augmenter le haut du boîtier àZ121mm.
 for i,y in enumerate([-49.,41.]):
  arm=gd.getObject('Bras'+str(i));arm.Placement.Base=A.Vector(-191.,y,92.255)
  arm.Length=31.;arm.Width=8.;arm.Height=10.
 meta(guard,'EvolutionFixation','Bras8×10mm continus vers les brides ; pièceunique, tenue physique Àvalider')
 final(gd,guard,gd.getObject(guard.ObjetFinal),(.32,.35,.40))
 u_radius=math.hypot(15,7.5);raw=arc_wire((-99,-5,82),(-99-u_radius,-12.5,97),(-99,-20,112));raw=Part.Wire(raw.Edges+[Part.makeLine(A.Vector(-99,-20,112),A.Vector(-74,-20,112))])
 balance_radius=math.hypot(12.25,2);balance=arc_wire((-99,18,90.5),(-99-balance_radius,20,102.75),(-99,22,115));balance=Part.Wire(balance.Edges+[Part.makeLine(A.Vector(-99,22,115),A.Vector(-85,22,115))])
 a=A.Vector(-74,12,115);b=A.Vector(-107.8465,12,115);c=A.Vector(-118,1.8465,115);e=A.Vector(-118,-6.1535,107);f=A.Vector(-118,-6.1535,98.255);g=A.Vector(-126,-6.1535,90.255);rxy=10.1535;rt=math.sqrt(.5)
 uart=Part.Wire([Part.makeLine(a,b),Part.Arc(b,A.Vector(b.x-rxy*rt,1.8465+rxy*rt,115),c).toShape(),Part.Arc(c,A.Vector(-118,1.8465-8*rt,107+8*rt),e).toShape(),Part.makeLine(e,f),Part.Arc(f,A.Vector(-126+8*rt,-6.1535,98.255-8*rt),g).toShape()])
 wires=[('EQ_LeadPack8AWG_Plus20A',Part.Wire([Part.makeLine(A.Vector(-99,5,82),A.Vector(-116.2548,5,82))]),2.5,(.88,.12,.1)),('EQ_LeadPack8AWG_Moins20A',raw,2.5,(.14,.15,.18)),('EQ_BMS_PMoins_TE20A',one_arc((-74,-6,112),(-116.2548,15.5,109.01)),2.5,(.12,.13,.17)),('EQ_BoucleEquilibragePack20Ah_Reservation',balance,1.75,(.9,.63,.13)),('EQ_BMS_UART_TE20A',uart,1.4,(.63,.23,.77))]
 limit='Raccord compact : ports BMS réservés hors PCB, tangenteport non imposée ; gainescourbes, coupe/terminaisons/rayonslot/sertissage etretenue Àvalider. AucunB+supplémentaire : mesureBC22/B6interne.'
 for name,w,rad,rgb in wires:wire_ref(name,w,rad,rgb,limit);placement(dock.getObject(name),(0,0,0),A.Rotation())
 presence=dock.EQ_BouclePresenceTE20A.LinkedObject.Document;pw=presence.Chemin.Shape.copy();pw.translate(delta);wire_ref(presence.Name,pw,.5,(.64,.26,.79),'Bouclepassive postmate, contacts/cavités etrayons Àvalider')
 for pol,z,yend in [('Plus',82.,-115.),('Moins',98.51,-99.)]:
  bend_y=-130.
  start=A.Vector(-191.9,-11.4,z);p0=A.Vector(start.x,bend_y+50,z);q=p0+A.Vector(50,-50,0);rt=math.sqrt(.5)
  arc=Part.Arc(p0,p0+A.Vector(50*(1-rt),-50*rt,0),q).toShape();edges=[Part.makeLine(start,p0),arc]
  if pol=='Plus':edges+=s_route(tuple(q),(-40,yend,-16.5)).Edges
  else:
   # TroisquartsR50 et deuxdroites : descente monotone hors desbrasOEM.
   a=A.Vector(-140,bend_y,z);edges.append(Part.makeLine(q,a))
   end=A.Vector(-40,yend,-16.5);u=A.Vector(0,end.y-a.y,end.z-a.z);distance=u.Length;u.normalize();f=A.Vector(1,0,0)
   b=a+f*50+u*50;c=b+u*(distance-100);finish=c+f*50+u*50
   edges+=[Part.Arc(a,a+f*(50*rt)+u*(50*(1-rt)),b).toShape(),Part.makeLine(b,c),Part.Arc(c,c+f*(50*(1-rt))+u*(50*rt),finish).toShape()]
  wire=Part.Wire(edges);wire_ref('EQ_CordonFixe8AWG_'+pol+'20A',wire,2.5,(.88,.12,.1) if pol=='Plus' else (.12,.13,.17),'CordonsfixesR50 ; départ réel fûtscossesfixes, pointsJETI inchangés ; terminaisons/longueurs Àvalider')
 protection(dock)
 cassette=load('sous_assemblages','SA02_Cassette20Ah_Coulissante').Document
 for o in dock.Objects:
  if o.TypeId!='App::Link' or getattr(o,'Mobile','non')!='oui':continue
  name=o.Name[5:] if o.Name.startswith('Cass_') else o.Name;target=cassette.getObject(name) or cassette.getObject(o.Name)
  if target:target.setLink(o.LinkedObject);target.LinkPlacement=o.LinkPlacement;meta(target,'Mobile','oui')
 changed(cassette);meta(dock.Ensemble,'BMSIntegre','BMS au-dessus du pack ; raccord TE compact, positifaxial et cosse−X−90 ; plateau+25mm conservé');meta(dock.Ensemble,'Limite','Implantationcompacte ; portsBMS/sections/rayons/terminaisons/supports/touchsafe/thermique etlot Àvalider')
 for d in CHANGED:d.recompute()
 hits=[];checks=0;subjects=[dock.getObject(n) for n,_,_,_ in wires]+[dock.P43_ProtectionConducteurs20Ah,dock.CosseMobileDirecte0,dock.CosseMobileDirecte1,dock.EQ_CordonFixe8AWG_Plus20A,dock.EQ_CordonFixe8AWG_Moins20A]
 intended={frozenset(['EQ_LeadPack8AWG_Plus20A','CosseMobileDirecte0']),frozenset(['EQ_BMS_PMoins_TE20A','CosseMobileDirecte1']),frozenset(['EQ_BoucleEquilibragePack20Ah_Reservation','EQ_EquilibragePack20Ah_Reservation'])}
 for o in subjects:
  for q in dock.Objects:
   if q.TypeId!='App::Link' or not hasattr(q,'Shape') or q==o:continue
   if not o.Shape.BoundBox.intersect(q.Shape.BoundBox):continue
   checks+=1;vol=o.Shape.common(q.Shape).Volume
   if vol>1e-5:hits.append({'objet':o.Name,'autre':q.Name,'volume_mm3':vol,'interface_intentionnelle':frozenset([o.Name,q.Name]) in intended})
 route_metrics={n:{'longueur_mm':w.Length,'rayons_mm':[e.Curve.Radius for e in w.Edges if isinstance(e.Curve,Part.Circle)],'BOP_sain':True,'diametre_reservation_mm':2*rad} for n,w,rad,_ in wires}
 evidence={'recette_sha256':sha(__file__),'delta_TE_mm':[40,-6.1535,12.255],'routes':route_metrics,'intersections_locales':hits,'booléens_locaux':checks,'fichiers_modifies':[str(Path(d.FileName).relative_to(ROOT)).replace('\\','/') for d in CHANGED],'sources_avant_enregistrement_sha256':{str(Path(d.FileName).relative_to(ROOT)).replace('\\','/'):sha(d.FileName) for d in CHANGED},'limites':['Points/portsBMSréservés noncotésOEM','ArcbrutR16.77/balanceR12.41/UARTR8 nonqualifiés surlot','Positifcourt exigeadaptationlongueurusine150mm etsertissagequalifié','Efforts/fixations/touchsafe/thermique/extractioncontinue Àvalider']}
 proof['candidat']=evidence;proof['finalisation_correcte']=False;proof_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'routes':route_metrics,'intersections':hits,'fichiers':len(CHANGED),'sauver':sauver}),flush=True)
 if any(not h['interface_intentionnelle'] for h in hits):raise RuntimeError('Collisionslocales nonrésolues : relire compactage_raccord_bms_te.json')
 if sauver:
  for d in CHANGED:save_native(d)
  proof['apres']={'enregistrement_natif_effectue':True,'sources_sha256':{str(Path(d.FileName).relative_to(ROOT)).replace('\\','/'):sha(d.FileName) for d in CHANGED},'bbox_dock_mm':bb(dock.Ensemble.Shape),'bbox_cassette_mobile_mm':bb(Part.makeCompound([o.Shape for o in dock.Objects if o.TypeId=='App::Link' and getattr(o,'Mobile','non')=='oui'])),'routes':route_metrics,'poses_TE':{o.Name:{'base':list(o.LinkPlacement.Base),'rotation_quaternion':list(o.LinkPlacement.Rotation.Q)} for o in [dock.Conn_HousingPin,dock.Conn_HousingSocket,dock.CosseMobileDirecte0,dock.CosseMobileDirecte1]},'relecture_independante':'À valider'};proof_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return proof
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();main(not args.check)
