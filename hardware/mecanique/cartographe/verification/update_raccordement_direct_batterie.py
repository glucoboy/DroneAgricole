"""Évolution en place du dock : pack retourné, cosses90 et câbles directs R50.

Infrastructure CAO, pas instruction de fabrication ni qualification électrique.
"""
from etage_batterie_helpers import *
import Part, math, json, hashlib
SHIFT=82.0
changed=[]
def bb(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def box(d,r,n,dim,pos):
 o=d.addObject('Part::Box',n);r.addObject(o);o.Length,o.Width,o.Height=dim;o.Placement.Base=A.Vector(*pos);return o
def cyl(d,r,n,rad,L,pos,axis=(0,0,1)):
 o=d.addObject('Part::Cylinder',n);r.addObject(o);o.Radius=rad;o.Height=L;o.Placement=A.Placement(A.Vector(*pos),A.Rotation(A.Vector(0,0,1),A.Vector(*axis)));return o
def fuse(d,r,n,parts):
 if len(parts)==1:return parts[0]
 o=d.addObject('Part::MultiFuse',n);r.addObject(o);o.Shapes=parts;o.Refine=True
 for p in parts:p.Visibility=False
 return o
def cut(d,r,n,base,tools):
 tool=fuse(d,r,n+'Outils',tools);o=d.addObject('Part::Cut',n);r.addObject(o);o.Base=base;o.Tool=tool;o.Refine=True;base.Visibility=False;tool.Visibility=False;return o
def finish(d,r,out,rgb=(.32,.35,.40)):
 meta(r,'ObjetFinal',out.Name);meta(r,'Etat','À valider');meta(r,'RealisationCAO','Implémenté')
 for o in d.Objects:
  if o.TypeId.startswith('Part::'):o.Visibility=o==out;color(o,rgb)
 d.recompute();assert out.Shape.isValid() and len(out.Shape.Solids)==1,(d.Name,bb(out.Shape),len(out.Shape.Solids))
 changed.append(d)
def clear_features(d):
 for o in reversed(d.Objects):
  if o.TypeId.startswith(('Part::','PartDesign::')):d.removeObject(o.Name)
def route(start,end,lead_fraction=.5):
 p=A.Vector(*start);q=A.Vector(*end);f=A.Vector(1 if q.x>p.x else -1,0,0);u=A.Vector(0,q.y-p.y,q.z-p.z);D=u.Length;u.normalize();R=50.
 theta=math.acos(1-D/(2*R));span=2*R*math.sin(theta);straight=(abs(p.x-q.x)-span)*lead_fraction
 assert straight>=0
 edges=[]
 if straight>1e-6:edges.append(Part.makeLine(p,p+f*straight));p=p+f*straight
 mid=p+f*(R*math.sin(theta/2))+u*(R*(1-math.cos(theta/2)))
 p1=p+f*(R*math.sin(theta))+u*(R*(1-math.cos(theta)))
 edges.append(Part.Arc(p,mid,p1).toShape())
 mid2=p1+f*(R*(math.sin(theta)-math.sin(theta/2)))+u*(R*(math.cos(theta/2)-math.cos(theta)))
 p2=p1+f*(R*math.sin(theta))+u*(R*(1-math.cos(theta)))
 edges.append(Part.Arc(p1,mid2,p2).toShape())
 if (p2-q).Length>1e-6:edges.append(Part.makeLine(p2,q))
 return Part.Wire(edges)

def main():
 dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
 before=bb(dock.Ensemble.Shape);removed=[]
 # Les pièces natifs/catalogue retirées restent disponibles dans Git.
 obsolete=['Conducteur0','Conducteur1','CosseFrontal0','CosseFrontal1','P45_CouvercleLateralConducteurs20Ah','BootFrontal','PorteXT90','XT90Male','XT90FemellePack','EQ_Cordon10AWG_Plus_Dock20A','EQ_Cordon10AWG_Moins_Dock20A','SupportJETI','MainSwitchJETI','CommandeMagnetiqueJETI','RepriseFaisceauFixe','CollierRepriseGaines','EQ_FactoryJETI_IN_Plus20A','EQ_FactoryJETI_IN_Moins20A','VisPoigneeGaucheP43']
 prefixes=['VisM5Frontal','RondelleM5Frontal','EcrouBorneFront','VisCapRear','EcrouCapRear','VisCapLat','EcrouCapLat','VisPorteXT90','EcrouPorteXT90','CollierJETI','CollierMag','CollierXT90','SpliceJETI','IsolationSplice']
 for o in list(dock.Objects):
  if o.Name in obsolete or any(o.Name.startswith(p) for p in prefixes):removed.append(o.Name);dock.removeObject(o.Name)
 # Supports natifs : reculer panneau et outils, allonger bras, garder ancrages.
 for name,arm in [('P39_SupportFixeContacts20Ah','Pied'),('P40_SupportMobileContacts20Ah','Bras')]:
  r=load('pieces/fabriquees',name);d=r.Document
  if not hasattr(r,'MigrationDirecte'):
   for o in d.Objects:
    preserve=o.Name.startswith(('TrouPiedM3','FraisureM3','TrouFondM3'))
    if o.TypeId in ['Part::Box','Part::Cylinder','Part::Cone','Part::Feature'] and not preserve:
     if o.TypeId=='Part::Feature':shift_placement(o,'Placement',(-SHIFT,0,0))
     else:
      if 'Placement.Base.x' in [x[0] for x in o.ExpressionEngine]:o.setExpression('Placement.Base.x',None)
      shift_placement(o,'Placement',(-SHIFT,0,0))
    if o.TypeId=='Part::Box' and o.Name.startswith(arm):o.Length=float(o.Length)+SHIFT
   meta(r,'MigrationDirecte','TE reculé82mm, ancrages existants préservés ; cantilever/rigidité À valider')
   d.Parametres.set('B1',str(-242 if arm=='Pied' else -212.65)+' mm')
   color(d.Resultat,(.78,.62,.33));changed.append(d)
 # Deux passages protégés candidats dans la capture (pas dans le softpack).
 r=load('pieces/fabriquees','P31_CaptureCassette20Ah');d=r.Document
 if not d.getObject('PassagesFilsDirects'):
  old=d.Resultat;old.Label='Capture avant passe-fils'
  holes=[cyl(d,r,'PassagePack'+str(i),3.25,6,(-105,y,82),(1,0,0)) for i,y in enumerate([5,-5])]
  out=cut(d,r,'PassagesFilsDirects',old,holes);meta(r,'PasseFils','DeuxØ6.5mm étude, sorties lot à relever ; manchons anti-frottement requis, non qualifiés.')
  finish(d,r,out,(.95,.48,.12))
 # Cosse commerciale90°, enveloppe paramétrique suivant cotes de série F.
 name='EQ_Klauke742F5_Cosse90_TE';p=MEC/'pieces/commerce'/(name+'.FCStd')
 r=load('pieces/commerce',name) if p.exists() else A.newDocument(name).addObject('App::Part','Reference');d=r.Document
 clear_features(d)
 parts=[cyl(d,r,'PlageM5',6,2,(0,0,0),(1,0,0)),box(d,r,'CoudeEtude',(5,10.5,6),(0,-10.5,-3)),cyl(d,r,'FutEtude',4,14,(1,-10.5,0),(1,0,0))]
 out=cut(d,r,'Resultat',fuse(d,r,'CorpsCosse',parts),[cyl(d,r,'TrouM5',2.65,4,(-1,0,0),(1,0,0)),cyl(d,r,'EntreeFil',2.75,15,(2,-10.5,0),(1,0,0))])
 meta(r,'MPN','742F5');meta(r,'Source','https://www.klauke.com/be/de/winkelrohrkabelschuhe-cu-90-und-45-abgewinkelt-f-reihe')
 meta(r,'Limite','Enveloppe90° M5/trou5.3,d1=5.5,d4=8,a=14,b=12 ; déport10.5 et forme du coude étude. Catalogue10mm² classes5/6 ; compatibilité AWG8/sertissage/outillage à confirmer. Ne pas usiner la cosse commerciale.')
 finish(d,r,out,(.76,.67,.36));d.FileName=str(p)
 # Recaler occurrences TE, sauf supports dont géométrie a déjà été déplacée.
 contacts=load('sous_assemblages','SA02_Contacts20Ah','Ensemble').Document
 for d,prefix in [(dock,'Conn_'),(contacts,'')]:
  for o in d.Objects:
   if o.TypeId!='App::Link' or (prefix and not o.Name.startswith(prefix)):continue
   key=o.Name[len(prefix):]
   if key.startswith(('Support','VisFond','EcrouSousFond','VisFraiseePied')):continue
   if not hasattr(o,'ReculDirectTE'):
    x=o.LinkPlacement.Base.x-SHIFT
    if getattr(o,'Mobile','non')=='oui':o.setExpression('LinkPlacement.Base.x',str(x)+' mm + Parametres.ExtractionX')
    else:shift_placement(o,'LinkPlacement',(-SHIFT,0,0))
    meta(o,'ReculDirectTE','82mm')
  meta(d.getObject('Ensemble'),'RaccordementCourant','Direct pack/cosses90, TE−82mm ; engagement et résistance supports À valider');changed.append(d)
 # Fixed borne guard and hardware translated with contacts.
 for o in dock.Objects:
  if o.TypeId=='App::Link' and (o.Name.startswith(('EntretoiseCuFixe','CosseFixe','RondelleBorneFixe','VisBorneFixe','VisProtectionFixe','RondelleProtectionFixe','EcrouProtectionFixe','VisCapFixe','EcrouCapFixe')) or o.Name in ['ProtectionFixeTE','CapotProtectionFixeTE']):
   if not hasattr(o,'ReculDirectTE'):shift_placement(o,'LinkPlacement',(-SHIFT,0,0));meta(o,'ReculDirectTE','82mm')
 # Pack retourné ; sorties/équilibrage nominales se trouvent maintenant derrière.
 rot=A.Rotation(A.Vector(0,0,1),180)
 set_rotation(dock.Cass_Batterie,'LinkPlacement',rot)
 cass=load('sous_assemblages','SA02_Cassette20Ah_Coulissante','Reference').Document
 set_rotation(cass.Batterie,'LinkPlacement',rot);changed.append(cass)
 for o in dock.Objects:
  if o.Name.startswith(('P51_','P52_','EQ_Equilibrage','EQ_BoucleEquilibrage','VisRetenueEquilibrage','EcrouRetenueEquilibrage','VisCapotEquilibrage','EcrouCapotEquilibrage')) and o.TypeId=='App::Link' and not hasattr(o,'EquilibrageRetourne'):
   base=rot.multVec(o.LinkPlacement.Base);base.y+=36;o.LinkPlacement=A.Placement(base,rot.multiply(o.LinkPlacement.Rotation));o.setExpression('LinkPlacement.Base.x',str(base.x)+' mm + Parametres.ExtractionX');meta(o,'EquilibrageRetourne','oui')
 # Faisceau équilibrage séparé, hors coffret puissance et hors contactsTE.
 eq=dock.EQ_BoucleEquilibragePack20Ah_Reservation
 eq.LinkPlacement=A.Placement();eq.setExpression('LinkPlacement.Base.x','Parametres.ExtractionX')
 src=eq.LinkedObject.Document;sw=next(o for o in src.Objects if o.TypeId=='Part::Sweep');path=sw.Spine[0];section=sw.Sections[0]
 path.Shape=Part.Wire([Part.makeLine(A.Vector(-99,18,92),A.Vector(-99,39,92)),Part.Arc(A.Vector(-99,39,92),A.Vector(-103.3934,49.6066,92),A.Vector(-114,54,92)).toShape(),Part.makeLine(A.Vector(-114,54,92),A.Vector(-131,54,92))])
 section.Shape=Part.Wire(Part.makeCircle(1.75,A.Vector(-99,18,92),A.Vector(0,1,0)));sw.Spine=(path,[]);path.Visibility=False;section.Visibility=False;changed.append(src)
 # Protection mobile en place devient un coffret arrière court.
 rguard=load('pieces/fabriquees','P43_ProtectionConducteurs20Ah');d=rguard.Document;clear_features(d)
 base=box(d,rguard,'CoffretArriere',(108,46,42),(-210,-15,62))
 tools=[box(d,rguard,'VideInterieur',(111,42,38),(-212,-13,64)),box(d,rguard,'FenetreFils',(5,34,24),(-104,-11,65))]
 out=cut(d,rguard,'Resultat',base,tools);meta(rguard,'Limite','PA12 candidat, capot et passe-fils directs ; fixations et rigidité À valider. Pas de barres longitudinales.');finish(d,rguard,out)
 rcap=load('pieces/fabriquees','P44_CouvercleArriereConducteurs20Ah');d=rcap.Document;clear_features(d)
 out=box(d,rcap,'Resultat',(108,46,2),(-210,-15,104));finish(d,rcap,out)
 rows=[]
 for i,(pol,y,z) in enumerate([('Plus',5,69.745),('Moins',-5,86.255)]):
  name='EQ_LeadPack8AWG_'+pol+'20A';o=dock.getObject(name);src=o.LinkedObject.Document
  start=(-99,y,82);end=(-186.2548,11.1535,z);wire=route(start,end)
  sw=src.Cordon;path=sw.Spine[0];section=sw.Sections[0];path.Shape=wire;section.Shape=Part.Wire(Part.makeCircle(2.5,A.Vector(*start),A.Vector(-1,0,0)))
  sw.Spine=(path,[]);sw.Solid=True;src.recompute();assert sw.Shape.isValid()
  meta(src.Reference,'Limite','AWG8 pack direct cosse90 ; sorties nominales non mesurées, coupe/sertissage sur lot et rayonR50 à valider ; aucune intervention sur cellules scellées.')
  meta(src.Reference,'LongueurChemin_mm',wire.Length);path.Visibility=False;section.Visibility=False;color(sw,(.85,.08,.09) if i==0 else (.1,.11,.14));changed.append(src)
  if not dock.getObject('CosseMobileDirecte'+str(i)):
   lug=link(dock,dock.Ensemble,'CosseMobileDirecte'+str(i),r,(-200.2548,21.6535,z));meta(lug,'Mobile','oui');lug.setExpression('LinkPlacement.Base.x','-200.2548 mm + Parametres.ExtractionX')
  for key in ['VisM5ContactMobile','RondelleM5ContactMobile']:
   obj=dock.getObject(key+str(i))
   if not hasattr(obj,'ReculDirectTE'):
    x=obj.LinkPlacement.Base.x-SHIFT;obj.setExpression('LinkPlacement.Base.x',str(x)+' mm + Parametres.ExtractionX');meta(obj,'ReculDirectTE','82mm')
  rows.append(dict(reference=name,depart_mm=start,entree_cosse_mm=end,longueur_mm=wire.Length,rayon_mm=50,diametre_etude_mm=5))
 # Ancrage coffret à reprendre sur brasP40 ; étude affichée sans fausse fixation.
 meta(dock.Ensemble,'Limite','CAO directe et étage énergie À valider. Corps TE inchangés. Supports rallongés et capots candidats ; lot pack/cosse, accouplement, cantilever, thermique et charges à qualifier. Pas dossier fabrication.')
 for d in A.listDocuments().values():d.recompute()
 for d in dict.fromkeys(changed):
  save_native(d);Part.export([d.getObject(getattr(d.Reference,'ObjetFinal','Resultat'))],str(MEC/'exports/cassette20Ah_20261002'/(d.Name+'.step'))) if d.getObject('Reference') and getattr(d.Reference,'ObjetFinal','') else None
 dock.recompute();save_native(dock)
 proof=dict(date='2026-10-04',realisation_CAO='Implémenté',statut='À valider',fichier='sous_assemblages/SA02A_Dock20Ah.FCStd',bbox_avant_mm=before,bbox_apres_mm=bb(dock.Ensemble.Shape),supprimes=removed,TE_recul_mm=SHIFT,pack_rotation_Z_deg=180,cosses={'reference':'742F5','AWG8_sertissage_confirme':False,'geometrie_coude':'enveloppe étude'},routes_mobiles=rows,fichiers_modifies=[str(Path(d.FileName).relative_to(ROOT)).replace('\\','/') for d in dict.fromkeys(changed)],finalisation_correcte=True)
 (VER/'raccordement_direct_batterie.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(proof,ensure_ascii=False))
if __name__=='__main__':main()
