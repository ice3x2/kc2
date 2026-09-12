"""CON-ARCH-006 solid-filled plate sections with explicit 3D reserved spaces.

This kernel has no implicit sparse ribs, shell offset, switch-family dimensions,
or print-strength claim. Callers must supply source-backed physical envelopes.
"""
from dataclasses import dataclass
import math
from shapely.ops import unary_union


@dataclass(frozen=True)
class Void:
    name: str
    geometry: object
    z0: float
    z1: float


@dataclass(frozen=True)
class Layer:
    z0: float
    z1: float
    geometry: object


def valid_interval(z0,z1):
    if not all(isinstance(z,(int,float)) and math.isfinite(z) for z in (z0,z1)) or z1<=z0:
        raise ValueError('Finite increasing height interval required')


def fill_layers(outline,z0,z1,voids,part_mask=None):
    """Fill EVERY available point, separating strata at exact void boundaries."""
    valid_interval(z0,z1)
    if outline.is_empty or not outline.is_valid or outline.area<=0:
        raise ValueError('Valid nonempty area outline required')
    for cut in voids:
        valid_interval(cut.z0,cut.z1)
        if not cut.name or not cut.geometry.is_valid:
            raise ValueError('Reserved space must be named and valid')
    domain=outline if part_mask is None else outline.intersection(part_mask)
    heights=sorted({z0,z1,*[z for cut in voids for z in (cut.z0,cut.z1) if z0<z<z1]})
    result=[]
    for bottom,top in zip(heights,heights[1:]):
        active=[cut.geometry for cut in voids if cut.z0<top and cut.z1>bottom]
        section=domain.difference(unary_union(active))
        if not section.is_empty:
            result.append(Layer(bottom,top,section))
    return result


def coverage_errors(required,actual,tolerance_mm2=1e-7):
    """Independent section comparison rejects both hollowing and filled holes."""
    errors=[]
    if required.difference(actual).area>tolerance_mm2:
        errors.append('unfilled structural interior')
    if actual.difference(required).area>tolerance_mm2:
        errors.append('material in reserved or exterior space')
    return errors


def build_solid(layers):
    """Extrude the full sections, fuse touching strata, reject loose islands."""
    import cadquery as cq
    from tools import generate_kc2_x3_v2_housings as base
    solids=[]
    for layer in layers:
        solids.extend(base._extrude_geometry(cq,layer.geometry,layer.z1-layer.z0,layer.z0).val().Solids())
    if not solids:raise ValueError('No structural material')
    result=solids[0].fuse(*solids[1:]).clean() if len(solids)>1 else solids[0]
    if not result.isValid() or len(result.Solids())!=1:
        raise ValueError('Invalid or disconnected filled plate')
    expected=sum(r.geometry.area*(r.z1-r.z0) for r in layers)
    if abs(result.Volume()-expected)>max(.002,expected*1e-7):
        raise ValueError('Filled section volume lost or duplicated during fusion')
    return result
