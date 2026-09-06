"""CON-ARCH-006 flat MX plate-lid geometry; explicit datums, never order approval.

Inputs are design datums, not a claim that a particular switch was qualified.
Generic Cherry reference: https://www.farnell.com/datasheets/1792245.pdf
The selected switch's flange relief, clips, travel and pin engagement must still
be checked before this development geometry becomes a printable release.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import uuid
from pathlib import Path

from tools import generate_kc2_x3_v2_housings as lower


def stack_parameters(*, plate_top_above_pcb_mm, clip_thickness_mm, aperture_mm):
    values = (plate_top_above_pcb_mm, clip_thickness_mm, aperture_mm)
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('All explicit MX datums must be finite and positive')
    if plate_top_above_pcb_mm <= clip_thickness_mm:
        raise ValueError('Plate must have a positive component-clear standoff')
    pcb_top = lower.PCB_BOTTOM_Z_MM + lower.PCB_THICKNESS_MM
    bearing = pcb_top + plate_top_above_pcb_mm - 1.5
    collar_bottom = pcb_top + 1.2
    if bearing - collar_bottom < 1.0:
        raise ValueError('Recess requires at least 1 mm supported collar floor')
    return {
        'requirement': 'CON-ARCH-006', 'order_ready': False,
        'qualification_status': 'pending_exact_switch_and_fastener',
        'plate_top_above_pcb_mm': plate_top_above_pcb_mm,
        'clip_thickness_mm': clip_thickness_mm, 'aperture_mm': aperture_mm,
        'pcb_top_z_mm': pcb_top,
        'plate_top_z_mm': pcb_top + plate_top_above_pcb_mm,
        'plate_bottom_z_mm': pcb_top + plate_top_above_pcb_mm - clip_thickness_mm,
        'standoff_height_mm': plate_top_above_pcb_mm - clip_thickness_mm,
        'qualified_long_screw_length_mm': None,
        'nominal_under_head_to_receiver_entry_mm': bearing - lower.PCB_BOTTOM_Z_MM,
        'head_pocket_diameter_mm': 3.4, 'head_pocket_depth_mm': 1.5,
        'head_bearing_z_mm': bearing, 'head_top_z_mm': bearing + 1.2,
        'upper_collar_diameter_mm': 4.6, 'collar_bottom_z_mm': collar_bottom,
        'pcb_landing_diameter_mm': 3.0,
        'nominal_collar_wall_mm': .6,
        'collar_strength_qualification': 'engineering_geometry_only_not_strength_pass',
        'nominal_receiver_pilot_depth_mm': lower.MOUNTING_PILOT_DEPTH_MM,
        'receiver_qualification_status': 'pending_not_inherited_from_lower_only',
        'print_material': None, 'print_orientation': 'plate_top_on_bed_standoffs_up',
        'pending': ['exact_switch_drawing', 'socket_flange_relief', 'pin_engagement',
                    'printed_clip_fit', 'long_screw_receiver_torque', 'full_travel',
                    'split_joint_qualification', '2N_deflection', 'Fusion_native_round_trip'],
    }


def upper_plan(shp, plan, stack):
    """Actual key centers, concealed outline, open controller service, MH hard stops."""
    holes = []
    half = stack['aperture_mm']/2
    for switch in plan['switches']:
        x, y = switch['center']
        opening = shp['box'](x-half, y-half, x+half, y+half)
        opening = shp['affinity'].rotate(opening, switch['angle_deg'], origin=(x,y))
        if not plan['housing_outline'].covers(opening):
            raise RuntimeError(f"{switch['ref']}: opening escapes concealed outline")
        holes.append(opening)
    service = shp['unary_union']([
        plan['feature_geometries']['controller_socket'].convex_hull,
        *plan['mounting_service_geometries'].values(),
        plan['reset_actuator_geometry'],
    ]).buffer(.3)
    openings = shp['unary_union'](holes)
    pilots = shp['unary_union']([
        shp['Point'](*h['housing_center_mm']).buffer(.8, quad_segs=24)
        for h in plan['mounting_holes']
    ])
    plate = plan['housing_outline'].difference(openings.union(service).union(pilots))
    lands = plan['mounting_land_geometry'].difference(pilots)
    collars = shp['unary_union']([
        shp['Point'](*h['housing_center_mm']).buffer(stack['upper_collar_diameter_mm']/2, quad_segs=24)
        for h in plan['mounting_holes']]).difference(pilots)
    pockets = shp['unary_union']([
        shp['Point'](*h['housing_center_mm']).buffer(stack['head_pocket_diameter_mm']/2, quad_segs=24)
        for h in plan['mounting_holes']])
    if not plate.buffer(1e-6).covers(collars):
        raise RuntimeError('Recess collar collides with opening/service/outline')
    if not plate.covers(lands):
        raise RuntimeError('MX lid mounting land collides with opening/service/outline')
    if plate.geom_type != 'Polygon':
        raise RuntimeError('MX plate is disconnected; redesign service opening')
    return dict(plate=plate, openings=openings, service=service, lands=lands, pilots=pilots,
                collars=collars, pockets=pockets)


def split_upper_plan(shp, plan, upper):
    """Keep each key aperture whole, joining the two islands with captive heads."""
    from shapely import voronoi_polygons
    from shapely.geometry import MultiPoint
    centers = [s['center'] for s in plan['switches']]
    mid = (plan['housing_outline'].bounds[0]+plan['housing_outline'].bounds[2])/2
    cells = voronoi_polygons(MultiPoint(centers), extend_to=plan['housing_outline'].envelope)
    a_cells, b_cells = [], []
    for cell in cells.geoms:
        center = next(c for c in centers if cell.covers(shp['Point'](*c)))
        (a_cells if center[0] < mid else b_cells).append(cell)
    a_mask, b_mask = shp['unary_union'](a_cells), shp['unary_union'](b_cells)
    for opening in upper['openings'].geoms:
        region = opening.buffer(1.)
        if opening.centroid.x < mid:
            a_mask, b_mask = a_mask.union(region), b_mask.difference(region)
        else:
            a_mask, b_mask = a_mask.difference(region), b_mask.union(region)
    for hole in plan['mounting_holes']:
        # Reserve whole 4.6 mm collar plus seam setback; especially right MH8.
        disk = shp['Point'](*hole['housing_center_mm']).buffer(2.6, quad_segs=24)
        if a_mask.covers(shp['Point'](*hole['housing_center_mm'])):
            a_mask, b_mask = a_mask.union(disk), b_mask.difference(disk)
        else:
            a_mask, b_mask = a_mask.difference(disk), b_mask.union(disk)
    seam = a_mask.boundary.intersection(b_mask.boundary).intersection(plan['housing_outline'])
    # Unlike a straight saw cut, this stepped seam stays between complete clips.
    a = upper['plate'].intersection(a_mask.buffer(-.1))
    b = upper['plate'].intersection(b_mask.buffer(-.1))
    protected = upper['collars'].buffer(.3).union(upper['openings'].buffer(.6))
    capture = []
    for distance in [i*.1 for i in range(int(seam.length/.1)+1)]:
        point = seam.interpolate(distance)
        x,y = point.x, point.y
        if any(math.hypot(x-c[0], y-c[1]) < 15 for c in capture):
            continue
        for angle in (0,90,180,270):
            key = lower._puzzle_key_geometry(shp,x,y)
            # Extend the neck back into side A so the nominal seam gap cannot
            # create a zero-area contact at the root.
            root = shp['box'](x-.6,y-1,x+.2,y+1)
            key = shp['affinity'].rotate(key.union(root),angle,origin=(x,y))
            slot = key.buffer(.2)
            if not upper['plate'].covers(slot) or slot.intersects(protected):
                continue
            if key.intersection(a).area < .5 or key.intersection(b).area < 8:
                continue
            candidate_a = a.union(key)
            candidate_b = b.difference(slot)
            if candidate_a.geom_type!='Polygon' or candidate_b.geom_type!='Polygon':
                continue
            a,b = candidate_a,candidate_b
            capture.append([round(x,4),round(y,4),angle])
            break
        if len(capture)==2:
            break
    if len(capture)!=2:
        raise RuntimeError(f'Cannot retain right MX lid with two component-clear keys (found {len(capture)})')
    if a.intersection(b).area>1e-8 or not a.union(b).buffer(1e-6).covers(upper['lands']):
        raise RuntimeError('MX split cuts a hard-stop land or overlaps')
    for collar in upper['collars'].geoms:
        if not any(part.buffer(1e-6).covers(collar) for part in (a,b)):
            raise RuntimeError('MX split interrupts recessed-head collar')
    for opening in upper['openings'].geoms:
        # The continuous 0.6 mm clip-support ring must belong to one part.
        ring = opening.buffer(.6).difference(opening)
        if not any(part.buffer(1e-6).covers(ring) for part in (a,b)):
            raise RuntimeError(f'MX split interrupts a switch clip ring at {opening.centroid.wkt}')
    clamp_counts = [sum(part.covers(h['land_geometry'].difference(upper['pilots']))
                        for h in plan['mounting_holes']) for part in (a,b)]
    if any(count<2 for count in clamp_counts):
        raise RuntimeError('Each MX lid part needs at least two complete MH hard stops')
    motions = {name:float(shp['affinity'].translate(a,xoff=dx,yoff=dy).intersection(b).area)
               for name,dx,dy in [('positive_x',1,0),('negative_x',-1,0),('positive_y',0,1),('negative_y',0,-1)]}
    if any(area<=1e-6 for area in motions.values()):
        raise RuntimeError('MX puzzle joint does not constrain cardinal in-plane motion')
    return [a,b], dict(capture_count=2, capture_points=capture,
                      one_mm_in_plane_motion_collision_area_mm2=motions,
                      clamp_count_by_part=clamp_counts,
                      neck_width_mm=2., head_diameter_mm=4.5, clearance_mm=.2,
                      retention='two_in_plane_captive_heads_plus_long_screw_Z_clamp',
                      assembly_sequence='Engage puzzle keys vertically before mounting; align all MH holes; tighten long screws evenly')


def snapshot_board_geometry(output_dir, kicad_python):
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Snapshot bytes first: KiCad must not lock the routing agent's live board.
    snapshots = {}
    for side, path in lower.BOARD_PATHS.items():
        snapshot = output_dir / f'.source_{side}.kicad_pcb'
        shutil.copy2(path, snapshot)
        snapshots[side] = str(snapshot)
    code = ('import json,pcbnew; from pathlib import Path; '
            'from tools import generate_kc2_x3_v2_housings as g; '
            f'paths={snapshots!r}; '
            'g.BOARD_PATHS={k:Path(v) for k,v in paths.items()}; '
            'print(json.dumps({"boards":{k:g.extract_board(pcbnew,Path(v)) for k,v in paths.items()}}))')
    result = subprocess.run([str(kicad_python), '-B', '-c', code], cwd=lower.ROOT,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout), snapshots


def inspect_recess_geometry(cq, shp, model, part_plan, plan, upper, stack):
    """Measure generated BRep at each owned mount; no strength qualification."""
    rows=[]
    for hole in plan['mounting_holes']:
        x,y=hole['housing_center_mm']
        if not part_plan.covers(shp['Point'](x,y).buffer(.81).difference(upper['pilots'])):
            continue
        def cylinder(r,z,h):
            return cq.Workplane('XY').workplane(offset=z).center(x,y).circle(r).extrude(h)
        bearing=stack['head_bearing_z_mm']
        pcb=stack['pcb_top_z_mm']
        head=model.intersect(cylinder(1.5,bearing+.0001,1.2)).val().Volume()
        wall=model.intersect(cylinder(2.25,bearing+.2,.5).cut(
            cylinder(1.75,bearing+.1,.7))).val().Volume()
        outside=model.intersect(cylinder(2.3,pcb+.0001,.1).cut(
            cylinder(1.5001,pcb,.2))).val().Volume()
        collar=shp['Point'](x,y).buffer(2.3,quad_segs=24).difference(upper['pilots'])
        contained=part_plan.buffer(1e-6).covers(collar)
        if abs(head)>1e-7 or abs(wall-math.pi)>1e-7 or abs(outside)>1e-7 or not contained:
            raise RuntimeError(f'{hole["ref"]}: failed actual recessed-head BRep section')
        rows.append(dict(ref=hole['ref'],head_intersection_mm3=head,collar_slice_mm3=wall,
                         outside_landing_mm3=outside,collar_contained_in_one_part=bool(contained)))
    return rows


def generate(output_dir, kicad_python, stack):
    import cadquery as cq
    output_dir = output_dir.resolve()
    shp = lower.legacy_geometry.require_shapely()
    snapshot_dir = lower.ROOT/'.codex-tmp'/f'mx-upper-source-{uuid.uuid4().hex}'
    extracted, snapshots = snapshot_board_geometry(snapshot_dir,kicad_python)
    output_dir.mkdir(parents=True,exist_ok=True)
    manifest = dict(stack=stack, order_ready=False, print_ready=False, outputs={},
                    generated_by='tools/generate_kc2_mx_upper_housings.py',
                    generator_sha256=lower.sha256_file(Path(__file__)),
                    lower_generator_sha256=lower.sha256_file(Path(lower.__file__)),
                    hash_policy=lower.HASH_POLICY)
    for side, board in extracted['boards'].items():
        plan = lower.build_plan_geometry(shp, side, board)
        upper = upper_plan(shp, plan, stack)
        part_plans, joint = ([upper['plate']], None) if side=='left' else split_upper_plan(shp, plan, upper)
        models, parts, recess_checks = [], [], []
        for index, part_plan in enumerate(part_plans):
            plate = lower._extrude_geometry(cq, part_plan, stack['clip_thickness_mm'], stack['plate_bottom_z_mm'])
            stops = lower._extrude_geometry(cq, upper['lands'].intersection(part_plan), stack['standoff_height_mm'], stack['pcb_top_z_mm'])
            collars = lower._extrude_geometry(cq, upper['collars'].intersection(part_plan),
                stack['plate_bottom_z_mm']-stack['collar_bottom_z_mm'], stack['collar_bottom_z_mm'])
            pockets = lower._extrude_geometry(cq, upper['pockets'].intersection(part_plan),
                stack['head_pocket_depth_mm']+.1, stack['head_bearing_z_mm'])
            model = plate.union(stops).union(collars).cut(pockets)
            if len(model.solids().vals()) != 1 or not model.val().isValid():
                raise RuntimeError(f'{side}: invalid/disconnected MX lid solid')
            recess_checks.extend(inspect_recess_geometry(cq,shp,model,part_plan,plan,upper,stack))
            bounds = lower.model_bounds(model)
            if any(v>lower.PRINT_VOLUME_LIMIT_MM for v in bounds['size_xyz_mm']):
                raise RuntimeError(f'{side} part {index}: exceeds print envelope')
            suffix = '' if side=='left' else f'_part_{chr(97+index)}'
            stl = output_dir / f'kc2_{side}_mx_upper_housing{suffix}.stl'
            cq.exporters.export(model, str(stl), tolerance=.03, angularTolerance=.08, opt={'ascii':True})
            lower.normalize_exported_text(stl)
            from tools.verify_kc2_x3_v2_housing import inspect_ascii_stl
            mesh = inspect_ascii_stl(stl)
            if not mesh['watertight'] or mesh['shell_count'] != 1:
                raise RuntimeError(f'{side} part {index}: invalid STL topology')
            parts.append(dict(stl=stl.relative_to(lower.ROOT).as_posix(), stl_sha256=lower.sha256_file(stl),
                              watertight=True, shell_count=1, solid_count=1,
                              volume_mm3=model.val().Volume(), **bounds))
            models.append(model.val())
        model = cq.Workplane(obj=cq.Compound.makeCompound(models))
        step = output_dir / f'kc2_{side}_mx_upper_housing.step'
        cq.exporters.export(model, str(step), exportType='STEP')
        lower.normalize_exported_text(step)
        record = dict(source_board=lower.BOARD_PATHS[side].relative_to(lower.ROOT).as_posix(), source_board_sha256=lower.sha256_file(Path(snapshots[side])),
                      step=step.relative_to(lower.ROOT).as_posix(), step_sha256=lower.sha256_file(step),
                      step_has_trailing_whitespace=lower.has_trailing_horizontal_whitespace(step),
                      solid_count=len(models), switch_opening_count=len(plan['switches']),
                      hard_stop_count=len(plan['mounting_holes']), order_ready=False, print_ready=False,
                      fits_print_envelope=True, printable_parts=parts, split_joint=joint,
                      recess_geometry_checks=recess_checks)
        if len(recess_checks)!=len(plan['mounting_holes']):
            raise RuntimeError(f'{side}: incomplete recessed-head section evidence')
        svg = output_dir / f'kc2_{side}_mx_upper_plan.svg'
        x0,y0,x1,y1 = plan['housing_outline'].bounds
        shapes = ''.join(p.svg(scale_factor=.1, fill_color=color) for p,color in zip(part_plans,('#cce3f0','#e7cfad')))
        centers = ''.join(f'<circle cx="{h["housing_center_mm"][0]}" cy="{h["housing_center_mm"][1]}" r="1.5" fill="none" stroke="red" stroke-width=".15"/>' for h in plan['mounting_holes'])
        svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{x1-x0}mm" height="{y1-y0}mm" viewBox="{x0} {y0} {x1-x0} {y1-y0}">{shapes}{centers}</svg>',encoding='utf-8')
        record['top_plan_svg'] = svg.relative_to(lower.ROOT).as_posix()
        manifest['outputs'][side] = record
    path = output_dir / 'kc2_mx_upper_housing_manifest.json'
    # Dimensioned nominal axial section through MH; exact screw length is pending.
    section = output_dir / 'kc2_mx_mounting_section.svg'
    layers = [(lower.DESK_DATUM_Z_MM, lower.PCB_BOTTOM_Z_MM, '#cccccc','lower / blind receiver',.55,1.5),
              (lower.PCB_BOTTOM_Z_MM,stack['pcb_top_z_mm'],'#78af78','PCB / free NPTH',.8,1.5),
              (stack['pcb_top_z_mm'],stack['collar_bottom_z_mm'],'#89b8db','3 mm PCB landing / hard stop',.8,1.5),
              (stack['collar_bottom_z_mm'],stack['head_bearing_z_mm'],'#89b8db','4.6 mm upper collar / bearing floor',.8,2.3),
              (stack['head_bearing_z_mm'],stack['plate_top_z_mm'],'#467ca3','3.4 mm pocket / 0.6 mm wall',1.7,2.3)]
    content = '<text x="4" y="6" font-size="3">DEVELOPMENT: nominal MH section; screw and switch qualification pending</text>'
    for z0,z1,color,label,radius,outer_radius in layers:
        top=48-z1*3
        for x in (22-outer_radius*3,22+radius*3):
            width=(outer_radius-radius)*3
            content+=f'<rect x="{x}" y="{top}" width="{width}" height="{(z1-z0)*3}" fill="{color}" stroke="black" stroke-width=".1"/>'
        content+=f'<text x="32" y="{top+2}" font-size="2.3">{label}: Z {z0:.2f} .. {z1:.2f} mm</text>'
    content+=f'<rect x="17.5" y="{48-lower.MOUNTING_PILOT_BOTTOM_Z_MM*3}" width="9" height="{lower.MOUNTING_CLOSED_BOTTOM_MM*3}" fill="#cccccc" stroke="black" stroke-width=".1"/>'
    # Recess section: white pocket replaces the old plate-top head depiction.
    content+=f'<rect x="16.9" y="{48-stack["plate_top_z_mm"]*3}" width="10.2" height="4.5" fill="white" stroke="black" stroke-width=".1"/>'
    content+=f'<rect x="17.5" y="{48-stack["head_top_z_mm"]*3}" width="9" height="3.6" fill="none" stroke="red" stroke-width=".2"/>'
    content+='<text x="4" y="54" font-size="2.5">Red: 3.00 x 1.20 head; 1.50 recess, upper collar OD4.60 / pocket3.40; screw unqualified</text>'
    section.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="145mm" height="58mm" viewBox="0 0 145 58">'+content+'</svg>',encoding='utf-8')
    manifest['mounting_section_svg']=section.relative_to(lower.ROOT).as_posix()
    path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plate-top-above-pcb-mm', type=float, required=True)
    parser.add_argument('--clip-thickness-mm', type=float, required=True)
    parser.add_argument('--aperture-mm', type=float, required=True)
    parser.add_argument('--output-dir', type=Path, default=lower.OUTPUT_DIR)
    parser.add_argument('--kicad-python', type=Path, default=Path('C:/Program Files/KiCad/10.0/bin/python.exe'))
    args = parser.parse_args()
    stack = stack_parameters(plate_top_above_pcb_mm=args.plate_top_above_pcb_mm,
                             clip_thickness_mm=args.clip_thickness_mm, aperture_mm=args.aperture_mm)
    print(json.dumps(generate(args.output_dir, args.kicad_python, stack), indent=2))


if __name__ == '__main__':
    main()
