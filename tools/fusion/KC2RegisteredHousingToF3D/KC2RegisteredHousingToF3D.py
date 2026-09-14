"""CON-ARCH-006 one explicitly selected staged housing -> F3D -> STEP readback.

Call run('upper:left:deep_sea') or run('lower:left:normal'); no implicit batch.
Does not approve geometry: independently review readback STEP before publishing.
"""
from pathlib import Path
import runpy,sys,traceback


def run(context=None):
    root=Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    from tools.kc2_registered_native import preflight_job,revalidate_job,digest
    # Reject invalid/incomplete selection before any Fusion document mutation.
    job=preflight_job(root,context)
    import adsk.core
    helper_path=root/'tools/fusion/KC2StepToF3D/KC2StepToF3D.py'
    helper=runpy.run_path(str(helper_path));app=adsk.core.Application.get()
    bindings=dict(job['source_sha256'])
    for p in [Path(__file__),helper_path,root/'tools/kc2_registered_native.py',root/'tools/test_kc2_registered_native.py']:
        bindings[p.relative_to(root).as_posix()]=digest(p)
    frozen=dict(job,source_sha256=bindings)
    source=job['source'];target=source.with_suffix('.f3d')
    readback=source.with_name(source.stem+'.native-readback.step')
    result_path=source.parent/'native-generation.json'
    report=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='running',
        selected_job=job['label'],fusion_version=app.version,physical_qualified=False,
        independent_geometry_verified=False,source_sha256=bindings,outputs={})
    write=lambda:helper['write_result'](result_path,report)
    documents=[]
    try:
        report['phase']='import_step';write()
        document=app.importManager.importToNewDocument(app.importManager.createSTEPImportOptions(str(source)))
        if not document:raise RuntimeError('STEP import failed')
        documents.append(document);design=helper['find_design'](document)
        if design is None:raise RuntimeError('No imported design')
        bodies=helper['component_bodies'](design.rootComponent);before=helper['solid_records'](bodies)
        if len(before)!=job['count']:raise RuntimeError('Unexpected actual source body count')
        helper['validate_round_trip'](before,before)
        for i,body in enumerate(bodies):body.name=f"KC2 registered {job['label']} part {i+1}"
        report['phase']='export_f3d';write()
        if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):
            raise RuntimeError('Native archive export failed')
        archive_sha=digest(target)
        report['phase']='reopen_f3d';write()
        reopened=app.importManager.importToNewDocument(app.importManager.createFusionArchiveImportOptions(str(target)))
        if not reopened:raise RuntimeError('Native archive reopen failed')
        documents.append(reopened);native=helper['find_design'](reopened)
        if native is None:raise RuntimeError('No reopened design')
        after=helper['solid_records'](helper['component_bodies'](native.rootComponent))
        helper['validate_round_trip'](before,after)
        report['phase']='export_readback';write()
        if not native.exportManager.execute(native.exportManager.createSTEPExportOptions(str(readback),native.rootComponent)):
            raise RuntimeError('Readback STEP export failed')
        if digest(target)!=archive_sha:raise RuntimeError('Archive changed after reopen')
        revalidate_job(root,frozen)
        report['outputs'][job['label']]=dict(source_step=source.name,source_sha256=job['step_sha256'],
            generation_record=job['record_path'].name,generation_sha256=job['record_sha256'],
            expected_body_count=job['count'],source_solids=before,reopened_solids=after,
            f3d=target.name,f3d_sha256=archive_sha,readback_step=readback.name,
            readback_sha256=digest(readback),round_trip_verified=True)
        report['status']='pass';report['phase']='complete'
    except Exception:
        report['status']='failed';report['error']=traceback.format_exc()
    finally:
        for document in reversed(documents):
            try:document.close(False)
            except Exception:
                report['status']='failed';report.setdefault('cleanup_errors',[]).append(traceback.format_exc())
        write()
    return report


if __name__=='__main__':run()
