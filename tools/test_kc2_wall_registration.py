"""CON-ARCH-006: candidate walls must be printable, anchored and non-clamping."""
import unittest
from dataclasses import replace

from shapely.geometry import GeometryCollection, box
from shapely.affinity import rotate

from tools.kc2_wall_registration import RegistrationLimits, plan_registration


class WallRegistrationTests(unittest.TestCase):
    def args(self):
        return dict(
            board=box(0, 0, 20, 20),
            floor_anchor=box(-5, -5, 25, 25),
            allowed_outline=box(-5, -5, 25, 25),
            upper_solid=box(-5, -5, 25, 25),
            protected=GeometryCollection(),
            central_exclusion=GeometryCollection(),
            split_exclusion=GeometryCollection(),
            candidates={"north": box(3, -2, 9, -.8), "west": box(-2, 3, -.8, 9)},
        )

    def test_CON_ARCH_006_two_distributed_registrars_and_exact_clearances(self):
        result = plan_registration(**self.args())
        self.assertEqual(set(result), {"north", "west"})
        p = result["north"]
        self.assertAlmostEqual(p.groove.distance(p.wall), 0)
        self.assertAlmostEqual(p.wall.boundary.distance(p.groove.boundary), .25)
        self.assertEqual((p.wall_bottom, p.wall_top, p.groove_bottom, p.groove_top), (-1, 5, 4.4, 5.2))

    def test_CON_ARCH_006_thin_wall_rejected(self):
        args = self.args(); args["candidates"]["north"] = box(3, -2, 9, -1)
        with self.assertRaisesRegex(ValueError, "width"):
            plan_registration(**args)

    def test_CON_ARCH_006_disconnected_candidate_rejected(self):
        args = self.args(); args["candidates"]["north"] = box(3,-2,5,-.8).union(box(7,-2,9,-.8))
        with self.assertRaisesRegex(ValueError, "rectangle"):
            plan_registration(**args)

    def test_CON_ARCH_006_orphan_or_partial_root_rejected(self):
        args = self.args(); args["floor_anchor"] = box(0, 0, 20, 20)
        with self.assertRaisesRegex(ValueError, "floor"):
            plan_registration(**args)

    def test_CON_ARCH_006_pcb_and_protected_collisions_rejected(self):
        for field in ("board", "protected"):
            args = self.args(); args[field] = box(4, -1.9, 5, -1)
            with self.subTest(field=field), self.assertRaises(ValueError):
                plan_registration(**args)

    def test_CON_ARCH_006_central_and_split_exclusions_include_groove_cheeks(self):
        for field in ("central_exclusion", "split_exclusion"):
            args = self.args(); args[field] = box(9.3, -2, 10, 0)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "exclusion"):
                plan_registration(**args)

    def test_CON_ARCH_006_no_silent_outline_expansion(self):
        args = self.args(); args["allowed_outline"] = box(0, 0, 20, 20)
        with self.assertRaisesRegex(ValueError, "outline"):
            plan_registration(**args)

    def test_CON_ARCH_006_existing_thin_skirt_cannot_receive_groove(self):
        args = self.args(); args["upper_solid"] = box(3, -2, 9, -.8)
        with self.assertRaisesRegex(ValueError, "cheek"):
            plan_registration(**args)

    def test_CON_ARCH_006_roof_and_vertical_non_support_clearance(self):
        for limits in (replace(RegistrationLimits(), upper_top=6.1),
                       replace(RegistrationLimits(), groove_top=5.0),
                       replace(RegistrationLimits(), side_clearance=.1)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                plan_registration(**self.args(), limits=limits)

    def test_CON_ARCH_006_no_empty_or_single_locator_claim(self):
        args = self.args(); args["candidates"] = {}
        with self.assertRaises(ValueError): plan_registration(**args)
        args["candidates"] = {"north": box(3, -2, 9, -.8)}
        with self.assertRaises(ValueError): plan_registration(**args)

    def test_CON_ARCH_006_rotated_constant_width_wall_allowed(self):
        args = self.args()
        args["candidates"]["north"] = rotate(box(3,-2,9,-.8), 2)
        self.assertEqual(len(plan_registration(**args)), 2)

    def test_CON_ARCH_006_concave_thin_neck_and_overlapping_candidates_rejected(self):
        args = self.args()
        args["candidates"]["north"] = box(3,-2,9,-.8).difference(box(5,-2,6,-1.5))
        with self.assertRaisesRegex(ValueError, "rectangle"):
            plan_registration(**args)
        args = self.args()
        args["candidates"]["west"] = args["candidates"]["north"]
        with self.assertRaisesRegex(ValueError, "separated"):
            plan_registration(**args)

    def test_CON_ARCH_006_nonfinite_limits_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            plan_registration(**self.args(), limits=replace(RegistrationLimits(), roof=float("nan")))

    def test_CON_ARCH_006_negligible_vertical_engagement_rejected(self):
        with self.assertRaisesRegex(ValueError, "engagement"):
            plan_registration(**self.args(), limits=replace(RegistrationLimits(), groove_bottom=4.999999))


if __name__ == "__main__":
    unittest.main()
