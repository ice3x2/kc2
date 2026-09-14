"""CON-ARCH-006 independent finite SOLID/SOLID clearance, never compounds."""
import math

BOUND_PADDING_MM = 1e-5
POSITIVE_MARGIN_MM = 1e-4


def padded_bounds(values):
    if values is None or len(values) != 6 or not all(math.isfinite(v) for v in values):
        raise ValueError('Missing/nonfinite bounds')
    if any(values[i] > values[i+3] for i in range(3)):
        raise ValueError('Inverted bounds')
    return [v-BOUND_PADDING_MM if i<3 else v+BOUND_PADDING_MM for i,v in enumerate(values)]


def solid_bounds(solid):
    if (solid.ShapeType() != 'Solid' or not solid.isValid() or len(solid.Solids()) != 1
            or not solid.Shells() or any(not shell.Closed() for shell in solid.Shells())
            or not math.isfinite(solid.Volume()) or solid.Volume() <= 0):
        raise ValueError('Expected valid positive closed SOLID, not Compound')
    b=solid.BoundingBox()
    return padded_bounds([b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax])


def pair_clearance(a,b,distance_factory=None):
    aa,bb=solid_bounds(a),solid_bounds(b)
    return _validated_pair(a,b,aa,bb,distance_factory)


def clearance_inventory(parts,tools,progress=None):
    if not parts or not tools:
        raise ValueError('Empty solid inventory')
    part_bounds=[solid_bounds(s) for s in parts]
    tool_bounds=[solid_bounds(s) for s in tools]
    rows=[]
    # No Boolean/mutation operations occur between validation and distance.
    for i,(a,aa) in enumerate(zip(parts,part_bounds)):
        for j,(b,bb) in enumerate(zip(tools,tool_bounds)):
            row=dict(part=i,tool=j,**_validated_pair(a,b,aa,bb))
            rows.append(row)
            if progress is not None:progress(row)
    return rows


def _validated_pair(a,b,aa,bb,distance_factory=None):
    separation=max(bb[i]-aa[i+3] for i in range(3))
    separation=max(separation,max(aa[i]-bb[i+3] for i in range(3)))
    if separation > POSITIVE_MARGIN_MM:
        return dict(clear=True,method='outward_padded_aabb',distance_lower_bound_mm=separation,
                    a_bounds_mm=aa,b_bounds_mm=bb)
    if distance_factory is None:
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        distance_factory=BRepExtrema_DistShapeShape
    solver=distance_factory(a.wrapped,b.wrapped)
    solver.Perform()
    if not solver.IsDone():
        raise ValueError('Solid distance solver incomplete')
    value=solver.Value()
    if not math.isfinite(value) or value < 0:
        raise ValueError('Nonfinite/negative solid distance')
    return dict(clear=value > POSITIVE_MARGIN_MM,method='solid_solid_extrema',distance_mm=value,
                is_done=True,a_bounds_mm=aa,b_bounds_mm=bb)
