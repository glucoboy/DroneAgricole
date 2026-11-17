"""Retry large compound pairs with conservative component bounds."""

from functools import cached_property
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))
from electromechanical_engine import freecad_worker as native
from electromechanical_engine import xlink_native as xlink


def solid_components(shape):
    if shape.ShapeType == 'Solid':
        return [shape]
    if shape.ShapeType not in ('Compound', 'CompSolid'):
        raise ValueError(f'Compound contains a non-solid component: {shape.ShapeType}')
    return [solid for child in shape.childShapes() for solid in solid_components(child)]


def lower_gap(a, b, pad):
    return math.hypot(*(max(0.0, low_a - high_b - pad, low_b - high_a - pad)
                        for low_a, high_a, low_b, high_b in zip(*a, *b)))


class ShapeChecks:
    def __init__(self, shape, pad):
        self.shape = shape
        self.pad = pad

    @cached_property
    def valid(self):
        return self.shape.isValid()

    @cached_property
    def Solids(self):
        return self.shape.Solids

    @cached_property
    def Volume(self):
        return self.shape.Volume

    @cached_property
    def box(self):
        return native.bounds(self.shape)

    def isValid(self):
        return self.valid

    def isNull(self):
        return self.shape.isNull()


class SolidCompound(ShapeChecks):
    @cached_property
    def components(self):
        solids = solid_components(self.shape)
        if len(solids) != len(self.Solids):
            raise ValueError('Component decomposition does not cover the original solid occurrences')
        return [(part, native.bounds(part)) for part in solids]

    def ranked(self, other):
        rows = [(lower_gap(box, other.box, self.pad), index, part)
                for index, (part, box) in enumerate(self.components)]
        rows.sort(key=lambda row: (row[0], row[1]))
        return rows


class Cable(ShapeChecks):
    def common(self, other):
        overlapping = [part for lower, _, part in other.ranked(self) if lower == 0]
        print(f'Boolean on {len(overlapping)}/{len(other.components)} conservatively selected solids', flush=True)
        if not overlapping:
            return native.Part.makeCompound([])
        return self.shape.common(native.Part.makeCompound(overlapping))

    def distToShape(self, other):
        best = math.inf
        tested = 0
        for lower, _, part in other.ranked(self):
            if lower > best:
                break
            distance = self.shape.distToShape(part)[0]
            if not math.isfinite(distance) or distance < 0:
                raise ValueError('Invalid component clearance')
            best = min(best, distance)
            tested += 1
        print(f'Exact BRep distance on {tested}/{len(other.components)} solids', flush=True)
        if not math.isfinite(best):
            raise ValueError('No component could be measured')
        return (best,)


def measure(tasks, records, shapes, objects, criteria, cache_key):
    if any(task['kind'] != 'pair' or not task['b'].endswith('/FabricantSansRefroidissement')
           or task.get('relation') for task in tasks):
        raise ValueError('Method reserved for the profiled OEM compound in the frozen campaign')
    guarded = {}
    pad = criteria['distance_tolerance_mm']
    for task in tasks:
        if task['a'] not in guarded:
            guarded[task['a']] = Cable(shapes[task['a']], pad)
        if task['b'] not in guarded:
            guarded[task['b']] = SolidCompound(shapes[task['b']], pad)
    return original_measure(tasks, records, guarded, objects, criteria, cache_key)


if __name__ == '__main__':
    original_measure = xlink.measure
    xlink.measure = measure
    xlink.main()
