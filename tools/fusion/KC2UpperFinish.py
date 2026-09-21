"""Actual Fusion STEP -> F3D -> reopen -> native STL for upper finish."""
from pathlib import Path
import hashlib,json,traceback
import adsk.core,adsk.fusion

ROOT=Path(r'C:\Work\git\kc2');STAGE=ROOT/'.codex-tmp/upper-finish-20260921'
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):Path(path).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def bodies(design):
    root=design.rootComponent;result=[root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]
    for i in range(root.allOccurrences.count):
        occ=root.allOccurrences.item(i);result.extend(occ.bRepBodies.item(j) for j in range(occ.bRepBodies.count))
    return sorted(result,key=lambda b:b.physicalProperties.centerOfMass.x)
def records(items):
    rows=[]
    for body in items:
        p=body.physicalProperties;b=body.boundingBox
        rows.append(dict(volume_mm3=p.volume*1000,area_mm2=p.area*100,solid=body.isSolid,
            bounds_mm=[[b.minPoint.x*10,b.minPoint.y*10,b.minPoint.z*10],[b.maxPoint.x*10,b.maxPoint.y*10,b.maxPoint.z*10]]))
    return rows

def run(selected=None):
    app=adsk.core.Application.get();manager=app.importManager
    plan=json.loads((STAGE/'plan.json').read_text());labels=list(plan['jobs']) if selected is None else selected
    for label in labels:
        job=plan['jobs'][label];folder=STAGE/label.replace(':','-');source=folder/(job['stem']+'.step')
        gen=json.loads((folder/'generation.json').read_text())
        if gen['step_sha256']!=digest(source) or gen['plan_sha256']!=digest(STAGE/'plan.json'):raise ValueError('Stale CAD '+label)
        target=source.with_suffix('.f3d');documents=[]
        result=dict(status='running',label=label,errors=[],fusion_version=app.version,source_step_sha256=digest(source),
                    plan_sha256=digest(STAGE/'plan.json'),outputs={})
        out=folder/'native.json';write(out,result)
        try:
            doc=manager.importToNewDocument(manager.createSTEPImportOptions(str(source)))
            if not doc:raise RuntimeError('STEP import failed')
            documents.append(doc);design=adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
            bs=bodies(design);before=records(bs)
            if len(bs)!=len(job['parts']) or not all(x['solid'] for x in before):raise ValueError('Invalid STEP bodies')
            for i,b in enumerate(bs):
                b.name='KC2 finished upper '+label+' part '+str(i+1)
                if abs(before[i]['volume_mm3']-gen['parts'][i]['final_volume_mm3'])>.03:raise ValueError('Fusion STEP volume differs')
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):raise RuntimeError('F3D export failed')
            reopened=manager.importToNewDocument(manager.createFusionArchiveImportOptions(str(target)))
            if not reopened:raise RuntimeError('F3D reopen failed')
            documents.append(reopened);native=adsk.fusion.Design.cast(reopened.products.itemByProductType('DesignProductType'))
            bs=bodies(native);after=records(bs)
            if len(after)!=len(before):raise ValueError('F3D body count differs')
            for a,b in zip(before,after):
                bound=max(abs(x-y) for aa,bb in zip(a['bounds_mm'],b['bounds_mm']) for x,y in zip(aa,bb))
                if not b['solid'] or abs(a['volume_mm3']-b['volume_mm3'])>.002 or abs(a['area_mm2']-b['area_mm2'])>.002 or bound>.001:
                    raise ValueError('F3D round trip differs')
            if len(bs)==2:
                measured=app.measureManager.measureMinimumDistance(bs[0],bs[1])
                result['native_ab_clearance']=dict(minimum_distance_mm=measured.value*10,
                    points_mm=[[p.x*10,p.y*10,p.z*10] for p in (measured.positionOne,measured.positionTwo)])
            for body,name in zip(bs,job['stl_names']):
                stl=folder/name;opt=native.exportManager.createSTLExportOptions(body,str(stl))
                opt.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits;opt.isBinaryFormat=True;opt.sendToPrintUtility=False
                opt.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh;opt.surfaceDeviation=.0005;opt.normalDeviation=.08
                if not native.exportManager.execute(opt):raise RuntimeError('STL export failed')
                result['outputs'][name]=digest(stl)
            result['outputs'][target.name]=digest(target)
            result.update(status='pass',before=before,after=after,physical_qualified=False)
        except Exception:result.update(status='failed',errors=[traceback.format_exc()])
        finally:
            for doc in reversed(documents):doc.close(False)
            write(out,result)
        if result['errors']:raise RuntimeError(result['errors'])
        print('Native upper finish complete',label)
