"""CON-ARCH-006 combined retained lower and filled upper clearance evidence."""
import hashlib,json
from pathlib import Path
from shapely import affinity,wkt
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/solid-filled-plates'


def check_assembly(upper,lower):
    kinds=['mx','choc_v1','deep_sea'];sides=['left','right']
    if set(upper)!={(s,k) for s in sides for k in kinds} or set(lower)!=set(sides):
        raise ValueError('All six upper and both lower footprints required')
    errors=[];results={}
    for kind in kinds:
        left=upper['left',kind].union(lower['left']);right=upper['right',kind].union(lower['right'])
        gap=left.distance(right);overlap=left.intersection(right).area
        results[kind]=dict(minimum_gap_mm=gap,overlap_mm2=overlap)
        if gap<.30 or overlap>1e-8:errors.append(kind+' combined assembly clearance')
    return dict(errors=errors,joined=results)


def review():
    from tools.publish_kc2_local_covers import portable
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    bindings={};upper={};lower={};preserved={}
    def bind(name,sha):
        if digest(ROOT/name)!=sha:raise ValueError('Changed assembly input: '+name)
        if name in bindings and bindings[name]!=sha:raise ValueError('Conflicting source: '+name)
        bindings[name]=sha
    def read(path):
        bind(path.relative_to(ROOT).as_posix(),digest(path))
        return json.loads(path.read_text(encoding='utf8'))
    meshes=read(STAGE/'mesh-contract-review.json')
    if meshes['status']!='pass' or meshes['errors']:raise ValueError('Actual mesh/contract audit failed')
    for name,sha in meshes['source_sha256'].items():bind(name,sha)
    old_manifest=read(ROOT/'hardware/MODELS/kc2_local_cover_manifest.json')
    for name,sha in old_manifest['source_sha256'].items():
        if name.startswith(('hardware/PCB/','hardware/GERBER/')) or (name.startswith('hardware/MODELS/') and '_lower_housing' in name):
            bind(name,sha);preserved[name]=sha
    if len([n for n in preserved if n.startswith(('hardware/PCB/','hardware/GERBER/'))])!=16:
        raise ValueError('Expected all 16 ordered PCB/Gerber files')
    if len([n for n in preserved if '_lower_housing' in n])!=14:raise ValueError('Expected all 14 retained lower CAD files')
    for side in ['left','right']:
        folder=ROOT/'docs/reports/reinforced-covers-20260913'
        prior=read(folder/f'{side}-lower.json');audit=read(folder/f'{side}-lower-review.json')
        if audit['status']!='pass' or audit['errors']:raise ValueError('Retained actual lower audit failed')
        for name,sha in audit['source_sha256'].items():bind(portable(name),sha)
        raw=prior['raw_bounds']
        def transform(g):
            return affinity.translate(affinity.scale(g,xfact=-1,yfact=1,origin=(0,0)),xoff=raw[2]+(124.625 if side=='right' else 0),yoff=raw[1])
        lower[side]=transform(wkt.loads(prior['new_outline_wkt']))
        for kind in ['mx','choc_v1','deep_sea']:
            generated=read(STAGE/f'{side}-{kind}.json')
            t=generated['transform']
            if abs(t['dx']-124.625)>1e-8 or abs(t['dy'])>1e-8:raise ValueError('Original joined transform changed')
            parts=meshes['results'][side+'-'+kind]['parts']
            if any(p['bounds_mm'][2]<4.1-1e-5 for p in parts):raise ValueError('Upper intrudes below PCB top')
            upper[side,kind]=transform(unary_union([wkt.loads(p['footprint_wkt']) for p in parts]))
    result=check_assembly(upper,lower)
    for p in [Path(__file__),ROOT/'tools/test_review_kc2_filled_assembly.py',ROOT/'tools/publish_kc2_local_covers.py']:
        bind(p.relative_to(ROOT).as_posix(),digest(p))
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed during assembly review: '+name)
    report=dict(requirements=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],
        status='failed' if result['errors'] else 'pass',**result,source_sha256=bindings,
        preserved_pcb_gerber_lower_sha256=preserved,physical_qualified=False,
        scope='Actual-audited retained lower footprint plus actual STL upper footprint at unchanged joined positions; physical fit/caps/strength remain pending')
    (STAGE/'assembly-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    r=review();print(json.dumps({k:r[k] for k in ['status','errors','joined']}))
    raise SystemExit(0 if r['status']=='pass' else 1)
