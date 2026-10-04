"""Infrastructure d'inventaire CAO en lecture seule et consolidation de BOM.
Exécuter avec le Python fourni avec FreeCAD ; ne sauvegarde aucun FCStd.
Les masses issues de densités sont des hypothèses, jamais des pesées.
"""
from pathlib import Path
from collections import Counter
import json, hashlib
import FreeCAD as A

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
VER=MEC/'verification'
def read(name): return json.loads((VER/name).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p): return str(Path(p).relative_to(ROOT)).replace('\\','/')
proof=read('construction_cassette20Ah_20261002.json')
counts=Counter(x['reference'] for x in proof['occurrences'])
complete=MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd'
assembly_source=None
if complete.exists():
    dc=A.openDocument(str(complete)); dc.recompute()
    rd=dc.getObject('Ensemble') or dc.getObject('Reference')
    actual=Counter()
    def walk(obj,stack=()):
        if obj.TypeId=='App::Link':
            target=obj.LinkedObject
            if target is None:
                raise RuntimeError('Lien non résolu : '+obj.Name)
            name=Path(target.Document.FileName).stem
            if name.startswith(('P','EQ_')):
                actual[name]+=1
                return
            if (target.Document.Name,target.Name) in stack:
                raise RuntimeError('Cycle de lien : '+obj.Name)
            walk(target,stack+((target.Document.Name,target.Name),))
        else:
            for item in getattr(obj,'Group',[]): walk(item,stack)
    walk(rd)
    counts=actual
    assembly_source={'fichier':rel(complete),'sha256':sha(complete),'racine':rd.Name,'occurrences':dict(counts)}
    # Les documents externes restent ouverts pour les inventaires ci-dessous.
for key,q in {'P27_Interface_Pixhawk_Rehausse20':1,'P37_Entretoise70_6061_M3':4,
              'P38_Plateau309_PercagesRails':1,'P41_Support_Jeti_Dock20':1,
              'EQ_Vis_M2x10_CHC_Candidat':2}.items():
    counts[key]=max(counts[key],q)
fabricated=[]; standard=[]; errors=[]
densities={'P27':1.85,'P30':1.85,'P32':1.85,'P34':2.7,'P35':2.7,'P36':2.7,'P37':2.7,'P42':8.96,'P48':8.96}
for key,q in sorted(counts.items()):
    if not(key.startswith('P') or key.startswith(('EQ_ISO','EQ_DIN','EQ_Vis'))): continue
    folder='fabriquees' if key.startswith('P') else 'commerce'
    p=MEC/'pieces'/folder/(key+'.FCStd')
    if not p.exists(): errors.append('Référence native manquante : '+key); continue
    d=A.openDocument(str(p)); r=d.getObject('Reference') or d.getObject('Ensemble'); d.recompute()
    if r is None:
        errors.append('Racine Reference absente : '+key+' ; objets : '+','.join(x.Name for x in d.Objects if x.TypeId=='App::Part'))
        A.closeDocument(d.Name); continue
    if r.Shape.isNull() or not r.Shape.isValid(): errors.append('Forme native invalide : '+key)
    v=r.Shape.Volume
    row={'reference':key,'quantite_installee':q,'fichier':rel(p),'source_objet':r.Name,'solides_geometriques':len(r.Shape.Solids),
         'sha256':sha(p),'volume_unitaire_mm3':v,'statut_CAO':'Implémenté','statut_physique':'À valider',
         'specification_native':getattr(r,'Specification',''), 'matiere_native':getattr(r,'Materiau','')}
    if key.startswith('P'):
        density=densities.get(key[:3],1.01)
        row.update(densite_hypothese_g_cm3=density,masse_hypothese_g=q*v/1000*density,
                   fabrication='Usiner/découper ou imprimer la référence native et son STEP associé ; ne pas fabriquer une réservation commerciale.')
        fabricated.append(row)
    else:
        row.update(densite_hypothese_g_cm3=7.85,masse_hypothese_g=q*v/1000*7.85,
                   note_masse='Filet et empreinte de tête simplifiés ; provision par volume plein, pas masse réelle.')
        if 'M25x5' in key:
            row['fourniture_existante']={'fabricant':'Accu','mpn':'SIK-M2.5-5-CS-BZP','source':'https://www.accu.co.uk/phillips-countersunk-screws/989265-SIK-M2-5-5-CS-BZP','standard':'DIN965 Phillips, acier4.8 zingué, têteØ4,7/h1,5'}
        if key=='EQ_ISO7046_2_M3x8_Dock':
            row['fourniture_existante']={'fabricant':'Accu','mpn':'SIK-M3-8-CS-BZP','source':'https://accu-components.com/us/phillips-countersunk-screws/989274-SIK-M3-8-CS-BZP','standard':'DIN965 Phillips / ISO7046-2, acier4.8 zingué, têteØ5,6/h1,65'}
        if key=='EQ_DIN7991_M3x16_Contacts20Ah':
            row['fourniture_existante']={'fabricant':'Accu','mpn':'SSK-M3-16-10.9','source':'https://www.accu.co.uk/countersunk-socket-head-screws/495048-SSK-M3-16-10-9','standard':'DIN7991, classe10.9, têteØ6/h1,7','approvisionnement':'Page primaire disponible horsligne/fabricationpourcommande, disponibilité physique à confirmer.'}
        standard.append(row)
    A.closeDocument(d.Name)

