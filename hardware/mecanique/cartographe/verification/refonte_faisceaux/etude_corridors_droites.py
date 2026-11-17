"""Projection des arêtes droites BRep vers le calcul C++17 de corridors."""

import argparse
import json
from pathlib import Path
import sys

import FreeCAD as App
import Part

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from read_brep_prototype import Reader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('copy', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    reader = Reader(args.copy)
    verification = args.copy / 'verification'
    routes = json.loads((verification / 'routes_prototype.json').read_text(encoding='utf-8'))['routes']
    build = json.loads((verification / 'construction_prototype.json').read_text(encoding='utf-8'))
    occurrences = {r['occurrence']: r for r in build['occurrences'] if '/SA07_' in r['parent']}
    with args.output.open('w', encoding='ascii') as output:
        for route in routes:
            name = route['id']
            occurrence = occurrences[name]
            path = route['objet_parcours']
            if occurrence['source'] != route['fichier']:
                # La copie autonome lie le câble complet F16 de l'essai R50.
                props = reader.xml(occurrence['source'])[1][occurrence['objet_source']]
                path = props['Base'].find('Link').get('value')
            wire = reader.shape(occurrence['source'], path)
            pose = App.Placement(App.Matrix(*occurrence['matrice']))
            source_pose = reader.placement(occurrence['source'], occurrence['objet_source'])
            world = pose.multiply(source_pose.inverse())
            for edge in wire.Edges:
                if isinstance(edge.Curve, Part.Line):
                    start = world.multVec(edge.valueAt(edge.FirstParameter))
                    end = world.multVec(edge.valueAt(edge.LastParameter))
                    if start.distanceToPoint(end) > 0.001:
                        print(name, route['diametre_mm'], *start, *end, sep='\t', file=output)


if __name__ == '__main__':
    main()
