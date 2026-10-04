"""Infrastructure CAO contacts 6S20Ah. Originaux TE inchangés ; dérivés guides explicites, non approuvés fabricant."""
from pathlib import Path
import json,math
import FreeCAD as A,Part
from cad_dock20_helpers import *
SRC=MEC/'sources_fabricants/batterie20Ah_20261002'
refs={};rows=[]
for n in ['1648151','1648156','1766283','6648335']:
 src=next((SRC/('TE_'+n+'_STEP')).glob('*.stp'))
 refs[n]=imported('EQ_TE_'+n+'_Dock20',src,n+'-1')
for n in ['1648151','1648156']:
 d,r=new('EQ_TE_'+n+'_GuideTraversant_Dock20','Dérivé de vérification, non fabricant')
 d.saveAs(str(MEC/'pieces/commerce'/(d.Name+'.FCStd')))
 original=link(d,r,'OriginalTE',refs[n]);original.Visibility=False
 shape=refs[n].Shape
 wires=[w for w in shape.slice(A.Vector(0,0,1),-6.35) if w.isClosed() and 40<Part.Face(w).Area<50 and Part.Face(w).CenterOfMass.x<0 and abs(Part.Face(w).CenterOfMass.y)>30]
 assert len(wires)==1
 p=d.addObject('Part::Feature','ProfilCaviteSTEP');r.addObject(p);p.Shape=wires[0]
 meta(p,'Provenance','Section du STEP fabricant à Z=-6.35 mm ; profil existant inchangé.')
 ex=d.addObject('Part::Extrusion','ProlongementGuide');r.addObject(ex);ex.Base=p;ex.Dir=A.Vector(0,0,-20);ex.Solid=True;p.Visibility=False
 out=cut(d,r,'Resultat',original,[ex]);refs[n+'_derived']=save(d,r,out,'commerce')
 meta(r,'Limite','Prolongement de la cavité de guide jusqu’au flanc arrière selon vue arrière du plan. Hypothèse non approuvée TE ; reste ~1.99 mm3 d’interférence profil-guide. Ne certifie pas l’accouplement réel.')
 d.save()
# Vis épaulement, géométrie enveloppe dérivée du plan officiel 1650589.
d,r=new('EQ_TE_1650589_Dock20','Acier',{'TeteD':12.7,'TeteH':3.81,'EpaulementD':7.493,'EpaulementL':6.604,'FiletageD':4,'FiletageL':5.08})
q=[cyl(d,r,'Tete',6.35,3.81,(0,0,-3.81)),cyl(d,r,'Epaulement',3.7465,6.604,(0,0,0)),cyl(d,r,'FiletageEnveloppe',2,5.08,(0,0,6.604))]
meta(r,'MPN','1650589-1');meta(r,'Source','TE_1650589.pdf');meta(r,'Limite','Enveloppe suivant plan ; empreinte outil et hélice du filet omises.')
refs['1650589']=save(d,r,fuse(d,r,'Resultat',q),'commerce')
# Profil hexagonal natif pour écrous captifs.
def hexcut(d,r,name,x,y,z,af,depth):
 pts=[A.Vector(x,y+af/math.sqrt(3)*math.cos(i*math.pi/3),z+af/math.sqrt(3)*math.sin(i*math.pi/3)) for i in range(6)];pts.append(pts[0])
 p=d.addObject('Part::Feature',name+'Profil');r.addObject(p);p.Shape=Part.makePolygon(pts)
 ex=d.addObject('Part::Extrusion',name);r.addObject(ex);ex.Base=p;ex.Dir=A.Vector(depth,0,0);ex.Solid=True;p.Visibility=False;return ex
# P39 : cage imprimée avec écrous M4 captifs ; pieds sur fixations arrière existantes.
d,r=new('P39_SupportFixeContacts20Ah','PA12 SLS candidat',{'PanelX':-160,'PanelT':3.696,'CentreZ':78,'FenetreY':63,'FenetreZ':35.6})
parts=[box(d,r,'Bride',(3.696,88,40),(-160,-44,58))]
for_side=[]
for j,y in enumerate([-49,43]):
 parts.append(box(d,r,'Pied'+str(j),(46,6,3),(-160,y,39)))
 parts.append(box(d,r,'Montant'+str(j),(3.696,8,59),(-160,-49 if y<0 else 41,39)))
