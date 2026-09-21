"""CON-ARCH-006: source-CAD-backed binary STL coordinate rounding check."""
import math
import numpy as np

def assess(mesh_gap,cad_gap,max_coordinate,required=.3999):
    valid=all(math.isfinite(x) for x in (mesh_gap,cad_gap,max_coordinate,required))
    quantum=float(np.spacing(np.float32(abs(max_coordinate)))) if valid else 0.
    # Two independently rounded XY points, each coordinate within half an ULP.
    bound=math.sqrt(2)*quantum
    return dict(mesh_gap_mm=mesh_gap,cad_gap_mm=cad_gap,required_mm=required,
        float32_distance_bound_mm=bound,cad_kernel_tolerance_mm=1e-7,
        **{'pass':bool(valid and 0<bound<=.000025 and cad_gap+1e-7>=required
                       and mesh_gap>0 and abs(mesh_gap-cad_gap)<=bound+1e-7)})
