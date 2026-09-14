"""CON-ARCH-006 / OPS-ARCH-006 release PREPARATION, never publication.

No filesystem writes or fabricated future approvals. Old canonical model
source references resolve to pinned Git blobs, independently of new output
bytes. Development records may be byte-bound provenance; their nested stale
sources are NOT recursively upgraded to current verification evidence.
Future combined-mechanical schemas deliberately have no generic pass adapter.
"""
import hashlib
import math
from pathlib import Path,PurePosixPath
import subprocess

BASELINE='5b99bcb4567ea1c6bb4f17e54887d4de7614cd03'
STAGE='.codex-tmp/registered-housing-fit'
DEFERRED_GATES={'central_actual','full_joined_path','lower_ab_actual','lower_root_actual','printability_actual'}


def jobs():
    return [(family,side,kind) for family,kinds in [('upper',['mx','choc_v1','deep_sea']),('lower',['normal','magnetic'])]
            for side in ['left','right'] for kind in kinds]


def stem(family,side,kind):
    return f'kc2_{side}_{kind}_upper_housing' if family=='upper' else f'kc2_{side}_lower_housing'+('_magnetic' if kind=='magnetic' else '')


def job_names(family,side,kind):
    name=stem(family,side,kind)
    if side=='left':stls=[name+'.stl']
    elif family=='upper':stls=[name+'_part_'+p+'.stl' for p in 'ab']
    else:stls=['kc2_right_lower_housing_part_'+p+('_magnetic' if kind=='magnetic' else '')+'.stl' for p in 'ab']
    return [name+'.step',name+'.f3d',*stls]


def inventory():
    return {'hardware/MODELS/'+name:f'{STAGE}/{family}/{side}-{kind}/{name}'
            for family,side,kind in jobs() for name in job_names(family,side,kind)}


def required_gate_ids():
    result=set(DEFERRED_GATES)
    for family,side,kind in jobs():
        for role in (['generation','brep','mesh','native_generation','native_review'] if family=='upper'
                     else ['generation','native_generation','native_review']):
            result.add(f'{family}:{side}:{kind}:{role}')
    result.update(f'{side}:{role}' for side in ['left','right'] for role in ['lower_void','stack'])
    result.update('right:'+kind+':profile_actual' for kind in ['mx','choc_v1','deep_sea'])
    return result


