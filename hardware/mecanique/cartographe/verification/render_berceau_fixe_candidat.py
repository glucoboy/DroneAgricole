"""Aperçu des maillages dérivés des natifs FreeCAD ; aucune CAO modifiée.

Exécuter après build_berceau_fixe_candidat.py avec le Python FreeCAD.
Le maillage temporaire n'est pas une source de conception.
"""
from pathlib import Path
import json
import hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
MEC = ROOT / 'hardware/mecanique/cartographe'
mesh = ROOT / '.runtime/batterie_reprise_20261002/maillages.json'
data = json.loads(mesh.read_text(encoding='utf-8'))
labels = {'Berceau': 'Berceau fixe ajouré', 'Batterie': 'Pack 6S',
          'Capot': 'Capot captif', 'LoquetReservation': 'Réservation du loquet',
          'ProtectionG10': 'Protection inférieure'}

for ah in (16, 20):
    fig = plt.figure(figsize=(14, 7), facecolor='#f7f8fa')
    legends = {}
    for index, angle in enumerate((0, 110), 1):
        state = next(s for s in data['states'] if s['variant_ah'] == ah and s['angle_deg'] == angle)
        ax = fig.add_subplot(1, 2, index, projection='3d')
        ax.set_facecolor('#f7f8fa')
        all_triangles, all_colors = [], []
        for part in state['parts']:
            vertices = np.array(part['vertices'])
            triangles = vertices[np.array(part['faces'])]
            all_triangles.extend(triangles)
            all_colors.extend([part['color']] * len(triangles))
            if part['name'] in labels:
                legends[labels[part['name']]] = part['color']
        # Une seule collection trie ensemble les faces de toutes les pièces.
        # Le tri par objet peut montrer la cage à travers le pack opaque.
        surface = Poly3DCollection(all_triangles, facecolors=all_colors,
            edgecolors=all_colors, linewidths=0, alpha=1, shade=True,
            zsort='average')
        ax.add_collection3d(surface)
        if angle == 0:
            limits = ((-135, 135), (-65, 65), (75, 205))
        else:
            limits = ((-225, 135), (-65, 65), (75, 390))
        ax.set_xlim(*limits[0]); ax.set_ylim(*limits[1]); ax.set_zlim(*limits[2])
        ax.set_box_aspect([b-a for a,b in limits])
        ax.view_init(elev=23, azim=-58)
        ax.set_axis_off()
        ax.set_title('Fermé' if angle == 0 else 'Capot ouvert à 110°', fontsize=14, pad=0)
    fig.suptitle(f'Variante candidate — berceau fixe pour batterie 6S {ah} Ah',
                 fontsize=18, x=0.5, y=0.96)
    legend = [Patch(facecolor=c, label=n) for n,c in legends.items()]
    fig.legend(handles=legend, loc='lower center', bbox_to_anchor=(0.5, 0.08),
               ncol=3, frameon=False, fontsize=10)
    footer = 'Géométrie native FreeCAD ; mousse et axe représentés par réservations. '
    footer += 'Accrochage du loquet, fixations et tenue physique à valider.'
    if ah == 20:
        footer += '\nCale ajourée de 7 mm sous le pack 20 Ah ; tolérances de ce pack hypothétiques.'
    fig.text(0.5, 0.03, footer, fontsize=9, ha='center', color='#46515c')
    fig.subplots_adjust(left=0, right=1, bottom=0.17, top=0.88, wspace=-0.08)
    out = MEC / f'verification/berceau_fixe_{ah}Ah_candidat_20261002.png'
    fig.savefig(out, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(out.relative_to(ROOT), hashlib.sha256(out.read_bytes()).hexdigest())
