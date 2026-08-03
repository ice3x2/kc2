"""Import KC2 STEP housings into Fusion and export native F3D archives."""

from __future__ import annotations

import json
import hashlib
import os
import traceback
from pathlib import Path

import adsk.core
import adsk.fusion

DEFAULT_REPO_ROOT = Path(r"C:\Work\git\kc2")


def find_design(document: adsk.core.Document) -> adsk.fusion.Design | None:
    for index in range(document.products.count):
        design = adsk.fusion.Design.cast(document.products.item(index))
        if design:
            return design
    return None


def component_bodies(root: adsk.fusion.Component) -> list[adsk.fusion.BRepBody]:
    bodies = [root.bRepBodies.item(index) for index in range(root.bRepBodies.count)]
    for index in range(root.allOccurrences.count):
        occurrence = root.allOccurrences.item(index)
        component = occurrence.component
        bodies.extend(component.bRepBodies.item(body_index) for body_index in range(component.bRepBodies.count))
    return bodies


def bounding_box_mm(bodies: list[adsk.fusion.BRepBody]) -> list[float]:
    boxes = [body.boundingBox for body in bodies]
    return [
        min(box.minPoint.x for box in boxes) * 10.0,
        min(box.minPoint.y for box in boxes) * 10.0,
        min(box.minPoint.z for box in boxes) * 10.0,
        max(box.maxPoint.x for box in boxes) * 10.0,
        max(box.maxPoint.y for box in boxes) * 10.0,
        max(box.maxPoint.z for box in boxes) * 10.0,
    ]


def body_bounding_boxes_mm(bodies: list[adsk.fusion.BRepBody]) -> list[list[float]]:
    return [
        [
            body.boundingBox.minPoint.x * 10.0,
            body.boundingBox.minPoint.y * 10.0,
            body.boundingBox.minPoint.z * 10.0,
            body.boundingBox.maxPoint.x * 10.0,
            body.boundingBox.maxPoint.y * 10.0,
            body.boundingBox.maxPoint.z * 10.0,
        ]
        for body in bodies
    ]


def write_result(path: Path, result: dict) -> None:
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(_context: str) -> None:
    app = adsk.core.Application.get()
    ui = app.userInterface
    repo_root = Path(os.environ.get("KC2_REPO_ROOT", str(DEFAULT_REPO_ROOT))).resolve()
    case_dir = repo_root / "hardware" / "case"
    result_path = case_dir / "kc2_fusion_export_result.json"
    result = {
        "status": "failed",
        "fusion_version": app.version,
        "requirement": "CON-ARCH-003",
        "outputs": {},
    }

    try:
        import_manager = app.importManager
        jobs = {
            "left": case_dir / "kc2_left_lower_housing.step",
            "right": case_dir / "kc2_right_lower_housing.step",
        }
        expected_body_counts = {"left": 1, "right": 2}
        for side, step_path in jobs.items():
            if not step_path.exists():
                raise FileNotFoundError(step_path)
            f3d_path = step_path.with_suffix(".f3d")
            options = import_manager.createSTEPImportOptions(str(step_path))
            options.isViewFit = False
            document = import_manager.importToNewDocument(options)
            if not document:
                raise RuntimeError(f"Fusion failed to import {step_path}")

            try:
                adsk.doEvents()
                design = find_design(document)
                if not design:
                    raise RuntimeError(f"Imported document has no Fusion design: {step_path}")
                root = design.rootComponent
                bodies = component_bodies(root)
                expected_body_count = expected_body_counts[side]
                if len(bodies) != expected_body_count:
                    raise RuntimeError(
                        f"Expected {expected_body_count} imported bodies for {side}, "
                        f"found {len(bodies)}"
                    )
                for index, body in enumerate(bodies, start=1):
                    suffix = f" Part {index}" if expected_body_count > 1 else ""
                    body.name = f"KC2 {side.capitalize()} Lower Housing{suffix}"

                export_manager = design.exportManager
                export_options = export_manager.createFusionArchiveExportOptions(str(f3d_path))
                export_ok = bool(export_manager.execute(export_options))
                if not export_ok:
                    raise RuntimeError(f"Fusion archive export failed for {side}")

                archive_document = None
                try:
                    archive_options = import_manager.createFusionArchiveImportOptions(str(f3d_path))
                    archive_document = import_manager.importToNewDocument(archive_options)
                    if not archive_document:
                        raise RuntimeError(f"Fusion failed to re-import {f3d_path}")
                    adsk.doEvents()
                    archive_design = find_design(archive_document)
                    if not archive_design:
                        raise RuntimeError(f"Re-imported archive has no Fusion design: {f3d_path}")
                    archive_bodies = component_bodies(archive_design.rootComponent)
                    if len(archive_bodies) != expected_body_count:
                        raise RuntimeError(
                            f"Expected {expected_body_count} re-imported bodies for {side}, "
                            f"found {len(archive_bodies)}"
                        )
                    archive_bounding_box = bounding_box_mm(archive_bodies)
                    archive_body_bounding_boxes = body_bounding_boxes_mm(archive_bodies)
                    archive_body_names = [body.name for body in archive_bodies]
                finally:
                    if archive_document:
                        archive_document.close(False)

                result["outputs"][side] = {
                    "source_step": str(step_path.relative_to(repo_root)),
                    "source_step_sha256": sha256(step_path),
                    "f3d": str(f3d_path.relative_to(repo_root)),
                    "f3d_sha256": sha256(f3d_path),
                    "body_count": len(bodies),
                    "bounding_box_mm": bounding_box_mm(bodies),
                    "body_bounding_boxes_mm": body_bounding_boxes_mm(bodies),
                    "export_ok": export_ok,
                    "archive_size_bytes": f3d_path.stat().st_size,
                    "archive_reimport_body_count": len(archive_bodies),
                    "archive_reimport_bounding_box_mm": archive_bounding_box,
                    "archive_reimport_body_bounding_boxes_mm": archive_body_bounding_boxes,
                    "archive_reimport_body_names": archive_body_names,
                }
            finally:
                document.close(False)

        result["status"] = "pass"
        write_result(result_path, result)
        ui.messageBox("KC2 left/right Fusion F3D export completed.", "KC2 STEP to F3D")
    except Exception:
        result["error"] = traceback.format_exc()
        write_result(result_path, result)
        ui.messageBox(result["error"], "KC2 STEP to F3D failed")
