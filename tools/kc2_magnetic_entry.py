"""CON-ARCH-006 coaxial through-access in NEW raised magnetic walls only.

Original blind mouths remain X0.10(left)/149.30(right), Ø2.40, depth1.20,
Y103/111 and centerZ0.75. Access begins outside the new wall and STOPS at
the old mouth; the0.40 airgap is not an extension of the blind pocket.
"""
def entry_tools(side):
    import cadquery as cq
    if side not in ('left','right'):raise ValueError('Invalid side')
    start,mouth,sign=(-1.6,.1,1) if side=='left' else (151.,149.3,-1)
    return [cq.Solid.makeCylinder(1.2,abs(mouth-start),cq.Vector(start,y,.75),cq.Vector(sign,0,0)) for y in (103.,111.)]
def open_entries(shape,side):
    result=shape.cut(*entry_tools(side)).clean()
    if not result.isValid() or len(result.Solids())!=len(shape.Solids()):raise ValueError('Magnet access disconnected housing')
    return result
