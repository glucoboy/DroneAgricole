"""Infrastructure de persistance des apparences natives FreeCAD 1.1.

Le Python embarqué externe crée ici des fichiers MaterialList v3 vides au
save(). Réparer uniquement les données GUI, au format natif documenté par
PropertyMaterialList::SaveDocFile (FreeCAD src/App/PropertyStandard.cpp).
La géométrie courante est conservée ; les arbres GUI initiaux viennent de Git.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
import subprocess
import zipfile
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[4]
VER = Path(__file__).resolve().parent
proof_path = VER/'couleurs_dock20Ah.json'
proof = json.loads(proof_path.read_text(encoding='utf-8'))
PALETTE = proof['palette']
BASELINE = json.loads((VER/'suivi_git_dock20Ah.json').read_text(encoding='utf-8'))['commit_avant']


def packed(rgb):
    r, g, b = (round(v*255) for v in rgb)
    return (r << 24) | (g << 16) | (b << 8) | 255


def appearance(rgb):
    # UInt32 count, quatre RGBA UInt32, deux Float32, puis trois chaînes vides.
    return struct.pack('<IIIIIffIII', 1, 0x555555FF, packed(rgb), 0x888888FF,
                       0x000000FF, 0.9, 0.0, 0, 0, 0)


for row in proof['references_colorees']:
    path = ROOT/row['fichier']
    baseline_bytes = subprocess.check_output(['git', 'show', BASELINE+':'+row['fichier']], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(baseline_bytes)) as old, zipfile.ZipFile(path) as current:
        # Conserver toujours Document.xml et les géométries courantes : un
        # rejeu ne doit jamais annuler une évolution ultérieure d'une pièce.
        payload = {n: current.read(n) for n in current.namelist()}
        original_gui = old.read('GuiDocument.xml')
        gui = ET.fromstring(original_gui)
        document = ET.fromstring(payload['Document.xml'])
        types = {e.attrib['name']: e.attrib.get('type', '') for e in document.find('Objects') if 'name' in e.attrib}
        baseline_document = ET.fromstring(old.read('Document.xml'))
        baseline_types = {e.attrib['name']: e.attrib.get('type', '') for e in baseline_document.find('Objects') if 'name' in e.attrib}
        assert types == baseline_types, 'Arbre natif évolué : adapter la recette GUI avant colorisation de '+row['fichier']
        # Restaurer aussi les tables GUI voisines ; le save externe les vide.
        for element in gui.iter():
            filename = element.attrib.get('file')
            if filename and filename in old.namelist():
                payload[filename] = old.read(filename)
        colored = []
        for vp in gui.iter('ViewProvider'):
            name = vp.attrib['name']
            if not types.get(name, '').startswith(('Part::', 'PartDesign::')):
                continue
            for prop in vp.iter('Property'):
                if prop.attrib.get('name') == 'ShapeAppearance':
                    ml = prop.find('MaterialList')
                    filename = ml.attrib.get('file')
                    if filename:
                        payload[filename] = appearance(PALETTE[row['famille']])
                        colored.append(name)
        payload['GuiDocument.xml'] = original_gui
        assert colored, row['fichier']
        # Tous les éléments autres que GUI et tables référencées gardent leurs octets.
        temp = path.with_suffix('.couleurs.tmp')
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as out:
            for name, data in payload.items():
                out.writestr(name, data)
    temp.replace(path)
    row['objets'] = colored
    row['sha256_apres'] = hashlib.sha256(path.read_bytes()).hexdigest()

proof['persistance'] = 'Tables ShapeAppearance v3 natives, GUI initiale préservée depuis Git ; réouverture et rendu séparés requis.'
proof['recette_persistance_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'references_colorees': len(proof['references_colorees']), 'finalisation_correcte': True}))
