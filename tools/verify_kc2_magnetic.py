"""CON-ARCH-006 / OPS-ARCH-006 source-bound optional mechanical release check."""
import hashlib
import io
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODELS=ROOT/'hardware/MODELS'
REPORT=ROOT/'docs/reports/magnetic-20260908'
EXPECTED_MESH_NAMES={
    'kc2_left_lower_housing_magnetic.stl',
    'kc2_right_lower_housing_part_a_magnetic.stl',
    'kc2_right_lower_housing_part_b_magnetic.stl',
    'kc2_magnet_fit_coupon_magnetic.stl',
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def baseline_errors(records):
    expected={'tests.json','report-tests.json','audit-budget-test.json'}
    if len(records)!=3 or {r.get('baseline_suite') for r in records}!=expected or any(r.get('exit_code')!=0 for r in records):
        return ['Incomplete or failed baseline regression suites']
    return []


def contract_errors(r):
    errors=[]
    for field,value in [('diameter_mm',2.4),('depth_mm',1.2),('center_z_mm',.75),
                        ('minimum_back_wall_mm',.6),('web_top_bottom_rim_mm',.55),
                        ('physical_qualified',False),('digital_delta_status','pass')]:
        if r.get(field)!=value:errors.append('Contract mismatch: '+field)
    pairs=r.get('pairs',[])
    if len(pairs) not in [1,2]:errors.append('Missing pair or wrong pair count')
    if len(pairs)==1 and not r.get('fallback_reason'):errors.append('Unjustified single pair')
    if len(pairs)==2 and abs(pairs[0]['y']-pairs[1]['y'])<6:errors.append('Pockets too close')
    gaps=r.get('magnet_face_gap_mm',[])
    if len(gaps)!=len(pairs) or any(abs(g-p['gap']-.4)>1e-6 for g,p in zip(gaps,pairs)):
        errors.append('Incorrect magnet face air gap')
    for side,sign,solids,supports,mounts in [('left',1,1,31,8),('right',-1,2,39,9)]:
        s=r.get('sides',{}).get(side,{})
        pockets=s.get('pockets',[])
        if len(pockets)!=len(pairs) or any(p['sign']!=sign or p['y']!=pair['y'] for p,pair in zip(pockets,pairs)):
            errors.append(side+': wrong axis/count/alignment')
        if s.get('protected_primary_supports')!=supports or s.get('protected_mounting_lands')!=mounts:
            errors.append(side+': support/land count')
        d=s.get('delta',{})
        if d.get('errors')!=[] or d.get('solids')!=solids:errors.append(side+': CAD failure')
        for key in ['added_mm3','off_pocket_removed_mm3','obstructed_bore_mm3']:
            if not math.isfinite(d.get(key,math.inf)) or d.get(key,math.inf)>.002:
                errors.append(side+': '+key)
        if abs(d.get('actual_removed_mm3',0)-len(pairs)*math.pi*1.2**2*1.2)>.002:
            errors.append(side+': wrong subtraction volume')
    meshes=r.get('meshes',{})
    if set(meshes)!=EXPECTED_MESH_NAMES:errors.append('Missing STL output')
    for name,m in meshes.items():
        if m.get('watertight') is not True or m.get('winding_consistent') is not True or m.get('shells')!=1:
            errors.append('Invalid STL: '+name)
    return errors


def main():
    errors=[]
    cad=json.loads((REPORT/'cad-delta.json').read_text(encoding='utf8'))
    errors+=contract_errors(cad)
    manifest=json.loads((MODELS/'kc2_housing_manifest_magnetic.json').read_text(encoding='utf8'))
    if manifest!=cad:errors.append('CAD report and model manifest differ')
    bindings=dict(cad['source_bindings'])
    regression_path=REPORT/'baseline-regressions.json'
    regressions=json.loads(regression_path.read_text(encoding='utf8'))
    errors+=baseline_errors(regressions)
    bindings[str(regression_path.relative_to(ROOT))]=sha(regression_path)
    before=json.loads((REPORT/'originals-before.json').read_text(encoding='utf8'))
    bindings.update(before)
    # Reuse the exact unchanged r5 component-clearance proof only after checking
    # every one of its original raw-byte bindings. A strictly subtractive delta
    # cannot worsen those plastic/component intersections. Magnet envelope fits
    # inside each checked cavity, above/below which plastic remains intact.
    baseline_path=ROOT/'docs/reports/continuous-web-20260908-r5/populated-cad.json'
    baseline=json.loads(baseline_path.read_text(encoding='utf8'))
    if baseline['errors'] or not baseline['sources_unchanged']:
        errors.append('Original populated CAD baseline failed')
    bindings.update(baseline['source_sha256'])
    bindings[str(baseline_path.relative_to(ROOT))]=sha(baseline_path)
    native=json.loads((MODELS/'kc2_fusion_export_result_magnetic.json').read_text(encoding='utf8'))
    if native.get('status')!='pass' or set(native.get('outputs',{}))!={'left','right'}:
        errors.append('Fusion export/reopen failed or missing')
    for side,s in cad['sides'].items():
        bindings[f'hardware/MODELS/kc2_{side}_lower_housing_magnetic.step']=s['step_sha256']
    for name,m in cad['meshes'].items():bindings['hardware/MODELS/'+name]=m['sha256']
    for side,n in native['outputs'].items():
        if n.get('solid_round_trip_verified') is not True:errors.append(side+': native round-trip flag')
        bindings[n['source_step']]=n['source_step_sha256'];bindings[n['f3d']]=n['f3d_sha256']
        source=n['source_solids'];reopened=n['archive_reimport_solids']
        expected=1 if side=='left' else 2
        if len(source)!=expected or len(reopened)!=expected:errors.append(side+': native count')
        unmatched=list(reopened)
        for s in source:
            match=next((a for a in unmatched if all(abs(x-y)<.001 for x,y in zip(s['bounds_mm'],a['bounds_mm']))
                        and abs(s['volume_mm3']-a['volume_mm3'])<max(.001,s['volume_mm3']*1e-6)),None)
            if match is None:errors.append(side+': native dimensions/volume')
            else:unmatched.remove(match)
        stl_volume=sum(m['brep_volume_mm3'] for name,m in cad['meshes'].items() if name.startswith('kc2_'+side+'_'))
        if abs(sum(s['volume_mm3'] for s in source)-stl_volume)>max(.01,stl_volume*1e-6):
            errors.append(side+': native does not match CQ volume')
    bindings['tools/fusion/KC2MagneticToF3D/KC2MagneticToF3D.py']=native['script_sha256']
    for path,expected in bindings.items():
        p=ROOT/path
        if not p.is_file() or sha(p)!=expected:errors.append('Stale or missing source/output: '+path)
    buffer=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromNames(['tools.test_kc2_magnetic_housing','tools.test_verify_kc2_magnetic'])
    tests=unittest.TextTestRunner(stream=buffer,verbosity=2).run(suite)
    if not tests.wasSuccessful():errors.append('Regression tests failed')
    test_result={'requirements':['CON-ARCH-006','OPS-ARCH-006'], 'tests_run':tests.testsRun,
                 'pass':tests.wasSuccessful(), 'output':buffer.getvalue(),
                 'initial_red':'Missing generator, missing magnetic-only Fusion exporter and missing evidence verifier were each executed and failed before implementation.'}
    (REPORT/'tests.json').write_text(json.dumps(test_result,indent=2)+'\n',encoding='utf8')
    for path in [Path(__file__),ROOT/'tools/test_verify_kc2_magnetic.py',REPORT/'tests.json',
                 REPORT/'cad-delta.json',MODELS/'kc2_housing_manifest_magnetic.json',
                 MODELS/'kc2_fusion_export_result_magnetic.json',MODELS/'PRINT_magnetic.md']:
        bindings[str(path.relative_to(ROOT)).replace('\\','/')]=sha(path)
    result={'requirements':['CON-ARCH-006','OPS-ARCH-006'], 'errors':errors,
            'status':'pass' if not errors else 'failed', 'original_files_checked':len(before),
            'source_bindings':bindings, 'tests_run':tests.testsRun,
            'baseline_component_proof':'Unchanged source-bound r5 populated CAD plus exact subtraction-only STEP delta; no added plastic. Pocket plan reserves and original support counts checked at generation.',
            'physical_qualified':False,'pending':cad['pending']}
    (REPORT/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({'status':result['status'],'errors':errors,'tests_run':tests.testsRun,
                      'original_files_checked':len(before)},indent=2))
    raise SystemExit(bool(errors))


if __name__=='__main__':main()
