"""CON-ARCH-004 AC-3/AC-9: selected MX contacts cannot inherit bare-pin PASS."""
import unittest
import copy

from tools.verify_kc2_mx_receptacle_evidence import verify_mx_receptacle_evidence as raw_verify


def verify_mx_receptacle_evidence(data, **kwargs):
    # Only this unit fixture emulates the upstream artifact/hash verifier.
    return raw_verify(data, verified_artifact_paths={"synthetic-test-only"}, **kwargs)


class MXReceptacleEvidenceTests(unittest.TestCase):
    def fixture(self):
        # Synthetic unit-test numbers, NOT a production specification.
        contact = {"finished_hole_mm": 1.6, "barrel_mm": 1.45}
        for stage in ("before", "after"):
            contact.update({stage + "_insertion_force_n": 2, stage + "_extraction_force_n": 2, stage + "_contact_resistance_ohm": .01})
        key = {"half": "left", "key_id": "a", "replacement_cycles": 10, "flange_lift_mm": 0, "housing_clearance_mm": .5, "contacts": [dict(contact, contact_id="1", tested_replacement_cycles=list(range(11))), dict(contact, contact_id="2", tested_replacement_cycles=list(range(11)))]}
        for field in ("center_locator_fully_seated", "plate_retention_pass", "no_socket_rotation_or_pullout", "no_pad_damage", "no_intermittent_or_open_contact"):
            key[field] = True
        data = {name: "synthetic-test-only" for name in ("socket_specification", "switch_specification", "plate_material", "coupon_id", "limits_source_artifact")}
        data["limits"] = {"finished_hole_min_mm": 1.55, "finished_hole_max_mm": 1.65, "barrel_min_mm": 1.4, "barrel_max_mm": 1.5, "insertion_force_min_n": 1, "insertion_force_max_n": 3, "extraction_force_min_n": 1, "extraction_force_max_n": 3, "contact_resistance_max_ohm": .1, "flange_lift_max_mm": .1, "housing_clearance_min_mm": .2}
        data["nominal_socket"] = {"open_bottom": True, "length_mm": 3.0, "barrel_od_mm": 1.45, "flange_od_mm": 2.0, "flange_thickness_mm": .2}
        data["records"] = [copy.deepcopy(key) for _ in range(3)]
        data["records"][1]["key_id"] = "b"
        data["records"][2]["half"] = "right"
        return data

    def test_complete_synthetic_coupon(self):
        self.assertEqual([], verify_mx_receptacle_evidence(self.fixture()))

    def test_out_of_limits_and_missing_cycles_rejected(self):
        for mutate in (
            lambda d: d["records"][0].update(replacement_cycles=9),
            lambda d: d["records"][0]["contacts"][1].update(after_contact_resistance_ohm=.2),
            lambda d: d["records"][0]["contacts"][0].update(before_insertion_force_n=0),
            lambda d: d["limits"].update(barrel_max_mm=1.6),
            lambda d: d["records"][2].update(half="left"),
            lambda d: d["records"][0].update(plate_retention_pass=False),
        ):
            data = self.fixture()
            mutate(data)
            self.assertTrue(verify_mx_receptacle_evidence(data))

    def test_legacy_pass_is_not_contact_evidence(self):
        self.assertTrue(verify_mx_receptacle_evidence({"status": "passed"}))

    def test_missing_limits_fail(self):
        self.assertTrue(verify_mx_receptacle_evidence({"limits": {}, "records": []}))

    def test_nonselected_mode_does_not_require_contacts(self):
        self.assertEqual([], verify_mx_receptacle_evidence(None, assembly="mx_direct_solder"))

    def test_nonfinite_limits_fail(self):
        self.assertTrue(verify_mx_receptacle_evidence({"limits": {"contact_resistance_max_ohm": float("nan")}, "records": []}))

    def test_wrong_socket_geometry_rejected(self):
        data = self.fixture()
        data["nominal_socket"]["length_mm"] = 4
        self.assertTrue(verify_mx_receptacle_evidence(data))

    def test_claimed_provenance_is_not_verified_provenance(self):
        data = self.fixture()
        self.assertTrue(raw_verify(data))
        self.assertTrue(raw_verify(data, verified_artifact_paths=set()))

    def test_duplicate_contact_and_partial_cycle_records_rejected(self):
        for mutation in (
            lambda c: c.update(contact_id="1"),
            lambda c: c.update(tested_replacement_cycles=[0, 10]),
            lambda c: c.update(after_contact_resistance_ohm=float("nan")),
        ):
            data = self.fixture()
            mutation(data["records"][0]["contacts"][1])
            self.assertTrue(verify_mx_receptacle_evidence(data))


if __name__ == "__main__":
    unittest.main()
