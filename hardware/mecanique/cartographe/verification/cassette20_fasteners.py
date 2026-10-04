"""Infrastructure native des fixations ISO du dock ; filets simplifiés."""
import FreeCAD as A,Part,math
from cad_dock20_helpers import new,cyl,fuse,cut,save,meta

def refs():
 out={}
 for dia,length in [(3,8),(3,10),(3,12),(3,16),(4,20)]:
  n=f'EQ_ISO4762_M{dia}x{length}_Dock';d,r=new(n,'Acier classe8.8 zingué')
  meta(r,'Specification',f'ISO4762 M{dia}×{length}, classe8.8 ; filetage simplifié')
  s=cyl(d,r,'Tige',dia/2,length,(0,0,0))
  h=cyl(d,r,'Tete',2.75 if dia==3 else 3.5,dia,(0,0,-dia))
  out[n]=save(d,r,fuse(d,r,'Resultat',[s,h]),'commerce')
 for dia,af,h in [(3,5.5,2.4),(4,7,3.2),(5,8,4)]:
  std='ISO4032'if dia!=5 else'DIN934'
  n=f'EQ_{std}_M{dia}_Dock';d,r=new(n,'Acier classe8 zingué')
  meta(r,'Specification',f'{std} M{dia}, clé{af}, épaisseur{h} ; filetage simplifié')
  p=d.addObject('Part::Prism','Hexagone');r.addObject(p);p.Polygon=6;p.Circumradius=af/math.sqrt(3);p.Height=h
  hole=cyl(d,r,'Filetage',dia/2,h+2,(0,0,-1));out[n]=save(d,r,cut(d,r,'Resultat',p,[hole]),'commerce')
 for dia,od,h in [(3,7,0.5),(4,9,0.8),(5,10,1)]:
  n=f'EQ_ISO7089_M{dia}_Dock';d,r=new(n,'Acier zingué')
  p=cyl(d,r,'Rondelle',od/2,h,(0,0,0));hole=cyl(d,r,'Trou',dia/2+0.2,h+2,(0,0,-1));out[n]=save(d,r,cut(d,r,'Resultat',p,[hole]),'commerce')
 n='EQ_ISO7046_2_M25x5_Dock';d,r=new(n,'Acier classe4.8 zingué')
 head=d.addObject('Part::Cone','TeteFraisee');r.addObject(head);head.Radius1=2.35;head.Radius2=0.85;head.Height=1.5
 stem=cyl(d,r,'Tige',1.25,3.9,(0,0,1.1));out[n]=save(d,r,fuse(d,r,'Resultat',[head,stem]),'commerce')
 n='EQ_ISO7046_2_M3x8_Dock';d,r=new(n,'Acier classe4.8 zingué')
 head=d.addObject('Part::Cone','TeteFraisee');r.addObject(head);head.Radius1=2.8;head.Radius2=1.15;head.Height=1.65
 stem=cyl(d,r,'Tige',1.5,6.7,(0,0,1.3));out[n]=save(d,r,fuse(d,r,'Resultat',[head,stem]),'commerce')
 n='EQ_ISO4032_M25_Dock';d,r=new(n,'Acier classe8 zingué')
 p=d.addObject('Part::Prism','Hexagone');r.addObject(p);p.Polygon=6;p.Circumradius=5/math.sqrt(3);p.Height=2
 hole=cyl(d,r,'Filetage',1.25,4.2,(0,0,-1));out[n]=save(d,r,cut(d,r,'Resultat',p,[hole]),'commerce')
 return out

def occurrences():
 result=[]
 def put(name,ref,mobile,p,axis=(0,0,1)):
  result.append((name,ref,mobile,A.Placement(A.Vector(*p),A.Rotation(A.Vector(0,0,1),A.Vector(*axis)))))
 for i,(x,y)in enumerate([(x,y)for x in[-40,40]for y in[-51.5,51.5]]):
  put('VisRail'+str(i),'EQ_ISO4762_M3x12_Dock',False,(x,y,31))
  put('RondelleRail'+str(i),'EQ_ISO7089_M3_Dock',False,(x,y,36.5))
  put('EcrouRail'+str(i),'EQ_ISO4032_M3_Dock',False,(x,y,37))
 for i,(sx,sy)in enumerate([(x,y)for x in[-1,1]for y in[-1,1]]):
  put('VisFond'+str(i),'EQ_ISO4762_M3x8_Dock',True,(sx*104,sy*33,37))
  put('EcrouFond'+str(i),'EQ_ISO4032_M3_Dock',True,(sx*104,sy*33,42.4))
  put('VisCap'+str(i),'EQ_ISO7046_2_M3x8_Dock',True,(sx*105,sy*36,102),(0,0,-1))
  put('EcrouCap'+str(i),'EQ_ISO4032_M3_Dock',True,(sx*105,sy*36,94))
 for i,y in enumerate([33,-36]):
  put('VisPoignee'+str(i),'EQ_ISO4762_M3x12_Dock',True,(112.5,y,55),(-1,0,0))
  put('EcrouPoignee'+str(i),'EQ_ISO4032_M3_Dock',True,(101,y,55),(1,0,0))
 for i,x in enumerate([101.5,131.5]):
  put('VisSupportLoquet'+str(i),'EQ_ISO4762_M3x16_Dock',False,(x,49.5,45),(0,0,-1))
  put('EcrouSupportLoquet'+str(i),'EQ_ISO4032_M3_Dock',False,(x,49.5,30.6))
 for i,z in enumerate([55.3,80.7]):
  put('VisLoquet'+str(i),'EQ_ISO4762_M4x20_Dock',False,(116.85,50.5,z),(0,1,0))
  put('RondelleLoquet'+str(i),'EQ_ISO7089_M4_Dock',False,(116.85,63.5,z),(0,1,0))
  put('EcrouLoquet'+str(i),'EQ_ISO4032_M4_Dock',False,(116.85,64.3,z),(0,1,0))
 put('EcrouGache','EQ_DIN934_M5_Dock',True,(116.85,42.1,68),(0,-1,0))
 for i,y in enumerate([-46,46]):
  put('VisSupportButee'+str(i),'EQ_ISO4762_M3x12_Dock',False,(-117.5,y,39),(0,0,-1))
  put('EcrouSupportButee'+str(i),'EQ_ISO4032_M3_Dock',False,(-117.5,y,30.6))
 for i,y in enumerate([-25,25]):
  put('EcrouReglage'+str(i),'EQ_ISO4032_M4_Dock',False,(-111,y,35.5),(1,0,0))
  put('ContreEcrouReglage'+str(i),'EQ_ISO4032_M4_Dock',False,(-118.2,y,35.5),(1,0,0))
 for i,y in enumerate([-33,33]):
  put('VisBarreButee'+str(i),'EQ_ISO7046_2_M25x5_Dock',True,(-98,y,39),(0,0,-1))
  put('EcrouBarreButee'+str(i),'EQ_ISO4032_M25_Dock',True,(-98,y,34.2))
 return result