base=fuse(d,r,'CageFixe',parts)
tools=[box(d,r,'FenetreVerticale',(6,58,35.6),(-161,-29,60.2)),box(d,r,'FenetreHorizontale',(6,63,30.6),(-161,-31.5,62.7))]
for j,(y,z) in enumerate([(-29,62.7),(-29,93.3),(29,62.7),(29,93.3)]):tools.append(cyl(d,r,'AngleFenetre'+str(j),2.5,6,(-161,y,z),(1,0,0)))
for j,y in enumerate([-36.0045,36.0045]):
 tools.append(cyl(d,r,'TrouFlottantM4_'+str(j),2.2,6,(-161,y,78),(1,0,0)))
 tools.append(hexcut(d,r,'EcrouCaptifM4_'+str(j),-159.8,y,78,7.2,3.3))
for j,y in enumerate([-46,46]):
 tools.append(cyl(d,r,'TrouPiedM3_'+str(j),1.6,5,(-117.5,y,38)))
 co=d.addObject('Part::Cone','FraisureM3_'+str(j));r.addObject(co);co.Radius1=1.5;co.Radius2=3;co.Height=1.5;co.Placement.Base=A.Vector(-117.5,y,40.5);tools.append(co)
for j,y in enumerate([-45,45]):
 tools.append(cyl(d,r,'FixationProtectionFixe'+str(j),1.6,6,(-161,y,84),(1,0,0)))
 tools.append(hexcut(d,r,'EcrouProtectionFixe'+str(j),-158.9,y,84,5.7,2.6))
refs['P39']=save(d,r,cut(d,r,'Resultat',base,tools))
meta(r,'Interface','Deux axes M3 x=-117.5 y=±46, dessus P35 z=39. Deux écrous M4 ISO4032 captifs et vis TE1650589, bride avant fixe x=-149.7.')
d.save()
# P40 : cage mobile, réutilise perçages latéraux disponibles du P31 x=-100,z=47.
d,r=new('P40_SupportMobileContacts20Ah','PA12 SLS candidat',{'PanelX':-130.65,'PanelT':3,'CentreZ':78,'FenetreY':63,'FenetreZ':35.6})
parts=[box(d,r,'Bride',(3,88,40),(-130.65,-44,58))]
for j,y in enumerate([-37,29]):
 parts.append(box(d,r,'Bras'+str(j),(29.65,8,3),(-130.65,y,45)))
 parts.append(box(d,r,'Montant'+str(j),(3,8,53),(-130.65,y,45)))
base=fuse(d,r,'CageMobile',parts)
tools=[box(d,r,'FenetreVerticale',(5,58,35.6),(-131.65,-29,60.2)),box(d,r,'FenetreHorizontale',(5,63,30.6),(-131.65,-31.5,62.7))]
for j,(y,z) in enumerate([(-29,62.7),(-29,93.3),(29,62.7),(29,93.3)]):tools.append(cyl(d,r,'AngleFenetre'+str(j),2.5,5,(-131.65,y,z),(1,0,0)))
for j,y in enumerate([-36.0045,36.0045]):tools.append(cyl(d,r,'TrouM4_'+str(j),2.2,5,(-131.65,y,78),(1,0,0)))
for j,y in enumerate([-33,33]):tools.append(cyl(d,r,'TrouFondM3_'+str(j),1.6,5,(-104,y,44)))
refs['P40']=save(d,r,cut(d,r,'Resultat',base,tools))
meta(r,'Interface','Axes partagés fond arrière x=-104,y=±33 ; bras z45..48 posés sur bossages bas P31. Vis M3x14 dessus48, écrous déplacés sousG10z34.6..37. Bride socket x=-137..-130.65, panneau arrière x=-130.65..-127.65.')
d.save()
# Sous-ensemble de contact, liens vers originaux et dérivés comparables.
d=A.newDocument('SA02_Contacts20Ah');root=d.addObject('App::Part','Ensemble')
root.addProperty('App::PropertyString','Etat').Etat='À valider'
root.addProperty('App::PropertyString','Limite').Limite='A=12.7 mm selon 114-13206. Original STEP :335mm3 d’interférence guides ; dérivés:1.99mm3 résiduel. Interfaces internes STEP simplifiées. Contrôle physique indispensable.'
rotpin=A.Rotation(A.Vector(0,1,0),90);rotsocket=A.Rotation(A.Vector(0,1,0),-90)
d.saveAs(str(MEC/'sous_assemblages/SA02_Contacts20Ah.FCStd'))
placements=[]
def occ(name,ref,pos=(0,0,0),rot=None,moving=False):
 l=link(d,root,name,ref,pos,rot);meta(l,'Mobile','oui' if moving else 'non')
 placements.append({'objet':name,'reference':ref.Document.Name,'mobile':moving,'placement_matrice':list(l.LinkPlacement.toMatrix().A)});return l
