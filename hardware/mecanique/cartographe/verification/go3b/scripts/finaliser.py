"""Finaliser les reçus et le rapport de la campagne native GO3B."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from preparation import ROOT, RUN, read, write, require
from electromechanical_engine.freecad import guard
from archiver import publish

OUT = ROOT / "docs/verification"
DETAIL = OUT / "v21_go3b"
CASES = ("H03-A", "H03-B", "H02-A", "H02-B", "H01-A-reprise", "H01-B-reprise")
ALL = ("baseline", *CASES, "consolidee")
VERDICT = "GO3B_CAO_NO_GO_MOTIVE"


def artifact(path):
    path = Path(path)
    return {"path":path.relative_to(ROOT).as_posix(),"sha256":guard.sha256(path)}


def numbers(case):
    snapshot = read(RUN / case / "snapshot.json")
    return snapshot["metrics"]


def format_mm(value):
    return f"{value:.3f}".replace(".", ",")


def make_report(candidate, validation, manifest):
    rows = []
    for case in ALL:
        metrics = numbers(case)
        ind = validation["independent_cases"][case]
        counts = ind["counts"]["by_status"]
        rows.append("| " + " | ".join((case, format_mm(metrics["axis_sum_mm"]),
              format_mm(metrics["zones_mm"]["bay"]),format_mm(metrics["zones_mm"]["above"]),
              format_mm(metrics["zones_mm"]["sous_P66_emprise_stricte"]),
              str(counts["FAIL"]), str(counts["NOT_RUN"]))) + " |")
    report = f"""# GO3B V2.1 — reconstruction et contre-validation

**{VERDICT}**, 17 novembre 2026. Les trois familles ont été
construites sur copies du prototype cartographe sans dock. Six variantes
ont été sauvegardées, recalculées et rouvertes. Une copie consolidée de
diagnostic réunit les seules corrections communes. La réception CAO est
refusée à cause de défauts mesurés et de contrôles incomplets.
La maturité du dossier est **Implémenté**, le montage reste **À valider**.

