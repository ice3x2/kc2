"""CON-ARCH-006: actual native exports/reopens, staged local-cover variants only."""
from pathlib import Path
import runpy
import traceback
import adsk.core


def export_jobs(folder):
    return {f'{side}_{kind}{suffix}':folder/f'kc2_{side}_{kind}_housing{suffix}.step'
            for side in ['left','right'] for kind,suffix in
            [('lower',''),('lower','_magnetic'),('mx_upper','')]}


def run(context='all'):
    root=Path(__file__).resolve().parents[3]
    folder=root/'.codex-tmp/local-cover-build'
    helpers=runpy.run_path(str(root/'tools/fusion/KC2StepToF3D/KC2StepToF3D.py'))
    app=adsk.core.Application.get()
    report={'requirement':'CON-ARCH-006','status':'failed','fusion_version':app.version,
            'physical_qualified':False,'outputs':{},'script_sha256':helpers['sha256'](Path(__file__))}
    documents=[]
    try:
        jobs=export_jobs(folder)
        if context in ['left','right']:jobs={k:p for k,p in jobs.items() if k.startswith(context+'_')}
        if any(not p.is_file() for p in jobs.values()):raise RuntimeError('Missing staged STEP')
        for label,source in jobs.items():
            document=app.importManager.importToNewDocument(app.importManager.createSTEPImportOptions(str(source)))
            if not document:raise RuntimeError('STEP import failed')
            documents.append(document)
            design=helpers['find_design'](document)
            bodies=helpers['component_bodies'](design.rootComponent)
            before=helpers['solid_records'](bodies)
            expected=1 if label.startswith('left_') else 2
            if len(before)!=expected:raise RuntimeError('Unexpected source bodies')
            for i,body in enumerate(bodies):body.name=f'KC2 local-cover {label} part{i+1}'
            target=source.with_suffix('.f3d')
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):
                raise RuntimeError('Native export failed')
            reopened=app.importManager.importToNewDocument(app.importManager.createFusionArchiveImportOptions(str(target)))
            if not reopened:raise RuntimeError('Native reopen failed')
            documents.append(reopened)
            after=helpers['solid_records'](helpers['component_bodies'](helpers['find_design'](reopened).rootComponent))
            helpers['validate_round_trip'](before,after)
            report['outputs'][label]={'source_step':source.name,'source_sha256':helpers['sha256'](source),
                'f3d':target.name,'f3d_sha256':helpers['sha256'](target),
                'source_solids':before,'reopened_solids':after,'round_trip_verified':True}
            reopened.close(False);documents.remove(reopened)
            document.close(False);documents.remove(document)
            helpers['write_result'](folder/f'native-{context}.json',report)
        report['status']='pass'
    except Exception:report['error']=traceback.format_exc()
    finally:
        for document in reversed(documents):document.close(False)
        helpers['write_result'](folder/f'native-{context}.json',report)


if __name__=='__main__':run()
