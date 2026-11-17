"""Prépare les entrées observées des régressions électriques L4."""

import argparse
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def electrical_cases():
    nominal = read("interconnection_engine/examples/banc_l2.json")
    yield "electrical-nominal", {"dossier": nominal}
    yield "native-l2", {"dossier": nominal}

    wrong_port = copy.deepcopy(nominal)
    records = wrong_port["model"]["records"]
    records["ports"][0]["id"] = "GPS2"
    records["connector_receptacles"][0]["port_id"] = "GPS2"
    wrong_port["interfaces"][0]["required_port_id"] = "GPS2"
    yield "f12-wrong-port", {"dossier": wrong_port, "status": "PASS"}

    unknown_port = copy.deepcopy(nominal)
    records = unknown_port["model"]["records"]
    records["ports"][0].update(id="GPIO", direction="UNKNOWN", evidence_ids=[])
    records["connector_receptacles"][0]["port_id"] = "GPIO"
    yield "f24a-unidentified", {"dossier": unknown_port}

    angled = copy.deepcopy(nominal)
    records = angled["model"]["records"]
    angled["interfaces"][0].update(mate_part_id="fiche-autre-cle", exit_orientation="ELBOW_90")
    wrong_key = next(part for part in angled["catalog"]["parts"] if part["id"] == "fiche-autre-cle")
    records["connector_mates"][0]["part_reference"] = copy.deepcopy(wrong_key["reference"])
    records["connector_mates"][0]["keying"] = copy.deepcopy(wrong_key["attributes"]["keying"])
    wrong_key["attributes"]["keying"]["value"] = "Clé-A"
    yield "angled-incompatible", {"dossier": angled}

    revision = copy.deepcopy(nominal)
    revision["model"]["records"]["connector_mates"][0]["part_reference"]["revision"] = "banc-2"
    yield "manufacturer-revision-conflict", {"dossier": revision}

    missing_data = copy.deepcopy(nominal)
    del missing_data["model"]["records"]["circuits"][-1]
    yield "electrical-missing-data", {"dossier": missing_data}

    rewritten_matrix = copy.deepcopy(nominal)
    records = rewritten_matrix["model"]["records"]
    for pin in records["pins"]:
        if pin["signal"] in {"PAIR_P", "PAIR_N"}:
            pin["signal"] = "PAIR_N" if pin["signal"] == "PAIR_P" else "PAIR_P"
    for circuit in records["circuits"]:
        if circuit["function"] in {"PAIR_P", "PAIR_N"}:
            circuit["function"] = "PAIR_N" if circuit["function"] == "PAIR_P" else "PAIR_P"
    yield "electrical-matrix-tampered", {"dossier": rewritten_matrix, "status": "PASS"}

    benches = read("architecture_decision_engine/fixtures/benches.json")["benches"]
    diagnostic = next(bench for bench in benches if bench["id"] == "diagnostic")
    graph = diagnostic["parameters"]["connection_graph"]
    yield "diagnostic-nominal", {"diagnostic_graph": graph}
    yield "diagnostic-missing-return", {"diagnostic_graph": [edge for edge in graph if edge["signal"] != "RETURN"]}

    yield "electrical-historical-documentary", {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for case_id, data in electrical_cases():
        with (args.output / f"{case_id}.json").open("x", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")


if __name__ == "__main__":
    main()
