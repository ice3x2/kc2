"""CON-ARCH-004 AC-8: render the actual Gerber/Excellon bytes for inspection.

Requires gerbonara 1.6.3, resvg-py 0.5.0 and Pillow in an isolated environment.
Never edits PCB files or manufacturing inputs and never approves an order.
"""
from pathlib import Path
import argparse
import hashlib
import json
import importlib.metadata

SUFFIXES = {'F_Cu':'gtl','B_Cu':'gbl','F_Mask':'gts','B_Mask':'gbs',
            'F_Paste':'gtp','B_Paste':'gbp','F_Silkscreen':'gto',
            'B_Silkscreen':'gbo','Edge_Cuts':'gm1'}


def input_paths(root, side, *, require=True):
    if side not in ('left','right'):
        raise ValueError('side must be left or right')
    result = {name: root/side/f'kc2_{side}-{name}.{ext}' for name,ext in SUFFIXES.items()}
    result.update({name:root/side/f'kc2_{side}-{name}.drl' for name in ('PTH','NPTH')})
    if require:
        for path in result.values():
            if not path.is_file():
                raise FileNotFoundError(path)
    return result


def open_layer(path):
    from gerbonara import GerberFile, ExcellonFile
    return (ExcellonFile if path.suffix == '.drl' else GerberFile).open(path)


def render_layer(path, bounds):
    return str(open_layer(path).to_svg(force_bounds=bounds))


def rasterize(svg, width):
    import resvg_py
    return resvg_py.svg_to_bytes(svg_string=svg, width=width, dpi=96, background='white')


def overlay(layers, name, bounds):
    from gerbonara import LayerStack
    # Explicit layers: drill maps are never interpreted as actual drills.
    stack = LayerStack(graphic_layers={('top','outline'):layers['Edge_Cuts'],
                                     ('top','copper'):layers[name]},
                       drill_pth=layers['PTH'], drill_npth=layers['NPTH'])
    return str(stack.to_svg(force_bounds=bounds, colors={
        'top copper':'#ad382f', 'top outline':'#2275cc',
        'drill pth':'#ffffff', 'drill npth':'#323232'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Keep review derivatives separate from the manufacturing input directories.
    if args.output.resolve().is_relative_to(args.input.resolve()):
        raise ValueError('inspection output must be outside manufacturing input tree')
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'requirement':'CON-ARCH-004 AC-8', 'order_approval':False,
                'orientation':'All views are board top-coordinate view; bottom is not physically mirrored.',
                'versions':{p:importlib.metadata.version(p) for p in ('gerbonara','resvg-py','Pillow')},
                'sides':{}}
    for side in ('left','right'):
        paths = input_paths(args.input,side)
        hashes = {n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in paths.items()}
        layers = {n:open_layer(p) for n,p in paths.items()}
        bb = layers['Edge_Cuts'].bounding_box()
        bounds = ((bb[0][0]-1,bb[0][1]-1),(bb[1][0]+1,bb[1][1]+1))
        records = {}
        def save(name, svg, width=2400):
            p=args.output/f'{side}-{name}.svg'; p.write_text(svg,encoding='utf-8')
            q=p.with_suffix('.png'); q.write_bytes(rasterize(svg,width))
            records[name]={'svg':p.name,'png':q.name,
                           'svg_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                           'png_sha256':hashlib.sha256(q.read_bytes()).hexdigest()}
        for name,layer in layers.items():
            save(name,str(layer.to_svg(force_bounds=bounds)))
        for name in ('F_Cu','B_Cu','F_Mask','B_Mask'):
            save(name+'-holes',overlay(layers,name,bounds))
            # Source coordinates: service area lies at y=39..71 on the PCB,
            # which is y=-71..-39 in actual KiCad Gerber output.
            service=((107,-72),(153,-37)) if side=='left' else ((57,-72),(103,-37))
            save(name+'-service',overlay(layers,name,service),2200)
        # Six copper tiles cover the entire outline on each layer without gaps.
        for name in ('F_Cu','B_Cu'):
            for row in range(3):
                for col in range(2):
                    x0=bounds[0][0]+col*(bounds[1][0]-bounds[0][0])/2
                    y0=bounds[0][1]+row*(bounds[1][1]-bounds[0][1])/3
                    tile=((x0,y0),(x0+(bounds[1][0]-bounds[0][0])/2,y0+(bounds[1][1]-bounds[0][1])/3))
                    save(f'{name}-tile-{row}-{col}',overlay(layers,name,tile),1800)
        if hashes != {n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in paths.items()}:
            raise RuntimeError('Manufacturing inputs changed during rendering')
        manifest['sides'][side]={'input_sha256':hashes,'bounds_mm':bounds,'views':records,
                                'objects':{n:len(l.objects) for n,l in layers.items()}}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'views':sum(len(s['views']) for s in manifest['sides'].values()),'order_approval':False}))


if __name__ == '__main__':
    main()
