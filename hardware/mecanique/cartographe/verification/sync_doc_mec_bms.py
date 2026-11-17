from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
p=ROOT/'docs/architecture/ARCHITECTURE_MECANIQUE.md';t=p.read_text(encoding='utf-8')
t=t.replace('du faisceau ne sont pas recalées sur la stack revue.','du faisceau sont désormais recalées sur la stack revue (§4.1.3.3), avec ports\nréservés et interfaces de lot À valider.')
t=t.replace(' └── SA07_Distribution_Systeme_Candidat\n',' ├── SA07_Distribution_Systeme_Candidat\n └── SA08_Faisceau_Systeme_Candidat\n')
t=t.replace(' SA06_RTK_Helical_Systeme_Candidat\n SA08_Faisceau_Systeme_Candidat\n SA07_Station_sol',' SA06_RTK_Helical_Systeme_Candidat\n SA07_Station_sol')
a=t.index('Le sous-assemblage `SA08_Faisceau_Systeme_Candidat` contient');b=t.index('| Point |',a)
new='''Le sous-assemblage `SA08_Faisceau_Systeme_Candidat` contient désormais
37 références de cordons à chemins arrondis et balayages natifs, pilotées
par la [recette](../../hardware/mecanique/cartographe/verification/routes_systeme_candidat_20261003.json).
Le faisceau recoté est lié à l'intégration locale courante avec BMS/TE.
Les sorties sont des passages réservés, pas des prises accouplées de lot.
Trois groupes restent non routés : refroidissement, accessoires de vol et LED.

Le contrôle courant est [la relecture native BMS](../../hardware/mecanique/cartographe/verification/controle_faisceau_natif_bms.json).
Les 37 cordons sont valides et sans intersection avec les obstacles
contrôlés en position assemblée ; les rayons, contacts, retenues, repli des
bras, mouvement du bloc isolé et course continue restent À valider.
Le contrôle du3octobre et ses 32 cordons avec recouvrements est historique ;
ses anciennes empreintes ne certifient pas les routes actuelles.
Aucune qualification matérielle ni bilan de centrage n'est déduit.

'''
t=t[:a]+new+t[b:]
t=t.replace('`X = 90..150`, `Y = -40..40`, `Z = -59..-36 mm`.','`X = 90..150`, `Y = -135..-55`, `Z = -52..-29 mm` (étage courant).')
p.write_text(t,encoding='utf-8')
print('Hiérarchie et sectionSA08 courantes synchronisées')