def safe_relative(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:
        raise ValueError('Unsafe relative path')
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or p.as_posix()!=name:raise ValueError('Unsafe relative path')
    return name


def sha_bytes(data):return hashlib.sha256(data).hexdigest()


def hash_string(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid SHA-256')
    return value


def resolve_binding(root,name,expected,*,git_reader=None):
    """Resolve one direct binding; never recurse into development JSON."""
    root=Path(root).resolve();safe_relative(name);hash_string(expected)
    if name in inventory():
        data=(git_reader(BASELINE,name) if git_reader else
              subprocess.check_output(['git','show',BASELINE+':'+name],cwd=root))
        descriptor=dict(kind='git_blob',revision=BASELINE,path=name,sha256=expected)
    else:
        path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Binding escapes workspace')
        data=path.read_bytes();descriptor=dict(kind='workspace',path=name,sha256=expected)
    if sha_bytes(data)!=expected:raise ValueError('Source binding mismatch: '+name)
    return descriptor


def check_inventory(root,expected):
    selected=inventory()
    if set(expected)!=set(selected):raise ValueError('Exact 35-output inventory required')
    result={}
    for target,source in selected.items():
        sha=hash_string(expected[target]);path=Path(root)/source
        if sha_bytes(path.read_bytes())!=sha:raise ValueError('Current artifact hash mismatch: '+source)
        result[target]=dict(staged_source=source,sha256=sha)
    return result


def finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Finite numerical evidence required')
    return float(value)


def passed(record):
    if record.get('status')!='pass' or record.get('errors',[]):raise ValueError('Report not passed')


def check_sections(row,*,mesh=False):
    passed(row)
    levels=row.get('levels_mm',[]);sections=row.get('sections',[])
    if len(levels)<2 or levels!=sorted(set(levels)) or len(sections)!=len(levels)-1:
        raise ValueError('Complete actual height coverage absent')
    tolerance=.02 if mesh else .001
    volume=0.
    for lo,hi,section in zip(levels,levels[1:],sections):
        if abs(finite(section.get('z_mm'))-(finite(lo)+finite(hi))/2)>1e-6:
            raise ValueError('Wrong actual section interval')
        if any(not 0<=finite(section.get(k))<=tolerance for k in ['missing_mm2','extra_mm2']):
            raise ValueError('Actual material mismatch')
        area=finite(section.get('area_mm2' if mesh else 'actual_area_mm2'))
        if area<0:raise ValueError('Invalid actual section area')
        volume+=area*(hi-lo)
    limit=max(.02,volume*1e-5) if mesh else max(.002,volume*1e-7)
    if not 0<=finite(row.get('volume_error_mm3'))<=limit:raise ValueError('Invalid volume difference')


def require_sources(record,context):
    bindings=record.get('source_sha256')
    if not isinstance(bindings,dict) or not bindings:raise ValueError('Missing direct source bindings')
    for name,sha in [(context['generation'],context['generation_sha256']),(context['step'],context['step_sha256'])]:
        if bindings.get(name)!=sha:raise ValueError('Actual STEP/generation source chain missing')


def check_job_report(role,record,context):
    """Known current schemas only. Caller separately resolves all byte bindings."""
    family,side,kind=context['family'],context['side'],context['kind']
    if (family,side,kind) not in jobs() or context['label']!=':'.join([family,side,kind]):
        raise ValueError('Wrong job context identity')
    if context['stem']!=stem(family,side,kind) or context['count']!=(1 if side=='left' else 2):
        raise ValueError('Wrong job context stem/body count')
    count=context['count'];names=job_names(family,side,kind)
    if role=='generation':
        if record.get('status')!='generated_pending_independent_review' or record.get('side')!=side:
            raise ValueError('Wrong or unfinished generation identity')
        if family=='upper':
            if record.get('kind')!=kind or len(record.get('parts',[]))!=count:raise ValueError('Wrong upper identity')
        elif record.get('magnetic') is not (kind=='magnetic') or record.get('body_count')!=count:
            raise ValueError('Wrong lower identity')
        expected=set(names)-{context['stem']+'.f3d'}
        if set(record.get('outputs',{}))!=expected:raise ValueError('Wrong exact generation output names')
        if record['outputs'].get(context['stem']+'.step')!=context['step_sha256']:raise ValueError('Wrong STEP bytes')
        for sha in record['outputs'].values():hash_string(sha)
        if not record.get('source_sha256'):raise ValueError('Missing generation input bindings')
        return
    passed(record);require_sources(record,context)
    if role in ['brep','mesh','native_review']:
        parts=record.get('parts',[])
        if len(parts)!=count:raise ValueError('Wrong actual part count')
        if role=='native_review':
            if record.get('selected_job')!=context['label'] or record.get('independent_geometry_verified') is not True:
                raise ValueError('Missing selected actual native geometry review')
        elif record.get('side',side)!=side or record.get('kind',kind)!=kind:
            raise ValueError('Wrong geometry review identity')
        for part in parts:
            if family=='upper':check_sections(part,mesh=role=='mesh')
            else:
                passed(part)
                if any(not 0<=finite(part.get(k))<=.002 for k in ['missing_mm3','extra_mm3']):
                    raise ValueError('Actual native lower material mismatch')
        if role=='mesh' and {p.get('stl') for p in parts}!={n for n in names if n.endswith('.stl')}:
            raise ValueError('Wrong actual STL identities')
    elif role=='native_generation':
        if record.get('selected_job')!=context['label'] or record.get('phase')!='complete':raise ValueError('Native execution incomplete')
        if set(record.get('outputs',{}))!={context['label']}:raise ValueError('Wrong native job inventory')
        output=record['outputs'][context['label']]
        if output.get('source_sha256')!=context['step_sha256'] or output.get('generation_sha256')!=context['generation_sha256']:
            raise ValueError('Native chain mismatch')
        if output.get('round_trip_verified') is not True or output.get('expected_body_count')!=count:
            raise ValueError('Native round trip absent')
        if output.get('source_step')!=context['stem']+'.step' or output.get('f3d')!=context['stem']+'.f3d' or output.get('readback_step')!=context['stem']+'.native-readback.step':
            raise ValueError('Wrong native filenames')
        hash_string(output.get('f3d_sha256'));hash_string(output.get('readback_sha256'))
        if len(output.get('source_solids',[]))!=count or len(output.get('reopened_solids',[]))!=count:
            raise ValueError('Actual native body evidence absent')
    else:raise NotImplementedError('No semantic adapter for '+role)


def preparation_status(report_ids):
    """Inventory planning only: even a full ID set is NOT an approval."""
    supplied=set(report_ids);wanted=required_gate_ids()
    return dict(status='incomplete_preparation',publication_authorized=False,
                missing=sorted(wanted-supplied),unexpected=sorted(supplied-wanted),
                unimplemented_semantic_gates=sorted(DEFERRED_GATES|{'lower_void','stack','profile_actual'}))


def check_native_links(native_generation,native_review,context):
    """Cross-report archive/readback identity; not a substitute for both audits."""
    output=native_generation['outputs'][context['label']]
    folder=PurePosixPath(context['step']).parent
    required={(folder/output['f3d']).as_posix():hash_string(output['f3d_sha256']),
              (folder/output['readback_step']).as_posix():hash_string(output['readback_sha256']),
              (folder/'native-generation.json').as_posix():hash_string(context['native_generation_sha256'])}
    if any(native_review.get('source_sha256',{}).get(k)!=v for k,v in required.items()):
        raise ValueError('Native review archive/readback/generation chain differs')


def evidence_destination(source):
    """Proposed evidence-only mapping; never copies or rewrites files."""
    safe_relative(source)
    if source in inventory().values():raise ValueError('Current CAD output must use canonical mapping, not a second evidence copy')
    if not source.startswith(STAGE+'/'):raise ValueError('Not a selected development artifact')
    return 'docs/reports/registered-housing-fit-20260913/evidence/'+source[len(STAGE)+1:]
