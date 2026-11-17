"""Infrastructure CAO : vrais objets Cables Workbench, sans sauvegarde implicite.

Le profil circulaire décrit l'encombrement extérieur, sans attribuer une section
de cuivre fictive à un câble USB/coaxial. L'extension installée reste nécessaire
pour recalculer et éditer les objets après réouverture du document.
"""
from pathlib import Path
import hashlib
import importlib
import math
import sys

import FreeCAD as App


def bootstrap_paths():
    """Charger les chemins stock et utilisateur, puis retourner la provenance.

    Pour un processus Python autonome, initialiser FreeCADGui avant la création
    (showMainWindow puis hide si processus dédié). Ne change aucune fenêtre ici.
    Dans FreeCAD interactif, aucune activation manuelle de l'atelier n'est requise.
    """
    stock = Path(App.getResourceDir()) / "Mod"
    user_mod = Path(App.getUserAppDataDir()) / "Mod"
    candidates = [user_mod / "Cables", stock / "Cables"]
    addon = next((p for p in candidates
                  if (p / "freecad/cables/archCable.py").is_file()), None)
    if addon is None:
        raise RuntimeError("Extension Cables absente du profil FreeCAD actif.")
    for path in [stock / "Draft", stock / "BIM", user_mod, addon]:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    importlib.invalidate_caches()
    from freecad.cables import version
    names = ["archCable.py", "wireFlex.py", "wireutils.py", "version.py"]
    hashes = {name: hashlib.sha256(
        (addon / "freecad/cables" / name).read_bytes()).hexdigest() for name in names}
    return {"nom": "Cables Workbench", "version": version.__version__,
            "dossier": str(addon), "sha256_modules": hashes,
            "freecad": App.Version()}


def _check_polyline(points, diameter, radius):
    if len(points) < 2 or diameter <= 0 or radius <= diameter / 2:
        raise ValueError("Il faut au moins2points, un diamètre positif et un rayon supérieur au rayon du câble.")
    segments = [b - a for a, b in zip(points, points[1:])]
    if any(v.Length < 1e-5 for v in segments):
        raise ValueError("Deux sommets consécutifs sont confondus.")
    tangents = [0.0] * len(points)
    for i in range(1, len(points) - 1):
        a, b = segments[i - 1], segments[i]
        cosine = max(-1.0, min(1.0, a.dot(b) / (a.Length * b.Length)))
        angle = math.acos(cosine)
        if angle > math.pi - 1e-6:
            raise ValueError("Demi-tour instantané dans le parcours.")
        tangents[i] = radius * math.tan(angle / 2)
    for i, segment in enumerate(segments):
        if tangents[i] + tangents[i + 1] > segment.Length - 1e-4:
            raise ValueError(f"Segment{i + 1} trop court pour le rayon{radius:g}mm : "
                             f"{segment.Length:g}mm disponibles, "
                             f"{tangents[i] + tangents[i + 1]:g}mm de tangences.")


def effective_wire(cable):
    """Retourner le parcours courbe effectivement recalculé par l'extension."""
    wires = cable.Base.Shape.Wires
    if len(wires) != 1 or wires[0].isClosed():
        raise ValueError("Le parcours effectif doit être un fil ouvert unique.")
    return wires[0].copy()


def cable_geometry(cable):
    """Données de contrôle obtenues sur la courbe effective, pas la polyligne."""
    wire = effective_wire(cable)
    radii = [float(e.Curve.Radius) for e in wire.Edges if hasattr(e.Curve, "Radius")]
    continuity = all(
        min((va.Point - vb.Point).Length for va in a.Vertexes for vb in b.Vertexes) < 1e-5
        for a, b in zip(wire.Edges, wire.Edges[1:]))
    errors = [o.Name for o in [cable, cable.Base]
              if any(state in ("Invalid", "Error") for state in o.State)]
    return {"cable_proxy": type(cable.Proxy).__module__ + "." + type(cable.Proxy).__name__,
            "route_proxy": type(cable.Base.Proxy).__module__ + "." + type(cable.Base.Proxy).__name__,
            "longueur_courbe_mm": wire.Length, "longueur_addon_mm": cable.Length.Value,
            "diametre_exterieur_mm": cable.ProfilExterieur.DiametreExterieur.Value,
            "rayon_demande_mm": cable.BaseWireFilletRadius.Value,
            "rayons_arcs_mm": radii, "continuite": continuity,
            "parcours_valide": wire.isValid(), "solides": len(cable.Shape.Solids),
            "solide_valide": cable.Shape.isValid(), "volume_mm3": cable.Shape.Volume,
            "erreurs": errors}


