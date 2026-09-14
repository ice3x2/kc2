"""CON-ARCH-006 explicit old-V2 predicates + independent bounded subtraction.

This does NOT rerun V2 Booleans or turn historical measurements into new ones.
Any nonzero proof delta rejects transfer; fresh direct V2 is the fallback.
"""
import json
from pathlib import Path
from tools.kc2_registered_release_gate import STAGE,sha_bytes,passed,finite,safe_relative,stem
SCHEMA='right-receiver-v2-predicate-transfer-v1'
DELTA_SCHEMA='right-receiver-cleanup-delta-v1'
VARIANTS=('normal','magnetic')
CACHE=STAGE+'/lower-development/receiver-cleanup-inputs'
SNAPSHOT=CACHE+'/snapshot-map.json'
OLD=CACHE+'/right-void-review.json'
PROOF=STAGE+'/lower/right-receiver-cleanup-review.json'
OUTPUT=STAGE+'/lower/right-void-review.json'
MAPPING={**{f'{STAGE}/lower/right-{v}':f'{CACHE}/right-{v}' for v in VARIANTS},
 OUTPUT:OLD,'.codex-tmp/receiver_cleanup_candidate.py':CACHE+'/provenance/receiver_cleanup_candidate.py'}
DELTA_ZERO=('added_mm3','off_cutter_removed_mm3','part_a_missing_mm3','part_a_extra_mm3',
 'expected_removal_missing_mm3','expected_removal_extra_mm3','required_stock_removed_mm3',
 'floor_removed_mm3','floor_added_mm3','protected_roles_removed_mm3',
 'pocket_entry_protected_material_removed_mm3','remaining_candidate_mm3')
MAGNET_ZERO=('missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3')

def archived(logical):
    safe_relative(logical)
    for prefix,target in MAPPING.items():
        if logical==prefix or logical.startswith(prefix+'/'):return target+logical[len(prefix):]
    return logical

def exact_zero(value):
    if finite(value)!=0.:raise ValueError('Nonzero kernel evidence; direct V2 required')

def check_predicates(old,proof):
    from tools.publish_kc2_registered_housings import check_lower_void,LOWER_VOID_ZERO
    check_lower_void(old,'right',False);passed(proof)
    if proof.get('schema')!=DELTA_SCHEMA or proof.get('side')!='right' or proof.get('native_readback') is not False or proof.get('actual_exported_STEP_reimported') is not True:
        raise ValueError('Not independent exported STEP delta evidence')
    if proof.get('strict_transfer_eligible') is not True:raise ValueError('Independent delta not strict-transfer eligible')
    if proof.get('cut_z_mm')!=[-1,2.5] or proof.get('ys_mm')!=[73.25,86.25] or set(proof.get('variants',{}))!=set(VARIANTS):raise ValueError('Wrong bounded cleanup/variant identity')
    for variant in VARIANTS:
        previous=old['variants'][variant];row=proof['variants'][variant]
        if type(previous.get('body_count')) is not int or previous['body_count']!=2:raise ValueError('Wrong historical body count')
        for key in LOWER_VOID_ZERO:exact_zero(previous.get(key))
        if any(type(row.get(k)) is not int or row[k]!=2 for k in ('body_count','matched_body_count')) or row.get('valid_solids') is not True:raise ValueError('Missing valid matched bodies')
        for key in DELTA_ZERO:exact_zero(row.get(key))
        if finite(row.get('removed_mm3'))<=0:raise ValueError('No actual cleanup subtraction')
    for key in MAGNET_ZERO:exact_zero(old['magnet'].get(key))
    for key in ('normal_minus_magnetic_mm3','magnetic_minus_normal_mm3'):exact_zero(proof.get('paired_removal',{}).get(key))

