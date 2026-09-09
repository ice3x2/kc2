"""CON-ARCH-006 / OPS-ARCH-006: fail-closed, byte-preserving CAD publication.

--apply promotes reviewed staged artifacts. --verify needs no temporary tree,
CadQuery, Fusion or compatibility junctions. Physical acceptance stays pending.
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT='docs/reports/enclosed-housing-20260909'
STAGE='.codex-tmp/enclosure-build'
BASELINE='cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'
MANIFEST='hardware/MODELS/kc2_enclosure_manifest.json'
REPORT_NAMES={'left-generation.json','right-generation.json','left-audit.json','right-audit.json','joined-plan.json','native-all.json'}
SUPERSEDED=['kc2_housing_manifest.json','kc2_housing_clearance.json','kc2_mx_upper_housing_manifest.json',
 'kc2_housing_manifest_magnetic.json','kc2_fusion_export_result.json','kc2_fusion_export_result_magnetic.json']
REVIEW_NAMES=['independent-review-final.json','regressions.json','retained-feet-and-drawings.json']

def expected_cad_names():
    names=set()
    for side in ['left','right']:
        for kind,suffix in [('lower',''),('lower','_magnetic'),('mx_upper','')]:
            base=f'kc2_{side}_{kind}_housing'
            names.update(base+suffix+extension for extension in ['.step','.f3d'])
            names.update(base+part+suffix+'.stl' for part in ([''] if side=='left' else ['_part_a','_part_b']))
    return {'hardware/MODELS/'+name for name in names}

def preserved_paths():
    gerber=['digital-validation.json','fabrication-profile.json','kc2_left-manual-mx-bom.json',
            'kc2_left-pcb-fabrication-only.zip','kc2_right-manual-mx-bom.json',
            'kc2_right-pcb-fabrication-only.zip','manifest.json','review-evidence.json']
    return {'hardware/GERBER/'+n for n in gerber}|{
        f'hardware/PCB/kc2_{side}/'+name for side in ['left','right'] for name in
        ['fp-lib-table',f'kc2_{side}.drc.json',f'kc2_{side}.kicad_pcb',f'kc2_{side}.kicad_pro']}

def static_inputs():
    return {'README.md','hardware/README.md',REPORT+'/README.md',
            'tools/publish_kc2_enclosure.py','tools/test_publish_kc2_enclosure.py',
            'tools/fusion/KC2StepToF3D/KC2StepToF3D.py'}|{
        'hardware/MODELS/'+n for n in [*SUPERSEDED,'README.md','PRINT-enclosed.md','PRINT-r5.md','PRINT_magnetic.md',
            'kc2_magnet_fit_coupon_magnetic.stl','adapters/kc2_mx_ring_cap_020.stl','adapters/kc2_v1_ring_cap_020.stl']}

def inventory_errors(result,required,observed):
    """Required graph is derived from observed reports, never manifest counts."""
    errors=[]
    bindings=result.get('source_sha256',{})
    if set(bindings)!=set(required):errors.append('Incomplete or unexpected publication binding inventory')
    for path,sha in required.items():
        value=bindings.get(path)
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            errors.append('Missing/invalid SHA-256: '+path)
        elif sha is not None and value!=sha:errors.append('Report binding mismatch: '+path)
    if result.get('observed_path_mapping')!=observed:errors.append('Incorrect observed-to-portable mapping')
    preserved=result.get('preserved_pcb_gerber_sha256',{})
    if set(preserved)!=preserved_paths():errors.append('Incomplete preserved PCB/Gerber inventory')
    for path,sha in preserved.items():
        if bindings.get(path)!=sha:errors.append('Preservation binding mismatch: '+path)
    outputs=result.get('outputs',[])
    if len(outputs)!=21 or len(set(outputs))!=21 or set(outputs)!=expected_cad_names():
        errors.append('Expected exact unique9STL/6STEP/6F3D output set')
    if result.get('physical_qualified') is not False or result.get('new_fabrication_approval') is not False:
        errors.append('Physical/fabrication approval must remain false')
    return errors

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def json_bytes(value):return (json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode('utf8')

def write(path,value):Path(path).write_bytes(json_bytes(value))

def portable(path):
    if path.startswith(STAGE+'/'):
        name=path[len(STAGE)+1:]
        if '/' in name or '..' in name:raise ValueError('Unsafe temporary path: '+path)
        if name in REPORT_NAMES:return REPORT+'/'+name
        if name.startswith('kc2_') and Path(name).suffix in ['.step','.stl','.f3d']:
            return 'hardware/MODELS/'+name
        raise ValueError('Unmapped staging input: '+path)
    if path.startswith('.codex-tmp/'):raise ValueError('Unresolved temporary input: '+path)
    for side in ['left','right']:
        prefix=f'hardware/kicad/kc2_{side}/'
        if path.startswith(prefix):return f'hardware/PCB/kc2_{side}/'+path[len(prefix):]
    if Path(path).is_absolute() or '..' in Path(path).parts:raise ValueError('Nonportable path: '+path)
    return path

def same_solids(a,b):
    if len(a)!=len(b) or not a:return False
    remaining=list(b)
    for before in a:
        box=before['bounds_mm'];v=before['volume_mm3']
        if len(box)!=6 or not all(math.isfinite(x) for x in box+[v]) or v<=0:return False
        match=next((i for i,after in enumerate(remaining)
            if len(after['bounds_mm'])==6 and all(abs(x-y)<=.001 for x,y in zip(box,after['bounds_mm']))
            and abs(v-after['volume_mm3'])<=max(.002,v*1e-6)),None)
        if match is None:return False
        remaining.pop(match)
    return True

def native_errors(native,expected):
    errors=[]
    if native.get('physical_qualified') is not False:errors.append('Physical qualification must remain pending')
    if native.get('status')!='pass':errors.append('Native export/reopen not complete')
    outputs=native.get('outputs',{})
    if set(outputs)!=set(expected) or len(expected)!=6:errors.append('All six native variants required')
    for label,model in expected.items():
        row=outputs.get(label,{})
        if row.get('source_sha256')!=model['step_sha256'] or row.get('round_trip_verified') is not True:
            errors.append(label+': stale/unverified native')
        for field in ['source_solids','reopened_solids']:
            if not same_solids(model['solids'],row.get(field,[])):errors.append(label+': '+field+' mismatch')
    return errors

def preserved_hardware():
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASELINE,'--','hardware/PCB','hardware/GERBER'],cwd=ROOT,text=True).splitlines()
    result={}
    for path in paths:
        expected=subprocess.check_output(['git','rev-parse',BASELINE+':'+path],cwd=ROOT,text=True).strip()
        actual=subprocess.check_output(['git','hash-object','--no-filters','--',path],cwd=ROOT,text=True).strip()
        if actual!=expected:raise ValueError('Ordered hardware changed: '+path)
        result[path]=digest(ROOT/path)
    if len(result)<16:raise ValueError('Incomplete preservation inventory')
    return result

def publish():
    records={name:read(ROOT/STAGE/name) for name in REPORT_NAMES}
    expected={};bindings={};copies={}
    def bind(path,sha):
        if digest(ROOT/path)!=sha:raise ValueError('Stale input: '+path)
        target=portable(path)
        if target in bindings and bindings[target]!=sha:raise ValueError('Conflicting input: '+target)
        bindings[target]=sha
        if path!=target:copies[path]=target
    for side in ['left','right']:
        generation=records[side+'-generation.json'];audit=records[side+'-audit.json']
        if generation['status']!='generated_not_independently_verified' or audit['status']!='pass' or audit['errors']:
            raise ValueError('Incomplete generation or failed audit')
        expected.update(generation['outputs'])
        for report in [generation,audit]:
            for path,sha in report['source_sha256'].items():bind(path,sha)
        for output in generation['outputs'].values():
            bind(STAGE+'/'+output['step'],output['step_sha256'])
            for name,mesh in output['meshes'].items():
                if not mesh['watertight'] or not mesh['winding_consistent'] or mesh['shells']!=1:raise ValueError('Invalid STL')
                bind(STAGE+'/'+name,mesh['sha256'])
    for name in ['independent-review-final.json','regressions.json','retained-feet-and-drawings.json']:
        report=read(ROOT/REPORT/name)
        if report.get('status')!='pass' or report.get('errors'):raise ValueError('Review/test gate failed')
        for path,sha in report['source_sha256'].items():bind(path,sha)
        for path,sha in report.get('drawings',{}).items():bind(path,sha)
        bind(REPORT+'/'+name,digest(ROOT/REPORT/name))
    native=records['native-all.json']
    errors=native_errors(native,expected)
    if errors:raise ValueError('; '.join(errors))
    bind('tools/fusion/KC2EnclosedToF3D/KC2EnclosedToF3D.py',native['script_sha256'])
    for row in native['outputs'].values():bind(STAGE+'/'+row['f3d'],row['f3d_sha256'])
    for name in REPORT_NAMES:bind(STAGE+'/'+name,digest(ROOT/STAGE/name))
    for path in ['README.md','hardware/README.md',REPORT+'/README.md',
                 *['hardware/MODELS/'+n for n in ['README.md','PRINT-enclosed.md','PRINT-r5.md','PRINT_magnetic.md',
                    'kc2_magnet_fit_coupon_magnetic.stl','adapters/kc2_mx_ring_cap_020.stl','adapters/kc2_v1_ring_cap_020.stl']]]:
        bind(path,digest(ROOT/path))
    preserved=preserved_hardware()
    bindings.update(preserved)
    pending_json={}
    for name in SUPERSEDED:
        path='hardware/MODELS/'+name
        pending_json[path]={'status':'superseded','historical_commit':BASELINE,
            'historical_path':path,'current_manifest':'kc2_enclosure_manifest.json',
            'note':'Old open-r5 evidence is in Git; not qualification of current enclosed CAD.'}
        bindings[path]=hashlib.sha256(json_bytes(pending_json[path])).hexdigest()
    for path in ['tools/publish_kc2_enclosure.py','tools/test_publish_kc2_enclosure.py',
                 'tools/fusion/KC2StepToF3D/KC2StepToF3D.py']:
        bindings[path]=digest(ROOT/path)
    result={'requirements':['CON-ARCH-006','CON-ARCH-007','REL-ARCH-001','OPS-ARCH-006'],
        'status':'digital_geometry_verified','physical_qualified':False,'new_fabrication_approval':False,
        'baseline_commit':BASELINE,'outputs':sorted(portable(STAGE+'/'+n) for o in expected.values() for n in [o['step'],*o['meshes'],Path(o['step']).with_suffix('.f3d').name]),
        'source_sha256':bindings,'observed_path_mapping':{k:portable(k) for k in copies},
        'preserved_pcb_gerber_sha256':preserved,'native_report':REPORT+'/native-all.json',
        'joined':records['joined-plan.json'],'print_guide':'PRINT-enclosed.md',
        'nominal_stack_mm':{'floor_bottom':-2.2,'floor_top':-1.,'pcb_bottom':2.5,'pcb_top_and_wall_seat':4.1,
            'mx_plate_bottom':7.8,'mx_plate_top':9.3,'plate_thickness':1.5,'mx_opening':14.,
            'screw_under_head_length':7.5,'screw_insertion':2.2,'screw_tip_reserve':.6,
            'head_pocket_diameter':3.4,'head_pocket_depth':1.5},
        'preserved_supports_and_mounts':{'left_keys':31,'right_keys':39,'left_mounts':8,'right_mounts':9},
        'pending_physical':['printer/nozzle/strength','exact keycap/full travel and supplied part/header/cable fit','magnet fit/adhesion/polarity/pull','power/thermal/RF qualification']}
    # Validate the complete prospective canonical graph without modifying it.
    # Reads/hashes resolve copied files to their exact staged source bytes and
    # superseded pointers to their deterministic, still in-memory JSON bytes.
    staged_targets={target:source for source,target in copies.items() if source.startswith(STAGE+'/')}
    def prospective_read(path):
        target=Path(path).relative_to(ROOT).as_posix()
        return pending_json[target] if target in pending_json else read(ROOT/staged_targets.get(target,target))
    def prospective_digest(path):
        target=Path(path).relative_to(ROOT).as_posix()
        if target in pending_json:return hashlib.sha256(json_bytes(pending_json[target])).hexdigest()
        return digest(ROOT/staged_targets.get(target,target))
    verify(result,prospective_read,prospective_digest)
    # Every validation above is read-only. Only now publish the observed bytes.
    for source,target in copies.items():
        if source.startswith(STAGE+'/'):shutil.copyfile(ROOT/source,ROOT/target)
    for path,value in pending_json.items():write(ROOT/path,value)
    write(ROOT/MANIFEST,result)
    return verify()

def verify(result=None,reader=None,hasher=None):
    reader=reader or read;hasher=hasher or digest
    result=reader(ROOT/MANIFEST) if result is None else result
    if (result.get('status')!='digital_geometry_verified' or result.get('physical_qualified') is not False
        or result.get('new_fabrication_approval') is not False):raise ValueError('Wrong publication state')
    if result.get('baseline_commit')!=BASELINE:raise ValueError('Unexpected preserved baseline')
    outputs=result.get('outputs',[])
    if len(outputs)!=21 or len(set(outputs))!=21 or set(outputs)!=expected_cad_names():
        raise ValueError('Expected exact unique9STL/6STEP/6F3D output set')
    required={path:None for path in static_inputs()|preserved_paths()};observed={};expected={}
    def need(path,sha=None):
        target=portable(path)
        if target in required and required[target] is not None and sha is not None and required[target]!=sha:
            raise ValueError('Conflicting observed input: '+target)
        if sha is not None or target not in required:required[target]=sha
        if path!=target:observed[path]=target
    def report(name,staged=False):
        path=REPORT+'/'+name
        value=reader(ROOT/path)
        if name not in ['joined-plan.json','native-all.json'] and not value.get('source_sha256'):
            raise ValueError('Report has no source binding graph: '+name)
        need(STAGE+'/'+name if staged else path,hasher(ROOT/path))
        for source,sha in value.get('source_sha256',{}).items():need(source,sha)
        for source,sha in value.get('drawings',{}).items():need(source,sha)
        return value
    for side in ['left','right']:
        generation=report(side+'-generation.json',True);audit=report(side+'-audit.json',True)
        if generation.get('status')!='generated_not_independently_verified' or audit.get('status')!='pass' or audit.get('errors'):
            raise ValueError('Incomplete generation or failed audit')
        expected.update(generation['outputs'])
        for output in generation['outputs'].values():
            need(STAGE+'/'+output['step'],output['step_sha256'])
            for name,mesh in output['meshes'].items():
                if not mesh['watertight'] or not mesh['winding_consistent'] or mesh['shells']!=1:raise ValueError('Invalid STL')
                need(STAGE+'/'+name,mesh['sha256'])
    for name in REVIEW_NAMES:
        value=report(name)
        if value.get('status')!='pass' or value.get('errors'):raise ValueError('Review/test gate failed')
    joined=report('joined-plan.json',True)
    if result.get('joined')!=joined:raise ValueError('Published joined transform mismatch')
    if result.get('native_report')!=REPORT+'/native-all.json':raise ValueError('Unexpected native report path')
    native=report('native-all.json',True)
    errors=native_errors(native,expected)
    if errors:raise ValueError('; '.join(errors))
    need('tools/fusion/KC2EnclosedToF3D/KC2EnclosedToF3D.py',native['script_sha256'])
    for label,row in native['outputs'].items():
        if row['f3d']!=Path(expected[label]['step']).with_suffix('.f3d').name:
            raise ValueError('Native filename does not match source model')
        need(STAGE+'/'+row['f3d'],row['f3d_sha256'])
    if not expected_cad_names().issubset(required):raise ValueError('CAD input graph incomplete')
    errors=inventory_errors(result,required,observed)
    if errors:raise ValueError('; '.join(errors))
    for path,sha in result['source_sha256'].items():
        if path!=portable(path) or hasher(ROOT/path)!=sha:raise ValueError('Changed/missing portable input: '+path)
    return {'status':'pass','output_count':21,'bindings':len(result['source_sha256']),'physical_qualified':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--apply',action='store_true');group.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    print(json.dumps(publish() if args.apply else verify(),indent=2))