p=occ('HousingPin',refs['1648151'],(-137,0,78),rotpin)
s=occ('HousingSocket',refs['1648156'],(-149.7,0,78),rotsocket,True)
for k,z in [('39Plus',69.745),('40Moins',86.255)]:
 # Application114-13206 : pinA=12.95 depuisbrideavant−12.7 =>tip+.254 ; socketprotégéderrièreentrée−2.54.
 occ('ContactPin'+k,refs['1766283'],(-136.746,21.6535,z),rotpin)
 occ('ContactSocket'+k,refs['6648335'],(-147.16,21.6535,z),rotsocket,True)
occ('SupportFixe',refs['P39']);occ('SupportMobile',refs['P40'],moving=True)
for j,y in enumerate([-36.0045,36.0045]):occ('VisFlottante'+str(j),refs['1650589'],(-149.7,y,78),A.Rotation(A.Vector(0,0,1),A.Vector(-1,0,0)))
d.recompute();d.saveAs(str(MEC/'sous_assemblages/SA02_Contacts20Ah.FCStd'))
raw=p.Shape.common(s.Shape).Volume
pd=refs['1648151_derived'].Shape.copy();pd.Placement=p.LinkPlacement
sd=refs['1648156_derived'].Shape.copy();sd.Placement=s.LinkPlacement
proof={'schema_version':1,'date':'2026-10-02','etat':'Implémenté','qualification':'À valider','montage':placements,'A_brides_avant_mm':12.7,'origine_pin_mm':[-137,0,78],'origine_socket_mm':[-149.7,0,78],'interference_STEP_brut_guides_mm3':raw,'interference_derive_guides_mm3':pd.common(sd).Volume,'limites':['Originals TE non modifiés. Dérivés de contrôle prolongeant seulement cavitéguideexistante, non approuvés fabricant.','Contacts et clips internes représentés par interfaces simplifiées : volume brut recouvrant les contacts ne vaut pas preuve de blocage.','Course des contacts, tolérance de capture, montage au couple et accouplement physique à valider.','Protection touchsafe et faisceau hors de ce sous-ensemble.']}
for key,ref in refs.items():
 out=ref.Document.getObject(ref.ObjetFinal);proof.setdefault('references',[]).append({'reference':ref.Document.Name,'file':str(Path(ref.Document.FileName).relative_to(MEC)).replace('\\','/'),'source_objet':'Reference','valid':out.Shape.isValid(),'solids':len(out.Shape.Solids),'volume_mm3':out.Shape.Volume,'sha256':sha(ref.Document.FileName)})
(MEC/'verification/construction_contacts20Ah_20261002.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
bom={'schema_version':1,'etat':'À valider','pieces':[{'reference':refs[x].Document.Name,'MPN':x+'-1','quantite':q} for x,q in [('1648151',1),('1648156',1),('1766283',2),('6648335',2),('1650589',2)]],'fabriquees':[{'reference':refs[x].Document.Name,'quantite':1,'materiau':'PA12 SLS','qualification':'À valider'} for x in ['P39','P40']],'visserie':[{'designation':'ISO4032 M4 acier 8, écrou captif supportfixe','quantite':2},{'designation':'ISO4762 M4×20 acier8.8, fixation logementmobile','quantite':2},{'designation':'ISO7089 M4 acier200HV','quantite':2},{'designation':'ISO10511 M4 acier8 écroufreiné','quantite':2},{'designation':'ISO4762 M3×14 acier8.8, remplace 2 vis fond arrière, écrousISO4032M3déplacés sousG10 + Loctite243','quantite':2},{'designation':'DIN7991 M3×16 acier8.8 fraisée, remplace 2 vis P35, tête affleurante z42','quantite':2}], 'bornes':{'39':'PLUS z69.745 y21.6535','40':'MOINS z86.255 y21.6535'},'contacts_M5':{'filetage':'M5×0.8 interne','couple_max_Nm':2.9,'cosse':'Adaptée à section réellement livrée, harnaisroot','vis':'ISO4762M5×8 + ISO7089M5, 4 ensembles, profondeur à vérifier surborne livrée'}}
(MEC/'verification/bom_contacts20Ah_20261002.json').write_text(json.dumps(bom,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'raw':raw,'derived':proof['interference_derive_guides_mm3'],'count':len(refs)},indent=2))





