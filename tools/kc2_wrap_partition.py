"""CON-ARCH-006 continuation of original profile_split ownership OUTSIDE its domain.

Interior capture keys/receivers are never recomputed or replaced. This repeats
only the original unbounded initial Voronoi/ring/boss assignment to extend the
existing seam where added perimeter stock lies beyond the former outline.
"""
from shapely import voronoi_polygons
from shapely.geometry import MultiPoint, Point
from shapely.ops import unary_union


def raw_owners(original_domain, openings, mounting_centers):
    centers = [(g.centroid.x, g.centroid.y) for g in openings.geoms]
    middle = (original_domain.bounds[0]+original_domain.bounds[2])/2
    cells = voronoi_polygons(MultiPoint(centers), extend_to=original_domain.envelope)
    groups = [[], []]
    for cell in cells.geoms:
        center = next(c for c in centers if cell.covers(Point(*c)))
        groups[int(center[0] >= middle)].append(cell)
    a, b = [unary_union(g) for g in groups]
    for opening in openings.geoms:
        region = opening.buffer(1.01)
        if opening.centroid.x < middle:
            a, b = a.union(region), b.difference(region)
        else:
            a, b = a.difference(region), b.union(region)
    for center in mounting_centers:
        point = Point(*center); disk = point.buffer(2.61, quad_segs=64)
        if a.covers(point):
            a, b = a.union(disk), b.difference(disk)
        else:
            a, b = a.difference(disk), b.union(disk)
    return a.buffer(-.20002), b.buffer(-.20002)
