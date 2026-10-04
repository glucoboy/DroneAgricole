"""Infrastructure KiCad : reconstruire le placement CA01, sans cuivre ajouté.

Exécuter avec le Python fourni par KiCad 10.0.6. Les coordonnées du JSON
placement_mecanique.json sont locales au coin supérieur gauche du PCB.
Le mode --initialise est réservé au premier préplacement ; sans cette option,
la recette reprend exactement les positions enregistrées et les empreintes
de la netlist exportée par KiCad.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pcbnew as p

CARD = Path(__file__).resolve().parents[1]
VERIFY = CARD / "verification"
LIBS = Path(p.__file__).resolve().parents[3] / "share/kicad/footprints"
ORIGIN = (50.0, 50.0)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def vec(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))


def location(x, y):
    return vec(x + ORIGIN[0], y + ORIGIN[1])


def footprint(libid):
    lib, name = libid.split(":", 1)
    folder = CARD / (lib + ".pretty") if lib == "CA01_Mecanique" else LIBS / (lib + ".pretty")
    fp = p.FootprintLoad(str(folder), name)
    if fp is None:
        raise RuntimeError("Empreinte absente : " + libid)
    fp.SetFPID(p.LIB_ID(lib, name))
    return fp


def box(fp):
    fp.BuildCourtyardCaches()
    bb = fp.GetCourtyard(p.F_CrtYd).BBox()
    return [p.ToMM(bb.GetLeft()) - ORIGIN[0], p.ToMM(bb.GetTop()) - ORIGIN[1],
            p.ToMM(bb.GetRight()) - ORIGIN[0], p.ToMM(bb.GetBottom()) - ORIGIN[1]]


def intersects(a, b, gap=0.25):
    return a[0] < b[2] + gap and a[2] + gap > b[0] and a[1] < b[3] + gap and a[3] + gap > b[1]


def set_position(fp, x, y, angle=0):
    fp.SetOrientationDegrees(angle)
    fp.SetPosition(location(x, y))


def label(board, text, x, y, layer=p.Dwgs_User, size=1.0):
    obj = p.PCB_TEXT(board)
    obj.SetText(text)
    obj.SetPosition(location(x, y))
    obj.SetLayer(layer)
    obj.SetTextSize(vec(size, size))
    obj.SetTextThickness(p.FromMM(size / 7))
    board.Add(obj)


def rectangle(board, bounds, layer, width=0.1):
    x1, y1, x2, y2 = bounds
    for a, b in [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                 ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]:
        shape = p.PCB_SHAPE(board)
        shape.SetShape(p.SHAPE_T_SEGMENT)
        shape.SetStart(location(*a))
        shape.SetEnd(location(*b))
        shape.SetLayer(layer)
        shape.SetWidth(p.FromMM(width))
        board.Add(shape)


def initial_positions(fps):
    # Ancres physiques par fonction. Le rapprochement électrique final reste
    # à revoir lors du routage (boucles chaudes, Kelvin, CEM, thermique).
    anchors = {
        "J103": (14, 62, 90), "J104": (15.1, 44, 90),
        "J201": (66, 64, 0), "J301": (96, 64, 0),
        "J401": (31, 3.6, 180), "J402": (47, 3.6, 180),
        "J503": (65, 3.6, 180), "J502": (104, 5.5, 180),
        "J504": (122.4, 23, 90), "J505": (122.4, 36, 90),
        "J506": (122.4, 45, 90), "J507": (80, 3.6, 180),
        "J508": (122.4, 56, 90), "J509": (90, 3.6, 180),
        "J501": (122.4, 65, 90), "JP501": (119, 71, 0),
        "U101": (31, 58, 0), "Q101": (25, 68, 90), "Q102": (35, 68, 90),
        "F101": (22, 55, 90), "C105": (44.5, 68, 0),
        "U102": (33, 40, 0), "Q103": (43, 35, 0), "Q104": (43, 44, 0),
        "L101": (55, 40, 0), "R116": (33, 48, 0),
        "U201": (67, 58, 0), "L201": (79, 59, 0), "C203": (57, 69, 0),
        "U301": (98, 58, 0), "L301": (109, 62, 0), "C303": (111, 74, 0),
        "U503": (56, 19, 0), "U512": (70, 17, 0), "U513": (76, 17, 0),
        "U504": (100, 25, 0), "U505": (104, 37, 0), "U507": (114, 43, 0),
        "U510": (84, 25, 0), "U511": (90, 25, 0), "U506": (91, 37, 0),
        "Q501": (109, 16, 0), "U509": (113, 51, 0),
        "C401": (32, 9, 0), "C402": (37, 9, 0),
        "R401": (47, 10, 0), "R402": (47, 14, 0), "F102": (27, 9, 0),
    }
    placements = {}
    occupied = [("TVS_reserve", [13, 72, 23, 79])]
    if 'MOD401' in fps:
        anchors['MOD401'] = (16.5, 20.5, 90)
    else:
        occupied.append(("RP4TD_reserve", [8, 8, 25, 33]))
    for ref, xy in (("H1", (3, 3)), ("H2", (123, 3)), ("H3", (123, 77)), ("H4", (3, 77))):
        set_position(fps[ref], *xy)
        placements[ref] = [*xy, 0]
        occupied.append((ref, box(fps[ref])))
    for ref, pos in anchors.items():
        set_position(fps[ref], *pos)
        bb = box(fps[ref])
        hits = [r for r, b in occupied if intersects(bb, b)]
        if hits:
            raise RuntimeError(f"Ancres en collision : {ref} / {hits}")
        if min(bb[0], bb[1]) < 0.25 or bb[2] > 125.75 or bb[3] > 79.75:
            raise RuntimeError(f"Ancre hors carte : {ref} {bb}")
        placements[ref] = list(pos)
        occupied.append((ref, bb))

    def target(ref):
        num = int("".join(c for c in ref if c.isdigit()))
        if 100 <= num <= 105:
            return (31, 58), [18, 50, 50, 76]
        if 110 <= num <= 126:
            if ref.startswith("C") and 117 <= num <= 121:
                return (38, 30), [27, 26, 57, 36]
            if ref.startswith("C") and 122 <= num <= 126:
                return (53, 48), [39, 45, 66, 53]
            return (33, 40), [21, 29, 48, 53]
        if 200 <= num <= 299:
            return (67, 58), [50, 49, 88, 74]
        if 300 <= num <= 399:
            return (98, 58), [88, 49, 118, 74]
        if 500 <= num <= 599:
            # Passifs de chaque adaptation, regroupés par signal/IC.
            groups = {
                "C501": "U503", "C502": "U503", "F501": "U503", "C503": "U509",
                "C504": "U504", "C505": "U505", "C506": "U507", "C507": "U511",
                "C508": "U512", "C509": "U513", "C510": "U504", "C511": "U505",
                "C512": "U507", "C513": "U511", "C514": "U510", "C515": "U510",
                "R530": "U504", "R531": "U506", "R532": "U505", "R533": "U507",
                "R534": "U512", "R535": "U513", "R536": "U512", "R537": "U513",
                "R538": "U504", "R539": "U511", "R540": "U505", "R541": "U504",
                "R542": "U511", "R543": "U505", "D503": "U512", "D504": "U513",
                "R510": "Q501", "R511": "Q501", "R512": "U509", "R513": "U509",
                "R514": "U509", "D501": "U509", "D502": "U509",
            }
            u = "U506" if ref in {f"C{i}" for i in range(516, 522)} else groups.get(ref, "U503")
            return tuple(anchors[u][:2]), [50, 10, 119, 56]
        raise RuntimeError("Groupe de placement indéfini : " + ref)

    # Grille de recherche déterministe ; boîtes de courtyards conservatrices.
    remaining = [r for r in fps if r not in placements]
    remaining.sort(key=lambda r: (-(box(fps[r])[2]-box(fps[r])[0]) *
                                   (box(fps[r])[3]-box(fps[r])[1]), r))
    for ref in remaining:
        fp = fps[ref]
        (tx, ty), limits = target(ref)
        candidates = [(x / 2, y / 2) for x in range(math.ceil(limits[0]*2), math.floor(limits[2]*2)+1)
                       for y in range(math.ceil(limits[1]*2), math.floor(limits[3]*2)+1)]
        candidates.sort(key=lambda xy: ((xy[0]-tx)**2+(xy[1]-ty)**2, xy[1], xy[0]))
        found = False
        for x, y in candidates:
            set_position(fp, x, y, 0)
            bb = box(fp)
            if bb[0] < limits[0] or bb[1] < limits[1] or bb[2] > limits[2] or bb[3] > limits[3]:
                continue
            if any(intersects(bb, other) for _, other in occupied):
                continue
            placements[ref] = [x, y, 0]
            occupied.append((ref, bb))
            found = True
            break
        if not found:
            raise RuntimeError("Pas de position sans chevauchement : " + ref)
    return placements


def build(initialise=False, allow_incomplete=False, output=None):
    pcb_path = Path(output) if output else CARD / 'CA01_Avionique.kicad_pcb'
    if pcb_path.exists():
        current = p.LoadBoard(str(pcb_path))
        if list(current.GetTracks()) or list(current.Zones()):
            raise RuntimeError('PCB déjà routé : reconstruction de préplacement refusée pour préserver pistes/vias/zones. Utiliser une copie isolée pour cette recette historique.')
    project_file = CARD / 'CA01_Avionique.kicad_pro'
    project_bytes = project_file.read_bytes()
    config_path = CARD / "placement_mecanique.json"
    existing_config = json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
    xml = ET.parse(VERIFY / "netlist.xml")
    board = p.BOARD()
    board.SetCopperLayerCount(2)  # Canevas préliminaire, stackup non décidé.
    board.GetDesignSettings().SetBoardThickness(p.FromMM(1.6))
    rectangle(board, [0, 0, 126, 80], p.Edge_Cuts, 0.05)
    connections = {}
    for node in xml.findall("./nets/net"):
        # L'XML exporte les noms de broches avec '/', le PCB les échappe dans
        # les seuls noms automatiques. Préserver les séparateurs de feuilles.
        name = node.attrib["name"]
        for marker in ('Net-(', 'unconnected-('):
            if marker in name:
                head, tail = name.split(marker, 1)
                name = head + marker + tail.replace('/', '{slash}')
                break
        net = p.NETINFO_ITEM(board, name)
        board.Add(net)
        for pin in node.findall("node"):
            connections[(pin.attrib["ref"], pin.attrib["pin"])] = net
    fps = {}
    pin_sets = {(x.attrib["lib"], x.attrib["part"]): {pin.attrib["num"] for pin in x.findall("./pins/pin")}
                for x in xml.findall("./libparts/libpart")}
    root_uuid = ET.parse(VERIFY / "netlist.xml").findtext("./design/sheet/tstamps")
    # L'UUID racine est conservé explicitement depuis le fichier schématique.
    import re
    root_uuid = re.search(r'\(uuid "([^"]+)"\)', (CARD / "CA01_Avionique.kicad_sch").read_text(encoding="utf-8"))[1]
    for comp in xml.findall("./components/comp"):
        ref = comp.attrib["ref"]
        props = {x.attrib["name"] for x in comp.findall("property")}
        if "exclude_from_board" in props:
            raise RuntimeError("Composant encore exclu du PCB : " + ref)
        libid = comp.findtext("footprint")
        if not libid:
            raise RuntimeError("Empreinte non affectée : " + ref)
        fp = footprint(libid)
        envelopes = {'J103': 'XT30PW_M', 'J104': 'XT30PW_F', 'J201': 'JST_VH_2',
                     'J301': 'JST_VH_2', 'J502': 'JST_PH_6',
                     'Q101': 'TI_Q5A', 'Q102': 'TI_Q5A', 'Q103': 'TI_Q5A',
                     'Q104': 'TI_Q5A', 'R116': 'CSM3637',
                     'U201': 'LM76003_RNP', 'U301': 'LM76003_RNP',
                     'U101': 'LM74800_DRR', 'D503': 'TPD1E05U06_DPY',
                     'D504': 'TPD1E05U06_DPY', 'F101': 'Fuse_NANO2_451'}
        models_inventory = json.loads((CARD/'modeles_3d.json').read_text(encoding='utf-8')) if (CARD/'modeles_3d.json').exists() else None
        if models_inventory:
            configured = models_inventory['models_by_ref'][ref]
            if configured['path']:
                models = fp.Models()
                if not len(models):
                    fp.Add3DModel(p.FP_3DMODEL())
                    models = fp.Models()
                models[0].m_Filename = configured['path']
                transform = configured['transform']
                models[0].m_Offset = p.VECTOR3D(*transform['offset_mm'])
                models[0].m_Rotation = p.VECTOR3D(*transform['rotation_deg'])
                models[0].m_Scale = p.VECTOR3D(*transform['scale'])
        elif ref in envelopes:
            # Enveloppes paramétriques identifiées, pas des modèles OEM exacts.
            path = '${KIPRJMOD}/../../../mecanique/cartographe/exports/ca01_placement_20261001/' + envelopes[ref] + '.step'
            models = fp.Models()
            if len(models):
                models[0].m_Filename = path
            else:
                model = p.FP_3DMODEL()
                model.m_Filename = path
                fp.Add3DModel(model)
        fp.SetReference(ref)
        fp.SetValue(comp.findtext("value"))
        fp.SetDNP("dnp" in props)
        fp.SetExcludedFromBOM("exclude_from_bom" in props)
        for field in comp.findall('./fields/field'):
            if field.attrib['name'] == 'Footprint':
                continue
            fp.SetField(field.attrib['name'], field.text or '')
            pcb_field = fp.GetField(field.attrib['name'])
            pcb_field.SetVisible(False)
            pcb_field.SetTextSize(vec(1.0, 1.0))
        fp.SetSheetname(comp.find("sheetpath").attrib["names"])
        fp.SetSheetfile(next((x.attrib.get("value", "") for x in comp.findall("property") if x.attrib["name"] == "Sheetfile"), ""))
        path = "/" + root_uuid + comp.find("sheetpath").attrib["tstamps"] + comp.findtext("tstamps")
        fp.SetPath(p.KIID_PATH(path))
        fp.SetUuid(p.KIID(comp.findtext("tstamps")))
        source = comp.find("libsource").attrib
        # MP : ancrages mécaniques des bibliothèques JST, sans broche électrique.
        actual = {pad.GetNumber() for pad in fp.Pads() if pad.GetNumber() not in ("", "MP")}
        expected = pin_sets[(source["lib"], source["part"])]
        if actual != expected:
            pending = existing_config.get('incomplete_electrical_footprints', {}).get(ref, {})
            declared = set(pending.get('missing_pad_numbers', []))
            if not (allow_incomplete and pending.get('footprint') == libid
                    and actual <= expected and expected - actual == declared):
                raise RuntimeError(f"Pads différents du symbole : {ref} {actual} / {expected}. "
                                   "--allow-incomplete autorise uniquement le préplacement déclaré non fabricable.")
        for pad in fp.Pads():
            key = (ref, pad.GetNumber())
            if key in connections:
                pad.SetNet(connections[key])
        board.Add(fp)
        fps[ref] = fp
    for ref in ["H1", "H2", "H3", "H4"]:
        fp = footprint("MountingHole:MountingHole_3.2mm_M3")
        fp.SetReference(ref)
        fp.SetValue("Fixation M3 / Holybro")
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        fp.SetBoardOnly(True)
        board.Add(fp)
        fps[ref] = fp
    for ref, module in existing_config.get('board_only_modules', {}).items():
        if ref in fps:
            raise RuntimeError('Référence mécanique dupliquée : ' + ref)
        fp = footprint(module['footprint'])
        fp.SetReference(ref)
        fp.SetValue(module['value'])
        fp.SetBoardOnly(True)
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)
        if list(fp.Pads()):
            raise RuntimeError('Module mécanique avec pads électriques non définis : ' + ref)
        board.Add(fp)
        fps[ref] = fp
    if initialise:
        config = {"schema_version": 1, "date": "2026-10-01", "status": "Implémenté",
                  "qualification": "À valider", "scope": "Préplacement mécanique uniquement ; aucun routage",
                  "outline_mm": [126, 80], "thickness_mm": 1.6, "pcb_origin_mm": list(ORIGIN),
                  "mounting_centres_mm": [[3,3],[123,3],[123,77],[3,77]], "mounting_hole_diameter_mm": 3.2,
                  "stack_candidate": "CA01 sous Holybro ; face composants tournée vers extérieur inférieur",
                  "pcb_gap_candidate_mm": 10,
                  "board_only_modules": existing_config.get('board_only_modules', {}),
                  "reservations": [{"reference": "RP4TD", "bounds_mm": [8,8,25,33],
                                    "part_dimensions_mm": [23.7,16.3,4.0], "rotated_90_degrees": True,
                                    "source": "https://radiomasterrc.com/products/rp4td-expresslrs-2-4ghz-diversity-receiver",
                                    "owner": "MOD401" if 'MOD401' in fps else None,
                                    "limits": "Enveloppe du module ; support, isolant, antennes et câble non modélisés"},
                                   {"reference": "TVS_ENTREE_A_DEFINIR", "bounds_mm": [13,72,23,79],
                                    "limits": "Réserve graphique sans composant électrique ; dimension définitive ouverte"}],
                  "placements": initial_positions(fps),
                  "limits": ["Entretoises, révision Holybro, faisceau et montage physique non validés",
                             "Courtyards 2D uniquement ; modèles 3D standards et enveloppes candidates",
                             "Implantation à reprendre pour boucles de commutation, Kelvin, thermique et CEM",
                             "Nombre de couches et épaisseur de cuivre non décidés pour fabrication",
                             "Protections, Ceff, stabilité, niveaux et séquencements électriques restent ouverts"]}
        write(config_path, config)
    else:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if set(config["placements"]) != set(fps):
        raise RuntimeError("Le placement ne couvre pas exactement les composants + les quatre fixations")
    for ref, pos in config["placements"].items():
        fp = fps[ref]
        set_position(fp, *pos)
        fp.Value().SetVisible(False)
        # Références de préplacement sur fabrication ; la sérigraphie finale
        # sera définie après l'implantation électrique et le routage.
        fp.Reference().SetLayer(p.F_Fab)
        fp.Reference().SetTextSize(vec(1.0, 1.0))
        fp.Reference().SetTextThickness(p.FromMM(0.1))
        fp.Reference().SetTextAngle(p.EDA_ANGLE(0, p.DEGREES_T))
        bb = box(fp)
        fp.Reference().SetPosition(location((bb[0]+bb[2])/2, bb[1]-0.65))
        # Le grand ${REFERENCE} de fabrication serait redondant sur l'aperçu.
        for item in fp.GraphicalItems():
            if hasattr(item, 'GetText') and item.GetText() == "${REFERENCE}":
                item.SetVisible(False)
    for reservation in config["reservations"]:
        if reservation.get('owner') in fps:
            continue  # Le contour est porté par l'empreinte du module propriétaire.
        rectangle(board, reservation["bounds_mm"], p.Dwgs_User)
        a = reservation["bounds_mm"]
        label(board, reservation["reference"], (a[0]+a[2])/2, (a[1]+a[3])/2, size=0.8)
    label(board, "CA01 - PREPLACEMENT MECANIQUE - SANS ROUTAGE", 63, 83, size=1.2)
    label(board, "126 x 80 mm / 4 trous 3.2 / entraxes 120 x 74 - A VALIDER", 63, 86)
    label(board, "Face composants vers exterieur de la stack ; refroidissement Holybro libre", 63, 89, size=0.8)
    for text, x, y in [("ENTREE 6S",10,48),("CALCUL 12V",44,25),("LIDAR 12V",70,48),
                       ("AUX 5V",101,48),("TEMPS / CAMERA",85,12)]:
        label(board, text, x, y, size=0.8)
    board.GetDesignSettings().SetAuxOrigin(location(0,0))
    board.GetDesignSettings().SetGridOrigin(location(0,0))
    board.BuildConnectivity()
    try:
        p.SaveBoard(str(pcb_path), board)
    finally:
        # SaveBoard peut sérialiser les réglages par défaut du BOARD neuf dans
        # le .pro voisin. Préserver les règles ERC/DRC et variantes existantes.
        if project_file.read_bytes() != project_bytes:
            project_file.write_bytes(project_bytes)
    print(json.dumps({"footprints": len(fps), "nets": board.GetNetCount(),
                      "tracks": len(list(board.GetTracks())), "zones": len(list(board.Zones()))}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialise", action="store_true")
    parser.add_argument('--allow-incomplete', action='store_true',
                        help='Préplacement seulement des empreintes incomplètes déclarées ; fabrication et parité restent ouvertes')
    parser.add_argument('--output', type=Path, help='PCB isolé pour reconstruction de contrôle ; ne remplace pas le PCB routé')
    args = parser.parse_args()
    build(args.initialise, args.allow_incomplete, args.output)
