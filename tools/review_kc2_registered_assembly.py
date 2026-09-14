"""CON-ARCH-006 actual lower upper-height strata against audited upper layers.

Central friction, under-PCB component voids and right split capture have separate
audits. This audit establishes the PCB-surround clearance and plate registration
at unchanged Z datums, not cap travel or printed fit/strength.
"""
from pathlib import Path
import argparse,hashlib,json,math
from shapely import wkt
from shapely.ops import unary_union
from tools.kc2_actual_sections import section_geometry

ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def void_path(side):
    if side not in ('left','right'):raise ValueError('Unknown void side')
    return '.codex-tmp/registered-housing-fit/lower/'+('right-receiver-strata-transfer.json' if side=='right' else 'left-void-review.json')

def qualify_void(side,read_bytes):
    """Validate actual direct/explicit derived semantics and freeze every read."""
    from tools.publish_kc2_registered_housings import check_void_proof
    from tools.kc2_registered_release_gate import safe_relative
    bindings={}
    def read(name):
        safe_relative(name);data=read_bytes(name);sha=hashlib.sha256(data).hexdigest()
        if name in bindings and bindings[name]!=sha:raise ValueError('Void source changed during qualification')
        bindings[name]=sha;return data
    record=json.loads(read(void_path(side)))
    check_void_proof(record,side,False,read)
    if not record.get('source_sha256'):raise ValueError('Missing complete void proof sources')
    for name,sha in record['source_sha256'].items():
        if hashlib.sha256(read(name)).hexdigest()!=sha:raise ValueError('Stale void proof source '+name)
    for name in ('publish_kc2_registered_housings','test_publish_kc2_registered_housings','kc2_registered_release_gate'):
        read('tools/'+name+'.py')
    # Derived validators read and bind their own executed dependency closure.
    # Freeze it alongside the direct dispatcher, not just the report pass flag.
    for name,sha in list(bindings.items()):
        if hashlib.sha256(read(name)).hexdigest()!=sha:raise ValueError('Void source freeze failed')
    return record,bindings
def overlap_errors(lower,upper):
    return ['lower/upper material intersection'] if lower.intersection(upper).area>.001 else []

def review(side):
    import cadquery as cq
    if side not in ('left','right'):raise ValueError('Unknown side')
    stage=ROOT/'.codex-tmp/registered-housing-fit';bindings={};errors=[]
    def bind(p,sha=None):
        name=p.relative_to(ROOT).as_posix();actual=digest(p)
        if sha is not None and actual!=sha:raise ValueError('Changed input '+name)
        if name in bindings and bindings[name]!=actual:raise ValueError('Conflicting input '+name)
        bindings[name]=actual
    def read(p):
        bind(p);r=json.loads(p.read_text())
        for name,sha in r.get('source_sha256',{}).items():bind(ROOT/name,sha)
        return r
    uppers={}
    for kind in ('mx','choc_v1','deep_sea'):
        folder=stage/'upper'/(side+'-'+kind);r=read(folder/'generation.json');a=read(folder/'brep-review.json')
        if r['status']!='generated_pending_independent_review' or a['status']!='pass' or a['errors']:raise ValueError('Upper actual review not passed')
        step=folder/f'kc2_{side}_{kind}_upper_housing.step'
        for path in (folder/'generation.json',step):
            if a['source_sha256'].get(path.relative_to(ROOT).as_posix())!=digest(path):raise ValueError('Upper review does not bind source')
        uppers[kind]=[(l['z0'],l['z1'],wkt.loads(l['wkt'])) for part in r['parts'] for l in part['layers']]
    void,void_bindings=qualify_void(side,lambda name:(ROOT/name).read_bytes())
    for name,sha in void_bindings.items():bind(ROOT/name,sha)
    perimeter=read(ROOT/'.codex-tmp/perimeter-wall-plans.json')
    # The declared inner envelope includes actual PCB+.30 and switch-body reserves.
    # Only inspect the physical PCB Z interval for that envelope.
    inner=wkt.loads(perimeter['sides'][side]['inner_wkt'])
    rows={};reference=None
    for variant in ('normal','magnetic'):
        folder=stage/'lower'/(side+'-'+variant);r=read(folder/'generation.json')
        name=f'kc2_{side}_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step'
        path=folder/name;bind(path,r['outputs'][name])
        if void['source_sha256'].get(path.relative_to(ROOT).as_posix())!=digest(path):raise ValueError('Void review does not bind actual lower')
        print('import lower for actual stack',side,variant,flush=True)
        shapes=cq.importers.importStep(str(path)).solids().vals()
        levels={2.5,4.1,4.35,4.4,5.0,5.2}
        for shape in shapes:
            for face in shape.Faces():
                b=face.BoundingBox()
                if b.zmax<=2.5+1e-6:continue
                if face.geomType()!='PLANE':errors.append('non-prismatic lower above PCB bottom');continue
                nz=abs(face.normalAt().z)
                if min(nz,abs(nz-1))>1e-6:errors.append('sloped lower above PCB bottom')
            for v in shape.Vertices():
                if v.Z>2.5+1e-5:levels.add(round(v.Z,5))
        levels=sorted(levels);sections={};checks=[]
        for lo,hi in zip(levels,levels[1:]):
            if hi-lo<1e-6:continue
            z=(lo+hi)/2
            print('actual lower section',side,variant,z,flush=True)
            actual=unary_union([section_geometry(s,z) for s in shapes]);sections[z]=actual
            if z<4.1 and actual.intersection(inner).area>.001:errors.append('PCB/body clearance envelope obstructed')
            if z>=4.1:
                for kind,layers in uppers.items():
                    upper=unary_union([g for a,b,g in layers if a<=z<b])
                    errs=overlap_errors(actual,upper);errors.extend(kind+': '+e for e in errs)
                    checks.append(dict(kind=kind,z_mm=z,overlap_mm2=actual.intersection(upper).area,
                        gap_mm=None if actual.is_empty or upper.is_empty else actual.distance(upper)))
        if reference is not None:
            if set(reference)!=set(sections):errors.append('normal/magnetic upper-height strata differ')
            else:
                for z in sections:
                    if sections[z].symmetric_difference(reference[z]).area>.001:errors.append('normal/magnetic upper registration differs')
        reference=sections;rows[variant]=dict(checks=checks,levels_mm=levels)
    for p in (Path(__file__),ROOT/'tools/test_review_kc2_registered_assembly.py',ROOT/'tools/review_kc2_filled_plates.py',
              ROOT/'tools/kc2_actual_sections.py',ROOT/'tools/test_kc2_actual_sections.py'):bind(p)
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed during assembly review')
    result=dict(status='pass' if not errors else 'failed',errors=sorted(set(errors)),side=side,requirements=['CON-ARCH-006','CON-ARCH-007'],
        physical_qualified=False,source_sha256=bindings,variants=rows,
        scope='Actual prismatic lower Z>=2.5 sections against independently actual-audited upper layers; central contact and under-PCB voids separate')
    (stage/(side+'-stack-review.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result['errors'],flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('side');a=p.parse_args();raise SystemExit(0 if review(a.side)['status']=='pass' else 1)
