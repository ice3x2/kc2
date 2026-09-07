"""CON-ARCH-006: Fusion export/reopen only optional magnetic lower files."""
import json
import runpy
import traceback
from pathlib import Path
import adsk.core


def export_jobs(folder):
    return {side: folder / f'kc2_{side}_lower_housing_magnetic.step' for side in ['left', 'right']}


def run(_context=''):
    root = Path(r'C:\Work\git\kc2')
    folder = root / 'hardware/MODELS'
    helpers = runpy.run_path(str(root / 'tools/fusion/KC2StepToF3D/KC2StepToF3D.py'))
    app = adsk.core.Application.get()
    result = {'requirements': ['CON-ARCH-006','OPS-ARCH-006'], 'status':'failed',
              'fusion_version':app.version, 'physical_qualified':False, 'outputs':{}}
    report = folder / 'kc2_fusion_export_result_magnetic.json'
    documents = []
    try:
        for side, source in export_jobs(folder).items():
            if not source.is_file():
                raise FileNotFoundError(source)
            document = app.importManager.importToNewDocument(app.importManager.createSTEPImportOptions(str(source)))
            if not document:
                raise RuntimeError('STEP import failed')
            documents.append(document)
            design = helpers['find_design'](document)
            bodies = helpers['component_bodies'](design.rootComponent)
            before = helpers['solid_records'](bodies)
            if len(before) != (1 if side == 'left' else 2):
                raise RuntimeError('Wrong source solid count')
            for index, body in enumerate(bodies):
                body.name = f'KC2 {side} lower magnetic {index+1}'
            target = source.with_suffix('.f3d')
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):
                raise RuntimeError('Native archive export failed')
            reopened = app.importManager.importToNewDocument(app.importManager.createFusionArchiveImportOptions(str(target)))
            if not reopened:
                raise RuntimeError('Native archive reopen failed')
            documents.append(reopened)
            after = helpers['solid_records'](helpers['component_bodies'](helpers['find_design'](reopened).rootComponent))
            helpers['validate_round_trip'](before, after)
            result['outputs'][side] = {'source_step':str(source.relative_to(root)),
                'source_step_sha256':helpers['sha256'](source), 'f3d':str(target.relative_to(root)),
                'f3d_sha256':helpers['sha256'](target), 'source_solids':before,
                'archive_reimport_solids':after, 'solid_round_trip_verified':True}
            reopened.close(False)
            documents.remove(reopened)
            document.close(False)
            documents.remove(document)
            helpers['write_result'](report,result)
        result['status'] = 'pass'
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        for document in reversed(documents):
            document.close(False)
        result['script_sha256'] = helpers['sha256'](Path(__file__))
        helpers['write_result'](report,result)


if __name__ == '__main__':
    run()
