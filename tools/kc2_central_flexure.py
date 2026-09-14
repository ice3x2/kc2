"""CON-ARCH-006 free-standing vertical cheeks, floor-rooted central fit.

Provisional geometry in local seam coordinates X0/4. The two cheeks themselves
are flexures, not rigid backers. Their outer sides AND rear ends are free above
Z-1.00; each is attached only to a continuous floor below that plane. No elastic
modulus, material allowables, force or printed fit is asserted by this module.
"""
from shapely.geometry import box
from shapely import affinity
from shapely.ops import unary_union
from tools.kc2_central_fit import CentralFit,central_sections


def flexure_plan():
    seed=central_sections(CentralFit())
    cutoff=box(-10,-10,3.2,10)
    body=seed['female_rigid'].intersection(cutoff)
    tip=seed['contact'].intersection(cutoff)
    floor=seed['female_rigid']
    case=box(4,-2.55,5,2.55)
    free=body.union(tip).buffer(.30,join_style=2).difference(body.union(tip))
    beams=[dict(plan=g,rear_clearance_mm=4-g.bounds[2],
                root_z=-1.,tip_z=1.5) for g in body.geoms]
    return dict(male=seed['male'],beams=beams,beam_body=body,contact=tip,
                root_floor=floor,case_rigid=case,free_space=free,
                free_volume_mm3=free.area*2.5,
                nominal_tip_deflection_mm=.02,physical_qualified=False,
                floor_z=(-2.2,-1.),beam_z=(-1.,1.5),contact_z=(.8,1.5),
                pending=['actual integrated component clearance','nonlinear elastic/print test',
                         'root fillet and repeated assembly life','actual force and tolerance coupon'])


def audit_flexure(p):
    errors=[]
    expected=flexure_plan()
    fields=['male','beam_body','contact','root_floor','free_space']
    if (any(p[k].symmetric_difference(expected[k]).area>1e-9 for k in fields) or
        p['nominal_tip_deflection_mm']!=.02 or p['floor_z']!=(-2.2,-1.) or
        p['beam_z']!=(-1.,1.5) or p['contact_z']!=(.8,1.5)):
        errors.append('declared geometry differs from dimensional contract')
    if p['free_space'].intersection(p['case_rigid']).area>1e-9:
        errors.append('free deflection pocket obstructed')
    for b in p['beams']:
        if not p['root_floor'].covers(b['plan']):errors.append('missing floor root')
        if b['rear_clearance_mm']<.79:errors.append('rear end not free')
        if b['plan'].intersection(p['case_rigid']).area>1e-9:errors.append('beam backed by rigid case')
    overlap=p['male'].intersection(p['case_rigid'].union(p['beam_body'])).area
    intended=p['male'].intersection(p['contact']).area
    if overlap>1e-9:errors.append('rigid overlap')
    if intended<=1e-9:errors.append('missing requested contact')
    return dict(errors=errors,rigid_overlap_mm2=overlap,intended_interference_mm2=intended,
                force_qualified=False,material_qualified=False,
                scope='Local declared-plan floor/root/free-volume topology only; actual CAD integration pending')


def prism(geometry,z0,z1):
    """Actual millimetre BRep; no canonical files are written."""
    import cadquery as cq
    pieces=[]
    for g in getattr(geometry,'geoms',[geometry]):
        if g.is_empty:continue
        wp=cq.Workplane('XY').workplane(offset=z0)
        for ring in [g.exterior,*g.interiors]:
            wp=wp.polyline(list(ring.coords)[:-1]).close()
        pieces.extend(wp.extrude(z1-z0).val().Solids())
    if not pieces:raise ValueError('Empty extrusion')
    return pieces[0] if len(pieces)==1 else cq.Compound.makeCompound(pieces)


def build_central_solids(p=None):
    """Two local test/interface solids, not complete keyboard housings.

Contact growth is seven0.10mm height strata, max lateral step0.0243mm.
The free cheek is floor-rooted and isolated from the case above the floor.
"""
    p=flexure_plan() if p is None else p
    if audit_flexure(p)['errors']:raise ValueError('Invalid declared flexure')
    left=prism(p['male'],-2.2,1.5)
    right=prism(p['root_floor'].union(p['case_rigid']),-2.2,-1.)
    additions=[prism(p['case_rigid'],-1.,1.5),prism(p['beam_body'],-1.,1.5)]
    for i in range(1,8):
        lips=[]
        for g in p['contact'].geoms:
            pivot=1.35 if g.centroid.y>0 else -1.35
            lips.append(affinity.scale(g,xfact=1,yfact=i/7,origin=(0,pivot)))
        additions.append(prism(unary_union(lips),.8+(i-1)*.1,.8+i*.1))
    right=right.fuse(*[s for shape in additions for s in shape.Solids()]).clean()
    if not right.isValid() or len(right.Solids())!=1:raise ValueError('Invalid central BRep')
    return left,right


def place_feature_solids(side,protected,ys=(95.,117.)):
    """Place feature-only BReps; trim root additions against actual cutouts.

Trimming is permitted only inside original case X, never on the bridge or
flexure. Full existing housing fusion and its free-pocket audit are separate.
"""
    if side not in ('left','right'):raise ValueError('Unknown housing side')
    p=flexure_plan();left,right=build_central_solids(p)
    shape=left if side=='left' else right
    xoff=.1 if side=='left' else 153.3
    planar=(p['male'] if side=='left' else p['root_floor'].union(p['case_rigid']).union(p['contact']))
    critical=planar.intersection(box(0 if side=='left' else -10,-10,10 if side=='left' else 4,10))
    results=[]
    for y in ys:
        mapped=lambda g:affinity.translate(affinity.scale(g,xfact=-1,yfact=1,origin=(0,0)),xoff=xoff,yoff=y)
        if mapped(critical).intersection(protected).area>1e-8:
            raise ValueError('Component cutout intersects central functional bridge')
        placed=shape.mirror('YZ').translate((xoff,y,0))
        local=protected.intersection(mapped(planar).buffer(.01))
        if not local.is_empty:
            placed=placed.cut(*prism(local,-1.,2.5).Solids()).clean()
        if not placed.isValid() or len(placed.Solids())!=1:raise ValueError('Root trim disconnected central feature')
        results.append(placed)
    return results
