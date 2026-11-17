"""Contrôle sur les formes sauvegardées des captures RF et du départ F41."""
import argparse
from pathlib import Path

from rf_p70 import measure
from valider_modules import App, Scene, metadata_for, read, require, sha, write

HERE = Path(__file__).resolve().parent
NAV = "sous_assemblages/SA06_Prototype_Navigation.FCStd#"
AVI = "sous_assemblages/SA05_Prototype_Avionique.FCStd#"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fixtures = read(args.fixtures)
    generation = read(args.copy / "verification/generation.json")
    require(fixtures["complete"] and fixtures["native_sha256"] == generation["native_sha256"],
            "Contrôles des pièces différents des natifs")
    scene = Scene(args.copy, metadata_for(args.copy))
    natives = scene.hashes()
    require(all(natives[path] == digest for path, digest in generation["native_sha256"].items()),
            "Natifs divergents")
    capture = {}
    for index, name in enumerate(generation["radio"]["changed_occurrences"]):
        support = scene.items[NAV + name]
        column = scene.items[AVI + "ColonnePorteuse_" + str(1 - index)]
        limits = {AVI + item: scene.items[AVI + item].shape for item in ("CA01", "Holybro6XOrin")}
        gap = support.shape.distToShape(column.shape)[0]
        samples = {}
        for delta, stop in ((-.3, "CA01"), (.3, "Holybro6XOrin")):
            moved = support.shape.copy()
            moved.translate(App.Vector(0, 0, delta))
            result = measure(moved, limits)
            expected = AVI + stop
            require(not result["erreurs"] and any(row["occurrence"] == expected
                    and row["volume_intersection_mm3"] > 1e-4 for row in result["observations"]),
                    "Butée axiale non observée " + name)
            samples[str(delta)] = result
        capture[name] = {"column": column.key, "radial_clearance_mm": gap,
                         "axial_stop_witness_at_offset_mm": samples,
                         "antenna_retention": ("Prise latérale intégrée au support" if index == 0
                                               else "Bande indépendante BandeAntenneRF1")}
    require(natives == scene.hashes(), "Copie modifiée pendant le contrôle")
    check = fixtures["fixtures"]["contacts_intersections_unknowns"]
    ids = {*generation["radio"]["changed_occurrences"], "BandeAntenneRF1",
           "PinceDepartF41", "PressionDepartF41", "BandeDepartF41"}
    anomalies = [row for row in check if ids & {key.split("#")[-1] for key in row["pair"]}
                 and (row["intersection_status"] != "pass" or row["clearance_status"] == "unknown")]
    write(args.output, {
        "complete": True, "native_read_only": True, "native_sha256": generation["native_sha256"],
        "script_sha256": sha(Path(__file__)),
        "nominal_candidates": {"axial_capture": capture, "fixture_pair_anomalies": anomalies},
        "axial_note": "Les translations forcées de 0,3 mm servent à identifier les faces qui bornent le jeu. Elles ne représentent pas des poses nominales ni des efforts.",
        "status": "NON_CONFORME" if anomalies else "CANDIDAT_CONDITIONNEL",
        "open": read(HERE / "integration_radio.json")["open"],
    })


if __name__ == "__main__":
    main()
