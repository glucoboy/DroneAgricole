import copy
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from electromechanical_engine import contracts
from electromechanical_engine.contracts import (
    ContractError, freeze, load, open_reference, validate_candidate, validate_requirements,
    validate_system,
)
from electromechanical_engine.search import explore


FIXTURE = Path(__file__).parent / "fixtures" / "banc"


class ReferenceTests(unittest.TestCase):
    def test_frozen_reference_round_trip(self):
        with TemporaryDirectory() as temp:
            destination = Path(temp) / "reference"
            lock = freeze(FIXTURE, destination)
            system, requirements, verified = open_reference(destination)
            self.assertEqual(verified, lock)
            self.assertEqual(requirements["system_id"], system["id"])
            self.assertEqual(len(lock["reference_sha256"]), 64)
            self.assertTrue(lock["frozen_at_utc"].endswith("+00:00"))

    def test_detects_reference_mutation_even_if_json_equivalent(self):
        with TemporaryDirectory() as temp:
            destination = Path(temp) / "reference"
            freeze(FIXTURE, destination)
            with (destination / "design_requirements.yaml").open("a", encoding="utf-8") as stream:
                stream.write("\n")
            with self.assertRaisesRegex(ContractError, "empreinte"):
                open_reference(destination)
            with self.assertRaises(FileExistsError):
                freeze(FIXTURE, destination)

    def test_freeze_does_not_publish_lock_after_source_or_copy_divergence(self):
        for affected_directory, message in (("source", "sources"), ("reference", "copies")):
            with self.subTest(affected_directory=affected_directory), TemporaryDirectory() as temp:
                root = Path(temp)
                source = copytree(FIXTURE, root / "source")
                destination = root / "reference"
                changed = root / affected_directory / "design_requirements.yaml"
                digest = contracts.digest

                def mutate_before_hash(path):
                    if path == changed:
                        with path.open("ab") as stream:
                            stream.write(b"\n")
                    return digest(path)

                with patch.object(contracts, "digest", side_effect=mutate_before_hash):
                    with self.assertRaisesRegex(ContractError, message):
                        freeze(source, destination)
                self.assertFalse((destination / "reference_lock.json").exists())
                with self.assertRaises(FileNotFoundError):
                    open_reference(destination)

    def test_detects_duplicate_key_and_nonfinite_value(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            for raw in ('{"id": 1, "id": 2}', '{"value": NaN}'):
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(ContractError):
                    load(path)

    def test_system_rejects_dangling_port_and_requires_explicit_unknown(self):
        system = load(FIXTURE / "system_model.json")
        changed = copy.deepcopy(system)
        changed["links"][0]["target"] = "not-there"
        with self.assertRaisesRegex(ContractError, "extrémités"):
            validate_system(changed)
        changed = copy.deepcopy(system)
        changed["ports"][0]["status"] = "INCONNUE"
        with self.assertRaisesRegex(ContractError, "INCONNUE"):
            validate_system(changed)
        changed["ports"][0]["interface"] = None
        validate_system(changed)

    def test_rejects_incomplete_requirements(self):
        system = load(FIXTURE / "system_model.json")
        requirements = load(FIXTURE / "design_requirements.yaml")
        requirements["links"].clear()
        with self.assertRaisesRegex(ContractError, "liaisons"):
            validate_requirements(system, requirements)

    def test_rejects_invalid_cavity_list_and_corridor_limit(self):
        system = load(FIXTURE / "system_model.json")
        system["links"][0]["source_cavities"] = ["1", "1"]
        with self.assertRaisesRegex(ContractError, "identifiants dupliqués"):
            validate_system(system)
        system["links"][0]["source_cavities"] = ["1"]
        system["corridors"][0]["max_carrier_distance_mm"] = -1
        with self.assertRaisesRegex(ContractError, "max_carrier_distance_mm"):
            validate_system(system)

    def test_rejects_duplicate_extraction_and_clearance_without_obstacles(self):
        system = load(FIXTURE / "system_model.json")
        first = system["geometry"]["extraction"][0]
        system["geometry"]["extraction"].append(copy.deepcopy(first))
        with self.assertRaisesRegex(ContractError, "dupliqué"):
            validate_system(system)
        system["geometry"]["extraction"].pop()
        first["ignore_ids"] = ["Deck", "Obstacle", "L1"]
        with self.assertRaisesRegex(ContractError, "sans obstacle"):
            validate_system(system)
        first["ignore_ids"] = ["absent"]
        with self.assertRaisesRegex(ContractError, "hors inventaire"):
            validate_system(system)

    def test_rejects_ambiguous_contact_and_zero_radius(self):
        system = load(FIXTURE / "system_model.json")
        requirements = load(FIXTURE / "design_requirements.yaml")
        requirements["allowed_contacts"].append({"a": "Obstacle", "b": "Deck",
                                                   "relation": "functional_contact", "source": "test"})
        with self.assertRaisesRegex(ContractError, "dupliquée"):
            validate_requirements(system, requirements)
        requirements["allowed_contacts"].pop()
        requirements["links"]["L1"]["min_radius_mm"] = 0
        with self.assertRaisesRegex(ContractError, "min_radius_mm"):
            validate_requirements(system, requirements)

    def test_candidate_cannot_change_reference_or_requirements(self):
        candidate = {"version": 1, "id": "C1", "family": "MATERIEL_CONSTANT",
                     "reference_sha256": "a" * 64, "connections": [], "routes": {}}
        validate_candidate(candidate, "a" * 64)
        with self.assertRaisesRegex(ContractError, "autre référentiel"):
            validate_candidate(candidate, "b" * 64)
        candidate["requirements"] = {"clearance_mm": 0}
        with self.assertRaisesRegex(ContractError, "critères"):
            validate_candidate(candidate, "a" * 64)

    def test_mobile_fixture_freezes_poses_and_rejects_uncovered_routes(self):
        fixture = FIXTURE.with_name("banc_mobile")
        with TemporaryDirectory() as temp:
            destination = Path(temp) / "reference"
            freeze(fixture, destination)
            system, requirements, lock = open_reference(destination)
        space = load(fixture / "design_space.json")
        candidates = explore(system, space, lock["reference_sha256"], requirements)["candidates"]
        self.assertEqual(len(candidates), 5)
        self.assertEqual(candidates[0]["routes"], candidates[1]["routes"])
        self.assertNotEqual(candidates[0]["motion_routes"], candidates[1]["motion_routes"])
        candidate = candidates[0]
        validate_candidate(candidate, lock["reference_sha256"], system, requirements)
        candidate["motion_routes"]["extra"] = {}
        with self.assertRaisesRegex(ContractError, "état hors référentiel"):
            validate_candidate(candidate, lock["reference_sha256"], system, requirements)
        del candidate["motion_routes"]["extra"]
        requirements["links"]["L1"]["required_motion_states"].remove("extreme")
        with self.assertRaisesRegex(ContractError, "mouvement de liaison non prévu"):
            validate_candidate(candidate, lock["reference_sha256"], system, requirements)
        with self.assertRaisesRegex(ContractError, "ports mobiles"):
            validate_requirements(system, requirements)

    def test_closed_retention_bore_and_wall_must_fit_reference_geometry(self):
        system = load(FIXTURE.with_name("banc_mobile") / "system_model.json")
        support = system["geometry"]["boxes"][1]
        support["through_bore_x"]["radius_mm"] = 2
        with self.assertRaisesRegex(ContractError, "alésage intérieur"):
            validate_system(system)
        support["through_bore_x"]["radius_mm"] = 1
        system["geometry"]["anchors"][0]["retentions"][0]["capture_wall_mm"] = 0
        with self.assertRaisesRegex(ContractError, "capture_wall_mm"):
            validate_system(system)


if __name__ == "__main__":
    unittest.main()
