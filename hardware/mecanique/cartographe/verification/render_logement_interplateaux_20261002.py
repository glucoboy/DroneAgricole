"""Coupe de principe des hauteurs mesurées, sans modification de CAO.

Python FreeCAD avec matplotlib. Hypothèses de supports/jeu, pas plan fabricant.
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'hardware/mecanique/cartographe/verification/logement_interplateaux_20261002.png'
fig,axes=plt.subplots(1,3,figsize=(12.5,5.7),sharex=True,sharey=True)
fig.patch.set_facecolor('#f7f8fa')
scenarios=[('État actuel',0,None),('20 Ah — rehausse candidate +20 mm',20,60),
           ('16 Ah — rehausse candidate +30 mm',30,67)]
for ax,(title,raise_mm,height) in zip(axes,scenarios):
    roof=83+raise_mm
    ax.set_facecolor('#f7f8fa')
    # Vue Y/Z : plateaux de largeur 160/120 et colonnes OD5 à Y±52.
    ax.add_patch(Rectangle((-80,31),160,2,facecolor='#59636f'))
    ax.add_patch(Rectangle((-60,roof),120,2,facecolor='#59636f'))
    for y in (-52,52):
        ax.add_patch(Rectangle((y-2.5,33),5,roof-33,facecolor='#a9afb6'))
    if height is None:
        ax.text(0,58,'Volume occupé\npar le Pixhawk actuel',ha='center',va='center',
                fontsize=11,color='#a34238')
        ax.text(0,94,'Packs nus : 58 / 65 mm\n50 mm disponibles',ha='center',fontsize=10)
    else:
        ax.add_patch(Rectangle((-42,33),84,4,facecolor='#d98032'))
        ax.add_patch(Rectangle((-42,37),84,1,facecolor='#6b9d62'))
        ax.add_patch(Rectangle((-42,38),84,2,facecolor='#9cbaa2'))
        ax.add_patch(Rectangle((-39,40),78,height,facecolor='#3569d0'))
        ax.text(0,40+height/2,f'Pack max.\n78 × {height} mm',ha='center',va='center',
                color='white',fontsize=11)
        gap=roof-(40+height)
        ax.annotate(f'Jeu haut {gap} mm',xy=(0,(roof+40+height)/2),xytext=(0,123),
                    ha='center',fontsize=9,arrowprops={'arrowstyle':'->','color':'#48545e'})
        ax.text(0,23,'Appuis/protection : 4 + 1 + 2 mm',ha='center',fontsize=9)
    ax.annotate('',xy=(72,roof),xytext=(72,33),arrowprops={'arrowstyle':'<->','color':'#48545e'})
    ax.text(75,(roof+33)/2,f'{roof-33} mm',va='center',rotation=90,fontsize=10)
    ax.set_title(title,fontsize=11,pad=14)
    ax.set_xlim(-90,90);ax.set_ylim(19,134);ax.set_aspect('equal')
    ax.set_xticks([-52,0,52]);ax.set_xlabel('Y (mm)')
    ax.set_yticks([33,83,103,113]);ax.grid(axis='y',alpha=0.15)
    ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('Z (mm), repère du drone')
fig.suptitle('Batterie entre les deux plateaux supérieurs — coupe Y/Z de principe',fontsize=15,y=0.97)
fig.text(0.5,0.05,'Scénarios candidats après déplacement de l’avionique ; pack horizontal, grand axe X.\n'
         'Tolérances 20 Ah hypothétiques. Accès, verrou, hélices et résistance ne sont pas qualifiés.',
         ha='center',fontsize=10,color='#46515c')
fig.subplots_adjust(left=0.06,right=0.97,bottom=0.19,top=0.86,wspace=0.15)
fig.savefig(OUT,dpi=160,facecolor=fig.get_facecolor())
plt.close(fig)
print(OUT)
