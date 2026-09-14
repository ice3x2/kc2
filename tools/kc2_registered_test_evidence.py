"""OPS-ARCH-006 executed final regressions, direct source/report hash freeze.

Final collection requires all actual reports to exist first. It never upgrades
development provenance recursively and never treats missing tests as success.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from tools.kc2_registered_release_gate import sha_bytes,STAGE,passed,hash_string

CORE=['tools.test_publish_kc2_registered_housings','tools.test_kc2_registered_release_gate',
      'tools.test_kc2_registered_transaction','tools.test_kc2_registered_test_evidence','tools.test_kc2_registered_guide',
      'tools.test_kc2_step_whitespace','tools.test_kc2_registered_step_publication']
# Explicit inventory remains stable after commit (not based on untracked state).
CORE += ['tools.'+name for name in '''
test_kc2_actual_sections test_kc2_central_fit test_kc2_central_flexure
test_kc2_joined_sweep test_kc2_lower_central_relief test_kc2_lower_floor
test_kc2_lower_native_identity test_kc2_lower_native_transfer test_kc2_lower_split_extension test_kc2_magnetic_entry
test_kc2_perimeter_wall test_kc2_profile_split test_kc2_registered_git_bytes
test_kc2_registered_native test_kc2_registered_upper test_kc2_registered_wall_plan
test_kc2_required_lower_clearance test_kc2_split_fit_relief test_kc2_wall_registration
test_review_kc2_ab_ligament test_review_kc2_actual_envelopes
test_review_kc2_integrated_central test_review_kc2_lower_split
test_review_kc2_lower_voids_v2 test_review_kc2_magnetic_entry
test_review_kc2_profile_split_cad test_review_kc2_registered_assembly
test_review_kc2_registered_lower test_review_kc2_registered_mesh
test_review_kc2_registered_native test_review_kc2_registered_upper
test_review_kc2_registered_upper_faces test_stage_kc2_ab_lower
test_stage_kc2_ab_relief test_stage_kc2_central_features
test_stage_kc2_lower_top_clearance test_stage_kc2_registered_lower
test_stage_kc2_registered_upper test_stage_kc2_right_magnetic_from_normal
test_review_kc2_registered_upper_mask_contract test_review_kc2_registered_upper_direct
test_kc2_solid_clearance test_kc2_component_local_certificate test_kc2_lower_predicate_bundle
test_kc2_receiver_cleanup test_review_kc2_receiver_cleanup test_kc2_receiver_void_transfer
test_kc2_receiver_snapshot
test_kc2_receiver_bundle_transfer
test_kc2_lower_strata test_kc2_magnetic_subset
test_kc2_lower_strata_bundle
test_kc2_floor_capture_gate test_kc2_registered_void_proof
test_review_kc2_right_lower_native test_kc2_stl_zero_area_filter
test_kc2_left_central_relief test_stage_kc2_left_central_relief test_review_kc2_left_central_voids
test_kc2_floor_capture test_review_kc2_floor_receiver test_diagnose_kc2_receiver_floor_prism
'''.split()]

def execution_result(returncode,stdout,stderr):
    if returncode!=0:raise ValueError('Regression subprocess failed')
    text=stdout+'\n'+stderr
    counts=re.findall(r'^Ran (\d+) tests? in [0-9.]+s$',text,re.MULTILINE)
    if len(counts)!=1 or int(counts[0])<=0 or not re.search(r'^OK\s*$',text,re.MULTILINE):
        raise ValueError('Complete successful test-run summary absent; skipped tests not accepted')
    if re.search(r'\b(?:FAILED|ERROR|skipped=|expected failures=|unexpected successes=)',text):
        raise ValueError('Incomplete regression qualification')
    return int(counts[0])

def selected_modules(records):
    tests=set(CORE)
    for record in records.values():
        for source in record.get('source_sha256',{}):
            if source.startswith('tools/test_') and source.endswith('.py'):
                tests.add(source[:-3].replace('/','.'))
    return sorted(tests)

def check_evidence(record,modules,reports):
    passed(record)
    if record.get('test_modules')!=sorted(set(modules)):raise ValueError('Wrong complete test module inventory')
    if record.get('report_sha256')!=reports:raise ValueError('Tests are not bound to current actual reports')
    if record.get('tests_run')!=execution_result(record.get('returncode'),record.get('stdout',''),record.get('stderr','')):
        raise ValueError('Wrong executed test count')
    for module in modules:
        name=module.replace('.','/')+'.py';hash_string(record.get('source_sha256',{}).get(name))
    for name,sha in reports.items():
        if record.get('source_sha256',{}).get(name)!=sha:raise ValueError('Report source binding omitted')

def collect(root):
    from tools.publish_kc2_registered_housings import report_paths,contained,PUBLICATION_DOCS,NEW_GUIDE,check_guide
    root=Path(root).resolve();records={};reports={};frozen={}
    for label,name in report_paths().items():
        if label=='tests':continue
        data=contained(root,name).read_bytes();row=json.loads(data)
        if label.endswith(':generation'):
            if row.get('status')!='generated_pending_independent_review':raise ValueError('Incomplete generation '+label)
        else:passed(row)
        records[label]=row;reports[name]=sha_bytes(data);frozen[name]=reports[name]
        # Freeze direct current Python source only. Cached JSON is provenance,
        # not a reason to demand its obsolete nested sources remain current.
        for source,expected in row.get('source_sha256',{}).items():
            if source.endswith('.py'):
                actual=sha_bytes(contained(root,source).read_bytes())
                if actual!=expected:raise ValueError('Current checker source changed '+source)
                frozen[source]=actual
    modules=selected_modules(records)
    for target,source in PUBLICATION_DOCS.items():
        data=contained(root,source).read_bytes()
        if target==NEW_GUIDE:check_guide(data.decode('utf-8'))
        frozen[source]=sha_bytes(data)
    for module in modules:
        name=module.replace('.','/')+'.py';frozen[name]=sha_bytes(contained(root,name).read_bytes())
    for name in ('tools/kc2_registered_test_evidence.py','tools/publish_kc2_registered_housings.py',
                 'tools/kc2_registered_release_gate.py','tools/kc2_step_whitespace.py'):
        frozen[name]=sha_bytes(contained(root,name).read_bytes())
    started=time.time();command=[sys.executable,'-B','-m','unittest','-v',*modules]
    print('Execute final source-bound tests:',len(modules),'modules',flush=True)
    result=subprocess.run(command,cwd=root,text=True,capture_output=True)
    errors=[];count=0
    try:count=execution_result(result.returncode,result.stdout,result.stderr)
    except ValueError as exc:errors.append(str(exc))
    for name,sha in frozen.items():
        if sha_bytes(contained(root,name).read_bytes())!=sha:errors.append('Source changed during executed tests: '+name)
    record=dict(status='pass' if not errors else 'fail',errors=errors,test_modules=modules,tests_run=count,
      returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,command=command,
      elapsed_seconds=time.time()-started,report_sha256=reports,source_sha256=frozen,
      requirements=['CON-ARCH-006','OPS-ARCH-006'],physical_qualified=False)
    path=contained(root,STAGE+'/test-execution.json');path.write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    result=collect(args.root);print(result['status'],result['tests_run'],result['errors']);raise SystemExit(result['status']!='pass')
