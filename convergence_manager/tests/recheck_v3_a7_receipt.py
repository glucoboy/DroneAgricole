"""Recalcul indépendant du dossier et du reçu A.7, sur un dépôt privé."""

import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path, PurePosixPath


def sha(data):
    return hashlib.sha256(data).hexdigest()


def distinct_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clé JSON en double : {key}")
        result[key] = value
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=distinct_pairs, parse_float=Decimal)


def confirm(condition, reason):
    if not condition:
        raise ValueError(reason)


def content(root, reference):
    posix = PurePosixPath(reference["path"])
    confirm(not posix.is_absolute() and posix.as_posix() == reference["path"] and ".." not in posix.parts
            and "\\" not in reference["path"] and ":" not in reference["path"], "Chemin source invalide")
    path = root.joinpath(*posix.parts)
    confirm(path.resolve(strict=True) == path, "Chemin source redirigé")
    data = path.read_bytes()
    confirm(sha(data) == reference["sha256"], "Empreinte source divergente")
    return data


def close(left, right, tolerance=1e-7):
    confirm(math.isclose(float(left), float(right), abs_tol=tolerance, rel_tol=0), "Valeur recalculée divergente")


def check_datum(detail, frame, policy_frame):
    def rows(values):
        confirm(len(values) == 16, "Taille de matrice invalide")
        return [list(map(float, values[off:off + 4])) for off in range(0, 16, 4)]

    def times(left, right):
        return [[sum(a * b for a, b in zip(row, col)) for col in zip(*right)] for row in left]

    def direction_matches(observed, expected):
        magnitude = math.hypot(*observed)
        confirm(magnitude > 1e-7, "Direction nulle")
        for component, target in zip(observed, expected):
            close(component / magnitude, target)

    transform = rows(frame["local_to_parent"])
    inverse = rows(frame["parent_to_local"])
    reference = rows(policy_frame["local_to_parent"])
    for candidate in (transform, inverse):
        confirm(len(candidate[3]) == 4, "Forme de matrice invalide")
        for col in range(4):
            close(candidate[3][col], int(col == 3))
        rotation = [row[:3] for row in candidate[:3]]
        for row, unit in enumerate(times(rotation, list(zip(*rotation)))):
            for col, value in enumerate(unit):
                close(value, int(row == col))
        a, b, c = rotation
        close(a[0] * (b[1] * c[2] - b[2] * c[1])
              - a[1] * (b[0] * c[2] - b[2] * c[0])
              + a[2] * (b[0] * c[1] - b[1] * c[0]), 1)
    for product in (times(transform, inverse), times(inverse, transform)):
        for row, values in enumerate(product):
            for col, value in enumerate(values):
                close(value, int(row == col))
    confirm(frame["datum"] == policy_frame["datum"] and frame["parent"] == policy_frame["parent"],
            "Association datum-parent divergente")
    for measured, expected in zip(transform[:3], reference[:3]):
        for value, target in zip(measured[:3], expected[:3]):
            close(value, target, float(policy_frame["rotation_entry_tolerance"]))
    confirm(math.dist([row[3] for row in transform[:3]], [row[3] for row in reference[:3]])
            <= float(policy_frame["position_tolerance_mm"]), "Écart d’origine hors tolérance")
    x, y, z, translation = list(zip(*transform[:3]))
    direction_matches(tuple(map(float, detail["x_direction"])), x)
    y_source = tuple(map(float, detail["y_direction"]))
    # Projeter Y sur le plan XY en contrôlant indépendamment le terme suivant Z.
    confirm(abs(sum(a * b for a, b in zip(y_source, z))) <= 1e-7 * math.hypot(*y_source),
            "Témoin Y hors plan")
    confirm(sum(a * b for a, b in zip(y_source, y)) > 1e-7 * math.hypot(*y_source), "Sens de Y divergent")
    confirm(detail["normal_sign"] in (1, -1), "Signe de normale invalide")
    direction_matches(tuple(float(c) * detail["normal_sign"] for c in detail["observed_normal"]), z)
    for observed, expected in zip(detail["origin_mm"], translation):
        close(observed, expected)