def make_native_cable(doc, root, name, points, diameter, bend_radius,
                      color=(0.18, 0.18, 0.20)):
    """Créer ArchCable + WireFlex éditables ; retourner (câble, route).

    points sont des coordonnées dans le repère du document en millimètres.
    Modifier route.Points (coordonnées locales à route.Placement), ou les attaches
    WireFlex, puis cable.BaseWireFilletRadius et doc.recompute(). Modifier le
    diamètre via cable.ProfilExterieur.DiametreExterieur. root peut être None.
    Aucune sauvegarde, export, modification d'une source ou fenêtre n'est réalisé.
    """
    provenance = bootstrap_paths()
    if not App.GuiUp:
        raise RuntimeError("Initialiser FreeCADGui avant make_native_cable : WireFlex crée un ViewProvider natif.")
    import Part
    import Sketcher
    from freecad.cables import wireFlex, archCable
    vectors = [App.Vector(*p) if not isinstance(p, App.Vector) else App.Vector(p)
               for p in points]
    _check_polyline(vectors, float(diameter), float(bend_radius))
    App.setActiveDocument(doc.Name)
    route = wireFlex.make_wireflex_from_vectors(vectors)
    route.Label = name + " — parcours éditable"
    route.PathType = "Wire"
    route.FilletRadius = float(bend_radius)
    profile = doc.addObject("Sketcher::SketchObject", "Profil_" + name)
    profile.Label = name + " — diamètre extérieur"
    profile.addProperty("App::PropertyLength", "DiametreExterieur", "Encombrement")
    profile.DiametreExterieur = float(diameter)
    profile.addGeometry(Part.Circle(App.Vector(), App.Vector(0, 0, 1), diameter / 2), False)
    profile.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    index = profile.addConstraint(Sketcher.Constraint("Diameter", 0, float(diameter)))
    profile.renameConstraint(index, "Diametre")
    profile.setExpression("Constraints.Diametre", "DiametreExterieur")
    doc.recompute()
    cable = archCable.makeCable(baseobj=route, profileobj=profile, name=name)
    cable.addProperty("App::PropertyLink", "ProfilExterieur", "Encombrement")
    cable.ProfilExterieur = profile
    cable.addProperty("App::PropertyString", "ModeleEncombrement", "Encombrement")
    cable.ModeleEncombrement = "Section extérieure circulaire ; structure interne et terminaisons non représentées."
    cable.addProperty("App::PropertyString", "ExtensionVersion", "Provenance")
    cable.ExtensionVersion = provenance["version"]
    cable.StrippedWireLength = 0
    cable.BaseWireFilletRadius = float(bend_radius)
    cable.ShowSubLines = False
    if root is not None:
        root.addObject(cable)
    doc.recompute()
    profile.Visibility = False
    route.Visibility = False
    for child in cable.SubProfiles:
        child.Visibility = False
    material = App.Material()
    material.DiffuseColor = tuple(color)
    cable.ViewObject.ShapeAppearance = [material]
    cable.Visibility = True
    check = cable_geometry(cable)
    if (check["solides"] != 1 or not check["solide_valide"]
            or not check["parcours_valide"] or not check["continuite"] or check["erreurs"]
            or any(abs(r - bend_radius) > 1e-4 for r in check["rayons_arcs_mm"])):
        raise RuntimeError(f"Câble natif{name} invalide : {check}")
    return cable, route
