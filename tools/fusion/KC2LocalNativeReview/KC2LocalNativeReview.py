"""CON-ARCH-006: reopen existing F3D and export diagnostic STEP only.

Does not rewrite source STEP/F3D or claim geometric equivalence. That is tested
by review_kc2_local_native using the same OpenCascade importer on both files.
"""
import hashlib
import json
from pathlib import Path
import runpy
import traceback
import adsk.core


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(context='left_mx_upper'):
    root=Path(__file__).resolve().parents[3]
    folder=root/'.codex-tmp/local-cover-build'
    helper=root/'tools/fusion/KC2StepToF3D/KC2StepToF3D.py'
    helpers=runpy.run_path(str(helper))
    app=adsk.core.Application.get()
    jobs={f'{side}_{kind}{suffix}':f'kc2_{side}_{kind}_housing{suffix}'
          for side in ['left','right'] for kind,suffix in [('lower',''),('lower','_magnetic'),('mx_upper','')]}
    if context!='all':jobs={context:jobs[context]}
    sources={p.relative_to(root).as_posix():digest(p) for p in [Path(__file__),helper]}
    for base in jobs.values():
        for extension in ['.f3d','.step']:
            path=folder/(base+extension);sources[path.relative_to(root).as_posix()]=digest(path)
    report=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='failed',
                physical_qualified=False,fusion_version=app.version,source_sha256=sources,outputs={})
    document=None
    target=folder/f'native-review-export-{context}.json'
    try:
        for label,base in jobs.items():
            source=folder/(base+'.f3d')
            document=app.importManager.importToNewDocument(app.importManager.createFusionArchiveImportOptions(str(source)))
            if not document:raise RuntimeError('F3D reopen failed')
            design=helpers['find_design'](document)
            bodies=helpers['component_bodies'](design.rootComponent)
            if len(bodies)!=(1 if label.startswith('left_') else 2):raise RuntimeError('Unexpected native body count')
            output=folder/f'native-check-{label}.step'
            options=design.exportManager.createSTEPExportOptions(str(output))
            if not options or not design.exportManager.execute(options):raise RuntimeError('Verification STEP export failed')
            report['outputs'][label]=dict(source_f3d=source.name,source_f3d_sha256=digest(source),
                source_step=base+'.step',source_step_sha256=digest(folder/(base+'.step')),
                verification_step=output.name,verification_step_sha256=digest(output),body_count=len(bodies))
            document.close(False);document=None
            target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        if any(digest(root/p)!=sha for p,sha in sources.items()):raise RuntimeError('Source changed during native diagnostic')
        report['status']='exported_not_geometry_verified'
        report['sources_unchanged']=True
    except Exception:report['error']=traceback.format_exc()
    finally:
        if document:document.close(False)
        target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':run()