commercial=[]
def part(id,manufacturer,mpn,q,description,model=None,url=None,included=False,mass=None):
    row={'reference':id,'fabricant':manufacturer,'mpn':mpn,'quantite_installee':q,
         'quantite_achat_unitaire':0 if included else q,'designation':description,
         'statut_selection':'Implémenté : sélection de conception','statut_physique':'À valider'}
    if url:row['source']=url
    if model:
        p=MEC/'pieces/commerce'/model
        row['fichier']=rel(p)
        if p.exists(): row['sha256']=sha(p)
        else: errors.append('Modèle commercial manquant : '+model)
    if mass is not None: row['masse_publiee_g']=mass
    commercial.append(row)
part('BAT20','Tattu','TAA200006S5X9S',1,'NMC 6S 20Ah 22,2V, 193×76×58mm ; AWG8/150mm et XT90-S conservés',
     'EQ_Tattu20Ah6S_Dock.FCStd','https://gensace.de/collections/semi-solid-state/products/tattu-nmc-20000mah-22-2v-5c-6s1p-lipo-battery-pack-with-xt90-s-plug',mass=1950)
part('LOQUET','Southco','R4-05-40-405-10',1,'Micro rotary push-to-close, deux stages, bumper et gâchette manuelle intégrés','EQ_SouthcoR405.FCStd','https://southco.com/en_au_int/r4-05-40-405-10')
part('GACHE','Southco','R4-90-0521-10',1,'Gâche acier Ø6, filetage M5×0,8','EQ_SouthcoGacheR490.FCStd','https://southco.com/en_au_int/r4-90-0521-10')
part('SW100','JETI','J-MSW-100-MS',1,'MainSwitch100 avec câbles et commande magnétique incluse ; commute le négatif. Modèle à ports réservés, à mesurer sur kit réel. Ne pas usiner le module.','EQ_JetiMainSwitch100_PortsEtude20A.FCStd','https://jetimodelusa.com/products/j-msw-100-ms',mass=110)
part('MAG','JETI','Inclus dans J-MSW-100-MS',1,'Commande magnétique du kit ; enveloppe2025/06 à contrôler sur le lot','EQ_JetiMagneticSwitch.FCStd',included=True,mass=11)
part('COLLIERS','HellermannTyton','111-05012',7,'T50R-PA612-BK, 202×4,6×1,2mm ; 4 pour MainSwitch/commande dont un partagé P53,2 pour XT90,1 pour gaines du faisceau fixe',url='https://www.hellermanntyton.com/products/cable-ties-inside-serrated/t50r/111-05012')
part('ADAPTATEUR_PACK','Amass','XT90H-M.G.Y',1,'Mâle soudable accouplé à XT90-S du pack ; source45A/10AWG, pas85Acontinu','EQ_AmassXT90HM_Dock20A.FCStd',url='https://www.china-amass.net/xt90h-m-product/')
part('CONNECTEUR_PACK_INCLUS','Amass / Tattu','XT90S-F.G.Y, lot à contrôler',1,'Femelle XT90-S fournie et maintenue avec le pack ; incluse dans BAT20, ne pas acheter unsecondjeu','EQ_AmassXT90SF_Dock20A.FCStd',included=True)
part('CAP_ADAPTATEUR','Amass','043.0222.Y',1,'Cap arrière isolant XT90H-M jaune',url='https://www.china-amass.net/xt90h-m-product/')
part('COSSES_FRONTALES','Phoenix Contact','3240028',2,'C-RCI6/M5, AWG10, 4–6mm², à sertir sur adaptateur mobile','EQ_Phoenix3240028_Dock20A.FCStd','https://www.phoenixcontact.com/en-us/products/ring-cable-lug-c-rci-6-m5-3240028',mass=1.708)
part('CORDON_PLUS','TE Connectivity / Raychem','55A0111-10-2',1,'Fil rougeAWG10, ETFE, Ønominal3,25mm ; route mobile sousP46/P47, longueur de coupe selon faisceau','EQ_Cordon10AWG_Plus_Dock20A.FCStd','https://www.te.com/fr/product-070069-002.html')
part('CORDON_MOINS','TE Connectivity / Raychem','55A0111-10-0',1,'Fil noirAWG10, ETFE, Ønominal3,25mm ; route mobile sousP46/P47, longueur de coupe selon faisceau','EQ_Cordon10AWG_Moins_Dock20A.FCStd','https://www.te.com/en/product-552231-000.html')
part('COSSES_FIXES','Phoenix Contact','3240219',2,'C-RCI10/M5, adaptateur AWG8 fixe TE vers JETI ; contrôler sertissage et cosse réelle','EQ_Phoenix3240219_Dock20A.FCStd','https://www.phoenixcontact.com/en-pc/products/ring-cable-lug-c-rci-10-m5-3240219',mass=3.493)
part('CORDON_FIXE_PLUS','TE Connectivity / Raychem','55A0111-8-2',1,'AWG8 rouge ETFE, préparation600mm puis ajustage sur gabarit après contrôle des courbures et des terminaisons','EQ_CordonFixe8AWG_Plus20A.FCStd','https://www.te.com/fr/product-4812533001.html')
part('CORDON_FIXE_MOINS','TE Connectivity / Raychem','55A0111-8-0',1,'AWG8 noir ETFE, préparation520mm puis ajustage sur gabarit après contrôle des courbures et des terminaisons','EQ_CordonFixe8AWG_Moins20A.FCStd','https://www.te.com/en/product-741387-000.html')
part('EPISSURES_JETI','TE Connectivity','34321',2,'SOLISTRAND splice AWG8, uniquement pour kit JETI8mm² confirmé ; outil et gaine de protection selon fabricant','EQ_TE34321_Splice8AWG_Dock20A.FCStd','https://www.te.com/en/product-34321.html')
part('ISOLATION_EPISSURES','TE Connectivity / Raychem','ATUM-12/3-0-50MM',2,'Gaine adhésive4:1 précoupée50mm, fournit une protection pour chaque splice ; recouvrement posé44mm à contrôler','EQ_ATUM12_3_IsolationSplice20Ah.FCStd','https://www.te.com/en/product-NB08926001.html')
part('EQUILIBRAGE_INCLUS','Tattu / JST','Prise XH7 et fils du lot BAT20',1,'Prise et fils d’équilibrage fournis dans BAT20, rangés enP51/P52 ; genre et sortie réelle à contrôler','EQ_EquilibragePack20Ah_Reservation.FCStd',included=True)
for id,mpn,q,text in [('TE_PIN','1648151-1',1,'Boîtier MiddleDrawer125A pin, fixé au drone'),
                     ('TE_SOCKET','1648156-1',1,'Boîtier MiddleDrawer125A socket, fixé à cassette'),
                     ('TE_CONTACT_PIN','1766283-1',2,'Contact puissance pin M5'),
                     ('TE_CONTACT_SOCKET','6648335-1',2,'Contact puissance socket M5'),
                     ('TE_FLOAT','1650589-1',2,'Vis épaulée de montage flottant M4')]:
    part(id,'TE Connectivity',mpn,q,text,model='EQ_TE_'+mpn.split('-')[0]+'_Dock20.FCStd',url='https://www.te.com/en/product-'+mpn+'.html')

