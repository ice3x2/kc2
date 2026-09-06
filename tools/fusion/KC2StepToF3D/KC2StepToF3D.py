"""Import KC2 STEP housings into Fusion and export native F3D archives."""

from __future__ import annotations

import json
import hashlib
import math
import os
import traceback
from pathlib import Path

import adsk.core
import adsk.fusion

DEFAULT_REPO_ROOT = Path(r"C:\Work\git\kc2")
EXPECTED_BODY_COUNTS = {
    "left_lower": 1, "right_lower": 2,
    "left_mx_upper": 1, "right_mx_upper": 2,
}


def export_jobs(case_dir: Path) -> dict[str, Path]:
    """CON-ARCH-006: preflight all four source files before any export."""
    jobs = {
        f"{side}_{kind}": case_dir / f"kc2_{side}_{kind}_housing.step"
        for kind in ("lower", "mx_upper")
        for side in ("left", "right")
    }
    missing = [str(path) for path in jobs.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required housing STEP sources: " + ", ".join(missing))
    return jobs


def solid_records(bodies: list) -> list[dict]:
    if not bodies or any(not body.isSolid for body in bodies):
        raise RuntimeError("Housing must contain nonempty solid BRep bodies")
    return [
        {"bounds_mm": box, "volume_mm3": body.volume * 1000.0}
        for body, box in zip(bodies, body_bounding_boxes_mm(bodies))
    ]


def validate_round_trip(source: list[dict], reopened: list[dict]) -> None:
    """Check solids, print bounds and material volume, independently of body order."""
    if not source or len(source) != len(reopened):
        raise RuntimeError("Fusion round-trip solid body count changed or is empty")
    for record in source + reopened:
        box = record['bounds_mm']
        volume = record['volume_mm3']
        if len(box) != 6 or not all(math.isfinite(v) for v in box):
            raise RuntimeError("Fusion round-trip bounds are invalid")
        if not math.isfinite(volume) or volume <= 0:
            raise RuntimeError("Fusion round-trip solid volume is invalid")
        for axis in range(3):
            size = box[axis + 3] - box[axis]
            if size <= 0 or size > 150.001:
                raise RuntimeError("Fusion body violates the 150 mm print envelope")
    unmatched = list(reopened)
    for before in source:
        index = next((i for i, after in enumerate(unmatched)
                      if all(abs(a-b) <= 0.001 for a, b in zip(before['bounds_mm'], after['bounds_mm']))
                      and abs(before['volume_mm3']-after['volume_mm3']) <= max(0.001, before['volume_mm3'] * 1e-6)), None)
        if index is None:
            raise RuntimeError("Fusion round-trip bounds or volume changed")
        unmatched.pop(index)


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
        # Autodesk Occurrence.bRepBodies returns root-context body proxies;
        # component.bRepBodies would discard occurrence placement transforms.
        # https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Occurrence_bRepBodies.htm
        bodies.extend(occurrence.bRepBodies.item(body_index) for body_index in range(occurrence.bRepBodies.count))
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
        "requirement": "CON-ARCH-006",
        "assembly_mode": "mx_receptacle_with_plate",
        "order_ready": False,
        "outputs": {},
    }

    try:
        import_manager = app.importManager
        jobs = export_jobs(case_dir)
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
                source_solids = solid_records(bodies)
                validate_round_trip(source_solids, source_solids)
                expected_body_count = EXPECTED_BODY_COUNTS[side]
                if len(bodies) != expected_body_count:
                    raise RuntimeError(
                        f"Expected {expected_body_count} imported bodies for {side}, "
                        f"found {len(bodies)}"
                    )
                for index, body in enumerate(bodies, start=1):
                    suffix = f" Part {index}" if expected_body_count > 1 else ""
                    body.name = f"KC2 {side.replace('_', ' ').title()} Housing{suffix}"

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
                    archive_solids = solid_records(archive_bodies)
                    validate_round_trip(source_solids, archive_solids)
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
                    "source_solids": source_solids,
                    "archive_reimport_solids": archive_solids,
                    "solid_round_trip_verified": True,
                }
            finally:
                document.close(False)

        result["status"] = "pass"
        write_result(result_path, result)
        ui.messageBox("KC2 left/right lower and MX upper Fusion F3D exports completed.", "KC2 STEP to F3D")
    except Exception:
        result["error"] = traceback.format_exc()
        write_result(result_path, result)
        ui.messageBox(result["error"], "KC2 STEP to F3D failed")
