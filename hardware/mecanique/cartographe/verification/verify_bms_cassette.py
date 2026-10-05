"""Relecture native neuve et collisions BMS/cassette ; jamais qualification physique."""
from pathlib import Path
import hashlib,json,sys,math
import FreeCAD as A,Part
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def bb(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def common(a,b):return a.common(b).Volume if a.BoundBox.intersect(b.BoundBox) else 0
def main():
 top=A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
 for d in A.listDocuments().values():
  for o in d.Objects:o.touch()
 for _ in range(2):
  for d in A.listDocuments().values():d.recompute()
 dock=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='SA02A_Dock20Ah');dist=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='SA07_Distribution_Systeme_Candidat')
 invalid=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if 'Invalid' in o.State]
 broken=[d.Name+'.'+o.Name for d in A.listDocuments().values() for o in d.Objects if o.TypeId=='App::Link' and (not o.LinkedObject or o.Shape.isNull())]
 assert not invalid and not broken,(invalid,broken)
 new=[o for o in dock.Objects if o.TypeId=='App::Link' and (o.Name=='ProtectionFixeTE' or o.Name.startswith(('BMS_','P43_','P44_','EQ_BMS_','EQ_LeadPack','EQ_BoucleEquilibrage','EQ_BouclePresence','EQ_CordonFixe','AppuiIsolationBMS')))]
 hits=[]
 others=[o for o in dock.Objects if o.TypeId=='App::Link']
 for o in new:
  for q in others:
   if q==o:continue
   if q in new and q.Name<o.Name:continue
   v=common(o.Shape,q.Shape)
   if v>.001:hits.append(dict(objet=o.Name,autre=q.Name,volume_mm3=v))
  for q in top.Objects:
   if q.TypeId=='App::Link' and q.Name not in ['SA02A_Dock20Ah','SA08_Faisceau_Systeme_Candidat']:
    v=common(o.Shape,q.Shape)
    if v>.001:hits.append(dict(objet=o.Name,autre='integration.'+q.Name,volume_mm3=v))
 iso=dist.InterfaceBMSIsolee
 for q in top.Objects:
  if q.TypeId=='App::Link' and q.Name not in ['SA07_Distribution_Systeme_Candidat','SA08_Faisceau_Systeme_Candidat']:
   v=common(iso.Shape,q.Shape)
   if v>.001:hits.append(dict(objet=iso.Name,autre='integration.'+q.Name,volume_mm3=v))
 for q in dist.Objects:
  if q.TypeId=='App::Link' and q!=iso:
   v=common(iso.Shape,q.Shape)
   if v>.001:hits.append(dict(objet=iso.Name,autre=q.Name,volume_mm3=v))
 # BMS/coffret/fils doivent suivre la même extraction ; contacts électriquescandidats exclus.
 samples=[]
 chassis=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='SA01_Chassis_Stack_Revue_20261003')
 fixed=[o for o in chassis.Objects if o.TypeId=='App::Link']+[o for o in dock.Objects if o.TypeId=='App::Link' and getattr(o,'Mobile','non')!='oui' and not o.Name.startswith(('Conn_Contact','Conn_Signal','Conn_Housing'))]
 for x in [0,10,25,50,100,200,350,500]:
  found=[]
  for o in new:
   if getattr(o,'Mobile','non')!='oui':continue
   s=o.Shape.copy();s.translate(A.Vector(x,0,0))
   for q in fixed:
    v=common(s,q.Shape)
    if v>.001:found.append(dict(objet=o.Name,autre=q.Name,volume_mm3=v))
  samples.append(dict(extraction_mm=x,intersections=found))
 shape=Part.makeCompound([dock.Ensemble.Shape,dist.Reference.Shape]);bounds=bb(shape)
 proof=dict(date='2026-10-05',test='T-CARTO-BMS-02-CAO',processus_neuf=True,FreeCAD='.'.join(A.Version()[:3]),erreurs_recalcul=invalid,liens_non_resolus=broken,bbox_BMS_mm=bb(dock.BMS_JBD.Shape),bbox_coffret_mm=bb(dock.P43_ProtectionConducteurs20Ah.Shape),bbox_batterie_et_energie_mm=bounds,dimensions_batterie_et_energie_mm=[bounds[i+3]-bounds[i] for i in range(3)],intersections_brutes=hits,extraction_echantillonnee=samples,sources_sha256={str(Path(d.FileName).relative_to(ROOT)).replace('\\','/'):hashlib.sha256(Path(d.FileName).read_bytes()).hexdigest() for d in A.listDocuments().values() if d.FileName and Path(d.FileName).is_relative_to(ROOT)},qualification='À valider',limites=['EnveloppePCBtolérancée seulement, bornes/prises/dissipateurBMSnonconfirmés.','InterfaceWaveshareenréservation90×80×26, contacts#20enveloppesprovisoires,cavitésnumérotéesàconfirmer.','Ports/sections/rayons/sertissages/maintien/touchsafe/thermiqueetlotaqualifier.','Échantillonnageextractionneprouvepascontinuitédecourse niinterférencesprototypeslot.'],finalisation_correcte=False)
 intended={frozenset(['EQ_BoucleEquilibragePack20Ah_Reservation','EQ_EquilibragePack20Ah_Reservation']):'Entrée du câble dans réservation JST ; accouplement physique à valider',frozenset(['EQ_BMS_PMoins_TE20A','CosseMobileDirecte1']):'Fil dans fut de cosse négative ; sertissage à valider',frozenset(['EQ_BMS_BPlus_Liaison20A','EQ_LeadPack8AWG_Plus20A']):'Jonction B+ commune réservée ; terminaison de branche et isolation à définir'}
 proof['interfaces_intentionnelles']=[dict(h,justification=intended[frozenset([h['objet'],h['autre']])]) for h in hits if frozenset([h['objet'],h['autre']]) in intended]
 proof['intersections_non_resolues']=[h for h in hits if frozenset([h['objet'],h['autre']]) not in intended]
 proof['finalisation_correcte']=not invalid and not broken and not proof['intersections_non_resolues'] and all(not s['intersections'] for s in samples)
 proof['implantation']='Au-dessus de la batterie' if 'au-dessus' in dock.Ensemble.BMSIntegre else 'Arrière historique'
 if proof['implantation']=='Au-dessus de la batterie':
  assert abs(float(chassis.Parametres.Rehausse)-45)<1e-6
  col=next(d for d in A.listDocuments().values() if Path(d.FileName).stem=='P37_Entretoise70_6061_M3')
  assert abs(float(col.Parametres.Longueur)-95)<1e-6
  assert abs(chassis.Part__Feature311.Shape.BoundBox.ZMin-128)<1e-6
  assert abs(dock.BMS_JBD.Shape.BoundBox.ZMin-107)<1e-6
  lead=dock.EQ_LeadPack8AWG_Plus20A.LinkedObject.Document.Chemin.Shape
  radii=[e.Curve.Radius for e in lead.Edges if hasattr(e.Curve,'Radius')]
  proof['positif_direct']=dict(longueur_mm=lead.Length,rayons_mm=radii,longueur_usine_etude_mm=150,surplus_usine_non_affecte_mm=150-lead.Length,limite='Coupe/sertissage/stockage du surplus à valider ; longueur sous139 mm ne qualifie pas le raccordement')
  assert all(abs(r-50)<1e-6 for r in radii) and lead.Length<139
  if 'compact' in dock.Ensemble.BMSIntegre.lower():
   guard=dock.ProtectionFixeTE.LinkedObject.Document
   guard_final=guard.getObject(guard.Reference.ObjetFinal).Shape
   guard_final.check(True)
   assert guard_final.isValid() and len(guard_final.Solids)==1,'Protection fixe à rendre monobloc'
   assert abs(dock.ProtectionFixeTE.Shape.BoundBox.ZMax-121)<1e-6,'Hauteur protection fixe modifiée'
   expected_axis=A.Vector(-1,0,0)
   axes=[]
   for name in ['Conn_HousingSocket','Conn_ContactSocket39Plus','Conn_ContactSocket40Moins','VisM5ContactMobile0','VisM5ContactMobile1']:
    axis=dock.getObject(name).LinkPlacement.Rotation.multVec(A.Vector(0,0,1))
    assert (axis-expected_axis).Length<1e-6,(name,tuple(axis))
    axes.append(dict(occurrence=name,axe_source_Z_monde=list(axis)))
   for i,contact in enumerate(['Conn_ContactSocket39Plus','Conn_ContactSocket40Moins']):
    lug=dock.getObject('CosseMobileDirecte'+str(i))
    assert abs(dock.getObject(contact).Shape.BoundBox.XMax-lug.LinkPlacement.Base.x)<1e-4,contact
   routes=[]
   for name in ['EQ_LeadPack8AWG_Plus20A','EQ_LeadPack8AWG_Moins20A','EQ_BMS_PMoins_TE20A','EQ_BoucleEquilibragePack20Ah_Reservation','EQ_BMS_UART_TE20A']:
    obj=dock.getObject(name);src=obj.LinkedObject.Document;wire=src.Chemin.Shape;obj.Shape.check(True)
    rs=[e.Curve.Radius for e in wire.Edges if isinstance(e.Curve,Part.Circle)]
    routes.append(dict(reference=name,longueur_mm=wire.Length,rayons_mm=rs,controle_BOP=True))
   for i,name in enumerate(['EQ_LeadPack8AWG_Plus20A','EQ_BMS_PMoins_TE20A']):
    wire=dock.getObject(name).LinkedObject.Document.Chemin.Shape;edge=wire.Edges[-1]
    endpoint=edge.valueAt(edge.LastParameter);entry=dock.getObject('CosseMobileDirecte'+str(i)).LinkPlacement.multVec(A.Vector(14,-10.5,0))
    assert (endpoint-entry).Length<1e-6,(name,list(endpoint),list(entry))
    assert (edge.tangentAt(edge.LastParameter)-expected_axis).Length<1e-6,name
   assert len(lead.Edges)==1 and isinstance(lead.Edges[0].Curve,Part.Line)
   proof['raccord_compact']=dict(axes_geometriques=axes,routes=routes,entrees_cosses_axiales=True,protection_fixe_monobloc=True,hauteur_max_protection_fixe_mm=121,limite='Axes et interfaces de la représentation cohérents ; ne qualifie pas insertion, couple, sertissage, rayon ou accouplement du lot')
  proof['jeu_capot_plateau_mm']=chassis.Part__Feature311.Shape.BoundBox.ZMin-dock.P44_CouvercleArriereConducteurs20Ah.Shape.BoundBox.ZMax
  proof['jeu_pack_etude_fond_mm']=104-100
  p=VER/'implantation_bms_dessus.json';comp=json.loads(p.read_text(encoding='utf-8'))
  reference=VER/'bbox_bms_arriere_git.json'
  if reference.exists():
   baseline=json.loads(reference.read_text(encoding='utf-8'));assert baseline['finalisation_correcte']
   comp['bbox_avant_mm']=baseline['bbox_mm'];comp['reference_avant']='verification/bbox_bms_arriere_git.json'
   comp['limite_reference_avant']='145 sources exactes et deux reconstructions paramétriques P37=70/châssisRehausse=20, recalculées isolément ; pas147blobsGit identiques'
  comp['bbox_apres_mm']=dict(dock=bb(dock.Ensemble.Shape),batterie_et_energie=bb(shape),cassette_mobile=bb(Part.makeCompound([o.Shape for o in dock.Objects if o.TypeId=='App::Link' and getattr(o,'Mobile','non')=='oui'])),integration_locale=bb(top.IntegrationRevue.Shape))
  for scope,a in comp['bbox_avant_mm'].items():
   b=comp['bbox_apres_mm'][scope];da=[a[i+3]-a[i] for i in range(3)];db=[b[i+3]-b[i] for i in range(3)]
   comp['comparaison'][scope]=dict(dimensions_avant_mm=da,dimensions_apres_mm=db,volume_avant_mm3=math.prod(da),volume_apres_mm3=math.prod(db),variation_volume_pct=100*(math.prod(db)/math.prod(da)-1))
  comp['sources_sha256']=proof['sources_sha256'];comp['finalisation_geometrique_correcte']=proof['finalisation_correcte']
  p.write_text(json.dumps(comp,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  compact_path=VER/'compactage_raccord_bms_te.json'
  if compact_path.exists():
   current=json.loads(compact_path.read_text(encoding='utf-8'))
   current['sources_apres_verification_sha256']=proof['sources_sha256']
   current['bbox_apres_verification_mm']=comp['bbox_apres_mm']
   current['controle_geometrique']='controle_bms_cassette.json'
   current['finalisation_geometrique_correcte']=proof['finalisation_correcte']
   compact_path.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (VER/'controle_bms_cassette.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:proof[k] for k in ['intersections_brutes','extraction_echantillonnee','dimensions_batterie_et_energie_mm','finalisation_correcte']},ensure_ascii=False))
 if not proof['finalisation_correcte']:raise RuntimeError('Intersections non résolues ; voir contrôle BMS enregistré.')
if __name__=='__main__':main()
