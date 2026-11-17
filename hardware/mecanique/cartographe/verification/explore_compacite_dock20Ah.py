"""Exploration de compacité CAO, sans modifier les documents FreeCAD existants."""
from pathlib import Path
import json, math, hashlib
import FreeCAD as A, Part
MEC=Path(__file__).resolve().parents[1]
R=50.0
X=A.Vector(1,0,0); Z=A.Vector(0,0,1)
def arc(a,m,b): return Part.Arc(a,m,b).toShape()
def route(plus):
    y=-55.2465 if plus else 21.6535
    z=119.745 if plus else 113.155
    start=A.Vector(-179.9,y,z)
    edges=[]
    if plus:
        a=A.Vector(-179.9,-5.2465,69.745)
        edges.append(arc(a,A.Vector(-179.9,-40.6018390593274,84.3896609406726),start))
    center=start-X*R
    end=center+Z*R
    edges.append(arc(start,center+(X+Z)*(R/math.sqrt(2)),end))
    target_y=-8 if plus else 8
    uy=(target_y-y)/(2*R)
    u=A.Vector(0,uy,-math.sqrt(1-uy*uy))
    lower_z=end.z+2*R*u.z
    delta=145-lower_z
    theta=math.acos(1-delta/(2*R))
    distance=2*R*math.sin(theta)
    # Garder 5 mm droits avant la terminaison; aucun retour axial.
    extension=end.x+distance+5-(-174)
    turn_start=end-X*extension
    edges.append(Part.makeLine(end,turn_start))
    center=turn_start+u*R
    turn_end=turn_start+u*(2*R)
    edges.append(arc(turn_start,center-X*R,turn_end))
    v=Z
    join=turn_end+X*(R*math.sin(theta))+v*(delta/2)
    mid1=turn_end+X*(R*math.sin(theta/2))+v*(R*(1-math.cos(theta/2)))
    end=turn_end+X*distance+v*delta
    mid2=end-X*(R*math.sin(theta/2))-v*(R*(1-math.cos(theta/2)))
    edges.extend([arc(turn_end,mid1,join),arc(join,mid2,end),Part.makeLine(end,A.Vector(-174,target_y,145))])
    wire=Part.Wire(edges)
    first=wire.Vertexes[0].Point
    tangent=A.Vector(0,-1,0) if plus else Z
    section=Part.Wire(Part.makeCircle(2.5,first,tangent))
    shape=wire.makePipeShell([section],True,False)
    b=shape.BoundBox
    return wire, section, shape, {'longueur_libre_mm':wire.Length,'rayon_minimum_arcs_mm':R,'diametre_mm':5,'bbox_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],'extension_avant_demi_tour_mm':extension,'angle_S_deg':math.degrees(theta),'arcs_circulaires_tangents':True,'valide':shape.isValid(),'solides':len(shape.Solids),'points_depart_fin':[tuple(first),(-174,target_y,145)]}

def candidate(plus):
    _, _, shape, metrics = route(plus)
    return shape, metrics

def main():
    d=A.openDocument(str(MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'))
    d.recompute()
    shapes={}; rows={}
    for plus in [True,False]:
        n='EQ_CordonFixe8AWG_'+('Plus' if plus else 'Moins')+'20A'
        shapes[n],rows[n]=candidate(plus)
    others=[o for o in d.Objects if o.TypeId=='App::Link' and o.Name not in shapes]
    hits=[]
    for n,s in shapes.items():
        for o in others:
            b=o.Shape.BoundBox
            if s.BoundBox.intersect(b):
                volume=s.common(o.Shape).Volume
                if volume>0.001: hits.append({'cordon':n,'autre':o.Name,'volume_mm3':volume})
    for h in hits:
        original=d.getObject(h['cordon']).Shape
        h['volume_initial_mm3']=original.common(d.getObject(h['autre']).Shape).Volume
        h['variation_mm3']=h['volume_mm3']-h['volume_initial_mm3']
    common=shapes[list(shapes)[0]].common(shapes[list(shapes)[1]]).Volume
    mobiles=[o for o in others if getattr(o,'Mobile','non')=='oui']
    min_mobile=min(o.Shape.BoundBox.XMin for o in mobiles)
    max_fixed=max(s.BoundBox.XMax for s in shapes.values())
    course={'critere':'Separation conservative sur X, extraction +X','x_min_mobile_verrouille_mm':min_mobile,'x_max_cordons_mm':max_fixed,'marge_separation_mm':min_mobile-max_fixed,'course_continue_plus_X_sans_obstacle':min_mobile>max_fixed}
    assembly=A.openDocument(str(MEC/'assemblages/Integration_Stack_Revue_20261003.FCStd'))
    assembly.recompute()
    static_hits=[]
    for n,s in shapes.items():
        for o in assembly.Objects:
            if o.TypeId=='App::Link' and o.Name!='SA02A_Dock20Ah' and s.BoundBox.intersect(o.Shape.BoundBox):
                volume=s.common(o.Shape).Volume
                if volume>0.001: static_hits.append({'cordon':n,'autre':o.Name,'volume_mm3':volume})
    combined=Part.makeCompound([o.Shape for o in others]+list(shapes.values()))
    b=combined.BoundBox
    out={'schema_version':1,'recette':'verification/explore_compacite_dock20Ah.py','unites':'mm','repere':'Coordonnees locales Ensemble du dock, placements externes conserves','sha256_inputs':{str(Path(q.FileName).relative_to(MEC)).replace(chr(92),'/'):hashlib.sha256(Path(q.FileName).read_bytes()).hexdigest() for q in A.listDocuments().values() if q.FileName and Path(q.FileName).is_relative_to(MEC)},'sha256_recette':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'date':'2026-10-04','statut':'À valider','nature':'Exploration, sources FCStd non sauvegardées','hypotheses':['Mêmes départs et arrivées que les cordons actifs','Diamètre étude5 mm et minimum R50 conservés','Contrôles géométriques réalisés sur le dock et son intégration courante; course +X certifiée par enveloppes séparées'],'routes':rows,'collisions_nominales_dock':hits,'intersection_entre_cordons_mm3':common,'course_continue':course,'intersections_integration_stack':static_hits,'bbox_dock_candidat_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],'dimensions_dock_candidat_mm':[b.XLength,b.YLength,b.ZLength],'limites':['Pas de qualification thermique, vibration, liberté flottante ou courbure réelle','Pack, fils scellés et protections natives inchangés','Sweep et collision géométrique seulement; qualification au banc nécessaire']}
    (MEC/'verification/explore_compacite_dock20Ah.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=True,indent=2))
    
    

if __name__ == '__main__':
    main()

