"""Sonde BRep en lecture seule pour les quatre feuilles OEM sans désignation.

Adaptateur de preuve FreeCAD : aucune définition massique ni modification native.
"""
import hashlib
import json
import os
from pathlib import Path

from read_brep_prototype import Reader


BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[2]
PROOF = BASE / 'verification/orch_reprise_masses_structure.json'
NATIVE = 'pieces/commerce/EQ_Chassis_X650.FCStd'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    reader = Reader(BASE)
    before = sha(BASE / NATIVE)
    rows = []
    for unknown, lower, upper, motor, diffuser in (
        (212, 182, 183, 184, 185), (244, 214, 215, 216, 217),
        (276, 246, 247, 248, 249), (308, 278, 279, 280, 281),
    ):
        name = 'Part__Feature%03d' % unknown
        shape = reader.shape(NATIVE, name)
        contacts = []
        for number, role in ((lower, 'base moteur inférieure'),
                             (upper, 'base moteur supérieure'),
                             (motor, 'moteur'), (diffuser, 'diffuseur LED')):
            neighbor = 'Part__Feature%03d' % number
            other = reader.shape(NATIVE, neighbor)
            contacts.append({
                'objet_voisin': neighbor,
                'role_voisin': role,
                'distance_mm': shape.distToShape(other)[0],
                'volume_intersection_mm3': shape.common(other).Volume,
            })
        rows.append({'objet': name, 'valide': shape.isValid(),
                     'volume_mm3': shape.Volume, 'voisinage': contacts})
    assert before == sha(BASE / NATIVE), 'La sonde a modifié le natif'
    proof = json.loads(PROOF.read_text(encoding='utf-8-sig'))
    proof['sonde_feuilles_oem'] = {
        'natif': 'hardware/mecanique/cartographe/' + NATIVE,
        'sha256_avant': before, 'sha256_apres': before,
        'natif_inchange': True, 'observations': rows,
        'recette': str(Path(__file__).resolve().relative_to(ROOT)).replace('\\', '/'),
        'recette_sha256': sha(__file__),
        'lecteur_sha256': sha(BASE / 'verification/read_brep_prototype.py'),
        'interpretation': (
            'Les feuilles 00/001/002/003 chevauchent presque entièrement la base '
            'moteur inférieure. Leur attribution automatique à une carte LED '
            'n’est pas justifiée. Fonction, matière et caractère physique '
            'distinct doivent être confirmés par le fabricant ; aucune masse '
            'et aucune suppression ne sont déduites de ce chevauchement.'
        ),
    }
    PROOF.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n',
                     encoding='utf-8')
    print(json.dumps({'feuilles_sondees': len(rows), 'natif_inchange': True}))


if __name__ == '__main__':
    main()
    # La sonde n'ouvre aucun document ; terminer explicitement le runtime Qt.
    import sys
    sys.stdout.flush()
    os._exit(0)
