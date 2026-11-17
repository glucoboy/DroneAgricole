"""Criblage ciblé des sorties et du passage sous P66."""
import os
import sys
import essayer_faces as trial

trial.PARAMS=trial.HERE/"parametres_derniere_passe.json"
base_write=trial.write
trial.write=lambda path,data:base_write(path.with_name("essais_derniere_passe.json"),data)
try:
    trial.main()
finally:
    trial.PAIRS.close()
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
