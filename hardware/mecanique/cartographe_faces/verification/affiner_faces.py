"""Deuxième passe bornée. Réemploie le même crible et conserve le premier résultat."""
import os
import sys

import essayer_faces as trial

trial.PARAMS = trial.HERE / "parametres_affinage.json"
original_write = trial.write


def write_affinage(path, value):
    value["replay_wrapper_sha256"] = trial.sha(__file__)
    original_write(path.with_name("essais_affinage.json"), value)


trial.write = write_affinage
try:
    trial.main()
finally:
    trial.PAIRS.close()
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
