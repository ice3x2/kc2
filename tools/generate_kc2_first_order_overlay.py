"""OPS-ARCH-007 AC-5: read-only actual PCB pad/plate 1:1 SVG evidence.

Run with KiCad Python. Does not save boards or claim physical fit.
"""
import hashlib
import html
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def render_svg(data, side, digest):
    if not data['edges']:
        raise ValueError('missing actual board outline')
    xs = [v for e in data['edges'] for v in (e[0], e[2])]
    ys = [v for e in data['edges'] for v in (e[1], e[3])]
    x, y = min(xs)-5, min(ys)-5
    w, h = max(70, max(xs)-x+5), max(ys)-y+15
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}mm" height="{h:g}mm" viewBox="{x:g} {y:g} {w:g} {h:g}">',
           f'<title>{side}: 1 SVG unit = 1 mm; actual PCB centers; not a full-travel fit approval</title>',
           f'<desc>PCB SHA256 {digest}; black Edge.Cuts, blue nominal 14 mm aperture, red U1 holes, green MH holes, orange switch holes. Print actual size, no fit-to-page.</desc>']
    for a,b,c,d in data['edges']:
        out.append(f'<path d="M {a:g},{b:g} L {c:g},{d:g}" fill="none" stroke="black" stroke-width=".15"/>')
    for s in data['switches']:
        cx,cy=s['center']; ref=html.escape(s['ref'], quote=True)
        out.append(f'<rect data-ref="{ref}" x="{cx-7:g}" y="{cy-7:g}" width="14" height="14" transform="rotate({-s["rotation"]:g} {cx:g} {cy:g})" fill="none" stroke="#1673b1" stroke-width=".12"/>')
        out.append(f'<text x="{cx:g}" y="{cy-5:g}" font-size="1.5" text-anchor="middle">{ref}</text>')
    for p in data['pads']:
        cx,cy=p['center']; ref=html.escape(p['ref']+':'+p['number'], quote=True)
        color='red' if p['ref']=='U1' else '#08782c' if p['ref'].startswith('MH') else '#a45b00'
        out.append(f'<circle data-ref="{ref}" cx="{cx:g}" cy="{cy:g}" r="{p["drill"]/2:g}" fill="none" stroke="{color}" stroke-width=".10"/>')
    footer=max(ys)+4
    out.append(f'<text x="{x+2:g}" y="{footer:g}" font-size="1.7">Black PCB / blue 14mm plate / red U1 / green MH / orange SW</text>')
    out.append(f'<path d="M {x+3:g},{footer+6:g} h 50 m -50,-1 v 2 m 50,-2 v 2" fill="none" stroke="black" stroke-width=".2"/>')
    out.append(f'<text x="{x+3:g}" y="{footer+4:g}" font-size="1.7">50 mm calibration; print 100%, no fit-to-page</text>')
    out.append('</svg>')
    return '\n'.join(out)+'\n'


def generate():
    import pcbnew
    output = ROOT/'hardware/case'
    manifest={'requirement':'OPS-ARCH-007 AC-5', 'units':'mm', 'hash_policy':'sha256_raw_bytes_no_newline_normalization; independent overlay provenance, not canonical_hash main-chain digests', 'physical_qualification_complete':False, 'boards':{}}
    for side, expected in [('left',31),('right',39)]:
        path=ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
        raw=path.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(prefix='kc2-overlay-') as tmp:
            snapshot=Path(tmp)/path.name
            snapshot.write_bytes(raw)
            board=pcbnew.LoadBoard(str(snapshot))
            point=lambda p:[pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)]
            data={'edges':[], 'switches':[], 'pads':[]}
            for d in board.GetDrawings():
                if d.GetLayer()==pcbnew.Edge_Cuts:
                    if d.GetShape()!=pcbnew.SHAPE_T_SEGMENT:
                        raise ValueError('non-segment outline needs exact additional renderer')
                    data['edges'].append(point(d.GetStart())+point(d.GetEnd()))
            for fp in board.GetFootprints():
                ref=fp.GetReference()
                switch=ref.startswith('SW') and ref[2:].isdigit()
                if switch:
                    data['switches'].append(dict(ref=ref,center=point(fp.GetPosition()),rotation=fp.GetOrientationDegrees()))
                if switch or ref=='U1' or ref.startswith('MH'):
                    for p in fp.Pads():
                        drill=point(p.GetDrillSize())
                        if drill[0]>0:
                            if abs(drill[0]-drill[1])>1e-8:
                                raise ValueError('slot needs exact additional renderer')
                            data['pads'].append(dict(ref=ref,number=p.GetNumber(),center=point(p.GetPosition()),drill=drill[0]))
            if len(data['switches'])!=expected or sum(p['ref']=='U1' for p in data['pads'])!=24:
                raise ValueError('unexpected source switch/controller count')
        if path.read_bytes()!=raw:
            raise ValueError('source changed during extraction')
        dest=output/f'kc2_{side}_first_order_1to1.svg'
        dest.write_text(render_svg(data,side,digest),encoding='utf-8')
        manifest['boards'][side]={'source':path.relative_to(ROOT).as_posix(),'source_sha256':digest,'svg':dest.relative_to(ROOT).as_posix(),'svg_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'actual_geometry':data}
    target=output/'kc2_first_order_1to1_manifest.json'
    target.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(target)


if __name__=='__main__':
    generate()
