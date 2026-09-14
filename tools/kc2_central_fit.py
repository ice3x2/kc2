"""CON-ARCH-006 provisional non-latching central guide/contact sections.

These are candidate XY sections, not a published housing or strength approval.
Rigid guides have positive clearance. Contact strips require a separately
verified free-deflection/root design in Z before CAD integration may pass.
Local coordinates: left wall X0, right wall X4; insertion along +X.
"""
from dataclasses import dataclass,asdict
import math
from numbers import Real
from shapely.geometry import Polygon,box
from shapely import affinity
from shapely.ops import unary_union


@dataclass(frozen=True)
class CentralFit:
    gap:float=4.
    projection:float=2.8
    tongue_width:float=2.4
    running_clearance:float=.15
    contact_deflection:float=.02
    wall:float=1.2
    root:float=1.
    entry:float=.4


def central_sections(p):
    values=asdict(p)
    if any(isinstance(v,bool) or not isinstance(v,Real) or not math.isfinite(v) for v in values.values()):
        raise ValueError('Dimensions must be finite real measurements, not booleans')
    if (min(p.gap,p.projection,p.tongue_width,p.root,p.entry)<=0 or
        p.wall<1.2 or p.running_clearance<=0 or not 0<=p.contact_deflection<=.05 or
        p.projection>=p.gap or 2*p.projection<=p.gap or p.entry>=p.tongue_width/2 or
        p.entry>=2*p.projection-p.gap):raise ValueError('Unsafe initial guide dimensions')
    h=p.tongue_width/2;tip=p.projection;start=p.gap-p.projection
    male=Polygon([(-p.root,-h),(tip-p.entry,-h),(tip,-h+p.entry),
                  (tip,h-p.entry),(tip-p.entry,h),(-p.root,h)])
    inner=h+p.running_clearance
    cheeks=[box(start,inner,p.gap+p.root,inner+p.wall),
            box(start,-inner-p.wall,p.gap+p.root,-inner)]
    top=Polygon([(start,inner),(start+p.entry,h-p.contact_deflection),
                 (p.gap,h-p.contact_deflection),(p.gap,inner)])
    bottom=affinity.scale(top,xfact=1,yfact=-1,origin=(0,0))
    contact=top.union(bottom)
    rigid=unary_union(cheeks)
    return dict(male=male,female_rigid=rigid,contact=contact,female=rigid.union(contact),
                engagement_mm=2*p.projection-p.gap,parameters=values,
                physical_qualified=False,compliance_verified=False,
                pending=['actual root and free deflection in Z','populated housing integration',
                         'print tolerance coupon','measured insertion and release force'])


def insertion_audit(s):
    """Exact convex translation sweep for rigid obstruction; sampled contact area.

Contact-area sampling is not a force or maximum-strain proof. The rigid swept
polygon is exhaustive for straight X insertion because the male is convex.
"""
    p=s['parameters'];male=s['male'];errors=[]
    expected=central_sections(CentralFit(**p))
    if s['contact'].symmetric_difference(expected['contact']).area>1e-9:
        errors.append('requested contact geometry missing or changed')
    if male.symmetric_difference(male.convex_hull).area>1e-9:
        raise ValueError('Convex sweep assumption invalid')
    travel=p['gap']+p['projection']+p['root']
    sweep=male.union(affinity.translate(male,xoff=-travel)).convex_hull
    if sweep.intersection(s['female_rigid']).area>1e-9:errors.append('rigid insertion obstruction')
    areas=[affinity.translate(male,xoff=-travel*i/100).intersection(s['contact']).area for i in range(101)]
    return dict(errors=errors,rigid_swept_intersection_mm2=sweep.intersection(s['female_rigid']).area,
                maximum_intended_contact_mm2=max(areas),contact_scope='101-position area samples, not force',
                force_qualified=False)
