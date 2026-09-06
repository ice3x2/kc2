"""CON-ARCH-004 AC-3/AC-9 fail-closed MX receptacle qualification.

This supplementary gate does not replace repository artifact/hash binding or the
scan/housing gates. Nominal seller dimensions cannot establish contact limits.
"""
import math


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def verify_mx_receptacle_evidence(data, *, assembly="mx_receptacle_with_plate", verified_artifact_paths=None):
    """Return errors; callers must also bind raw evidence artifacts and identities."""
    if assembly != "mx_receptacle_with_plate":
        return []
    prefix = "CON-ARCH-004 AC-3/AC-9 MX receptacle: "
    if not isinstance(data, dict):
        return [prefix + "contact qualification evidence missing"]
    errors = []
    nominal = data.get("nominal_socket")
    expected = {"length_mm": 3.0, "barrel_od_mm": 1.45, "flange_od_mm": 2.0, "flange_thickness_mm": .2}
    if not isinstance(nominal, dict) or nominal.get("open_bottom") is not True or any(
        not _number(nominal.get(name)) or abs(nominal[name] - value) > 1e-9
        for name, value in expected.items()
    ):
        errors.append(prefix + "selected open-bottom 3.00/1.45/2.00/0.20 mm nominal geometry missing or changed")
    for field in ("socket_specification", "switch_specification", "plate_material", "coupon_id", "limits_source_artifact"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or any(word in value.lower() for word in ("pending", "unknown", "tbd")):
            errors.append(prefix + field + " missing or unqualified")
    # Paths must be supplied by the caller's successful canonical-path/SHA-256
    # artifact verifier, never copied from this untrusted raw JSON itself.
    bound = verified_artifact_paths if isinstance(verified_artifact_paths, (set, frozenset)) else set()
    for field in ("socket_specification", "switch_specification", "limits_source_artifact"):
        value = data.get(field)
        if not isinstance(value, str) or value not in bound:
            errors.append(prefix + field + " lacks independently verified artifact provenance")
    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        limits = {}
    names = ("finished_hole_min_mm", "finished_hole_max_mm", "barrel_min_mm", "barrel_max_mm", "insertion_force_min_n", "insertion_force_max_n", "extraction_force_min_n", "extraction_force_max_n", "contact_resistance_max_ohm", "flange_lift_max_mm", "housing_clearance_min_mm")
    for name in names:
        if not _number(limits.get(name)) or limits[name] < 0:
            errors.append(prefix + "missing finite nonnegative specification limit " + name)
    if any(not _number(limits.get(name)) or limits[name] < 0 for name in names):
        return errors
    for family in ("finished_hole", "barrel"):
        if limits[family + "_min_mm"] <= 0 or limits[family + "_max_mm"] < limits[family + "_min_mm"]:
            errors.append(prefix + family + " limits inconsistent")
    if limits["finished_hole_min_mm"] <= limits["barrel_max_mm"]:
        errors.append(prefix + "worst-case barrel does not clear finished plated hole")
    for family in ("insertion", "extraction"):
        if limits[family + "_force_min_n"] <= 0 or limits[family + "_force_max_n"] < limits[family + "_force_min_n"]:
            errors.append(prefix + family + " force limits inconsistent")
    if limits["contact_resistance_max_ohm"] <= 0 or limits["housing_clearance_min_mm"] <= 0:
        errors.append(prefix + "resistance/clearance limits must be positive")
    records = data.get("records")
    if not isinstance(records, list) or len(records) < 3:
        return errors + [prefix + "minimum three-key coupon records missing"]
    halves, keys = set(), set()
    for record in records:
        if not isinstance(record, dict):
            errors.append(prefix + "invalid key record")
            continue
        half, key = record.get("half"), record.get("key_id")
        if half not in ("left", "right") or not isinstance(key, str) or not key or (half, key) in keys:
            errors.append(prefix + "key identity missing/duplicated")
        else:
            keys.add((half, key))
            halves.add(half)
        for field in ("center_locator_fully_seated", "plate_retention_pass", "no_socket_rotation_or_pullout", "no_pad_damage", "no_intermittent_or_open_contact"):
            if record.get(field) is not True:
                errors.append(prefix + field + " not proven")
        for field, threshold, minimum in (("flange_lift_mm", "flange_lift_max_mm", False), ("housing_clearance_mm", "housing_clearance_min_mm", True)):
            value = record.get(field)
            if not _number(value) or value < 0 or (value < limits[threshold] if minimum else value > limits[threshold]):
                errors.append(prefix + field + " out of specification")
        cycles = record.get("replacement_cycles")
        if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 10:
            errors.append(prefix + "ten replacement cycles not proven")
        contacts = record.get("contacts")
        if not isinstance(contacts, list) or len(contacts) != 2:
            errors.append(prefix + "both flat-blade contact records required")
            continue
        contact_ids = set()
        for contact in contacts:
            if not isinstance(contact, dict):
                errors.append(prefix + "invalid contact record")
                continue
            contact_id = contact.get("contact_id")
            if contact_id not in ("1", "2") or contact_id in contact_ids:
                errors.append(prefix + "distinct contact 1 and 2 records required")
            else:
                contact_ids.add(contact_id)
            observed_cycles = contact.get("tested_replacement_cycles")
            if (
                not isinstance(cycles, int) or isinstance(cycles, bool) or cycles < 10
                or not isinstance(observed_cycles, list)
                or any(not isinstance(cycle, int) or isinstance(cycle, bool) for cycle in observed_cycles)
                or len(observed_cycles) != cycles + 1
                or set(observed_cycles) != set(range(cycles + 1))
            ):
                errors.append(prefix + "contact replacement-cycle coverage incomplete or duplicated")
            for field, lo, hi in (("finished_hole_mm", "finished_hole_min_mm", "finished_hole_max_mm"), ("barrel_mm", "barrel_min_mm", "barrel_max_mm")):
                value = contact.get(field)
                if not _number(value) or not limits[lo] <= value <= limits[hi]:
                    errors.append(prefix + field + " out of specification")
            for stage in ("before", "after"):
                for family in ("insertion", "extraction"):
                    value = contact.get(stage + "_" + family + "_force_n")
                    if not _number(value) or not limits[family + "_force_min_n"] <= value <= limits[family + "_force_max_n"]:
                        errors.append(prefix + stage + " " + family + " force out of specification")
                resistance = contact.get(stage + "_contact_resistance_ohm")
                if not _number(resistance) or not 0 <= resistance <= limits["contact_resistance_max_ohm"]:
                    errors.append(prefix + stage + " contact resistance out of specification")
    if halves != {"left", "right"}:
        errors.append(prefix + "representative left/right geometry missing")
    return errors
