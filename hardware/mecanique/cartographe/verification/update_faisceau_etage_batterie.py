"""Infrastructure CAO : TE flottant vers JETI déporté sous la batterie, R50."""
from update_raccordement_direct_batterie import route, cyl,cut
from etage_batterie_helpers import *
import Part, math,json
require_legacy_layout('update_faisceau_etage_batterie.py')
dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
rows=[]
for i,(pol,z,yend) in enumerate([('Plus',69.745,-115),('Moins',86.255,-99)]):
 # Les cosses droites fixes sortent toutes deux vers−Y, dans le capot.
 set_rotation(dock.getObject('CosseFixe'+str(i)),'LinkPlacement',A.Rotation(A.Vector(0,0,1),-90))
 start=A.Vector(-261.9,-5.2465,z);p=A.Vector(-261.9,yend+50,z)
 mid=p+A.Vector(50*(1-math.cos(math.pi/4)),-50*math.sin(math.pi/4),0);q=p+A.Vector(50,-50,0)
 turn=Part.Arc(p,mid,q).toShape();s=route(tuple(q),(-40,yend,-16.5),lead_fraction=0)
 wire=Part.Wire([Part.makeLine(start,p),turn]+s.Edges)
 src=dock.getObject('EQ_CordonFixe8AWG_'+pol+'20A').LinkedObject.Document
 src.Chemin.Shape=wire;src.Section.Shape=Part.Wire(Part.makeCircle(2.5,start,A.Vector(0,-1,0)));src.Cordon.Spine=(src.Chemin,[]);src.Cordon.Sections=[src.Section];src.Cordon.Solid=True
 src.Chemin.Visibility=False;src.Section.Visibility=False;color(src.Cordon,(.85,.08,.09) if i==0 else (.1,.11,.14))
 meta(src.Reference,'LongueurChemin_mm',wire.Length);meta(src.Reference,'Limite','TE fixe vers entréeJETI àétage inférieur ; R50/Ø5 étude. Pas de premier bridage proche du TE. Sectionkit8mm², raccordOEM, flottement et vibration à confirmer. Longueur totale ne prouve pas distance152.4mm.')
 src.recompute();assert src.Cordon.Shape.isValid(),pol;save_native(src)
 Part.export([src.Cordon],str(MEC/'exports/cassette20Ah_20261002'/(src.Name+'.step')))
 rows.append(dict(reference=src.Name,depart_mm=list(start),fin_mm=[-40,yend,-16.5],longueur_mm=wire.Length,rayons_mm=[e.Curve.Radius for e in wire.Edges if isinstance(e.Curve,Part.Circle)],distance_spatiale_TE_module_mm=(A.Vector(-167.353-82,21.6535,z)-A.Vector(-40,yend,-16.5)).Length,premier_collier_CAO=None))
# Corriger les passages du capot existant sur les axes effectifs des câbles.
r=load('pieces/fabriquees','P49_ProtectionFixeTE20Ah');d=r.Document
if not d.getObject('PassagesDirectsEtage'):
 holes=[cyl(d,r,'PassageEtage'+str(i),3.25,55,(-179.9,-52,z),(0,1,0)) for i,z in enumerate([69.745,86.255])]
 out=cut(d,r,'PassagesDirectsEtage',d.Resultat,holes);meta(r,'ObjetFinal',out.Name);meta(r,'Limite','PassagesØ6.5 étudealignés aux deuxsorties−Y ; protection touchsafe, jeux et flottement À valider.');color(out,(.32,.35,.40));save_native(d)
dock.recompute();save_native(dock)
(VER/'faisceau_etage_batterie.json').write_text(json.dumps(dict(date='2026-10-04',routes=rows,statut='À valider',finalisation_correcte=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows))
