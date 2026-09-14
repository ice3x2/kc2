"""CON-ARCH-006 required component clearance, not the nominal cutter profile."""
import math
from shapely.ops import unary_union
def required_envelope(raw_classes):
    #4 facets per quadrant: circumscribing rather than inscribing bounds the
    # complete mathematical .301 offset, including the required .300 minimum.
    return unary_union([g.buffer(.301/math.cos(math.pi/16),join_style='round',quad_segs=4)
                        for g in raw_classes.values() if not g.is_empty])
