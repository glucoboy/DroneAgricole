"""Vues orthographiques comparables de A et de l'implantation par faces."""
from pathlib import Path

from essayer_faces import COPY, HERE, Scene, load, require, sha, write
from controles_vues import BACKGROUND, NAVY, Patch, dimension_scale, footer, heading, np, plt, projection, render, save, set_panel

OUTPUT = HERE.parent / "exports/vues"
CROP = ((-118,118),(-153,110),(28,178))
COLORS = {"dessus":"#cd6724","entre":"#278071","dessous":"#3976bf",
          "changed":"#b0447b","fixture":"#578043","plug":"#8f662d","structure":"#7b8ea1"}
Z_P66=85
Z_PORTEUSE=130.052


def type_of(item):
    if item.name.startswith("Gabarit"):
        return "plug"
    if item.name in {"SupportSecurite","ClipColonneF12","RetenueP85F25","PinceDepartF41","BandeDepartF41"}:
        return "fixture"
    if item.role in {"cable","gaine"} or item.name.startswith(("ConnecteurF16","ConnecteurM8Camera")):
        return "cable"
    return "structure"


def tessellate(scene, cache, hashes):
    output=[]
    for item in scene.items.values():
        if any(getattr(item.shape.BoundBox, axis+"Min")>hi or getattr(item.shape.BoundBox,axis+"Max")<lo
               for axis,(lo,hi) in zip("XYZ",CROP)):
            continue
        role=type_of(item)
        key=(hashes[item.row["source"]],item.row["objet_source"],tuple(item.pose.toMatrix().A),role)
        if key not in cache:
            vs,ts=item.shape.tessellate(.35 if role!="structure" else 2)
            require(ts,"Maillage vide "+item.name)
            cache[key]=np.asarray([(v.x,v.y,v.z) for v in vs])[np.asarray(ts)]
        output.append((item.name,role,cache[key]))
    return output


def palette(items,mode):
    result=[]
    for name,role,tri in items:
        if role=="cable":
            z=tri[:,:,2].mean(axis=1)
            masks={"dessous":z<Z_P66,"entre":(z>=Z_P66)&(z<Z_PORTEUSE),"dessus":z>=Z_PORTEUSE}
            for key,mask in masks.items():
                if np.any(mask):
                    result.append((name,"solid",COLORS[key],COLORS[key],tri[mask]))
            continue
        if mode=="cables" or (mode=="accessories" and role=="structure"):
            continue
        c=COLORS[role]
        state="structure" if role=="structure" else "solid"
        result.append((name,state,c,c,tri))
    return result


def figure(path,sources,specs,subtitle):
    fig, axs=plt.subplots(3,2,figsize=(13,14),facecolor=BACKGROUND)
    fig.subplots_adjust(left=.045,right=.955,top=.815,bottom=.125,wspace=.09,hspace=.27)
    heading(fig,"Cartographe · implantation par faces",subtitle)
    for axes,(view_label,orient,mode) in zip(axs,specs):
        view=projection(*orient)
        for ax,source,label in zip(axes,sources,("Référence A","Copie par faces")):
            set_panel(ax,view_label+"  ·  "+label)
            render(ax,palette(source,mode),view,crop=CROP)
            dimension_scale(ax,50)
    keys=[("dessus","Au-dessus de la porteuse"),("entre","Entre niveaux"),
          ("dessous","Sous le plan de P66"),("fixture","Retenue représentée"),("plug","Gabarit de fiche")]
    handles=[Patch(color=COLORS[k],label=label) for k,label in keys]
    fig.legend(handles=handles,loc="lower center",bbox_to_anchor=(.5,.064),ncol=3,frameon=False,fontsize=10)
    footer(fig,"Échelle identique dans chaque paire. Les gabarits sont des réservations. Les axes de construction sont masqués.")
    save(fig,path)


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    origin=Path(load(COPY/"experiment.json")["source_root"])
    scenes=[Scene(origin),Scene(COPY)]
    hashes=[s.hashes() for s in scenes]
    require(load(HERE/"installation.json")["native_sha256"]==hashes[1],"Copie non identifiée")
    cache={}
    meshes=[tessellate(s,cache,h) for s,h in zip(scenes,hashes)]
    specs=[
        ("01_dessus_dessous_profil.png",
          [("Vue supérieure",(-90,90),"context"),("Vue inférieure",(-90,-90),"context"),
           ("Vue latérale sud",(-90,0),"context")],
          "Vues orthographiques de dessus, dessous et de profil"),
        ("02_baie_cables_retenues.png",
          [("Baie transparente",(-65,38),"context"),("Câbles seuls",(-65,38),"cables"),
           ("Câbles, prises et retenues",(-65,38),"accessories")],
          "Même angle pour les vues de la baie, avec et sans les volumes d’implantation"),
    ]
    for name,panels,subtitle in specs:
        figure(OUTPUT/name,meshes,panels,subtitle)
        print(name,flush=True)
    require([s.hashes() for s in scenes]==hashes,"Un natif a changé")
    write(OUTPUT/"index_vues.json",{"source_sha256":hashes[0],"candidate_sha256":hashes[1],
          "z_p66_mm":Z_P66,"z_porteuse_mm":Z_PORTEUSE,"crop_mm":CROP,
          "exports":{name:sha(OUTPUT/name) for name,_,_ in specs}})


if __name__=="__main__":
    main()

