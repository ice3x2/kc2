"""CON-ARCH-006 native archive identity and generation prerequisites."""
from pathlib import Path
import json
from tools.kc2_flat_central_native import digest

STAGE = Path('.codex-tmp/wrap-housing-20260920-r1')


def jobs():
    result = {}
    for side in ('left', 'right'):
        for kind in ('normal', 'magnetic', 'mx', 'choc_v1', 'deep_sea'):
            lower = kind in ('normal', 'magnetic')
            stem = f'kc2_{side}_lower_housing'+('_magnetic' if kind == 'magnetic' else '') if lower else f'kc2_{side}_{kind}_upper_housing'
            result[side+':'+kind] = dict(folder=('lower' if lower else 'upper')+'/'+side+'-'+kind,
                step=stem+'.step', body_count=1 if side == 'left' else 2)
    return result


def select_jobs(selected):
    result = list(jobs()) if selected is None else list(selected)
    if not result or len(set(result)) != len(result) or not set(result).issubset(jobs()):
        raise ValueError('Unknown, empty or duplicate native job selection')
    return result


def preflight(root, label):
    root = Path(root).resolve()
    job = jobs().get(label)
    if job is None:
        raise ValueError('Unknown sleeve job')
    folder = root/STAGE/job['folder']
    source = folder/job['step']
    path = folder/'generation.json'
    r = json.loads(path.read_text())
    if (r.get('status') != 'generated_pending_independent_review' or r.get('errors') or
            r.get('body_count') != job['body_count'] or r.get('outputs', {}).get(source.name) != digest(source)):
        raise ValueError('Incomplete or changed sleeve generation')
    for name, sha in r['source_sha256'].items():
        if digest(root/name) != sha:
            raise ValueError('Changed generation input: '+name)
    return dict(label=label, folder=folder, source=source, generation_path=path,
                generation_sha256=digest(path), source_sha256=digest(source),
                step=job['step'], body_count=job['body_count'])