def check_margin(record, policy_check, check, observation):
    measurement = record["measurement"]
    tolerance = measurement["tolerance"]
    confirm(measurement["kind"] == policy_check["kind"] == check["kind"]
            and tolerance["unit"] == check["unit"] and tolerance["comparison"] == check["comparison"]
            and tolerance == policy_check["tolerance"] and measurement["unit"] == policy_check["input_unit"],
            "Quantité ou limite divergente")
    factors = {"mm": Decimal(1), "cm": Decimal(10), "in": Decimal("25.4")}
    source, destination = measurement["unit"], tolerance["unit"]
    confirm(source == destination or (source in factors and destination in factors), "Unités incompatibles")
    factor = factors[source] / factors[destination] if source != destination else Decimal(1)
    value, radius, resolution = (Decimal(measurement[key]) * factor for key in ("value", "uncertainty", "resolution"))
    confirm(resolution > 0 and radius >= resolution / 2 and policy_check["plausible_min"] <= value
            <= policy_check["plausible_max"], "Incertitude ou plage invalide")
    low, high = value - radius, value + radius
    margin = low - tolerance["limit"] if tolerance["comparison"] == "GE" else tolerance["limit"] - high
    # Recalcul décimal indépendant, avec la marge d'arrondi spécifiée par A.4.
    epsilon = Decimal(2) ** -50 * max(1, abs(low), abs(high), abs(tolerance["limit"]))
    confirm(margin > epsilon and observation["status"] == "PASS", "Marge insuffisante")
    for output, target in zip(observation["measurement_interval"], (low, high), strict=True):
        close(output, target)
    close(observation["conservative_margin"], margin)
    confirm(observation["limit_unit"] == destination, "Unité de sortie divergente")


def check_record(root, record, detail, policy, check, observation, parent, submission):
    identity = policy["identities"][record["subject"]]
    policy_check = policy["checks"][check["id"]]
    confirm(record["review"] is None and record["capture"]["power_state"] == "DEENERGIZED"
            and record["capture"]["detached"] is True, "Contexte de relevé ou revue invalide")
    confirm(record["issue"] == policy_check["issue"] and record["subject"] == policy_check["subject"] == check["subject"]
            and record["identity"] == identity["identity"] and record["frame"]["parent"] == parent,
            "Identité, occurrence ou portée divergente")
    facts = record["facts"]
    confirm(facts == policy_check["facts"] and facts["carrier"] == submission["carrier"]
            and facts["assembly_id"] == submission["assembly_id"]
            and all(facts[key] in allowed for key, allowed in check.get("facts", {}).items()), "Faits contradictoires")
    sources = record["sources"]
    for field in ("raw", "photo", "identity_photo", "manufacturer_document", "tolerance_document"):
        content(root, sources[field])
    confirm(sources["identity_photo"]["sha256"] == identity["identity_photo_sha256"]
            and sources["manufacturer_document"]["sha256"] == identity["manufacturer_sha256"]
            and sources["manufacturer_locator"] == identity["manufacturer_locator"]
            and sources["manufacturer_revision"] == identity["manufacturer_revision"]
            and sources["tolerance_document"]["sha256"] == policy_check["tolerance_sha256"],
            "Provenance applicable divergente")
    if detail["calibration"] is not None:
        content(root, detail["calibration"])
    confirm(set(detail["artifacts"]) == set(check["artifacts"]), "Pièces complémentaires manquantes")
    hashes = {sha(content(root, reference)) for reference in detail["artifacts"].values()}
    confirm(len(hashes) == len(check["artifacts"]), "Pièces complémentaires répétées")
    check_datum(detail, record["frame"], policy_check["frame"])
    check_margin(record, policy_check, check, observation)


