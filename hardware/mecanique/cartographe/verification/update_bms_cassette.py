"""Infrastructure CAO : BMS commercial et interface isolée, évolution en place.

Enveloppes d'étude explicites ; aucune instruction de modification des cellules.
"""
from etage_batterie_helpers import *
from update_raccordement_direct_batterie import box,cyl,cut,fuse,clear_features,route
import Part,json,math,hashlib

def final(d,r,o,rgb):
 meta(r,'ObjetFinal',o.Name);meta(r,'Etat','À valider');meta(r,'RealisationCAO','Implémenté')
 d.recompute()
 for f in d.Objects:
  if f.TypeId.startswith('Part::'):f.Visibility=f==o;f.ViewObject.Visibility=f==o;color(f,rgb)
 assert o.Shape.isValid() and o.Shape.Volume>0,d.Name
 save_native(d,d.FileName or MEC/'pieces/commerce'/(d.Name+'.FCStd'))

def envelope(name,dim,rgb,mpn,source,limit):
 p=MEC/'pieces/commerce'/(name+'.FCStd')
 r=load('pieces/commerce',name) if p.exists() else A.newDocument(name).addObject('App::Part','Reference')
 d=r.Document;clear_features(d);o=box(d,r,'Resultat',dim,(0,0,0))
 meta(r,'MPN',mpn);meta(r,'Source',source);meta(r,'Limite',limit);final(d,r,o,rgb)
 return r

def mobile(d,name,r,pos):
 o=d.getObject(name) or link(d,d.Ensemble,name,r,pos)
 rotation=o.LinkPlacement.Rotation
 o.setLink(r);o.LinkPlacement=A.Placement(A.Vector(*pos),rotation);meta(o,'Mobile','oui')
 o.setExpression('LinkPlacement.Base.x',str(pos[0])+' mm + Parametres.ExtractionX')
 return o

def wire_ref(name,points,rad,rgb,limit,curve=None):
 p=MEC/'pieces/commerce'/(name+'.FCStd')
 r=load('pieces/commerce',name) if p.exists() else A.newDocument(name).addObject('App::Part','Reference')
 d=r.Document;clear_features(d)
 pts=[A.Vector(*q) for q in points];path=d.addObject('Part::Feature','Chemin');r.addObject(path)
 path.Shape=curve or Part.makePolygon(pts);profile=d.addObject('Part::Feature','Section');r.addObject(profile)
 tangent=path.Shape.Edges[0].tangentAt(path.Shape.Edges[0].FirstParameter)
 profile.Shape=Part.Wire(Part.makeCircle(rad,pts[0],tangent))
 sw=d.addObject('Part::Sweep','Cordon');r.addObject(sw);sw.Sections=[profile];sw.Spine=(path,[]);sw.Solid=True;sw.Frenet=True
 meta(r,'Limite',limit);meta(r,'LongueurChemin_mm',path.Shape.Length);final(d,r,sw,rgb)
 return r

