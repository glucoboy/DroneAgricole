"""Criblage des hypothèses de service sur les BRep réellement sauvegardés."""
import os
import sys
from pathlib import Path

from preparation import RUN, require, write, read
from construction import TRIAL, SA03, sha_tree
from electromechanical_engine.freecad import guard
from electromechanical_engine.qualification.native_replay import MEC, collisions
from electromechanical_engine.freecad_worker import App

sys.path[:0] = [str(MEC / "cartographe_refonte_systeme/verification"),
                str(MEC / "cartographe/verification/refonte_faisceaux"), str(MEC / "cartographe/verification")]
from adapter_implantation import BoundedPairs, Scene, distance_bound
from controles_geometrie import bounds


def checks(case):
    folder = RUN / case
    cad = folder / "cad"
    original = sha_tree(cad)
    service_path = cad / TRIAL
    service_hash = guard.sha256(service_path)
    scene = Scene(cad)
    trials = {"case": case, "pid": os.getpid(), "service_sha256": service_hash,
              "comparison": "Gabarits ASSUMED. Test sur une pose nominale. Seuil de volume du criblage local = 0,0001 mm³.",
              "base_service_gestures": ["position emboîtée", "sortie axiale", "volume outil"],
              "envelopes": {}, "support": None}
    obstacles = {item.key: item for item in scene.items.values() if item.name != "ASSUMED_ServiceGO3B"}
    tests = read(folder / "construction.json")["envelopes"]
    probe = BoundedPairs()
    try:
        for envelope in tests:
            name = envelope["name"]
            shape = scene.reader.shape(TRIAL, "ASSUMED_" + name)
            require(shape.isValid() and len(shape.Solids) == 1, f"Gabarit non valide : {name}")
            # Connected host and its own cable are reported separately. They are not physical permissions.
            mate = {"TTL": {"UART_isole","F40"}, "USB": {"UART_isole","F41"}, "CAN1": {"Holybro6XOrin","F31"},
                    "Ferrite": {"F41"}, "F16": {"F16"}, "M8": {"F_M8"},
                    "TTLDeporte": {"F40"}, "USBDeporte": {"F41"}}[name.split("_")[0]]
            regular = {key: item.shape for key, item in obstacles.items() if item.name not in mate}
            coupled = {key: item.shape for key, item in obstacles.items() if item.name in mate}
            result = collisions(shape, regular, distance_bound, probe.measure)
            mating = collisions(shape, coupled, distance_bound, probe.measure)
            trials["envelopes"][name] = {"hypothesis_status":"INCONCLUSIVE", "box_mm":bounds(shape),
                 "scenario_result": "FAIL" if result["collisions"] else ("INCONCLUSIVE" if result["unknown"] else "PASS"),
                 "unrelated": result, "mating_overlap_reported_separately": mating}
            write(folder / "service.json", trials)
        if TRIAL in original:
            target = next(item for item in scene.items.values() if item.name == "ASSUMED_ServiceGO3B")
            near = {}
            for key, item in obstacles.items():
                if item.name in {"Interface","UART_isole","P72_Guide","P75_Cadre"}:
                    near[key] = {"distance_mm": target.shape.distToShape(item.shape)[0],
                                 "axis_aligned_gap_mm": distance_bound(target.shape.BoundBox, item.shape.BoundBox)}
            results = collisions(target.shape, {key: item.shape for key, item in obstacles.items()},
                                 distance_bound, probe.measure)
            volume = target.shape.Volume
            trials["support"] = {"volume_mm3": volume, "box_mm": bounds(target.shape), "neighbors": near,
                "crible": results, "ancrage": "INCONCLUSIVE", "estimated_mass_g_if_aluminum": volume * 0.00270,
                "density_reference": "DOC-MEC §6.1, 2,70 g/cm³, analogie spécifique ; matériau, vis et appui non déterminés"}
    finally:
        probe.close()
    require(original == sha_tree(cad) and service_hash == guard.sha256(service_path),
            "Fichier modifié durant le contrôle de service.")
    trials["status"] = "COMPLETE"
    write(folder / "service.json", trials)
    print(case, len(trials["envelopes"]), flush=True)


if __name__ == "__main__":
    checks(sys.argv[1])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