# Standard hardware sources are nominal envelopes; threads omitted.
def bolt(name,diam,length,headD,headH,countersunk=False):
 dd,rr=new(name,'Acier8.8',{'Diametre':diam,'Longueur':length,'TeteD':headD,'TeteH':headH})
 if countersunk:
  hd=dd.addObject('Part::Cone','TeteFraisee');rr.addObject(hd);hd.Radius1=headD/2;hd.Radius2=diam/2;hd.Height=headH
  sh=cyl(dd,rr,'Tige',diam/2,length-headH,(0,0,headH))
 else:hd=cyl(dd,rr,'Tete',headD/2,headH,(0,0,-headH));sh=cyl(dd,rr,'Tige',diam/2,length,(0,0,0))
 meta(rr,'Limite','Enveloppe nominale de montage, filet et empreinte outil omis ; dimensions fournisseur à contrôler.')
 return save(dd,rr,fuse(dd,rr,'Resultat',[hd,sh]),'commerce')
def washer(name,di,do,h):
 dd,rr=new(name,'Acier200HV',{'Interieur':di,'Exterieur':do,'Epaisseur':h})
 return save(dd,rr,cut(dd,rr,'Resultat',cyl(dd,rr,'Rondelle',do/2,h,(0,0,0)),[cyl(dd,rr,'Trou',di/2,h+1,(0,0,-.5))]),'commerce')
def nut(name,dia,af,h):
 dd,rr=new(name,'Acierclasse8',{'Diametre':dia,'Surplats':af,'Hauteur':h})
 pts=[A.Vector(af/math.sqrt(3)*math.cos(k*math.pi/3),af/math.sqrt(3)*math.sin(k*math.pi/3),0)for k in range(6)];pts.append(pts[0])
 pp=dd.addObject('Part::Feature','ProfilHexagonal');rr.addObject(pp);pp.Shape=Part.makePolygon(pts)
 ee=dd.addObject('Part::Extrusion','Hexagone');rr.addObject(ee);ee.Base=pp;ee.Dir=A.Vector(0,0,h);ee.Solid=True;pp.Visibility=False
 return save(dd,rr,cut(dd,rr,'Resultat',ee,[cyl(dd,rr,'Trou',dia/2,h+1,(0,0,-.5))]),'commerce')
refs['m4x20']=bolt('EQ_ISO4762_M4x20_Contacts20Ah',4,20,7,4)
refs['m3x14']=bolt('EQ_ISO4762_M3x14_Contacts20Ah',3,14,5.5,3)
refs['m3x16cs']=bolt('EQ_DIN7991_M3x16_Contacts20Ah',3,16,6,1.5,True)
refs['wm4']=washer('EQ_ISO7089_M4_Contacts20Ah',4.3,9,.8)
refs['wm5large']=washer('EQ_DIN9021_M5_Contacts20Ah',5.3,15,1.2)
refs['nm4']=nut('EQ_ISO4032_M4_Contacts20Ah',4,7,3.2)
refs['nm4nyl']=nut('EQ_ISO10511_M4_Contacts20Ah',4,7,5)
refs['nm3']=nut('EQ_ISO4032_M3_Contacts20Ah',3,5.5,2.4)
# ISO10511 low-form M4 height5 nominal includes nylon zone; not equivalentISO4032.
for j,y in enumerate([-36.0045,36.0045]):
 occ('EcrouFlottant'+str(j),refs['nm4'],(-159.75,y,78),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)).multiply(A.Rotation(A.Vector(0,0,1),30)))
 occ('VisLogementMobile'+str(j),refs['m4x20'],(-138.2,y,78),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)),True)
 occ('RondelleLargeMobile'+str(j),refs['wm5large'],(-138.2,y,78),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)),True)
 occ('RondelleM4Mobile'+str(j),refs['wm4'],(-127.65,y,78),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)),True)
 occ('EcrouM4Mobile'+str(j),refs['nm4nyl'],(-126.85,y,78),A.Rotation(A.Vector(0,0,1),A.Vector(1,0,0)),True)
