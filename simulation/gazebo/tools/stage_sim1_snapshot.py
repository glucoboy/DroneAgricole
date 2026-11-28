"""Copy the saved CAD export inputs to a fresh, private replay workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory


CAD = Path("hardware/mecanique/cartographe")
MODEL = Path("simulation/gazebo/models/cartographe")
FILES = (
    Path("AGENTS.md"),
    CAD / "manifest.json",
    CAD / "nomenclature_prototype.json",
    CAD / "verification/read_brep_prototype.py",
    MODEL / "dynamics_preview.json",
    MODEL / "geometry/mass_ledger.json",
    MODEL / "model.config",
    Path("simulation/gazebo/worlds/cartographe_flat.sdf"),
    Path("simulation/gazebo/ModelBuilder.cpp"),
    Path("simulation/gazebo/ModelBuilder.hpp"),
    Path("simulation/gazebo/tools/cad_export_cartographe.py"),
    Path("simulation/gazebo/tools/cad_export_collisions.py"),
)


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def unique_file(root, relative):
    path = root / relative
    resolved = path.resolve(strict=True)
    if resolved != path or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Fichier non canonique : {relative}")
    return path


def stage(workspace, destination, manufacturer_root):
    private = workspace / ".runtime/sim1"
    destination = workspace / destination
    if (destination.resolve() != destination or not destination.is_relative_to(private) or
            destination == private or destination.exists()):
        raise ValueError("La destination doit être neuve et sous .runtime/sim1/")
    manifest = unique_file(workspace, CAD / "manifest.json")
    configuration = json.loads(manifest.read_bytes())["prototype_cartographe"]
    entries = {CAD / row["fichier"]: row["sha256"]
               for row in configuration["references"] + configuration["assemblages"]}
    manufacturer = {CAD / path: expected for path, expected in configuration["sources_preservees"].items()}
    entries.update(manufacturer)
    declared = {**dict.fromkeys(FILES), **entries}
    sources = {}
    for path, expected in declared.items():
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Chemin non canonique : {path}")
        try:
            source = unique_file(workspace, path)
        except FileNotFoundError:
            if manufacturer_root is None or path not in manufacturer:
                raise
            source = unique_file(manufacturer_root, path)
        observed = sha(source)
        if expected is not None and observed != expected:
            raise ValueError(f"Empreinte différente du manifeste : {path}")
        sources[path] = (source, observed)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".prepare-", dir=destination.parent) as tmp:
        stage_root = Path(tmp) / "snapshot"
        for path, (source, observed) in sources.items():
            copy = stage_root / path
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, copy)
            if sha(copy) != observed:
                raise ValueError(f"Source modifiée pendant la copie : {path}")
        if destination.exists():
            raise FileExistsError(destination)
        stage_root.rename(destination)
    print(f"{len(sources)} fichiers copiés : {destination.relative_to(workspace).as_posix()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--manufacturer-root", type=Path,
                        help="Racine du dépôt contenant les originaux fabricant hors Git")
    args = parser.parse_args()
    stage(args.workspace.resolve(strict=True), args.destination,
          args.manufacturer_root.resolve(strict=True) if args.manufacturer_root else None)


if __name__ == "__main__":
    main()
