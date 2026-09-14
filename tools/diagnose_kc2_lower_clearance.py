"""CON-ARCH-006 distinguish nominal tool-cut envelope from required clearance."""
from pathlib import Path
import json,hashlib
from shapely import wkt
from tools.review_kc2_local_covers import prism
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import load_plans
    p=load_plans()[0]['left'];oldpath=ROOT/'docs/reports/reinforced-covers-20260913/left-lower.json'
    expanded=wkt.loads(json.loads(oldpath.read_text())['clearance_wkt'])
    paths=[Path(__file__),ROOT/'tools/review_kc2_local_covers.py',ROOT/'tools/generate_kc2_magnetic_housings.py',
        ROOT/'tools/generate_kc2_x3_v2_housings.py',ROOT/'tools/generate_kc2_housings.py',oldpath,
        ROOT/'hardware/MODELS/kc2_left_lower_housing.step',ROOT/'.codex-tmp/registered-housing-fit/lower/left-normal/kc2_left_lower_housing.step',
        ROOT/'hardware/PCB/kc2_left/kc2_left.kicad_pcb',ROOT/'hardware/PCB/kc2_right/kc2_right.kicad_pcb']
    before={v.relative_to(ROOT).as_posix():digest(v) for v in paths}
    classes={}
    for name,raw in p['component_geometries'].items():
        if raw.is_empty:continue
        minimum=raw.buffer(.3,join_style='round',quad_segs=4)
        classes[name]=dict(raw_bounds=raw.bounds,nominal_overlap_area_mm2=p['support_surface'].intersection(p['component_cutout_geometries'][name]).area,
            minimum_clearance_overlap_area_mm2=p['support_surface'].intersection(minimum).area,
            actual_plan_distance_to_raw_mm=p['support_surface'].distance(raw),minimum_wkt=minimum.wkt)
    print('import canonical baseline for envelope diagnosis',flush=True)
    baseline=cq.importers.importStep(str(ROOT/'hardware/MODELS/kc2_left_lower_housing.step')).val()
    print('actual baseline vs nominal .35 tool clearance',flush=True)
    overlap=baseline.intersect(prism(expanded,-1,2.5))
    baseline_overlap=overlap.Volume();bb=overlap.BoundingBox()
    print('baseline nominal overlap',baseline_overlap,flush=True)
    final=cq.importers.importStep(str(ROOT/'.codex-tmp/registered-housing-fit/lower/left-normal/kc2_left_lower_housing.step')).val()
    for name,row in classes.items():
        print('actual full final required .30 clearance',name,flush=True)
        required=prism(wkt.loads(row.pop('minimum_wkt')),-.4,2.5)
        row['actual_final_minimum_obstruction_mm3']=final.intersect(required).Volume()
    if before!={v.relative_to(ROOT).as_posix():digest(v) for v in paths}:raise ValueError('Changed source')
    report=dict(requirements=['CON-ARCH-006'],status='diagnosed',source_sha256=before,classes=classes,
        baseline_nominal_overlap_mm3=baseline_overlap,baseline_overlap_z_mm=[bb.zmin,bb.zmax],
        expected_simplification_overlap_mm3=p['support_surface'].intersection(expanded).area*3.5,
        physical_qualified=False,nominal_tool_clearance_mm=.35,required_clearance_mm=.3,simplify_mm=.02,
        required_component_z_mm=[-.4,2.5],scope='Actual baseline nominal-tool-clearance intrusion and actual final required per-class clearance; no tolerance waiver')
    path=ROOT/'.codex-tmp/registered-housing-fit/lower/left-clearance-diagnosis.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'}),flush=True)
if __name__=='__main__':main()
