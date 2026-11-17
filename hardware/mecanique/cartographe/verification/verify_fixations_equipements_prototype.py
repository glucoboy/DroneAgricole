"""Contrôle borné des fixations d'équipements, candidat ou fichiers finaux.

Le mode candidat travaille en mémoire avec les formes déjà sauvegardées. Il
n'écrit aucun natif ni résultat de succès final. Le mode final sera exécuté sur
la construction réconciliée et produit la preuve légère voisine.
"""
from pathlib import Path
import sys
import json
import math
import hashlib
import argparse
from datetime import datetime, timezone
import FreeCAD as A
import Part
import prototype_fixations_equipements as model
from read_brep_prototype import Reader

VER = Path(__file__).resolve().parent
MEC = VER.parent
TOL = 1e-5


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CandidateAPI:
    """Primitives de vérification uniquement, sans catalogue ni sauvegarde."""
    def __init__(self):
        self.index = 0
    def doc(self,name,*args):
        self.index += 1
        d=A.newDocument('Candidat'+str(self.index))
        return d,d.addObject('App::Part','Ensemble')
    def box(self,d,n,size,pos=(0,0,0)):
        o=d.addObject('Part::Box',n);o.Length,o.Width,o.Height=size;o.Placement.Base=A.Vector(*pos);return o
    def cylinder(self,d,n,r,h,pos=(0,0,0)):
        o=d.addObject('Part::Cylinder',n);o.Radius=r;o.Height=h;o.Placement.Base=A.Vector(*pos);return o
    def boolean(self,d,r,base,tools,name='Resultat'):
        current=base
        for t in tools:
            c=d.addObject('Part::Cut',name);c.Base=current;c.Tool=t;current.Visibility=False;t.Visibility=False;current=c
        r.addObject(current);d.recompute();return current
    def color(self,*args):pass
    def meta(self,r,n,value):
        if n not in r.PropertiesList:r.addProperty('App::PropertyString',n)
        setattr(r,n,str(value))


def bbox_overlap(a,b):
    return all(min(getattr(a,k+'Max'),getattr(b,k+'Max'))-max(getattr(a,k+'Min'),getattr(b,k+'Min'))>1e-7 for k in 'XYZ')


def intersection(a,b):
    if not bbox_overlap(a.BoundBox,b.BoundBox):return 0.0
    pieces=b.Solids if len(b.Solids)>30 else [b]
    return sum(a.common(piece).Volume for piece in pieces if bbox_overlap(a.BoundBox,piece.BoundBox))


def validate_shapes(named):
    failures=[]
    for name,shape in named.items():
        if shape.isNull() or not shape.isValid() or len(shape.Solids)!=1:
            failures.append({'objet':name,'valide':shape.isValid(),'solides':len(shape.Solids)})
    return failures


