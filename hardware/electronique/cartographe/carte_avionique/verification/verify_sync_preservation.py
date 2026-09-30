"""Vérification d'infrastructure : conservation du circuit hors adaptations GNSS."""
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE/'netlist_avant_sync_physique_20260930.xml'
CURRENT=HERE/'netlist.xml'
before=ET.parse(BASE).getroot(); after=ET.parse(CURRENT).getroot()
# Les quatre blocs abstraits et les quatre résistances de sortie sont remplacés.
# Tous les autres composants existants sont protégés, y compris Basler et énergie.
changed={'U504','U505','U506','U507','R530','R531','R532','R533'}
old={c.attrib['ref']:c for c in before.findall('./components/comp')}
new={c.attrib['ref']:c for c in after.findall('./components/comp')}
protected=set(old)-changed
def nets(tree):
    return {frozenset(n.attrib['ref']+'/'+n.attrib['pin'] for n in net.findall('node')
                     if n.attrib['ref'] in protected)
            for net in tree.findall('./nets/net') if any(n.attrib['ref'] in protected for n in net.findall('node'))}
checks=[]
checks.append({'id':'protected_components_present','passed':protected <= set(new),'count':len(protected)})
checks.append({'id':'protected_pin_groups_unchanged','passed':nets(before)==nets(after),
               'lost':[sorted(s) for s in nets(before)-nets(after)],
               'added':[sorted(s) for s in nets(after)-nets(before)]})
def fields(c):
    return (c.findtext('value'),c.findtext('footprint'),
            sorted((p.attrib['name'],p.attrib.get('value','')) for p in c.findall('property')
                   if p.attrib['name'] in {'dnp','exclude_from_bom','exclude_from_board'}),
            next((p.text or '' for p in c.findall('./fields/field') if p.attrib['name']=='MPN'),''))
modified=[ref for ref in sorted(protected) if ref in new and fields(old[ref])!=fields(new[ref])]
checks.append({'id':'protected_values_footprints_dnp_unchanged','passed':not modified,'modified':modified})
proof={'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),
       'scope':'CA01 : conservation énergie, radio, trigger/capture Basler et connecteurs existants après réalisation GNSS',
       'platform':'Windows amd64 ; netlist KiCad 10.0.6',
       'checks':checks,'passed':all(c['passed'] for c in checks),
       'inputs':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (BASE,CURRENT)],
       'hardware_tests_executed':False,'manufacturing_ready':False,'qualification':'À valider',
       'limits':['Les ajouts de broches nouvelles aux rails communs sont autorisés ; la topologie entre broches existantes doit rester identique.',
                 'Les annotations Description/Qualification et déplacements graphiques peuvent changer ; valeurs, empreintes, MPN et exclusions restent protégés.',
                 'Cette comparaison ne vérifie ni les marges, ni les empreintes physiques, ni le comportement hors tension.']}
(HERE/'conservation_sync_20260930.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f"{sum(c['passed'] for c in checks)}/{len(checks)} contrôles de conservation conformes")
if not proof['passed']:raise SystemExit(1)
