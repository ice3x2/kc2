"""CON-ARCH-006: original STEP vs F3D-derived STEP under identical CQ/OCP mass calculation."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/local-cover-build'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def adaptive_volume(shape):
    """Use controlled quadrature, not default non-adaptive trimmed-face mass."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    props=GProp_GProps()
    error=BRepGProp.VolumeProperties_s(shape.wrapped,props,1e-9,True,False)
    volume=props.Mass()
    if not math.isfinite(error) or not 0<=error<=1e-8 or not math.isfinite(volume) or volume<=0:
        raise ValueError('Native volume integration failed to converge')
    return volume


def compare_records(before,after):
    def valid(row):
        b=row.get('bounds_mm',[]);v=row.get('volume_mm3')
        return (len(b)==6 and all(type(x) in (int,float) and math.isfinite(x) for x in b+[v])
                and v>0 and all(b[i+3]>b[i] for i in range(3)))
    if not before or len(before)!=len(after):return ['Native same-kernel solid count changed']
    if not all(valid(r) for r in before+after):return ['Native same-kernel records malformed']
    remaining=list(after)
    for row in before:
        match=next((i for i,r in enumerate(remaining)
                    if all(abs(a-b)<=.001 for a,b in zip(row['bounds_mm'],r['bounds_mm']))
                    and abs(row['volume_mm3']-r['volume_mm3'])<=max(.002,row['volume_mm3']*1e-6)),None)
        if match is None:return ['Native same-kernel bounds/volume mismatch']
        remaining.pop(match)
    return []


def review(context='left_mx_upper'):
    import cadquery as cq
    export_path=STAGE/f'native-review-export-{context}.json'
    export=json.loads(export_path.read_text(encoding='utf8'))
    if export.get('status')!='exported_not_geometry_verified' or export.get('physical_qualified') is not False:
        raise ValueError('Native verification export incomplete')
    labels={f'{side}_{kind}{suffix}' for side in ['left','right']
            for kind,suffix in [('lower',''),('lower','_magnetic'),('mx_upper','')]}
    expected=labels if context=='all' else {context}
    if not expected.issubset(labels) or set(export['outputs'])!=expected:raise ValueError('Wrong native verification inventory')
    sources=dict(export['source_sha256'])
    for path in [Path(__file__),ROOT/'tools/test_review_kc2_local_native.py',export_path]:
        sources[path.relative_to(ROOT).as_posix()]=digest(path)
    for name,sha in sources.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed export source: '+name)
    outputs={};errors=[]
    def records(path):
        shapes=cq.importers.importStep(str(path)).solids().vals()
        if not shapes or any(not shape.isValid() for shape in shapes):raise ValueError('Invalid STEP solids')
        result=[];defaults=[]
        for shape in shapes:
            b=shape.BoundingBox()
            bounds=[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]
            result.append(dict(bounds_mm=bounds,volume_mm3=adaptive_volume(shape)))
            defaults.append(dict(bounds_mm=bounds,volume_mm3=shape.Volume()))
        return result,defaults
    for label,row in export['outputs'].items():
        print(label,'importing original and native-derived STEP in identical kernel',flush=True)
        for field in ['source_f3d','source_step','verification_step']:
            name=row[field]
            if Path(name).name!=name:raise ValueError('Nonlocal diagnostic path')
            path=STAGE/name
            if digest(path)!=row[field+'_sha256']:raise ValueError('Changed native diagnostic input')
            sources[path.relative_to(ROOT).as_posix()]=digest(path)
        before,default_before=records(STAGE/row['source_step'])
        after,default_after=records(STAGE/row['verification_step'])
        failures=compare_records(before,after)
        if len(before)!=(1 if label.startswith('left_') else 2):failures.append('Wrong original part count')
        outputs[label]=dict(source_solids=before,reopened_solids=after,errors=failures,
                            default_source_solids=default_before,default_reopened_solids=default_after,
                            source_step_sha256=row['source_step_sha256'],source_f3d_sha256=row['source_f3d_sha256'],
                            verification_step_sha256=row['verification_step_sha256'])
        errors.extend(label+': '+e for e in failures)
    if any(digest(ROOT/name)!=sha for name,sha in sources.items()):raise ValueError('Source changed during native review')
    report=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='failed' if errors else 'pass',errors=errors,
                physical_qualified=False,source_sha256=sources,sources_unchanged=True,outputs=outputs,
                method='F3D reopened in Fusion, exported diagnostic STEP, both STEP files imported by same CadQuery/OpenCascade process',
                cadquery_version=cq.__version__,bounds_tolerance_mm=.001,
                mass_integration_relative_epsilon=1e-9,
                volume_tolerance='max(0.002 mm3, original volume * 1e-6)',
                scope='Native geometry bounds/volume round trip; no physical qualification')
    (STAGE/f'native-kernel-review-{context}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':report['status'],'errors':errors,'outputs':outputs}),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='left_mx_upper')
    raise SystemExit(bool(review(parser.parse_args().label)['errors']))
