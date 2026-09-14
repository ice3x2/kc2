"""CON-ARCH-006 independently inspect actual F3D readback geometry."""
from pathlib import Path
import argparse,json
from tools.kc2_registered_native import preflight_job,revalidate_job,digest

ROOT=Path(__file__).resolve().parents[1]

def check_source_binding(audit,expected):
    if any(audit.get('source_sha256',{}).get(k)!=v for k,v in expected.items()):
        raise ValueError('Independent source audit is not bound to selected generation and STEP')

def acceptance_errors(source_audit,parts):
    errors=[]
    if source_audit.get('status')!='pass' or source_audit.get('errors'):
        errors.append('Original independent geometry audit failed')
    if not parts:errors.append('Actual native geometry audit absent')
    for p in parts:
        if p.get('status')!='pass' or p.get('errors'):errors.append('Actual native geometry differs')
    return errors

def review(label):
    import cadquery as cq
    from shapely import wkt
    from tools.kc2_solid_plate import Layer
    from tools.kc2_actual_sections import audit_prismatic_solid
    job=preflight_job(ROOT,label);folder=job['source'].parent
    nativepath=folder/'native-generation.json';native=json.loads(nativepath.read_text())
    if native.get('status')!='pass' or native.get('selected_job')!=label:raise ValueError('Incomplete native execution')
    n=native['outputs'][label]
    if n['generation_sha256']!=job['record_sha256'] or n['source_sha256']!=job['step_sha256'] or n['round_trip_verified'] is not True:
        raise ValueError('Native source chain mismatch')
    bindings=dict(job['source_sha256'])
    def bind(path,sha=None):
        key=path.relative_to(ROOT).as_posix();actual=digest(path)
        if sha is not None and sha!=actual:raise ValueError('Changed native input '+key)
        if key in bindings and bindings[key]!=actual:raise ValueError('Conflicting native input '+key)
        bindings[key]=actual
    for name,sha in native['source_sha256'].items():bind(ROOT/name,sha)
    readback=folder/n['readback_step'];bind(readback,n['readback_sha256']);bind(folder/n['f3d'],n['f3d_sha256']);bind(nativepath)
    auditpath=folder/'brep-review.json' if job['family']=='upper' else folder.parent/(job['side']+'-void-review.json')
    audit=json.loads(auditpath.read_text());bind(auditpath)
    check_source_binding(audit,{job['source'].relative_to(ROOT).as_posix():job['step_sha256'],
        job['record_path'].relative_to(ROOT).as_posix():job['record_sha256']})
    for name,sha in audit['source_sha256'].items():bind(ROOT/name,sha)
    for p in [Path(__file__),ROOT/'tools/test_review_kc2_registered_native.py',ROOT/'tools/review_kc2_filled_plates.py',ROOT/'tools/kc2_solid_plate.py',
              ROOT/'tools/kc2_actual_sections.py',ROOT/'tools/test_kc2_actual_sections.py']:
        bind(p)
    print('import actual native readback',label,flush=True)
    actual=cq.importers.importStep(str(readback)).solids().vals()
    if len(actual)!=job['count'] or any(not s.isValid() for s in actual):raise ValueError('Invalid native body count/shape')
    record=json.loads(job['record_path'].read_text());parts=[]
    if job['family']=='upper':
        remaining=list(actual)
        for i,p in enumerate(record['parts']):
            wanted=p['bounds_mm']
            def bounds_error(shape):
                b=shape.BoundingBox();got=(b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax)
                return sum(abs(x-y) for x,y in zip(got,wanted))
            s=min(remaining,key=bounds_error);remaining.remove(s)
            print('complete native section audit',label,i,flush=True)
            parts.append(audit_prismatic_solid(s,[Layer(l['z0'],l['z1'],wkt.loads(l['wkt'])) for l in p['layers']]))
    else:
        baseline=cq.importers.importStep(str(job['source'])).solids().vals()
        # Match bodies spatially rather than trusting import ordering.
        remaining=list(actual)
        for i,s in enumerate(baseline):
            a=min(remaining,key=lambda v:(v.Center()-s.Center()).Length);remaining.remove(a)
            print('native symmetric material difference',label,i,flush=True)
            missing=s.cut(a).Volume();extra=a.cut(s).Volume()
            errors=[] if missing<=.002 and extra<=.002 else ['Native material differs']
            parts.append(dict(status='pass' if not errors else 'failed',errors=errors,missing_mm3=missing,extra_mm3=extra))
    revalidate_job(ROOT,dict(source_sha256=bindings))
    errors=acceptance_errors(audit,parts)
    result=dict(status='pass' if not errors else 'failed',errors=errors,selected_job=label,requirements=['CON-ARCH-006','OPS-ARCH-006'],
        source_sha256=bindings,parts=parts,independent_geometry_verified=not errors,physical_qualified=False)
    (folder/'native-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],errors,flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');a=p.parse_args()
    raise SystemExit(0 if review(a.label)['status']=='pass' else 1)