part('CALES','RS PRO','205-513',1,'Feuille EPDM dense noir70ShA épaisseur1mm ; découper et empiler selon pack mesuré, fond198×78mm. Quantité1 signifie matière première, pas1cale universelle.',
     'EQ_MousseEPDM1_Dock.FCStd','https://docs.rs-online.com/805e/A700000012600376.pdf')
part('FREINFILET','Henkel Loctite','1335884',1,'Loctite243 flacon50mL ; fixationsM3 selon assemblage. Compatibilité borne puissance à confirmer avant usage sur contact.')

# Provisions de masse de modèles commerciaux, avec densités hypothétiques.
# Les logements et contacts industriels peuvent mélanger plusieurs matériaux.
te_provisions=[]
for row in commercial:
    if not row['reference'].startswith('TE_') or not row.get('fichier'): continue
    p=ROOT/row['fichier']; dd=A.openDocument(str(p)); rr=dd.getObject('Reference') or dd.getObject('Ensemble'); dd.recompute()
    volume=rr.Shape.Volume
    density=1.4 if row['reference'] in ('TE_PIN','TE_SOCKET') else 7.85 if row['reference']=='TE_FLOAT' else 8.9
    te_provisions.append({'reference':row['reference'],'quantite':row['quantite_installee'],
        'volume_unitaire_mm3':volume,'densite_hypothese_g_cm3':density,
        'masse_provision_g':volume/1000*density*row['quantite_installee'],
        'limite':'Modèle industriel simplifié et densité présumée ; pas masse fabricant, pas pesée et pas borne certifiée.'})
    A.closeDocument(dd.Name)

