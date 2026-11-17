"""Contrelecture indépendante des liens, itinéraires et preuves de la copie."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from controles_geometrie import App, ENTRY, Part, Scene, baseline_metadata, read, sha, write


SA = "sous_assemblages/SA07_Prototype_Faisceaux.FCStd"


def vector(point):
    return App.Vector(*point)


def values(prop, kind="LinkList"):
    return {node.get("value") for node in prop.find(kind)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("proof_dir", type=Path)
    args = parser.parse_args()
    folder = args.proof_dir
    installation = json.loads(read(folder / "installation.json"))
    graph = json.loads(read(folder / "graphe_physique.json"))
    inventory = json.loads(read(folder / "inventaire.json"))
    metadata = baseline_metadata()
    metadata.update(json.loads(read(folder / "metadonnees_controle.json")))
    after = Scene(args.copy, metadata)
    before = Scene(args.reference, baseline_metadata())
    issues = []

    def check(condition, reason):
        if not condition:
            issues.append(reason)

    after_hashes = after.hashes()
    check(installation["finalized"], "Installation non finalisée")
    natives = {k: v for k, v in after_hashes.items() if k.endswith(".FCStd")}
    check(natives == installation["modeles_natifs_sha256"], "Fermeture ou empreinte native différente")
    check(sha(folder / "graphe_physique.json") == installation["graphe_sha256"], "Graphe différent de l’installation")
    check(sha(folder / "metadonnees_controle.json") == installation["metadata_sha256"], "Métadonnées différentes de l’installation")
    check(set(before.routes) == set(after.routes), "IDs de parcours modifiés")
    check(all(before.routes[cid]["points_mm"][0] == after.routes[cid]["points_mm"][0]
              and before.routes[cid]["points_mm"][-1] == after.routes[cid]["points_mm"][-1]
              and before.routes[cid]["bom_ids"] == after.routes[cid]["bom_ids"]
              and before.routes[cid].get("terminaisons") == after.routes[cid].get("terminaisons")
              for cid in set(before.routes) & set(after.routes)), "Interface déclarée ou BOM modifiée")

    groups = {group["id"]: set(group["routes"]) for group in graph["groupes"]}
    members = Counter(cid for group in graph["groupes"] for cid in group["routes"])
    check(set(members) == set(after.routes) and all(n == 1 for n in members.values()), "Partition physique incomplète")
    check(len(groups) == len(graph["groupes"]), "Identifiant de groupe physique dupliqué")
    _, objects = after.reader.xml(SA)
    for name, wanted in groups.items():
        native = objects.get("Groupe_" + name, {})
        observed = values(native["Group"]) & set(after.routes) if "Group" in native else set()
        check(observed == wanted, "Composition native divergente pour " + name)

    graph_ids = [row["id"] for row in graph["routes"]]
    check(len(set(graph_ids)) == len(graph_ids) and set(graph_ids) == set(after.routes), "Identités des itinéraires divergentes")
    sleeve_rows = {row["occurrence"]: row for row in graph["gaines"]}
    cover = {name: set() for name in sleeve_rows}
    for route in graph["routes"]:
        name = route["id"]
        wire = after.wires[name].Wires[0]
        rows = route["segments"]
        check(all(math.isfinite(row["longueur_mm"]) and row["longueur_mm"] > 0 for row in rows),
              "Longueur non positive " + name)
        check(abs(sum(row["longueur_mm"] for row in rows) - wire.Length) < 1e-5, "Longueur non conservée " + name)
        check(name in groups[route["groupe"]], "Groupe divergent " + name)
        check((rows[0]["point_depart_mm"], rows[-1]["point_arrivee_mm"]) ==
              (after.routes[name]["points_mm"][0], after.routes[name]["points_mm"][-1]),
              "Extrémités d’itinéraire non conservées " + name)
        for a, b in zip(rows, rows[1:]):
            check(a["destination"] == b["origine"] and (vector(a["point_arrivee_mm"]) -
                   vector(b["point_depart_mm"])).Length <= 1e-5, "Dérivation discontinue " + name)
        for row in rows:
            for key in ("point_depart_mm", "point_arrivee_mm"):
                dist = wire.distToShape(Part.Vertex(vector(row[key])))[0]
                check(math.isfinite(dist) and dist <= 1e-5, "Point d’itinéraire hors axe " + name)
            if row["nature"] == "gaine_commune":
                sleeve = sleeve_rows[row["id"]]
                cover[row["id"]].add(name)
                check(abs(row["longueur_mm"] - sleeve["longueur_mm"]) <= 1e-5, "Longueur de gaine divergente " + name)
    for name, sleeve in sleeve_rows.items():
        check(name in objects and "CablesContenus" in objects[name], "Gaine non liée " + name)
        if name in objects and "CablesContenus" in objects[name]:
            check(values(objects[name]["CablesContenus"]) == cover[name] == set(sleeve["membres"]),
                  "Membres de gaine divergents " + name)

    ids = [item["id"] for item in inventory["connections"]]
    check(len(set(ids)) == len(ids), "Identifiant électrique dupliqué")
    mapped = {cid for row in inventory["connections"] for cid in row.get("route_ids", [])}
    check(set(after.routes) <= mapped, "Route native absente de la nomenclature")
    check(mapped <= set(after.routes), "Parcours d’inventaire absent de la copie")
    check(all(row.get("integration") and (row["integration"] != "non_resolue" or row.get("reason"))
              for row in inventory["connections"]), "Statut ou justification absente")

    report = {"schema": "cartographe.revue-independante-faisceaux.v1", "entry": ENTRY,
              "status": "fail" if issues else "pass", "issues": issues,
              "counts": {"routes": len(after.routes), "groupes": len(groups), "gaines": len(sleeve_rows),
                         "connections": len(ids), "native_documents": len(natives)},
              "inputs_sha256": {name: sha(folder / name) for name in
                                ("installation.json", "graphe_physique.json", "inventaire.json", "metadonnees_controle.json")},
              "limits": ["Couverture et intégrité numérique, sans qualification physique.",
                         "Les longueurs des itinéraires sont des longueurs d’axe. Les prises et réserves utiles restent distinctes.",
                         "La gaine conditionnelle ne qualifie pas la CEM, le thermique ou le démontage.",
                         "Les collisions, contacts et positions mobiles ont des preuves de portée distincte."]}
    write(folder / "controles_revue.json", report)
    print(report["status"], report["counts"], issues, flush=True)
    if issues:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
