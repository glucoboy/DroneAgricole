"""Compare les géométries A et modulaire dans le même volume de baie."""
from collections import Counter
import math
from pathlib import Path

from adapter_implantation import (
    COPY, HERE, Scene, bounds, load, require, sha,
    verify_sources, write,
)



def combined_box(shapes):
    boxes = [bounds(shape) for shape in shapes]
    return [fun(box[i] for box in boxes) for i, fun in enumerate([min, min, min, max, max, max])]


def clipped_segment(a, b, lower, upper):
    first, last = 0.0, 1.0
    for start, finish, low, high in zip(a, b, lower, upper):
        direction = finish - start
        if abs(direction) < 1e-12:
            if not low <= start <= high:
                return 0.0
            continue
        left, right = sorted(((low - start) / direction, (high - start) / direction))
        first, last = max(first, left), min(last, right)
        if last <= first:
            return 0.0
    return (b - a).Length * (last - first)


def clipped_axis(wire, lower, upper):
    length = 0.0
    for edge in wire.Edges:
        count = 2 if edge.Curve.TypeId == "Part::GeomLine" else 96
        start, stop = edge.ParameterRange
        points = [edge.valueAt(start + (stop-start)*i/(count-1)) for i in range(count)]
        length += sum(clipped_segment(a, b, lower, upper) for a, b in zip(points, points[1:]))
    return length


def metrics(scene, lower, upper, previous=None, changed=None):
    axes = dict(previous["axes_by_route_mm"]) if previous else {}
    inside = dict(previous["axes_inside_by_route_mm"]) if previous else {}
    for key in (changed or scene.wires):
        wire = scene.wires[key]
        axes[key] = wire.Length
        inside[key] = clipped_axis(wire, lower, upper)
    support = next(r.shape for r in scene.items.values() if r.name == "SupportSecurite")
    cable_bounds = combined_box([item.shape for item in scene.cables.values()])
    return {"routes":len(axes), "axis_sum_mm":sum(axes.values()), "axis_in_bay_mm":sum(inside.values()),
            "axes_inside_bay":sum(length > 1e-6 for length in inside.values()),
            "cable_envelope_bbox_mm":cable_bounds,
            "volume_proxy_in_bay_cm3":sum(math.pi * scene.routes[key]["diametre_mm"]**2 * length / 4000
                                          for key, length in inside.items()),
            "f25_mm":axes["F25"], "f31_mm":axes["F31"], "f40_mm":axes["F40"], "f41_mm":axes["F41"],
            "p71_volume_cm3":support.Volume / 1000,
            "p71_brep_centroid_mm":list(support.Solids[0].CenterOfMass), "axes_by_route_mm":axes,
            "axes_inside_by_route_mm":inside, "occurrences":len(scene.items)}


def main():
    receipt = load(COPY / "experiment.json")
    source = Path(receipt["source_root"])
    initial, final = Scene(source), Scene(COPY)
    print("Scenes chargées", flush=True)
    source_integrity = verify_sources(receipt)
    require(source_integrity["sources_unchanged"], "Source de copie altérée")
    installed = load(HERE / "installation_A.json")
    require(installed["complete"] and installed["final_sha256"] == final.hashes(),
            "Installation et natifs divergents")
    matrix = load(HERE / "matrice_interconnexion.json")
    ids = [row["id"] for row in matrix["routes"]]
    modules = load(COPY / "verification/modules_electriques.json")
    membership = Counter(key for row in modules["modules"] for key in row["route_ids"])
    require(set(ids) == set(initial.routes) == set(final.routes) == set(membership)
            and len(set(ids)) == len(ids) == 53 and set(membership.values()) == {1},
            "Axes de la matrice, du registre, de la CAO ou des modules divergents")
    require(all(row["bom_ids"] == final.routes[row["id"]]["bom_ids"] for row in matrix["routes"]),
            "Postes BOM des routes divergents")
    lower, upper = (-94, -88, 85), (94, 88, 165)
    before = metrics(initial, lower, upper)
    print("Référence mesurée", flush=True)
    changed = [k for k, row in final.routes.items() if row["points_mm"] != initial.routes[k]["points_mm"]]
    require(set(changed) == {"F25","F31"}, "Périmètre de géométrie différent")
    require(all(final.routes[k]["points_mm"][-1] == initial.routes[k]["points_mm"][-1] for k in changed),
            "Extrémité porteuse déplacée")
    original_sha, final_sha = initial.hashes(), final.hashes()
    files = {k for k, digest in final_sha.items() if original_sha.get(k) != digest}
    for key in set(final.routes) - set(changed):
        path = final.routes[key]["fichier"]
        require(original_sha[path] == final_sha[path]
                and list(initial.cables[key].pose.toMatrix().A) == list(final.cables[key].pose.toMatrix().A),
                "Recalcul requis pour " + key)
    after = metrics(final, lower, upper, before, changed)
    print("Variante mesurée", flush=True)
    data = {
        "complete":True, "before":before, "after":after, "changed_routes":changed,
        "changed_paths":sorted(files), "source_integrity":source_integrity,
        "source_cao_sha256":original_sha, "variant_cao_sha256":final_sha,
        "matrix_sha256":sha(HERE / "matrice_interconnexion.json"),
        "method":{"bay_mm":[-94,-88,85,94,88,165],
                  "length":"Longueur polygonale dans la baie. Deux points pour les droites, 96 points par arête courbe, puis troncature des segments par la boîte. Aucune borne d'erreur globale.",
                  "volume":"Aire circulaire par diamètre de réservation × longueur d'axe dans la baie. Somme des approximations, sans union ni masse.",
                  "supports":"Volume de matière BRep de P71, sans quincaillerie."},
        "delta":{key:after[key] - before[key] for key in ("axis_sum_mm","axis_in_bay_mm",
                  "volume_proxy_in_bay_cm3","p71_volume_cm3","f25_mm","f31_mm","f41_mm")},
        "unchanged_architecture":{"functional_matrix_rows":len(matrix["connections"]), "assembly_modules":len(modules["modules"]),
                                  "added_boards":0, "intended_added_matings":0,"added_electronic_power_w":0},
        "unknowns":{"harness_mass_g":None,"support_mass_g":None,"conductor_length_mm":None,"physical_matings":None,
                    "physical_harnesses":None,"measured_cg_mm":None,"thermal_margin_deg_c":None,"delta_loss_w":None},
        "cg":"Δr_G = [m_USL(30,−20,0) + Δmoment(P71, câbles et retenues) − r_G0·Δm]/(M0+Δm), avec toutes masses dans la même unité. Poses et volumes nominaux disponibles, masse nette USL et câbles ouverts.",
        "expected_power_loss":"Pour F31 avec 3 fils documentés, 167,714 mm d'axe de moins représentent 503,14 mm de fil pour le seul scénario 3 fils intégralement coextensifs. F25 inconnu. R par conducteur = ρ L/S. I et S réels inconnus."
    }
    write(HERE / "comparaison_systeme.json", data)

    print(data["delta"], flush=True)


if __name__ == "__main__":
    main()