def candidate():
    api=CandidateAPI();reader=Reader(MEC)
    build=json.loads((VER/'construction_prototype.json').read_text('utf-8'))
    entries={x['occurrence']:x for x in build['occurrences'] if x['parent'].startswith('sous_assemblages/')}
    shapes={};specs={}
    for kind,ref,offset in [('gnss','P69_Support_GNSS_Prototype',(0,110,88)),
                            ('securite','P71_Support_Securite_Prototype',(0,-100,88))]:
        d,r=api.doc(ref)
        # Reproduire l'arbre de production : plaque finale et bras visibles,
        # anciens résultats et outils de coupe également dans root mais masqués.
        source='pieces/fabriquees/'+ref+'.FCStd';types,props=reader.xml(source)
        plate_names=[n for n in props if n.startswith('Resultat') and types[n]=='Part::Cut']
        final_plate=sorted(plate_names)[-1]
        for name in props:
            if name.startswith(('Plaque','Percage','Resultat','BrasAppui')) and types[name] not in ('App::Origin',):
                try:saved=reader.shape(source,name)
                except RuntimeError:continue
                if saved is None or saved.isNull():continue
                b=d.addObject('Part::Feature','Fixture'+name);b.Shape=saved;r.addObject(b)
                b.Visibility=name in (final_plate,'BrasAppui')
        shape,spec=model.finish_navigation_mount(api,d,r,kind);s=r.Shape.copy();s.translate(A.Vector(*offset))
        shapes[kind]=s;specs[kind]=spec
    d,r=api.doc('P70');base=api.box(d,'Plaque',(18,12,3),(-9,-6,0));r.addObject(base)
    holes=[api.box(d,'PassageAntenne',(3,4.8,5),(x-1.5,-2.4,-1)) for x in (-5,5)]
    for tool in holes:r.addObject(tool)
    base=api.boolean(d,r,base,holes);rf,specs['radio']=model.extend_radio_mount(api,d,r,base)
    for i,y in enumerate((28,-15)):
        s=r.Shape.copy();s.translate(A.Vector(-76,y,103));shapes['SupportRF'+str(i)]=s
    d,r=api.doc('P73');r.Placement=A.Placement(A.Vector(),A.Rotation(A.Vector(0,0,1),180))
    b=d.addObject('Part::Feature','FixtureP73Sauvegardee')
    fixture=reader.shape('pieces/fabriquees/P73_Guide_Faisceau_Droit_Prototype.FCStd','Ensemble')
    fixture.Placement=r.Placement.inverse().multiply(fixture.Placement);b.Shape=fixture;r.addObject(b)
    midi,specs['midi']=model.extend_midi_shelf(api,d,r,b)
    s=midi.Shape.copy();s.Placement=r.Placement.multiply(s.Placement);shapes['P73']=s
    tablet=d.getObject('TabletteMIDI').Shape.copy()
    tablet.Placement=r.Placement.multiply(tablet.Placement);shapes['TabletteMIDI']=tablet
    for name,bounds,plane,axes in [('RF',[-85.4,102.6,-71.6,114.4],'xz',[16,-17.5]),
                                 ('MIDI',[-86.4,-55.4,-55.6,-27.6],'yz',[39,63])]:
        for i,axis in enumerate(axes):
            d,r=api.doc('Collier');obj=model.collar_shape_native(d,r,'Bande',bounds,axis,plane)
            shapes['Collier'+name+str(i)]=obj.Shape.copy()
    errors=validate_shapes(shapes)
    pairs=[('CollierRF'+str(i),'SupportRF'+str(i)) for i in (0,1)]
    pairs += [('CollierMIDI'+str(i),'P73') for i in (0,1)]
    additional={name:reader.occurrence(entries[name]) for name in ['P75_Cadre','AntenneRF0','AntenneRF1','GNSS_Helical','BoutonBuzzerLED','Protection_amont','Interface']}
    routes=json.loads((VER/'routes_prototype.json').read_text('utf-8'))
    for row in routes['routes']:
        additional['Cable/'+row['id']]=reader.shape(row['fichier'],row['objet_cable'])
    replaced={'SupportGNSS','SupportSecurite','SupportRF0','SupportRF1','P73_Guide',
              'CollierAncrageRF0','CollierAncrageRF1','CollierMIDI0','CollierMIDI1'}
    for row in build['occurrences']:
        if row['parent'].startswith('sous_assemblages/') and row['occurrence'] not in replaced:
            additional['Physique/'+Path(row['parent']).stem+'/'+row['occurrence']]=reader.occurrence(row)
    checks=[]
    for a,b in pairs:
        volume=intersection(shapes[a],shapes[b]);checks.append({'a':a,'b':b,'volume_mm3':volume})
        if volume>TOL:errors.append(checks[-1])
    for a in [n for n in shapes if n.startswith('Collier') or n in ('gnss','securite','SupportRF0','SupportRF1','TabletteMIDI')]:
        for b,other in additional.items():
            volume=intersection(shapes[a],other)
            if not b.startswith('Cable/') or volume>TOL:checks.append({'a':a,'b':b,'volume_mm3':volume})
            if volume>TOL:
                common=shapes[a].common(other)
                checks[-1]['bbox_mm']=[round(getattr(common.BoundBox,k),4) for k in ['XMin','YMin','ZMin','XMax','YMax','ZMax']]
                errors.append(checks[-1])
    result={'mode':'candidat_en_memoire','conforme':not errors,'erreurs':errors,'controles':checks,'interfaces':specs,
            'qualification':'À valider','natifs_modifies':False}
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result


