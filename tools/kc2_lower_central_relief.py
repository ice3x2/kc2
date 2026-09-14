"""CON-ARCH-006 free-cheek clearance in NEW right perimeter only.

The existing socket covers and floor are not cut. A0.30 mm plan clearance and
0.30 mm overhead clearance avoid attaching the floor-rooted flexure to the new
wall. The raised wall resumes above Z1.80; its short lintel requires print review.
"""
from shapely import affinity
from shapely.ops import unary_union
from tools.kc2_central_flexure import flexure_plan
def _place(area):
    return unary_union([affinity.translate(affinity.scale(area,xfact=-1,origin=(0,0)),xoff=153.3,yoff=y) for y in (95,117)])
def central_free_envelopes():
    p=flexure_plan();area=p['beam_body'].union(p['contact']).buffer(.3,join_style=2)
    return _place(area)
def male_insertion_envelopes():
    male=flexure_plan()['male']
    # Approach from the left in local feature X; the withdrawal translation
    # and convex hull bound the complete straight insertion path. New material
    # receives0.30 mm clearance; original intended contacts are never cut.
    sweep=male.union(affinity.translate(male,xoff=-5)).convex_hull.buffer(.3,join_style=2)
    return _place(sweep)
def wall_bands(wall):
    return [(-1,1.8,wall.difference(central_free_envelopes().union(male_insertion_envelopes()))),(1.8,4.10,wall)]
def floor_relief(floor):return floor.difference(male_insertion_envelopes())
