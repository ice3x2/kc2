"""CON-ARCH-006 raised perimeter additions, three approved central omissions.

Existing socket covers are never cutters here. All returned polygons are
ADDITIONS except explicit new-wall-only omission/service bookkeeping.
"""
from dataclasses import dataclass
from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union

# Actual world-coordinate conflicts, rounded outward by1.2mm to terminate
# the new wall clear of the collision rather than taper into a fragile remnant.
APPROVED_WORLD_OMISSIONS=unary_union([box(*b).buffer(1.2,quad_segs=16) for b in [
    (158.450191,86.1,166.524809,88.),
    (158.450191,105.15,161.762309,107.05),
    (163.212691,124.2,171.287309,126.1)]])


@dataclass(frozen=True)
class PerimeterPlan:
    wall: object
    floor_addition: object
    central_removed: object
    service_removed: object
    inner: object
    bands: tuple = ((-1.,2.5),(2.5,4.10))
    floor_z: tuple = (-2.2,-1.)


def to_world(g,raw_bounds,side):
    if side not in ('left','right'):raise ValueError('unknown side')
    return affinity.translate(affinity.scale(g,xfact=-1,yfact=1,origin=(0,0)),
        xoff=raw_bounds[2]+(124.625 if side=='right' else 0),yoff=raw_bounds[1])


def to_local(g,raw_bounds,side):
    if side not in ('left','right'):raise ValueError('unknown side')
    return affinity.scale(affinity.translate(g,xoff=-raw_bounds[2]-(124.625 if side=='right' else 0),
        yoff=-raw_bounds[1]),xfact=-1,yfact=1,origin=(0,0))


def perimeter_plan(*,board,lower_protected,mx_body,service,floor,
                   world_omissions,raw_bounds,side):
    if side not in ('left','right'):raise ValueError('unknown side')
    for name,g in [('board',board),('lower',lower_protected),('MX',mx_body),
                   ('service',service),('floor',floor),('omissions',world_omissions)]:
        if not g.is_valid or (name in ('board','floor') and g.is_empty):raise ValueError('invalid '+name)
    if world_omissions.difference(APPROVED_WORLD_OMISSIONS).area>1e-8:
        raise ValueError('omission exceeds approved local envelope')
    inner=board.buffer(.3,join_style=2).union(lower_protected).union(mx_body)
    complete=inner.buffer(1.2,join_style=2).difference(inner)
    central=to_local(world_omissions,raw_bounds,side)
    wall=complete.difference(central).difference(service)
    # A common footprint through both Z bands avoids unsupported outward steps
    # at PCB top. Floor extension has an inward2mm anchor only belowZ-1.
    floor_addition=wall.union(wall.buffer(2,join_style=2).intersection(inner))
    parts=list(floor_addition.geoms) if hasattr(floor_addition,'geoms') else [floor_addition]
    if wall.is_empty or any(g.intersection(floor).area<.1 for g in parts):
        raise ValueError('floor attachment missing')
    return PerimeterPlan(wall,floor_addition,complete.intersection(central),
                         complete.difference(central).intersection(service),inner)
