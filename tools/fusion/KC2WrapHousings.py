"""CON-ARCH-006 real Fusion import/archive/reopen/readback for ten sleeve jobs.

Run this file in Fusion's Python console, then run(). It writes staged files
only, closes only documents opened by this function, and never publishes.
"""
from pathlib import Path
import sys
import traceback
import json

ROOT = Path(r'C:\Work\git\kc2')


def run(selected=None):
    import adsk.core
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.kc2_wrap_native import jobs, preflight, digest, STAGE, select_jobs
    from tools.kc2_flat_central_native import validate_native_output
    from tools.fusion.KC2FlatCentralToF3D.KC2FlatCentralToF3D import _design, _bodies, _records, _write
    app = adsk.core.Application.get()
    manager = app.importManager
    master = dict(status='running', errors=[], requirements=['CON-ARCH-006', 'OPS-ARCH-006'],
                  fusion_version=app.version, outputs={}, physical_qualified=False)
    master_path = ROOT/STAGE/'native-generation.json'
    # Completed per-job archives may be retained across explicit batches only
    # when every source/archive/readback identity still matches the current job.
    for label, spec in jobs().items():
        record_path = ROOT/STAGE/spec['folder']/'native-generation.json'
        if not record_path.is_file():
            continue
        try:
            job = preflight(ROOT, label)
            row = json.loads(record_path.read_text())
            if (row.get('status') == 'pass' and row.get('round_trip_verified') is True and
                    row['source_sha256'] == job['source_sha256'] and
                    row['generation_sha256'] == job['generation_sha256'] and
                    digest(job['folder']/row['f3d']) == row['f3d_sha256'] and
                    digest(job['folder']/row['readback_step']) == row['readback_sha256'] and
                    not validate_native_output(row['source_bodies'], row['reopened_bodies'])):
                master['outputs'][label] = row
        except Exception:
            pass  # Stale/missing records are not evidence and will not be retained.
    _write(master_path, master)
    for label in select_jobs(selected):
        documents = []
        try:
            job = preflight(ROOT, label)
            source = job['source']
            target = source.with_suffix('.f3d')
            readback = source.with_name(source.stem+'.native-readback.step')
            document = manager.importToNewDocument(manager.createSTEPImportOptions(str(source)))
            if not document:
                raise RuntimeError('STEP import failed')
            documents.append(document)
            design = _design(document)
            if not design:
                raise RuntimeError('No imported design')
            bodies = _bodies(design)
            before = _records(bodies)
            if len(before) != job['body_count']:
                raise RuntimeError('Wrong STEP body count')
            for i, body in enumerate(bodies):
                body.name = f'KC2 continuous sleeve {label} part {i+1}'
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):
                raise RuntimeError('F3D export failed')
            reopened = manager.importToNewDocument(manager.createFusionArchiveImportOptions(str(target)))
            if not reopened:
                raise RuntimeError('F3D reopen failed')
            documents.append(reopened)
            native = _design(reopened)
            after = _records(_bodies(native))
            errors = validate_native_output(before, after)
            if errors:
                raise RuntimeError('; '.join(errors))
            if not native.exportManager.execute(native.exportManager.createSTEPExportOptions(str(readback), native.rootComponent)):
                raise RuntimeError('Readback export failed')
            row = dict(status='pass', errors=[], selected_job=label, fusion_version=app.version,
                source_step=source.name, source_sha256=job['source_sha256'],
                generation_sha256=job['generation_sha256'], source_bodies=before, reopened_bodies=after,
                f3d=target.name, f3d_sha256=digest(target), readback_step=readback.name,
                readback_sha256=digest(readback), round_trip_verified=True, physical_qualified=False)
            _write(job['folder']/'native-generation.json', row)
            master['outputs'][label] = row
        except Exception:
            master['errors'].append(label+': '+traceback.format_exc())
        finally:
            for document in reversed(documents):
                try:
                    document.close(False)
                except Exception:
                    master['errors'].append(label+': document close failed')
            _write(master_path, master)
    master['status'] = ('failed' if master['errors'] else
                        'pass' if set(master['outputs']) == set(jobs()) else 'partial')
    _write(master_path, master)