def final():
    build_path,routes_path=VER/'construction_prototype.json',VER/'routes_prototype.json'
    build=json.loads(build_path.read_text('utf-8'));routes=json.loads(routes_path.read_text('utf-8'))
    if not build.get('finalisation_correcte'):raise ValueError('Construction non finalisée')
    expected={r['fichier']:r['sha256'] for r in build['references']}
    expected.update(build['sources_preservees'])
    if any(not (MEC/p).is_file() or sha(MEC/p)!=digest for p,digest in expected.items()):
        raise ValueError('Natif absent ou différent de la construction')
    recipe=Path(model.__file__).name
    if build.get('recettes_sha256',{}).get(recipe)!=sha(VER/recipe):
        raise ValueError('Recette de fixation absente ou périmée dans la construction')
    reader=Reader(MEC)
    rows=[r for r in build['occurrences'] if r['parent'].startswith('sous_assemblages/')]
    entries={r['occurrence']:r for r in rows}
    collars=['CollierAncrageRF0','CollierAncrageRF1','CollierMIDI0','CollierMIDI1']
    supports=['SupportGNSS','SupportSecurite','SupportRF0','SupportRF1']
    hardware=[prefix+kind+suffix+str(i) for kind in ('GNSS','Securite') for i in (0,1)
              for prefix,suffix in [('VisSupport',''),('RondelleSupport','B'),('RondelleSupport','H'),('EcrouSupport','')]]
    if not set(collars+supports+hardware).issubset(entries):
        raise ValueError('Périmètre de fixation incomplet dans les occurrences')
    focus={n:reader.occurrence(entries[n]) for n in collars+supports+hardware}
    errors=validate_shapes({n:s for n,s in focus.items() if n not in hardware})
    collisions=[];cables={r['id'] for r in routes['routes']};obstacles=[]
    for row in rows:
        identifier=Path(row['parent']).stem+'/'+row['occurrence']
        obstacles.append((identifier,row,reader.occurrence(row)))
    checks=0
    for name,shape in focus.items():
        own=entries[name]['parent']+'#'+name
        for identifier,row,other in obstacles:
            if row['parent']+'#'+row['occurrence']==own:continue
            if not bbox_overlap(shape.BoundBox,other.BoundBox):continue
            checks+=1;volume=intersection(shape,other)
            if volume>TOL:
                collisions.append({'a':name,'b':identifier,'volume_mm3':round(volume,8)})
    support_pairs=[('SupportGNSS','Interface'),('SupportSecurite','Interface'),
                   ('SupportRF0','P75_Cadre'),('SupportRF1','P75_Cadre'),
                   ('Protection_amont','P73_Guide')]
    contacts=[]
    for a,b in support_pairs:
        if a not in entries or b not in entries:raise ValueError('Support requis absent : '+a+'/'+b)
        distance=reader.occurrence(entries[a]).distToShape(reader.occurrence(entries[b]))[0]
        contacts.append({'a':a,'b':b,'distance_mm':round(distance,8)})
        if distance>1e-4:errors.append({'appui_absent':a+'/'+b,'distance_mm':distance})
    # Lire les métadonnées sauvegardées, pas une promesse du constructeur.
    stacks=[]
    for kind,y in [('GNSS',29),('Securite',-29)]:
        for index,x in enumerate((-43,43)):
            names={'vis':'VisSupport'+kind+str(index),
                   'rondelle_basse':'RondelleSupport'+kind+'B'+str(index),
                   'rondelle_haute':'RondelleSupport'+kind+'H'+str(index),
                   'ecrou':'EcrouSupport'+kind+str(index)}
            values={key:[focus[n].BoundBox.ZMin,focus[n].BoundBox.ZMax] for key,n in names.items()}
            # Tête Z80,7..82,7 ; la tige se termine à94,7. La rondelle
            # basse porte sur OEM83, et l'écrou termine à92,9.
            expected_z={'vis':[80.7,94.7],'rondelle_basse':[82.7,83],
                        'rondelle_haute':[91,91.3],'ecrou':[91.3,92.9]}
            if any(abs(a-b)>1e-5 for key in values for a,b in zip(values[key],expected_z[key])):
                errors.append({'empilement':kind+str(index),'mesures_z_mm':values})
            stacks.append({'id':kind+str(index),'axe_mm':[x,y],'mesures_z_mm':values,
                           'saillie_mm':round(values['vis'][1]-values['ecrou'][1],8)})
    unchanged=all(sha(MEC/p)==digest for p,digest in expected.items())
    result={'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),
            'script_sha256':sha(__file__),'module_sha256':sha(model.__file__),
            'lecteur_sha256':sha(VER/'read_brep_prototype.py'),
            'construction_sha256':sha(build_path),'routes_sha256':sha(routes_path),
            'natifs_sha256':expected,'fichiers_non_modifies':unchanged,
            'occurrences_controlees':list(focus),'obstacles_controles':len(obstacles),
            'pieces_controlees':[{'objet':n,'valide':s.isValid(),'solides':len(s.Solids)}
                                for n,s in focus.items() if n not in hardware],
            'paires_intersection_calculees':checks,'contacts':contacts,'empilements':stacks,
            'colliers':collars,'erreurs':errors,'collisions':collisions,
            'conforme':not errors and not collisions and unchanged,
            'finalisation_correcte':True,'qualification':'À valider',
            'limites':['Fixations des supports et boîtier nominal seulement ; plans/lot GNSS, USL et modules électroniques non confirmés.',
                       'Bandes fermées4,6×1,2 nominales ; tête, couple/serrage, freinage et tenue physique non qualifiés.']}
    (VER/'controle_fixations_equipements_prototype.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({k:result[k] for k in ['conforme','erreurs','collisions','fichiers_non_modifies','paires_intersection_calculees']},ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidat',action='store_true');args=parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8',line_buffering=True)
    sys.exit(0 if (candidate() if args.candidat else final())['conforme'] else 1)
