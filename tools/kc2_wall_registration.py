"""CON-ARCH-006 pure XY planner for selected floor-rooted registration walls.

Inputs are assembled-coordinate Shapely polygons in mm, not board filenames.
``floor_anchor`` must be independently proven solid continuously from inner
floor Z=-1 to the wall start; a floor silhouette alone is NOT that evidence.
``upper_solid`` is the intersection of material sections over the full groove
and roof height, with switch/service/fastener voids already removed. This module
does not establish either input's physical/CAD truth or design a perimeter skirt.
Rejected candidates raise instead of clipping away safety material. Callers may
enumerate alternative rectangular locations and record rejection diagnostics.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class RegistrationLimits:
    pcb_clearance: float = .30
    min_width: float = 1.20
    side_clearance: float = .25
    cheek: float = 1.20
    roof: float = 1.00
    wall_bottom: float = -1.00
    wall_top: float = 5.00
    groove_bottom: float = 4.40
    groove_top: float = 5.20
    upper_top: float = 6.25


@dataclass(frozen=True)
class RegistrationFeature:
    wall: Polygon
    groove: Polygon
    required_upper: Polygon
    wall_bottom: float
    wall_top: float
    groove_bottom: float
    groove_top: float


def _covers(container, feature):
    return feature.difference(container).area <= 1e-8


def plan_registration(*, board: BaseGeometry, floor_anchor: BaseGeometry,
                      allowed_outline: BaseGeometry, upper_solid: BaseGeometry,
                      protected: BaseGeometry, central_exclusion: BaseGeometry,
                      split_exclusion: BaseGeometry,
                      candidates: Mapping[str, Polygon],
                      limits: RegistrationLimits = RegistrationLimits()
                      ) -> dict[str, RegistrationFeature]:
    """Return extrusion and subtractive-groove footprints or fail closed.

    At least two separated locator footprints are required. Rectangular shape
    validation makes the minimum width auditable (no hidden thin necks). No
    snap/retaining hook is generated, and groove ceiling is above the wall tip
    so existing screw stops retain the vertical load. Z spans use absolute mm.
    The entire groove plus cheek is excluded from center and A/B seam regions.
    """
    if not all(isfinite(v) for v in vars(limits).values()):
        raise ValueError("nonfinite limits")
    if (limits.pcb_clearance < .30 or limits.min_width < 1.20 or
            not .20 <= limits.side_clearance <= .30 or limits.cheek < 1.20 or
            limits.roof < 1 or limits.wall_bottom != -1 or
            not limits.wall_bottom < limits.groove_bottom < limits.wall_top or
            limits.wall_top - limits.groove_bottom < .60 - 1e-8 or
            limits.groove_top - limits.wall_top < .199999 or
            limits.upper_top - limits.groove_top < limits.roof - 1e-8):
        raise ValueError("unsafe clearance, root, engagement or roof dimensions")
    for name, geometry in (("board", board), ("floor", floor_anchor),
                           ("outline", allowed_outline), ("upper", upper_solid),
                           ("protected", protected), ("central", central_exclusion),
                           ("split", split_exclusion)):
        if not geometry.is_valid or (name in {"board", "floor", "outline", "upper"}
                                     and geometry.is_empty):
            raise ValueError(f"invalid {name} geometry")
    if len(candidates) < 2:
        raise ValueError("two separated registrars required")
    features = {}
    pcb_keepout = board.buffer(limits.pcb_clearance, join_style=2)
    for name, wall in candidates.items():
        if (not isinstance(wall, Polygon) or not wall.is_valid or wall.is_empty or
                wall.interiors or wall.symmetric_difference(wall.minimum_rotated_rectangle).area > 1e-8):
            raise ValueError(f"{name}: wall must be one solid rectangle")
        corners = list(wall.minimum_rotated_rectangle.exterior.coords)
        widths = [((a[0]-b[0])**2 + (a[1]-b[1])**2)**.5
                  for a, b in zip(corners, corners[1:])]
        if min(widths) < limits.min_width - 1e-8:
            raise ValueError(f"{name}: insufficient wall width")
        groove = wall.buffer(limits.side_clearance, join_style=2)
        required = groove.buffer(limits.cheek, join_style=2)
        if wall.intersection(pcb_keepout).area > 1e-8:
            raise ValueError(f"{name}: PCB clearance collision")
        if wall.intersection(protected).area > 1e-8:
            raise ValueError(f"{name}: protected component collision")
        if not _covers(floor_anchor, wall):
            raise ValueError(f"{name}: incomplete floor-continuous root")
        if not _covers(allowed_outline, wall):
            raise ValueError(f"{name}: unauthorized outline expansion")
        if not _covers(upper_solid, required):
            raise ValueError(f"{name}: missing upper groove cheek or roof")
        if required.intersects(central_exclusion) or required.intersects(split_exclusion):
            raise ValueError(f"{name}: central/split exclusion collision")
        if any(required.intersects(previous.required_upper) for previous in features.values()):
            raise ValueError(f"{name}: registrars must be separated")
        features[name] = RegistrationFeature(wall, groove, required,
            limits.wall_bottom, limits.wall_top, limits.groove_bottom, limits.groove_top)
    return features