def recheck(matrix_path, root, submission_path, receipt_path, current_sha, policy_path, policy_sha):
    matrix_bytes, policy_bytes = matrix_path.read_bytes(), policy_path.read_bytes()
    matrix, policy = decode(matrix_bytes), decode(policy_bytes)
    submitted = content(root, {"path": submission_path, "sha256": current_sha})
    submission = decode(submitted)
    packet_bytes = content(root, submission["packet"])
    packet = decode(packet_bytes)
    receipt_bytes = receipt_path.read_bytes()
    receipt = decode(receipt_bytes)
    confirm(receipt["schema"] == "v3.a7.completeness/1" and receipt["status"] in ("ANALYZED", "NOT_RUN")
            and receipt["matrix_sha256"] == sha(matrix_bytes) and receipt["submission_sha256"] == current_sha
            and receipt["packet_sha256"] == sha(packet_bytes) and receipt["policy_sha256"] == policy_sha == sha(policy_bytes)
            and receipt["classification"] == submission["classification"], "Reçu ou chaîne d’empreintes divergents")
    confirm(receipt["authority"] == receipt["cartographer_mutation"] == "DENY" and receipt["construction"] == "NOT_RUN"
            and receipt["inspected_lots_by_tool"] == receipt["cartographer_candidate_count"] == 0,
            "Frontière d’autorité divergente")
    rows = {row["check_id"]: row for row in packet["records"]}
    confirm(len(rows) == len(packet["records"]) == len(submission["details"]), "Mesures ou détails dupliqués")
    confirm(set(matrix["carriers"]) == {c["carrier"] for c in receipt["carriers"]}, "Porteurs divergents")
    measured = set()
    for carrier in receipt["carriers"]:
        name = carrier["carrier"]
        confirm(carrier["parent"] == matrix["carriers"][name] and carrier["operation"] == matrix["operation"]
                and carrier["occurrence"] == matrix["occurrence"] and carrier["decision"] == "DENY",
                "Opération ou occurrence divergente")
        confirm(len(carrier["requirements"]) == len(matrix["requirements"]), "Nombre d’exigences divergent")
        for requirement, rule in zip(carrier["requirements"], matrix["requirements"]):
            confirm(requirement["id"] == rule["id"] and requirement["source"] == rule["source"]
                    and len(requirement["checks"]) == len(rule["checks"]), "Matrice des exigences divergente")
            statuses = []
            for observation, check in zip(requirement["checks"], rule["checks"]):
                confirm(observation["check_id"] == check["id"], "Relevé associé au mauvais contrôle")
                record = rows.get(check["id"]) if name == submission["carrier"] else None
                if record is None:
                    expected = "MISSING"
                else:
                    expected = "PASS"
                    expected_class = ("EXAMPLE_NOT_AUTHORITY" if submission["classification"] == "EXAMPLE_NOT_AUTHORITY"
                                      else "PHYSICAL_MEASURED")
                    confirm(record["record_id"] == observation["record_id"] and record["issue"] == rule["id"]
                            and record["evidence_class"] == expected_class, "Identité de relevé divergente")
                    detail = submission["details"][record["record_id"]]
                    check_record(root, record, detail, policy, check, observation, carrier["parent"], submission)
                    measured.add(check["id"])
                confirm(observation["status"] == expected, "État de relevé divergent")
                statuses.append(expected)
            expected = {"AUTHORIZED_REVIEW": "PENDING_AUTHORIZED_REVIEW", "PRODUCTION_TRUST": "NOT_RUN"}.get(
                rule["id"], "MISSING" if "MISSING" in statuses else "PASS")
            confirm(requirement["status"] == expected and requirement["blocking"] == (expected != "PASS"),
                    "Complétude ou blocage divergent")
    confirm(measured == set(rows), "Des relevés manquent dans le reçu")
    return {"schema": "v3.a7.independent_receipt_check/1", "status": "PASS",
            "receipt_sha256": sha(receipt_bytes), "checked_measurements": len(measured), "authority": "DENY"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("matrix", "raw-root", "receipt", "policy"):
        parser.add_argument("--" + argument, type=Path, required=True)
    for argument in ("submission", "current-sha256", "policy-sha256"):
        parser.add_argument("--" + argument, required=True)
    args = parser.parse_args()
    print(json.dumps(recheck(args.matrix, args.raw_root.resolve(strict=True), args.submission,
                            args.receipt, args.current_sha256, args.policy, args.policy_sha256)))
