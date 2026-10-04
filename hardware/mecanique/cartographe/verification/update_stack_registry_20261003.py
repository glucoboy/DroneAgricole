"""Infrastructure : registre de variante, sous-BOM et galerie de captures natives."""
from pathlib import Path
import json,hashlib,html
ROOT=Path(__file__).resolve().parents[4];MEC=ROOT/'hardware/mecanique/cartographe';VER=MEC/'verification'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
build=read(VER/'construction_stack_revue_20261003.json')
control=read(VER/'controle_stack_revue_20261003.json')
render=read(VER/'rendus_stack_revue_20261003.json')
assert control['finalisation_correcte'] and render['finalisation_correcte']
assert control['construction_sha256']==render['construction_sha256']==sha(VER/'construction_stack_revue_20261003.json')
for row in build['nouveaux_fichiers']:assert sha(ROOT/row['fichier'])==row['sha256']
refs=[dict(row,reference=Path(row['fichier']).stem,
      type='fabriquee' if '/fabriquees/' in row['fichier'] else 'commerce' if '/commerce/' in row['fichier'] else 'assemblage',
      realisation_CAO='Implémenté',statut='À valider') for row in build['nouveaux_fichiers']]
bom=[{'reference':'P54_Appui_CA01_Holybro_Stack','quantite':4,'definition_mm':{'L':2,'D':5.5,'passage':3.2}},
     {'reference':'P55_EntretoiseBasse_Stack','quantite':4,'definition_mm':{'L':24,'D':6,'passage':3.2}},
     {'reference':'EQ_VisM3x65_Stack','quantite':4,'definition_mm':{'longueur_sous_tete':65,'filet_nominal':3}},
     {'reference':'EQ_RondelleM3_Stack','quantite':4,'definition_mm':{'epaisseur':.5,'D':7,'passage':3.2}},
     {'reference':'P56_PlaqueBasse_PercagesStack','quantite':1,'substitution':'OEM312, aucune addition de plaque','definition_mm':{'trous_repris':3.2}},
     {'reference':'CA01_PCB_Revue_20261003','quantite':1,'substitution':'CA01_preplacement, aucune deuxième carte'}]
for row in bom:row.update({'statut':'À valider','masse_unitaire_g':None,'masse_perimetre':'Matière, fournisseur et pesée non établis'})
mass={'statut':'À valider','masse_stack_montee_g':None,'masse_fixations_ajoutees_g':None,
      'regle':'La plaqueP56 et CA01de revue sont des substitutions ; P17 et kitOEM restent comptés dans leur ensemble. Aucune masseCAO de métal fileté assimilée à pesée.'}
variant={'date':'2026-10-03','active':False,'statut':'À valider','realisation_CAO':'Implémenté',
    'assemblage':'hardware/mecanique/cartographe/assemblages/Integration_Stack_Revue_20261003.FCStd',
    'reference_plan':'https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/dimension-and-weight',
    'references':refs,'occurrences':build['occurrences'],'montage':build['montage'],'sous_BOM':bom,
    'bilan_masse':mass,'verification':'verification/controle_stack_revue_20261003.json',
    'revue':'verification/revue_independante_stack_20261003.json',
    'visuels':'exports/stack_avionique_revue_20261003/index.html','faisceau_recale':False,'qualification_physique':False}
manifest=MEC/'manifest.json';m=read(manifest);baseline={k:v for k,v in m.items() if k!='configuration_stack_revue_20261003'}
m['configuration_stack_revue_20261003']=variant;write(manifest,m)
assert {k:v for k,v in read(manifest).items() if k!='configuration_stack_revue_20261003'}==baseline
cfg=MEC/'configuration_cible_20261003.json';c=read(cfg)
c['configuration']['variante_stack_revue']='assemblages/Integration_Stack_Revue_20261003.FCStd'
c['configuration']['limite_stack_revue']='Fixation commune candidate à P17, accès outil avec bloccapteurs déposé ; ancien faisceau non recalé, physique et masse À valider.'
byid={r['id']:r for r in c['bom']}
for key,children in [('AVI_SUPPORT',bom[1:2]+bom[4:5]),('AVI_SPACERS',bom[0:1]),('AVI_FAST',bom[2:4])]:
    byid[key]['statut_CAO']='Implémenté dans variante inactive de stack montée'
    byid[key]['sous_BOM_revue']=children
    byid[key]['reserves']=['Choix candidat ; tenue/précharge/fluage P17 et PCB, isolement tiges/carbone, serrage et fournisseur À valider.']
byid['AVI_FAST']['quantite_cible']=4;byid['AVI_FAST']['quantite_statut']='Quatre jeux candidats vis+rondelle'
byid['CA01']['variante_CAO_courante']='pieces/fabriquees/CA01_PCB_Revue_20261003.FCStd'
c['revue_stack_20261003']={'manifest_key':'configuration_stack_revue_20261003','sous_BOM':bom,'montage':build['montage'],'bilan_masse':mass}
write(cfg,c)
out=MEC/'exports/stack_avionique_revue_20261003'
labels={'stack_montee_isometrique':'Stack et fixation commune — les P17 et la plaque figurent dans les vues intégrées',
        'stack_montee_profil':'Profil de la stack ; G10 brun, CA01 vert, visserie grise',
        'CA01_placement_courant':'CA01, placement du PCB courant',
        'stack_montee_dessous':'Dessous de la stack : connecteurs et composants',
        'integration_stack_profil':'Vue locale intégrée : stack, plaque basse et appuis capteurs',
        'integration_stack_isometrique':'Vue locale dans le drone candidat'}
fig=[]
for r in render['images']:
    file=ROOT/r['fichier'];assert sha(file)==r['sha256']
    fig.append('<figure><a href="'+file.name+'"><img src="'+file.name+'"></a><figcaption>'+html.escape(labels[r['nom']])+'</figcaption></figure>')
page='''<!doctype html><meta charset="utf-8"><title>Stack avionique — revue FreeCAD</title>
<style>body{font:16px system-ui;background:#f3f5f7;color:#172332;max-width:1400px;margin:30px auto;padding:0 24px}h1{font-size:28px}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}figure{margin:0;background:white;padding:14px;border-radius:8px}img{width:100%;display:block}figcaption{padding:10px}a{color:#235c82}p{max-width:1000px;line-height:1.6}@media(max-width:800px){main{grid-template-columns:1fr}}</style>
<h1>Stack avionique — montage candidat</h1><p>Captures directement produites dans FreeCAD. Porteuse OEM conservée ; CA01 synchronisée. Quatre appuis2mm, entretoises24mm et visM3×65. Fixation commune avec P17 : déposer le bloccapteurs pour accéder aux vis. Tenue, précharge, isolement électrique, thermique et faisceau restent à valider.</p><main>'''+''.join(fig)+'</main>'
(out/'index.html').write_text(page,encoding='utf-8')
write(VER/'controle_registre_stack_20261003.json',{'finalisation_correcte':True,'date':'2026-10-03',
    'autres_champs_manifest_preserves':True,'references':len(refs),'occurrences':len(build['occurrences']),
    'postes_BOM_cible':len(c['bom']),'sous_BOM_stack':bom,'bilan_masse':mass,
    'manifest_sha256':sha(manifest),'configuration_cible_sha256':sha(cfg),'galerie_sha256':sha(out/'index.html'),
    'construction_sha256':sha(VER/'construction_stack_revue_20261003.json')})
print(json.dumps({'references':len(refs),'occurrences':len(build['occurrences']),'images':len(fig),'champs_manifest_preserves':True}))