old=read('bilan_masse_volumes_20261002.json')
removed=sum(x['masse_pleine_hypothese_g'] for x in old['references_actives_non_metalliques'] if x['reference'].startswith(('P13_','P14_','P15_','P20_')))
oldcolumns=4*688.867895855217/1000*2.7
computed=sum(x['masse_hypothese_g'] for x in fabricated if not x['reference'].startswith('P38'))
steel=sum(x['masse_hypothese_g'] for x in standard)
delta=computed+steel+121-removed-oldcolumns
mass={'statut':'À valider','type':'Budget partiel par volumes et densités, non pesé',
      'base_20Ah_historique_kg':[5.591456,6.205456],
      'retrait_P13_P14_P15_P20_hypothese_g':removed,
      'retrait_4_colonnes50_hypothese_alu_g':oldcolumns,
      'ajout_fabrication_hors_P38_g':computed,'ajout_visserie_native_hypothese_acier_g':steel,
      'ajout_JETI_110_et_commande11_provision_g':121,
      'delta_partielle_g':delta,'sous_total_partiel_kg':[5.591456+delta/1000,6.205456+delta/1000],
      'provisions_TE_separees':te_provisions,
      'sous_total_plus_TE_provision_kg':[5.591456+(delta+sum(x['masse_provision_g']for x in te_provisions))/1000,6.205456+(delta+sum(x['masse_provision_g']for x in te_provisions))/1000],
      'provision_EPDM_fond_198x78x1_g':23.166,
      'commerces_metalliques_masses_publiees_g':18.686,
      'detail_commerces_metalliques':'2 splices34321 à4.142g +2 cosses3240219 à3.493g +2 cosses3240028 à1.708g ; distincts des contactsTE et de la visserie.',
      'sous_total_plus_TE_EPDM_commerces_connus_kg':[5.591456+(delta+sum(x['masse_provision_g']for x in te_provisions)+23.166+18.686)/1000,6.205456+(delta+sum(x['masse_provision_g']for x in te_provisions)+23.166+18.686)/1000],
      'pack_tolerance_a_propagation_g':20,
      'limite_decollage_X650_publiee_kg':6.3,
      'non_comptes':['Loquet et gâche Southco : masses fabricant non récupérées',
                    'TE logements, quatre contacts et vis épaulées : provision séparée, pas dans sous-total partiel',
                    'XT90 adaptateur et conducteurs souples : masses à consolider ; cosses comptées dans commerces connus',
                    'Cales softpack supplémentaires, colliers et gaines ; EPDM de fond provisionné séparément',
                    'Différence masse réelle des équipements électroniques versus provisions historiques'],
      'absence_credit':'Ancien connecteur SBS/faisceau non retiré car non individualisé dans le budget historique ; aucun crédit inventé.',
      'limite':'P38 est le plateau309 existant repercé, pas un second plateau à ajouter. Une marge du sous-total ne démontre pas conformité du drone complet. Anciennes durées20Ah ne concernent pas cette nouvelle masse.'}
