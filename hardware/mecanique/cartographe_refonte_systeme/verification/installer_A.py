"""Installe la variante A contrôlée dans la copie neuve du reçu d'expérience."""
import os
import sys
import traceback

from adapter_implantation import (
    App, BUILD, COPY, ENTRY, HERE, P71, ROUTES, Scene, V, boot, bounds,
    check_isolation, load, modify_p71, no_interference, rebuild_route,
    require, sha, verify_sources, write,
)


def check_board(proof):
    for key, reports in proof["results"].items():
        candidate = reports["candidate"]["pairs"]
        require(all("error" not in r and r["volume_mm3"] <= 1e-4 for r in candidate),
                "Intersection ou inconnue de la porteuse " + key)


def install():
    scene = Scene(COPY)
    receipt = load(COPY / "experiment.json")
    require(COPY.resolve() == type(COPY)(receipt["copy_root"]).resolve(), "Copie inattendue")
    require(verify_sources(receipt)["sources_unchanged"], "Baseline altérée")
    require(all(sha(COPY / name) == digest for name, digest in receipt["inputs_sha256"].items()),
            "Repartir d'une copie neuve avant installation")
    plan_path = HERE / "selection_A.json"
    plan = load(plan_path)
    trials_path = HERE / "essais_implantation.json"
    board_path = HERE / "controle_porteuse_A.json"
    trials, board = load(trials_path), load(board_path)
    require(trials["complete"] and board["complete"], "Contrôles non finalisés")
    require(trials["initial_cao_sha256"] == board["source_sha256"] == scene.hashes(),
            "Entrées d'essai différentes")
    require(trials["spec_sha256"] == sha(HERE / "implantation.json")
            and trials["adapter_sha256"] == sha(HERE / "adapter_implantation.py")
            and board["script_sha256"] == sha(HERE / "controle_porteuse_A.py"), "Recette divergente")
    check_board(board)
    require(no_interference(board["f25_f31"]), "Intersection ou inconnu F25 et F31")
    x, y = plan["security_shift_xy_mm"]
    study = next(r for r in trials["security"] if (r["x_mm"], r["y_mm"]) == (x, y))
    require(all(no_interference(study[key]) for key in ("support", "switch", "access")), "Placement USL refusé")
    selected = {"F25": study["routes"][plan["security_path_index"]],
                "F31": trials["routing"][plan["f31_path_index"]]}
    for key, route in selected.items():
        require(route["points_mm"] == board["results"][key]["candidate"]["points_mm"], "Port différent " + key)
        pairs = route["pairs"]
        require(pairs and not pairs["collisions"]
                and {row["name"] for row in pairs["unknowns"]} <= {"Holybro6XOrin"}, "Trajet refusé " + key)
    environment = boot()
    reg = load(COPY / BUILD)
    route_doc = load(COPY / ROUTES)
    routes = {r["id"]: r for r in route_doc["routes"]}
    old_lengths = {key: routes[key]["longueur_courbe_mm"] for key in selected}
    ref = next(r for r in reg["references"] if r["fichier"] == P71)
    doc = App.openDocument(str(COPY / P71))
    check_isolation()
    support = modify_p71(doc, x, y)
    require(abs(support.Volume - study["support_volume_mm3"]) < 1e-5, "Support différent de l'essai")
    doc.save()
    ref.update(sha256=sha(COPY / P71), bbox_mm=bounds(support))
    App.closeDocument(doc.Name)

    rebuilt = {key: rebuild_route(routes[key], row["points_mm"], reg["references"]) for key, row in selected.items()}
    for key, geometry in rebuilt.items():
        require(abs(geometry["longueur_courbe_mm"] - selected[key]["geometry"]["longueur_courbe_mm"]) < 1e-5,
                "Génération différente de l'essai " + key)
    entry = App.openDocument(str(COPY / ENTRY))
    check_isolation()
    occurrence = next(r for r in reg["occurrences"] if r["occurrence"] == "BoutonBuzzerLED")
    parent = next(doc for doc in App.listDocuments().values()
                  if type(COPY)(doc.FileName).resolve() == COPY / occurrence["parent"])
    switch = parent.getObject(occurrence["occurrence"])
    pose = switch.Placement
    pose.Base += V(x, y, 0)
    switch.Placement = pose
    occurrence["matrice"] = list(pose.toMatrix().A)
    parent.recompute()
    require(not any(set(obj.State) & {"Error", "Invalid"} for obj in parent.Objects), "Sous-assemblage en erreur")
    parent.save()
    entry.Label = "Cartographe — variante système A — À valider"
    entry.recompute()
    require(not any(set(obj.State) & {"Error", "Invalid"} for obj in entry.Objects), "Assemblage en erreur")
    entry.save()

    reg["integration_systeme"] = {"variante":"A", "statut":"À valider", "date":"2026-11-10",
                                  "controle":"../../verification/validation_A.json",
                                  "reprise":["BoutonBuzzerLED", "SupportSecurite", "F25", "F31"]}
    route_doc["nature"] = "Variante A isolée. F25 et F31 reconstruits. F40/F41 hérités comme réservations."
    write(COPY / BUILD, reg)
    write(COPY / ROUTES, route_doc)
    modules_path = COPY / "verification/modules_electriques.json"
    modules = load(modules_path)
    module = next(row for row in modules["modules"] if row["id"] == "AVIONIQUE")
    module["zone"] = "USL déporté vers le sud-est. Montée CAN1 depuis le PM08, traversée au sud."
    module["open"] += ["Maintien intermédiaire et séparation F24B/F24C, prise GPS1 et accès réel USL."]
    modules["configuration"] = "cartographe_refonte_systeme_A"
    modules["routes_courantes"] = "routes_prototype.json"
    modules["statut_routes_heritage"] = "Les champs baseline conservent la référence du calcul antérieur."
    write(modules_path, modules)
    manifest = load(COPY / "manifest.json")
    manifest.update(configuration="cartographe_refonte_systeme_A", promotion=False, qualification="À valider",
                    date_mise_a_jour="2026-11-10", references=reg["references"], occurrences=reg["occurrences"],
                    controle="../verification/validation_A.json",
                    definition_retenues="../../cartographe_faisceaux_modulaires/verification/integration.json",
                    integration_radio="../../cartographe_faisceaux_modulaires/verification/integration_radio.json",
                    validation_radio="../../cartographe_faisceaux_modulaires/verification/validation_radio.json")
    write(COPY / "manifest.json", manifest)
    write(HERE / "installation_A.json", {"complete":True, "environment":environment,
          "old_lengths_mm":old_lengths, "regenerated":rebuilt, "sha256_selection":sha(plan_path),
          "sha256_trials":sha(trials_path), "sha256_board_test":sha(board_path), "sha256_installer":sha(__file__),
          "reference_unchanged":verify_sources(receipt)["sources_unchanged"], "final_sha256":Scene(COPY).hashes()})


if __name__ == "__main__":
    try:
        install()
        code = 0
    except Exception:
        traceback.print_exc()
        code = 2
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
