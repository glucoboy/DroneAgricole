"""Rendu des axes BRep sauvegardés ; ne démontre aucun dégagement."""
from pathlib import Path
import sys
import FreeCAD as App
import Part
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
MEC = HERE.parents[1]
sys.path.insert(0, str(MEC / 'verification'))
from read_brep_prototype import Reader

reader = Reader(MEC)
paths = [('Initial : lignes et arcs', reader.shape('pieces/commerce/W_F16_Prototype.FCStd', 'Wire')),
         ('Essai : BSpline_K rejetée', reader.shape(HERE/'F16_copie.FCStd', 'Wire'))]
fig = plt.figure(figsize=(13, 7))
for i, (title, wire) in enumerate(paths, 1):
    ax = fig.add_subplot(1, 2, i, projection='3d')
    for edge in wire.Edges:
        pts = edge.discretize(Number=500)
        ax.plot([p.x for p in pts], [p.y for p in pts], [p.z for p in pts], color='#d24b1c', lw=2)
    ax.set_xlim(-30, 180); ax.set_ylim(-160, 30); ax.set_zlim(-130, 170)
    ax.set_box_aspect((210, 190, 300)); ax.view_init(23, -58)
    ax.set_xlabel('X mm'); ax.set_ylabel('Y mm'); ax.set_zlabel('Z mm'); ax.set_title(title)
fig.suptitle('F16 : axes uniquement, obstacles et gaine non représentés')
fig.tight_layout(); fig.savefig(HERE/'axes_3d.png', dpi=160)
