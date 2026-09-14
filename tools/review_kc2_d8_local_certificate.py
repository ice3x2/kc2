"""CON-ARCH-006 exact D8-only alternative evidence; retain raw failure metrics."""
import hashlib,json
from pathlib import Path
from shapely import wkt
from shapely.geometry import box
from tools.kc2_component_local_certificate import certify_local,inspect_tool_prism,verify_bindings,validate_certificate
from tools.kc2_required_lower_clearance import required_envelope
ROOT=Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    from tools.review_kc2_local_covers import prism
    stage=ROOT/'.codex-tmp/registered-housing-fit/lower'
    distance_path=stage/'right-component-distance-review.json';raw_path=stage/'right-void-review.json'
    distance=json.loads(distance_path.read_text());raw=json.loads(raw_path.read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    required_paths=[];inputs={}
    for variant in ('normal','magnetic'):
        folder=stage/('right-'+variant);gp=folder/'generation.json'
        sp=folder/('kc2_right_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step')
        g=json.loads(gp.read_text())
        if g['status']!='generated_pending_independent_review' or digest(sp)!=g['outputs'][sp.name]:
            raise ValueError('Current source identity mismatch')
        inputs[variant]=(gp,sp);required_paths.extend([gp.relative_to(ROOT).as_posix(),sp.relative_to(ROOT).as_posix()])
    verify_bindings(ROOT,distance['source_sha256'],required_paths)
    verify_bindings(ROOT,raw['source_sha256'],required_paths)
    if distance['schema']!='lower-component-distance-v1' or distance['status'] not in ('pass','fail'):
        raise ValueError('Original distance inventory incomplete')
    for variant in inputs:
        rows=distance['variants'][variant]['pairs']
        if len(rows)!=306 or {(r['part'],r['tool']) for r in rows}!={(i,j) for i in range(2) for j in range(153)}:
            raise ValueError('Original distance pair inventory incomplete')
        if any(not r['clear'] and (r['part'],r['tool'])!=(0,2) for r in rows):
            raise ValueError('New non-D8 distance failure requires investigation')
    paths=[Path(__file__),distance_path,raw_path]+[ROOT/'tools'/name for name in (
        'kc2_component_local_certificate.py','test_kc2_component_local_certificate.py',
        'kc2_required_lower_clearance.py','review_kc2_local_covers.py','kc2_solid_clearance.py','kc2_actual_sections.py')]
    paths += [ROOT/name for name in distance['source_sha256']]
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    classes={k:wkt.loads(v) for k,v in raw['component_envelope']['raw_classes_wkt'].items()}
    expected=required_envelope(classes)
    if expected.symmetric_difference(wkt.loads(raw['component_envelope']['required_union_wkt'])).area>1e-9:
        raise ValueError('Required geometry changed')
    print('actual153tool full XY/Z identity inventory',flush=True)
    tool_shape=prism(expected,-.4,2.5);tools=tool_shape.Solids();polygons=list(expected.geoms)
    if len(tools)!=153 or len(polygons)!=153:raise ValueError('Required tool count changed')
    inventory=[]
    for i,(tool,polygon) in enumerate(zip(tools,polygons)):
        row=inspect_tool_prism(tool,polygon,i)
        if max(row['actual_section_missing_mm2'],row['actual_section_extra_mm2'])>1e-8 or abs(row['actual_volume_mm3']-polygon.area*2.9)>.002:
            raise ValueError('Actual tool order/geometry mismatch '+str(i))
        for variant in inputs:
            for part in range(2):
                pair=next(r for r in distance['variants'][variant]['pairs'] if r['part']==part and r['tool']==i)
                padded=[v-1e-5 if j<3 else v+1e-5 for j,v in enumerate(row['actual_bounds_mm'])]
                if max(abs(a-b) for a,b in zip(padded,pair['b_bounds_mm']))>1e-8:
                    raise ValueError('Raw distance tool identity/order mismatch')
        inventory.append(row)
        if i%20==0:print('tool identity',i,flush=True)
    actual_d8=inventory[2]['actual_bounds_mm']
    wanted=[15.393103061379296,31.918103061379306,-.4,18.156896938620715,38.131896938620706,2.5]
    if max(abs(a-b) for a,b in zip(actual_d8,wanted))>1e-8:raise ValueError('Unexpected D8 tool identity')
    cases=[];errors=[];xy=polygons[2];roi=box(xy.bounds[0]-1,xy.bounds[1]-1,xy.bounds[2]+1,xy.bounds[3]+1)
    for variant,(gp,sp) in inputs.items():
        print('fresh actual D8 local certificate',variant,flush=True)
        parts=cq.importers.importStep(str(sp)).val().Solids()
        if len(parts)!=2:raise ValueError('Wrong actual subject part count')
        local=certify_local(parts[0],tools[2],xy,roi)
        if not local['eligible']:errors.extend(variant+': '+e for e in local['errors'])
        cases.append(dict(variant=variant,part=0,tool=2,step_path=sp.relative_to(ROOT).as_posix(),step_sha256=digest(sp),
            generation_path=gp.relative_to(ROOT).as_posix(),generation_sha256=digest(gp),local=local))
    verify_bindings(ROOT,frozen,required_paths)
    result=dict(requirements=['CON-ARCH-006'],schema='right-d8-local-certificate-v1',status='fail' if errors else 'pass',
        errors=errors,source_sha256=frozen,actual_tool_count=153,required_z_mm=[-.4,2.5],required_tool_union_wkt=expected.wkt,
        tool_inventory=inventory,cases=cases,physical_qualified=False,
        original_distance_report=distance_path.relative_to(ROOT).as_posix(),original_boolean_report=raw_path.relative_to(ROOT).as_posix(),
        scope='Exact right D8 part0/tool2 only, bothvariants; no raw distance or Boolean numeric result replaced')
    if not errors:validate_certificate(result)
    (stage/'right-d8-local-certificate.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],errors,flush=True)
    return result


if __name__=='__main__':raise SystemExit(bool(run()['errors']))
