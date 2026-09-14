"""CON-ARCH-006 TDD for subtractive removal of every central protrusion."""
import unittest

import cadquery as cq

from tools.kc2_flat_central_revision import FLAT_FACE_X, GUIDE_YS
from tools.stage_kc2_flat_central_revision import (
    apply_flat_join, audit_flat_join, audit_magnetic_preservation,
)


def toy(side):
    face = FLAT_FACE_X[side]
    if side == "left":
        base = cq.Workplane("XY").box(3, 30, 4, centered=False).val().translate((face, 85, -2.2))
        teeth = [cq.Workplane("XY").box(1.2, 5.1, 4, centered=False).val().translate((face-1.2, y-2.55, -2.2)) for y in GUIDE_YS]
    else:
        base = cq.Workplane("XY").box(3, 30, 4, centered=False).val().translate((face-3, 85, -2.2))
        teeth = [cq.Workplane("XY").box(1.2, 5.1, 4, centered=False).val().translate((face, y-2.55, -2.2)) for y in GUIDE_YS]
    return base.fuse(*teeth).clean(), cq.Compound.makeCompound(teeth), base


class FlatCentralStageTests(unittest.TestCase):
    def test_both_teeth_are_removed_without_touching_inboard_body(self):
        for side in ("left", "right"):
            before, allowed, base = toy(side)
            after = apply_flat_join(before, side)
            audit = audit_flat_join(before, after, side, allowed, base)
            self.assertEqual(audit["errors"], [])
            self.assertGreater(audit["removed_mm3"], 0)
            self.assertEqual(audit["added_mm3"], 0)
            self.assertEqual(audit["off_guide_removed_mm3"], 0)
            self.assertEqual(audit["baseline_removed_mm3"], 0)
            self.assertEqual(audit["remaining_protrusion_mm3"], 0)
            self.assertAlmostEqual(after.Volume(), base.Volume(), places=6)

    def test_invalid_side_and_disconnected_result_fail_closed(self):
        shape, allowed, base = toy("left")
        with self.assertRaises(ValueError):
            apply_flat_join(shape, "upper")
        empty = shape.cut(shape)
        audit = audit_flat_join(shape, empty, "left", allowed, base)
        self.assertIn("Invalid/disconnected flat housing", audit["errors"])

    def test_existing_magnetic_subtraction_is_unchanged(self):
        normal, _, _ = toy("left")
        pocket = cq.Solid.makeCylinder(.25, 1, cq.Vector(-.5, 105, -.5), cq.Vector(1, 0, 0))
        magnetic = normal.cut(pocket)
        flat_normal = apply_flat_join(normal, "left")
        flat_magnetic = apply_flat_join(magnetic, "left")
        self.assertEqual(audit_magnetic_preservation(
            normal, magnetic, flat_normal, flat_magnetic)["errors"], [])
        extra = cq.Solid.makeCylinder(.2, 1, cq.Vector(-.5, 108, -.5), cq.Vector(1, 0, 0))
        changed = flat_magnetic.cut(extra)
        self.assertTrue(audit_magnetic_preservation(
            normal, magnetic, flat_normal, changed)["errors"])

    def test_prior_unrelated_baseline_relief_is_not_charged_to_this_cut(self):
        before, allowed, base = toy("right")
        # Historical stock can contain material already absent before this
        # revision (for example the separately approved right A/B relief).
        old_extra = cq.Workplane("XY").box(1, 1, 1, centered=False).val().translate((140, 100, 0))
        historical = base.fuse(old_extra)
        after = apply_flat_join(before, "right")
        audit = audit_flat_join(before, after, "right", allowed, historical)
        self.assertEqual(audit["errors"], [])
        self.assertEqual(audit["baseline_removed_mm3"], 0)


if __name__ == "__main__":
    unittest.main()
