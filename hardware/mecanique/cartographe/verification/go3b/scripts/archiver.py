"""Archiver les copies GO3B vérifiées et leurs preuves, sans promotion de l'actif."""
import json
from pathlib import Path
import shutil

from preparation import ROOT, RUN, read, write, require
from electromechanical_engine.freecad import guard

DESTINATION = ROOT / "hardware/mecanique/cartographe/verification/go3b"
CASES = ("baseline", "H03-A", "H03-B", "H02-A", "H02-B", "H01-A-reprise", "H01-B-reprise", "consolidee",
         "H01-A", "H01-B")
REPORTS = ("experiment.json", "construction.json", "snapshot.json", "reopen.json", "service.json")


def publish():
    preflight = read(RUN / "preflight.json")
    source = ROOT / "hardware/mecanique/cartographe"
    unchanged = {name: guard.sha256(source / name) for name in preflight["source_hashes"]}
    require(unchanged == preflight["source_hashes"], "Les sources diffèrent du préflight.")
    archives = {}
    for case in CASES:
        trial = RUN / case
        cad = trial / "cad"
        files = guard.dependencies(cad, ["assemblages/Prototype_Cartographe.FCStd"])
        auxiliary = [cad / name for name in preflight["source_hashes"] if not name.lower().endswith(".fcstd")]
        service = cad / "pieces/fabriquees/ASSUMED_GO3B_Service.FCStd"
        # Keep disconnected trial geometry explicitly as auxiliary input.
        detached_native = set(cad.rglob("*.FCStd")) - set(files)
        selected = sorted(set(files) | set(auxiliary) | detached_native)
        hashes = {p.relative_to(cad).as_posix(): guard.sha256(p) for p in selected}
        target = DESTINATION / "artefacts" / case / "cad"
        for name, digest in hashes.items():
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copy2(cad / name, destination)
            require(guard.sha256(destination) == digest, f"Archive divergente : {case}/{name}")
        copied = guard.dependencies(target, ["assemblages/Prototype_Cartographe.FCStd"])
        require({p.relative_to(target).as_posix() for p in copied} == {p.relative_to(cad).as_posix() for p in files},
                f"Fermeture déplacée divergente : {case}")
        for name in ("experiment.json", *REPORTS[1:]):
            original = cad / name if name == "experiment.json" else trial / name
            if original.exists():
                destination = target.parent / name
                shutil.copy2(original, destination)
        closure_hashes = {p.relative_to(cad).as_posix(): hashes[p.relative_to(cad).as_posix()] for p in files}
        archives[case] = {"run_root": trial.relative_to(ROOT).as_posix(),
             "root": target.relative_to(ROOT).as_posix(),
             "entrypoint": (target / "assemblages/Prototype_Cartographe.FCStd").relative_to(ROOT).as_posix(),
             "native_closure_count": len(files), "native_sha256": closure_hashes,
             "auxiliary_sha256": {name: digest for name, digest in hashes.items() if name not in closure_hashes},
             "native_bytes": sum(p.stat().st_size for p in files), "byte_identical_to_measured_copy": True,
             "closure_relocated_with_relative_xlinks": True,
             "construction_status": read(trial / "construction.json")["phase"] if (trial / "construction.json").exists() else "WITNESS"}
        print(case, len(files), len(detached_native), flush=True)
    script_dir = DESTINATION / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    for name in ("preparation.py", "construction.py", "snapshot.py", "reouvrir.py", "mesurer_service.py", "archiver.py"):
        shutil.copy2(RUN / name, script_dir / name)
    for folder, names in (
        (".runtime/v21-go3b-electrical", ("replay.py", "summarize.py")),
        (".runtime/v21-go3b-interfaces", ("render.py", "review_native.py", "screen.py")),
    ):
        destination = script_dir / folder.rsplit("-",1)[-1]
        destination.mkdir(exist_ok=True)
        for name in names:
            shutil.copy2(ROOT / folder / name, destination / name)
    write(RUN / "archives.json", {"source_status":"PASS", "source_hashes_after":unchanged, "archives":archives})
    return archives


if __name__ == "__main__":
    publish()