Les décisions actives sont intégrées à DOC-MEC, DOC-ELEC et DOC-VAL.
Ce rapport constitue le livrable de campagne explicitement demandé.
[Décision mécanique](../architecture/ARCHITECTURE_MECANIQUE.md#cartographe-go3b-reconstruction) ·
[Résultat de validation](../VALIDATION_QUALIFICATION.md#cartographe-go3b-reconstruction)

## Référentiel et périmètre

La porte d’exploration a été rejouée sur les trois demandes exactes
H-03, H-02 et H-01 avec le binaire scellé C. Chaque reçu rend
EXPLORATION_ALLOWED / PLANNED et contrôle 180 fichiers.
Le gel est `3fc42609…`, sa racine active `87eec083…`.
Le témoin reprend 137 natifs et quatre auxiliaires du gel.
Le registre de construction existant est ajouté comme cinquième auxiliaire
pour vérifier les occurrences et les poses. Les 142 fichiers sources
sont retrouvés identiques après la campagne.

L’environnement exécuté est Windows amd64, FreeCAD 1.1.3, OCCT 7.8.1,
Python FreeCAD 3.11 et Cables 0.3.7. Le repli Python a passé le probe
Part et les 19 tests natifs Cables. Les commandes, versions et SHA-256
sont dans le manifeste. Les contrôles portent sur les fichiers sauvegardés
et les critères gelés. [Manifeste](../verification/v21_go3b_manifest.json)

La couverture documentaire conserve 71 lignes, 142 côtés, 53 axes,
56 associations et 21 exceptions motivées. L2 et la netlist CA01 ont
été rejoués indépendamment. Les 43 broches documentaires, 15 références,
six feuilles et quatre options DNP sont conservées. L2 détecte GPS2
sur le témoin et confirme la réservation TELEM1 des copies corrigées.
Les contacts montés et la continuité physique restent inconnus.
[Preuve électrique](../verification/v21_go3b/electrical_evidence.json)

## Construction et budget

Le plafond de 12 expériences est conservé. Huit tentatives de variantes
ont réellement été lancées, avec six sauvegardes complètes et deux
échecs de génération H01-A/B sur sommets successifs confondus.
Les deux reprises natives sont conservées avec leurs échecs d’origine.
La consolidation ajoute une expérience, soit **9/12 crédits consommés**.
Le témoin et les mesures en mémoire sont exclus de ce compte.
Le budget d’achat consommé est 0 €.

Deux configurations ont été évaluées dans chacune des trois familles.
L’arrêt intervient après les rejets des deux configurations et la
contre-validation de la consolidée. Les trois crédits restants sont
inutilisés. L’instruction GO3B de conserver les variantes rejetées conduit
à archiver les six états paramétriques, en plus des échecs de génération.
[Variantes et décisions](../verification/v21_go3b_candidates.json)

| Famille | Réalisation native et limite |
|---|---|
| H-03 | Isolateur déplacé au chant ouest, orientations 180° et 270°, branches F40/F41 régénérées avec faces et gestes transformés ensemble. Les appuis restent des réservations ASSUMED. |
| H-02 | Isolateur fixe, corridors F41 dessous ou latéral, F40 reconnecté à la réservation TTL, témoin F16 natif repris. Les corps coudés et la ferrite sont des enveloppes ASSUMED. Le parcours M8 de référence est conservé et sondé. |
| H-01 | Isolateur fixe, F40/F41 régénérés avec deux réservations passives distantes et témoin F16. Le modèle réserve les raccords, leur pin à pin et leur montage restent incomplets. |
| Consolidée | F12 vers TELEM1, F35 au sud, F25 et P85 au chant P66. Les choix incompatibles des trois familles rejetées sont écartés. L’isolateur et les branches historiques de diagnostic restent à reprendre. |

Les deux extrémités incidentes à l’isolateur suivent la mutation H-03.
Les extrémités opposées BMS/hôte restent à leur repère de référence.
Les six variantes ont une concordance géométrique aux réservations TTL/USB.
Sur la consolidée, les axes historiques restent à **98,871 mm du TTL**
et **53,639 mm de l’USB-B**. Ce sont des écarts aux faces du modèle,
avec contacts réels encore inconnus.
[Revue indépendante des interfaces](../verification/v21_go3b/interfaces_review.json)

## Mesures comparables et rejets

Même inventaire des 53 axes, même repère XYZ et mêmes zones gelées.
Les longueurs par zone sont calculées par clipping à 96 et 384 points
par courbe. Le tableau emploie 96 points pour reproduire la référence.
La somme des axes ne constitue pas une liste de coupes de cordons.

| Copie | Axes cumulés mm | Baie mm | Au-dessus mm | Sous P66 stricte mm | Paires FAIL observées | Paires NOT_RUN |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Les couvertures des variantes diffèrent. Les défauts dénombrés sont
des bornes inférieures. Chaque variante conserve les sept défauts B.2.
H03-A ajoute F40/P72 à 18,258 mm³. H03-B ajoute F40/P72 à 24,317 mm³
et isolateur/P72 à 146,756 mm³. Les supports H03 recoupent P72 à
109,734 mm³ sous l’hypothèse d’appui et laissent un jeu de 0,300 mm
avec le module. Les H02 recoupent F40/P72 à 42,676 mm³.
H02-A ajoute F41/P72 à 41,433 mm³. Les H01 recoupent notamment
F40/P73 à 618,710 ou 78,781 mm³.
[Mesures et périmètres](../verification/v21_go3b/independent_evidence.json)

La consolidée mesure 12 143,722 mm d’axes contre 12 125,900 mm au témoin,
soit +17,822 mm. La baie passe de 4 341,486 à 4 257,184 mm et le dessus
de 2 421,421 à 2 318,252 mm. Sous P66 stricte et en hauteur de gaine,
les valeurs restent 451,202 et 173,278 mm.
Le volume occupé par union avec les fiches exactes, la masse complète,
le centrage et le nombre d’opérations de maintenance sont inconnus.
Le support H03 donnerait 15,595 g avec une densité analogue aluminium
de 2,70 g/cm³, hors ancrages et vis. Ce calcul conditionnel ne renseigne
pas la masse complète.

## Couverture de contre-validation

La consolidée a été sauvegardée puis rouverte dans de nouveaux processus
FreeCAD. La fermeture relocalisée compte 138 natifs, dont P85.
Ses 566 solides relus passent le contrôle de validité et de volume.
Les 53 routes restent INCONCLUSIVE pour les limites constructeur et
les repères de contact manquants. L4 et sa finalisation T0 ont été
exécutés et validés sur H03-A et la consolidée.

Le contrôle indépendant de la consolidée énumère 28 567 paires avec
au moins un câble et écarte 26 941 paires par AABB.
Les 1 629 paires retenues, incluant trois paires supplémentaires
hors câble, donnent **7 FAIL, 1 562 INCONCLUSIVE et 60 NOT_RUN**
pour l’admission. Parmi les mesures nominales réalisées, 1 562 ont
un résultat géométrique favorable et sept échouent.
1 533 résultats antérieurs sont repris seulement après égalité des
BRep, poses, visibilité et critères. Les 36 mesures fraîches comprennent
29 paires sans intersection et les sept défauts confirmés.

Les six recouvrements des branches Airy restent interdits selon le
référentiel gelé. La paire F37_POS/P73 reste en échec à
2,8373 × 10⁻⁸ mm³ avec un seuil gelé nul. Son interprétation à une
tolérance physique reste ouverte. Les couples porteur/F12, F25 et
F35 ont bloqué les calculs et sont explicitement NOT_RUN.
Les autres paires hors budget de calcul gardent le même statut.
[Contrôles et exigences](../verification/v21_go3b_validation.json)

Les 93 enveloppes de service sont mesurées comme hypothèses statiques
dans une preuve distincte. Elles couvrent CAN1, TTL, USB, ferrite,
sorties caméra/M8 et déports selon la famille. Le seuil local de
criblage est 10⁻⁴ mm³. Ces sondes restent INCONCLUSIVE pour la réception.
Les premières variantes ont une section CAN1 transposée en XY,
enregistrée telle que sauvegardée. La consolidée porte la section
4,15 × 6,25 mm. Le balayage continu caméra, les verrous réels et
les gestes de montage ne sont pas exécutés.

## Artefacts et suite

Les copies, échecs, paramètres et reçus sont archivés sous
`hardware/mecanique/cartographe/verification/go3b/artefacts/`.
Les liens XLink restent relatifs et les fichiers livrés sont
byte-identiques aux copies mesurées. Conserver toute l’arborescence.
Les natifs et rendus restent exclus de Git.
[Ouvrir la consolidée](../../hardware/mecanique/cartographe/verification/go3b/artefacts/consolidee/cad/assemblages/Prototype_Cartographe.FCStd)

Les trois planches comparent dessus, dessous, profil, baie transparente
et accès de service. Les enveloppes ASSUMED servent de sondes.
[Vues orthographiques](../../hardware/mecanique/cartographe/verification/go3b/vues/01_dessus_dessous_profil.png) ·
[Baie et service](../../hardware/mecanique/cartographe/verification/go3b/vues/02_service_et_camera.png) ·
[Détails des interfaces supposées](../../hardware/mecanique/cartographe/verification/go3b/vues/03_interfaces_supposees.png) ·
[Index des vues](../../hardware/mecanique/cartographe/verification/go3b/vues/vues.json)

La BOM électrique dérivée compte 142 côtés, 36 cordons et dix
jonctions documentaires. La BOM physique conserve 369 liens directs
en explicitant les sous-assemblages. Les masses, coupes et raccords
inconnus restent ouverts. La séquence de montage est proposée pour
revue et porte l’étape bloquante du diagnostic.
[BOM électrique](../verification/v21_go3b/electrical_bom.csv) ·
[BOM physique](../verification/v21_go3b/physical_bom.csv) ·
[Séquence](../verification/v21_go3b/assembly_sequence.json)

La prochaine expérience discriminante doit réaliser un appui effectivement
ancré de l’isolateur et un trajet F40 indépendant des retenues P72/P73,
puis recontrôler les deux branches avec CAN1, PDB et F25 présents.
Elle doit aussi définir la séparation géométrique des branches Airy
et instruire le défaut F37_POS/P73. L’épreuve de réception sera relancée
sur une copie complète après ces corrections.

Les essais sur exemplaires, continuité, isolement, mouvement, traction,
vibration/fatigue, thermique, CEM et vol sont NOT_RUN. Le plan GO4
porte leurs prérequis et les critères encore à définir.
[Liste GO4](../verification/v21_go3b/go4.json)
"""
    path = ROOT / "docs/electromechanical_v2_1/06_GO3B_REPORT.md"
    path.write_text(report, encoding="utf-8")


def main():
    independent = read(DETAIL / "independent_evidence.json")
    electrical = read(DETAIL / "electrical_evidence.json")
    require(independent["verdict"] == VERDICT, "Verdict indépendant divergent.")
    service = {}
    for case in (*CASES,"consolidee"):
        path = RUN / case / "service.json"
        result = read(path)
        require(result.get("status") == "COMPLETE", f"Service non finalisé : {case}")
        service[case] = result
    service_result = {"schema":"drone_agricole.go3b.service.v1","status":"INCONCLUSIVE","date":"2026-11-17",
        "threshold_mm3":1e-4,"not_acceptance_criteria":True,
        "native_orientation_limitation":"Sections CAN1 XY transposées sur les six variantes, section 4,15×6,25 mm sur la consolidée.",
        "samples":sum(len(row["envelopes"]) for row in service.values()),
        "scenario_counts":dict(Counter(row["scenario_result"] for case in service.values() for row in case["envelopes"].values())),
        "cases":service,"physical_extraction":"NOT_RUN","moving_envelope":"NOT_RUN"}
    write(DETAIL / "service_evidence.json", service_result)
    archive = publish()
    preflight = read(RUN / "preflight.json")
    control = {"schema":"drone_agricole.go3b.validation.v1","date":"2026-11-17",
        "verdict":VERDICT,"test_id":"T-CARTO-V21-GO3B","scope":"Prototype cartographe sans dock sur Windows amd64",
        "reference_sha256":preflight["lock"]["reference_sha256"],"maturity":"Implémenté",
        "coverage":{"documentary":electrical["coverage"],"independent":independent["cases"]["consolidee"]["counts"],
                    "native_pair_measurement_counts":independent["cases"]["consolidee"]["native_pair_measurement_counts"],
                    "service_samples":service_result["samples"]},
        "controls":[
         {"id":"T-GO3B-REF","status":"PASS","requirements":["G3A-08"],"result":"Gel, fermeture et 142 fichiers sources identiques."},
         {"id":"T-GO3B-NATIVE","status":"PASS","requirements":["G3A-08"],"result":"Six variantes et une copie consolidée sauvegardées et rouvertes, sans lien rompu ni objet en erreur."},
         {"id":"T-GO3B-GRAPH","status":"INCONCLUSIVE","requirements":["G3A-01","G3A-02","G3A-03","G3A-05","G3A-07"],"result":"Jointure documentaire PASS. Contacts montés et continuité physique ouverts."},
         {"id":"T-GO3B-B2","status":"FAIL","requirements":["G3A-07","G3A-08"],"result":"Sept défauts hérités confirmés sur toutes les copies. Paires manquantes explicites."},
         {"id":"T-GO3B-SERVICE","status":"INCONCLUSIVE","requirements":["G3A-02","G3A-04","G3A-05","G3A-06"],"result":"93 sondes ASSUMED mesurées. Domaine mobile continu et gestes réels ouverts."},
         {"id":"T-GO3B-CONSOLIDATED-DIAGNOSTIC","status":"FAIL","requirements":["G3A-05"],"result":"Axes historiques à 98,871 et 53,639 mm des réservations TTL/USB. Accouplement non réalisé."},
         {"id":"T-GO3B-METRICS","status":"PASS","requirements":["G3A-08"],"result":"Même inventaire de 53 axes et mêmes sept boîtes de zones, mesures 96/384."},
         {"id":"T-GO3B-MASS","status":"INCONCLUSIVE","requirements":["G3A-08"],"result":"BOM dérivée disponible, masse totale/CG/inerties inconnus."},
         {"id":"T-GO3B-OCCUPANCY","status":"NOT_RUN","requirements":["G3A-06","G3A-07"],"result":"Union de volumes connectés exacts indisponible, terminaisons et matériel incomplets."},
         {"id":"T-GO3B-PHYSICAL","status":"NOT_RUN","requirements":[f"G3A-0{i}" for i in range(1,9)],"result":"Essais GO4 non exécutés, protocole et matériel requis."}],
        "requirements":{f"G3A-0{i}":{"status":"FAIL" if i in (5,7,8) else "INCONCLUSIVE",
            "refs":["CAB-CARTO-001","MEC-INT-001","METH-001"]} for i in range(1,9)},
        "independent_cases":independent["cases"],
        "evidence":{name:artifact(DETAIL/name) for name in ("electrical_evidence.json","independent_evidence.json","interfaces_review.json",
                 "service_evidence.json","electrical_bom.json","physical_bom.json","assembly_sequence.json","go4.json","interfaces_visuals.json","interfaces_go4.json")},
        "not_run":independent["not_run"]+["Validation interactive FreeCAD", "Union exacte des volumes connectés", "Masse, centrage et inerties complets"],
        "limits":["Les résultats de paire à volume nul restent INCONCLUSIVE pour l’admission nominale.",
                  "Des solides et contacts restent des enveloppes candidates. Les 60 paires NOT_RUN de la consolidée restent dans le dénominateur.",
                  "H01 réserve des raccords passifs, et H02 sonde les profils de fiches. Les interfaces matérielles de ces réservations restent à définir."]}
    control["control_status_counts"] = dict(Counter(row["status"] for row in control["controls"]))
    write(OUT / "v21_go3b_validation.json", control)
    candidates=[]
    for case in (*CASES,"consolidee","H01-A","H01-B"):
        built = read(RUN/case/"construction.json")
        row={"id":case,"state":built["phase"],"counted_experience":True,
             "verdict":VERDICT,"archive":archive[case]["entrypoint"],
             "construction_sha256":guard.sha256(RUN/case/"construction.json"),
             "parameter_case":built.get("parameter_case"),"mutations":built.get("affected",[]),
             "connected_volume_mm3":None,"harness_mass_g":None,"installed_delta_mass_g":None,
             "center_of_gravity_mm":None,"physical_service_operations":None}
        if built["phase"]=="SAVED":
            metrics = numbers(case)
            row.update(metrics=metrics,reopen=artifact(RUN/case/"reopen.json"),
                       independent_counts=independent["cases"][case]["counts"],
                       decision="REJETEE" if case!="consolidee" else "CONSOLIDATION_DE_DIAGNOSTIC",
                       reason="Intersections mesurées et couverture ouverte. Aucune admission géométrique.",
                       parameters=built.get("parameters",{}),donors=built["donors"])
        else:
            row.update(decision="ECHEC_DE_GENERATION",reason=built["error"],retry=case+"-reprise")
        candidates.append(row)
    candidate={"schema":"drone_agricole.go3b.candidates.v1","date":"2026-11-17","verdict":VERDICT,
        "reference_sha256":preflight["lock"]["reference_sha256"],
        "budget":{"detailed_limit":12,"variant_attempts_launched":8,"variant_attempts_failed":2,"variants_saved":6,
                  "consolidation_attempts":1,"spent_experiences":9,"remaining":3,"witness_counted":False,
                  "parametric_families":3,"parameter_cases_per_family":2,"spend_eur":0,
                  "stop_reason":"Deux configurations par famille ont été rejetées. Sept défauts hérités restent confirmés après consolidation. Les crédits restants ne sont pas engagés.",
                  "retention_override":"Le mandat GO3B demande de conserver les variantes rejetées, ce qui étend la conservation au-delà d’un seul natif par famille du portefeuille GO3A."},
        "selection":{"admissible":[],"consolidated":"consolidee",
                     "common_mutations":["F12_TELEM1","F35_SUD","F25_P85"],
                     "families_merged":False,
                     "diagnostic_limit":"Consolidation des corrections communes avec branches F40/F41 historiques toujours en défaut."},
        "candidates":candidates,"baseline":numbers("baseline")}
    write(OUT/"v21_go3b_candidates.json",candidate)
    scripts = ROOT/"hardware/mecanique/cartographe/verification/go3b/scripts"
    for name in ("bom_sequence.py","finaliser.py"):
        shutil.copy2(RUN/name,scripts/name)
    inputs = read(ROOT/"docs/verification/v21_go3a_candidates.json")["reference"]["dependencies"]
    manifest={"schema":"drone_agricole.go3b.manifest.v1","date":"2026-11-17",
        "finalized_at_utc":datetime.now(timezone.utc).isoformat(),"verdict":VERDICT,
        "reference":preflight["lock"],"active_sources":{"before":preflight["source_hashes"],
            "after":{name:guard.sha256(ROOT/"hardware/mecanique/cartographe"/name) for name in preflight["source_hashes"]},
            "status":"PASS"},"frozen_dependencies":inputs,"preflight":artifact(RUN/"preflight.json"),
        "backend":{"kind":"freecad_python","rpc_tool_available":False,"part_probe":artifact(RUN/"part-probe.json"),
                   "cables_probe":artifact(RUN/"cables-probe.json"),"environment":read(RUN/"consolidee/reopen.json")["environment"]},
        "archives":archive,
        "scripts":{p.relative_to(scripts).as_posix():artifact(p) for p in sorted(scripts.rglob("*.py"))},
        "results":{name:artifact(OUT/name) for name in ("v21_go3b_candidates.json","v21_go3b_validation.json")},
        "commands":[
          "Depuis la racine, PYTHONPATH=. et QT_QPA_PLATFORM=offscreen. Exécuter preparation.py avec Python système.",
          "Python FreeCAD -B construction.py <copie> <cas>, puis snapshot.py <copie> et reouvrir.py <copie>, chacun dans un nouveau processus.",
          "L2 et L4 exécutent les recettes des preuves electrical_evidence.json et independent_evidence.json.",
          "Python FreeCAD -B mesurer_service.py <copie>, puis Python système -B finaliser.py."],
        "publication":"Copies et rapports archivés byte-identiques aux mesures. Aucune promotion dans l’assemblage actif."}
    require(manifest["active_sources"]["before"]==manifest["active_sources"]["after"],"Sources finales divergentes.")
    make_report(candidate,control,manifest)
    manifest["results"]["06_GO3B_REPORT.md"]=artifact(ROOT/"docs/electromechanical_v2_1/06_GO3B_REPORT.md")
    write(OUT/"v21_go3b_manifest.json",manifest)
    print(VERDICT, service_result["samples"],"sondes",len(archive),"copies archivées",flush=True)


if __name__=="__main__":
    main()
