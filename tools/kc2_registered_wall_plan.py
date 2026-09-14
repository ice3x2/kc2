"""CON-ARCH-006 fixed, outward-open registrar rebates; not the full skirt.

All polygons use local housing XY millimetres. Inputs must be independently
established actual geometry: lower_floor at its continuous floor layer and
upper_solid across the attachment height. This pure planner does not establish
CAD truth, received-component compatibility or printed friction/strength.
"""
from dataclasses import dataclass
from shapely.geometry import box


@dataclass(frozen=True)
class Registrar:
    wall: object
    addition: object
    groove: object
    floor_addition: object
    wall_z: tuple = (-1.,5.)
    upper_z: tuple = (4.4,6.25)
    groove_z: tuple = (4.4,5.2)
    floor_z: tuple = (-2.2,-1.)
    outward: str = '-y'

    @property
    def roof_thickness(self):return self.upper_z[1]-self.groove_z[1]


def plan_registrars(*,side,kind,board,lower_floor,upper_solid,
                    lower_protected,upper_protected,central_exclusion,
                    split_exclusion):
    """Return three additions/cutters, rejecting rather than clipping conflicts.

    The rebate intentionally opens outwards. Its inside and both ends retain
    1.20 mm material; its roof never becomes a Z stop (0.20 mm tip gap).
    The solid floor patch reaches existing floor by >=0.80 mm, while the
    upright wall remains outside PCB+0.30. Floor patches belong ONLY below Z-1.
    The caller must union additions before cutting rebates from the whole upper.
    """
    if side not in ('left','right') or kind not in ('mx','choc_v1','deep_sea'):
        raise ValueError('unknown side or profile')
    inputs=locals().copy()
    for name in ('board','lower_floor','upper_solid','lower_protected',
                 'upper_protected','central_exclusion','split_exclusion'):
        g=inputs[name]
        if not g.is_valid or (name in ('board','lower_floor','upper_solid') and g.is_empty):
            raise ValueError('invalid '+name)
    if side=='left':
        candidates=[('top_a',(30,-1.5,36,-.3),'-y'),('top_b',(48,-1.5,54,-.3),'-y'),
                    ('outer',(16.9,10,18.1,16),'-x')]
    else:
        candidates=[('top_a',(110,-1.5,116,-.3),'-y'),('top_b',(128,-1.5,134,-.3),'-y'),
                    ('outer',(140.5875,10,141.7875,16),'+x')]
    top={'mx':9.3,'choc_v1':6.5,'deep_sea':6.25}[kind]
    result={}
    for name,bounds,direction in candidates:
        x0,y0,x1,y1=bounds;wall=box(*bounds);groove=wall.buffer(.25,join_style=2)
        if direction=='-y':
            addition=box(x0-1.45,y0,x1+1.45,y1+1.45)
            root=box(x0,y1+.4,x1,y1+1.2)
        elif direction=='-x':
            addition=box(x0,y0-1.45,x1+1.45,y1+1.45)
            root=box(x1+.4,y0,x1+1.2,y1)
        else:
            addition=box(x0-1.45,y0-1.45,x1,y1+1.45)
            root=box(x0-1.2,y0,x0-.4,y1)
        if wall.distance(board)<.3-1e-8:raise ValueError(name+': PCB clearance')
        if wall.intersection(lower_protected).area>1e-8:
            raise ValueError(name+': lower protected collision')
        if addition.intersection(upper_protected).area>1e-8:
            raise ValueError(name+': upper protected collision')
        for label,region in [('central',central_exclusion),('split',split_exclusion)]:
            if addition.intersects(region):raise ValueError(name+': '+label+' exclusion')
        for label,existing in [('floor',lower_floor),('upper',upper_solid)]:
            if root.difference(existing.buffer(1e-8)).area>1e-8:
                raise ValueError(name+': '+label+' attachment below0.8mm')
        result[name]=Registrar(wall,addition,groove,addition,upper_z=(4.4,top),outward=direction)
    return result
