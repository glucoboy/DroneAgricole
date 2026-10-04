"""Galerie des captures natives FreeCAD ; aucune reconstruction de géométrie."""
from pathlib import Path
import hashlib,html,json,zipfile
from PIL import Image, ImageDraw, ImageFont, ImageChops

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
OUT=MEC/'exports/rendus_freecad_sous_assemblages_20261003'
PROOF=MEC/'verification/rendus_sous_assemblages_freecad_20261003.json'
data=json.loads(PROOF.read_text(encoding='utf-8'))
assert data['finalisation_correcte'] and data['natifs_preserves']
assert data['nombre_sous_assemblages']==23

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

qa=[]
for record in data['sous_assemblages']:
    for image in record['images']:
        path=ROOT/image['fichier'];assert sha(path)==image['sha256']
        with Image.open(path) as im:
            assert im.size==(1800,1200)
            assert im.info.get('Software','').startswith('FreeCAD'),im.info
            bbox=ImageChops.difference(im.convert('RGB'),Image.new('RGB',im.size,'white')).getbbox()
            assert bbox is not None and bbox[2]-bbox[0]>60 and bbox[3]-bbox[1]>60,path
            qa.append({'fichier':image['fichier'],'dimensions':list(im.size),'bbox_pixels_non_blancs':list(bbox),
                       'logiciel':im.info['Software'],'capture_non_vide':True})

fontdir=Path('C:/Windows/Fonts')
font=ImageFont.truetype(str(fontdir/'arial.ttf'),26)
small=ImageFont.truetype(str(fontdir/'arial.ttf'),20)
large=ImageFont.truetype(str(fontdir/'arialbd.ttf'),40)
art=[]
for num,records,title in [(1,data['sous_assemblages'][:12],'Sous-assemblages courants et candidats'),
                          (2,data['sous_assemblages'][12:],'Sous-assemblages historiques et alternatives')]:
    canvas=Image.new('RGB',(2400,1780),'white');draw=ImageDraw.Draw(canvas)
    draw.text((55,30),title,font=large,fill='#203247')
    draw.text((55,90),'Captures directes de FreeCAD — vues isométriques',font=small,fill='#526170')
    for i,r in enumerate(records):
        x=30+(i%4)*590;y=155+(i//4)*510
        iso=next(j for j in r['images'] if j['vue']=='isometrique')
        with Image.open(ROOT/iso['fichier']) as im:
            im.thumbnail((570,390));canvas.paste(im,(x+(570-im.width)//2,y))
        draw.text((x+10,y+405),r['titre'],font=font,fill='#203247')
        draw.text((x+10,y+445),r['etat'],font=small,fill='#806039')
    draw.text((55,1720),'Toutes les vues de dessous et les images pleine résolution sont disponibles dans la galerie.',font=small,fill='#526170')
    name=f'{num:02d}_planche_freecad.png';canvas.save(OUT/name)
    art.append({'fichier':str((OUT/name).relative_to(ROOT)).replace('\\','/'),'sha256':sha(OUT/name)})

articles=[]
for r in data['sous_assemblages']:
    pics=[]
    for im in r['images']:
        name=Path(im['fichier']).name
        pics.append(f'<figure><a href="{name}"><img src="{name}" alt="{html.escape(r["titre"])} — {im["vue"]}"></a>'
                    f'<figcaption>{"Vue isométrique" if im["vue"]=="isometrique" else "Vue de dessous"}</figcaption></figure>')
    articles.append(f'<article><h2>{html.escape(r["titre"])}</h2><p class="etat">{html.escape(r["etat"])}</p>'
                    '<div class="vues">'+''.join(pics)+'</div><p>'+html.escape(r['legende'])+'</p>'
                    f'<p class="source">{r["id"]}.FCStd</p></article>')
page='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rendus FreeCAD — sous-assemblages du cartographe</title><style>
body{font:16px system-ui,sans-serif;background:#f5f7f9;color:#203247;max-width:1500px;margin:30px auto;padding:0 18px}
article{background:white;border:1px solid #d7dee5;border-radius:12px;margin:24px 0;padding:22px}h2{margin:0;font-size:24px}
.vues{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0}img{width:100%;display:block}figcaption{color:#526170;text-align:center}
.etat{color:#806039}.source{font-size:12px;color:#526170}a{color:#235e86}@media(max-width:700px){.vues{grid-template-columns:1fr}}
</style><h1>Les 23 sous-assemblages — rendus directs de FreeCAD</h1>
<p>46 captures natives : vue isométrique et vue de dessous pour chaque sous-assemblage. Cliquez sur une image pour ouvrir sa pleine résolution.</p>
<p><a href="01_planche_freecad.png">Planche des modèles courants et candidats</a> · <a href="02_planche_freecad.png">Planche historique et alternatives</a></p>
<p>Les versions courantes, candidates, alternatives et historiques sont signalées. Ces vues ne qualifient pas le montage ou le câblage.</p>'''+''.join(articles)+'</html>'
(OUT/'index.html').write_text(page,encoding='utf-8')
art.append({'fichier':str((OUT/'index.html').relative_to(ROOT)).replace('\\','/'),'sha256':sha(OUT/'index.html')})
zip_path=OUT/'rendus_freecad_sous_assemblages.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for file in sorted(OUT.iterdir()):
        if file.suffix in ['.png','.html']:z.write(file,file.name)
art.append({'fichier':str(zip_path.relative_to(ROOT)).replace('\\','/'),'sha256':sha(zip_path)})
result={'date':'2026-10-03','moteur_images':'FreeCAD / Coin3D','captures_natives':len(qa),
        'captures_valides':qa,'galerie_et_planches':art,'preuve_native_sha256':sha(PROOF),
        'script_sha256':sha(__file__),'nature':'Mise en page et contrôle des captures natives ; images sources inchangées'}
(MEC/'verification/galerie_rendus_freecad_20261003.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'captures_FreeCAD':len(qa),'galerie':str(OUT/'index.html'),'zip':str(zip_path)}))
