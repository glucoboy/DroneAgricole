"""Arrêt préalable des recettes historiques après séparation des sous-assemblages."""
from pathlib import Path
import zipfile

def require_monolithic_layout(recipe):
    root = Path(__file__).resolve().parents[4]
    top = root / 'hardware/mecanique/cartographe/assemblages/Integration_Stack_Revue_20261003.FCStd'
    if top.exists():
        with zipfile.ZipFile(top) as archive:
            separated = b'batterie_recepteur_principal' in archive.read('Document.xml')
        if separated:
            raise RuntimeError(recipe + ' est historique (BMS monolithique). Utiliser update_hierarchie_batterie.py, verify_hierarchie_batterie.py et update_registres_hierarchie_batterie.py ; retour antérieur par Git.')