def main_historique():
 raise RuntimeError('Implantation arrière historique ; utiliser main() pour BMS supérieur. Retour par Git.')
 dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
 contacts=load('sous_assemblages','SA02_Contacts20Ah','Ensemble').Document
 if not hasattr(dock.Ensemble,'BMSIntegre'):
  for name,arm in [('P39_SupportFixeContacts20Ah','Pied'),('P40_SupportMobileContacts20Ah','Bras')]:
   r=load('pieces/fabriquees',name);d=r.Document
   for o in d.Objects:
    if o.TypeId in ['Part::Box','Part::Cylinder','Part::Cone','Part::Feature'] and not o.Name.startswith(('TrouPiedM3','FraisureM3','TrouFondM3')):
     if o.TypeId=='Part::Box':o.setExpression('Placement.Base.x',None)
     shift_placement(o,'Placement',(-44,0,0))
     if o.TypeId=='Part::Box' and o.Name.startswith(arm):o.Length=float(o.Length)+44
   meta(r,'EvolutionBMS','Allonge additionnelle44mm ; ancragesOEM préservés, rigiditéÀvalider')
   for o in d.Objects:o.touch()
   d.recompute();save_native(d)
  for d,prefix in [(dock,'Conn_'),(contacts,'')]:
   for o in d.Objects:
    if o.TypeId!='App::Link' or (prefix and not o.Name.startswith(prefix)):continue
    key=o.Name[len(prefix):]
    if key.startswith(('Support','VisFond','EcrouSousFond','VisFraiseePied')):continue
    x=o.LinkPlacement.Base.x-44
    if getattr(o,'Mobile','non')=='oui':o.setExpression('LinkPlacement.Base.x',str(x)+' mm + Parametres.ExtractionX')
    else:shift_placement(o,'LinkPlacement',(-44,0,0))
   save_native(d)
  for o in dock.Objects:
   if o.TypeId=='App::Link' and (o.Name.startswith(('EntretoiseCuFixe','CosseFixe','RondelleBorneFixe','VisBorneFixe','VisProtectionFixe','RondelleProtectionFixe','EcrouProtectionFixe','VisCapFixe','EcrouCapFixe')) or o.Name in ['ProtectionFixeTE','CapotProtectionFixeTE']):shift_placement(o,'LinkPlacement',(-44,0,0))
   if o.TypeId=='App::Link' and o.Name.startswith(('CosseMobileDirecte','VisM5ContactMobile','RondelleM5ContactMobile')):
    x=o.LinkPlacement.Base.x-44;o.setExpression('LinkPlacement.Base.x',str(x)+' mm + Parametres.ExtractionX')
  meta(dock.Ensemble,'BMSIntegre','JBD-SP22S003 A01 100A candidat ; TE conservé recul additionnel44mm')
 # PCB maximale documentée, raccords et thermique ne sont pas inclus.
 bms=envelope('EQ_JBD_SP22S003_BMS',(130.5,65.5,12),(.12,.65,.32),'JBD-SP22S003 Li-ion A01 variante100A','https://cdn-files.myshopline.com/file/store/1720492677212/JBD-SP22S003-Li-ion-A01-2.pdf','PCB130±0.5×65±0.5×10±2mm ; enveloppe tolérancée, aucune cote de dissipateur/prises ajoutée. Ports géométriquesréservés ; courant100A nonqualifié danscassette. NTC/J2-J3/niveauTTL/borneP−ouC− etbridageàcontrôlerlot.')
 mobile(dock,'BMS_JBD',bms,(-239,-32.75,50))
 # Coffret native avec ouvertures de raccordement et dégagement des brasP40.
 for name in ['P43_ProtectionConducteurs20Ah','P44_CouvercleArriereConducteurs20Ah']:
  r=load('pieces/fabriquees',name);d=r.Document;clear_features(d)
  if name.startswith('P43'):
   body=box(d,r,'CoffretArriere',(142,76,53.5),(-248,-38,47))
   tools=[box(d,r,'VideInterieur',(138,72,53.5),(-246,-36,49)),box(d,r,'FenetreFils',(6,42,28),(-110,-21,68))]
   for i,z in enumerate([69.745,86.255]):tools.append(cyl(d,r,'PassageBorne'+str(i),7.1,6,(-251,21.6535,z),(1,0,0)))
   tools.append(box(d,r,'PassageSignauxTE',(6,19,27),(-251,-9.5,65)))
   # Le brasP40 reste la source, outil d'évidement de cette seule piècefabriquée.
   tool=d.addObject('Part::Feature','DegagementP40');r.addObject(tool);tool.Shape=dock.Conn_SupportMobile.Shape.copy();tools.append(tool)
   for obj in dock.Objects:
    if obj.TypeId=='App::Link' and obj.Name.startswith(('Cass_Capture','Cass_CapG10','Cass_VisCap','Cass_EcrouCap','Conn_HousingSocket','Conn_VisLogementMobile','Conn_EcrouM4Mobile','Conn_VisFondMobile')):
     b=obj.Shape.BoundBox
     tools.append(box(d,r,'Degagement_'+obj.Name,(b.XLength+1,b.YLength+1,b.ZLength+1),(b.XMin-.5,b.YMin-.5,b.ZMin-.5)))
   out=cut(d,r,'Resultat',body,tools)
  else:
   body=box(d,r,'Plaque',(142,76,2),(-248,-38,100.5));tools=[]
   for obj in dock.Objects:
    if obj.TypeId=='App::Link' and obj.Name.startswith(('Cass_CapG10','Cass_VisCap')):
     b=obj.Shape.BoundBox;tools.append(box(d,r,'Degagement_'+obj.Name,(b.XLength+1,b.YLength+1,b.ZLength+1),(b.XMin-.5,b.YMin-.5,b.ZMin-.5)))
   out=cut(d,r,'Resultat',body,tools)
  meta(r,'Limite','CoffretBMSmobile142×76 ; fixation/verrouillage/isolementthermiqueIPetvibrationÀvalider. AucuntrouPCBfabricantinventé ; pas dossierfabrication.')
  final(d,r,out,(.28,.34,.40))
 # Retirer l'ancien coffretbalance et ses fixations ; JSTreste à l'intérieur.
 for o in list(dock.Objects):
  if o.TypeId=='App::Link' and o.Name.startswith(('P51_','P52_','VisCapotEquilibrage','EcrouCapotEquilibrage')):dock.removeObject(o.Name)
 eq=dock.getObject('EQ_EquilibragePack20Ah_Reservation');b=eq.LinkedObject.Shape.BoundBox;pos=A.Vector(-172-b.XMin,-31-b.YMin,69-b.ZMin);eq.LinkPlacement=A.Placement(pos,A.Rotation());eq.setExpression('LinkPlacement.Base.x',str(pos.x)+' mm + Parametres.ExtractionX')
 # Appuiisolant1mm ; retenueaxiale/verticaleetmatériauthermiqueàvalider.
 p=MEC/'pieces/fabriquees/P58_AppuiIsolationBMS.FCStd'
 carrier=load('pieces/fabriquees','P58_AppuiIsolationBMS') if p.exists() else A.newDocument('P58_AppuiIsolationBMS').addObject('App::Part','Reference')
 dc=carrier.Document;clear_features(dc);out=box(dc,carrier,'Resultat',(130.5,65.5,1),(-239,-32.75,49));meta(carrier,'Limite','AppuiisolantG10candidat1mm entrePCB etfond ; maintienpositif,dissipation,matériau etfixationàvalider. Aucuntroucommercialinventé.');dc.FileName=str(p);final(dc,carrier,out,(.16,.46,.52));mobile(dock,'AppuiIsolationBMS',carrier,(0,0,0))
 # Routagebrut négatif versBMS puisP−protégé versTE ; positif continu via borneB+.
 paths={'Plus':[(-99,5,82),(-230.2548,11.1535,69.745)],'Moins':[(-99,-5,82),(-117,-5,82),(-117,-18,71),(-128,-18,66)]}
 for pol,pts in paths.items():
  r=wire_ref('EQ_LeadPack8AWG_'+pol+'20A',pts,2.5,(.88,.12,.1) if pol=='Plus' else (.14,.15,.18),'AWG8 usine versTEpositif ouB−BMS ; pointsentréeBMSréservés noncotésfabricant. PositifR50,150mmusinemoinsterminaison11mmétude, coupe/rayon/tolérancesàvaliderlot. AucunXT90, aucuneinterventioncellules.',route(pts[0],pts[-1]) if pol=='Plus' else None)
  mobile(dock,r.Document.Name,r,(0,0,0))
 r=wire_ref('EQ_BMS_PMoins_TE20A',[(-218,-18,66),(-218,-18,86.255),(-230.2548,11.1535,86.255)],2.5,(.12,.13,.17),'SortieprotégéeP−/C− commune versTE40, jamaisB−brut. PointsportBMS/rayoncourbure etborneàvaliderlot.')
 mobile(dock,r.Document.Name,r,(0,0,0))
 # Noticep14 : seules bornesbulk B− etC− ; positifBMS viaBC22/B6 interne.
 # Aucun piquagepositif ni borneB+puissance supplémentaire ne sont requis.
 if dock.getObject('EQ_BMS_BPlus_Liaison20A'):dock.removeObject('EQ_BMS_BPlus_Liaison20A')
 r=wire_ref('EQ_BoucleEquilibragePack20Ah_Reservation',[(-99,18,90.5),(-116,18,90.5),(-116,-28,90.5),(-155,-28,77)],1.75,(.9,.63,.13),'JST7pack versfaisceauB0..B6 BMS interne uniquement ; adaptation6Sauconnecteur22Ssuivantnoticefabricant àvérifier, pasconnexionautomatique7premièrescavités.')
 mobile(dock,r.Document.Name,r,(0,0,0))
 # Contacts #20 placés sur axes du STEPfabricant, cavitésnumérotéesàvérifier.
 axes=[(-6.6675,68.094),(-6.6675,74.698),(-6.6675,81.302),(-6.6675,87.906),(-4.7625,71.396)]
 signals=['GND_ISO_BRAW','TX_BMS','RX_BMS','PRES1','PRES2'];pins=['1650161-1','1650155-1','1650155-1','1650162-2','1650162-2']
 for side in ['Pin','Socket']:
  for i,((y,z),signal) in enumerate(zip(axes,signals)):
   mpn=pins[i] if side=='Pin' else '1648325-1';name='EQ_TE_'+mpn.replace('-','_')+'_Signal20'
   p=MEC/'pieces/commerce'/(name+'.FCStd');r=load('pieces/commerce',name) if p.exists() else A.newDocument(name).addObject('App::Part','Reference');d=r.Document
   if not p.exists():
    body=cyl(d,r,'CorpsEtude',.30 if side=='Pin' else .50,25,(0,0,0),(1,0,0))
    out=cut(d,r,'Resultat',body,[cyl(d,r,'DouilleEtude',.36,10,(0,0,0),(1,0,0))]) if side=='Socket' else body
    meta(r,'MPN',mpn);meta(r,'Source','TE_ELCON_Catalogue.pdf /114-13206F');meta(r,'Limite','Contactcommercial#20 enveloppegéométriqueprovisoireL25 ; dimensionscomplètes/sertissageAWG24–20/cavitésnumérotées etséquenceàvalider, nepasfabriquercecontact.');final(d,r,out,(.86,.70,.25))
   if side=='Pin':d.CorpsEtude.Radius=.3;save_native(d)
   pos=(-290,y,z) if side=='Pin' else (-274,y,z)
   o=dock.getObject('Conn_Signal'+side+'_'+signal) or link(dock,dock.Ensemble,'Conn_Signal'+side+'_'+signal,r,pos)
   if side=='Socket':mobile(dock,o.Name,r,pos)
   meta(o,'Fonction',signal);meta(o,'Cavite','Affectationcandidate suraxeSTEP ; numérotationetvueduplanàvalider')
   if side=='Pin':o.LinkPlacement=A.Placement(A.Vector(*pos),A.Rotation())
   co=contacts.getObject('Signal'+side+'_'+signal) or link(contacts,contacts.Ensemble,'Signal'+side+'_'+signal,r,pos)
   co.setLink(r);co.LinkPlacement=A.Placement(A.Vector(*pos),A.Rotation());meta(co,'Fonction',signal);meta(co,'Mobile','oui' if side=='Socket' else 'non');meta(co,'Cavite','Numérotationcandidate nonconfirmée')
 r=wire_ref('EQ_BouclePresenceTE20A',[(-247,-6.6675,87.906),(-242,-6.6675,87.906),(-242,-4.7625,71.396),(-247,-4.7625,71.396)],.5,(.64,.26,.79),'Bouclepassiveentre2contactsTEpostmate, indépendanteB−brut. CôtéfixeNC ; géométrie/terminaisons/rayon/cavitésàvalider.')
 mobile(dock,r.Document.Name,r,(0,0,0))
 r=wire_ref('EQ_BMS_UART_TE20A',[(-172,-14,66),(-172,-14,78),(-240,0,78)],1.4,(.63,.23,.77),'UARTTX/RX/GNDbrut verscontactsTE5signaux ;5voiesdontboucleprésencepassiveindépendante. VDDJBDNC. PointJ2réservé, niveauTTLàvalider ; décodageJetsonPlanifié.')
 mobile(dock,r.Document.Name,r,(0,0,0))
 # Reprendre les deux routes fixes conservées vers le JETI inférieur.
 for i,(pol,z,yend) in enumerate([('Plus',69.745,-115),('Moins',86.255,-99)]):
  src=dock.getObject('EQ_CordonFixe8AWG_'+pol+'20A').LinkedObject.Document
  start=A.Vector(-305.9,-5.2465,z);p=A.Vector(-305.9,yend+50,z);q=p+A.Vector(50,-50,0)
  arc=Part.Arc(p,p+A.Vector(50*(1-math.cos(math.pi/4)),-50*math.sin(math.pi/4),0),q).toShape()
  s=route(tuple(q),(-40,yend,-16.5),lead_fraction=0);src.Chemin.Shape=Part.Wire([Part.makeLine(start,p),arc]+s.Edges)
  src.Section.Shape=Part.Wire(Part.makeCircle(2.5,start,A.Vector(0,-1,0)));src.Cordon.Spine=(src.Chemin,[]);src.recompute();save_native(src)
 # Interface USB↔TTL réellement isolée : enveloppeinstalléeconservatrice, pas coteOEM.
 iso=envelope('EQ_Waveshare15817_UART_Isole',(90,80,26),(.49,.27,.74),'Waveshare USB TO RS232/485/TTL 15817','https://files.waveshare.com/wiki/USB-TO-RS232-485-TTL/manual/USB_TO_RS232_485_TTL_-user-manual-en.pdf','Réservationinstallée90×80×26mm, dimensionsnonconfirmées fabricant. Manueldata+DC/DCisolés ; TTL3.3VàcontrôlerJBD. VDD/5VisolésNC, GND_ISO=B−brut seulement. USBavioniqueavalJETI ; pas parserPX4.')
 dist=load('sous_assemblages','SA07_Distribution_Systeme_Candidat').Document
 o=dist.getObject('InterfaceBMSIsolee') or link(dist,dist.Reference,'InterfaceBMSIsolee',iso,(-235,-140,-55));o.LinkPlacement=A.Placement(A.Vector(-235,-140,-55),A.Rotation())
 meta(dist.Reference,'DiagnosticBMS','USB↔TTLisolé, réservationcommerciale ; fixationmodule/ports/retoursisolésÀvalider')
 meta(dock.Ensemble,'Limite','BMScommercialmobile, coffretélargi142×76sanshauteuradditionnelle ; TE+44mm. CotesPCBtolérancées maisprises/raccordsenréservation, fixationthermiqueetlottousÀvalider. Chargecommuneprotégée, VDDNC, mesuresdiagnosticlectureseule.')
 save_native(dock);save_native(dist);save_native(contacts)
 cassette=load('sous_assemblages','SA02_Cassette20Ah_Coulissante').Document
 if cassette.getObject('EQ_BMS_BPlus_Liaison20A'):cassette.removeObject('EQ_BMS_BPlus_Liaison20A')
 for src in dock.Objects:
  if src.TypeId=='App::Link' and (src.Name.startswith(('BMS_','P43_','P44_','EQ_BMS_','EQ_LeadPack','EQ_BoucleEquilibrage')) or src.Name=='AppuiIsolationBMS'):
   o=cassette.getObject(src.Name) or link(cassette,cassette.Reference,src.Name,src.LinkedObject)
   o.setLink(src.LinkedObject);o.LinkPlacement=src.LinkPlacement;meta(o,'Mobile','oui')
 meta(cassette.Reference,'ConfigurationBMS','Cassettecommerciale JBD +coffret142×76 ; montagenatifréutilisédansdock, qualificationÀvalider')
 save_native(cassette)
 integration=load('assemblages','Integration_Stack_Revue_20261003','IntegrationRevue').Document
 meta(integration.IntegrationRevue,'Configuration','CassetteBMSJBD100A/TE5signaux ; JETI/PM08/PDB+isolationétageinférieur, faisceauSA08courant')
 save_native(integration)
 print('BMS intégré en place ; contrôles géométriques indépendants à exécuter')

def main():
 from update_bms_dessus import main as update
 update()

if __name__=='__main__':main()
