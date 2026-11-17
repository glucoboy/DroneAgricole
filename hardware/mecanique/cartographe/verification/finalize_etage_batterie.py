"""Finalisation géométrique et GUI actuelle, sans rétablir une ancienne géométrie."""
from etage_batterie_helpers import *
from update_raccordement_direct_batterie import cyl,cut
import Part,json,zipfile,xml.etree.ElementTree as ET
require_legacy_layout('finalize_etage_batterie.py')
dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
r=load('pieces/fabriquees','P43_ProtectionConducteurs20Ah');d=r.Document
d.CoffretArriere.Length=96;d.CoffretArriere.Height=39.5;p=d.CoffretArriere.Placement;p.Base=A.Vector(-202,-15,61);d.CoffretArriere.Placement=p
d.VideInterieur.Length=97;d.VideInterieur.Height=35.5;p=d.VideInterieur.Placement;p.Base=A.Vector(-200,-13,63);d.VideInterieur.Placement=p
p=d.FenetreFils.Placement;p.Base=A.Vector(-108,p.Base.y,p.Base.z);d.FenetreFils.Placement=p
if not d.getObject('PassagesBornes'):
 out=cut(d,r,'PassagesBornes',d.Resultat,[cyl(d,r,'PassageBorne'+str(i),3.25,6,(-204,21.6535,z),(1,0,0)) for i,z in enumerate([69.745,86.255])]);meta(r,'ObjetFinal',out.Name);color(out,(.32,.35,.40))
for i in range(2):d.getObject('PassageBorne'+str(i)).Radius=7
if not d.getObject('DegagementCoudesBornes'):
 tools=[]
 for i,z in enumerate([69.745,86.255]):
  tool=d.addObject('Part::Box','OuvertureCoude'+str(i));r.addObject(tool);tool.Length=6;tool.Width=20;tool.Height=14;tool.Placement=A.Placement(A.Vector(-204,9,z-7),A.Rotation());tools.append(tool)
 out=cut(d,r,'DegagementCoudesBornes',d.PassagesBornes,tools);meta(r,'ObjetFinal',out.Name);color(out,(.32,.35,.40))
save_native(d)
r=load('pieces/fabriquees','P44_CouvercleArriereConducteurs20Ah');d=r.Document;d.Resultat.Length=96;p=d.Resultat.Placement;p.Base=A.Vector(-202,p.Base.y,100.5);d.Resultat.Placement=p;save_native(d)
r=load('pieces/fabriquees','P31_CaptureCassette20Ah');d=r.Document
if d.getObject('PassageEquilibrageDirectOutils'):
 d.PassageEquilibrageDirect.Tool=d.PassageFilEquilibrage;d.removeObject('PassageEquilibrageDirectOutils');save_native(d)
if not d.getObject('PassageEquilibrageDirect'):
 out=cut(d,r,'PassageEquilibrageDirect',d.getObject(r.ObjetFinal),[cyl(d,r,'PassageFilEquilibrage',3,7,(-99,38,92),(0,1,0))]);meta(r,'ObjetFinal',out.Name);color(out,(.95,.48,.12));save_native(d)
if not d.getObject('FenetreEquilibrageArriere'):
 tool=d.addObject('Part::Box','PassageArriereEquilibrage');r.addObject(tool);tool.Length=6;tool.Width=20;tool.Height=7;tool.Placement.Base=A.Vector(-105,-33,87)
 out=cut(d,r,'FenetreEquilibrageArriere',d.getObject(r.ObjetFinal),[tool]);meta(r,'ObjetFinal',out.Name);color(out,(.95,.48,.12));save_native(d)
# Équilibrage dans le corridor intérieur, sans traverser les colonnesY±52.
for o in list(dock.Objects):
 if o.TypeId=='App::Link' and o.Name.startswith(('VisRetenueEquilibrage','EcrouRetenueEquilibrage')):dock.removeObject(o.Name);continue
 if o.TypeId=='App::Link' and o.Name.startswith(('P51_','P52_','EQ_Equilibrage','VisCapotEquilibrage','EcrouCapotEquilibrage')) and not hasattr(o,'EquilibrageInterieur'):
  shift_placement(o,'LinkPlacement',(0,-83.5,-1.5));meta(o,'EquilibrageInterieur','corridorY−42..−17, fixationÀdéfinir')
