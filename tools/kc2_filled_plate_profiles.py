"""CON-ARCH-006 engineering plate datums; no exact received-part qualification.

V1: official CPG135001D01 family drawing + existing 0.20 mm adapter flange.
Deep Sea: CPG1353S01D01-01 temporary silent-family drawing; brown-lot linkage
unconfirmed. Its 2.15 mm seat is inferred from 1.35 mm clip + 0.80 mm base.
MX: retained published KC2 geometry, not an exact TTC supplier qualification.
"""
from dataclasses import dataclass
from tools.kc2_solid_plate import Void,fill_layers


@dataclass(frozen=True)
class Profile:
    plate_bottom: float
    plate_top: float
    aperture: float
    body_clear_width: float
    bearing: float
    boss_top: float
    screw_length: float
    exact_received_part_verified: bool=False


PROFILES={
    'mx':Profile(7.8,9.3,14.0,16.202,7.8,9.3,7.5),
    'choc_v1':Profile(5.3,6.5,14.2,15.3,5.1,6.6,5.0),
    'deep_sea':Profile(5.05,6.25,14.2,15.3,5.1,6.6,5.0),
}


def plate_layers(profile,domain,body,openings,service,bores,pockets,bosses,lands,part_mask=None):
    """Full solid field in every stratum; only explicit functional voids remain."""
    high=max(profile.plate_top,profile.boss_top)
    common=[Void('screw_through',bores,4.1,high+.1),
            Void('screw_head',pockets,profile.bearing,high+.1),
            Void('controller_and_service',service,4.1,high+.1)]
    result=fill_layers(lands,4.1,4.4,common+[Void('switch_body',body,4.1,profile.plate_bottom)],part_mask)
    result+=fill_layers(domain,4.4,profile.plate_bottom,common+[Void('switch_body_and_clip',body,4.1,profile.plate_bottom)],part_mask)
    result+=fill_layers(domain,profile.plate_bottom,profile.plate_top,common+[Void('switch_apertures',openings,profile.plate_bottom,high+.1)],part_mask)
    if profile.boss_top>profile.plate_top:
        result+=fill_layers(bosses,profile.plate_top,profile.boss_top,common+[Void('switch_envelope',body,profile.plate_top,high+.1)],part_mask)
    return result
