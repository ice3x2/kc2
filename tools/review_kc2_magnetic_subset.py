"""CON-ARCH-006 fresh actual right magnetic subset, not component clearance."""
import hashlib
import json
from pathlib import Path
from tools.kc2_magnetic_subset import audit,check_generation,validate_metrics
from tools.review_kc2_lower_strata import validate_import

ROOT=Path(__file__).resolve().parents[1]
STAGE='.codex-tmp/registered-housing-fit/lower'
SCHEMA='right-magnetic-material-subset-v1'


def run():
    import cadquery as cq
    frozen={}
    def bind(name,expected=None):
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()):raise ValueError('Source escapes root')
        data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
        if expected is not None and sha!=expected or name in frozen and frozen[name]!=sha:
            raise ValueError('Stale/conflicting actual source '+name)
        frozen[name]=sha;return data
    original_path=STAGE+'/right-void-review.json';original=json.loads(bind(original_path))
    if (original.get('schema')!='lower-void-v2' or original.get('side')!='right'
        or original.get('native_readback') is not False or original.get('status')!='fail'):
        raise ValueError('Expected preserved original failed V2 evidence')
    if not original.get('source_sha256'):raise ValueError('Missing original source closure')
    for name,sha in original['source_sha256'].items():bind(name,sha)
    for name in ('kc2_magnetic_subset','test_kc2_magnetic_subset','review_kc2_magnetic_subset',
                 'review_kc2_lower_strata','test_kc2_lower_strata'):
        bind('tools/'+name+'.py')
    variants={};identities={}
    for variant in ('normal','magnetic'):
        folder=STAGE+'/right-'+variant
        gp=folder+'/generation.json';sp=folder+'/kc2_right_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step'
        generation=json.loads(bind(gp));bind(sp)
        if any(original['source_sha256'].get(p)!=frozen[p] for p in (gp,sp)):
            raise ValueError('Original failure does not bind current exact STEP/generation')
        if not generation.get('source_sha256'):raise ValueError('Missing generation closure')
        for name,sha in generation['source_sha256'].items():bind(name,sha)
        print('import fresh actual '+variant+' STEP',flush=True)
        shape=cq.importers.importStep(str(ROOT/sp)).val()
        parts=validate_import(shape)
        check_generation(generation,variant,frozen[sp],parts)
        variants[variant]=parts
        identities[variant]=dict(step_path=sp,step_sha256=frozen[sp],generation_path=gp,generation_sha256=frozen[gp],
            whole_import_topology_covered_by_two_solids=True,whole_import_positive_volume_mm3=shape.Volume())
    metrics=audit(variants['normal'],variants['magnetic'],lambda i,op:print('actual part',i,op,flush=True))
    errors=[]
    try:validate_metrics(metrics)
    except ValueError as exc:errors.append(str(exc))
    for name,sha in list(frozen.items()):bind(name,sha)
    result=dict(requirements=['CON-ARCH-006'],schema=SCHEMA,status='fail' if errors else 'pass',errors=errors,
        side='right',native_readback=False,actual_exported_STEP_reimported=True,variants=identities,
        actual_material_comparison=metrics,kernel_computed_subset_proved=not errors,
        component_qualified=False,physical_qualified=False,original_v2_report=original_path,
        original_v2_sha256=frozen[original_path],original_v2_status='fail',original_v2_errors=original['errors'],
        original_component_obstruction_mm3={v:original['variants'][v]['component_obstruction_mm3'] for v in variants},
        source_sha256=frozen,scope='Subset only; no component clearance, pocket position or physical qualification')
    output=ROOT/STAGE/'right-magnetic-subset-review.json'
    if output.exists():raise ValueError('Existing immutable subset evidence retained')
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    return int(bool(run()['errors']))


if __name__=='__main__':raise SystemExit(main())
