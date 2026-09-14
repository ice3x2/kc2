"""Fusion add-in: convert all four reviewed flat-seam lower STEP jobs to F3D."""
from pathlib import Path
import json
import sys
import traceback

import adsk.core
import adsk.fusion


ROOT = Path(r"C:\Work\git\kc2")
_handlers = []


def _design(document):
    for index in range(document.products.count):
        result = adsk.fusion.Design.cast(document.products.item(index))
        if result:
            return result
    return None


def _bodies(design):
    root = design.rootComponent
    result = [root.bRepBodies.item(index) for index in range(root.bRepBodies.count)]
    for index in range(root.allOccurrences.count):
        component = root.allOccurrences.item(index).component
        result.extend(component.bRepBodies.item(i) for i in range(component.bRepBodies.count))
    return result


def _records(bodies):
    rows = []
    for body in bodies:
        box = body.boundingBox
        rows.append(dict(
            volume_mm3=body.physicalProperties.volume * 1000.0,
            bounds_mm=[box.minPoint.x*10, box.minPoint.y*10, box.minPoint.z*10,
                       box.maxPoint.x*10, box.maxPoint.y*10, box.maxPoint.z*10],
        ))
    return rows


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _execute():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.kc2_flat_central_native import jobs, preflight, digest, validate_native_output

    app = adsk.core.Application.get(); manager = app.importManager
    master = dict(status="running", errors=[], requirements=["CON-ARCH-006", "OPS-ARCH-006"],
                  fusion_version=app.version, outputs={}, physical_qualified=False)
    master_path = ROOT / ".codex-tmp/flat-central-revision/native-generation.json"
    _write(master_path, master)
    for label in jobs():
        documents = []
        try:
            job = preflight(ROOT, label); source = job["source"]
            target = source.with_suffix(".f3d")
            readback = source.with_name(source.stem + ".native-readback.step")
            document = manager.importToNewDocument(manager.createSTEPImportOptions(str(source)))
            if not document: raise RuntimeError("STEP import failed")
            documents.append(document); design = _design(document)
            if not design: raise RuntimeError("Imported document has no design")
            source_bodies = _bodies(design); before = _records(source_bodies)
            if len(before) != job["body_count"]: raise RuntimeError("Source body count differs")
            for index, body in enumerate(source_bodies):
                body.name = "KC2 flat central " + label + " part " + str(index + 1)
            if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(str(target))):
                raise RuntimeError("F3D export failed")
            reopened = manager.importToNewDocument(manager.createFusionArchiveImportOptions(str(target)))
            if not reopened: raise RuntimeError("F3D reopen failed")
            documents.append(reopened); native = _design(reopened)
            if not native: raise RuntimeError("Reopened F3D has no design")
            after = _records(_bodies(native)); errors = validate_native_output(before, after)
            if errors: raise RuntimeError("; ".join(errors))
            if not native.exportManager.execute(native.exportManager.createSTEPExportOptions(str(readback), native.rootComponent)):
                raise RuntimeError("Native STEP readback export failed")
            record = dict(status="pass", errors=[], selected_job=label,
                          requirements=["CON-ARCH-006", "OPS-ARCH-006"],
                          fusion_version=app.version, source_step=source.name,
                          source_sha256=job["source_sha256"],
                          generation_sha256=job["generation_sha256"],
                          source_bodies=before, reopened_bodies=after,
                          f3d=target.name, f3d_sha256=digest(target),
                          readback_step=readback.name, readback_sha256=digest(readback),
                          round_trip_verified=True, physical_qualified=False)
            _write(job["folder"] / "native-generation.json", record)
            master["outputs"][label] = record
        except Exception:
            master["errors"].append(label + ": " + traceback.format_exc())
        finally:
            for document in reversed(documents):
                try: document.close(False)
                except Exception: master["errors"].append(label + ": document close failed")
            _write(master_path, master)
    master["status"] = "pass" if not master["errors"] and len(master["outputs"]) == 4 else "failed"
    _write(master_path, master)


class _StartupHandler(adsk.core.ApplicationEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, _args):
        _execute()


def run(_context=None):
    app = adsk.core.Application.get()
    if getattr(app, "isStartupComplete", False):
        _execute()
        return
    handler = _StartupHandler()
    _handlers.append(handler)
    app.startupCompleted.add(handler)


def stop(_context=None):
    app = adsk.core.Application.get()
    for handler in _handlers:
        try: app.startupCompleted.remove(handler)
        except Exception: pass
    _handlers.clear()
