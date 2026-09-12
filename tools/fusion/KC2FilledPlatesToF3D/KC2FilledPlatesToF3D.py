"""CON-ARCH-006 actual six-variant F3D export, reopen and STEP readback.

Staging only. The readback STEP must subsequently pass the independent
sectional CAD audit; Fusion mass/bounds alone do not prove final geometry.
"""
from pathlib import Path
import runpy,sys,traceback


def run(context='all'):
    import adsk.core
    root=Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    from tools.kc2_filled_native import preflight_jobs,digest
    folder=root/'.codex-tmp/solid-filled-plates'
    helpers_path=root/'tools/fusion/KC2StepToF3D/KC2StepToF3D.py'
    helpers=runpy.run_path(str(helpers_path))
    app=adsk.core.Application.get()
    report=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='running',
        fusion_version=app.version,physical_qualified=False,outputs={},
        source_sha256={p.relative_to(root).as_posix():digest(p) for p in [Path(__file__),helpers_path,
            root/'tools/kc2_filled_native.py',root/'tools/test_kc2_filled_native.py']})
    documents=[]
    result_path=folder/'native-filled.json'
    write=lambda:helpers['write_result'](result_path,report)
    try:
        jobs=preflight_jobs(folder,root)
        write()
        for job in jobs:
            label=job['label'];source=job['source']
            report['active_job']=label;report['phase']='import_step';write()
            document=app.importManager.importToNewDocument(app.importManager.createSTEPImportOptions(str(source)))
            if not document:raise RuntimeError('STEP import failed')
            documents.append(document)
            design=helpers['find_design'](document)
            bodies=helpers['component_bodies'](design.rootComponent)
            before=helpers['solid_records'](bodies)
            if len(before)!=job['count']:raise RuntimeError('Unexpected source body count')
            helpers['validate_round_trip'](before,before)
            for i,body in enumerate(bodies):body.name=f'KC2 solid-filled {label} part {i+1}'
            target=source.with_suffix('.f3d')
            report['phase']='export_f3d';write()
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):
                raise RuntimeError('Native export failed')
            report['phase']='reopen_f3d';write()
            reopened=app.importManager.importToNewDocument(app.importManager.createFusionArchiveImportOptions(str(target)))
            if not reopened:raise RuntimeError('Native reopen failed')
            documents.append(reopened)
            native=helpers['find_design'](reopened)
            after=helpers['solid_records'](helpers['component_bodies'](native.rootComponent))
            helpers['validate_round_trip'](before,after)
            readback=source.with_name(source.stem+'.native-readback.step')
            report['phase']='export_readback';write()
            if not native.exportManager.execute(native.exportManager.createSTEPExportOptions(str(readback),native.rootComponent)):
                raise RuntimeError('Native readback export failed')
            if digest(source)!=job['step_sha256'] or digest(job['record_path'])!=job['record_sha256']:
                raise RuntimeError('Source changed during Fusion operation')
            report['outputs'][label]=dict(source_step=source.name,source_sha256=digest(source),
                generation_record=job['record_path'].name,generation_sha256=job['record_sha256'],
                f3d=target.name,f3d_sha256=digest(target),source_solids=before,reopened_solids=after,
                readback_step=readback.name,readback_sha256=digest(readback),round_trip_verified=True)
            reopened.close(False);documents.remove(reopened)
            document.close(False);documents.remove(document)
            write()
        for name,sha in report['source_sha256'].items():
            if digest(root/name)!=sha:raise RuntimeError('Exporter changed during run')
        report['status']='pass';report['phase']='complete';report.pop('active_job',None)
    except Exception:
        report['status']='failed';report['error']=traceback.format_exc()
    finally:
        for document in reversed(documents):document.close(False)
        write()


if __name__=='__main__':run()
