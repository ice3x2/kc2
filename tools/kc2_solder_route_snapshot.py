"""CON-ARCH-004/006 reviewed routing replay, gated by exact physical pad identity.

Run with KiCad Python. Capture is a development artifact, never order approval.
The restore function mutates only in-memory tracks/vias after verifying the
complete pad fingerprint. Callers retain responsibility for save backups/DRC.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import pcbnew

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'hardware/kicad/autoroute/kc2_mx_solder_support_routes.json'
SCHEMA=2


def xy(point):
    return [point.x,point.y]


def pad_fingerprint(board):
    records=[]
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            records.append([footprint.GetReference(),pad.GetNumber(),pad.GetNetname(),
                xy(pad.GetPosition()),xy(pad.GetSize()),xy(pad.GetDrillSize()),
                int(pad.GetShape()),int(pad.GetAttribute()),pad.GetOrientation().AsDegrees(),
                list(pad.GetLayerSet().Seq()),pad.GetLocalSolderMaskMargin(),
                footprint.GetLocalSolderMaskMargin(),
                pad.GetSolderMaskExpansion(pcbnew.F_Mask),
                pad.GetSolderMaskExpansion(pcbnew.B_Mask)])
    payload=json.dumps(sorted(records,key=lambda p:json.dumps(p)),ensure_ascii=True,separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def capture(board):
    from tools.finalize_kc2_x3_v2_routes import _route_counter_digest, _route_signature
    tracks=[]
    for track in board.GetTracks():
        if track.GetClass() not in ('PCB_TRACK','PCB_VIA'):
            raise ValueError(f'unsupported route item {track.GetClass()}; no silent arc conversion')
        if isinstance(track,pcbnew.PCB_VIA):
            record={'kind':'via','net':track.GetNetname(),'position_iu':xy(track.GetPosition()),
                'diameter_iu':track.GetWidth(pcbnew.F_Cu),'drill_iu':track.GetDrillValue(),
                'type':int(track.GetViaType()),'top_layer':track.TopLayer(),'bottom_layer':track.BottomLayer()}
        else:
            record={'kind':'track','net':track.GetNetname(),'start_iu':xy(track.GetStart()),'end_iu':xy(track.GetEnd()),
                'width_iu':track.GetWidth(),'layer':track.GetLayer()}
        tracks.append(record)
    return {'pad_fingerprint_sha256':pad_fingerprint(board),
            'route_track_via_count':len(tracks),
            'route_digest_sha256':_route_counter_digest(Counter(_route_signature(t) for t in board.GetTracks())),
            'tracks':sorted(tracks,key=lambda t:json.dumps(t,sort_keys=True))}


def restore(board, snapshot):
    if pad_fingerprint(board)!=snapshot['pad_fingerprint_sha256']:
        raise ValueError('Physical pad fingerprint differs; routing snapshot cannot be replayed')
    for item in snapshot['tracks']:
        if not isinstance(item,dict) or item.get('kind') not in ('track','via'):
            kind=item.get('kind') if isinstance(item,dict) else type(item).__name__
            raise ValueError(f'unsupported snapshot route kind {kind}')
    nets={item.GetNetname():item.GetNetCode() for item in board.GetNetInfo().NetsByNetcode().values()}
    missing={item['net'] for item in snapshot['tracks']}-nets.keys()
    if missing:
        raise ValueError(f'Unknown snapshot nets: {sorted(missing)}')
    for track in board.GetTracks():
        if track.GetClass() not in ('PCB_TRACK','PCB_VIA'):
            raise ValueError(f'unsupported route item {track.GetClass()}; replay refuses to delete it')
    for track in list(board.GetTracks()):
        board.Delete(track)
    for item in snapshot['tracks']:
        if item['kind']=='via':
            track=pcbnew.PCB_VIA(board)
            track.SetPosition(pcbnew.VECTOR2I(*item['position_iu']))
            track.SetViaType(item['type']); track.SetLayerPair(item['top_layer'],item['bottom_layer'])
            track.SetWidth(item['diameter_iu']); track.SetDrill(item['drill_iu'])
        else:
            track=pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(*item['start_iu'])); track.SetEnd(pcbnew.VECTOR2I(*item['end_iu']))
            track.SetLayer(item['layer']); track.SetWidth(item['width_iu'])
        track.SetNetCode(nets[item['net']]); board.Add(track)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args()
    payload={'schema':SCHEMA,'requirements':['CON-ARCH-004','CON-ARCH-006'],
        'purpose':'Enlarged solder-land and housing-support routing replay; not fabrication evidence',
        'order_ready':False,'sides':{}}
    for side in ('left','right'):
        path=ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
        payload['sides'][side]=capture(pcbnew.LoadBoard(str(path)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(args.output)


if __name__=='__main__':
    main()
