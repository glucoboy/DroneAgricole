"""Vérifie des poses et chemins de diagnostic sur les BRep sauvegardés de A."""

import os
from pathlib import Path
import sys
import traceback

from adapter_implantation import (
    App, COPY, HERE, PAIRS, Part, Scene, V, boot, bounds, cable_geometry, load,
    make_native_cable, move, report_pairs, require, sha, write,
)


OUTPUT = HERE / "essais_diagnostic.json"
SHIFT = (-20, 0, 0)
EXCLUSIONS = {
    "UART_isole": "Pose remplacée par la pose de l'essai",
    "F40": "Axe remplacé par l'essai",
    "F41": "Axe remplacé par l'essai",
    "PinceDepartF41": "P84 à reconstruire après validation du chemin",
    "PressionDepartF41": "Vis de pression du P84 remplacé",
    "BandeDepartF41": "Bande du P84 remplacé",
}


def make_trial(row, points):
    doc = App.newDocument("EssaiDiagnostic")
    try:
        cable, _ = make_native_cable(doc, None, row["id"], points,
                                     row["diametre_mm"], row["rayon_courbure_mm"])
        return cable_geometry(cable), cable.Shape.copy()
    finally:
        App.closeDocument(doc.Name)


def inspect_route(row, points, obstacles):
    result = {"points_mm": points}
    try:
        geometry, shape = make_trial(row, points)
        result.update(geometry=geometry, pairs=report_pairs(shape, obstacles, nearby=1.0))
    except Exception as error:
        result["error"] = str(error)
        return result, None
    return result, shape


def candidate_f40(port, x=-100, y=4, z=74, x_end=5):
    return [
        [-66.25, -10, -13], [x, -10, -10], [x, y, -10], [x, y, z],
        [x_end, y, z], [x_end, port[1], port[2]], port,
    ]


def candidate_f41(port, x=-144, y=-98, z=131.5):
    return [
        port, [x, port[1], port[2]], [x, port[1], 115],
        [x, y, z], [7, y, z], [7, -42, 131.5],
    ]


def main():
    environment = boot()
    scene = Scene(COPY)
    before = scene.hashes()
    lookup = {obj.name: obj for obj in scene.items.values()}
    require(set(EXCLUSIONS) <= set(lookup), "Objet de remplacement introuvable")
    obstacles = {name: obj.shape for name, obj in lookup.items() if name not in EXCLUSIONS}
    iso = lookup["UART_isole"]
    module = move(iso.shape, SHIFT)
    obstacles["UART_isole_candidat"] = module
    usb = scene.reader.shape(iso.row["source"], "ORCH_USB_B").BoundBox
    ttl = scene.reader.shape(iso.row["source"], "ORCH_BornierTTL").BoundBox
    direct = {
        "usb_b": list(iso.pose.multVec(V(usb.XMin, usb.Center.y, usb.Center.z)) + V(*SHIFT)),
        "ttl": list(iso.pose.multVec(V(ttl.XMax, ttl.Center.y, ttl.Center.z)) + V(*SHIFT)),
    }
    # Positions projetées sur l'image Waveshare. Les cotes exactes restent inconnues.
    photo = {
        "usb_b": list(iso.pose.multVec(V(usb.XMin, 21.7, 15.6)) + V(*SHIFT)),
        "ttl": list(iso.pose.multVec(V(ttl.XMax, 43, ttl.Center.z)) + V(*SHIFT)),
    }
    access_scene = {name: shape for name, shape in obstacles.items()
                    if name != "UART_isole_candidat"}
    result = {
        "schema": "cartographe.essais-diagnostic.v1",
        "complete": False,
        "versions": environment,
        "adaptateur_sha256": sha(Path(__file__)),
        "copie_A_sha256": before,
        "translation_iso_mm": SHIFT,
        "port_b_source_image": "https://www.waveshare.com/img/devkit/accBoard/USB-TO-RS232-485-TTL/USB-TO-RS232-485-TTL-details-size.jpg",
        "port_a_source": "Extrémité modélisée F41 de la copie modulaire, face réelle encore à vérifier",
        "gabarit_usb": "Lindy 36671, hypothèse conservatrice de profondeur 35 mm entièrement hors réceptacle",
        "gabarit_usb_source": "https://int.lindy.com/cables-adapters-c1/usb-c449/0-5m-usb-2-0-type-a-to-b-cable-anthra-line-p11292",
        "obstacles_exclus": EXCLUSIONS,
        "mesures": [],
        "module_bbox_mm": bounds(module),
        "module": report_pairs(module, access_scene, nearby=2.0),
    }
    write(OUTPUT, result)
    f25_points = load(HERE / "implantation.json")["security"][0]["paths"][0]
    _, new_f25 = make_trial(scene.routes["F25"], f25_points)
    f40 = scene.routes["F40"]
    f41 = scene.routes["F41"]
    for source, ports in (("photo", photo), ("enveloppe_cao", direct)):
        x, y, z = ports["usb_b"]
        plug = Part.makeBox(35, 11.8, 10.2, V(x-35, y-5.9, z-5.1))
        extraction = Part.makeBox(50, 11.8, 10.2, V(x-50, y-5.9, z-5.1))
        item = {
            "id": source, "ports_mm": ports,
            "gabarit_fiche_B": report_pairs(plug, access_scene, nearby=1.0),
            "gabarit_extraction_B_avec_course_exploratoire_15_mm":
                report_pairs(extraction, access_scene, nearby=1.0),
            "routes": [],
        }
        result["mesures"].append(item)
        f40_tests = (
            candidate_f40(ports["ttl"]),
            candidate_f40(ports["ttl"], x=-108, y=7, z=78),
            candidate_f40(ports["ttl"], x=-108, y=10, z=74, x_end=6),
        )
        f41_tests = (
            candidate_f41(ports["usb_b"]),
            candidate_f41(ports["usb_b"], x=-149, y=-98),
            candidate_f41(ports["usb_b"], x=-149, y=-100, z=128),
        )
        for f40_points, f41_points in zip(f40_tests, f41_tests):
            first, first_shape = inspect_route(f40, f40_points, obstacles)
            second, second_shape = inspect_route(f41, f41_points, obstacles)
            pair = None
            if first_shape is not None and second_shape is not None:
                pair = report_pairs(first_shape, {"F41_candidat": second_shape}, nearby=1.0)
            if first_shape is not None:
                first["contre_F25_X30"] = report_pairs(first_shape, {"F25_X30": new_f25}, nearby=1.0)
            if second_shape is not None:
                second["contre_F25_X30"] = report_pairs(second_shape, {"F25_X30": new_f25}, nearby=1.0)
            item["routes"].append({"F40": first, "F41": second, "paire_F40_F41": pair})
            write(OUTPUT, result)
            print(source, len(item["routes"]), flush=True)
    result["copie_A_inchangee"] = Scene(COPY).hashes() == before
    require(result["copie_A_inchangee"], "La copie a changé durant l'essai")
    result["complete"] = True
    write(OUTPUT, result)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        exit_code = 2
    else:
        exit_code = 0
    finally:
        PAIRS.close()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)

