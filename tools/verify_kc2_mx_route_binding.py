"""CON-ARCH-004/006: bind final MX routing to an exact pad-gated replay artifact."""
import json
from pathlib import Path
from tools.canonical_hash import sha256_file
from tools.kc2_solder_route_snapshot import SCHEMA, capture

ROOT = Path(__file__).resolve().parents[1]
REPLAY = 'hardware/kicad/autoroute/kc2_mx_solder_support_routes.json'


def verify_mx_route_binding(manifest, board, side):
    binding = manifest.get('mx_solder_route_replay')
    if not isinstance(binding, dict) or binding.get('path') != REPLAY:
        return [f'{side}: current MX routing replay binding is missing or noncanonical']
    try:
        path = ROOT/REPLAY
        if binding.get('sha256') != sha256_file(path):
            return [f'{side}: MX routing replay SHA-256 mismatch']
        payload = json.loads(path.read_text(encoding='utf-8'))
        if payload.get('schema') != SCHEMA or payload.get('order_ready') is not False or payload.get('requirements') != ['CON-ARCH-004', 'CON-ARCH-006']:
            return [f'{side}: MX routing replay schema/provenance is invalid']
        if payload.get('sides', {}).get(side) != capture(board):
            return [f'{side}: current physical pads or routing differ from the complete MX replay snapshot']
    except (OSError, ValueError, TypeError, KeyError) as error:
        return [f'{side}: MX routing replay cannot be verified: {error}']
    return []
