"""Ajouter le faisceau courant au fichier d'intégration conservé en place."""
from etage_batterie_helpers import *
import json
proof=json.loads((VER/'controle_routes_systeme_courant.json').read_text(encoding='utf-8'))
assert proof['finalisation_correcte'] and not proof['collisions_restantes']
top=load('assemblages','Integration_Stack_Revue_20261003','IntegrationRevue').Document
r=load('sous_assemblages','SA08_Faisceau_Systeme_Candidat')
o=top.getObject('SA08_Faisceau_Systeme_Candidat') or link(top,top.IntegrationRevue,'SA08_Faisceau_Systeme_Candidat',r)
o.setLink(r);o.LinkTransform=False;o.LinkPlacement=A.Placement();o.Visibility=True
dock=load('sous_assemblages','SA02A_Dock20Ah','Ensemble').Document
if 'compact' in dock.Ensemble.BMSIntegre.lower():
 meta(top.IntegrationRevue,'Configuration','BMS au-dessus du pack, plateau relevé25mm ; TE rapproché40mm enX, décalé−6.1535mm enY et relevé12.255mm ; positif axial court, cosse négative tournée−90° autourX ; faisceau courant SA08. Implantation À valider.')
meta(top.IntegrationRevue,'Limites','IntégrationlocaleBMS/TE/SA07/SA08 ; géométriesdeprises etcontacts/rayons/fixationslot candidats, physiqueÀvalider. GNSSnonimplanté ; pasdronevolqualifié.')
save_native(top)
print('Assemblage final courant : six sous-systèmes, SA08 lié')
