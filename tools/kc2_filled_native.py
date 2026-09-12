"""CON-ARCH-006 fixed six-job preflight, without importing Fusion API."""
import hashlib,json


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight_jobs(folder,root):
    jobs=[]
    for side in ['left','right']:
        for kind in ['mx','choc_v1','deep_sea']:
            path=folder/f'{side}-{kind}.json'
            record=json.loads(path.read_text(encoding='utf8'))
            if record.get('status')!='generated_pending_independent_review':raise ValueError('Generation incomplete')
            if (record.get('side'),record.get('kind'))!=(side,kind):raise ValueError('Wrong generation identity')
            count=1 if side=='left' else 2
            if len(record['parts'])!=count:raise ValueError('Wrong source body count')
            source=folder/f'kc2_{side}_{kind}_upper_housing.step'
            if digest(source)!=record['outputs'][source.name]:raise ValueError('Changed STEP: '+source.name)
            for name,sha in record['source_sha256'].items():
                if digest(root/name)!=sha:raise ValueError('Changed generation source: '+name)
            jobs.append(dict(label=side+'_'+kind,source=source,count=count,record_path=path,
                             record_sha256=digest(path),step_sha256=digest(source)))
    return jobs
