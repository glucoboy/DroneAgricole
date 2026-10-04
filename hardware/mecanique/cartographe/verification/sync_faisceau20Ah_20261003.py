"""Infrastructure documentaire : relever les chemins natifs et synchroniser le contrat de faisceau."""
from pathlib import Path
import json, hashlib
import FreeCAD as A
ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
VER=MEC/'verification'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def path_data(name):
    p=MEC/'pieces/commerce'/(name+'.FCStd')
    d=A.openDocument(str(p));r=d.getObject('Reference');d.recompute()
    path=d.getObject('Chemin')
    row={'reference_native':name,'fichier':str(p.relative_to(ROOT)).replace('\\','/'),
         'sha256':sha(p),'longueur_chemin_CAO_mm':path.Shape.Length,
         'forme_valide':r.Shape.isValid(),'solides':len(r.Shape.Solids)}
    A.closeDocument(d.Name);return row
p=VER/'faisceau_dock20Ah_20261002.json';w=json.loads(p.read_text(encoding='utf-8'))
w['date_utc']='2026-10-03'
w['realisation']='Implémenté : routes natives, interfaces, retenues et références de raccordement'
w['terminaisons']['dimensions_faisceaux']='Longueurs natives et préparations ci-dessous. Les préparations réservent une marge ; dénudages, sertissages et longueur finale sur gabarit à valider avec le lot. Aucun fil scellé du pack raccourci.'
for row,name,prep in [(w['routes_mobiles'][2],'EQ_Cordon10AWG_Plus_Dock20A',90),
                      (w['routes_mobiles'][3],'EQ_Cordon10AWG_Moins_Dock20A',100)]:
    row.update(path_data(name));row['longueur_chemin_CAO_indicative_mm']=row['longueur_chemin_CAO_mm']
    row['preparation_fil_mm']=prep;row['longueur_coupe_mm']=None
    row['validation_coupe']='Préparer cette longueur puis ajuster sur gabarit après contrôle des engagements cosse/soudure Amass ; coupe finale non qualifiée.'
fixed=[]
for net,name,mpn,prep in [('BAT_PLUS_BRUT','EQ_CordonFixe8AWG_Plus20A','55A0111-8-2',600),
                           ('BAT_MOINS_BRUT','EQ_CordonFixe8AWG_Moins20A','55A0111-8-0',520)]:
    row=path_data(name);row.update(net=net,fil_mpn=mpn,AWG=8,diametre_nominal_mm=4.78,
        diametre_etude_mm=5,rayon_minimum_arcs_CAO_mm=50,preparation_fil_mm=prep,
        cosse_mpn='3240219',epissure_mpn='34321',gaine_mpn='ATUM-12/3-0-50MM',
        gaine_ID_TE='NB08926001',gaine_preparation_mm=50,gaine_pose_etude_mm=44,
        reprise='P53 et collier T50R après la boucle libre ; tenue et mouvement flottant à valider',
        premier_bridage_apres_chemin_libre_CAO_mm=row['longueur_chemin_CAO_mm'],
        longueur_coupe_finale_mm=None)
    fixed.append(row)
w['segment_fixe_TE_JETI']={'statut':'Implémenté : CAO et BOM ; fabrication et essais À valider',
    'depart_bornes_mm':[[-167.353,21.6535,69.745],[-167.353,21.6535,86.255]],
    'destination':'JETI IN+/IN-','section_lot_JETI_mm2':None,'notice_sections_mm2':[6,8],
    'lot_requis':'8 mm² confirmé pour splice34321 retenu ; si kit6 mm², choisir une épissure différente validée avant assemblage.',
    'routes':fixed,'stock_JETI_routes':[path_data('EQ_FactoryJETI_IN_Plus20A'),path_data('EQ_FactoryJETI_IN_Moins20A')],
    'ports_module':{'centres_etude_mm':[[-130,-8,123.5],[-130,8,123.5]],'mesures_fabricant':False,
        'limite':'Réservations dans modèle dérivé uniquement ; ne pas usiner le module commercial. Mesurer le kit puis revoir les routes si ses sorties diffèrent.'},
    'protection':'P48 entretoises Cu, P49/P50 capot fixe, ATUM sur les deux épissures ; passages des fils et du collier dans P53/P41.',
    'rayon_stock_etude_mm':11.5,
    'limite':'R50 et >152,4mm libres démontrés géométriquement sur adaptateur. Compatibilité du mouvement flottant TE, rigidité, vibration et courbures réelles du stock JETI restent À valider.'}
