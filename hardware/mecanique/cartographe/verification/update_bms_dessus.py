"""Infrastructure CAO : BMS au-dessus du pack, rehausse et connecteur rapproché."""
from update_bms_cassette import final,mobile,wire_ref
from etage_batterie_helpers import *
from update_raccordement_direct_batterie import box,cyl,cut,fuse,clear_features,route,bb
import Part,math,json

def main():
 top=load('assemblages','Integration_Stack_Revue_20261003','IntegrationRevue').Document
 dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
 contacts=load('sous_assemblages','SA02_Contacts20Ah','Ensemble').Document
 chassis=load('sous_assemblages','SA01_Chassis_Stack_Revue_20261003','Ensemble').Document
 dist=load('sous_assemblages','SA07_Distribution_Systeme_Candidat').Document
 p=VER/'implantation_bms_dessus.json'
 if not p.exists():
  before=dict(batterie_et_energie=bb(Part.makeCompound([dock.Ensemble.Shape,dist.Reference.Shape])),cassette_mobile=bb(Part.makeCompound([o.Shape for o in dock.Objects if o.TypeId=='App::Link' and getattr(o,'Mobile','non')=='oui'])),integration_locale=bb(top.IntegrationRevue.Shape))
 else:before=json.loads(p.read_text(encoding='utf-8'))['bbox_avant_mm']
 # Placement cible absolu : un rejeu ne rallonge ni les supports ni les colonnes.
 dx=-189-dock.Conn_HousingPin.LinkPlacement.Base.x
 if abs(dx)>1e-6:
  for name,arm in [('P39_SupportFixeContacts20Ah','Pied'),('P40_SupportMobileContacts20Ah','Bras')]:
   r=load('pieces/fabriquees',name);d=r.Document
   for o in d.Objects:
    if o.TypeId in ['Part::Box','Part::Cylinder','Part::Cone','Part::Feature'] and not o.Name.startswith(('TrouPiedM3','FraisureM3','TrouFondM3')):
     if o.TypeId=='Part::Box':o.setExpression('Placement.Base.x',None)
     shift_placement(o,'Placement',(dx,0,0))
     if o.TypeId=='Part::Box' and o.Name.startswith(arm):o.Length=float(o.Length)-dx
   meta(r,'EvolutionBMS','Connecteur rapproché, ancrages conservés ; rigidité À valider')
   for o in d.Objects:o.touch()
   save_native(d)
  for d,prefix in [(dock,'Conn_'),(contacts,'')]:
   for o in d.Objects:
    if o.TypeId!='App::Link' or (prefix and not o.Name.startswith(prefix)):continue
    key=o.Name[len(prefix):]
    if key.startswith(('Support','VisFond','EcrouSousFond','VisFraiseePied')):continue
    pos=list(o.LinkPlacement.Base);pos[0]+=dx
    if getattr(o,'Mobile','non')=='oui':mobile(d,o.Name,o.LinkedObject,pos)
    else:shift_placement(o,'LinkPlacement',(dx,0,0))
  for o in dock.Objects:
   if o.TypeId!='App::Link':continue
   if o.Name.startswith(('EntretoiseCuFixe','CosseFixe','RondelleBorneFixe','VisBorneFixe','VisProtectionFixe','RondelleProtectionFixe','EcrouProtectionFixe','VisCapFixe','EcrouCapFixe')) or o.Name in ['ProtectionFixeTE','CapotProtectionFixeTE']:shift_placement(o,'LinkPlacement',(dx,0,0))
   if o.Name.startswith(('CosseMobileDirecte','VisM5ContactMobile','RondelleM5ContactMobile')):
    pos=list(o.LinkPlacement.Base);pos[0]+=dx;mobile(dock,o.Name,o.LinkedObject,pos)
 # P37 garde son arbre et ses taraudages paramétriques. L'OEM plateau est déplacé.
 col=load('pieces/fabriquees','P37_Entretoise70_6061_M3');col.Document.Parametres.set(col.Document.Parametres.getCellFromAlias('Longueur'),'95 mm')
 meta(col,'LongueurCourante','95 mm, ancien nom de fichier conservé ; rigidité/vibration À valider');save_native(col.Document)
 # Les expressions du châssis commandent plateau et fixations ensemble.
 chassis.Parametres.set(chassis.Parametres.getCellFromAlias('Rehausse'),'45 mm')
 chassis.recompute()
 meta(chassis.Ensemble,'RehausseBMS','Colonnes P37 95 mm ; plateau supérieur Z128..130, +25 mm')
 save_native(chassis)
 mobile(dock,'BMS_JBD',dock.BMS_JBD.LinkedObject,(-65.25,-32.75,107))
 # Coffret supérieur solidaire de la cassette, quatre pieds sur les capots G10.
 r=load('pieces/fabriquees','P43_ProtectionConducteurs20Ah');d=r.Document;clear_features(d)
 body=box(d,r,'CoffretDessus',(170,76,19),(-99,-38,104))
 tools=[box(d,r,'VideInterieur',(166,72,19),(-97,-36,106)),box(d,r,'PassagePuissance',(32,30,16),(-102,-27,103)),box(d,r,'PassageDonnees',(32,25,16),(-102,6,103))]
 shell=cut(d,r,'CoffretEvide',body,tools)
 feet=[box(d,r,'Pied_'+str(i),(10,5,4),(x,y,102)) for i,(x,y) in enumerate([(-65,-38),(55,-38),(-65,33),(55,33)])]
 # Protection courte des cosses sous l'étage BMS, ouverte vers le TE.
 rear=box(d,r,'ProtectionCosses',(78,46,42),(-180,-15,62))
 rear_tools=[box(d,r,'VideCosses',(81,42,38),(-182,-13,64)),box(d,r,'SortieFils',(5,34,30),(-104,-11,65)),box(d,r,'RemonteeFils',(34,30,9),(-142,-12,100))]
 rear_shell=cut(d,r,'ProtectionCossesEvidee',rear,rear_tools)
 bridge=box(d,r,'LiaisonEtages',(11,46,4),(-106,-15,102))
 bridge_out=cut(d,r,'LiaisonEtagesEvidee',bridge,[box(d,r,'VideLiaison',(11,32,5),(-107,-12,102))])
 out=fuse(d,r,'Resultat',[shell,rear_shell,bridge_out]+feet)
 meta(r,'Limite','Logement supérieur 170×76 et protection courte des cosses ; appuis sur capture G10, montage solidaire cassette. Fixation/verrouillage/ventilation/touchsafe/thermique et vibration À valider, pas trous OEM inventés.')
 final(d,r,out,(.28,.34,.40))
 r=load('pieces/fabriquees','P44_CouvercleArriereConducteurs20Ah');d=r.Document;clear_features(d)
 out=box(d,r,'Resultat',(170,76,2),(-99,-38,123));meta(r,'Limite','Capot supérieur Z123..125 ; retenue positive et ventilation À valider');final(d,r,out,(.28,.34,.40))
 r=load('pieces/fabriquees','P58_AppuiIsolationBMS');d=r.Document;clear_features(d)
 out=box(d,r,'Resultat',(130.5,65.5,1),(-65.25,-32.75,106));meta(r,'Limite','Appui G10 1 mm sur fond du coffret supérieur ; maintien PCB et dissipation À valider');final(d,r,out,(.16,.46,.52))
 mobile(dock,'AppuiIsolationBMS',r,(0,0,0))
 # Points de ports réservés hors volume du PCB ; aucun bornier OEM fictif.
 paths=[('EQ_LeadPack8AWG_Plus20A',[(-99,5,82),(-156.2548,11.1535,69.745)],2.5,(.88,.12,.1),True),
 ('EQ_LeadPack8AWG_Moins20A',[(-99,-5,82),(-117,-5,82),(-117,-20,112),(-74,-20,112)],2.5,(.14,.15,.18),False),
 ('EQ_BMS_PMoins_TE20A',[(-74,-6,112),(-117,-6,112),(-117,-6,104),(-130,11.1535,86.255),(-156.2548,11.1535,86.255)],2.5,(.12,.13,.17),False),
 ('EQ_BoucleEquilibragePack20Ah_Reservation',[(-99,18,90.5),(-117,18,90.5),(-117,22,115),(-85,22,115)],1.75,(.9,.63,.13),False),
 ('EQ_BMS_UART_TE20A',[(-74,12,115),(-135,12,115),(-135,-25,115),(-135,-25,78),(-135,0,78),(-166,0,78)],1.4,(.63,.23,.77),False),
 ('EQ_BouclePresenceTE20A',[(-173,-6.6675,87.906),(-168,-6.6675,87.906),(-168,-4.7625,71.396),(-173,-4.7625,71.396)],.5,(.64,.26,.79),False)]
 for name,pts,rad,rgb,curved in paths:
  r=wire_ref(name,pts,rad,rgb,'Implantation supérieure : ports/terminaisons réservés, coupe et rayons À valider. B+ direct TE, B− brut vers BMS, C− protégé vers TE ; aucun pont vers masse avionique.',route(pts[0],pts[-1]) if curved else None)
  mobile(dock,name,r,(0,0,0))
 eq=dock.EQ_EquilibragePack20Ah_Reservation;b=eq.LinkedObject.Shape.BoundBox
 mobile(dock,eq.Name,eq.LinkedObject,(-94-b.XMin,18-b.YMin,108-b.ZMin))
 # Dégagements locaux des interfaces réelles, avec jeu d'étude0,5mm.
 # Chaque outil reste un primitif natif ; aucune collision n'est masquée par une exception.
 dock.recompute()
 rr=load('pieces/fabriquees','P43_ProtectionConducteurs20Ah');dd=rr.Document;original=dd.getObject(rr.ObjetFinal);tools=[]
 for name in ['Cass_Capture','Conn_SupportMobile','CosseMobileDirecte0','CosseMobileDirecte1','EQ_LeadPack8AWG_Moins20A','EQ_BoucleEquilibragePack20Ah_Reservation','EQ_BMS_UART_TE20A']:
  obj=dock.getObject(name);hit=original.Shape.common(obj.Shape)
  if hit.Volume>1e-6:
   b=hit.BoundBox;tools.append(box(dd,rr,'Degagement_'+name,(b.XLength+1,b.YLength+1,b.ZLength+1),(b.XMin-.5,b.YMin-.5,b.ZMin-.5)))
 if tools:final(dd,rr,cut(dd,rr,'ResultatDegage',original,tools),(.28,.34,.40))
 for pol,z,yend in [('Plus',69.745,-115),('Moins',86.255,-99)]:
  src=dock.getObject('EQ_CordonFixe8AWG_'+pol+'20A').LinkedObject.Document
  bend_y=-99 if pol=='Plus' else yend
  start=A.Vector(-231.9,-5.2465,z);p0=A.Vector(-231.9,bend_y+50,z);q=p0+A.Vector(50,-50,0)
  arc=Part.Arc(p0,p0+A.Vector(50*(1-math.cos(math.pi/4)),-50*math.sin(math.pi/4),0),q).toShape()
  src.Chemin.Shape=Part.Wire([Part.makeLine(start,p0),arc]+route(tuple(q),(-40,yend,-16.5),lead_fraction=0).Edges)
  src.Section.Shape=Part.Wire(Part.makeCircle(2.5,start,A.Vector(0,-1,0)));src.Cordon.Spine=(src.Chemin,[]);save_native(src)
 meta(dock.Ensemble,'BMSIntegre','BMS au-dessus du pack ; plateau +25 mm ; TE recul total52 mm')
 meta(dock.Ensemble,'Limite','Implantation supérieure, PCB tolérancé ; ports/fixations/thermique À valider')
 save_native(dock);save_native(contacts)
 cassette=load('sous_assemblages','SA02_Cassette20Ah_Coulissante').Document
 for src in dock.Objects:
  if src.TypeId=='App::Link' and getattr(src,'Mobile','non')=='oui':
   name=src.Name[5:] if src.Name.startswith('Cass_') else src.Name
   o=cassette.getObject(name) or cassette.getObject(src.Name)
   if o is None:continue
   o.setLink(src.LinkedObject);o.LinkPlacement=src.LinkPlacement;meta(o,'Mobile','oui')
 meta(cassette.Reference,'ConfigurationBMS','BMS au-dessus du pack sous plateau rehaussé, coffret supérieur et P58');save_native(cassette)
 meta(top.IntegrationRevue,'Configuration','BMS supérieur, colonnes95 mm, TE rapproché74 mm ; énergie inférieure et SA08');save_native(top)
 after=dict(batterie_et_energie=bb(Part.makeCompound([dock.Ensemble.Shape,dist.Reference.Shape])),cassette_mobile=bb(Part.makeCompound([o.Shape for o in dock.Objects if o.TypeId=='App::Link' and getattr(o,'Mobile','non')=='oui'])),integration_locale=bb(top.IntegrationRevue.Shape))
 comparisons={}
 for scope in before:
  a=[before[scope][i+3]-before[scope][i] for i in range(3)];b=[after[scope][i+3]-after[scope][i] for i in range(3)]
  comparisons[scope]=dict(dimensions_avant_mm=a,dimensions_apres_mm=b,volume_avant_mm3=math.prod(a),volume_apres_mm3=math.prod(b),variation_volume_pct=100*(math.prod(b)/math.prod(a)-1))
 proof=dict(date='2026-10-05',implantation='BMS au-dessus de la batterie',bbox_avant_mm=before,bbox_apres_mm=after,comparaison=comparisons,TE_avance_depuis_BMS_arriere_mm=74,TE_recul_total_mm=52,colonne_longueur_mm=95,plateau_rehausse_mm=25,qualification='À valider',controle_geometrique='controle_bms_cassette.json',limite='Comparaison géométrique, pas mesure de masse ni qualification physique')
 p.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(comparisons),flush=True)

if __name__=='__main__':main()
