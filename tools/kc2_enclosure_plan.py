"""CON-ARCH-006 preliminary envelope/spacing review, not printable CAD approval."""
import hashlib
import json
import math
from pathlib import Path
from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]


def wall_plan(board, components, thickness):
    if not math.isfinite(thickness) or thickness<.4:
        raise ValueError('Wall below0.40mm or nonfinite; no qualified print process')
    # Circumscribed allowance: chordal polygon approximation must not erode
    # the declared clearance at convex corners; add 1 micron numerical reserve.
    inner=board.union(components).buffer(.301/math.cos(math.pi/128),quad_segs=32)
    if inner.geom_type!='Polygon':
        raise ValueError('Disconnected cavity envelope requires an explicit connecting outline')
    inner=Polygon(inner.exterior)
    outer=inner.buffer(thickness,quad_segs=8)
    return {'inner':inner,'outer':outer,'wall':outer.difference(inner),'thickness_mm':thickness}


def join_review(left,right):
    overlap=left.intersection(right).area
    gap=left.distance(right)
    return {'overlap_area_mm2':overlap,'clearance_mm':gap,'passes':overlap<1e-8 and gap>=.3-1e-8}


def global_shape(shape,plan,dx=0):
    return affinity.translate(affinity.scale(shape,xfact=-1,yfact=1,origin=(0,0)),
                              xoff=plan['raw_bounds'][2]+dx,yoff=plan['raw_bounds'][1])


def allocate_outer_walls(left_inner,right_inner):
    """Prefer0.8mm, reserve0.4mm on both halves and0.301mm between cases."""
    minimum_left=left_inner.buffer(.401,quad_segs=32)
    minimum_right=right_inner.buffer(.401,quad_segs=32)
    if not join_review(minimum_left,minimum_right)['passes']:
        raise ValueError('Joined position cannot retain both minimum walls')
    left=left_inner.buffer(.801,quad_segs=32).difference(minimum_right.buffer(.310,quad_segs=32))
    right=right_inner.buffer(.801,quad_segs=32).difference(left.buffer(.301,quad_segs=32))
    for outer,minimum in [(left,minimum_left),(right,minimum_right)]:
        if outer.geom_type!='Polygon' or minimum.difference(outer.buffer(1e-7)).area>1e-6:
            raise ValueError('Allocation disconnected or thinned a wall')
    if not join_review(left,right)['passes']:
        raise ValueError('Outer walls collide')
    return left,right


def main():
    from tools import generate_kc2_x3_v2_housings as g
    from tools import generate_kc2_magnetic_housings as magnet
    plans,_,transform=magnet.load_plans()
    result={'requirements':['CON-ARCH-006','OPS-ARCH-006'],'baseline_commit':'cc854a3',
            'cad_changed':False,'pcb_gerber_changed':False,'joined_transform':transform,
            'pcb_component_clearance_mm':.3,'required_case_gap_mm':.3,'cases':[],
            'qualification':'plan feasibility only, not actual-solid/component/print approval',
            'source_sha256':{}}
    for thickness in [.8,.6,.4]:
        walls={}
        for side,p in plans.items():
            components=unary_union([*p['component_geometries'].values(),p['switch_service_body_geometry'],
                                   *p['mounting_service_geometries'].values(),
                                   p['feature_geometries']['controller_socket'].convex_hull,
                                   p['reset_actuator_geometry']])
            walls[side]=wall_plan(p['board'],components,thickness)
        l=global_shape(walls['left']['outer'],plans['left'])
        r=global_shape(walls['right']['outer'],plans['right'],transform['dx'])
        baseline=join_review(l,r)
        needed=next((i*.05 for i in range(301) if join_review(l,affinity.translate(r,xoff=i*.05))['passes']),None)
        row={'wall_mm':thickness,'original_join':baseline,'minimum_extra_x_on_0_05mm_grid':needed,
             'resulting_nominal_keycap_gap_mm':None if needed is None else 1.8+needed,
             'sides':{s:{'bounds_mm':w['outer'].bounds,'wall_area_mm2':w['wall'].area}
                      for s,w in walls.items()}}
        result['cases'].append(row)
        print(json.dumps(row),flush=True)
    pcb_left=global_shape(plans['left']['board'],plans['left'])
    pcb_right=global_shape(plans['right']['board'],plans['right'],transform['dx'])
    from shapely.ops import nearest_points
    a,b=nearest_points(pcb_left,pcb_right)
    result['pcb_only_bottleneck']={'gap_mm':pcb_left.distance(pcb_right),
        'closest_points_global_mm':[list(a.coords[0]),list(b.coords[0])],
        'maximum_symmetric_wall_mm_at_original_position':
            (pcb_left.distance(pcb_right)-2*.3-.3)/2,
        'basis':'PCB edge gap minus two0.30mm PCB allowances and0.30mm case gap, divided between walls'}
    for p in [Path(__file__),ROOT/'tools/test_kc2_enclosed_housing.py',Path(g.__file__),
              Path(magnet.__file__),*g.BOARD_PATHS.values()]:
        result['source_sha256'][p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    folder=ROOT/'docs/reports/enclosed-housing-20260909'
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'plan-feasibility.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
