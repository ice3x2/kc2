"""CON-ARCH-006 alternative study; creates no printable housing or release.

Wall height and roof calculations are engineering candidates, not qualified
print tolerances. Full-wrap planar envelopes deliberately include the center
and services so that the unmodified alternative's conflicts remain visible.
"""
import json
from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely import affinity
import numpy as np
import trimesh
from tools.kc2_pcb_seating import horizontal_section, digest

ROOT = Path(__file__).resolve().parents[1]
TOPS = {'mx': 9.3, 'choc_v1': 6.5, 'deep_sea': 6.25}


def height_budget(rise, top, roof_gap=.3):
    wall_top = 4.1 + rise
    roof = top - (wall_top + roof_gap)
    return dict(pcb_top_mm=4.1, rise_mm=rise, wall_top_mm=wall_top,
                groove_roof_z_mm=wall_top + roof_gap,
                nominal_overlap_mm=max(0., wall_top-4.4), roof_mm=roof,
                meets_user_height=rise >= 1., roof_at_least_1_2_mm=roof >= 1.2)


def wrap_envelope(silhouette, clearance=.3, thickness=1.2):
    inner = silhouette.buffer(clearance, join_style=2)
    return inner, inner.buffer(thickness, join_style=2).difference(inner)


def filled_exteriors(geometry):
    parts = list(geometry.geoms) if hasattr(geometry, 'geoms') else [geometry]
    return unary_union([Polygon(p.exterior) for p in parts if isinstance(p, Polygon)])


def world(g, side):
    return affinity.translate(affinity.scale(g, xfact=-1, yfact=1, origin=(0, 0)),
                              xoff=170.1125 if side == 'left' else 323.3125)


def run():
    models = ROOT / 'hardware/MODELS'
    bindings = {}
    rows = {}
    wraps = {}
    for side in ('left', 'right'):
        for kind in TOPS:
            stem = f'kc2_{side}_{kind}_upper_housing'
            names = [stem+'.stl'] if side == 'left' else [stem+f'_part_{p}.stl' for p in ('a', 'b')]
            meshes = []
            for name in names:
                path = models/name
                bindings[path.relative_to(ROOT).as_posix()] = digest(path)
                mesh = trimesh.load(path, force='mesh')
                if not mesh.is_watertight:
                    raise ValueError('Invalid input mesh: '+name)
                meshes.append(mesh)
            mesh = trimesh.util.concatenate(meshes)
            levels = sorted(set(float(v) for v in np.round(mesh.vertices[:, 2], 5)))
            # Every horizontal vertex-height band contributes to the side envelope.
            silhouette = unary_union([filled_exteriors(horizontal_section(mesh, (a+b)/2))
                                      for a, b in zip(levels, levels[1:])])
            inner, wall = wrap_envelope(silhouette)
            before = silhouette.bounds
            after = wall.bounds
            rows[side+':'+kind] = dict(actual_upper_bounds_xy_mm=list(before),
                untrimmed_wrap_bounds_xy_mm=list(after),
                untrimmed_wrap_width_mm=after[2]-after[0],
                untrimmed_wrap_depth_mm=after[3]-after[1],
                expansion_each_side_mm=[before[0]-after[0], before[1]-after[1],
                                        after[2]-before[2], after[3]-before[3]],
                wall_area_mm2=wall.area,
                height_candidates=[height_budget(h, TOPS[kind]) for h in (1., 1.2, 1.5, 2.)])
            wraps[side, kind] = world(wall, side)
            print(side, kind, 'measured', flush=True)
    joins = {kind: dict(untrimmed_wrap_overlap_mm2=wraps['left', kind].intersection(wraps['right', kind]).area,
                        untrimmed_wrap_gap_mm=wraps['left', kind].distance(wraps['right', kind])) for kind in TOPS}
    for name in ('tools/kc2_wall_engagement_study.py', 'tools/test_kc2_wall_engagement_study.py',
                 'tools/kc2_pcb_seating.py'):
        bindings[name] = digest(ROOT/name)
    if any(digest(ROOT/name) != value for name, value in bindings.items()):
        raise ValueError('Inputs changed during study')
    result = dict(requirement='CON-ARCH-006', status='alternative_study_not_print_release',
                  rows=rows, joins=joins, source_sha256=bindings, physical_qualified=False,
                  limitations=['Full-wrap silhouette is sampled from actual upper STL, not a finished wall design.',
                               'Central seam and USB/service openings are NOT removed in this deliberately naive candidate.',
                               'Right split mask, roots, keycap travel and native CAD are not implemented or qualified.',
                               'Clearance .30, thickness 1.20 and roof comparison are engineering assumptions.',
                               'A 1.50 mm PCB-relative rise wraps the lower portion of the upper side, not its entire height.'])
    output = ROOT/'docs/reports/wall-engagement-20260920/alternatives.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(joins), flush=True)
    return result


if __name__ == '__main__':
    run()
