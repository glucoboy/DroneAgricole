"""Collecte d'originaux fabricant du lot ORCH, sans modification des natifs/BOM.

Infrastructure seulement : téléchargements, empreintes et extraction brute de JSON.
Les calculs de masses sont exécutés par l'adaptateur C++17 voisin.
"""
from pathlib import Path
import hashlib
import json
import urllib.request
import sys

BASE = Path(__file__).resolve().parents[1]
DEST = BASE / 'sources_fabricants/orch_reprise_masses_fournitures'
SOURCES = [
 ('SORBOTHANE-101', 'sorbothane_101.pdf', 'https://www.sorbothane.com/wp-content/uploads/101-sorbothane-material-properties.pdf', '101, effective 2021-08-17 ; original relu visuellement'),
 ('SORBOTHANE-PLAN', 'sorbothane_bushings_washers.pdf', 'https://www.sorbothane.com/wp-content/uploads/sorbothane-spg-bushings-washers.pdf', 'Standard Products Guide, revised06/2025, pages6-7'),
 ('ETTINGER-M3-6', 'ettinger_m3x6.pdf', 'https://www.ettinger.de/en/product-datasheet/ed3b840b760c76c641f93ad8ec7f028d/create', '001.16.321, fiche courante'),
 ('ETTINGER-M3-8', 'ettinger_m3x8.pdf', 'https://www.ettinger.de/en/product-datasheet/80c2e6aa901f3ce5edcdaec9d1d9e929/create', '001.16.331, fiche courante'),
 ('ETTINGER-M3-12', 'ettinger_m3x12.pdf', 'https://www.ettinger.de/en/product-datasheet/0d5ccb9f746dcfb12f7d043366c5ef7d/create', '001.16.351, fiche courante'),
 ('ETTINGER-M3-16', 'ettinger_m3x16.pdf', 'https://www.ettinger.de/en/product-datasheet/be2066741bdcbed49131622c79dd652e/create', '001.16.361, fiche courante'),
 ('CHAVESBAO-M3-985', 'chavesbao_985.html', 'https://www.chavesbao.com/en/tornilleria/nuts/insert-nuts/din-985-zp/', '660730003, fiche courante'),
 ('FERROMETAL-INDUSTRIE', 'ferrometal_industrie.pdf', 'https://www.ferrometal.fi/media/downloads/catalogues/ferrometal_fasteners_for_industry.pdf', 'Catalogue fixmaster fabricant/distributeur, version en ligne'),
 ('FERROMETAL-CONSTRUCTION', 'ferrometal_construction.pdf', 'https://www.ferrometal.fi/media/downloads/catalogues/ferrometal_steel_construction_fasteners.pdf', 'Catalogue fixmaster version en ligne'),
 ('ETTINGER-WASHERS', 'ettinger_washers.html', 'https://www.ettinger.de/en/fastening-technology/washers/flat-washers/', 'Catalogue courant'),
 ('ETTINGER-WASHER-M3', 'ettinger_washer_m3.html', 'https://www.ettinger.de/en/p/flat-washer-din125-a-iso7089-oe3.2-7.0-x-0.5-zinc-plated-steel/003.05.031', '003.05.031, fiche courante'),
 ('ETTINGER-WASHER-M3-PDF', 'ettinger_washer_m3.pdf', 'https://www.ettinger.de/en/product-datasheet/c306b57669cb47545341122054e840f8/create', '003.05.031, fiche courante'),
 ('MOLEX-502439', 'molex_502439.html', 'https://www.molex.com/en-us/products/series-chart/502439', 'Catalogue courant ; MPN candidats non substitués aux prises OEM inconnues'),
 ('MOLEX-502438', 'molex_502438.html', 'https://www.molex.com/en-us/products/series-chart/502438', 'Catalogue courant'),
 ('LITTELFUSE-FHAC', 'littelfuse_fhac.pdf', 'https://www.littelfuse.com/assetdocs/littelfuse-fuse-holder-ato-fhac-datasheet.pdf?assetguid=272e0b1a-a576-4173-8740-c1eb469efd79', 'ATO FHAC Series, édition courante'),
 ('LITTELFUSE-ATOF', 'littelfuse_atof.pdf', 'https://www.littelfuse.com/assetdocs/littelfuse_datasheet_287_atof_r2.7.pdf?assetguid=43dcdce8-8ca2-426f-8998-7e566f048d40', 'ATOF, revised02/04/2025, 1.4g typique sans tolérance actuelle'),
 ('LITTELFUSE-ATO', 'littelfuse_ato.html', 'https://www.littelfuse.com/products/fuses-overcurrent-protection/fuses/automotive-aftermarket-products-fuses/blade-fuses-shunts-automotive-aftermarket/ato', '287Series, page courante'),
]

def sha(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 DEST.mkdir(parents=True, exist_ok=True)
 result=[]
 for ident,name,url,revision in SOURCES:
  target=DEST/name
  row=dict(id=ident,url=url,fichier=target.relative_to(BASE).as_posix(),revision=revision,date_consultation='2026-10-25',droits='Document public du fabricant ; aucune licence de redistribution identifiée. Original conservé hors Git selon politique projet.')
  try:
   if not target.exists():
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=20) as response:
     data=response.read()
     if name.endswith('.pdf') and not data.startswith(b'%PDF'): raise RuntimeError('Réponse non PDF')
     target.write_bytes(data)
   row['sha256']=sha(target)
   row['octets']=target.stat().st_size
  except Exception as exc: row.update(sha256=None,erreur=str(exc))
  result.append(row)
  print(ident,row.get('sha256'),row.get('erreur',''),flush=True)
 (DEST/'collecte.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
