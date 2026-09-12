"""OPS-ARCH-006 real isolated publication check and byte/inventory mutations."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='hardware/MODELS/kc2_filled_plate_manifest.json'


def main():
    original=ROOT/MANIFEST;raw=original.read_bytes();manifest=json.loads(raw)
    isolated=Path(tempfile.mkdtemp(prefix='filled-portable-',dir=ROOT/'.codex-tmp'))
    for name,sha in {**manifest['source_sha256'],MANIFEST:hashlib.sha256(raw).hexdigest()}.items():
        source=ROOT/name
        if hashlib.sha256(source.read_bytes()).hexdigest()!=sha:raise ValueError('Source changed: '+name)
        destination=isolated/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    command=[sys.executable,'-S','-B','-m','tools.publish_kc2_filled_plates','--verify']
    def run():
        p=subprocess.run(command,cwd=isolated,capture_output=True,text=True,encoding='utf8')
        return dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
    initial=run()
    if initial['returncode']:raise ValueError('Isolated publication failed: '+initial['stderr'])
    mutations={}
    stl='hardware/MODELS/kc2_left_deep_sea_upper_housing.stl'
    with (isolated/stl).open('ab') as output:output.write(b'changed')
    mutations['changed_print_stl']=run();shutil.copyfile(ROOT/stl,isolated/stl)
    path=isolated/MANIFEST
    changed=json.loads(raw);changed['outputs'].pop();path.write_text(json.dumps(changed),encoding='utf8')
    mutations['missing_output_inventory']=run();path.write_bytes(raw)
    audit=isolated/'docs/reports/solid-filled-plates-20260913/right-deep_sea-native-review.json'
    held=audit.with_suffix('.held');audit.rename(held)
    mutations['missing_native_evidence']=run();held.rename(audit)
    final=run()
    if final['returncode'] or any(r['returncode']==0 for r in mutations.values()):raise ValueError('Mutation rejection or restoration failed')
    report=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='pass',physical_qualified=False,
        manifest_sha256=hashlib.sha256(raw).hexdigest(),verifier_sha256=hashlib.sha256((ROOT/'tools/publish_kc2_filled_plates.py').read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),isolated_root=str(isolated),
        command=command,initial=initial,mutations=mutations,restored=final,
        scope='Actual isolated raw-byte publication, without site packages, Git, temporary source tree or CAD/Fusion runtimes')
    target=ROOT/'docs/reports/solid-filled-plates-20260913/portable-verification.json'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(status='pass',mutations_rejected=len(mutations),isolated_root=str(isolated))))


if __name__=='__main__':main()