bom={'schema_version':1,'date_utc':'2026-10-03','statut':'À valider','realisation_CAO':'Implémenté',
     'objet':'BOM du changement 6S20Ah : cassette/dock, rehausse et déplacement avionique ; équipements inchangés conservés par le manifeste principal.',
     'sources_sha256':{rel(VER/'construction_cassette20Ah_20261002.json'):sha(VER/'construction_cassette20Ah_20261002.json'),rel(VER/'construction_dock20Ah_20261003.json'):sha(VER/'construction_dock20Ah_20261003.json'),rel(Path(__file__)):sha(__file__)},
     'assemblage_inventorie':assembly_source,
     'alternative_etude':{'fabricant':'Tattu','mpn':'TAA200006S5ASX','active':False,'quantite_installee':0,
         'dimensions_nominales_mm':[193,76,58],'masse_publiee_g':1950,'tolerance_masse_g':20,
         'serie':6,'capacite_Ah':20,'sortie':'AS150+XT150','fils':'AWG8/150mm',
         'courant_catalogue_maillon_limitant_A':60,
         'conditions':'Amass2025 : AS15075A p32, XT15060A p27 ; 8AWG ΔT<85°C. Ces limites ne qualifient pas le profil mission.',
         'source':'https://gensace.de/products/tattu-nmc-20000mah-22-2v-5c-6s1p-lipo-battery-pack-with-as150-xt150-plug',
         'raison_non_active':'Genres/polarités du lot et intégration du nouvel adaptateur à définir ; conception présente retenue en XT90.'},
     'pieces_fabriquees':fabricated,'visserie_modelee':standard,'composants_commerce':commercial,
     'faisceau':'verification/faisceau_dock20Ah_20261002.json','sources_commerce':'verification/sources_bom_dock20Ah_20261002.json',
     'bilan_masse_partiel':mass,'anomalies_generation':errors,
     'elements_a_synchroniser':['Routes, sections, longueurs et terminaisons du faisceau avec sa preuve finale', 'Cosses et conducteur souple avec MPN de fourniture définitif', 'Cales mesurées pour immobiliser le pack sans compression forcée'],
     'qualification':'Aucun achat, assemblage physique, essai thermique, essai de verrouillage ou vol effectué.'}
(VER/'bom_dock20Ah_20261002.json').write_text(json.dumps(bom,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'references_fabriquees':len(fabricated),'visserie':len(standard),'anomalies':errors,'masse_partielle':mass},ensure_ascii=False))
