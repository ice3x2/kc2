"""CON-ARCH-004/006, OPS-ARCH-007 read-only current-board/output evidence.

Run with Python3.12+Shapely; invokes installed KiCad Python only to read boards.
Writes evidence beside this script, never changes hardware or release outputs.
"""
import hashlib,json,math,re,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
RAW=ROOT/'hardware/kicad/fabrication_review/v1-recess-20260906-r3'
MASK_SUFFIX={'F':'F_Mask.gts','B':'B_Mask.gbs'}
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def extract():
    import pcbnew
    sys.path.insert(0,str(ROOT))
    from tools.kc2_solder_route_snapshot import capture
    snapshot=json.loads((ROOT/'hardware/kicad/autoroute/kc2_mx_solder_support_routes.json').read_text())
    result={}
    for side in ('left','right'):
        path=ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
        board=pcbnew.LoadBoard(str(path))
        record=dict(vias=[],tracks=[],pads=[],switch_polygons=[],replay_matches=capture(board)==snapshot['sides'][side])
        for track in board.GetTracks():
            if isinstance(track,pcbnew.PCB_VIA):
                record['vias'].append(dict(center=[track.GetPosition().x/1e6,track.GetPosition().y/1e6],diameter=track.GetWidth(pcbnew.F_Cu)/1e6,drill=track.GetDrillValue()/1e6,net=track.GetNetname()))
            else:
                record['tracks'].append(dict(start=[track.GetStart().x/1e6,track.GetStart().y/1e6],end=[track.GetEnd().x/1e6,track.GetEnd().y/1e6],width=track.GetWidth()/1e6,layer=pcbnew.LayerName(track.GetLayer()),net=track.GetNetname()))
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                record['pads'].append(dict(reference=fp.GetReference(),number=pad.GetNumber(),center=[pad.GetPosition().x/1e6,pad.GetPosition().y/1e6],net=pad.GetNetname(),npth=pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH))
                if str(fp.GetFPID().GetLibItemName())=='SW_Choc_V2_Socket_MX_THT' and (pad.GetAttribute()==pcbnew.PAD_ATTRIB_PTH or (pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH and abs(pad.GetDrillSize().x/1e6-2.6)<1e-6)):
                    poly=pcbnew.SHAPE_POLY_SET(); pad.TransformShapeToPolygon(poly,pcbnew.F_Cu,0,100,pcbnew.ERROR_OUTSIDE)
                    p=poly.Outline(0)
                    record['switch_polygons'].append(dict(reference=fp.GetReference(),pad=pad.GetNumber(),points=[[p.CPoint(j).x/1e6,p.CPoint(j).y/1e6] for j in range(p.PointCount())]))
        result[side]=record
    (OUT/'current-board-extraction.json').write_text(json.dumps(result,indent=2),encoding='utf8')

def mask_flashes(path):
    from shapely.geometry import Point,LineString,Polygon,box
    from shapely.affinity import translate
    text=path.read_text(encoding='ascii')
    assert '%MOMM*%' in text and '%FSLAX46Y46*%' in text
    assert not re.search(r'D01\*|G36\*|%LPC|%(?:LR|LM|LS)',text),'Unsupported mask primitives'
    macros={name:[p.strip() for p in body.split('*') if p.strip() and not p.strip().startswith('0 ')] for name,body in re.findall(r'%AM(\w+)\*([^%]*)%',text)}
    oval=['20,1,$1,$2,$3,$4,$5,0','1,1,$1,$2,$3','1,1,$1,$4,$5']
    rounded=['4,1,4,$2,$3,$4,$5,$6,$7,$8,$9,$2,$3,0',
             '1,1,$1+$1,$2,$3','1,1,$1+$1,$4,$5','1,1,$1+$1,$6,$7','1,1,$1+$1,$8,$9',
             '20,1,$1+$1,$2,$3,$4,$5,0','20,1,$1+$1,$4,$5,$6,$7,0','20,1,$1+$1,$6,$7,$8,$9,0','20,1,$1+$1,$8,$9,$2,$3,0']
    apertures={}
    for code,kind,params in re.findall(r'%ADD(\d+)(\w+),([^*]+)\*%',text):
        v=list(map(float,params.split('X')))
        if kind=='C' and len(v)==1: shape=Point(0,0).buffer(v[0]/2,quad_segs=256)
        elif kind=='R' and len(v)==2: shape=box(-v[0]/2,-v[1]/2,v[0]/2,v[1]/2)
        elif kind=='O' and len(v)==2:
            w,h=v; e=abs(w-h)/2
            shape=LineString([(-e,0),(e,0)] if w>=h else [(0,-e),(0,e)]).buffer(min(v)/2,quad_segs=256)
        elif macros.get(kind)==oval and len(v)==6 and v[-1]==0:
            shape=LineString([(v[1],-v[2]),(v[3],-v[4])]).buffer(v[0]/2,quad_segs=256)
        elif macros.get(kind)==rounded and len(v)==10 and v[-1]==0:
            shape=Polygon([(v[i],-v[i+1]) for i in (1,3,5,7)]).buffer(v[0],quad_segs=256)
        else: raise ValueError(f'Unsupported actual aperture {kind} {params}')
        apertures[int(code)]=shape
    active=None;ref='';result=[]
    for line in text.splitlines():
        m=re.fullmatch(r'D(\d+)\*',line)
        if m: active=int(m[1]);continue
        m=re.fullmatch(r'%TO\.C,([^*]+)\*%',line)
        if m: ref=m[1];continue
        if line=='%TD*%': ref='';continue
        m=re.fullmatch(r'X(-?\d+)Y(-?\d+)D03\*',line)
        if m:
            center=(int(m[1])/1e6,-int(m[2])/1e6)
            result.append(dict(reference=ref,center=center,shape=translate(apertures[active],*center)))
    assert len(result)==text.count('D03*'),'Unparsed mask flash'
    return result

