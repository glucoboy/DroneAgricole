"""Infrastructure de placement absolu, sans accumulation au rejeu."""
from etage_batterie_helpers import *
import json
require_legacy_layout('canonical_positions_etage_batterie.py')
for name in ['P39_SupportFixeContacts20Ah','P40_SupportMobileContacts20Ah']:
 r=load('pieces/fabriquees',name);d=r.Document
 for o in d.Objects:
  if o.TypeId not in ['Part::Box','Part::Cylinder','Part::Cone','Part::Feature']:continue
  if o.Name.startswith(('TrouPiedM3','FraisureM3')):x=-117.5
  elif o.Name.startswith('TrouFondM3'):x=-104
  elif o.TypeId=='Part::Feature':x=-82
  elif name.startswith('P39'):x=-242 if o.Name.startswith(('Bride','Pied','Montant')) else -243
  else:x=-212.65 if o.Name.startswith(('Bride','Bras','Montant')) else -213.65
  if o.TypeId=='Part::Box':o.setExpression('Placement.Base.x',None)
  p=o.Placement;p.Base=A.Vector(x,p.Base.y,p.Base.z);o.Placement=p
 d.recompute();assert d.Resultat.Shape.isValid();save_native(d)
original=[json.loads(s) for s in (VER/'inventaire_etage_batterie.jsonl').read_text(encoding='utf-8-sig',errors='replace').splitlines()]
for name,index in [('SA02A_Dock20Ah',0),('SA02_Contacts20Ah',2)]:
 d=load('sous_assemblages',name,'Ensemble').Document;lookup={row['name']:row for row in original[index]['objects']}
 for o in d.Objects:
  if o.TypeId=='App::Link' and hasattr(o,'ReculDirectTE') and o.Name in lookup:
   xyz=lookup[o.Name]['pos'];xyz[0]-=82;p=o.LinkPlacement;p.Base=A.Vector(*xyz);o.LinkPlacement=p
   if getattr(o,'Mobile','non')=='oui':o.setExpression('LinkPlacement.Base.x',str(xyz[0])+' mm + Parametres.ExtractionX')
 save_native(d)
print('Placements absolus canoniques enregistrés')
