import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


BINARY = Path(sys.argv.pop(1)).resolve()
ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "interconnection_engine" / "examples"
FIXTURE = json.loads((EXAMPLES / "banc_l2.json").read_text(encoding="utf-8"))


class InterconnectionTest(unittest.TestCase):
    def setUp(self):
        self.dossier = copy.deepcopy(FIXTURE)
        self.records = self.dossier["model"]["records"]

    def run_cli(self, command="validate", *args, status=0, reports=()):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            dossier = directory / "fixture.json"
            dossier.write_text(json.dumps(self.dossier), encoding="utf-8")
            argv = [str(BINARY), command, str(dossier), *args]
            for i, report in enumerate(reports):
                path = directory / f"research-{i}.json"
                path.write_text(json.dumps(report), encoding="utf-8")
                argv += ["--research", str(path)]
            output = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=10)
            self.assertEqual(output.returncode, status, output.stderr.decode("utf-8", errors="replace"))
            if status == 1:
                self.assertEqual(output.stdout, b"")
                return None
            result = json.loads(output.stdout)
            self.assertEqual(result["input_sha256"], hashlib.sha256(dossier.read_bytes()).hexdigest())
            return result

    def finding(self, report, code, status):
        self.assertIn((code, status), [(f["code"], f["status"]) for f in report["findings"]])

    def test_nominal_and_bom(self):
        report = self.run_cli()
        self.assertEqual([report[k] for k in ("status", "electrical", "compatibility", "geometry")], ["PASS"] * 4)
        self.assertEqual(len(report["continuity"]), 4)
        self.assertEqual(report["continuity"][0]["endpoints"][1]["signal"], "PAIR_P")
        self.assertEqual([e["pin_id"] for e in report["continuity"][0]["endpoints"]], ["pa1", "pb1"])
        bom = {item["part_id"]: item["quantity"] for item in report["candidate_bom"]}
        self.assertEqual(bom, {"cable": 1, "contact-embase": 8, "contact-fiche": 8, "embase": 2,
                               "fiche": 2, "serre-cable": 2})
        self.assertTrue(all(item["status"] == "SYNTHETIC" and item["sources"] for item in report["candidate_bom"]))
        self.assertEqual(len(report["native_plan"]["interfaces"]), 2)

    def test_wrong_f12_port_identity(self):
        self.records["ports"][0]["id"] = "GPS2"
        self.records["connector_receptacles"][0]["port_id"] = "GPS2"
        self.dossier["interfaces"][0]["required_port_id"] = "TELEM1"
        self.finding(self.run_cli(status=2), "WRONG_PORT", "FAIL")

    def test_swapped_pin_mapping(self):
        first, second = self.records["cables"][0]["conductors"][:2]
        first["terminal_ids"][1], second["terminal_ids"][1] = second["terminal_ids"][1], first["terminal_ids"][1]
        report = self.run_cli(status=2)
        self.finding(report, "PIN_MAPPING", "FAIL")
        self.assertEqual(report["geometry"], "PASS")

    def test_reversed_differential_signal_labels(self):
        pins = {pin["id"]: pin for pin in self.records["pins"]}
        pins["pb1"]["signal"], pins["pb2"]["signal"] = pins["pb2"]["signal"], pins["pb1"]["signal"]
        report = self.run_cli(status=2)
        self.finding(report, "SIGNAL_POLARITY", "FAIL")
        self.assertEqual(report["geometry"], "PASS")

    def test_differential_aliases_are_not_treated_as_opposite_signals(self):
        pins = {pin["id"]: pin for pin in self.records["pins"]}
        pins["pb1"]["signal"] = "RECEIVER_P"
        pins["pb2"]["signal"] = "RECEIVER_N"
        self.assertEqual(self.run_cli()["electrical"], "PASS")

    def test_incompatible_same_ways(self):
        report = self.run_cli("mates", "embase")
        candidates = {c["mate_part_id"]: c for c in report["candidates"]}
        self.assertEqual(candidates["fiche"]["prescreen"], "PASS")
        self.assertEqual(candidates["fiche-autre-cle"]["prescreen"], "FAIL")
        self.dossier["interfaces"][0]["mate_part_id"] = "fiche-autre-cle"
        self.finding(self.run_cli(status=2), "keying", "FAIL")

    def test_incorrect_mate_rotation(self):
        frame = next(f for f in self.dossier["model"]["frames"] if f["id"] == "mate-a-frame")
        pose = frame["parent_from_local"]
        for row in pose[:3]:
            row[0] *= -1
            row[1] *= -1
        report = self.run_cli(status=2)
        self.finding(report, "MATING_ORIENTATION", "FAIL")
        self.assertEqual(report["electrical"], "PASS")

    def test_blocked_extraction(self):
        self.dossier["geometry"]["obstacles"].append({"id": "block", "box_mm": [18, -1, -1, 19, 1, 1]})
        self.finding(self.run_cli(status=2), "EXTRACTION_ENVELOPE", "FAIL")

    def add_physical_geometry(self):
        frames = {frame["id"]: frame for frame in self.dossier["model"]["frames"]}
        anchor = frames["mating-a"]
        self.dossier["model"]["frames"] += [
            dict(anchor, id="receptacle-a", parent_from_local=[[1, 0, 0, 0], [0, 1, 0, 0],
                                                              [0, 0, 1, 0], [0, 0, 0, 1]]),
            dict(anchor, id="plug-a", parent_frame_id="mate-a-frame",
                 parent_from_local=[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]),
        ]
        anchor["parent_frame_id"] = "receptacle-a"
        frames["exit-a"]["parent_frame_id"] = "plug-a"
        template = self.dossier["interfaces"][0]["requirements"]["current_A"]

        def envelope(dimensions):
            return {"geometry_class": "CONSERVATIVE_ENVELOPE",
                    "dimensions": dict(template, value=dimensions, unit="mm")}

        geometry = {
            "receptacle_frame_id": "receptacle-a",
            "plug_frame_id": "plug-a",
            "receptacle_body": envelope([-3, -3, 0, 3, 3, 4]),
            "plug_body": envelope([-3, -3, 0, 3, 3, 10]),
            "tool_access_envelope": dict(envelope([-5, -5, 0, 5, 5, 12]),
                                         lock_access_point=dict(template, value=[0, 3, 5], unit="mm")),
            "extraction_sweep": dict(envelope([-4, -4, 0, 4, 4, 18]),
                                     travel=dict(template, value=8, unit="mm")),
        }
        self.dossier["interfaces"][0]["physical_geometry"] = geometry
        return geometry

    def test_same_static_fit_with_distinct_retraction(self):
        geometry = self.add_physical_geometry()
        self.dossier["geometry"]["obstacles"].append({"id": "support-retrait", "box_mm": [20, -1, -1, 21, 1, 1]})
        report = self.run_cli(status=2)
        self.finding(report, "MATED_PLUG", "PASS")
        self.finding(report, "EXTRACTION_ENVELOPE", "FAIL")
        self.assertEqual(report["compatibility"], "PASS")

        # Same mating, shorter axial body, sideward cable exit outside the withdrawal obstacle.
        geometry["plug_body"]["dimensions"]["value"] = [-3, -3, 0, 3, 3, 6]
        geometry["extraction_sweep"]["dimensions"]["value"] = [-4, -4, 0, 4, 4, 14]
        exit_frame = next(f for f in self.dossier["model"]["frames"] if f["id"] == "exit-a")
        exit_frame["parent_from_local"] = [[1, 0, 0, 0], [0, 0, 1, 3], [0, -1, 0, 5], [0, 0, 0, 1]]
        self.records["routes"][0]["points_mm"] = [[9, 3, 0], [9, 5, 0], [18, 5, 0], [30, 0, 0], [86, 0, 0]]
        self.dossier["cable_parts"]["cordon"]["specifications"]["length_mm"]["value"] = 90
        self.dossier["model"]["configuration_id"] = "banc-l2-lateral"
        report = self.run_cli()
        self.finding(report, "EXTRACTION_ENVELOPE", "PASS")
        self.finding(report, "WIRE_EXIT", "PASS")

    def test_mated_body_and_tool_are_checked_independently(self):
        geometry = self.add_physical_geometry()
        self.dossier["geometry"]["obstacles"].append({"id": "latch-blocker", "box_mm": [7, 4.25, -1, 8, 4.5, 1]})
        report = self.run_cli(status=2)
        self.finding(report, "MATED_PLUG", "PASS")
        self.finding(report, "EXTRACTION_ENVELOPE", "PASS")
        self.finding(report, "TOOL_ENVELOPE", "FAIL")
        geometry["tool_access_envelope"]["dimensions"]["value"] = [90, 90, 90, 95, 95, 95]
        self.finding(self.run_cli(status=2), "LOCK_ACCESS_POINT", "FAIL")
        self.dossier["geometry"]["obstacles"][-1]["box_mm"] = [7, 2, -1, 8, 2.5, 1]
        self.finding(self.run_cli(status=2), "MATED_PLUG", "FAIL")

    def test_approximate_geometry_cannot_pass_clearance(self):
        geometry = self.add_physical_geometry()
        geometry["plug_body"]["geometry_class"] = "APPROXIMATION"
        report = self.run_cli(status=3)
        self.finding(report, "MATED_PLUG", "INCONCLUSIVE")
        self.finding(report, "EXTRACTION_SWEEP", "INCONCLUSIVE")
        self.assertEqual(report["electrical"], "PASS")

    def test_plug_geometry_must_reach_the_mating_and_exit_frames(self):
        geometry = self.add_physical_geometry()
        geometry["plug_body"]["dimensions"]["value"] = [-3, -3, 5, 3, 3, 6]
        self.finding(self.run_cli(status=2), "BODY_ANCHORS", "FAIL")

    def test_body_and_exit_follow_moved_equipment_when_attached(self):
        self.add_physical_geometry()
        frame = next(f for f in self.dossier["model"]["frames"] if f["id"] == "mate-a-frame")
        frame.update(parent_frame_id="mating-a",
                     parent_from_local=[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        report = self.run_cli("validate", "--state", "equipement-tourne", status=2)
        self.finding(report, "MATING_ORIENTATION", "PASS")
        self.finding(report, "WIRE_EXIT", "FAIL")
        first = report["native_plan"]["interfaces"][0]
        self.assertEqual(first["physical_geometry"]["plug_frame"], first["receptacle_mating"])

    def test_wrong_cavity_independent_of_geometry(self):
        contacts = [x for x in self.records["contacts"] if x["owner_id"] == "mate-a"]
        contacts[0]["cavity"], contacts[1]["cavity"] = contacts[1]["cavity"], contacts[0]["cavity"]
        report = self.run_cli(status=2)
        self.finding(report, "CONTACT_MAPPING", "FAIL")
        self.assertEqual(report["geometry"], "PASS")

    def test_physical_pin_number_matches_documented_cavity(self):
        interface = self.dossier["interfaces"][0]
        interface["receptacle_pinout"] = dict(interface["requirements"]["current_A"], unit="1",
                                               value={str(n): str(n) for n in range(1, 5)})
        self.finding(self.run_cli(), "PHYSICAL_PIN_NUMBER", "PASS")
        first, second = self.records["pins"][:2]
        first["number"], second["number"] = second["number"], first["number"]
        report = self.run_cli(status=2)
        self.finding(report, "PHYSICAL_PIN_NUMBER", "FAIL")
        self.assertEqual(report["geometry"], "PASS")

    def test_missing_exit(self):
        self.dossier["interfaces"][0]["exit_frame_id"] = None
        self.finding(self.run_cli(status=3), "MATING_FRAMES", "INCONCLUSIVE")

    def test_missing_supplier_source(self):
        self.dossier["catalog"]["parts"][1]["reference"]["evidence_ids"] = []
        self.finding(self.run_cli(status=3), "PART_PROVENANCE", "INCONCLUSIVE")

    def test_generic_cad_termination(self):
        self.records["terminals"][0].update(kind="FREE_END", contact_id=None)
        self.finding(self.run_cli(status=2), "TERMINAL_CONTACT", "FAIL")

    def test_generic_cad_axis_endpoint(self):
        self.records["routes"][0]["points_mm"][0] = [14, 0, 1]
        self.finding(self.run_cli(status=2), "WIRE_EXIT", "FAIL")

    def test_coordinated_exit_and_axis_displacement(self):
        frame = next(item for item in self.dossier["model"]["frames"] if item["id"] == "exit-a")
        frame["parent_from_local"][2][3] = 7
        self.records["routes"][0]["points_mm"][0] = [11, 0, 0]
        self.dossier["cable_parts"]["cordon"]["specifications"]["length_mm"]["value"] = 75
        report = self.run_cli(status=2)
        self.finding(report, "INTERFACE_REFERENCE_POSE", "FAIL")
        self.finding(report, "WIRE_EXIT", "FAIL")
        exit_check = report["native_plan"]["interfaces"][0]["interface_reference"]["poses"]["mate_contact_from_exit"]
        self.assertEqual((exit_check["expected_local"][11], exit_check["observed_local"][11]), (10, 7))
        self.assertEqual((exit_check["expected_world"][3], exit_check["observed_world"][3]), (14, 11))

    def test_external_authority_must_match_the_campaign_digest(self):
        path = ROOT / "interconnection_engine/fixtures/banc_l2_interface_reference.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        report = self.run_cli("validate", "--interface-authority", path, "--interface-authority-sha256", digest)
        self.assertEqual(report["interface_reference_sha256"], digest)
        self.run_cli("validate", "--interface-authority", path, "--interface-authority-sha256", "0" * 64, status=1)

    def test_synthetic_authority_cannot_issue_supplier_attestations(self):
        fixture = ROOT / "interconnection_engine/fixtures/banc_l2_interface_reference.json"
        authority = json.loads(fixture.read_text(encoding="utf-8"))
        authority["supplier_documents"] = [{"status": "SUPPLIER_DOCUMENT_VERIFIED", "mpn": "BANC-embase"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authority.json"
            path.write_text(json.dumps(authority), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.run_cli("validate", "--interface-authority", path, "--interface-authority-sha256", digest, status=1)

    def test_unknown_pinout(self):
        self.records["pins"][0]["evidence_ids"] = []
        self.finding(self.run_cli(status=3), "CONTACT_MAPPING", "INCONCLUSIVE")

    def test_equipment_reorientation(self):
        report = self.run_cli("validate", "--state", "equipement-tourne", status=2)
        self.finding(report, "MATING_ORIENTATION", "FAIL")
        self.assertEqual(report["electrical"], "PASS")

    def test_contact_reference_and_pin_number(self):
        self.records["contacts"][0]["part_reference"]["evidence_ids"] = []
        self.finding(self.run_cli(status=3), "CONTACT_REFERENCE", "INCONCLUSIVE")
        self.records["pins"][1]["number"] = self.records["pins"][0]["number"]
        self.finding(self.run_cli(status=2), "PIN_NUMBER", "FAIL")

    def test_contact_count(self):
        for part in self.dossier["catalog"]["parts"][:2]:
            part["attributes"]["ways"]["value"] = 1
        self.finding(self.run_cli(status=2), "CONTACT_COUNT", "FAIL")

    def test_missing_travel_and_detached_envelope(self):
        interface = self.dossier["interfaces"][0]
        travel = interface.pop("extraction_travel_mm")
        self.finding(self.run_cli(status=3), "EXTRACTION_SWEEP", "INCONCLUSIVE")
        interface.update(extraction_travel_mm=travel, extraction_box_local_mm=[90, 90, 90, 91, 91, 91])
        self.finding(self.run_cli(status=2), "EXTRACTION_SWEEP", "FAIL")

    def test_short_cable_and_inverted_temperature(self):
        specs = self.dossier["cable_parts"]["cordon"]["specifications"]
        specs["length_mm"]["value"] = 1
        specs["temperature_min_C"]["value"] = 90
        report = self.run_cli(status=2)
        self.finding(report, "CORD_LENGTH", "FAIL")
        self.finding(report, "CABLE_TEMPERATURE", "FAIL")

    def test_length_checks_detour_between_unchanged_endpoints(self):
        self.records["routes"][0]["points_mm"] = [
            [14, 0, 0], [30, 0, 0], [30, 20, 0], [60, 20, 0], [60, 0, 0], [86, 0, 0],
        ]
        self.finding(self.run_cli(status=2), "CORD_LENGTH", "FAIL")
        self.dossier["cable_parts"]["cordon"]["specifications"]["length_mm"]["value"] = 112
        self.assertEqual(self.run_cli()["geometry"], "PASS")

    def test_missing_accessory_and_broken_differential_group(self):
        self.dossier["interfaces"][0]["component_part_ids"] = []
        self.finding(self.run_cli(status=3), "ACCESSORY_COVERAGE", "INCONCLUSIVE")
        self.records["circuits"][0]["group_id"] = None
        self.finding(self.run_cli(status=2), "SIGNAL_GROUP", "FAIL")

    def test_unverified_prototype_source(self):
        self.dossier["mode"] = "PROTOTYPE_CANDIDATE"
        self.dossier["model"]["scope"] = "CARTOGRAPHE"
        evidence = self.records["technical_evidence"][0]
        evidence.update(kind="SOURCE", domain="DOCUMENT", hypothetical=False,
                        artifact_path="missing/not-a-source.pdf", sha256="0" * 64)
        for part in self.dossier["catalog"]["parts"]:
            part["origin"] = "SUPPLIER"
            for value in (part["reference"], *part["attributes"].values()):
                value["status"] = "SOURCED"
        candidates = self.run_cli("mates", "embase")["candidates"]
        self.assertTrue(all(c["prescreen"] != "PASS" for c in candidates))
        self.finding(self.run_cli(status=3), "SUPPLIER_APPLICABILITY", "INCONCLUSIVE")

    def test_wrong_l1_configuration_and_empty_chain(self):
        self.dossier = json.loads((EXAMPLES / "cartographe_candidats.json").read_text(encoding="utf-8"))
        self.finding(self.run_cli(status=3), "RESEARCH_MISSING", "INCONCLUSIVE")
        unrelated = {"schema_version": "1.0.0", "configuration_id": "other", "issue_id": "F12-TELEM1-REVISION",
                     "outcome": "RESOLVED"}
        self.run_cli(status=1, reports=(unrelated,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
