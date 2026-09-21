"""CON-ARCH-006 actual Fusion archive round trip and native STL export."""
from pathlib import Path
import json
import hashlib
import traceback
import adsk.core
import adsk.fusion

ROOT=Path(r'C:\Work\git\kc2')
STAGE=ROOT/'.codex-tmp/wall-gap-fix-20260921'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def bodies(design):
    root=design.rootComponent
    result=[root.bRepBodies.item(i) for i in range(root.bRepBodies.count)]
    for i in range(root.allOccurrences.count):
        occ=root.allOccurrences.item(i)
        result.extend(occ.bRepBodies.item(j) for j in range(occ.bRepBodies.count))
    return sorted(result,key=lambda b:b.physicalProperties.centerOfMass.x)

def records(items):
    result=[]
    for body in items:
        p=body.physicalProperties;b=body.boundingBox
        result.append(dict(volume_mm3=p.volume*1000,area_mm2=p.area*100,
            bounds_mm=[[b.minPoint.x*10,b.minPoint.y*10,b.minPoint.z*10],
                       [b.maxPoint.x*10,b.maxPoint.y*10,b.maxPoint.z*10]],solid=body.isSolid))
    return result

def run(selected=None):
    app=adsk.core.Application.get();manager=app.importManager
    plan=json.loads((STAGE/'plan.json').read_text())
    labels=list(plan['jobs']) if selected is None else selected
    for label in labels:
        folder=STAGE/label.replace(':','-');job=plan['jobs'][label]
        source=folder/(job['stem']+'.step')
        gen=json.loads((folder/'generation.json').read_text())
        if gen['step_sha256']!=digest(source) or gen['plan_sha256']!=digest(STAGE/'plan.json'):
            raise ValueError('Stale CAD job '+label)
        target=source.with_suffix('.f3d');documents=[]
        result=dict(status='running',label=label,errors=[],fusion_version=app.version,
                    source_step_sha256=digest(source),plan_sha256=digest(STAGE/'plan.json'),outputs={})
        path=folder/'native.json';write(path,result)
        try:
            doc=manager.importToNewDocument(manager.createSTEPImportOptions(str(source)))
            if not doc:raise RuntimeError('STEP import failed')
            documents.append(doc)
            design=adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
            bs=bodies(design);before=records(bs)
            if len(bs)!=len(job['parts']) or not all(r['solid'] for r in before):raise ValueError('Invalid STEP body count')
            for i,b in enumerate(bs):
                b.name='KC2 joined wall '+label+' part '+str(i+1)
                if abs(before[i]['volume_mm3']-gen['parts'][i]['final_volume_mm3'])>.03:
                    raise ValueError('Imported STEP volume differs from reviewed CAD')
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):
                raise RuntimeError('F3D export failed')
            reopened=manager.importToNewDocument(manager.createFusionArchiveImportOptions(str(target)))
            if not reopened:raise RuntimeError('F3D reopen failed')
            documents.append(reopened)
            native=adsk.fusion.Design.cast(reopened.products.itemByProductType('DesignProductType'))
            bs=bodies(native);after=records(bs)
            if len(after)!=len(before):raise ValueError('Reopened body count differs')
            for a,b in zip(before,after):
                if (not b['solid'] or abs(a['volume_mm3']-b['volume_mm3'])>.002 or
                    abs(a['area_mm2']-b['area_mm2'])>.002 or
                    max(abs(x-y) for ar,br in zip(a['bounds_mm'],b['bounds_mm']) for x,y in zip(ar,br))>.001):
                    raise ValueError('F3D round trip differs')
            for body,name in zip(bs,job['stl_names']):
                stl=folder/name
                options=native.exportManager.createSTLExportOptions(body,str(stl))
                options.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits
                options.isBinaryFormat=True;options.sendToPrintUtility=False
                options.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
                options.surfaceDeviation=.0005;options.normalDeviation=.08
                if not native.exportManager.execute(options):raise RuntimeError('Native STL export failed')
                result['outputs'][name]=digest(stl)
            result['outputs'][target.name]=digest(target)
            result.update(status='pass',before=before,after=after,physical_qualified=False)
        except Exception:
            result.update(status='failed',errors=[traceback.format_exc()])
        finally:
            for doc in reversed(documents):doc.close(False)
            write(path,result)
        if result['errors']:raise RuntimeError(result['errors'])
        print('Native gap fix complete',label)
