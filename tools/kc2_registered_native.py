"""CON-ARCH-006 fixed ten-identity, one-selected-job native source preflight."""
from pathlib import Path
import hashlib,json


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def safe_path(root,name):
    if not isinstance(name,str) or Path(name).is_absolute() or '\\' in name:
        raise ValueError('unsafe source path')
    p=(root/name).resolve()
    if not p.is_relative_to(root.resolve()):raise ValueError('escaping source path')
    return p


def revalidate_job(root,job):
    for name,sha in job['source_sha256'].items():
        if digest(safe_path(root,name))!=sha:raise ValueError('Changed source: '+name)


def preflight_job(root,label):
    root=Path(root).resolve()
    labels={f'{family}:{side}:{kind}' for family,kinds in [('upper',['mx','choc_v1','deep_sea']),('lower',['normal','magnetic'])] for side in ['left','right'] for kind in kinds}
    if not isinstance(label,str) or label not in labels:raise ValueError('Select exactly one known job')
    family,side,kind=label.split(':');folder=root/'.codex-tmp/registered-housing-fit'/family/(side+'-'+kind)
    record_path=folder/'generation.json';record_bytes=record_path.read_bytes()
    record=json.loads(record_bytes);record_sha=hashlib.sha256(record_bytes).hexdigest()
    if record.get('status')!='generated_pending_independent_review':raise ValueError('Generation incomplete')
    if record.get('side')!=side:raise ValueError('Wrong generation identity')
    count=1 if side=='left' else 2
    if family=='upper':
        if record.get('kind')!=kind or not isinstance(record.get('parts'),list) or len(record['parts'])!=count:
            raise ValueError('Wrong upper identity/body count')
        stem=f'kc2_{side}_{kind}_upper_housing'
    else:
        if record.get('magnetic') is not (kind=='magnetic') or type(record.get('body_count')) is not int or record['body_count']!=count:
            raise ValueError('Wrong lower identity/body count')
        stem=f'kc2_{side}_lower_housing'+('_magnetic' if kind=='magnetic' else '')
    source=folder/(stem+'.step')
    bindings=record.get('source_sha256')
    if not isinstance(bindings,dict) or not bindings:raise ValueError('Missing source bindings')
    bindings=dict(bindings)
    outputs=record.get('outputs',{})
    if source.name not in outputs:raise ValueError('Missing expected STEP output')
    for name,sha in outputs.items():
        if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name:
            raise ValueError('unsafe output path')
        bindings[(folder/name).relative_to(root).as_posix()]=sha
    bindings[record_path.relative_to(root).as_posix()]=record_sha
    for name,sha in bindings.items():
        safe_path(root,name)
        if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid source hash')
    job=dict(label=label,family=family,side=side,kind=kind,source=source,count=count,
             record_path=record_path,record_sha256=record_sha,step_sha256=outputs[source.name],
             source_sha256=bindings)
    revalidate_job(root,job)
    return job
