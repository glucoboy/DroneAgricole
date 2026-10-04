"""Infrastructure de construction FreeCAD des références du dock 20 Ah."""
from pathlib import Path
import hashlib
import FreeCAD as A
import Part

ROOT=Path(__file__).resolve().parents[4]
MEC=ROOT/'hardware/mecanique/cartographe'
EXPORT=MEC/'exports/cassette20Ah_20261002'
EXPORT.mkdir(parents=True,exist_ok=True)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def new(name,material='',values=None):
    d=A.newDocument(name);r=d.addObject('App::Part','Reference')
    r.addProperty('App::PropertyString','Etat').Etat='À valider'
    r.addProperty('App::PropertyString','RealisationCAO').RealisationCAO='Implémenté'
    r.addProperty('App::PropertyString','Materiau').Materiau=material
    s=d.addObject('Spreadsheet::Sheet','Parametres');r.addObject(s)
    for i,(k,v) in enumerate((values or {}).items(),1):
        s.set('A'+str(i),k);s.set('B'+str(i),str(v)+' mm');s.setAlias('B'+str(i),k)
    return d,r

def meta(o,k,v):
    o.addProperty('App::PropertyString',k);setattr(o,k,str(v))

def box(d,r,n,dim,pos):
    o=d.addObject('Part::Box',n);r.addObject(o)
    for k,v in zip(('Length','Width','Height'),dim):
        if isinstance(v,str): o.setExpression(k,v)
        else:setattr(o,k,v)
    for k,v in zip(('Placement.Base.x','Placement.Base.y','Placement.Base.z'),pos):
        if isinstance(v,str):o.setExpression(k,v)
        else:o.setExpression(k,str(v)+' mm')
    return o

def cyl(d,r,n,rad,length,pos,axis=(0,0,1)):
    o=d.addObject('Part::Cylinder',n);r.addObject(o);o.Radius=rad;o.Height=length
    o.Placement=A.Placement(A.Vector(*pos),A.Rotation(A.Vector(0,0,1),A.Vector(*axis)))
    return o

def fuse(d,r,n,objs):
    if len(objs)==1:return objs[0]
    o=d.addObject('Part::MultiFuse',n);r.addObject(o);o.Shapes=objs;o.Refine=True
    for p in objs:p.Visibility=False
    return o

def cut(d,r,n,base,tools):
    o=d.addObject('Part::Cut',n);r.addObject(o);o.Base=base
    o.Tool=fuse(d,r,n+'Outils',tools);o.Refine=True
    base.Visibility=False;o.Tool.Visibility=False
    return o

def save(d,r,out,kind='fabriquees'):
    d.recompute();assert out.Shape.isValid() and out.Shape.Volume>0,d.Name
    out.Label='Solide final — '+d.Name
    meta(r,'ObjetFinal',out.Name)
    p=MEC/'pieces'/kind/(d.Name+'.FCStd');d.saveAs(str(p))
    Part.export([out],str(EXPORT/(d.Name+'.step')))
    return r

def link(d,r,n,reference,pos=(0,0,0),rotation=None):
    l=d.addObject('App::Link',n);l.setLink(reference);r.addObject(l)
    l.LinkPlacement=A.Placement(A.Vector(*pos),rotation or A.Rotation())
    return l

def imported(n,filename,mpn):
    d,r=new(n);o=d.addObject('Part::Feature','FabricantSTEP');r.addObject(o)
    o.Shape=Part.read(str(filename));meta(r,'Fabricant','TE Connectivity')
    meta(r,'MPN',mpn);meta(r,'Source',Path(filename).relative_to(ROOT))
    meta(r,'SourceSHA256',sha(filename));meta(r,'Limite','STEP fabricant non modifié ; aucune qualification du drone.')
    return save(d,r,o,'commerce')
