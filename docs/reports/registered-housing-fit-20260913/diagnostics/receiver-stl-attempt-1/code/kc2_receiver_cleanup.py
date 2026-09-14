"""CON-ARCH-006 strictly bounded internal receiver-tip subtraction."""
from shapely.ops import unary_union

OUTWARD_TOLERANCE_MM = .002
CUT_Z_MM = (-1., 2.5)
REQUIRED_ROLES = frozenset(('support_posts', 'rail', 'mounting_lands', 'reset_local_support',
                          'existing_reinforced_socket_covers', 'new_perimeter_wall',
                          'registrar_top_a', 'registrar_top_b', 'registrar_outer'))


def validate_evidence(diagnosis, roles):
    if set(roles) != REQUIRED_ROLES or any(g.is_empty for g in roles.values()):
        raise ValueError('Incomplete preserved role inventory')
    rows = diagnosis['rows']
    if len(rows) != 2 or {r['y_mm'] for r in rows} != {73.25, 86.25}:
        raise ValueError('Wrong actual receiver identities')
    for row in rows:
        floor, upper = row['floor'], row['above_floor']
        if (not floor['eligible'] or floor['errors'] or floor['required_ring_missing_mm3'] != 0
                or not upper['constant_prism_eligible'] or upper['errors']):
            raise ValueError('Actual floor/prism proof failed')
        if (floor['levels_mm'] != [-2.2, -1.] or upper['levels_mm'] != [-1., 2.5]
                or floor['stratified_section_volume_error_mm3'] > .002
                or upper['volume_vs_z0_extrusion_error_mm3'] > .002
                or upper['z0_candidate_source_difference_mm2'] > .001
                or upper['cut_outside_roi_mm2'] != 0):
            raise ValueError('Actual floor/prism numeric proof failed')


def plan_cutters(candidates, protected_roles):
    if not candidates or any(g.is_empty or not g.is_valid or g.area <= 0 for g in candidates):
        raise ValueError('Missing/invalid cleanup candidate')
    cutter = unary_union(candidates).buffer(OUTWARD_TOLERANCE_MM, quad_segs=8)
    for name, protected in protected_roles.items():
        if cutter.intersects(protected):
            raise ValueError('Cleanup intersects protected role ' + name)
    return cutter


def clean_receiver(shape, footprint):
    from tools.kc2_central_flexure import prism
    result = shape.cut(*prism(footprint, *CUT_Z_MM).Solids()).clean()
    if not result.isValid() or len(result.Solids()) != len(shape.Solids()):
        raise ValueError('Cleanup invalid/disconnected result')
    return result
