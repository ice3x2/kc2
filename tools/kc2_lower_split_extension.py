"""CON-ARCH-006 outside-only lower partition extension and local A/B relief."""
from shapely.geometry import box,Point
from tools.kc2_split_fit_relief import plan_split_relief
def extend_relieve(a,b,domain,seam,protected_a=None,protected_b=None):
    if not a.bounds[0]<seam<b.bounds[2]:raise ValueError('Invalid extension seam')
    outside=domain.difference(a.union(b))
    x0,y0,x1,y1=domain.bounds
    aa=a.union(outside.intersection(box(x0-1,y0-1,seam-.1,y1+1)))
    bb=b.union(outside.intersection(box(seam+.1,y0-1,x1+1,y1+1)))
    return plan_split_relief(aa,bb,protected_a=protected_a,protected_b=protected_b,
        target_gap=.4,entry_extra=0,z_min=-2.2,z_max=5)

def retained_key_relief(a,b,domain,seam,ys):
    """Keep4.50 heads and2.00 necks; receiveronly .40004 relief.

    A2.00 neck with .40 per-face receiver space leaves2.80 throat;
    retained4.50 head gives0.85 nominal shoulder capture per side.
    """
    outside=domain.difference(a.union(b));x0,y0,x1,y1=domain.bounds
    aa=a.union(outside.intersection(box(x0-1,y0-1,seam-.1,y1+1)))
    bb=b.union(outside.intersection(box(seam+.1,y0-1,x1+1,y1+1)))
    for y in ys:
        old=box(seam-.1,y-1,seam+3,y+1).union(Point(seam+3,y).buffer(2.25,quad_segs=24))
        if old.difference(aa.buffer(1e-7)).area>1e-6:raise ValueError('Original capture not present')
    bb=bb.difference(aa.buffer(.40004,quad_segs=128))
    if aa.geom_type!='Polygon' or bb.geom_type!='Polygon' or aa.distance(bb)<.39999:
        raise ValueError('Retained-key relief disconnected or gap insufficient')
    return aa,bb
