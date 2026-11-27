"""Exercise the C++ model verifier and private publication entry points."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
import xml.etree.ElementTree as ET


CAD = Path("hardware/mecanique/cartographe")
MODEL = Path("simulation/gazebo/models/cartographe")
GEOMETRY = MODEL / "geometry/geometry_manifest.json"
COLLISIONS = MODEL / "geometry/collision_model.json"
WORLD = Path("simulation/gazebo/worlds/cartographe_flat.sdf")
AIRFRAME = Path("simulation/px4_sitl/airframes/40000_gz_cartographe")


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def json_write(path, payload):
    write(path, json.dumps(payload, indent=2).encode("utf-8") + b"\n")


def fixture(root, sources):
    write(root / "AGENTS.md", b"SYNTHETIC_PREVIEW fixture\n")
    native = root / CAD / "fixture.fcstd"
    write(native, b"Verification fixture; no saved CAD export is claimed.\n")
    json_write(root / CAD / "manifest.json", {"prototype_cartographe": {
        "references": [{"fichier": "fixture.fcstd", "sha256": sha(native)}],
        "assemblages": [], "sources_preservees": {}}})
    write(root / CAD / "nomenclature_prototype.json", b"{}\n")
    write(root / CAD / "verification/read_brep_prototype.py", b"# fixture\n")
    for name in ("ModelBuilder.cpp", "ModelBuilder.hpp", "tools/cad_export_cartographe.py",
                 "tools/cad_export_collisions.py"):
        write(root / "simulation/gazebo" / name, b"# immutable fixture\n")
    for name in ("dynamics_preview.json", "model.config"):
        write(root / MODEL / name, (sources / MODEL / name).read_bytes())
    json_write(root / MODEL / "geometry/mass_ledger.json", {"mass_complete_g": None})
    write(root / WORLD, b"<sdf version='1.9'><world name='cartographe_flat'/></sdf>\n")

    # A single triangle in a binary STL, used only as deterministic test data.
    stl = bytes(80) + struct.pack("<I12fH", 1, 0, 0, 1, 0, 0, 0, .1, 0, 0, 0, .1, 0, 0)
    body = "meshes/cartographe_body.stl"
    write(root / MODEL / body, stl)
    rotors = []
    for index, (x, y) in enumerate(((.2, .2), (-.2, .2), (-.2, -.2), (.2, -.2)), 1):
        name = f"meshes/rotor_{index}.stl"
        write(root / MODEL / name, stl)
        rotors.append({"cad_occurrence": f"Helice_{index}", "mesh": name,
                       "sha256": sha(root / MODEL / name), "position_m": [x, y, .1],
                       "axis_flu": [0, 0, 1], "cad_label_rotation": "CCW" if index > 2 else "CW"})
    json_write(root / GEOMETRY, {
        "finalized": True, "frame": {"scale": .001},
        "sources": {"cad_manifest_sha256": sha(root / CAD / "manifest.json"),
                    "dependencies_relative_to_cad_directory": {"fixture.fcstd": sha(native)}},
        "geometry": {"body_mesh": {"path": body, "sha256": sha(root / MODEL / body)}, "rotors": rotors},
    })
    json_write(root / COLLISIONS, {
        "geometry_manifest_sha256": sha(root / GEOMETRY),
        "boxes": [{"name": "pad", "centre_m": [0, 0, 0], "size_m": [.1, .1, .05]}],
    })


def run(argv, refusal=None, timeout=25):
    command = list(map(str, argv))
    result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    if refusal is None:
        assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
    else:
        assert result.returncode == 1 and refusal in result.stderr, (
            command, result.returncode, result.stdout, result.stderr)
        print(f"REFUSED {refusal}")
    return result


def check_sdf(path, airframe, expected_boxes):
    root = ET.parse(path).getroot()
    model = root.find("model")
    assert model.attrib["name"] == "cartographe"
    assert len(model.findall("link")) == 5
    assert len(model.findall("joint")) == 4
    assert len(model.findall("./link[@name='base_link']/collision")) == expected_boxes
    assert len(model.findall("./link/collision/geometry/cylinder")) == 4
    assert [item.text for item in model.findall("./joint/axis/xyz")] == ["0 0 1"] * 4
    assert [item.text for item in model.findall("./plugin/turningDirection")] == ["ccw", "ccw", "cw", "cw"]
    assert [item.text for item in model.findall("./plugin/motorNumber")] == ["0", "1", "2", "3"]
    resources = [uri.text for uri in model.findall("./link/visual/geometry/mesh/uri")]
    assert len(resources) == len(set(resources)) == 5
    assert all(uri.startswith("model://cartographe/") and
               (path.parent / uri.removeprefix("model://cartographe/")).is_file() for uri in resources)
    code = airframe.read_text(encoding="utf-8")
    assert "PX4_SIMULATOR=gz" in code and "CA_ROTOR_COUNT 4" in code
    assert all(f"CA_ROTOR{index}_AZ -1" in code for index in range(4))


def check_preview_mass(path):
    proof = read(path)
    assert proof["mass_scenario_kg"] == 6 and proof["physical_mass_identified"] is False
    assert [row["function"] for row in proof["rotor_allocation"]] == [101, 102, 103, 104]
    assert [row["cad_occurrence"] for row in proof["rotor_allocation"]] == [
        "Helice_4", "Helice_3", "Helice_2", "Helice_1"]
    assert all(row["axis_frd"] == [0, 0, -1] for row in proof["rotor_allocation"])


def rejection_tests(exe, root, sources):
    # Exact historical inputs, read-only even if the model is later brought up to date.
    run([exe, "verify", sources, MODEL], "stale CAD manifest")
    verify = [exe, "verify", root, MODEL]
    cases = [
        (root / CAD / "manifest.json", b" ", "stale CAD manifest"),
        (root / CAD / "fixture.fcstd", b"changed", "stale dependency fixture.fcstd"),
        (root / MODEL / "meshes/cartographe_body.stl", b"changed", "stale body mesh"),
        (root / MODEL / "meshes/rotor_1.stl", b"changed", "stale rotor mesh"),
    ]
    for path, suffix, refusal in cases:
        original = path.read_bytes()
        try:
            path.write_bytes(original + suffix)
            run(verify, refusal)
        finally:
            path.write_bytes(original)
    original = (root / COLLISIONS).read_bytes()
    collisions = json.loads(original)
    collisions["geometry_manifest_sha256"] = "0" * 64
    json_write(root / COLLISIONS, collisions)
    run(verify, "stale collisions")
    (root / COLLISIONS).write_bytes(original)
    run(verify)


def publication_tests(exe, publication, root):
    def attempt(relative, reason):
        run([exe, "rebuild", root, sys.executable, relative], reason)

    exists = ".runtime/existing/cartographe"
    marker = root / exists / "already-present.txt"
    write(marker, b"preserve\n")
    attempt(exists, "Le dossier existe")
    assert marker.read_bytes() == b"preserve\n"
    attempt(".runtime/../.runtime/dots/cartographe", "NON_CANONICAL_PATH")
    attempt("hardware/mecanique/cartographe/cartographe", "OUTPUT_OVERLAPS_SOURCE")
    external = root / "target"
    external.mkdir()
    alias = root / ".runtime/alias"
    if os.name == "nt":
        process = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(external)],
                                 capture_output=True, timeout=5)
        assert process.returncode == 0, process.stderr
    else:
        alias.symlink_to(external, target_is_directory=True)
    attempt(".runtime/alias/cartographe", "NON_CANONICAL_PATH")
    assert list(external.iterdir()) == []
    link = root / CAD / "hardlink.fcstd"
    os.link(root / CAD / "fixture.fcstd", link)
    try:
        run([exe, "verify", root, MODEL], "NON_CANONICAL_PATH")
    finally:
        link.unlink()
    result = run([publication, root])
    assert "STALE_SOURCE_DURING_EXPORT:" in result.stdout
    print(result.stdout.rstrip())


def native(args):
    if not args.private_root or not args.freecad_python:
        print("NOT_RUN: configure CARTOGRAPHE_SIM1_PRIVATE_ROOT and CARTOGRAPHE_SIM1_FREECAD_PYTHON")
        return 77
    root = Path(args.private_root).resolve(strict=True)
    assert root.is_relative_to((args.workspace / ".runtime").resolve())
    python = Path(args.freecad_python)
    if not python.is_file():
        print("NOT_RUN: Python FreeCAD missing")
        return 77
    input_manifest = read(root / CAD / "manifest.json")["prototype_cartographe"]
    sealed = {row["fichier"]: row["sha256"] for row in input_manifest["references"] + input_manifest["assemblages"]}
    sealed.update(input_manifest["sources_preservees"])
    absent = [name for name in sealed if not (root / CAD / name).is_file()]
    if absent:
        print(f"NOT_RUN: missing sealed sources: {absent}")
        return 77
    output = Path(".runtime/sim1-tests") / uuid4().hex / "cartographe"
    result = run([args.model, "rebuild", root, python, output], timeout=910)
    manifest = json.loads(result.stdout)
    assert manifest["finalized"] and manifest["regenerated_from_cad"]
    assert manifest["mass_scenario_kg"] == 6
    folder = root / output
    for name, expected in manifest["files_sha256"].items():
        assert sha(folder / name) == expected, name
    for name, expected in manifest["sources_sha256"].items():
        assert sha(root / name) == expected, name
    snapshot = read(folder / "snapshot_manifest.json")
    assert snapshot["mode"] == "SYNTHETIC_PREVIEW"
    assert snapshot["sources_sha256"] == manifest["sources_sha256"]
    geometry = read(folder / "geometry/geometry_manifest.json")
    collision = read(folder / "geometry/collision_model.json")
    assert geometry["geometry"]["published_bbox_max_error_mm"] <= 1
    assert geometry["checks"]["mesh_bbox_errors_within_deflection_plus_point_one_mm"]
    assert geometry["counts"]["rotors"] == len(collision["rotor_collisions"]) == 4
    assert len(list((folder / "meshes").glob("*.stl"))) == 5
    assert len(collision["boxes"]) == collision["body_collision_count"]
    assert collision["checks"]["all_box_sizes_positive"]
    assert ET.parse(folder / "preview_world.sdf").findtext("./world/include/uri") == "model://cartographe"
    assert ET.parse(folder / "model.config").findtext("./sdf") == "model.sdf"
    check_sdf(folder / "model.sdf", folder / "40000_gz_cartographe", len(collision["boxes"]))
    check_preview_mass(folder / "model_checks.json")
    run([args.model, "verify", root, output])
    run([args.model, "verify", root, output, "--physical"], "physical mode unavailable: mass/CG/inertias")
    print(f"PASS {folder} ({geometry['counts']['leaf_occurrences']} occurrences, {len(collision['boxes'])} boxes)")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("test", choices=("generation", "reject_unknown_mass", "reject_stale_inputs",
                                        "reject_snapshot_publication", "generation_native"))
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--private-root")
    parser.add_argument("--freecad-python")
    args = parser.parse_args()
    if args.test == "generation_native":
        return native(args)
    temp = args.workspace / ".runtime/sim1-tests"
    temp.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="fixture-", dir=temp) as directory:
        root = Path(directory).resolve()
        fixture(root, args.workspace)
        if args.test == "generation":
            run([args.model, root])
            check_sdf(root / MODEL / "model.sdf", root / AIRFRAME, 1)
            check_preview_mass(root / MODEL / "model_checks.json")
        elif args.test == "reject_unknown_mass":
            run([args.model, "verify", root, MODEL])
            run([args.model, "verify", root, MODEL, "--physical"], "physical mode unavailable: mass/CG/inertias")
            assert not (root / MODEL / "model.sdf").exists()
        elif args.test == "reject_stale_inputs":
            rejection_tests(args.model, root, args.workspace)
        else:
            publication_tests(args.model, args.publication, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
