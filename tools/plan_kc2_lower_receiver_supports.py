"""CON-ARCH-006 read-only support/cover exclusions for proposed receiver cleanup."""
import json,hashlib
from pathlib import Path
from shapely import wkt
from tools.plan_kc2_lower_receiver_repair import geometry
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    from tools.generate_kc2_magnetic_housings import load_plans
    from tools import generate_kc2_x3_v2_housings as legacy
    folder=ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal'
    oldp=ROOT/'docs/reports/reinforced-covers-20260913/right-lower.json';diagp=folder/'throat-diagnosis.json'
    pp=ROOT/'.codex-tmp/perimeter-wall-plans.json';gp=folder/'generation.json'
    paths=[Path(__file__),oldp,diagp,pp,gp]+[ROOT/'tools'/name for name in (
        'plan_kc2_lower_receiver_repair.py','generate_kc2_magnetic_housings.py','generate_kc2_x3_v2_housings.py',
        'generate_kc2_housings.py','render_kc2_x3_joined.py')]
    paths += [ROOT/f'hardware/PCB/kc2_{side}/kc2_{side}.kicad_pcb' for side in ('left','right')]
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('extract unchanged actual PCB support roles, no CAD generation',flush=True)
    plans,_,_=load_plans();p=plans['right'];old=json.loads(oldp.read_text());g=json.loads(gp.read_text())
    roles=dict(support_posts=legacy._support_plan_union(legacy.legacy_geometry.require_shapely(),p['support_posts']),
        rail=p['rail'],mounting_lands=p['mounting_land_geometry'],reset_local_support=p['reset_local_support_geometry'],
        existing_reinforced_socket_covers=wkt.loads(old['wall_wkt']),
        new_perimeter_wall=wkt.loads(json.loads(pp.read_text())['sides']['right']['wall_wkt']))
    for name,r in g['registrars'].items():roles['registrar_'+name]=wkt.loads(r['wall'])
    rows=[]
    for d in json.loads(diagp.read_text())['rows']:
        y=d['y_mm'];actual=wkt.loads(next(s['actual_wkt'] for s in d['sections'] if s['z_mm']==0))
        _,ring=geometry(y,1.2);cut=actual.intersection(ring)
        row=dict(y_mm=y,actual_z0_wkt=actual.wkt,full_ring_current_actual_removed_area_mm2=cut.area,
            full_ring_current_actual_role_overlap_mm2={name:cut.intersection(area).area for name,area in roles.items()})
        print(y,row['full_ring_current_actual_role_overlap_mm2'],flush=True);rows.append(row)
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Changed support source')
    report=dict(requirements=['CON-ARCH-006'],status='plan_only_no_approval_or_CAD_change',source_sha256=frozen,
        roles_wkt={name:area.wkt for name,area in roles.items()},rows=rows,physical_qualified=False)
    (folder/'receiver-supports-plan.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':run()