for j,y in enumerate([-33,33]):
 occ('VisFondMobile'+str(j),refs['m3x14'],(-104,y,48),A.Rotation(A.Vector(0,0,1),A.Vector(0,0,-1)),True)
 occ('EcrouSousFondMobile'+str(j),refs['nm3'],(-104,y,34.6),None,True)
for j,y in enumerate([-46,46]):occ('VisFraiseePiedFixe'+str(j),refs['m3x16cs'],(-117.5,y,42),A.Rotation(A.Vector(0,0,1),A.Vector(0,0,-1)))
d.recompute();d.save()
proof['montage']=placements
proof['visserie_limites']=['M4mobile: rondellelargeDIN9021M5Ø15 devant bride(TE recommande têteØ12.7min). VisM4×20 grip1.2+6.35+3+.8+nyloc5=16.35 mm ; longueur20 mm, dépassement3.65 mm au-delàécrou.','P40M3×14 sansrondelle, écrouISO4032M3h2.4 sousG10z34.6..37 avec freinfilet243, pasécrounyloc débordant sousplate33.','P39visDIN7991M3×16flushz42, écrousinférieursP35conservés, courseinterfaceàcontrôlerfull.']
proof['references']=[]
for ref in refs.values():
 out=ref.Document.getObject(ref.ObjetFinal);proof['references'].append({'reference':ref.Document.Name,'file':str(Path(ref.Document.FileName).relative_to(MEC)).replace('\\','/'),'source_objet':'Reference','valid':out.Shape.isValid(),'solids':len(out.Shape.Solids),'volume_mm3':out.Shape.Volume,'sha256':sha(ref.Document.FileName)})
(MEC/'verification/construction_contacts20Ah_20261002.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')


# Pose articulée paramétrique pour course +X.
par=d.addObject('Spreadsheet::Sheet','Parametres');root.addObject(par);par.set('A1','ExtractionX');par.set('B1','0 mm');par.setAlias('B1','ExtractionX')
for ll in d.Objects:
 if ll.TypeId=='App::Link' and hasattr(ll,'Mobile') and ll.Mobile=='oui':ll.setExpression('LinkPlacement.Base.x',str(ll.LinkPlacement.Base.x)+' mm + Parametres.ExtractionX')
d.recompute();d.save()
bom['visserie']=[{'designation':'ISO4032 M4 acier8, écrou captif P39','quantite':2,'reference_native':refs['nm4'].Document.Name},{'designation':'ISO4762 M4×20 acier8.8, housingmobile','quantite':2,'reference_native':refs['m4x20'].Document.Name},{'designation':'DIN9021 M5 acier200HV Ø15×1.2, rondellelargeDEVANThousingmobile','quantite':2,'reference_native':refs['wm5large'].Document.Name},{'designation':'ISO7089 M4 acier200HV Ø9×0.8, rondellearrière','quantite':2,'reference_native':refs['wm4'].Document.Name},{'designation':'ISO10511 M4 acier8 écroufreiné h5','quantite':2,'reference_native':refs['nm4nyl'].Document.Name},{'designation':'ISO4762 M3×14 acier8.8, remplace2visfondcassetteAR','quantite':2,'reference_native':refs['m3x14'].Document.Name},{'designation':'ISO4032 M3 acier8 h2.4, déplace2écrouscaptifsfondARsousG10 z34.6..37, freinfiletLoctite243','quantite':2,'reference_native':refs['nm3'].Document.Name,'substitution':'2écrouscaptifsbasAR deP31 à retirer'},{'designation':'DIN7991 M3×16 acier8.8 têteØ6fraisée90°, remplace2visP35, têteaffleurante42','quantite':2,'reference_native':refs['m3x16cs'].Document.Name},{'designation':'Loctite243 Henkel 1335884 50mL, freinfiletageM3fond etM5seloncompatibilitébornesfabricantàvalider','quantite':1,'unite':'flaconconsommable'}]
bom['assemblage']={'file':'sous_assemblages/SA02_Contacts20Ah.FCStd','root':'Ensemble','course':'Parametres.ExtractionX, 0 mm verrouillé, +X extraction','limites':'Géométrie STEPguides brute334.917mm3 ; prolongementguide natif1.9888mm3résiduel. Accouplementphysiqueàvalider.'}
(MEC/'verification/bom_contacts20Ah_20261002.json').write_text(json.dumps(bom,ensure_ascii=False,indent=2),encoding='utf-8')
proof['assemblage_sha256']=sha(d.FileName)
(MEC/'verification/construction_contacts20Ah_20261002.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
