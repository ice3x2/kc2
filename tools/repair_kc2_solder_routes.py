"""CON-ARCH-004: obstacle-aware local detours for enlarged solder lands.

Run orchestration with Python + Shapely; the script invokes the installed
KiCad Python for exact polygon extraction and board writes. Defaults to dry-run;
--apply backs up before saving. Pad copper geometry/nets/rules never change;
missing electrical PTH solder-mask layers are restored. Fresh KiCad DRC remains
authoritative; this geometric planner and its temporary plans are not sign-off.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import heapq
import math
from pathlib import Path
import shutil

import json
import subprocess
import uuid

try:
    import pcbnew
    import wx
    _log = wx.LogStderr()
    wx.Log.SetActiveTarget(_log)
except ImportError:
    pcbnew = None
if pcbnew is None:
    from shapely.geometry import Point, LineString, Polygon, box
    from shapely.ops import unary_union
    from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[1]


def xy(p):
    return (round(p.x / 1e6, 6), round(p.y / 1e6, 6))


def vec(p):
    return pcbnew.VECTOR2I(round(p[0] * 1e6), round(p[1] * 1e6))




def path_around(start, end, obstacle):
    direct = LineString([start, end])
    if not direct.intersects(obstacle):
        return [start, end]
    for margin in (2, 5, 10):
        area = box(min(start[0],end[0])-margin, min(start[1],end[1])-margin,
                   max(start[0],end[0])+margin, max(start[1],end[1])+margin)
        local = obstacle.intersection(area)
        # Buffered vertices give strictly exterior line-of-sight candidates.
        shell = local.buffer(0.006, quad_segs=2).simplify(0.002, preserve_topology=True)
        polygons = [shell] if shell.geom_type == 'Polygon' else list(shell.geoms)
        nodes = [start, end]
        for polygon in polygons:
            if polygon.geom_type == 'Polygon':
                nodes.extend(list(polygon.exterior.coords)[:-1])
                for ring in polygon.interiors:
                    nodes.extend(list(ring.coords)[:-1])
        prepared = prep(obstacle)
        costs = {0: 0.0}
        previous = {}
        queue = [(math.dist(start,end), 0.0, 0)]
        done = set()
        while queue:
            _, cost, current = heapq.heappop(queue)
            if current in done:
                continue
            done.add(current)
            if current == 1:
                path = [end]
                while current:
                    current = previous[current]
                    path.append(nodes[current])
                return list(reversed(path))
            for other in range(len(nodes)):
                if other in done:
                    continue
                length = math.dist(nodes[current], nodes[other])
                candidate = cost + length
                if candidate >= costs.get(other, float('inf')):
                    continue
                if prepared.intersects(LineString([nodes[current], nodes[other]])):
                    continue
                costs[other] = candidate
                previous[other] = current
                heapq.heappush(queue, (candidate + math.dist(nodes[other], end), candidate, other))
    raise RuntimeError(f'No local path from {start} to {end}')




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('side', choices=('left','right'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--apply-plan', action='store_true')
    parser.add_argument('--source')
    parser.add_argument('--report')
    parser.add_argument('--supports')
    args = parser.parse_args()
    path = ROOT / f'hardware/kicad/kc2_{args.side}/kc2_{args.side}.kicad_pcb'
    model_path = ROOT / f'.codex-tmp/{args.side}-solder-route-model.json'
    if args.export:
        board = pcbnew.LoadBoard(args.source or str(path))
        data = {'pads': [], 'tracks': [], 'edges': [], 'fcu': pcbnew.F_Cu, 'bcu': pcbnew.B_Cu}
        if args.supports:
            data['supports'] = json.loads(Path(args.supports).read_text(encoding='utf-8'))['sides'][args.side]
        report = json.loads(Path(args.report or ROOT / f'.codex-tmp/{args.side}-solder-route-regression.drc.json').read_text(encoding='utf-8'))
        data['suspects'] = list({item['uuid'] for violation in report['violations'] if violation['severity']=='error'
                                 for item in violation['items']})
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if not pad.IsOnLayer(layer) and pad.GetAttribute()!=pcbnew.PAD_ATTRIB_NPTH:
                        continue
                    poly = pcbnew.SHAPE_POLY_SET()
                    pad.TransformShapeToPolygon(poly, layer, 0, 1000, pcbnew.ERROR_OUTSIDE)
                    for i in range(poly.OutlineCount()):
                        outline = poly.Outline(i)
                        data['pads'].append({'net':pad.GetNetCode(), 'layer':layer, 'center':xy(pad.GetPosition()),
                            'polygon':[xy(outline.CPoint(j)) for j in range(outline.PointCount())]})
        for track in board.GetTracks():
            width = track.GetWidth(pcbnew.F_Cu) if isinstance(track,pcbnew.PCB_VIA) else track.GetWidth()
            data['tracks'].append({'uuid':track.m_Uuid.AsString(), 'net':track.GetNetCode(), 'width':width/1e6,
                'layer':track.GetLayer(), 'via':isinstance(track,pcbnew.PCB_VIA),
                'start':xy(track.GetStart()), 'end':xy(track.GetEnd())})
        for edge in board.GetDrawings():
            if edge.GetLayer()==pcbnew.Edge_Cuts and edge.GetShape()==pcbnew.SHAPE_T_SEGMENT:
                data['edges'].append([xy(edge.GetStart()),xy(edge.GetEnd())])
        model_path.write_text(json.dumps(data), encoding='utf-8')
        return
    if args.apply_plan:
        board = pcbnew.LoadBoard(str(path))
        data = json.loads(model_path.read_text(encoding='utf-8'))
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = ROOT / f'.codex-tmp/{path.stem}-before-solder-route-{stamp}.kicad_pcb'
        shutil.copy2(path, backup)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetAttribute()==pcbnew.PAD_ATTRIB_PTH:
                    layers = pcbnew.LSET(pcbnew.LSET.AllCuMask())
                    layers.AddLayer(pcbnew.F_Mask); layers.AddLayer(pcbnew.B_Mask)
                    pad.SetLayerSet(layers)
        consumed=set()
        for track in list(board.GetTracks()):
            if not isinstance(track,pcbnew.PCB_VIA):
                candidates=[t for t in data['tracks'] if t['uuid']==track.m_Uuid.AsString() and not t['via']]
                if len(candidates)==1:
                    source=candidates[0]
                    track.SetStart(vec(source['start'])); track.SetEnd(vec(source['end']))
                    track.SetLayer(source['layer']); track.SetNetCode(source['net'])
                    track.SetWidth(round(source['width']*1e6)); consumed.add(id(source))
                else:
                    board.Delete(track)
            else:
                source = next(t for t in data['tracks'] if t['uuid']==track.m_Uuid.AsString())
                track.SetPosition(vec(source['start']))
        for source in data['tracks']:
            if id(source) in consumed:
                continue
            if source['via']:
                if source.get('new'):
                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(vec(source['start']))
                    via.SetViaType(pcbnew.VIATYPE_THROUGH)
                    via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
                    via.SetWidth(round(source['width']*1e6))
                    via.SetDrill(pcbnew.FromMM(0.3))
                    via.SetNetCode(source['net']); board.Add(via)
                continue
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(vec(source['start'])); track.SetEnd(vec(source['end']))
            track.SetLayer(source['layer']); track.SetNetCode(source['net'])
            track.SetWidth(round(source['width']*1e6)); board.Add(track)
        pcbnew.SaveBoard(str(path), board)
        print(f'Saved {path}; backup {backup}')
        return
    kpython = 'C:/Program Files/KiCad/10.0/bin/python.exe'
    if not args.source:
        report_path = ROOT / f'.codex-tmp/{args.side}-solder-route-regression.drc.json'
        result = subprocess.run(['C:/Program Files/KiCad/10.0/bin/kicad-cli.exe','pcb','drc','--format','json',
            '--refill-zones','--all-track-errors','-o',str(report_path),str(path)],capture_output=True)
        if result.returncode not in (0,5):
            raise RuntimeError(result.stderr)
    export_args = [kpython,'-B','-m','tools.repair_kc2_solder_routes', args.side,'--export']
    if args.source:
        export_args += ['--source',args.source]
    if args.report:
        export_args += ['--report',args.report]
    if args.supports:
        export_args += ['--supports',args.supports]
    subprocess.run(export_args,check=True)
    data = json.loads(model_path.read_text(encoding='utf-8'))
    repair_model(data)
    model_path.write_text(json.dumps(data), encoding='utf-8')
    if args.apply:
        subprocess.run([kpython,'-B','-m','tools.repair_kc2_solder_routes',args.side,'--apply-plan'],check=True)


def model_obstacles(data, net, layer, width, region=None):
    extra = 0.301 + width/2
    shapes = []
    if layer==data['bcu']:
        shapes.extend(Point(s['x_mm'],s['y_mm']).buffer(s['copper_keepout_radius_mm']+width/2+0.002)
                      for s in data.get('supports',[]))
    for p in data['pads']:
        if p['layer']!=layer or (p['net']==net and net):
            continue
        if region is not None and not (region[0]-4 < p['center'][0] < region[2]+4 and region[1]-4 < p['center'][1] < region[3]+4):
            continue
        shapes.append(Polygon(p['polygon']).buffer(extra,quad_segs=8))
    for t in data['tracks']:
        if t['net']==net:
            continue
        if region is not None and (max(t['start'][0],t['end'][0])+extra+t['width']<region[0] or
            min(t['start'][0],t['end'][0])-extra-t['width']>region[2] or
            max(t['start'][1],t['end'][1])+extra+t['width']<region[1] or
            min(t['start'][1],t['end'][1])-extra-t['width']>region[3]):
            continue
        if t['via']:
            shapes.append(Point(t['start']).buffer(t['width']/2+extra))
        elif t['layer']==layer:
            shapes.append(LineString([t['start'],t['end']]).buffer(t['width']/2+extra))
    shapes.extend(LineString(edge).buffer(extra) for edge in data['edges'])
    return unary_union(shapes)


def repair_model(data):
    nodes = defaultdict(list)
    for track in data['tracks']:
        nodes[(track['net'], tuple(track['start']))].append((track,'start'))
        if not track['via']:
            nodes[(track['net'], tuple(track['end']))].append((track,'end'))
    moved = 0
    suspects = set(data['suspects'])
    for track in data['tracks']:
        if track['via'] or track['layer']==data['bcu']:
            shape=Point(track['start']) if track['via'] else LineString([track['start'],track['end']])
            if any(shape.distance(Point(s['x_mm'],s['y_mm'])) < s['copper_keepout_radius_mm']+track['width']/2+0.002
                   for s in data.get('supports',[])):
                suspects.add(track['uuid'])
    for (net,position), attached in nodes.items():
        if not any(t['uuid'] in suspects for t,kind in attached):
            continue
        layers = {}
        for t,kind in attached:
            for layer in (data['fcu'],data['bcu']) if t['via'] else (t['layer'],):
                layers[layer] = max(layers.get(layer,0),t['width'])
        region = (position[0]-2,position[1]-2,position[0]+2,position[1]+2)
        obstacle = unary_union([model_obstacles(data,net,layer,width,region) for layer,width in layers.items()])
        if not obstacle.intersects(Point(position)):
            continue
        if any(p['net']==net and math.dist(p['center'],position)<0.01 for p in data['pads']):
            print(f'Fixed pad retained at {position}; crossing route must move', flush=True)
            continue
        candidates = [(position[0]+r*0.05*math.cos(a*math.tau/64),position[1]+r*0.05*math.sin(a*math.tau/64))
                      for r in range(1,31) for a in range(64)]
        found = next((p for p in candidates if not obstacle.intersects(Point(p))),None)
        if found is None:
            raise RuntimeError(f'Cannot move {position}')
        for t,kind in attached:
            t[kind] = found
            suspects.add(t['uuid'])
            if t['via']:
                t['end'] = found
        moved += 1
        print(f'moved net {net} vertex {position} -> {found}',flush=True)
    print(f'moved {moved} vertices',flush=True)
    for track in list(data['tracks']):
        if track['via'] or track['uuid'] not in suspects:
            continue
        start,end=track['start'],track['end']
        region=(min(start[0],end[0])-10,min(start[1],end[1])-10,max(start[0],end[0])+10,max(start[1],end[1])+10)
        obstacle = model_obstacles(data,track['net'],track['layer'],track['width'],region)
        try:
            path = path_around(track['start'],track['end'],obstacle)
        except RuntimeError as exc:
            if bridge_chain(data,track,region):
                print(f'Bridged expanded net {track["net"]} chain', flush=True)
                continue
            if bridge(data,track,region):
                print(f'Bridged net {track["net"]} to opposite copper', flush=True)
                continue
            print(f'UNRESOLVED: {exc}', flush=True)
            continue
        if len(path)==2:
            continue
        data['tracks'].remove(track)
        for start,end in zip(path,path[1:]):
            data['tracks'].append({**track,'start':start,'end':end})
        print(f'detoured net {track["net"]} via {len(path)-1} segments',flush=True)


def bridge(data,track,region):
    layer = track['layer']
    other = data['fcu'] if layer==data['bcu'] else data['bcu']
    own = model_obstacles(data,track['net'],layer,track['width'],region)
    opposite = model_obstacles(data,track['net'],other,track['width'],region)
    via_obstacle = unary_union([model_obstacles(data,track['net'],l,0.6,region) for l in (layer,other)])
    def endpoints(position):
        options=[position]
        options.extend((position[0]+r*0.2*math.cos(a*math.tau/16),position[1]+r*0.2*math.sin(a*math.tau/16))
                       for r in range(1,26) for a in range(16))
        return [p for p in options if not via_obstacle.intersects(Point(p)) and
                (math.dist(position,p)<1e-6 or not own.intersects(LineString([position,p])))][:12]
    starts,ends=endpoints(track['start']),endpoints(track['end'])
    print(f'bridge candidates {len(starts)} / {len(ends)}',flush=True)
    for start in starts:
        for end in ends:
            try:
                path=path_around(start,end,opposite)
            except RuntimeError:
                continue
            data['tracks'].remove(track)
            for p in (start,end):
                data['tracks'].append({**track,'uuid':str(uuid.uuid4()),'start':p,'end':p,'width':0.6,'via':True,'new':True})
            for a,b in ((track['start'],start),(end,track['end'])):
                if math.dist(a,b)>1e-6:
                    data['tracks'].append({**track,'start':a,'end':b})
            for a,b in zip(path,path[1:]):
                data['tracks'].append({**track,'start':a,'end':b,'layer':other})
            return True
    return False


def bridge_chain(data, track, region):
    chain = [track]
    merged = dict(track)
    for end_name in ('start','end'):
        for _ in range(40):
            position = merged[end_name]
            if any(p['net']==track['net'] and math.dist(p['center'],position)<0.001 for p in data['pads']):
                break
            neighbors=[t for t in data['tracks'] if t not in chain and t['net']==track['net'] and
                       t['layer']==track['layer'] and not t['via'] and
                       (math.dist(t['start'],position)<0.00001 or math.dist(t['end'],position)<0.00001)]
            if len(neighbors)!=1:
                break
            neighbor=neighbors[0]
            chain.append(neighbor)
            merged[end_name]=neighbor['end'] if math.dist(neighbor['start'],position)<0.00001 else neighbor['start']
    if len(chain)==1:
        return False
    for t in chain:
        data['tracks'].remove(t)
    data['tracks'].append(merged)
    print(f'bridge chain {len(chain)} segments: {merged["start"]} -> {merged["end"]}',flush=True)
    if maze_bridge(data,merged):
        return True
    data['tracks'].remove(merged)
    data['tracks'].extend(chain)
    return False


def maze_bridge(data, track):
    start,end=track['start'],track['end']
    step=0.10
    layers=(data['fcu'],data['bcu'])
    region=(min(start[0],end[0])-15,min(start[1],end[1])-15,max(start[0],end[0])+15,max(start[1],end[1])+15)
    obstacles_by_layer={l:prep(model_obstacles(data,track['net'],l,track['width'],region)) for l in layers}
    via_obstacle=prep(unary_union([model_obstacles(data,track['net'],l,0.6,region) for l in layers]))
    print('maze endpoint blocked', obstacles_by_layer[track['layer']].intersects(Point(start)),
          obstacles_by_layer[track['layer']].intersects(Point(end)), flush=True)
    def point(node):
        return (start[0]+node[0]*step,start[1]+node[1]*step)
    initial=(0,0,track['layer'])
    queue=[(math.dist(start,end),0.,initial)]
    costs={initial:0.}
    previous={}
    done=set()
    valid={}
    terminal=None
    while queue:
        _,cost,current=heapq.heappop(queue)
        if current in done:
            continue
        done.add(current)
        p=point(current)
        obs=obstacles_by_layer[current[2]]
        if current[2]==track['layer'] and math.dist(p,end)<2.0 and not obs.intersects(LineString([p,end])):
            terminal=current
            break
        candidates=[(current[0]+dx,current[1]+dy,current[2]) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))]
        other=layers[1] if current[2]==layers[0] else layers[0]
        if not via_obstacle.intersects(Point(p)):
            candidates.append((current[0],current[1],other))
        for target in candidates:
            if target in done:
                continue
            q=point(target)
            if not (region[0]<q[0]<region[2] and region[1]<q[1]<region[3]):
                continue
            is_via=target[2]!=current[2]
            newcost=cost+(1.5 if is_via else math.dist(p,q))
            if newcost>=costs.get(target,float('inf')):
                continue
            if not is_via:
                edge=tuple(sorted((current,target)))
                if edge not in valid:
                    valid[edge]=not obs.intersects(LineString([p,q]))
                if not valid[edge]:
                    continue
            costs[target]=newcost; previous[target]=current
            heapq.heappush(queue,(newcost+math.dist(q,end),newcost,target))
    if terminal is None:
        print(f'maze failed after {len(done)} states',flush=True)
        return False
    states=[terminal]
    while states[-1]!=initial:
        states.append(previous[states[-1]])
    states.reverse()
    runs=[]; run=[start]; layer=track['layer']; vias=[]
    for state in states[1:]:
        p=point(state)
        if state[2]!=layer:
            runs.append((layer,run)); vias.append(p); run=[p]; layer=state[2]
        else:
            run.append(p)
    run.append(end); runs.append((layer,run))
    data['tracks'].remove(track)
    for p in vias:
        data['tracks'].append({**track,'uuid':str(uuid.uuid4()),'start':p,'end':p,'width':0.6,'via':True,'new':True})
    for layer,run in runs:
        i=0
        while i<len(run)-1:
            j=len(run)-1
            while j>i+1 and obstacles_by_layer[layer].intersects(LineString([run[i],run[j]])):
                j-=1
            if math.dist(run[i],run[j])>1e-6:
                data['tracks'].append({**track,'start':run[i],'end':run[j],'layer':layer})
            i=j
    print(f'maze solved {len(done)} states, {len(vias)} vias',flush=True)
    return True


if __name__ == '__main__':
    main()
