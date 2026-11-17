"""Mesures ciblées et vues dérivées des BRep enregistrés de la copie."""
from autonomie_cao import *


def run():
    reader = Reader(COPY)
    baseline = Reader(ROOT/'hardware/mecanique/cartographe_faisceaux')
    selected = read(OUT/'selection_f16.json')
    f16 = read(report(selected))
    build = read(COPY/'verification/construction_prototype.json')
    rows = {r['occurrence']: r for r in build['occurrences'] if r['parent'].startswith('sous_assemblages/')}
    path = reader.shape(f16['file'], f16.get('object_path','CompoundPath'))
    moving = reader.shape(f16['file'], f16.get('object_mobile','Cable'))
    fixed = reader.shape(f16['file'], f16.get('object_fixed','Cable001'))
    screw = reader.occurrence(rows['OEM_Part__Feature079'])
    diagnostic = []
    for name, shape in [('mobile', moving), ('fixe', fixed)]:
        lower = gap(shape.BoundBox, screw.BoundBox)
        distance = shape.distToShape(screw)[0]
        diagnostic.append({'segment': name, 'aabb_lower_bound_mm': lower, 'distance_occt_raw_mm': distance,
                           'distance_mm': distance if distance >= lower-1e-6 else None,
                           'intersection_excluded_by_aabb': lower > 1e-6})
    stations = []
    for st in read(OUT/'recherche_suspension.json')['stations']:
        released = st['id'] in ('F16_V_-45', 'F16_V_0', 'F16_V_35')
        point = Part.Vertex(App.Vector(*st['baseline_point_mm']))
        stations.append({'id': st['id'], 'retained': not released, 'distance_to_axis_mm': point.distToShape(path)[0]})
    cadre = reader.occurrence(rows['P75_Cadre'])
    protection = read(OUT/'protection_F38_OVALE_L80.json')
    wall = reader.shape(protection['file'], protection['object'])
    guide = reader.occurrence(rows['P73_Guide'])
    p75 = measured_pair(fixed, cadre)
    write(OUT/'controle_details_autonomie.json', {'f16_sha256': f16['sha256'], 'stations': stations,
          'retained_stations_at_0_6_mm': sum(s['retained'] and s['distance_to_axis_mm'] <= .6 for s in stations),
          'oem079_distance_diagnostic': diagnostic, 'p75_fixed_segment': p75,
          'clearance_acceptance_mm': None, 'scope': 'Le retour de distance inférieur à la borne AABB est indéterminé. La borne AABB positive démontre la séparation de la paire.'})

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    routes = read(baseline.base/'verification/routes_prototype.json')['routes']
    prior = next(r for r in routes if r['id'] == 'F16')
    old_path = baseline.shape(prior['fichier'], prior['objet_parcours'])
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 6.3), gridspec_kw={'width_ratios': [1.55, 1]})
    def curve(ax, shape, axes, label, color, width=1.6, style='-'):
        for i, edge in enumerate(shape.Edges):
            points = edge.discretize(Deflection=.08)
            ax.plot(*[[getattr(p,a) for p in points] for a in axes], color=color, lw=width, ls=style,
                    label=label if i == 0 else None)
    curve(left, old_path, 'xz', 'F16 initial', '#9da6b0', 1.7, '--')
    paths = [reader.shape(f16['file'], n) for n in ('Wire','Wire001')]
    curve(left, paths[0], 'xz', 'Zone mobile R50', '#7031ac', 2.8)
    curve(left, paths[1], 'xz', 'Zone fixe R24', '#1b7592', 2.8)
    left.scatter([96],[75],color='#142d43',s=25,zorder=4)
    left.annotate('Retenue V75', (96,75), xytext=(116,89), arrowprops={'arrowstyle':'-','color':'#596774'})
    left.set(title='F16 · projection latérale',xlabel='X (mm)',ylabel='Z (mm)',xlim=(-4,220),ylim=(-115,155))
    left.legend(loc='lower left',frameon=False,fontsize=9)
    for s, label, color in [(guide,'P73 avec ponts','#2c4151'),(wall,'Protection ovale','#16825a'),
                             (reader.occurrence(rows['F38_POS']),'F38 POS','#bd3c39'),
                             (reader.occurrence(rows['F38_NEG']),'F38 NEG','#4155a0')]:
        for i, wire in enumerate(s.slice(App.Vector(1,0,0),0)):
            curve(right,wire,'yz',label if i == 0 else None,color)
    right.set(title='F38 · coupe à X = 0 mm',xlabel='Y (mm)',ylabel='Z (mm)',xlim=(-112,-86),ylim=(45,68))
    right.legend(loc='upper center',bbox_to_anchor=(.5,-.18),frameon=False,fontsize=9,ncol=2)
    for ax in (left,right):
        ax.set_aspect('equal');ax.grid(alpha=.18);ax.set_axisbelow(True)
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Intégration candidate · F16 et protection F38',fontsize=16,fontweight='bold')
    fig.tight_layout()
    fig.savefig(OUT/'vues/04_autonomie_F16_F38.png',dpi=180,bbox_inches='tight')


if __name__ == '__main__':
    run()
