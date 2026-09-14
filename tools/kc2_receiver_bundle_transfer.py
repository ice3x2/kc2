"""CON-ARCH-006 explicit post-cleanup predicate inheritance; no report writer.

The original failed Boolean and independent component certificate are retained.
Only exact bounded subtraction permits set-disjointness inheritance.
"""
import importlib
import json
from pathlib import Path
from tools.kc2_registered_release_gate import STAGE,sha_bytes,safe_relative,stem,passed
from tools import kc2_lower_predicate_bundle as bundle
from tools import review_kc2_receiver_cleanup as delta

SCHEMA='right-receiver-bundle-predicate-transfer-v1'
CACHE=STAGE+'/lower-development/receiver-cleanup-inputs'
SNAPSHOT=CACHE+'/snapshot-map.json'
PROOF=STAGE+'/lower/right-receiver-cleanup-review.json'
MAPPING={**{f'{STAGE}/lower/right-{v}':f'{CACHE}/right-{v}' for v in bundle.VARIANTS},
    **{f'{STAGE}/lower/{n}':f'{CACHE}/{n}' for n in ('right-void-review.json',
       'right-component-distance-review.json','right-d8-local-certificate.json','right-predicate-bundle.json')},
    '.codex-tmp/receiver_cleanup_candidate.py':CACHE+'/provenance/receiver_cleanup_candidate.py'}


def parent_config(kind):
    helpers=('kc2_lower_predicate_bundle','kc2_registered_release_gate',
             'kc2_required_lower_clearance','kc2_component_local_certificate')
    if kind=='predicate_bundle':
        return dict(module='kc2_lower_predicate_bundle',output=bundle.OUTPUT,
                    schema=SCHEMA,method='complete_pair_inventory_and_local_prism_certificate',
                    helpers=helpers,mapping=MAPPING)
    if kind=='strata_bundle':
        mapping={k:v for k,v in MAPPING.items() if not k.endswith((
            'right-component-distance-review.json','right-d8-local-certificate.json','right-predicate-bundle.json'))}
        for name in ('right-normal-strata-review.json','right-magnetic-subset-review.json','right-strata-predicate-bundle.json'):
            mapping[STAGE+'/lower/'+name]=CACHE+'/'+name
        return dict(module='kc2_lower_strata_bundle',output=STAGE+'/lower/right-strata-predicate-bundle.json',
                    schema='right-receiver-strata-predicate-transfer-v1',
                    method='whole_normal_z_strata_plus_actual_magnetic_subset',
                    helpers=helpers+('kc2_lower_strata_bundle','kc2_lower_strata','kc2_magnetic_subset'),mapping=mapping)
    raise ValueError('Unknown explicit transfer parent kind')


def archived(name,mapping=None):
    safe_relative(name)
    mapping=MAPPING if mapping is None else mapping
    matches=[(p,r) for p,r in mapping.items() if name==p or name.startswith(p+'/')]
    target=matches[0][1]+name[len(matches[0][0]):] if matches else name
    safe_relative(target)
    return target


def check_delta(proof,parent):
    passed(proof)
    if (proof.get('schema')!='right-receiver-cleanup-delta-v2' or proof.get('side')!='right'
        or proof.get('native_readback') is not False or proof.get('actual_exported_STEP_reimported') is not True
        or proof.get('cut_z_mm')!=[-1,2.5] or proof.get('ys_mm')!=[73.25,86.25]
        or proof.get('old_v2_exact_zero') is not False or proof.get('parent_predicates_qualified') is not True
        or proof.get('strict_transfer_eligible') is not True):raise ValueError('Wrong independent delta semantics')
    if json.dumps(proof.get('parent_evidence'),sort_keys=True)!=json.dumps(parent,sort_keys=True):
        raise ValueError('Independent delta parent differs')
    if not delta.transfer_eligible(proof.get('variants',{}),proof.get('paired_removal',{}),True):
        raise ValueError('Nonzero/incomplete actual delta; direct review required')


