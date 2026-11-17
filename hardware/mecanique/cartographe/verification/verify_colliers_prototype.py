"""Passage des réserves, liaisons et retenues de boîtiers et d'antennes.

Contrôle BRep des natifs sauvegardés, sans les ouvrir ni les réécrire. Les bandes
témoins fermées représentent leur section nominale 4,6 × 1,2 mm ; les coins
extérieurs conservateurs ne constituent pas un modèle de fabrication du collier.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import FreeCAD as A
import Part
from read_brep_prototype import Reader

VER=Path(__file__).resolve().parent
MEC=VER.parent
ROOT=MEC.parents[2]
OUTPUT=VER/'controle_colliers_prototype.json'
WIDTH=4.6
THICKNESS=1.2
EPS_VOLUME=1e-5
MAX_PERIMETER=math.pi*50.0
# Poses nominales mesurées sur les bandes, puis recontrôlées sur chaque natif.
HEAD_POSES = {
  "P77_Berceau_Reserve_USB_Prototype/NO": [
    0.7619393177594597,
    -0.6476484200955401,
    0.0,
    -57.82001451345898,
    -0.6476484200955401,
    -0.7619393177594598,
    -0.0,
    19.609286140834666,
    0.0,
    0.0,
    -1.0,
    -1.15,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P77_Berceau_Reserve_USB_Prototype/SO": [
    3.3306690738754696e-16,
    0.64764842009554,
    -0.7619393177594594,
    -71.26583972346684,
    1.1102230246251565e-16,
    -0.7619393177594596,
    -0.64764842009554,
    -21.063689960552267,
    -0.9999999999999999,
    1.1102230246251565e-16,
    -2.220446049250313e-16,
    18.470000000000002,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P77_Berceau_Reserve_USB_Prototype/E": [
    1.0,
    0.0,
    0.0,
    -29.649999999999995,
    0.0,
    -1.0,
    0.0,
    3.8,
    0.0,
    0.0,
    -1.0,
    -1.1500000000000015,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P75_P72_BAS": [
    0.0,
    0.0,
    1.0,
    -84.92,
    1.0,
    0.0,
    0.0,
    52.35,
    0.0,
    1.0,
    0.0,
    55.7,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P75_P72_HAUT": [
    0.8430506551276907,
    0.0,
    -0.5378341685768686,
    -105.22249594545812,
    -0.5378341685768686,
    -2.220446049250313e-16,
    -0.8430506551276908,
    47.430310097337795,
    0.0,
    1.0000000000000002,
    -2.220446049250313e-16,
    81.2,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P73_P72_DIST_AV": [
    -0.7071067811865475,
    0.7071067811865477,
    0.0,
    -86.00770546792677,
    -0.7071067811865477,
    -0.7071067811865475,
    0.0,
    -47.133693930909004,
    0.0,
    0.0,
    1.0,
    72.58,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P73_P72_DIST_ARR": [
    -0.07582592011573364,
    0.7071067811865475,
    0.7030294658395213,
    -74.56071865946285,
    -0.07582592011573358,
    -0.7071067811865479,
    0.7030294658395211,
    -62.186707122445085,
    0.9942338053381634,
    5.551115123125783e-17,
    0.10723404460708919,
    58.84422495519836,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P73_P72_DIST_MONTANT": [
    0.6873574075965417,
    5.551115123125783e-17,
    -0.7263193472723699,
    -99.11394572568784,
    -0.7263193472723699,
    -4.440892098500626e-16,
    -0.6873574075965416,
    47.05932263089684,
    -2.7755575615628914e-16,
    1.0,
    -2.220446049250313e-16,
    39.7,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P73_P72_F01": [
    0.0,
    1.0000000000000002,
    5.551115123125783e-17,
    -91.8,
    0.10950769961125922,
    0.0,
    -0.9939859474488815,
    -48.035664316001224,
    -0.9939859474488815,
    5.551115123125783e-17,
    -0.10950769961125939,
    -7.884882276064596,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P73_P72_F38_POS": [
    0.5839145527640364,
    0.6917144638660748,
    -0.4249410494984502,
    -98.32177421176102,
    0.704783116878267,
    -0.6917144638660748,
    -0.15751780420582387,
    -96.3302777599506,
    -0.40289521371410025,
    -0.20751433915982295,
    -0.8914108176420859,
    59.006999400713134,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P73_P72_F38_NEG": [
    0.7071067811865475,
    0.7071067811865477,
    0.0,
    -92.80746224446587,
    0.7071067811865477,
    -0.7071067811865475,
    0.0,
    -102.43345070744809,
    0.0,
    0.0,
    -1.0,
    54.42,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "P78_P64": [
    2.220446049250313e-16,
    0.0,
    1.0,
    95.1,
    0.0,
    -1.0,
    0.0,
    82.4,
    1.0,
    0.0,
    -2.220446049250313e-16,
    33.875,
    0.0,
    0.0,
    0.0,
    1.0
  ],
  "QS8_P76": [1,0,0,111.23516522579585,0,-1,0,-16.199999999999985,0,0,-1,-63.08000000000001,0,0,0,1],
  "ANTENNE_RF0": [0.4685212856658081,0,0.8834522085987776,-75.8617735783185,0.6246950475544266,0.707106781186549,-0.3312945782245318,18.907647872139115,-0.6246950475544294,0.7071067811865459,0.33129457822453323,144.71834059084316,0,0,0,1],
  "ANTENNE_RF1": [1,0,0,-82.15000000000003,0,-1,0,-13.700000000000024,0,0,-1,101.60000000000002,0,0,0,1]
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def overlap(a,b):
    return all(min(getattr(a,k+'Max'),getattr(b,k+'Max'))-
               max(getattr(a,k+'Min'),getattr(b,k+'Min'))>1e-6 for k in 'XYZ')


def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def hull(points):
    points=sorted(set(points));lower=[];upper=[]
    for p in points:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def offset(poly,distance):
    lines=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        lines.append(((a[0]+distance*dy/length,a[1]-distance*dx/length),(dx,dy)))
    result=[]
    for (p,a),(q,b) in zip(lines[-1:]+lines[:-1],lines):
        den=a[0]*b[1]-a[1]*b[0]
        scale=((q[0]-p[0])*b[1]-(q[1]-p[1])*b[0])/den
        result.append((p[0]+scale*a[0],p[1]+scale*a[1]))
    return result


def frame(origin,normal):
    n=A.Vector(*normal);n.normalize()
    u=A.Vector(0,0,1).cross(n) if abs(n.z)<.9 else A.Vector(1,0,0)
    u.normalize();v=n.cross(u);v.normalize()
    matrix=A.Matrix(u.x,v.x,n.x,0,u.y,v.y,n.y,0,u.z,v.z,n.z,0,0,0,0,1)
    return A.Placement(A.Vector(*origin),A.Rotation(matrix)),u,v,n


def polygon_face(poly):
    points=[A.Vector(x,y,-WIDTH/2) for x,y in poly]
    return Part.Face(Part.makePolygon(points+[points[0]]))


def band_polygon(inner,outer,pose):
    face=polygon_face(inner)
    inside=face.extrude(A.Vector(0,0,WIDTH));inside.Placement=pose
    shape=polygon_face(outer).cut(face).extrude(A.Vector(0,0,WIDTH));shape.Placement=pose
    length=sum(math.dist(a,b) for a,b in zip(inner,inner[1:]+inner[:1]))
    return shape,inside,length


def rectangle_band(a,b,bottom,top,bevel=0):
    a,b=A.Vector(*a),A.Vector(*b);u=b-a;length=u.Length;u.normalize()
    n=u.cross(A.Vector(0,0,1))
    matrix=A.Matrix(u.x,0,n.x,0,u.y,0,n.y,0,u.z,1,n.z,0,0,0,0,1)
    pose=A.Placement(a,A.Rotation(matrix))
    inner=[(.6,bottom),(length-.6,bottom),(length-.6,top),(.6,top)]
    outer=[(-.6,bottom-THICKNESS),(length+.6,bottom-THICKNESS),
           (length+.6,top+THICKNESS),(-.6,top+THICKNESS)]
    if bevel:
        inner=[(.6,bottom),(length-.6,bottom),(length-.6,top-bevel),
               (length-.6-bevel,top),(.6+bevel,top),(.6,top-bevel)]
        outer=offset(inner,THICKNESS)
    return band_polygon(inner,outer,pose)


class SavedReader(Reader):
    def __init__(self,substitutions):
        super().__init__(MEC);self.substitutions=substitutions

    def resolve(self,path):
        absolute=(MEC/path).resolve()
        return self.substitutions.get(absolute,absolute)

    def xml(self,path):return super().xml(self.resolve(path))
    def placement(self,path,name):return super().placement(self.resolve(path),name)
    def shape(self,path,name):return super().shape(self.resolve(path),name)


def collisions(shape,obstacles):
    result=[]
    for name,obstacle in obstacles:
        if not overlap(shape.BoundBox,obstacle.BoundBox):continue
        for index,solid in enumerate(obstacle.Solids):
            if not overlap(shape.BoundBox,solid.BoundBox):continue
            if shape.distToShape(solid)[0]>1e-6:continue
            common=shape.common(solid)
            if common.Volume>EPS_VOLUME:
                result.append((name,index,common,solid))
    return result


def locate_head(band,obstacles,preferred=None):
    """Enveloppe fabricant 7,3 × 7,6 × 5,9, attachée à une plage droite.

    L'intersection avec sa propre bande est l'engagement dans la serrure ;
    aucune autre interférence n'est admise. Le positionnement reste libre sur
    les plages droites avant serrage, sans modifier aucun support ou câble.
    """
    if preferred is not None:
        pose=A.Placement(A.Matrix(*preferred))
        head=Part.makeBox(7.3,7.6,5.9);head.Placement=pose
        if head.common(band).Volume<=EPS_VOLUME:
            raise ValueError('Tête nominale sans engagement dans sa bande')
        if collisions(head,obstacles):
            raise ValueError('Tête nominale en collision avec un autre objet')
        return head,preferred
    for face in sorted(band.Faces,key=lambda f:f.Area,reverse=True):
        if type(face.Surface).__name__!='Plane' or len(face.Edges)!=4:continue
        width_edges=[e for e in face.Edges if abs(e.Length-WIDTH)<1e-5]
        long_edges=[e for e in face.Edges if e.Length>=7.3]
        if not width_edges or not long_edges:continue
        edge=width_edges[0];v=edge.Vertexes[-1].Point-edge.Vertexes[0].Point;v.normalize()
        a,b,c,d=face.ParameterRange;n=face.normalAt((a+b)/2,(c+d)/2);n.normalize()
        u=v.cross(n);u.normalize();length=max(e.Length for e in long_edges)
        for fraction in (0,-.35,.35):
            centre=face.CenterOfMass+u*(fraction*(length-7.3))
            matrix=A.Matrix(u.x,v.x,n.x,0,u.y,v.y,n.y,0,u.z,v.z,n.z,0,0,0,0,1)
            pose=A.Placement(centre-u*3.65-v*3.8-n*.2,A.Rotation(matrix))
            head=Part.makeBox(7.3,7.6,5.9);head.Placement=pose
            if not collisions(head,obstacles):return head,pose.toMatrix().A
    raise ValueError('Aucune plage droite disponible pour la tête fabricant')


def around_supports(reader,paths,obstacles,origin,normal,names):
    """Enveloppe des sections locales ; inclure explicitement tout objet capturé.

    Une collision ne devient jamais acceptable : la bande doit être reconstruite
    autour de la section entière concernée puis contrôlée de nouveau. Le domaine
    borné et le périmètre empêchent une enveloppe artificiellement illimitée.
    """
    pose,u,v,n=frame(origin,normal);o=A.Vector(*origin)
    slab=Part.makeBox(80,80,WIDTH,A.Vector(-40,-40,-WIDTH/2));slab.Placement=pose
    points=[];captured=[]
    def add(shape,near=None):
        section=shape.common(slab)
        if not section.Solids:raise ValueError('Support absent de la tranche')
        if near is not None:
            section=min(section.Solids,key=lambda s:s.distToShape(Part.Vertex(near))[0])
        for edge in section.Edges:
            for point in edge.discretize(Deflection=.01):
                q=point-o;points.append((q.dot(u),q.dot(v)))
    for prefix,name in names:
        ref=next(k for k in paths if k.startswith(prefix))
        shape=reader.shape(paths[ref],name)
        shape.Placement=reader.placement(paths[ref],'Ensemble').multiply(shape.Placement)
        add(shape);captured.append(prefix+'/'+name)
    for iteration in range(8):
        contour=hull(points)
        if max(max(abs(x),abs(y)) for x,y in contour)>=39.9:
            raise ValueError('Projection tronquée par le domaine de contrôle')
        inner,outer=offset(contour,.08),offset(contour,THICKNESS+.08)
        shape,inside,length=band_polygon(inner,outer,pose)
        hits=collisions(shape,obstacles)
        if not hits:
            return shape,inside,length,sorted(set(captured)),iteration
        for name,index,common,solid in hits:
            for component in common.Solids:add(solid,component.CenterOfMass)
            captured.append(name)
    raise ValueError('Boucle encore en collision après huit constructions : '+
                     str([(name,round(c.Volume,6)) for name,i,c,s in hits]))


def section_loop(shapes,origin,normal,components):
    """Contour borné des seules sections explicitement retenues.

    Les solides superposés de la réservation d'antenne sont intersectés
    séparément : un common sur leur composé peut perdre une section OCCT.
    """
    pose,u,v,n=frame(origin,normal);o=A.Vector(*origin)
    slab=Part.makeBox(100,100,WIDTH,A.Vector(-50,-50,-WIDTH/2));slab.Placement=pose
    points=[];sections=[]
    for name,near in components:
        pieces=[]
        for solid in shapes[name].Solids:
            pieces.extend(solid.common(slab).Solids)
        if not pieces:raise ValueError('Section de retenue absente : '+name)
        if near is not None:
            pieces=[min(pieces,key=lambda s:s.distToShape(Part.Vertex(A.Vector(*near)))[0])]
        section=Part.makeCompound(pieces)
        for edge in section.Edges:
            for p in edge.discretize(Deflection=.01):
                q=p-o;points.append((q.dot(u),q.dot(v)))
        sections.append((name,section))
    contour=hull(points)
    if max(max(abs(x),abs(y)) for x,y in contour)>=49.9:
        raise ValueError('Section tronquée par la tranche de retenue')
    inner=offset(contour,.08)
    shape,inside,length=band_polygon(inner,offset(contour,1.28),pose)
    return shape,inside,length,sections,slab,inner


def capture_sections(inside,sections):
    result=[]
    for name,section in sections:
        outside=section.cut(inside).Volume
        result.append(dict(occurrence=name,volume_section_mm3=section.Volume,
                           volume_hors_boucle_mm3=outside,capture=outside<=EPS_VOLUME))
    return result


def equipment_loops(shapes):
    """Trois retenues nominales, dont deux réemplois physiques explicites."""
    result=[]
    for tag,origin,normal,components in [
        ('QS8_P76',(115,-20,-50),(0,-1,0),[
            ('BerceauQS8',(115,-20,-60)),('QS8_manuel',(113,-20,-50)),
            ('P73_Guide',(123,-20,-40)),('F37_POS',(128,-20,-40))]),
        ('ANTENNE_RF0',(-78,28,141),(0,1,1),[
            ('P75_Cadre',(-80,24,145)),('AntenneRF0',None)])]:
        shape,inside,length,sections,slab,inner=section_loop(shapes,origin,normal,components)
        captures=capture_sections(inside,sections)
        row=dict(collier_id=tag,collier_physique_id=tag,type_collier='T50R',
            reference_achat='111-05012',largeur_mm=WIDTH,epaisseur_mm=THICKNESS,
            origine_mm=list(origin),normale=list(normal),interieur_plan_mm=inner,
            valide=shape.isValid(),solides=len(shape.Solids),perimetre_interieur_mm=length,
            sections=captures,capture_corps=all(r['capture'] for r in captures),
            partage_faisceau=tag=='QS8_P76',partage_collier_natif=False,
            stations_partagees=[],passage=True)
        if tag=='QS8_P76':
            row['limite_interface']='Réservation monobloc 42×24×15 mm sans face de joint ; bande Y[-22,3;-17,7]. Demi-corps fixe, séparation et accouplement/extraction manuels non démontrables. Identifier le joint et le demi-corps sur lot ; revoir la pose si cette plage gêne la manœuvre.'
        else:
            row['limite_interface']='Retenue nominale au P75 près du haut du boîtier, plan incliné à Z141 ; admissibilité de la zone de serrage, matériau et effet RF à valider sur antenne réelle.'
        result.append((tag,shape,inside,length,row))
    # La boucle native existante ferme le sandwich P70 / antenne horizontale /
    # P75. Le brin de 60 mm dépasse suivant Y : seule la section serrée, comprise
    # dans la largeur de la bande, doit être capturée. Aucune seconde bande.
    shape=shapes['CollierAncrageRF1'];faces=[f for f in shape.Faces if len(f.Wires)==2]
    if len(faces)!=2:raise ValueError('Profil fermé de la boucle RF1 non identifiable')
    face=min(faces,key=lambda f:f.CenterOfMass.y)
    wire=min(face.Wires,key=lambda w:Part.Face(w).Area)
    inside=Part.Face(wire).extrude(A.Vector(0,WIDTH,0))
    slab=Part.makeBox(80,WIDTH,80,A.Vector(-115,-19.8,85))
    antenna_sections=[]
    for solid in shapes['AntenneRF1'].Solids:
        antenna_sections.extend(solid.common(slab).Solids)
    captures=capture_sections(inside,[('AntenneRF1',Part.makeCompound(antenna_sections))])
    contacts=[]
    for name in ('SupportRF1','P75_Cadre'):
        a=Part.makeCompound(antenna_sections);b=shapes[name].common(slab)
        distance,pairs,details=a.distToShape(b);common=a.common(b)
        contact_z=a.BoundBox.ZMin if name=='SupportRF1' else a.BoundBox.ZMax
        points=[list(p) for pair in pairs for p in pair]
        on_face=any(abs(p[2]-contact_z)<=1e-6 for p in points)
        contacts.append(dict(occurrence=name,distance_mm=distance,
            volume_commun_mm3=common.Volume,aire_contact_mm2=common.Area,
            longueur_contact_mm=common.Length,points_contact_mm=points,
            face_appui='inférieure' if name=='SupportRF1' else 'supérieure',
            cote_appui_z_mm=contact_z,
            appui=distance<=1e-6 and common.Volume<=EPS_VOLUME and on_face))
    length=wire.Length
    row=dict(collier_id='ANTENNE_RF1',collier_physique_id='CollierAncrageRF1',
        type_collier='T50R',reference_achat='111-05012',largeur_mm=WIDTH,epaisseur_mm=THICKNESS,
        origine_mm=[0,-17.5,0],normale=[0,-1,0],valide=shape.isValid(),solides=len(shape.Solids),
        perimetre_interieur_mm=length,sections=captures,contacts=contacts,
        capture_corps=bool(antenna_sections) and all(r['capture'] for r in captures) and all(r['appui'] for r in contacts),
        partage_faisceau=False,partage_collier_natif=True,stations_partagees=[],passage=True,
        limite_interface='Même boucle native que l’ancrage RF1 au P75 ; section de boîtier en sandwich au contact du P70 et du P75. Serrage et tenue physiques À valider ; pas d’enveloppement de la longueur entière de l’antenne.')
    result.append(('ANTENNE_RF1',shape,inside,length,row))
    return result


def run(args):
    build_path=VER/'construction_prototype.json';routes_path=VER/'routes_prototype.json'
    contract_path=VER/'retenues_faisceaux_prototype.json'
    build=json.loads(build_path.read_text('utf8'));routes=json.loads(routes_path.read_text('utf8'))['routes']
    contract=json.loads(contract_path.read_text('utf8'))
    substitutions={}
    refs={r['reference']:r for r in build['references']}
    if args.candidats:
        backup=ROOT/'.runtime/finalisation_prototype/avant/hardware/mecanique/cartographe'
        baseline={r['fichier'] for r in build['references']}|set(build['sources_preservees'])
        baseline|={o['parent'] for o in build['occurrences']}
        for relative in baseline:
            if (backup/relative).is_file():
                substitutions[(MEC/relative).resolve()]=backup/relative
        for ref in refs:
            if not ref.startswith(('P72_','P73_','P75_','P77_','P78_')):continue
            directory='retenues_corrections' if ref.startswith(('P72_','P73_')) else 'retenues_integrees'
            if ref.startswith(('P77_','P78_')):directory='colliers_usb'
            path=ROOT/'.runtime'/directory/(ref+'.FCStd')
            if path.is_file():substitutions[(MEC/refs[ref]['fichier']).resolve()]=path
    reader=SavedReader(substitutions)
    if not args.candidats:
        if not build.get('finalisation_correcte'):
            raise ValueError('Construction non finalisée')
        declared={r['fichier']:r['sha256'] for r in build['references']}
        declared.update(build['sources_preservees'])
        if any(sha(MEC/p)!=h for p,h in declared.items()):
            raise ValueError('Natif différent de la construction déclarée')
        recipes=build.get('recettes_sha256',{})
        if not recipes or any(Path(p).name!=p or sha(VER/p)!=h for p,h in recipes.items()):
            raise ValueError('Recette différente de la construction déclarée')
    files={r['fichier']:sha(reader.resolve(r['fichier'])) for r in build['references']}
    files.update({p:sha(reader.resolve(p)) for p in build['sources_preservees']})
    inputs={p.name:sha(p) for p in (build_path,routes_path,contract_path)}
    paths={ref:row['fichier'] for ref,row in refs.items() if ref.startswith(('P72_','P73_','P75_','P77_','P78_'))}
    ids={r['id'] for r in routes};obstacles=[];occurrence_shapes={}
    for row in build['occurrences']:
        if not row['parent'].startswith('sous_assemblages/'):continue
        if 'SA07_' in row['parent'] and row['occurrence'] in ids:continue
        shape=reader.occurrence(row)
        if args.candidats and row['occurrence']=='Isolation':
            shape=shape.cut(Part.makeBox(6,4.8,5,A.Vector(81,76.2,35)))
        obstacles.append((row['parent']+'#'+row['occurrence'],shape))
        occurrence_shapes[row['occurrence']]=shape
    obstacles.extend((r['id'],reader.shape(r['fichier'],r['objet_cable'])) for r in routes)
    occurrence_shapes.update({n:s for n,s in obstacles if n in ids})
    report=dict(schema_version=1,date_utc=datetime.now(timezone.utc).isoformat(),
        script_fichier='verification/'+Path(__file__).name,script_sha256=sha(__file__),
        construction_sha256=inputs[build_path.name],routes_sha256=inputs[routes_path.name],
        contrat_sha256=inputs[contract_path.name],natifs_sha256=files,
        bande={'largeur_mm':WIDTH,'epaisseur_mm':THICKNESS,'volume_commun_max_mm3':EPS_VOLUME,
            'longueur_fabricant_mm':202,'diametre_faisceau_max_fabricant_mm':50,
            'borne_perimetre_interieur_mm':MAX_PERIMETER,
            'justification_borne':'Condition nécessaire de longueur : périmètre du faisceau circulaire maximal fabricant Ø50. Le rayon réel et les tolérances restent à valider au montage.',
            'tete_mm':[7.3,7.6,5.9],
            'source_fabricant':'https://www.hellermanntyton.com/products/cable-ties-inside-serrated/t50r/111-05012'},
        protocole='Bandes fermées 4,6 × 1,2 mm ; sections et passages OEM sauvegardés ; intersections OCCT exhaustives contre toutes les occurrences physiques et les 53 gaines. Les liaisons communes nomment chaque section capturée.',
        candidats=bool(args.candidats),colliers=[],liaisons=[],retenues_boitiers_antennes=[],tetes=[],collisions=[],erreurs=[],
        finalisation_correcte=False,qualification='À valider',limites=[
            'Enveloppe de tête fabricant contrôlée ; languette libre, rayon de pliage, insertion et serrage à vérifier sur matériel.',
            'Colliers à enfiler avant fermeture des plateaux ; pas de qualification de résistance, vibration, abrasion ou fluage.',
            'Aucune longueur de coupe, quantité réellement posée ou capacité de serrage qualifiée par cette preuve.'])
    samples=[]
    f41=next(r for r in contract['routes'] if r['id']=='F41')
    from verify_retenues_faisceaux_prototype import get_station
    for name,a,b,top in [('NO',(-68.5,23.7,0),(-46.5,5,0),26.5),
                         ('SO',(-68.5,-23.7,0),(-46.5,-5,0),29.79),
                         ('E',(-52,0,0),(0,0,0),29.79)]:
        tag='P77_Berceau_Reserve_USB_Prototype/'+name
        shape,inside,length=rectangle_band(a,b,-.15,top,bevel=4 if name=='E' else 0)
        entries=[e for e in f41['retenues'] if e.get('collier_id')==tag]
        stations=[];support=None
        for entry in entries:
            point,station,occurrence=get_station(reader,refs,build['occurrences'],entry)
            support=occurrence['parent']+'#'+occurrence['occurrence']
            contained=inside.isInside(point,1e-6,True)
            stations.append(dict(cable='F41',station_id=entry['station_id'],point_mm=list(point),
                                 centre_dans_boucle=contained))
        hits=collisions(shape,obstacles)
        row=dict(collier_id=tag,support=support,stations=stations,valide=shape.isValid(),
            solides=len(shape.Solids),passage_lumieres=not hits,enveloppement_pile=bool(stations) and
            all(s['centre_dans_boucle'] for s in stations),perimetre_interieur_mm=length,
            passages_plateau_xy_mm=[list(a[:2]),list(b[:2])])
        report['colliers'].append(row);samples.append((tag,shape))
    definitions=[
        ('P75_P72_BAS',(-98,56,59.5),(0,0,1),[('P72','VoletHaut'),('P75','RepriseP72Bas'),('P75','MontanteF41')]),
        ('P75_P72_HAUT',(-98,56,85),(0,0,1),[('P72','VoletHaut'),('P75','RepriseP72Haut'),('P75','MontanteF41')]),
        ('P73_P72_DIST_AV',(-89,-55.5,66.5),(1,-1,0),[('P72','RepriseGaucheF38'),('P73','AppuiTerminalP72')]),
        ('P73_P72_DIST_ARR',(-89,-82,66.5),(1,-1,0),[('P72','RepriseGaucheF38'),('P73','AppuiTerminalP001')]),
        ('P73_P72_DIST_MONTANT',(-86,61.5,43.5),(0,0,1),[('P72','VoletHaut'),('P73','ContactESCArriereP72')]),
        ('P73_P72_F01',(-88,-42,-12.5),(1,0,0),[('P72','TalonF01Gauche'),('P73','RubanF01Pos')]),
        ('P73_P72_F38_POS',(-89,-94,64),(1,-1,-.3),[('P72','RepriseGaucheF38'),('P73','RubanF38Pos')]),
        ('P73_P72_F38_NEG',(-89,-104,64),(1,-1,0),[('P72','RepriseGaucheF38'),('P73','RubanF38Neg')])]
    for tag,origin,normal,names in definitions:
        try:
            shape,inside,length,captured,iterations=around_supports(reader,paths,obstacles,origin,normal,names)
            # Seules les gaines explicitement revues et les supports fixes de
            # cette liaison peuvent entrer dans une boucle commune. Une carte,
            # un capteur isolé ou un équipement ne devient pas serrable parce
            # qu'une enveloppe géométrique peut l'englober.
            allowed_cables={'AIRY','F41','F38_NEG','F31','F32','F01_POS'}
            allowed_occurrences={'P72_Guide','P73_Guide','P75_Cadre',
                'VisGuideMilieu0','RondelleGuideMilieu0','EcrouGuideMilieu0'}
            unexpected=[value for value in captured if not (
                value.startswith(('P72/','P73/','P75/')) or value in allowed_cables or
                value.startswith('sous_assemblages/SA07_Prototype_Faisceaux.FCStd#') and
                value.split('#')[-1] in allowed_occurrences)]
            if unexpected:raise ValueError('Section non autorisée dans la liaison : '+str(unexpected))
            shared=[]
            for route in contract['routes']:
                for entry in route['retenues']:
                    if entry['collier_id']!=tag:continue
                    point,native,occurrence=get_station(reader,refs,build['occurrences'],entry)
                    if not inside.isInside(point,1e-6,True):
                        raise ValueError('Station partagée hors largeur ou intérieur du collier : '+entry['station_id'])
                    shared.append(dict(cable=route['id'],station_id=entry['station_id'],
                                       point_mm=list(point),centre_dans_boucle=True))
            report['liaisons'].append(dict(collier_id=tag,origine_mm=origin,normale=normal,
                valide=shape.isValid(),solides=len(shape.Solids),perimetre_interieur_mm=length,
                captures=captured,iterations=iterations,stations_partagees=shared,
                deja_compte_faisceau=bool(shared)))
            samples.append((tag,shape))
            print(tag,'OK',round(length,3),flush=True)
        except Exception as exc:report['erreurs'].append(dict(collier=tag,message=str(exc)))
    shape,inside,length=rectangle_band((84,78.6,0),(94.7,78.6,0),34.75,40.3)
    report['liaisons'].append(dict(collier_id='P78_P64',valide=shape.isValid(),solides=len(shape.Solids),
        perimetre_interieur_mm=length,passage='Lumière (84;78,6), gorge Z40,3..41,5 et bord X94'))
    samples.append(('P78_P64',shape))
    # Les occurrences de bande native sont exclues seulement de leur propre
    # comparaison ; les autres corps et toutes les autres bandes restent testés.
    def obstacles_for(tag):
        return [(name,shape) for name,shape in obstacles if not (
            tag=='ANTENNE_RF1' and name.endswith('#CollierAncrageRF1'))]
    for tag,shape,inside,length,row in equipment_loops(occurrence_shapes):
        if tag=='QS8_P76':
            for route in contract['routes']:
                for entry in route['retenues']:
                    if entry['collier_id']!=tag:continue
                    point,native,occurrence=get_station(reader,refs,build['occurrences'],entry)
                    if not inside.isInside(point,1e-6,True):
                        raise ValueError('Station partagée QS8 hors boucle : '+entry['station_id'])
                    row['stations_partagees'].append(dict(cable=route['id'],station_id=entry['station_id'],
                        point_mm=list(point),centre_dans_boucle=True))
            if len(row['stations_partagees'])!=1 or row['stations_partagees'][0]['station_id']!='F37_POS_-20':
                raise ValueError('Réemploi du collier F37_POS_-20 non établi')
        hits=collisions(shape,obstacles_for(tag));row['passage']=not hits
        report['retenues_boitiers_antennes'].append(row);samples.append((tag,shape))
        print(tag,'OK',round(length,3),flush=True)
    for tag,shape in samples:
        for name,index,common,solid in collisions(shape,obstacles_for(tag)):
            report['collisions'].append(dict(collier=tag,obstacle=name,solide=index,volume_mm3=common.Volume))
    for i,(tag,shape) in enumerate(samples):
        for other_tag,other in samples[i+1:]:
            if overlap(shape.BoundBox,other.BoundBox):
                common=shape.common(other)
                if common.Volume>EPS_VOLUME:
                    report['collisions'].append(dict(collier=tag,obstacle=other_tag,volume_mm3=common.Volume))
    heads=[]
    for tag,shape in samples:
        try:
            if tag not in HEAD_POSES:raise ValueError('Pose nominale de tête absente')
            head,matrix=locate_head(shape,obstacles_for(tag)+[(n,s) for n,s in samples if n!=tag]+heads,HEAD_POSES[tag])
            heads.append((tag+'/Tete',head))
            report['tetes'].append(dict(collier_id=tag,dimensions_mm=[7.3,7.6,5.9],matrice=matrix,
                valide=head.isValid(),solides=len(head.Solids),interference_avec_bande_propre='Engagement intentionnel dans la serrure'))
        except Exception as exc:report['erreurs'].append(dict(collier=tag,message=str(exc)))
    for row in report['retenues_boitiers_antennes']:
        row['tete_controlee']=any(r['collier_id']==row['collier_id'] for r in report['tetes'])
        row['sans_collision']=row['passage'] and not any(r['collier']==row['collier_id'] or r['obstacle']==row['collier_id'] for r in report['collisions'])
        if not row['capture_corps'] or not row['tete_controlee'] or not row['sans_collision']:
            report['erreurs'].append(dict(collier=row['collier_id'],message='Retenue de corps, passage ou tête non conforme'))
    for row in report['colliers']+report['liaisons']+report['retenues_boitiers_antennes']:
        if not row['valide'] or row['solides']!=1 or row['perimetre_interieur_mm']>MAX_PERIMETER:
            report['erreurs'].append(dict(collier=row['collier_id'],message='Bande non valide ou périmètre supérieur à la borne fabricant π×50mm'))
    if len(report['colliers'])!=3 or len(report['liaisons'])!=9 or len(report['retenues_boitiers_antennes'])!=3 or len(report['tetes'])!=15 or not all(
            c['enveloppement_pile'] and c['passage_lumieres'] for c in report['colliers']):
        report['erreurs'].append(dict(message='Couverture des quinze retenues incomplète'))
    report['fichiers_non_modifies']=all(sha(reader.resolve(p))==h for p,h in files.items()) and all(
        sha(VER/p)==h for p,h in inputs.items())
    report['comptage']=dict(colliers_reserve=3,liaisons_supports=9,
        liaisons_deja_comptees_faisceaux=sum(bool(r.get('deja_compte_faisceau')) for r in report['liaisons']),
        liaisons_supplementaires=sum(not r.get('deja_compte_faisceau',False) for r in report['liaisons']),
        retenues_boitiers_antennes=3,retenues_corps_deja_comptees_faisceaux=1,
        retenues_corps_deja_comptees_ancrages_natifs=1,retenues_corps_supplementaires=1,
        bandes_controlees=15,tetes_controlees=len(report['tetes']))
    report['finalisation_correcte']=True
    report['conforme']=not report['erreurs'] and not report['collisions'] and report['fichiers_non_modifies']
    output=ROOT/'.runtime/colliers_usb/controle_colliers_prototype.json' if args.candidats else OUTPUT
    if args.scene:
        scene=(ROOT/'.runtime/colliers_usb/ColliersControle.FCStd').resolve()
        document=A.newDocument('ColliersControle')
        for index,(tag,shape) in enumerate(samples):
            obj=document.addObject('Part::Feature','Collier'+str(index+1));obj.Label=tag;obj.Shape=shape
        for index,(tag,shape) in enumerate(heads):
            obj=document.addObject('Part::Feature','Tete'+str(index+1));obj.Label=tag;obj.Shape=shape
        document.recompute();document.saveAs(str(scene));A.closeDocument(document.Name)
        report['scene_fichier']=str(scene.relative_to(ROOT)).replace('\\','/')
        report['scene_sha256']=sha(scene)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({k:report[k] for k in ('conforme','erreurs','collisions')},ensure_ascii=False),flush=True)
    return report['conforme']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidats',action='store_true')
    parser.add_argument('--scene',action='store_true')
    raise SystemExit(0 if run(parser.parse_args()) else 1)
