"""CON-ARCH-006 source-bound selection of regenerated lower native readback."""
def native_output(record,side,variant,generation_sha,source_sha):
    key=f'lower:{side}:{variant}'
    if record.get('status')!='pass' or record.get('selected_job')!=key:raise ValueError('Native job identity/status')
    row=record.get('outputs',{}).get(key,{})
    if row.get('round_trip_verified') is not True or row.get('generation_sha256')!=generation_sha or row.get('source_sha256')!=source_sha:
        raise ValueError('Stale or incomplete native source')
    if row.get('expected_body_count')!=(1 if side=='left' else 2):raise ValueError('Native body count')
    for field in ['readback_step','readback_sha256','f3d','f3d_sha256']:
        if not isinstance(row.get(field),str) or not row[field]:raise ValueError('Missing native artifact')
    return row
