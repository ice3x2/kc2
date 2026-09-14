"""CON-ARCH-006 actual constant-floor section capture measurements."""
from shapely.geometry import LineString
from shapely.affinity import translate


def contiguous_throat(receiver, x, y):
    hit = receiver.intersection(LineString([(x, y-3), (x, y+3)]))
    intervals = [(g.bounds[1], g.bounds[3]) for g in getattr(hit, 'geoms', [hit])
                 if not g.is_empty and g.geom_type == 'LineString']
    if any(lo <= y <= hi for lo, hi in intervals):
        raise ValueError('Receiver center blocked')
    below = [hi for lo, hi in intervals if hi < y]
    above = [lo for lo, hi in intervals if lo > y]
    if not below or not above:
        raise ValueError('Missing contiguous receiver shoulder')
    return min(above) - max(below)


def motion_areas(donor, receiver):
    return [dict(dx=dx, dy=dy, collision_area_mm2=translate(donor, dx, dy).intersection(receiver).area)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
