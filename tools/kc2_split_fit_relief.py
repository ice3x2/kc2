"""CON-ARCH-006 subtractive, local right A/B fit planning in millimetres.

This is a section planner, not evidence of a printable or qualified 3D part.
Callers must protect mounting/clip roots and inspect every CAD height stratum.
Entry relief is a stepped recess, not a chamfer or a support-free-print claim.
"""
from dataclasses import dataclass
from math import cos, isfinite, pi
from numbers import Real

from shapely.geometry import GeometryCollection, Polygon
from shapely.geometry.base import BaseGeometry


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def _part(value, name):
    if not isinstance(value, Polygon) or value.is_empty or not value.is_valid:
        raise ValueError(f'{name} must be a valid connected Polygon')
    if not all(isfinite(v) for v in value.bounds):
        raise ValueError(f'{name} has nonfinite coordinates')


def _buffer(value, distance):
    # Circumscribed approximation: ordinary GEOS circular buffers are inscribed
    # and can under-clear diagonal corners. Bound that approximation outward.
    # A 0.00001 mm reserve also covers GEOS overlay rounding at the
    # many short edges in the retained real captive-key masks.
    return value.buffer(distance / cos(pi / 512) + 1e-5, quad_segs=128)


@dataclass(frozen=True)
class ReliefSection:
    part_a: Polygon
    part_b: Polygon
    cutter_a: BaseGeometry
    cutter_b: BaseGeometry
    target_gap: float


@dataclass(frozen=True)
class RequiredRoot:
    """Caller-designed minimum retained root, not an inferred strength value.

    The entire region must exist before relief and survive both height bands.
    Choose this envelope from the actual attachment's required width/path.
    """
    name: str
    region: Polygon


@dataclass(frozen=True)
class SplitReliefPlan:
    core: ReliefSection
    entry: ReliefSection
    z_min: float
    z_max: float
    entry_height: float

    def at_z(self, z):
        z = _number(z, 'z')
        if z < self.z_min or z > self.z_max:
            raise ValueError('z is outside the planned height')
        if z < self.z_min + self.entry_height or z > self.z_max - self.entry_height:
            return self.entry
        return self.core


def _section(a, b, protected_a, protected_b, target, seed=None):
    start_a, start_b = (a, b) if seed is None else (seed.part_a, seed.part_b)
    gap = start_a.distance(start_b)
    if gap >= target:
        aa, bb = start_a, start_b
    else:
        # Parallel seam walls retreat equally. For arbitrary corners the second
        # cut explicitly guarantees the final pair clearance; no perimeter-wide
        # erosion and no added material or moved reference coordinates.
        aa = start_a.difference(_buffer(start_b, (gap + target) / 2))
        _part(aa, 'relieved part A')
        bb = start_b.difference(_buffer(aa, target))
    _part(aa, 'relieved part A')
    _part(bb, 'relieved part B')
    ca, cb = a.difference(aa), b.difference(bb)
    for cutter, protected, name in ((ca, protected_a, 'A'), (cb, protected_b, 'B')):
        if cutter.intersection(protected).area > 1e-10:
            raise ValueError(f'relief cuts protected material on part {name}')
    if aa.distance(bb) < target - 1e-8:
        raise ValueError('relief failed to achieve requested clearance')
    return ReliefSection(aa, bb, ca, cb, target)


def plan_split_relief(part_a, part_b, *, protected_a=None, protected_b=None,
                      target_gap=.40, entry_extra=.20, entry_height=.40,
                      z_min=0., z_max=2.5, required_roots_a=(), required_roots_b=()):
    """Return expected core/entry sections and cutters in original coordinates.

    ``entry_extra`` is added to the total A/B gap, NOT independently to both
    faces. Entry cuts are nested in the core cuts. Any protected-material cut
    rejects the plan instead of silently reducing required fit relief.
    Protection may include already-empty screw/clip space, but callers should
    also include the surrounding structural roots that must remain intact.
    Zero entry_extra disables extra relief; nonzero entry bands cannot overlap.
    Supply named RequiredRoot envelopes for every clearance-adjacent structural
    neck in required_roots_a/b. Connected output alone does NOT establish a
    minimum neck or material strength. Without caller roots only topology and
    clearance are checked; this planner never certifies mechanical strength.
    """
    _part(part_a, 'part A')
    _part(part_b, 'part B')
    if part_a.intersection(part_b).area > 1e-10:
        raise ValueError('input parts overlap')
    roots = (tuple(required_roots_a), tuple(required_roots_b))
    for part, guards in zip((part_a, part_b), roots):
        for guard in guards:
            if not isinstance(guard, RequiredRoot) or not isinstance(guard.name, str) or not guard.name.strip():
                raise ValueError('required root must have a nonempty name')
            _part(guard.region, f'required root {guard.name}')
            if not part.covers(guard.region):
                raise ValueError(f'required root {guard.name} is absent from original part')
    protected = []
    for value in (protected_a, protected_b):
        value = GeometryCollection() if value is None else value
        if not isinstance(value, BaseGeometry) or not value.is_valid:
            raise ValueError('invalid protected geometry')
        protected.append(value)
    target_gap = _number(target_gap, 'target_gap')
    entry_extra = _number(entry_extra, 'entry_extra')
    entry_height = _number(entry_height, 'entry_height')
    z_min, z_max = _number(z_min, 'z_min'), _number(z_max, 'z_max')
    if target_gap <= 0 or entry_extra < 0 or entry_height < 0 or z_max <= z_min:
        raise ValueError('invalid gap or height range')
    if entry_extra and (entry_height == 0 or 2 * entry_height >= z_max - z_min):
        raise ValueError('entry bands must be positive and leave a core height')
    core = _section(part_a, part_b, *protected, target_gap)
    entry = (_section(part_a, part_b, *protected, target_gap + entry_extra, seed=core)
             if entry_extra else core)
    for section in (core, entry):
        for part, guards in zip((section.part_a, section.part_b), roots):
            for guard in guards:
                if not part.covers(guard.region):
                    raise ValueError(f'relief removes required root {guard.name}')
    return SplitReliefPlan(core, entry, z_min, z_max, entry_height)
