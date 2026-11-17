"""Contrôle de réouverture et des ports après construction sur copie."""
import os
from pathlib import Path
import sys
import traceback

from preparation import RUN, read, write, require
from construction import SA03, TRIAL, TTL, USB, sha_tree
from electromechanical_engine.freecad_worker import App, cables_environment, complete_dependencies, recalculate
from electromechanical_engine.qualification.native_replay import ENTRY


def reopen(case):
    target = RUN / case
    cad = target / "cad"
    before = sha_tree(cad)
    receipt = read(target / "construction.json")
    require(receipt["phase"] == "SAVED", "La construction n'a pas finalisé la copie.")
    require(receipt["pid"] != os.getpid(), "Second processus attendu.")
    require(receipt["native_sha256"] == before, "Empreintes différentes du reçu de construction.")
    version = cables_environment(False)
    root = App.openDocument(str(cad / ENTRY))
    partial = complete_dependencies(root, cad)
    docs, recomputed = recalculate(root, cad)
    paths = {Path(doc.FileName).resolve().relative_to(cad).as_posix():doc for doc in docs}
    require(set(paths) == set(before), f"Fermeture différente : {set(paths)^set(before)}")
    forbidden = []
    unresolved = []
    for name, doc in paths.items():
        require(not doc.Partial, f"Document toujours partiel : {name}")
        for obj in doc.Objects:
            if {"Invalid", "Error"} & set(obj.State):
                forbidden.append([name, obj.Name, list(obj.State)])
            if obj.TypeId == "App::Link" and obj.LinkedObject is None:
                unresolved.append([name,obj.Name])
    parameters = receipt.get("parameters", {})
    isolator = paths[SA03].getObject("UART_isole")
    local = isolator.LinkedObject
    subsystem_link = root.getObject("SA03_Prototype_Energie")
    group_pose = paths[SA03].getObject("Ensemble").Placement
    subsystem_frame = root.getObject("Ensemble").Placement.multiply(subsystem_link.Placement).multiply(group_pose.inverse())
    local_to_world = subsystem_frame.multiply(group_pose).multiply(isolator.Placement).multiply(local.Placement.inverse())
    ports = {}
    for key, name, direction in (("ttl", "ORCH_BornierTTL", "XMax"), ("usb", "ORCH_USB_B", "XMin")):
        box = local.Document.getObject(name).Shape.BoundBox
        face = App.Vector(getattr(box, direction), box.Center.y, box.Center.z)
        point = local_to_world.multVec(face)
        nominal = App.Vector(*parameters[key]) if key in parameters else (TTL if key == "ttl" else USB)
        ports[key] = {"source": name, "point_mm": list(point), "plan_mm": list(nominal),
                      "nominal_offset_mm": (point-nominal).Length}
    require(sha_tree(cad) == before, "Modification du natif durant la réouverture.")
    extra = cad / TRIAL
    if extra.exists() and TRIAL not in before:
        trial = App.openDocument(str(extra))
        require(Path(trial.FileName).resolve() == extra.resolve() and not trial.Partial, "Annexe de gabarits inaccessible.")
        auxiliary = [obj.Name for obj in trial.Objects if obj.TypeId == "Part::Box"]
    else:
        auxiliary = []
    result = {"case": case, "builder_pid": receipt["pid"], "reopen_pid": os.getpid(),
              "environment": version, "native_files": len(paths), "native_sha256": before,
              "assembly_sha256": before[ENTRY], "completed": partial, "objects": sum(len(d.Objects) for d in docs),
              "recomputed": recomputed, "errors": forbidden, "unresolved_links": unresolved, "ports": ports,
              "auxiliary_envelopes": auxiliary, "verdict": "PASS" if not forbidden and not unresolved else "FAIL"}
    write(target / "reopen.json", result)
    print(case, result["verdict"], len(paths), len(forbidden), len(unresolved), flush=True)
    return not forbidden and not unresolved


if __name__ == "__main__":
    try:
        status = reopen(sys.argv[1])
    except Exception:
        write(RUN / sys.argv[1] / "reopen.json", {"case": sys.argv[1], "verdict": "FAIL", "error": traceback.format_exc()})
        traceback.print_exc()
        status = False
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if status else 1)
