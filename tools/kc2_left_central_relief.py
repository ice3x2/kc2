"""CON-ARCH-006 subtract ONLY new left wall/floor around unchanged male.

The original stock and the complete male remain protected by actual CAD gates.
The nominal male/root running gap stays .15 mm; .30 applies outside the male.
The full-width lower wall window avoids an unsupported .50 mm residual strip.
"""
from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union
from tools.kc2_central_flexure import flexure_plan


def place(g,y):
    return affinity.translate(affinity.scale(g,xfact=-1,origin=(0,0)),xoff=.1,yoff=y)


def relief_plan(wall,floor):
    if not wall.is_valid or not floor.is_valid or wall.is_empty or floor.is_empty:
        raise ValueError('Valid nonempty declared left additions required')
    feature=flexure_plan()
    males=unary_union([place(feature['male'],y) for y in (95.,117.)])
    windows=unary_union([place(box(0,-2.85,2,2.85),y) for y in (95.,117.)])
    root_space=unary_union([place(feature['root_floor'].buffer(.3,join_style=2),y)
                            for y in (95.,117.)])
    low=wall.intersection(windows).difference(males)
    transition=wall.intersection(windows)
    bottom=floor.intersection(root_space).difference(males)
    return dict(requirements=['CON-ARCH-006'],ys_mm=[95.,117.],
                cuts=[(-2.2,-1.,bottom),(-1.,1.5,low),(1.5,1.8,transition)],
                wall_low=wall.difference(low),wall_transition=wall.difference(transition),
                wall_top=wall,floor=floor.difference(bottom),male=males,
                wall_z=[-1.,1.5,1.8,4.1],floor_z=[-2.2,-1.],
                lintel_span_mm=5.7,lintel_height_mm=2.3,lintel_width_mm=1.2,
                floor_clearance_mm=.3,male_running_gap_mm=.15,
                physical_qualified=False)
