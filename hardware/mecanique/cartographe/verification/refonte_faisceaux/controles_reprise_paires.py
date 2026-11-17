"""Rejoue les intersections dont le contrôle combiné a dépassé le délai."""
import json
from pathlib import Path

from controles_geometrie import PairWorker, Scene, baseline_metadata, read, sha, write


HERE = Path(__file__).resolve().parent
MECHANICAL = HERE.parents[2]


def main():
    source = HERE / 'controles_geometrie_delta.json'
    proof = json.loads(read(source))
    assert proof['complete'] and proof['native_read_only']
    results = {}
    for current, key, native_hashes in (
        (True, 'pairs', 'inputs_sha256'),
        (False, 'reference_pairs', 'reference_inputs_sha256'),
    ):
        root = MECHANICAL / ('cartographe_faisceaux_refonte' if current else 'cartographe_faisceaux_autonome')
        metadata = baseline_metadata()
        if current:
            metadata.update(json.loads(read(HERE / 'metadonnees_controle.json')))
        scene = Scene(root, metadata)
        if scene.hashes() != proof[native_hashes]:
            raise RuntimeError('Les sources de la reprise diffèrent du contrôle nominal')
        worker = PairWorker(scene, timeout=35)
        results[key] = []
        try:
            for row in proof[key]['near_or_invalid_pairs']:
                if row['intersection_status'] != 'unknown':
                    continue
                a, b = [scene.items[name] for name in row['pair']]
                if not (a.shape.isValid() and b.shape.isValid()):
                    results[key].append(dict(row, reprise='solide source invalide'))
                    continue
                a.valid = b.valid = True
                result = worker.check(a, b, row['aabb_lower_bound_mm'], False)
                results[key].append(result)
                print(key, result['pair'], result['intersection_status'], flush=True)
        finally:
            worker.close()
    write(HERE / 'controles_reprise_paires.json', {
        'schema': 'cartographe.refonte.reprise-paires.v1', 'complete': True,
        'source_sha256': sha(source), 'reprises': results,
        'scope': 'Intersection volumique seulement, sans recalcul de distance sur les paires reprises.',
    })


if __name__ == '__main__':
    main()
