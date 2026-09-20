"""CON-ARCH-006 approved continuous external sleeve; pure geometric planner."""
from dataclasses import dataclass
from shapely.geometry import box, GeometryCollection
from shapely.ops import unary_union


@dataclass(frozen=True)
class SleeveDimensions:
    pcb_bottom: float = 2.5
    pcb_top: float = 4.1
    upper_bottom: float = 4.4
    wall_top: float = 5.6
    wall_thickness: float = 1.2
    lateral_gap: float = .3
    floor_bottom: float = -2.2
    floor_top: float = -1.
    floor_heel: float = 2.


@dataclass(frozen=True)
class SleevePlan:
    wall: object
    floor: object
    central: object
    service: object
    inner: object
    dimensions: SleeveDimensions
    discarded_center_nubs: object


def mating_outline(domain, keycaps, board=None):
    """Wide nominal cap skirts may exceed the previous plate outline.

    Keep them inside the common interface outline, so the external sleeve has
    its full lateral clearance even where a cap extends past an old plate.
    """
    if domain.is_empty or not domain.is_valid or not keycaps.is_valid:
        raise ValueError('Invalid common outline input')
    result = domain.union(keycaps)
    if board is not None:
        if board.is_empty or not board.is_valid:
            raise ValueError('Invalid actual PCB outline')
        result = result.union(board)
    return result


def cad_outline(geometry):
    """Remove Boolean roundoff edges below CAD kernel resolution, not features."""
    cleaned = geometry.simplify(1e-9, preserve_topology=True)
    if (not cleaned.is_valid or cleaned.is_empty or
            geometry.symmetric_difference(cleaned).area > 1e-6 or
            geometry.hausdorff_distance(cleaned) > 2e-9):
        raise ValueError('Outline cleanup exceeded numerical-only tolerance')
    return cleaned


def validate_dimensions(d):
    if d.wall_top-d.pcb_top < 1.-1e-8:
        raise ValueError('Wall is not at least 1 mm above the PCB top')
    if abs(d.pcb_bottom-2.5)>1e-8 or abs(d.pcb_top-4.1)>1e-8:
        raise ValueError('Do not move the PCB stack')
    if d.wall_top <= d.upper_bottom or d.wall_thickness < 1.2-1e-8 or d.lateral_gap < .3-1e-8:
        raise ValueError('Insufficient overlap, wall thickness or assembly gap')


def sleeve_plan(side, domain, service, dimensions=SleeveDimensions(), *, central_exclusion=None):
    validate_dimensions(dimensions)
    if side not in ('left', 'right') or domain.is_empty or not domain.is_valid or not service.is_valid:
        raise ValueError('Invalid sleeve input')
    # A broad rectangular strip would incorrectly erase the non-central bottom
    # edge too. The caller derives this mask from the real opposite housing.
    central = GeometryCollection() if central_exclusion is None else central_exclusion
    if not central.is_valid:
        raise ValueError('Invalid central interface exclusion')
    corridors = [service]
    for g in getattr(service, 'geoms', [service]):
        if g.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        if side == 'left' and x1 >= domain.bounds[2]:
            corridors.append(box(x1-.01, y0, 300, y1))
        if side == 'right' and x0 <= domain.bounds[0]:
            corridors.append(box(-100, y0, x0+.01, y1))
    service = unary_union(corridors).buffer(.3, join_style=2)
    inner = domain.buffer(dimensions.lateral_gap, join_style=2)
    wall = inner.buffer(dimensions.wall_thickness, join_style=2).difference(inner)
    wall = wall.difference(central).difference(service)
    # Clipping the central interface can leave micron-scale disconnected
    # islands. Do not extrude them into fragile vertical needles. This removes
    # only separate new-wall components smaller than one 1.2x1.2 mm wall patch,
    # adjacent to the explicit central exclusion, never any existing housing.
    nubs = unary_union([g for g in getattr(wall, 'geoms', [wall])
                        if g.area < dimensions.wall_thickness**2 and g.distance(central) < .001])
    wall = wall.difference(nubs)
    # Heel exists ONLY in the floor band. The upright is vertically supported
    # from the floor; it is not a floating lip attached at the PCB edge.
    floor = wall.union(wall.buffer(dimensions.floor_heel, join_style=2).intersection(inner))
    floor = floor.difference(central)
    if wall.is_empty or floor.is_empty:
        raise ValueError('No sleeve remains')
    return SleevePlan(wall, floor, central, service, inner, dimensions, nubs)