def main():
    from shapely.geometry import Point,LineString,Polygon
    inputs=[Path(__file__),ROOT/'hardware/kicad/autoroute/kc2_mx_solder_support_routes.json',ROOT/'tools/kc2_solder_route_snapshot.py',ROOT/'tools/finalize_kc2_x3_v2_routes.py',OUT/'original-support-keepouts.json']
    inputs += [ROOT/f'hardware/kicad/kc2_{s}/kc2_{s}.{ext}' for s in ('left','right') for ext in ('kicad_pcb','kicad_pro','drc.json')]
    inputs += [RAW/s/f'kc2_{s}-{MASK_SUFFIX[l]}' for s in ('left','right') for l in ('F','B')]
    before={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in inputs}
    subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe','-B',str(Path(__file__)),'--extract'],check=True)
    boards=json.loads((OUT/'current-board-extraction.json').read_text())
    supports=json.loads((OUT/'original-support-keepouts.json').read_text())['sides']
    result=dict(requirements=['CON-ARCH-004','CON-ARCH-006','OPS-ARCH-007'],source_sha256=before,errors=[],sides={})
    for side,board in boards.items():
        r=dict(via_count=len(board['vias']),replay_matches=board['replay_matches'],mask_checks={},support_copper_violations=[],minimum_locator_to_mx_copper_mm=999)
        if not r['replay_matches']:result['errors'].append(side+' replay mismatch')
        for layer in ('F','B'):
            flashes=mask_flashes(RAW/side/f'kc2_{side}-{MASK_SUFFIX[layer]}')
            overlaps=[];isolated=0
            for via in board['vias']:
                copper=Point(via['center']).buffer(via['diameter']/2,quad_segs=256)
                hits=[]
                for flash in flashes:
                    if not flash['shape'].intersects(copper):continue
                    pads=[p for p in board['pads'] if p['reference']==flash['reference'] and math.dist(p['center'],flash['center'])<.0001]
                    same=bool(pads) and all(p['net']==via['net'] and not p['npth'] for p in pads)
                    hits.append(dict(reference=flash['reference'],pad_numbers=[p['number'] for p in pads],pad_nets=[p['net'] for p in pads],same_net=same,mask_overlap_area_mm2=flash['shape'].intersection(copper).area,drill_open_area_mm2=flash['shape'].intersection(Point(via['center']).buffer(via['drill']/2,quad_segs=256)).area))
                    if not same:result['errors'].append(f'{side} {layer} non-same-net mask/via {via["center"]}')
                if hits:overlaps.append(dict(**via,hits=hits))
                else:isolated+=1
            r['mask_checks'][layer]=dict(flash_count=len(flashes),fully_mask_covered_vias=isolated,overlaps=overlaps)
        for support in supports[side]:
            for track in board['tracks']+[dict(start=v['center'],end=v['center'],width=v['diameter'],layer='B.Cu') for v in board['vias']]:
                if track['layer']!='B.Cu':continue
                shape=LineString([track['start'],track['end']]) if track['start']!=track['end'] else Point(track['start'])
                margin=shape.distance(Point(support['x_mm'],support['y_mm']))-track['width']/2-support['copper_keepout_radius_mm']
                if margin<-.00001:r['support_copper_violations'].append(dict(support=support['switch_ref'],margin_mm=margin))
        if r['support_copper_violations']:result['errors'].append(side+' original support copper conflict')
        for ref in set(p['reference'] for p in board['switch_polygons']):
            holes=[Polygon(p['points']) for p in board['switch_polygons'] if p['reference']==ref and not p['pad']]
            pads=[Polygon(p['points']) for p in board['switch_polygons'] if p['reference']==ref and p['pad']]
            r['minimum_locator_to_mx_copper_mm']=min(r['minimum_locator_to_mx_copper_mm'],min(h.distance(p) for h in holes for p in pads))
        if r['minimum_locator_to_mx_copper_mm']<.30:result['errors'].append(side+' locator copper clearance')
        drcpath=ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.drc.json'
        drc=json.loads(drcpath.read_text())
        if drc['violations'] or drc['unconnected_items']:result['errors'].append(side+' DRC not empty')
        (OUT/f'{side}-canonical-drc.json').write_bytes(drcpath.read_bytes())
        result['sides'][side]=r
    assert before=={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in inputs},'Inputs changed during audit'
    result['generated_evidence_sha256']={p.name:sha(p) for p in [OUT/'current-board-extraction.json',OUT/'left-canonical-drc.json',OUT/'right-canonical-drc.json']}
    (OUT/'mask-via-support-replay-audit.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    extract() if '--extract' in sys.argv else main()
