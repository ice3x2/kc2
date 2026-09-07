"""CON-ARCH-006/OPS-ARCH-007: actual STEP populated-envelope and print audit.

This is nominal digital evidence, not qualification of unmeasured supplied parts.
"""
import hashlib
import json
from pathlib import Path
import cadquery as cq
from tools import generate_kc2_x3_v2_housings as g
from tools import generate_kc2_mx_upper_housings as upper

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/reports/continuous-web-20260908-r5'

def volume(shape):
    return sum(s.Volume() for s in shape.solids().vals())

def audit():
    sources=[Path(__file__),Path(g.__file__),Path(upper.__file__),
        ROOT/'tools/verify_kc2_x3_v2_housing.py']
    sources+=list((ROOT/'hardware/MODELS').glob('*.step'))
    sources+=list((ROOT/'hardware/MODELS').glob('*.stl'))
    sources+=list((ROOT/'hardware/GERBER').glob('*'))
    sources += [p for p in (ROOT/'hardware/PCB').rglob('*.kicad_pcb')]
    def hashes():
        return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sources if p.is_file()}
    before=hashes()
    boards=g.run_extractor(Path('C:/Program Files/KiCad/10.0/bin/python.exe'))['boards']
    shp=g.legacy_geometry.require_shapely()
    report=dict(requirements=['CON-ARCH-006','OPS-ARCH-007'],source_sha256=before,
        sides={},errors=[],physical_qualification_complete=False,
        assumptions={'maximum_underside_projection_mm':2.9,
            'inner_floor_to_PCB_mm':3.5,'nominal_vertical_reserve_mm':.6,
            'plan_clearance_mm':g.COMPONENT_MINIMUM_CLEARANCE_MM,
            'assembly_modes':'MX receptacles OR Choc sockets, never both on one switch',
            'unmeasured':['received pin/socket tolerances','header and solder projection',
                'exact battery and wiring envelope','keycap skirt through full travel',
                'print shrinkage, flatness and strength']})
    for side,board in boards.items():
        print(side, 'importing actual CAD',flush=True)
        plan=g.build_plan_geometry(shp,side,board)
        shapes={kind:cq.importers.importStep(str(ROOT/f'hardware/MODELS/kc2_{side}_{kind}_housing.step'))
                for kind in ('lower','mx_upper')}
        record={'solids':{},'components':{}}
        for kind,shape in shapes.items():
            record['solids'][kind]={'valid':all(s.isValid() for s in shape.solids().vals()),
                'count':len(shape.solids().vals()),'volume_mm3':volume(shape)}
            if not record['solids'][kind]['valid'] or record['solids'][kind]['count']!=(1 if side=='left' else 2):
                report['errors'].append(side+' '+kind+' invalid solid/count')
        if side=='right':
            split=g.build_right_split_plan(shp,plan)
            web=split['part_a_plan'].union(split['part_b_plan'])
            floors=split['floor_part_a_mask'].union(split['floor_part_b_mask'])
        else:web=plan['support_surface'];floors=plan['housing_outline']
        # The separate full housing verifier performs expensive complete BRep
        # inclusion. Corroborate it here with actual section geometry rather
        # than running the identical full-solid boolean a second time.
        def coords(wire):return [(p.x,p.y) for p in wire.sample(1e-5)[0]]
        sections=[]
        for z,expected in [(-.65,web),(1.1,web.difference(plan['mounting_pilot_geometry']))]:
            faces=shapes['lower'].section(z).faces().vals()
            actual=shp['unary_union']([shp['Polygon'](coords(face.outerWire()),
                [coords(w) for w in face.innerWires()]) for face in faces])
            missing=expected.difference(actual.buffer(.0001)).area
            extra=actual.difference(expected.buffer(.0001)).area
            sections.append(dict(z_mm=z,missing_area_mm2=missing,extra_area_mm2=extra,
                curve_deflection_mm=.00001,comparison_tolerance_mm=.0001))
            if missing>.001 or extra>.001:report['errors'].append(side+' support section mismatch')
        record['support_sections']=sections
        record['full_depth_evidence']='hardware/MODELS/kc2_housing_clearance.json: sides.'+side+'.web_continuity (required separately)'
        record['bottom_up_layer_containment']={
            'web_outside_floor_area_mm2':web.difference(floors).area,
            'basis':'floor prism -2.2..-1; web prism -1..2.5; top-open pilot removal starts -.3; no layer adds material outside preceding layer'}
        if web.difference(floors).area>1e-6:
            report['errors'].append(side+' unsupported material')
        overlap=volume(shapes['lower'].intersect(shapes['mx_upper']))
        record['lower_upper_intersection_mm3']=overlap
        if overlap>.001:report['errors'].append(side+' lower/upper collision')
        top_service={'controller_socket':plan['feature_geometries']['controller_socket'].convex_hull,
            **plan['mounting_service_geometries'],'reset_actuator':plan['reset_actuator_geometry']}
        record['top_service_intersection_mm3']={}
        for name,geometry in top_service.items():
            if geometry.is_empty:continue
            cutter=g._extrude_geometry(cq,geometry,5.2,4.1)
            collision=volume(shapes['mx_upper'].intersect(cutter))
            record['top_service_intersection_mm3'][name]=collision
            if collision>.001:report['errors'].append(side+' topside '+name+' collision')
        for name,raw in plan['component_geometries'].items():
            if raw.is_empty:continue
            print(side,name,'checking swept component envelope',flush=True)
            # All underside classes are conservatively swept to the maximum
            # allowed pin/fillet depth; this includes the newly extended web.
            envelope=raw.buffer(g.COMPONENT_MINIMUM_CLEARANCE_MM,join_style='round',quad_segs=4)
            cutter=g._extrude_geometry(cq,envelope,2.9,-.4)
            collision=volume(shapes['lower'].intersect(cutter))
            record['components'][name]={'count':plan['component_cutout_counts'][name],
                'tested_z_mm':[-.4,2.5],'intersection_mm3':collision,
                'status':'nominal envelope only; actual projection must meet bound'}
            if collision>.001:report['errors'].append(side+' '+name+' collision')
        rings=[]
        for sw in plan['switches']:
            x,y=sw['center']
            rings.append(cq.Workplane('XY',origin=(x,y,2.9)).circle(2.4).circle(1.75).extrude(1.2)
                .union(cq.Workplane('XY',origin=(x,y,4.1)).circle(3).circle(1.75).extrude(.2)).val())
        ring=cq.Workplane(obj=cq.Compound.makeCompound(rings))
        record['adapter_intersection_mm3']={kind:volume(shape.intersect(ring)) for kind,shape in shapes.items()}
        if any(v>.001 for v in record['adapter_intersection_mm3'].values()):report['errors'].append(side+' adapter collision')
        report['sides'][side]=record
        print(side,report['errors'],flush=True)
    report['sources_unchanged']=before==hashes()
    if not report['sources_unchanged']:report['errors'].append('sources changed during audit')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'populated-cad.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'errors':report['errors']},indent=2))
    return bool(report['errors'])

if __name__=='__main__':raise SystemExit(audit())
