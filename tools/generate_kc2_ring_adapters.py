"""CON-ARCH-004: reproducible trial centering rings, STL coordinates in mm."""
import json
import math
import struct
from pathlib import Path

SPECS = {'v1': 3.50, 'mx': 4.10}
ROOT = Path(__file__).resolve().parents[1]


def mesh(bore, segments=192):
    if not 0 < bore < 4.8 or segments < 12:
        raise ValueError('Bore must leave a barrel wall; segments >= 12')
    profile = [(bore/2, 0), (3, 0), (3, .2), (2.4, .2), (2.4, 1.4), (bore/2, 1.4)]
    vertices = [(r*math.cos(i*2*math.pi/segments), r*math.sin(i*2*math.pi/segments), z)
                for r,z in profile for i in range(segments)]
    faces = []
    for k in range(len(profile)):
        for i in range(segments):
            j = (i+1) % segments
            n = (k+1) % len(profile)
            a,b,c,d = k*segments+i, k*segments+j, n*segments+j, n*segments+i
            faces.extend([(a,b,c), (a,c,d)])
    return vertices, faces


def export_stl(path, vertices, faces):
    with path.open('wb') as out:
        out.write(b'KC2 CON-ARCH-004 trial ring; mm; flange down'.ljust(80, b' '))
        out.write(struct.pack('<I', len(faces)))
        for face in faces:
            a,b,c = [vertices[i] for i in face]
            u,v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
            normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            length = math.sqrt(sum(x*x for x in normal))
            out.write(struct.pack('<12fH', *[x/length for x in normal], *a, *b, *c, 0))


def main():
    target = ROOT/'hardware/case/adapters'
    target.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name,bore in SPECS.items():
        path = target/f'kc2_{name}_ring_cap_020.stl'
        vertices,faces = mesh(bore)
        export_stl(path, vertices, faces)
        outputs.append(dict(file=path.name, bore_mm=bore, triangles=len(faces)))
    import hashlib
    for item in outputs:
        item['sha256'] = hashlib.sha256((target/item['file']).read_bytes()).hexdigest()
    report = dict(requirement='CON-ARCH-004', units='mm', barrel_od_mm=4.8,
                  flange_od_mm=6, flange_thickness_mm=.2, insertion_length_mm=1.2,
                  total_height_mm=1.4, print_orientation='flange on bed, Z=0',
                  physical_fit_verified=False, dimensions='engineering trial, not measured part dimensions',
                  outputs=outputs)
    (target/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