eq=dock.EQ_BoucleEquilibragePack20Ah_Reservation;eq.LinkPlacement=A.Placement();eq.setExpression('LinkPlacement.Base.x','Parametres.ExtractionX')
src=eq.LinkedObject.Document;sw=next(o for o in src.Objects if o.TypeId=='Part::Sweep');path=sw.Spine[0];section=sw.Sections[0]
path.Shape=Part.Wire([Part.makeLine(A.Vector(-99,18,90.5),A.Vector(-99,-15,90.5)),Part.Arc(A.Vector(-99,-15,90.5),A.Vector(-103.3934,-25.6066,90.5),A.Vector(-114,-30,90.5)).toShape(),Part.makeLine(A.Vector(-114,-30,90.5),A.Vector(-131,-30,90.5))]);section.Shape=Part.Wire(Part.makeCircle(1.75,A.Vector(-99,18,90.5),A.Vector(0,-1,0)));sw.Spine=(path,[]);save_native(src)
# Dégagement de l'appui candidat P51 autour de l'allonge P40 (pièce fabriquée).
r51=load('pieces/fabriquees','P51_RetenueEquilibrage20Ah');d51=r51.Document
d51.EntreeFaisceau.Width=7;d51.EntreeFaisceau.Height=6;d51.EntreeFaisceau.Placement=A.Placement(A.Vector(124,-22,89),A.Rotation())
if not d51.getObject('DegagementBrasDirect'):
 tool=d51.addObject('Part::Box','ReservationBrasP40');r51.addObject(tool);tool.Length=112;tool.Width=8.8;tool.Height=3.8;tool.Placement.Base=A.Vector(101,-18.9,46.1)
 out=cut(d51,r51,'DegagementBrasDirect',d51.getObject(r51.ObjetFinal),[tool]);meta(r51,'ObjetFinal',out.Name);meta(r51,'Limite','Coffretéquilibrage intérieur, dégagementbrasP40 ; fixationÀdéfinir, anciennesvisretenue retirées. Appui, rigidité ettraitementanti-frottementÀvalider.');color(out,(.32,.35,.40));save_native(d51)
save_native(d51)
for o in dock.Objects:
 if o.TypeId=='App::Link':o.ViewObject.OverrideMaterial=False
save_native(dock)
integration=load('assemblages','Integration_Stack_Revue_20261003','IntegrationRevue').Document
meta(integration.IntegrationRevue,'Limites','Batterie directe TE et énergie à étage inférieur ; routesTE/JETI incluses. Faisceaux aval et fixations candidats, pas configuration drone finale ni qualification.');save_native(integration)
# Terminaison M5 : appui de la rondelle après la plage de cosse de 2 mm,
# tête de vis après la rondelle de 1 mm. Coude commercial représenté par
# une enveloppe d'étude ; aucun usinage de la cosse achetée n'est prescrit.
rcosse=load('pieces/commerce','EQ_Klauke742F5_Cosse90_TE');dc=rcosse.Document
dc.TrouM5.Height=8;dc.CoudeEtude.Width=5.5
meta(rcosse,'Limite','Enveloppe commerciale candidate, plage2mm et coude90 approximatif. Compatibilité AWG8, géométrie fabricant, outillage, engagementM5 et sertissage À valider ; ne pas usiner la cosse achetée.')
save_native(dc)
for i in range(2):
 for prefix,x in [('RondelleM5ContactMobile',-198.2548),('VisM5ContactMobile',-197.2548)]:
  o=dock.getObject(prefix+str(i));p=o.LinkPlacement;p.Base=A.Vector(x,p.Base.y,p.Base.z);o.LinkPlacement=p;o.setExpression('LinkPlacement.Base.x',str(x)+' mm + Parametres.ExtractionX')
save_native(dock)
from persist_etage_batterie import persist
persist()
print('Finalisation géométrie, visibilité et couleurs')
