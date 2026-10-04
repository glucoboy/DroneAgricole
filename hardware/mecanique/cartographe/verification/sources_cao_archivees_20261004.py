"""Infrastructure FreeCAD : reprendre une base archivée avec des pièces courantes."""
from pathlib import Path
import FreeCAD as A

MEC = Path(__file__).resolve().parents[1]
ARCHIVE = MEC / 'archives/avant_tri_20261004'

def load_chassis_source():
    relative = Path('sous_assemblages/SA01_Chassis_Rehausse20.FCStd')
    source = MEC / relative
    archived = not source.exists()
    doc = A.openDocument(str(ARCHIVE / relative if archived else source))
    if archived:
        for link in doc.Objects:
            if link.TypeId != 'App::Link':
                continue
            target = link.LinkedObject
            assert target is not None, link.Name
            old_file = Path(target.Document.FileName).resolve()
            live_file = MEC / old_file.relative_to(ARCHIVE.resolve())
            assert live_file.exists(), str(live_file)
            live_doc = next((d for d in A.listDocuments().values()
                             if d.FileName and Path(d.FileName).resolve() == live_file.resolve()), None)
            live_doc = live_doc or A.openDocument(str(live_file))
            live_target = live_doc.getObject(target.Name)
            assert live_target is not None, (live_file, target.Name)
            pose = A.Placement(link.LinkPlacement)
            link.LinkedObject = live_target
            link.LinkTransform = False
            link.LinkPlacement = pose
    assert all(not Path(o.LinkedObject.Document.FileName).resolve().is_relative_to(ARCHIVE.resolve())
               for o in doc.Objects if o.TypeId == 'App::Link')
    return doc
