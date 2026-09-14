"""CON-ARCH-006 filled upper plus outward-open rebates, exact height strata."""
from shapely.ops import unary_union
from tools.kc2_solid_plate import Layer
from tools.kc2_filled_plate_profiles import PROFILES,plate_layers

def compose_upper(kind,geometry,registrars,masks=None):
    profile=PROFILES[kind]
    domain=geometry['domain'].union(unary_union([r.addition for r in registrars]))
    masks=[domain] if masks is None else masks
    parts=[]
    for mask in masks:
        original=plate_layers(profile,domain,*[geometry[k] for k in
            ('body','openings','service','bores','pockets','bosses','lands')],part_mask=mask)
        output=[]
        for layer in original:
            heights=sorted({layer.z0,layer.z1,*[z for r in registrars for z in r.groove_z if layer.z0<z<layer.z1]})
            for a,b in zip(heights,heights[1:]):
                cuts=unary_union([r.groove for r in registrars if r.groove_z[0]<b and r.groove_z[1]>a])
                section=layer.geometry.difference(cuts)
                if not section.is_empty:output.append(Layer(a,b,section))
        parts.append(output)
    return parts
