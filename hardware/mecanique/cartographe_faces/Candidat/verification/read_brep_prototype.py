"""Lecture en mémoire des formes sauvegardées FCStd, sans document ni scène GUI.

Outil de vérification seulement : aucune reconstruction ou sauvegarde de pièce.
Les groupes sont composés à partir de leurs enfants visibles sauvegardés.
Toute discordance avec la boîte publiée par le constructeur doit être refusée.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import FreeCAD as App
import Part


class Reader:
    def __init__(self, base):
        self.base = Path(base)
        self.documents = {}

    def xml(self, relative):
        path = (self.base / relative).resolve()
        if path not in self.documents:
            with zipfile.ZipFile(path) as archive:
                root = ET.fromstring(archive.read('Document.xml'))
            types = {o.get('name'): o.get('type') for o in root.find('Objects').findall('Object')}
            objects = {o.get('name'): {p.get('name'): p for p in o.find('Properties')}
                       for o in root.find('ObjectData')}
            self.documents[path] = types, objects
        return self.documents[path]

    def placement(self, relative, name):
        _, objects = self.xml(relative)
        node = objects[name].get('Placement')
        node = None if node is None else node.find('PropertyPlacement')
        if node is None:
            return App.Placement()
        a = node.attrib
        return App.Placement(App.Vector(*(float(a[k]) for k in ('Px', 'Py', 'Pz'))),
                             App.Rotation(*(float(a[k]) for k in ('Q0', 'Q1', 'Q2', 'Q3'))))

    def shape(self, relative, name):
        types, objects = self.xml(relative)
        props = objects[name]
        if types[name] == 'App::Link':
            linked = props['LinkedObject'].find('XLink')
            if linked is None or list(linked):
                raise RuntimeError('Lien ou sous-élément non pris en charge : ' + str(relative) + '#' + name)
            source = ((self.base / relative).parent / linked.get('file')).resolve() \
                if linked.get('file') else (self.base / relative).resolve()
            source_name = linked.get('name')
            shape = self.shape(source, source_name)
            target = self.placement(relative, name)
            transform = props['LinkTransform'].find('Bool').get('value') == 'true'
            scale = float(props['Scale'].find('Float').get('value'))
            count = int(props['ElementCount'].find('Integer').get('value'))
            if scale != 1.0 or count != 0:
                raise RuntimeError('Lien avec échelle ou tableau non pris en charge : ' + str(relative) + '#' + name)
            if not transform:
                target = target.multiply(self.placement(source, source_name).inverse())
            shape.Placement = target.multiply(shape.Placement)
            return shape
        saved_shape = props.get('Shape')
        if saved_shape is not None and saved_shape.find('Part') is not None:
            entry = saved_shape.find('Part').get('file')
            if entry:
                with zipfile.ZipFile(self.base / relative) as archive:
                    data = archive.read(entry)
                shape = Part.Shape()
                shape.importBrepFromString(data.decode('ascii'))
                return shape
        group = props.get('Group')
        if group is not None and group.find('LinkList') is not None:
            children = []
            for child in group.find('LinkList'):
                child_name = child.get('value')
                visibility = objects[child_name].get('Visibility')
                if visibility is not None and visibility.find('Bool').get('value') == 'false':
                    continue
                child_shape = self.shape(relative, child_name)
                if child_shape is not None and not child_shape.isNull():
                    children.append(child_shape)
            if children:
                shape = Part.makeCompound(children)
                shape.Placement = self.placement(relative, name).multiply(shape.Placement)
                return shape
        if types[name] in ('App::Origin', 'App::Line', 'App::Plane', 'App::Point', 'Spreadsheet::Sheet'):
            return None
        raise RuntimeError('Forme sauvegardée absente/non prise en charge : ' + str(relative) + '#' + name)

    def occurrence(self, row):
        shape = self.shape(row['source'], row['objet_source'])
        pose = App.Placement(App.Matrix(*row['matrice']))
        # Tous les liens reconstruits emploient LinkTransform=False.
        source_pose = self.placement(row['source'], row['objet_source'])
        shape.Placement = pose.multiply(source_pose.inverse()).multiply(shape.Placement)
        return shape