def assemble(read,kind='predicate_bundle'):
    config=parent_config(kind)
    def archive(name):return archived(name,config['mapping'])
    bindings={}
    def bound(name):
        safe_relative(name);data=read(name);sha=sha_bytes(data)
        if name in bindings and bindings[name]!=sha:raise ValueError('Source changed during qualification')
        bindings[name]=sha;return data
    def merge(sources):
        if not isinstance(sources,dict) or not sources:raise ValueError('Missing source closure')
        for name,sha in sources.items():
            if sha_bytes(bound(name))!=sha:raise ValueError('Stale source '+name)
    snapshot=json.loads(bound(SNAPSHOT));historical=snapshot.get('historical_original_sha256',{})
    if (snapshot.get('status')!='verified_historical_snapshot' or snapshot.get('path_mapping')!=config['mapping']
        or snapshot.get('parent_proof_kind')!=kind or snapshot.get('parent_proof_path')!=config['output']):
        raise ValueError('Wrong immutable predicate parent resolver')
    remapped={archive(n):sha for n,sha in historical.items()}
    if not historical or len(remapped)!=len(historical) or remapped!=snapshot.get('source_sha256'):
        raise ValueError('Historical alias closure differs')
    merge(remapped)
    def historical_read(name):
        if name not in historical:raise ValueError('Unlisted historical identity')
        data=bound(archive(name))
        if sha_bytes(data)!=historical[name]:raise ValueError('Historical bytes changed')
        return data
    # The executed pure qualifiers must be the sealed revisions, not substitutes.
    for name in config['helpers']:
        module=importlib.import_module('tools.'+name);logical='tools/'+name+'.py'
        if Path(module.__file__).read_bytes()!=historical_read(logical) or bound(logical)!=historical_read(logical):
            raise ValueError('Loaded/current qualifier differs from historical source')
    qualifier=importlib.import_module('tools.'+config['module'])
    record=json.loads(historical_read(config['output']))
    if qualifier.validate_bundle(record,historical_read) is not True:
        raise ValueError('Parent predicate bundle did not qualify')
    parent_sha=sha_bytes(historical_read(config['output']))
    if snapshot.get('parent_proof_sha256')!=parent_sha:raise ValueError('Parent selector hash differs')
    old=json.loads(historical_read(bundle.ORIGINAL))
    parent=dict(kind=kind,logical_report=config['output'],archived_report=archive(config['output']),sha256=parent_sha,
        original_v2_status='fail',original_v2_sha256=sha_bytes(historical_read(bundle.ORIGINAL)),
        old_v2_exact_zero=False,predicates_qualified=True,component_method=config['method'],
        component_common_volume_mm3=None,original_component_obstruction_mm3={v:old['variants'][v]['component_obstruction_mm3'] for v in bundle.VARIANTS})
    proof=json.loads(bound(PROOF));check_delta(proof,parent)
    required={SNAPSHOT:bindings[SNAPSHOT],**remapped}
    for variant in bundle.VARIANTS:
        folder=f'{STAGE}/lower/right-{variant}';name=stem('lower','right',variant)
        gp=folder+'/generation.json';sp=folder+'/'+name+'.step'
        previous=json.loads(historical_read(gp));historical_read(sp)
        if previous.get('outputs',{}).get(name+'.step')!=historical[sp]:raise ValueError('Wrong archived material identity')
        current=json.loads(bound(gp));bound(sp)
        if (current.get('status')!='generated_pending_independent_review' or current.get('side')!='right'
            or current.get('magnetic') is not (variant=='magnetic') or type(current.get('body_count')) is not int
            or current['body_count']!=2 or current.get('outputs',{}).get(name+'.step')!=bindings[sp]):
            raise ValueError('Wrong final material identity')
        merge(current.get('source_sha256'));required.update({gp:bindings[gp],sp:bindings[sp]})
    for name in ('review_kc2_receiver_cleanup','test_review_kc2_receiver_cleanup',
                 'review_kc2_local_covers','kc2_lower_central_relief','kc2_magnetic_entry'):
        path='tools/'+name+'.py';required[path]=sha_bytes(bound(path))
    if bound('tools/review_kc2_receiver_cleanup.py')!=Path(delta.__file__).read_bytes():raise ValueError('Executed delta qualifier changed')
    if any(proof.get('source_sha256',{}).get(n)!=sha for n,sha in required.items()):
        raise ValueError('Independent delta lacks exact parent/final/code closure')
    merge(proof.get('source_sha256'))
    for name in ('kc2_receiver_bundle_transfer','test_kc2_receiver_bundle_transfer'):
        bound('tools/'+name+'.py')
    if any(sha_bytes(read(n))!=sha for n,sha in bindings.items()):raise ValueError('Source freeze failed')
    return dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],schema=config['schema'],status='pass',errors=[],
        side='right',native_readback=False,full_v2_boolean_rerun=False,physical_qualified=False,
        parent_evidence=parent,independent_delta_report=PROOF,independent_delta_sha256=bindings[PROOF],
        historical_predicate_measurements=old['variants'],historical_magnet_measurements=old['magnet'],
        component_envelope=old['component_envelope'],
        component_clearance=dict(method='set_disjointness_inherited_from_exact_material_subset',
            disjointness_proved=True,parent_report=archive(config['output']),parent_sha256=parent_sha,
            computed_common_volume_mm3=None,new_component_boolean_rerun=False),
        derived_noncomponent_upper_bounds={v:{k:0. for k in bundle.RETAINED_ZERO} for v in bundle.VARIANTS},
        derived_magnet_bounds={k:0. for k in bundle.MAGNET_ZERO},paired_magnetic_delta_unchanged=True,
        source_sha256=bindings,limitations=['Historical component Boolean remains failed and unchanged',
            'Fresh floor/capture/entry/native verification remains mandatory; no physical qualification'])


def validate(record,read,kind='predicate_bundle'):
    expected=assemble(read,kind)
    if json.dumps(record,sort_keys=True)!=json.dumps(expected,sort_keys=True):
        raise ValueError('Derived proof differs from actual parent/subtraction chain')
    return True


def output_path(kind):
    parent_config(kind)
    suffix='strata' if kind=='strata_bundle' else 'bundle'
    return STAGE+'/lower/right-receiver-'+suffix+'-transfer.json'


def emit(root=None,kind='predicate_bundle'):
    root=(Path(root) if root is not None else Path(__file__).resolve().parents[1]).resolve()
    def read(name):
        safe_relative(name);path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Source escapes root')
        return path.read_bytes()
    record=assemble(read,kind)
    data=(json.dumps(record,indent=2)+'\n').encode()
    if any(sha_bytes(read(n))!=sha for n,sha in record['source_sha256'].items()):
        raise ValueError('Sources changed before transfer emission')
    output=(root/output_path(kind)).resolve()
    if not output.is_relative_to(root):raise ValueError('Output escapes root')
    if output.exists():
        if output.read_bytes()!=data:raise ValueError('Conflicting immutable transfer')
        return record
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream:stream.write(data)
    return record


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent-proof',choices=('predicate_bundle','strata_bundle'),required=True)
    args=parser.parse_args()
    emit(kind=args.parent_proof)
