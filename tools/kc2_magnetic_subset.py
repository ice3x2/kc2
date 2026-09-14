"""CON-ARCH-006 actual two-solid subset only; not component qualification."""
import math

EXPECTED_REMOVAL_MM3=4*math.pi*1.2**2*1.2


def finite(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Non-numeric actual metric')
    return value


def bounds(shape):
    b=shape.BoundingBox()
    return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]


def nd_cut(a,b):
    import cadquery as cq
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.TopTools import TopTools_ListOfShape
    args=TopTools_ListOfShape();args.Append(a.wrapped)
    tools=TopTools_ListOfShape();tools.Append(b.wrapped)
    op=BRepAlgoAPI_Cut();op.SetArguments(args);op.SetTools(tools)
    op.SetNonDestructive(True);op.SetRunParallel(True);op.Build()
    if not op.IsDone():raise ValueError('Non-destructive Cut failed')
    return cq.Shape.cast(op.Shape())


def valid_body(body):
    return (body.ShapeType()=='Solid' and body.isValid() and len(body.Solids())==1
        and bool(body.Shells()) and all(s.Closed() for s in body.Shells())
        and finite(body.Volume())>0)


def check_generation(record,variant,step_sha,parts):
    name='kc2_right_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step'
    if (variant not in ('normal','magnetic') or record.get('side')!='right'
        or record.get('magnetic') is not (variant=='magnetic')
        or record.get('status')!='generated_pending_independent_review'
        or type(record.get('body_count')) is not int or record['body_count']!=2
        or record.get('outputs',{}).get(name)!=step_sha or len(record.get('parts',[]))!=2 or len(parts)!=2):
        raise ValueError('Wrong actual generation/variant identity')
    for i,(row,body) in enumerate(zip(record['parts'],parts)):
        if type(row.get('index')) is not int or row['index']!=i:raise ValueError('Wrong part ordering')
        expected=row.get('bounds_mm',[])
        if len(expected)!=6 or max(abs(finite(x)-y) for x,y in zip(expected,bounds(body)))>1e-6:
            raise ValueError('Actual part orientation/bounds differ from generation')
        if abs(finite(row.get('volume_mm3'))-body.Volume())>.002:raise ValueError('Actual part volume differs')


def audit(normal,magnetic,progress=None):
    if len(normal)!=2 or len(magnetic)!=2 or any(not valid_body(s) for s in normal+magnetic):
        raise ValueError('Expected two valid closed positive solids per variant')
    if any(parts[0].Center().x>=parts[1].Center().x for parts in (normal,magnetic)):
        raise ValueError('Part A/B orientation or ownership reversed')
    rows=[]
    for i,(a,b) in enumerate(zip(normal,magnetic)):
        if max(abs(x-y) for x,y in zip(bounds(a),bounds(b)))>1e-6:
            raise ValueError('Normal/magnetic paired body bounds differ')
        if progress:progress(i,'magnetic_minus_normal')
        extra=nd_cut(b,a)
        if progress:progress(i,'normal_minus_magnetic')
        removed=nd_cut(a,b)
        rows.append(dict(part=i,normal_valid_closed_positive=True,magnetic_valid_closed_positive=True,
            normal_bounds_mm=bounds(a),magnetic_bounds_mm=bounds(b),normal_volume_mm3=a.Volume(),magnetic_volume_mm3=b.Volume(),
            magnetic_minus_normal_mm3=extra.Volume(),magnetic_minus_normal_solids=len(extra.Solids()),
            magnetic_minus_normal_faces=len(extra.Faces()),
            normal_minus_magnetic_mm3=removed.Volume(),normal_minus_magnetic_solids=len(removed.Solids()),
            added_result_valid=extra.isValid(),removed_result_valid=removed.isValid()))
    return dict(body_count=2,parts=rows,removed_total_mm3=sum(r['normal_minus_magnetic_mm3'] for r in rows),
        expected_removed_mm3=EXPECTED_REMOVAL_MM3,non_destructive_cut=True)


def validate_metrics(record):
    if type(record.get('body_count')) is not int or record['body_count']!=2 or record.get('non_destructive_cut') is not True or len(record.get('parts',[]))!=2:
        raise ValueError('Incomplete actual subset topology')
    for i,row in enumerate(record['parts']):
        if type(row.get('part')) is not int or row['part']!=i:raise ValueError('Wrong actual part identity')
        for variant in ('normal','magnetic'):
            bb=row.get(variant+'_bounds_mm',[])
            if len(bb)!=6 or any(finite(bb[j+3])<=finite(bb[j]) for j in range(3)) or finite(row.get(variant+'_volume_mm3'))<=0:
                raise ValueError('Missing positive body extent/volume')
        if max(abs(a-b) for a,b in zip(row['normal_bounds_mm'],row['magnetic_bounds_mm']))>1e-6:
            raise ValueError('Paired actual ownership/bounds mismatch')
        if any(row.get(k) is not True for k in ('normal_valid_closed_positive','magnetic_valid_closed_positive','added_result_valid','removed_result_valid')):
            raise ValueError('Invalid or open actual material')
        if finite(row.get('magnetic_minus_normal_mm3'))!=0 or any(type(row.get(k)) is not int or row[k]!=0 for k in ('magnetic_minus_normal_solids','magnetic_minus_normal_faces')):
            raise ValueError('Magnetic material is not an exact subset')
        removed=finite(row.get('normal_minus_magnetic_mm3'))
        count=row.get('normal_minus_magnetic_solids')
        if type(count) is not int or (i==0 and (removed!=0 or count!=0)) or (i==1 and (count<1 or abs(removed-EXPECTED_REMOVAL_MM3)>.002)):
            raise ValueError('Removal has wrong part ownership or volume')
    total=finite(record.get('removed_total_mm3'))
    if finite(record.get('expected_removed_mm3'))!=EXPECTED_REMOVAL_MM3 or abs(total-EXPECTED_REMOVAL_MM3)>.002 or total!=sum(r['normal_minus_magnetic_mm3'] for r in record['parts']):
        raise ValueError('Incorrect complete magnet removal')
    return True
