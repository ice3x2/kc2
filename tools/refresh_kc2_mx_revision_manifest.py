"""CON-ARCH-004/006/007 incremental metadata; preserve historical DSN/SES provenance.

This does not regenerate boards or fabrication outputs. The current pad/routing
snapshot must already match both boards. Default is read-only; --apply backs up.
"""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import pcbnew
from tools.canonical_hash import sha256_file
from tools.generate_kc2_pcbs import x3_v2_switch_assembly_contract
from tools.verify_kc2_mx_route_binding import REPLAY, verify_mx_route_binding

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'hardware/kicad/kc2_generation_manifest.json'


def build_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    manifest.update(x3_v2_switch_assembly_contract())
    manifest['canonical_route_evidence_role'] = 'historical_pre_mx_revision_base_only'
    manifest['mx_solder_route_replay'] = {'path': REPLAY, 'sha256': sha256_file(ROOT/REPLAY)}
    hashes = {}
    for side in ('left', 'right'):
        path = ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
        errors = verify_mx_route_binding(manifest, pcbnew.LoadBoard(str(path)), side)
        if errors:
            raise ValueError('; '.join(errors))
        hashes[side] = sha256_file(path)
    service = manifest['controller_service_region']
    service['battery']['socket_pad_clearance_mm'] = .42
    service['nominal_clearances_mm']['battery_to_socket_pad'] = .42
    service['nominal_clearances_mm']['reset_courtyard_to_u1_socket_copper_min'] = 1.73
    manifest['mx_revision'] = {
        'date': '2026-09-06',
        'method': 'incremental_pad_mask_and_support_aware_routing_revision',
        'metadata_generator': 'tools/refresh_kc2_mx_revision_manifest.py',
        'metadata_generator_sha256': sha256_file(Path(__file__)),
        'pcb_generator_sha256': sha256_file(ROOT/'tools/generate_kc2_pcbs.py'),
        'replay_tool_sha256': sha256_file(ROOT/'tools/kc2_solder_route_snapshot.py'),
        'metadata_command': 'python -B -m tools.refresh_kc2_mx_revision_manifest --apply',
        'source_board_sha256': hashes,
        'baseline_generated': manifest['generated'],
        'fabrication_and_physical_qualification': 'pending_not_regenerated_by_metadata_refresh',
    }
    notes = manifest.get('notes', [])
    marker = '2026-09-06 incremental MX revision:'
    notes = [note for note in notes if not str(note).startswith(marker)]
    notes.append(marker + ' selected dimensional open-bottom receptacles + plate-lid; '
                 'enlarged exposed U1/MX lands and support-aware replay. Previous notes, '
                 'generated date and DSN/SES record describe the historical base only. '
                 'Current final routes are bound by mx_solder_route_replay. No order approval.')
    manifest['notes'] = notes
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    manifest = build_manifest()
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = ROOT/'.codex-tmp'/f'kc2_generation_manifest-before-mx-{stamp}.json'
        shutil.copy2(MANIFEST, backup)
        MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        print('backup:', backup)
    print(json.dumps({'written': args.apply, 'mx_revision': manifest['mx_revision']}, indent=2))


if __name__ == '__main__':
    main()
