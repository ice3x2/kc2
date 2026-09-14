"""CON-ARCH-006 fresh right lower native equality using explicit strata parent.

Old native reviewer is frozen; its binding/acceptance functions remain executed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from tools.kc2_registered_native import preflight_job,revalidate_job,digest
from tools.kc2_lower_native_identity import native_output
from tools.review_kc2_registered_native import check_source_binding,acceptance_errors
from tools.review_kc2_lower_strata import validate_import
from tools.kc2_magnetic_subset import nd_cut,bounds

ROOT=Path(__file__).resolve().parents[1]

def match_bodies(solids,record):
    parts=record.get('parts',[])
    if len(solids)!=2 or len(parts)!=2:raise ValueError('Expected two actual and declared bodies')
    remaining=list(solids);result=[]
    for i,part in enumerate(parts):
        wanted=part.get('bounds_mm',[])
        if type(part.get('index')) is not int or part['index']!=i or len(wanted)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in wanted):
            raise ValueError('Invalid declared A/B identity')
        matches=[s for s in remaining if max(abs(x-y) for x,y in zip(bounds(s),wanted))<=1e-6]
        if len(matches)!=1:raise ValueError('Native/source body bounds ownership missing or ambiguous')
        selected=matches[0];remaining.remove(selected);result.append(selected)
    if result[0].Center().x>=result[1].Center().x:raise ValueError('A/B ownership reversed')
    return result

def compare_body(source,actual,index):
    missing=nd_cut(source,actual);extra=nd_cut(actual,source)
    errors=[];metrics={}
    for name,shape in (('missing',missing),('extra',extra)):
        value=shape.Volume();valid=shape.isValid()
        metrics[name+'_mm3']=value;metrics[name+'_result_valid']=valid
        metrics[name+'_result_solids']=len(shape.Solids());metrics[name+'_result_faces']=len(shape.Faces())
        if type(value) not in (int,float) or not math.isfinite(value) or value<0 or value>.002 or not valid:
            errors.append('Invalid or nonmatching '+name+' material')
        if value==0 and (shape.Solids() or shape.Faces()):errors.append('Nonempty zero-volume '+name+' residue')
    return dict(part=index,status='failed' if errors else 'pass',errors=errors,
        source_bounds_mm=bounds(source),native_bounds_mm=bounds(actual),
        comparison_method='per_matched_solid_non_destructive_symmetric_cut',**metrics)

def review(variant):
    if variant not in ('normal','magnetic'):raise ValueError('Only right normal/magnetic accepted')
    import cadquery as cq
    from tools.kc2_receiver_bundle_transfer import validate
    label='lower:right:'+variant;job=preflight_job(ROOT,label);folder=job['source'].parent
    bindings=dict(job['source_sha256'])
    def bind(path,expected=None):
        path=path.resolve()
        if not path.is_relative_to(ROOT.resolve()):raise ValueError('Native input escapes root')
        key=path.relative_to(ROOT).as_posix();sha=digest(path)
        if expected is not None and expected!=sha or key in bindings and bindings[key]!=sha:
            raise ValueError('Changed/conflicting native input '+key)
        bindings[key]=sha;return path
    def read(name):
        from tools.kc2_registered_release_gate import safe_relative
        safe_relative(name);path=bind(ROOT/name);data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=bindings[path.relative_to(ROOT).as_posix()]:raise ValueError('Native input changed while reading')
        return data
    nativepath=bind(folder/'native-generation.json');native=json.loads(nativepath.read_text())
    n=native_output(native,'right',variant,job['record_sha256'],job['step_sha256'])
    stem=job['source'].stem
    if (native.get('phase')!='complete' or set(native.get('outputs',{}))!={label}
        or type(n.get('expected_body_count')) is not int or n['expected_body_count']!=2
        or n.get('source_step')!=job['source'].name or n.get('generation_record')!=job['record_path'].name
        or n.get('readback_step')!=stem+'.native-readback.step' or n.get('f3d')!=stem+'.f3d'
        or len(n.get('source_solids',[]))!=2 or len(n.get('reopened_solids',[]))!=2):
        raise ValueError('Wrong complete native output identity')
    for name,sha in native['source_sha256'].items():bind(ROOT/name,sha)
    readback=bind(folder/n['readback_step'],n['readback_sha256']);bind(folder/n['f3d'],n['f3d_sha256'])
    proofpath=folder.parent/'right-receiver-strata-transfer.json';proof=json.loads(read(proofpath.relative_to(ROOT).as_posix()))
    if validate(proof,read,kind='strata_bundle') is not True:raise ValueError('Right source proof did not qualify')
    check_source_binding(proof,{job['source'].relative_to(ROOT).as_posix():job['step_sha256'],
                                job['record_path'].relative_to(ROOT).as_posix():job['record_sha256']})
    for name,sha in proof['source_sha256'].items():bind(ROOT/name,sha)
    for name in ('review_kc2_right_lower_native','test_review_kc2_right_lower_native',
                 'review_kc2_registered_native','test_review_kc2_registered_native',
                 'kc2_registered_native','kc2_lower_native_identity','test_kc2_lower_native_identity',
                 'review_kc2_lower_strata','kc2_lower_strata','test_kc2_lower_strata',
                 'kc2_magnetic_subset','test_kc2_magnetic_subset','kc2_receiver_bundle_transfer','test_kc2_receiver_bundle_transfer'):
        bind(ROOT/'tools'/(name+'.py'))
    record=json.loads(job['record_path'].read_text())
    print('Import entire source and native STEP with topology ownership',variant,flush=True)
    source_shape=cq.importers.importStep(str(job['source'])).val()
    actual_shape=cq.importers.importStep(str(readback)).val()
    sources=match_bodies(validate_import(source_shape),record);actual=match_bodies(validate_import(actual_shape),record)
    parts=[]
    for i,(a,b) in enumerate(zip(sources,actual)):
        print('Actual independent ND native material difference',variant,i,flush=True)
        parts.append(compare_body(a,b,i))
    revalidate_job(ROOT,dict(source_sha256=bindings))
    errors=acceptance_errors(proof,parts)
    result=dict(status='failed' if errors else 'pass',errors=errors,selected_job=label,
        requirements=['CON-ARCH-006','OPS-ARCH-006'],source_sha256=bindings,parts=parts,
        independent_geometry_verified=not errors,physical_qualified=False,
        method='right_source_strata_transfer_plus_whole_import_and_per_solid_ND_native_equality',
        source_actual_report=proofpath.relative_to(ROOT).as_posix(),source_actual_sha256=digest(proofpath),
        whole_source_import_valid_closed_positive=True,whole_native_import_valid_closed_positive=True,
        whole_import_topology_covered_by_two_solids=True,body_ownership='unique_declared_part_bounds_not_nearest',
        inherited_acceptance_helpers=['check_source_binding','acceptance_errors'])
    (folder/'native-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],errors,flush=True);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('variant',choices=('normal','magnetic'));args=parser.parse_args()
    raise SystemExit(0 if review(args.variant)['status']=='pass' else 1)