def inputs(read):
    bindings={}
    def bound(path):
        data=read(path);sha=sha_bytes(data)
        if path in bindings and bindings[path]!=sha:raise ValueError('Changed proof source')
        bindings[path]=sha;return data
    def merge(mapping):
        if not isinstance(mapping,dict) or not mapping:raise ValueError('Missing source chain')
        for name,sha in mapping.items():
            if sha_bytes(bound(name))!=sha:raise ValueError('Stale direct source '+name)
    snapshot=json.loads(bound(SNAPSHOT))
    if snapshot.get('status')!='verified_historical_snapshot' or snapshot.get('path_mapping')!=MAPPING:raise ValueError('Wrong immutable historical resolver')
    historical=snapshot.get('historical_original_sha256',{})
    remapped={archived(n):sha for n,sha in historical.items()}
    if not historical or len(remapped)!=len(historical) or remapped!=snapshot.get('source_sha256'):raise ValueError('Incomplete/conflicting snapshot map')
    merge(remapped)
    old=json.loads(bound(OLD));proof=json.loads(bound(PROOF));check_predicates(old,proof)
    if historical.get(OUTPUT)!=bindings[OLD]:raise ValueError('Wrong original V2 report bytes')
    for name,sha in old.get('source_sha256',{}).items():
        if historical.get(name)!=sha or bindings.get(archived(name))!=sha:raise ValueError('Old V2 identity rebound or absent')
    if not old.get('source_sha256'):raise ValueError('Missing historical actual sources')
    required={SNAPSHOT:bindings[SNAPSHOT],OLD:bindings[OLD]}
    for variant in VARIANTS:
        folder=f'{STAGE}/lower/right-{variant}';name=stem('lower','right',variant)
        gp=folder+'/generation.json';sp=folder+'/'+name+'.step'
        for historical_path in (gp,sp):
            if old['source_sha256'].get(historical_path)!=historical.get(historical_path):raise ValueError('Old V2 lacks actual material identity')
            required[archived(historical_path)]=bindings[archived(historical_path)]
        previous=json.loads(read(archived(gp)))
        if previous.get('outputs',{}).get(name+'.step')!=required[archived(sp)]:raise ValueError('Archived generation does not identify archived STEP')
        current=json.loads(bound(gp));bound(sp)
        if current.get('status')!='generated_pending_independent_review' or current.get('side')!='right' or current.get('magnetic') is not (variant=='magnetic') or type(current.get('body_count')) is not int or current['body_count']!=2 or current.get('outputs',{}).get(name+'.step')!=bindings[sp]:raise ValueError('Wrong current generation/material')
        merge(current.get('source_sha256'));required.update({gp:bindings[gp],sp:bindings[sp]})
    for path in ('tools/review_kc2_receiver_cleanup.py','tools/test_review_kc2_receiver_cleanup.py',
                 'tools/review_kc2_lower_voids_v2.py','tools/test_review_kc2_lower_voids_v2.py'):
        required[path]=sha_bytes(bound(path))
    if any(proof.get('source_sha256',{}).get(n)!=sha for n,sha in required.items()):raise ValueError('Independent actual delta lacks exact evidence identities')
    merge(proof.get('source_sha256'))
    return old,proof,bindings

def validate(record,read):
    passed(record)
    if record.get('schema')!=SCHEMA or record.get('side')!='right' or record.get('native_readback') is not False or record.get('full_v2_boolean_rerun') is not False or record.get('physical_qualified') is not False or record.get('proof_method')!='bounded_exact_subtraction_predicate_transfer':raise ValueError('Wrong derived V2 semantics')
    old,proof,bindings=inputs(read)
    expected=dict(historical_actual_report=OLD,historical_actual_sha256=bindings[OLD],independent_delta_report=PROOF,independent_delta_sha256=bindings[PROOF],
      historical_predicate_measurements=old['variants'],historical_magnet_measurements=old['magnet'],component_envelope=old['component_envelope'],
      derived_predicate_upper_bounds={v:{k:0. for k in old['variants'][v] if k.endswith('_mm3')} for v in VARIANTS},derived_magnet_delta_unchanged=True)
    if any(record.get(k)!=v for k,v in expected.items()):raise ValueError('Historical measurements/derived bounds misrepresented')
    if any(record.get('source_sha256',{}).get(n)!=sha for n,sha in bindings.items()):raise ValueError('Derived V2 proof chain incomplete')
    return old

def build(root=None):
    from tools.publish_kc2_registered_housings import contained
    root=Path(root or Path(__file__).resolve().parents[1]).resolve();read=lambda n:contained(root,n).read_bytes()
    old,proof,bindings=inputs(read)
    for name in ('tools/kc2_receiver_void_transfer.py','tools/test_kc2_receiver_void_transfer.py','tools/publish_kc2_registered_housings.py','tools/test_publish_kc2_registered_housings.py','tools/kc2_registered_release_gate.py'):
        bindings[name]=sha_bytes(read(name))
    record=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],schema=SCHEMA,status='pass',errors=[],side='right',native_readback=False,
      full_v2_boolean_rerun=False,physical_qualified=False,proof_method='bounded_exact_subtraction_predicate_transfer',
      historical_actual_report=OLD,historical_actual_sha256=bindings[OLD],independent_delta_report=PROOF,independent_delta_sha256=bindings[PROOF],
      historical_predicate_measurements=old['variants'],historical_magnet_measurements=old['magnet'],component_envelope=old['component_envelope'],
      derived_predicate_upper_bounds={v:{k:0. for k in old['variants'][v] if k.endswith('_mm3')} for v in VARIANTS},derived_magnet_delta_unchanged=True,source_sha256=bindings,
      limitations=['Historical measured V2 values retained separately; no full V2 Boolean rerun','Fresh floor, split, magnetic access and native reviews remain mandatory','No physical strength, printing or fit qualification'])
    validate(record,read)
    if any(sha_bytes(read(n))!=sha for n,sha in bindings.items()):raise ValueError('Changed during transfer')
    out=contained(root,OUTPUT)
    if out.exists() and sha_bytes(out.read_bytes())!=bindings[OLD] and json.loads(out.read_bytes()).get('schema')!=SCHEMA:raise ValueError('Unrelated current V2 report retained')
    out.write_text(json.dumps(record,indent=2)+'\n');return record

if __name__=='__main__':print(build()['status'])
