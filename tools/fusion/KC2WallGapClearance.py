"""Measure exact reopened native-body A/B clearance; no geometry edits."""
import runpy,json,traceback
from pathlib import Path
import adsk.core,adsk.fusion
ROOT=Path(r'C:\Work\git\kc2');STAGE=ROOT/'.codex-tmp/wall-gap-fix-20260921'
helper=runpy.run_path(str(ROOT/'tools/fusion/KC2WallGapFix.py'))
digest=helper['digest'];write=helper['write'];bodies=helper['bodies']

def run():
    app=adsk.core.Application.get();manager=app.importManager
    plan=json.loads((STAGE/'plan.json').read_text())
    result=dict(status='running',rows={},source_sha256={},errors=[],fusion_version=app.version)
    path=STAGE/'clearance-native.json';write(path,result)
    try:
        for label,job in plan['jobs'].items():
            if not label.startswith('right:'):continue
            source=STAGE/label.replace(':','-')/(job['stem']+'.f3d')
            result['source_sha256'][source.relative_to(ROOT).as_posix()]=digest(source)
            doc=manager.importToNewDocument(manager.createFusionArchiveImportOptions(str(source)))
            if not doc:raise RuntimeError('Cannot reopen '+label)
            try:
                design=adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
                bs=bodies(design)
                if len(bs)!=2:raise ValueError('Wrong A/B body count')
                measured=app.measureManager.measureMinimumDistance(bs[0],bs[1])
                if not measured:raise RuntimeError('Measurement failed')
                result['rows'][label]=dict(minimum_distance_mm=measured.value*10,
                    points_mm=[[p.x*10,p.y*10,p.z*10] for p in (measured.positionOne,measured.positionTwo)])
                write(path,result)
                print(label,result['rows'][label])
            finally:doc.close(False)
        for name in ('tools/fusion/KC2WallGapClearance.py','tools/fusion/KC2WallGapFix.py'):
            result['source_sha256'][name]=digest(ROOT/name)
        result['status']='pass'
    except Exception:result.update(status='failed',errors=[traceback.format_exc()])
    write(path,result)

if __name__=='__main__':run()