w['fils_pack_conserves']=[]
for name in ['EQ_LeadPack8AWG_Plus20A','EQ_LeadPack8AWG_Moins20A']:
    row=path_data(name);row.update(longueur_fournie_mm=150,mou_a_ranger_mm=150-row['longueur_chemin_CAO_mm'],
        diametre_etude_mm=5,sortie_pack_mesuree=False,
        limite='Sorties du lot et rayon de courbure réel à contrôler ; géométrie interpolée sans auto-intersection ne qualifie pas le pliage des fils. Ranger le mou hors course sans modifier les fils scellés.')
    w['fils_pack_conserves'].append(row)
w['retenues']={'collier_mpn':'111-05012','quantite':7,
    'repartition':'2 module dont premier partagé avecP53 ;2 commande ;2 XT90 ;1 gaines surP53',
    'equilibrage':'Prise et faisceau du pack rangés dansP51/P52 ; genre, sortie et mou à contrôler sur le lot.',
    'limite':'Retenues implémentées dans la CAO ; traction, rigidité et vibration non testées physiquement.'}
w['sources_sha256']={str(q.relative_to(ROOT)).replace('\\','/'):sha(q)for q in [
    MEC/'sous_assemblages/SA02A_Dock20Ah.FCStd',VER/'build_dock20Ah_20261003.py',Path(__file__)]}
p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=VER/'sources_bom_dock20Ah_20261002.json';s=json.loads(p.read_text(encoding='utf-8'));s['date_utc']='2026-10-03'
extra=[
 {'fabricant':'TE Connectivity / Raychem','mpn':['55A0111-8-2','55A0111-8-0'],'url':'https://www.te.com/fr/product-4812533001.html','url_noir':'https://www.te.com/en/product-741387-000.html','donnees':{'AWG':8,'nombre_brins':133,'diametre_exterieur_nominal_mm':4.78,'tension_catalogue_V':600},'limite':'Ø5mm étude ; profil courant et courbures réelles à valider.'},
 {'fabricant':'TE Connectivity','mpn':'34321','url':'https://www.te.com/en/product-34321.html','donnees':{'AWG':8,'longueur_mm':21.01,'diametre_exterieur_mm':7.52,'diametre_interieur_mm':4.37,'masse_g':4.142},'limite':'Seulement pour kitJETI8mm² confirmé ; outillage de sertissage fabricant requis.'},
 {'fabricant':'TE Connectivity / Raychem','mpn':'ATUM-12/3-0-50MM','url':'https://www.te.com/en/product-NB08926001.html','donnees':{'ID_TE':'NB08926001','longueur_preparation_mm':50,'rapport_retreint':'4:1'},'limite':'Réservation posée44mm ; diamètre final, adhésion et recouvrement à mesurer.'},
 {'fabricant':'Henkel','mpn':'1335884','url':'https://dm.henkel-dam.com/is/content/henkel/CATALOGUE-VRM-2021-FR','donnees':{'designation':'Loctite243','volume_flacon_mL':50},'limite':'Compatibilité sur borne puissance TE à confirmer ; aucun couple universel inventé.'}]
for row in extra:
    s['sources']=[x for x in s['sources']if x.get('mpn')!=row['mpn']];s['sources'].append(row)
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'faisceau_fixe_longueurs_mm':[x['longueur_chemin_CAO_mm']for x in fixed],
    'cordons_mobiles_mm':[x['longueur_chemin_CAO_mm']for x in w['routes_mobiles'][2:]],'colliers':7},ensure_ascii=False))
