"""CON-ARCH-006 pure plan for a flat, non-interlocking central lower seam.

The user removed both former guide/flexure pairs.  An optional third magnetic
pair is accepted only with exact-zero missing reserve/protected overlap; a
failed search is a valid outcome and must not trigger wall enlargement.
"""
from numbers import Real
import math

from shapely.geometry import box


GUIDE_YS = (95.0, 117.0)
EXISTING_MAGNET_YS = (103.0, 111.0)
MIN_MAGNET_SPACING = 6.0
CONTROLLER_MAX_Y = min(EXISTING_MAGNET_YS) - MIN_MAGNET_SPACING
MAX_MAGNET_FACE_GAP = 4.4
FLAT_FACE_X = {"left": -1.5, "right": 150.9}


def flat_join_cutters(side):
    """Return conservative boxes that remove only former seam protrusions."""
    if side not in FLAT_FACE_X:
        raise ValueError("Unknown side")
    face = FLAT_FACE_X[side]
    x0, x1 = (-4.0, face) if side == "left" else (face, 154.0)
    return [dict(side=side, y=y, x0=x0, x1=x1, z0=-2.2, z1=1.8,
                 plan=box(x0, y - 2.6, x1, y + 2.6)) for y in GUIDE_YS]


def _measurement(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(name + " must be a finite real measurement")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(name + " must be finite and non-negative")
    return value


def choose_controller_magnet(candidates):
    """Choose a fully safe pair or None; never relax material/spacing gates."""
    accepted = []
    fields = ("y", "face_gap_mm", "reserve_missing_left_mm3",
              "reserve_missing_right_mm3", "forbidden_left_mm2",
              "forbidden_right_mm2")
    for source in candidates:
        if not isinstance(source, dict) or set(fields) - set(source):
            raise TypeError("Complete candidate measurements required")
        row = dict(source)
        values = {name: _measurement(row[name], name) for name in fields}
        row.update(values)
        if (values["y"] <= CONTROLLER_MAX_Y and
                values["face_gap_mm"] <= MAX_MAGNET_FACE_GAP and
                all(values[name] == 0.0 for name in fields[2:])):
            accepted.append(row)
    if not accepted:
        return None
    return min(accepted, key=lambda row: (row["face_gap_mm"], row["y"]))
