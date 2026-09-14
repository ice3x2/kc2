"""CON-ARCH-006 fresh immutable exported SOLID/SOLID required-space proof.

Independent of Boolean volume classification. Original failed Boolean evidence
is retained and bound; this does not assert its root cause was established.
"""
import hashlib, json, math
from pathlib import Path
from shapely import wkt
from tools.kc2_required_lower_clearance import required_envelope
from tools.review_kc2_local_covers import prism
from tools.kc2_solid_clearance import clearance_inventory, BOUND_PADDING_MM, POSITIVE_MARGIN_MM
ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    stage=ROOT/'.codex-tmp/registered-housing-fit/lower'
    failed_path=stage/'right-void-review.json'
    original=json.loads(failed_path.read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    paths=[Path(__file__),failed_path]+[ROOT/'tools'/name for name in (
        'kc2_solid_clearance.py','test_kc2_solid_clearance.py','kc2_required_lower_clearance.py',
        'test_kc2_required_lower_clearance.py','review_kc2_local_covers.py')]
    for name,sha in original['source_sha256'].items():
        p=ROOT/name
        if digest(p)!=sha:raise ValueError('Stale original evidence '+name)
        paths.append(p)
    raw={name:wkt.loads(value) for name,value in original['component_envelope']['raw_classes_wkt'].items()}
    xy=required_envelope(raw)
    if xy.symmetric_difference(wkt.loads(original['component_envelope']['required_union_wkt'])).area>1e-9:
        raise ValueError('Required tool geometry changed')
    records={}
    for variant in ('normal','magnetic'):
        folder=stage/('right-'+variant);gp=folder/'generation.json'
        g=json.loads(gp.read_text());sp=folder/('kc2_right_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step')
        if g['status']!='generated_pending_independent_review' or digest(sp)!=g['outputs'][sp.name]:
            raise ValueError('Incomplete/changed current source')
        paths.extend([gp,sp]);records[variant]=(g,sp)
        for name,sha in g['source_sha256'].items():
            p=ROOT/name
            if digest(p)!=sha:raise ValueError('Stale current source '+name)
            paths.append(p)
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('construct exact required tool; no Boolean intersections',flush=True)
    compound=prism(xy,-.4,2.5);tools=compound.Solids()
    if not compound.isValid() or len(tools)!=153 or abs(sum(t.Volume() for t in tools)-xy.area*2.9)>.002:
        raise ValueError('Invalid required tool inventory/volume')
    variants={};errors=[]
    for variant,(_,sp) in records.items():
        print('fresh actual solid-solid distance',variant,flush=True)
        parts=cq.importers.importStep(str(sp)).val().Solids()
        if len(parts)!=2:raise ValueError('Unexpected part inventory')
        def progress(row):
            if row['tool']%20==0 or not row['clear']:
                print(variant,row['part'],row['tool'],row['method'],row.get('distance_mm',row.get('distance_lower_bound_mm')),flush=True)
        rows=clearance_inventory(parts,tools,progress)
        if len(rows)!=306 or {(r['part'],r['tool']) for r in rows}!={(i,j) for i in range(2) for j in range(153)}:
            raise ValueError('Incomplete pair evidence')
        failures=[r for r in rows if not r['clear']]
        if failures:errors.append(variant+' required component clearance not proved')
        variants[variant]=dict(body_count=2,tool_count=153,pair_count=306,all_clear=not failures,
            minimum_distance_lower_bound_mm=min(r.get('distance_mm',r.get('distance_lower_bound_mm')) for r in rows),pairs=rows)
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:
        raise ValueError('Source changed during distance proof')
    result=dict(requirements=['CON-ARCH-006'],schema='lower-component-distance-v1',status='fail' if errors else 'pass',
        errors=errors,source_sha256=frozen,side='right',variants=variants,
        tool=dict(valid=True,solid_count=153,plan_area_mm2=xy.area,expected_volume_mm3=xy.area*2.9,
                  actual_volume_mm3=sum(t.Volume() for t in tools),required_clearance_mm=.3,
                  conservative_offset_mm=.301,circumscribed_radius_mm=.301/math.cos(math.pi/16),z_mm=[-.4,2.5]),
        bound_padding_mm=BOUND_PADDING_MM,positive_margin_mm=POSITIVE_MARGIN_MM,
        original_boolean_status=original['status'],original_boolean_failure_retained=True,
        boolean_root_cause='not established by this distance proof',physical_qualified=False)
    (stage/'right-component-distance-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],errors,flush=True)
    return result


if __name__=='__main__':raise SystemExit(bool(run()['errors']))
