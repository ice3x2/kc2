"""CON-ARCH-006 local socket covers; baseline datums/supports stay unchanged."""
import math
from shapely.geometry import Polygon
from shapely.ops import unary_union

WALL_MM=.401  # 0.40 nominal plus polygon/numeric reserve; printing unqualified.
ATTACHMENT_MM=.30


def clip_patches_to_split(patch,extended_part_masks):
    parts=[patch.intersection(mask) for mask in extended_part_masks]
    for i,part in enumerate(parts):
        if any(part.intersection(other).area>1e-8 for other in parts[i+1:]):
            raise ValueError('Local covers must not close the retained print seam')
    return parts


def assign_local_patches(patches,part_masks):
    assigned=[[] for mask in part_masks]
    for patch in patches:
        owners=[i for i,mask in enumerate(part_masks) if patch.intersection(mask).area>1e-7]
        if len(owners)!=1:
            raise ValueError('Local cover crosses existing split or has no floor attachment')
        assigned[owners[0]].append(patch)
    return [unary_union(items) if items else Polygon() for items in assigned]


def lower_cover_plan(outline,clearance_cutouts,thickness=WALL_MM):
    if not math.isfinite(thickness) or thickness < .4:
        raise ValueError('Local wall must have a finite >=0.40 mm design thickness')
    exposed=[part for part in getattr(clearance_cutouts,'geoms',[clearance_cutouts])
             if part.intersects(outline.boundary)]
    if not exposed:
        return dict(opening_count=0,outer=outline,wall=Polygon(),floor_patch=Polygon())
    local=unary_union(exposed)
    wrapped=local.buffer(thickness,quad_segs=64)
    outer=outline.union(wrapped)
    # Work only beside exposed cavities. Overlap the existing solid/floor by
    # 0.30 mm, rather than adding a strip around the entire old perimeter.
    locality=wrapped.buffer(ATTACHMENT_MM,quad_segs=64)
    patch=outer.difference(outline.buffer(-ATTACHMENT_MM)).intersection(locality)
    wall=patch.difference(clearance_cutouts)
    return dict(opening_count=len(exposed),outer=outer,wall=wall,floor_patch=patch)
