"""Nomenclature physique dérivée et essais GO4 de la copie consolidée GO3B."""
from collections import Counter
import csv
import json
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / "docs/verification/v21_go3b"
CAD = ROOT / ".runtime/v21-go3b/consolidee/cad"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n",encoding="utf-8")


rows = read(CAD / "verification/construction_prototype.json")["occurrences"]
data = []
for row in rows:
    data.append({"parent":row["parent"],"occurrence":row["occurrence"],"source":row["source"],
                 "object":row["objet_source"],"bom_ids":row.get("bom_ids",[]),
                 "kind":"sous_assemblage" if "sous_assemblages/" in row["source"] else "reference_physique",
                 "quantity_in_parent":1, "mass_g":None,
                 "mass_authority":"hardware/mecanique/cartographe/nomenclature_prototype.json",
                 "mass_status":"INCONCLUSIVE", "matrix_4x4":row["matrice"]})
write("physical_bom.json", {"schema":"drone_agricole.go3b.physical-bom.v1", "candidate":"consolidee",
      "status":"INCONCLUSIVE", "source_registry":".runtime/v21-go3b/consolidee/cad/verification/construction_prototype.json",
      "count_semantics":"Occurrences App::Link directes du registre. Les lignes de sous-assemblage regroupent leurs références filles.",
      "registered_occurrences":len(data), "kinds":dict(Counter(row["kind"] for row in data)),
      "total_mass_g":None, "center_of_gravity_mm":None, "records":data})
with (OUT / "physical_bom.csv").open("w",newline="",encoding="utf-8-sig") as f:
    fields=["parent","occurrence","source","object","bom_ids","kind","quantity_in_parent","mass_g","mass_status"]
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
    writer.writeheader()
    for row in data:
        writer.writerow(row | {"bom_ids":"|".join(row["bom_ids"])})

steps = [
 ("S01","Identifier références, lots, masses, contacts et protections puis consigner le système hors tension.",["G3A-01","G3A-02"],"INCONCLUSIVE"),
 ("S02","Monter et inspecter structure et énergie de référence, avant les branches supérieures.",["G3A-02","G3A-06"],"NOT_RUN"),
 ("S03","Présenter P85 au chant P66, contrôler chaque appui, vis et protection avant de maintenir F25.",["G3A-06"],"INCONCLUSIVE"),
 ("S04","Présenter F35 au sud et F12 vers TELEM1, vérifier verrou, détrompage et rayon sur le cordon monté.",["G3A-01","G3A-02"],"INCONCLUSIVE"),
 ("S05","Résoudre F40/F41 et les sept intersections B.2 avant fermeture de la distribution et des plateaux.",["G3A-05","G3A-07"],"FAIL"),
 ("S06","Contrôler CAN1, GPIO/CSI, l’accès SSD, le ventilateur et les prises caméra sur toute la plage de mouvement.",["G3A-02","G3A-03","G3A-04","G3A-07"],"NOT_RUN"),
 ("S07","Mesurer continuité, retours et isolement hors tension selon la matrice des 71 lignes.",["G3A-01","G3A-02","G3A-05"],"NOT_RUN"),
 ("S08","Exécuter les gestes de maintenance TTL/USB/CAN1 et la dépose caméra sur banc instrumenté après correction CAO.",["G3A-04","G3A-05","G3A-06"],"NOT_RUN"),
]
write("assembly_sequence.json", {"schema":"drone_agricole.go3b.assembly-sequence.v1","status":"INCONCLUSIVE",
      "scope":"Proposition de séquence de revue de la copie consolidée, montage physique non exécuté.",
      "steps":[{"id":id_,"action":action,"requirements":req,"readiness":status,"physical_execution":"NOT_RUN"}
               for id_,action,req,status in steps]})
electrical=read(OUT/"electrical_go4.json")
tests=[
 ("GO4-MEC-CONNECT","Accouplement, retrait, verrouillage, outillage et séquence sur exemplaires identifiés",["G3A-02","G3A-05","G3A-06"],"Plans et contacts applicables, corrections des collisions et protocole hors tension"),
 ("GO4-MEC-MOTION","Balayage continu translation/rotation caméra, réserve, traction et abrasion F16/M8",["G3A-04","G3A-06"],"Courses, butées et rayons dynamiques constructeur mesurés"),
 ("GO4-MASS","Pesée par occurrence avec accessoires, gaines, retenues, bilan, centrage et inerties",["G3A-08"],"Périmètres massiques et inclusions réconciliés"),
 ("GO4-VIBRATION","Tenue fixations, connectique et fatigue des faisceaux sous vibrations",["G3A-04","G3A-06"],"Montage, niveaux, cycles et critères approuvés"),
 ("GO4-THERMAL","Températures, débit ventilateur et déclassement sous charge",["G3A-02","G3A-07"],"Montage clos, puissance et ambiance définies"),
 ("GO4-EMC","Blindages, retours, CEM et intégrité USB/CAN/GNSS pendant acquisition synchronisée",["G3A-03","G3A-07"],"Protocole et niveaux d’essai approuvés"),
 ("GO4-FLIGHT","Qualification progressive propulsion, énergie, structure et acquisition avant essais en vol",["G3A-08"],"Niveaux précédents satisfaits selon DOC-VAL §2, autorisation et protocole de vol"),
]
write("go4.json",{"schema":"drone_agricole.go3b.go4.v1","status":"NOT_RUN",
      "physical_trials_authorized":False,"electrical_plan":"docs/verification/v21_go3b/electrical_go4.json",
      "tests":electrical["trials"]+[{"id":id_,"method":method,"requirements":req,"prerequisites":prereq,"status":"NOT_RUN",
                                   "acceptance_thresholds":None} for id_,method,req,prereq in tests]})
print(len(data),"occurrences de registre, BOM et séquence écrites")
