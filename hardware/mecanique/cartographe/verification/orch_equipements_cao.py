"""Adaptateur FreeCAD du lot ORCH-CAO-MASSE-1, équipements uniquement.

Usage avec le Python FreeCAD 1.1 : --apply, puis --verify dans un nouveau
processus. Cette recette ne calcule aucune masse métier. Les valeurs de masse
et leurs réserves sont déclaratives dans la preuve JSON voisine.
Les fichiers fabricant originaux ne sont jamais écrits.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
import FreeCAD as A
import Part
import Sketcher
from etage_batterie_helpers import save_native, color

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
PROOF = Path(__file__).with_name('orch_cao_masse_equipements.json')
SRC = MEC / 'sources_fabricants/orch_cao_masse_equipements'
GREY, BLACK, GREEN, METAL = (.28,.30,.32), (.10,.11,.12), (.08,.42,.23), (.70,.73,.76)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(data):
    PROOF.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def meta(o, key, value):
    if key not in o.PropertiesList:
        o.addProperty('App::PropertyString', key, 'ORCH_CAOMASSE')
    setattr(o, key, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))


def bounds(shape):
    b = shape.BoundBox
    return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]


def primitive(d, typ, name, tint=GREY):
    o=d.addObject(typ, 'ORCH_'+name)
    color(o,tint)
    return o


def box(d,name,size,xyz,tint=GREY):
    o=primitive(d,'Part::Box',name,tint)
    o.Length,o.Width,o.Height=size
    o.Placement.Base=A.Vector(*xyz)
    return o


def cylinder(d,name,r,h,xyz,axis=(0,0,1),tint=METAL):
    o=primitive(d,'Part::Cylinder',name,tint)
    o.Radius=r; o.Height=h
    o.Placement=A.Placement(A.Vector(*xyz), A.Rotation(A.Vector(0,0,1),A.Vector(*axis)))
    return o


def cut(d,name,base,tool):
    o=primitive(d,'Part::Cut',name)
    o.Base=base;o.Tool=tool
    base.Visibility=False;tool.Visibility=False
    return o


def feature(d,name,shape,tint=GREY):
    o=primitive(d,'Part::Feature',name,tint);o.Shape=shape
    return o


def compound(d,name,parts):
    o=primitive(d,'Part::Compound',name);o.Links=parts
    for p in parts:p.Visibility=False
    return o


def params(d, values):
    p=d.addObject('Spreadsheet::Sheet','ORCH_Cotes')
    for row,(key,value) in enumerate(values.items(),1):
        p.set('A'+str(row),key);p.set('B'+str(row),str(value)+' mm');p.setAlias('B'+str(row),key)
    p.Visibility=False
    return p


def reset(d,root):
    # Les arbres antérieurs restent accessibles hors de l'objet référencé.
    # Ils sont exclus de l'occurrence active, sans perte de leurs paramètres.
    for o in reversed(list(d.Objects)):
        if o.Name.startswith('ORCH_'):
            d.removeObject(o.Name)
    history=d.getObject('AvantORCH') or d.addObject('App::DocumentObjectGroup','AvantORCH')
    history.Label='Construction antérieure conservée — exclue de l’occurrence active'
    if root.TypeId=='App::Part':
        for o in list(root.Group):
            if o.TypeId not in ('App::Origin','Spreadsheet::Sheet'):
                root.removeObject(o);history.addObject(o);o.Visibility=False
    history.Visibility=False


def attach(d,root,parts):
    final=compound(d,'GeometrieDocumentee',parts)
    if root.TypeId=='App::Part':root.addObject(final)
    else:
        # Basler était un import Part::Feature invalide. Le même identifiant
        # devient un composé natif lié à ses primitives et opérations cotées.
        name,label,placement=root.Name,root.Label,root.Placement
        expressions=list(root.ExpressionEngine)
        strings={k:getattr(root,k) for k in root.PropertiesList
                 if k in ('Provenance','Statut')}
        d.removeObject(name)
        root=d.addObject('Part::Compound',name);root.Links=[final]
        root.Label=label;root.Placement=placement
        for k,v in strings.items():meta(root,k,v)
        for prop,expr in expressions:root.setExpression(prop,expr)
        final.Visibility=False
    return root


def build_pm08(d,root):
    s=Part.read(str(SRC/'Holybro_CAN_PM08_Case_v003.step'))
    assert len(s.Solids)==2 and s.isValid()
    b=s.BoundBox
    # Centre du corps 45×41 historique maintenu ; pattes OEM désormais incluses.
    s.translate(A.Vector(22.5,20.5,-b.ZMin))
    return attach(d,root,[feature(d,'BoitierFabricantV003',s,METAL)])


def build_basler(d,root):
    flange=10.570258993911898  # repère optique existant conservé
    rear=flange-42.8
    p=params(d,dict(Largeur=29,Hauteur=29,LongueurFrontII=42.8,
                    EntraxeM3=21,ProfondeurM3=4,IntrusionMax=10.9))
    body=box(d,'BoitierFrontII',(29,29,42.8),(-14.5,-14.5,rear),GREY)
    body.setExpression('Length','ORCH_Cotes.Largeur')
    body.setExpression('Width','ORCH_Cotes.Hauteur')
    body.setExpression('Height','ORCH_Cotes.LongueurFrontII')
    # Trous de la face de montage : M3 nominal, filet non représenté.
    for i,(x,z) in enumerate([(-10.5,flange-8.8),(10.5,flange-8.8),(0,flange-40.3)]):
        tool=cylinder(d,'M3_'+str(i),1.5,4,(x,-14.5,z),(0,1,0))
        body=cut(d,'BoitierM3_'+str(i),body,tool)
    # Réservation d'intrusion autorisée, pas une description de l'intérieur.
    aperture=cylinder(d,'IntrusionC',12.7,10.9,(0,0,flange),(0,0,-1))
    body=cut(d,'BoitierAvecMontureC',body,aperture)
    # Positions arrière tirées du plan coté, signes adaptés au repère existant.
    # Le corps connecteur I/O est une enveloppe M8 nominale ; sa cavité exacte
    # et les contacts ne sont pas présentés comme documentés.
    m8=cylinder(d,'CorpsM8',4.0,5.3,(-5.8,-8.1,rear),(0,0,-1),METAL)
    m8cut=cut(d,'CaviteM8',m8,cylinder(d,'ReserveM8',3.0,4.0,(-5.8,-8.1,rear-5.3),(0,0,1)))
    # Enveloppe USB Micro-B et deux taraudages M2 de profondeur 4.
    usb=box(d,'FaceUSB',(8,22,0.95),(4.285,-11.525,rear-.95),METAL)
    usb=cut(d,'OuvertureUSB',usb,box(d,'ReserveUSB',(5,13,1.4),(5.785,-7.025,rear-1.1),BLACK))
    for i,y in enumerate([-9.525,8.475]):
        tool=cylinder(d,'M2_USB_'+str(i),1.0,4,(8.285,y,rear),(0,0,1))
        body=cut(d,'BoitierM2_'+str(i),body,tool)
        usb=cut(d,'FaceM2_'+str(i),usb,cylinder(d,'PassageM2_'+str(i),1.0,1.2,(8.285,y,rear-1.0)))
    return attach(d,root,[body,m8cut,usb])


def build_fan(d,root):
    p=params(d,dict(Longueur=57.8,Largeur=39,Hauteur=18,Ouverture=37,
                    EntraxeLong=43.2,EntraxeCourt=28.8))
    body=box(d,'DissipateurExterieur',(57.8,39,18),(-28.9,-19.5,0),BLACK)
    for prop,expr in [('Length','Longueur'),('Width','Largeur'),('Height','Hauteur')]:
        body.setExpression(prop,'ORCH_Cotes.'+expr)
    # Réservation extérieure d'ouverture. Profondeur et ailettes internes
    # inconnues : cette coupe est déduite, et ne sert jamais au calcul de masse.
    tool=cylinder(d,'OuvertureVentilateur',18.5,4,(0,0,14))
    body=cut(d,'CarterVentile',body,tool)
    for i,(x,y) in enumerate([(x,y) for x in [-21.6,21.6] for y in [-14.4,14.4]]):
        body=cut(d,'FixationM2_'+str(i),body,cylinder(d,'AxeM2_'+str(i),1.0,18,(x,y,0)))
    rotor=cylinder(d,'ReserveMoyeu',7,2,(0,0,14),tint=GREY)
    return attach(d,root,[body,rotor])


def build_gnss(d,root):
    s=Part.read(str(SRC/'Holybro_DroneCAN_F9P_Helical_original.stp'))
    assert len(s.Solids)==11 and s.isValid()
    s.rotate(A.Vector(),A.Vector(1,0,0),90);s.translate(A.Vector(3.45,0,14))
    body=feature(d,'BoitierHelicalFabricant',s,BLACK)
    antenna=cylinder(d,'AntenneReservation',13.75,59,(0,0,22.9),tint=BLACK)
    meta(antenna,'NatureModele','Réservation extérieure Ø27,5×59 ; jonction non démontrée')
    meta(root,'InterfaceSMAOEM',{'point_local_mm':[-31.85,0,9.2],'axe_local':[-1,0,0],
        'origine':'Face extrême du connecteur du STEP ; pas une profondeur d’accouplement garantie',
        'antenne_candidate_actuelle_mm':[0,0,22.9],'axe_antenne_candidate':[0,0,1],
        'interface_valide':False,
        'pose_directe_a_etudier':{'base_mm':[-31.85,0,9.2],'axe':[-1,0,0],
          'bbox_enveloppe_mm':[-90.85,-17.5,-4.55,25.55,17.5,22.95],
          'limite':'Plan d’appui et engagement SMA mâle inconnus ; pose horizontale, non validée'}})
    return attach(d,root,[body,antenna])


def build_iso(d,root):
    p=params(d,dict(CoqueLongueur=71.6,CoqueLargeur=72.15,Hauteur=27.4,
                    PattesLongueur=68.5,PattesLargeur=86.5))
    body=box(d,'CoqueDocumentee',(71.6,72.15,27.4),(9.2,3.925,0),BLACK)
    tabs=box(d,'PlatineFixation',(68.5,86.5,1.2),(10.75,-3.25,0),BLACK)
    # Implantation des lumières et épaisseur de tôle déduites de la photographie.
    # Les centres et largeurs exacts restent à obtenir avant fabrication du support.
    for i,(x,y) in enumerate([(x,y) for x in [25,65] for y in [-.05,80.05]]):
        tabs=cut(d,'Lumiere_'+str(i),tabs,box(d,'ReserveLumiere_'+str(i),(10,3,2),(x-5,y-1.5,-.2)))
    ttl=box(d,'BornierTTL',(9.2,26,13),(80.8,40,5),GREEN)
    rs485=box(d,'BornierRS485',(9.2,20,13),(80.8,19,5),GREEN)
    usb=box(d,'USB_B',(10,8,10),(9.2,1.925,7),METAL)
    return attach(d,root,[body,tabs,ttl,rs485,usb])


def build_ssd(d,root):
    # Garder le repère d'engagement et l'encoche existants ; corriger seulement
    # les limites externes publiées. Les épaisseurs réparties restent déduites.
    p=params(d,dict(LongueurMax=80.15,LargeurMax=22.15,HauteurMax=2.38))
    pcb=box(d,'PCB_Max',(80.15,22.15,.8),(-40.075,-11.075,1.58),GREEN)
    pcb.setExpression('Length','ORCH_Cotes.LongueurMax');pcb.setExpression('Width','ORCH_Cotes.LargeurMax')
    pcb=cut(d,'PCB_Encoche',pcb,cylinder(d,'EncocheCandidate',1.75,3,(39.98,0,1)))
    chips=box(d,'ComposantsReservation',(71,20,1.58),(-31,-10,0),BLACK)
    return attach(d,root,[pcb,chips])


def build_lens(d,root):
    # Profil extérieur du DXF fabricant, x=281.1703665714 au plan d'appui,
    # y=146.8150603672 sur l'axe. Les bagues sont des enveloppes de révolution.
    p=params(d,dict(LongueurNominale=67,DiametreMax=54,MontureC=25.4,Intrusion=4))
    profile=[(-4,0),(-4,12.7),(0,12.7),(0,19.5),(57.37,19.5),
             (60.727,26.7),(61.027,27),(66.670,27),(66.970,26.7),(66.970,0)]
    sketch=d.addObject('Sketcher::SketchObject','ORCH_ProfilDXF')
    # Plan XZ : x=rayon, z=distance au plan d'appui. Révolution autour de Z.
    sketch.Placement=A.Placement(A.Vector(),A.Rotation(A.Vector(1,0,0),90))
    pts=[A.Vector(r,z,0) for z,r in profile]
    for a,b in zip(pts,pts[1:]+pts[:1]):sketch.addGeometry(Part.LineSegment(a,b),False)
    rev=primitive(d,'Part::Revolution','CorpsRevolution',BLACK);rev.Source=sketch
    rev.Axis=A.Vector(0,0,1);rev.Base=A.Vector();rev.Angle=360;rev.Solid=True
    sketch.Visibility=False
    # Deux vis de blocage : positions 42,3/20,4 nominales ; têtes mesurables DXF.
    screws=[cylinder(d,'Blocage_'+str(i),2.5,3.75,(19.5,0,z),(1,0,0),BLACK)
            for i,z in enumerate([42.253,20.438])]
    return attach(d,root,[rev]+screws)


BUILDERS={'pm08':build_pm08,'basler':build_basler,'fan':build_fan,
          'gnss':build_gnss,'iso':build_iso,'ssd':build_ssd,'lens':build_lens}


def apply(data):
    for record in data['geometries']:
        file=ROOT/record['fichier'];d=A.openDocument(str(file));root=d.getObject(record['objet_source'])
        assert root is not None, record['reference']
        record.setdefault('etat_initial',{'sha256':sha(file),'bbox_mm':bounds(root.Shape),
                                          'forme_valide':root.Shape.isValid()})
        if record.get('constructeur'):
            reset(d,root);root=BUILDERS[record['constructeur']](d,root)
        meta(root,'ORCH_Lot','ORCH-CAO-MASSE-1')
        meta(root,'ORCH_Nature',record['traitement'])
        meta(root,'ORCH_CotesDocumentees',record['cotes_documentees'])
        meta(root,'ORCH_CotesDeduites',record['cotes_deduites'])
        meta(root,'ORCH_CotesInconnues',record['cotes_inconnues'])
        meta(root,'ORCH_Sources',record['source_ids'])
        meta(root,'ORCH_Limites',record['limites'])
        d.recompute()
        assert root.Shape.isValid(), record['reference']+' : forme finale invalide'
        root.Visibility=True
        # Les intermédiaires et l'historique ne sont pas des occurrences actives.
        active=set(o.Name for o in getattr(root,'Group',[]))
        if root.TypeId=='Part::Compound':active.update(x.Name for x in root.Links)
        for o in d.Objects:
            if o.Name.startswith('ORCH_') and o.Name not in active:o.Visibility=False
        save_native(d)
        record['sha256']=sha(file)
        record['controle_construction']={'forme_valide':root.Shape.isValid(),
            'solides':len(root.Shape.Solids),'bbox_mm':bounds(root.Shape),
            'volume_geometrique_mm3':root.Shape.Volume,
            'volume_utilisable_pour_masse':False,
            'objet_source_stable':root.Name==record['objet_source']}
        A.closeDocument(d.Name)
        print('Enregistré '+record['reference'],flush=True)
        write(data)


def verify(data):
    checks=[]
    for record in data['geometries']:
        file=ROOT/record['fichier'];before=sha(file);d=A.openDocument(str(file));o=d.getObject(record['objet_source'])
        d.recompute()
        b=bounds(o.Shape);expected=record['controle_construction']['bbox_mm']
        item={'reference':record['reference'],'objet_source':o.Name,'sha256':before,
              'forme_valide':o.Shape.isValid(),'solides':len(o.Shape.Solids),
              'bbox_mm':b,'bbox_reproductible':all(abs(a-c)<1e-6 for a,c in zip(b,expected)),
              'erreurs_document':[x.Name for x in d.Objects if 'Invalid' in x.State or 'Error' in x.State]}
        A.closeDocument(d.Name);item['aucune_sauvegarde_reouverture']=before==sha(file)
        checks.append(item)
    sources=[{'id':s['id'],'sha256_coherent':s.get('sha256')==sha(ROOT/s['fichier'])}
             for s in data['sources'] if s.get('fichier')]
    data['validation']={'date_utc':datetime.now(timezone.utc).isoformat(),'environnement':
        {'os':'Windows','architecture':'amd64','freecad':A.Version()},
        'protocole':'Nouveau processus --verify après --apply ; réouverture, recalcul, contrôle BREP, identifiants et empreintes ; fermeture sans sauvegarde.',
        'controles':checks,'sources':sources,
        'conforme':all(c['forme_valide'] and c['bbox_reproductible'] and c['aucune_sauvegarde_reouverture']
                       and not c['erreurs_document'] for c in checks) and all(s['sha256_coherent'] for s in sources),
        'qualification_physique':False,
        'limites':'Contrôles des pièces seules. Assemblages, accouplements, collisions, fixations et routes sont contrôlés par l’intégrateur.'}
    data['finalisation_correcte']=data['validation']['conforme']
    write(data)
    print(json.dumps({'conforme':data['validation']['conforme'],'pieces':len(checks)},ensure_ascii=True))
    if not data['validation']['conforme']:raise SystemExit(2)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--verify',action='store_true')
    args=parser.parse_args();assert args.apply != args.verify,'Choisir --apply ou --verify'
    data=json.loads(PROOF.read_text(encoding='utf-8-sig'))
    for s in data['sources']:
        if s.get('fichier'):
            actual=sha(ROOT/s['fichier'])
            if s.get('sha256'):assert actual==s['sha256'],'Source fabricant modifiée : '+s['id']
            else:s['sha256']=actual
    if args.apply:apply(data)
    else:verify(data)
    sys.stdout.flush();sys.stderr.flush()
    os._exit(0)
