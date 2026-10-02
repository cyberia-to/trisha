"""Offline replay of the original remote ZIP and local closure; no proof body reads."""
import copy
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
LANE = BASE / 'whole-retention-remote-readback'
ORIGINAL = LANE / 'local-after-37047053221'
CODE = LANE / 'trisha/scripts/whole_readback'
MIB = 1024**2
CAP = 512*MIB
START = time.monotonic()


def identity(path):
    path = Path(path)
    assert path.stat().st_size <= 256*MIB, 'review never hashes full proof files'
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    return dict(bytes=path.stat().st_size, sha256=digest)


def ref(path):
    return dict(path=str(path), **identity(path))


def load(path):
    return json.loads(Path(path).read_text())


def deny_external(event, args):
    if event in ('subprocess.Popen', 'socket.connect', 'os.kill', 'os.killpg'):
        raise RuntimeError('offline review forbids external actions: '+event)


sys.addaudithook(deny_external)
OUT = ROOT / 'replay-1'
OUT.mkdir()
REPORT = dict(schema='trident/independent-actual-byte-closure-replay/v1', status='running',
              started_ns=time.time_ns(), driver=ref(__file__),
              command=[sys.executable, *sys.argv], cwd=str(Path.cwd()),
              policy=dict(network=False, native_execution=False, host_process_observation=False,
                          full_proof_reads=False, disk_bytes=CAP, wall_seconds=900))


def budget(reserve=0, **kwargs):
    assert type(reserve) is int and reserve >= 0
    total = sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    assert total + reserve <= CAP, 'independent replay disk cap'
    assert time.monotonic() - START <= 900, 'independent replay wall cap'
    REPORT['peak_owned_bytes'] = max(REPORT.get('peak_owned_bytes', 0), total+reserve)


def verify_identity(path, expected):
    assert identity(path) == {k:expected[k] for k in ('bytes','sha256')}, str(path)


try:
    receipt = load(ORIGINAL / 'receipt.json')
    assert identity(ORIGINAL / 'receipt.json')['sha256'] == '2489e9f52e040fb1eea20695bd6b4a9186433a6adb75e429f5b7e131c65d6dcc'
    assert receipt['schema'] == 'trident/local-remote-byte-closure/v2'
    assert receipt['status'] == 'byte-equivalent-transport-adopted-remote-replay'
    assert not any(k in receipt for k in ('error','cleanup_error','terminal_evidence_error'))
    source_map = load(LANE / 'trisha/.github/whole-readback-sources.json')
    assert identity(LANE / 'trisha/.github/whole-readback-sources.json')['sha256'] == '31e45b9a4875ae7e6e1c7c14026fab8ff0db63cb21db6a6797111f595661735e'
    for name, wanted in source_map.items():
        verify_identity(LANE / 'trisha' / name, wanted)
    review = BASE / 'whole-retention-remote-readback-independent/activation-9779559/independent-review.json'
    verify_identity(review, receipt['review'])
    assert load(review)['status'] == 'passed-source-review' and load(review)['sources'] == source_map
    assert receipt['sources'] == source_map
    REPORT.update(closure=ref(ORIGINAL / 'receipt.json'), source_manifest=ref(LANE / 'trisha/.github/whole-readback-sources.json'), source_review=ref(review))
    sys.path.insert(0, str(CODE))
    import gate
    import result
    import recorded
    import local_admission
    from common import check_asset, REPO, RELEASE
    selected, expected, prepared = gate.frozen()
    assert gate.sources() == source_map
    assert receipt['before']['prepared'] == receipt['after']['prepared'] == prepared
    before_path = LANE / 'local-before-9779559/before.json'
    after_path = ORIGINAL / 'after.json'
    assert load(before_path) == receipt['before'] and load(after_path) == receipt['after']
    local_admission.compare(receipt['before'], receipt['after'])
    for observed in (receipt['before'], receipt['after']):
        assert observed['worker_sources'] == source_map
        assert observed['source_manifest'] == identity(gate.MANIFEST)
        assert observed['independent_review'] == receipt['review']
    REPORT['local_scan_refs'] = dict(before=ref(before_path), after=ref(after_path))
    # Copy only bounded original command outputs into an isolated replay scope.
    commands = receipt['commands']
    assert len(commands) == len({r['name'] for r in commands}) == 50
    assert all(a['ended_ns'] <= b['started_ns'] for a,b in zip(commands,commands[1:]))
    copied = {}
    for row in commands:
        for channel in ('stdout','stderr'):
            original = Path(row[channel+'_path'])
            assert original.parent == ORIGINAL
            verify_identity(original, row[channel])
            destination = OUT / original.name
            assert destination.name not in copied
            budget(row[channel]['bytes'])
            shutil.copyfile(original,destination)
            copied[destination.name] = row[channel]
    # Preserve source API semantics, replacing transport with exact recorded observations.
    original_for_replay = copy.deepcopy(receipt)
    original_for_replay['gh'] = prepared['gh']
    transport = recorded.Recorded(OUT, original_for_replay, budget)
    transport.draft('initial')
    admitted = result.admit(transport, 37047053221, '97795590613e625b6be43c5e73afff4ab87009cd')
    assert admitted == receipt['admitted_remote'], 'independently replayed original result differs'
    job = admitted['jobs']['jobs'][0]
    assert job['id'] == 110970969490
    assert admitted['artifact']['id'] == 11245008879
    def ns(value):
        return int(datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*10**9)
    assert receipt['before']['ended_ns'] < ns(job['started_at'])
    assert receipt['after']['started_ns'] > ns(job['completed_at'])
    assert receipt['started_ns'] <= receipt['after']['started_ns'] <= receipt['after']['ended_ns'] <= receipt['ended_ns']
    worker = load(OUT / 'evidence/receipt.json')
    packing = load(OUT / 'packing.json')
    REPORT['remote'] = dict(run=worker['worker'], artifact=admitted['artifact']['id'],
                           original_zip=admitted['original_zip'], worker_receipt=ref(ORIGINAL / 'evidence/receipt.json'),
                           packing=ref(ORIGINAL / 'packing.json'), commands=len(worker['commands']),
                           parts=len(admitted['checked']['body_commands']), generations=[dict(generation=e['generation'],proof=e['proof'],parts=len(e['parts'])) for e in worker['entries']],
                           elapsed_seconds=worker['elapsed_monotonic_seconds'], sampled_peak_rss_bytes=worker['sampled_peak_rss_bytes'],
                           archive_members=len(packing['members']), decoded_bytes=sum(v['bytes'] for v in packing['members'].values()))
    assert worker == load(ORIGINAL / 'evidence/receipt.json')
    assert len(worker['commands']) == 356 and len(admitted['checked']['body_commands']) == 22
    for e, local_entry in zip(worker['entries'], prepared['admitted']['entries']):
        assert e['generation'] == local_entry['generation']
        assert e['proof'] == {k:local_entry['proof'][k] for k in ('bytes','sha256')}
        assert e['downloaded_reconstruction'] == e['proof']
    # Re-authenticate the two unique local publication observations and exact readback files.
    uploaded = []
    for label, original_name, key in [('original-local-metadata','original-local-metadata.tar.gz','retained_original_metadata'),('equivalence','equivalence.json','equivalence')]:
        pointer = receipt[key];wanted={k:pointer[k] for k in ('bytes','sha256')};asset=pointer['asset']
        verify_identity(ORIGINAL/original_name,wanted)
        assert wanted['bytes'] <= 32*MIB
        old_assets = transport.draft(label+'-before')
        assert asset['name'] not in {a['name'] for a in old_assets}
        row = transport.rows[label+'-upload']
        endpoint=f'https://uploads.github.com/repos/{REPO}/releases/{RELEASE}/assets?name='+quote(asset['name'],safe='')
        assert row['command']==[prepared['gh']['path'],'api','--method','POST',endpoint,'-H','Content-Type: application/octet-stream','--input',str(ORIGINAL/original_name)]
        assert row['expected_exit']==row['exit_code']==0 and row['timeout_seconds']==1800 and row['stdout_limit']==8*MIB
        assert 0<=row['elapsed_seconds']<=1830 and receipt['after']['ended_ns']<=row['started_ns']<=row['ended_ns']<=receipt['ended_ns']
        assert not any(k in row for k in ('error','cleanup_error','normal_persist_error','terminal_evidence_error'))
        assert row['cleanup'].get('status')=='leader-complete' or row['cleanup'].get('group_empty') is True
        uploaded_asset=load(OUT/(label+'-upload.stdout'))
        check_asset(uploaded_asset,asset['name'],wanted)
        assert all(uploaded_asset[k]==v for k,v in asset.items())
        transport.used.append(label+'-upload')
        new_assets=transport.draft(label+'-after')
        matches=[a for a in new_assets if a['name']==asset['name']]
        assert len(matches)==1 and matches[0]['id']==asset['id']
        check_asset(matches[0],asset['name'],wanted)
        body=transport.download(label+'-readback',asset,wanted)
        verify_identity(body,wanted)
        uploaded.append(dict(label=label,asset_id=asset['id'],name=asset['name'],identity=wanted,independently_downloaded=True))
    transport.draft('final')
    assert len(transport.used)==len(set(transport.used))==50 and set(transport.used)==set(transport.rows)
    assert transport.baseline==receipt['default_ref']
    assert len({e['asset_id'] for e in uploaded})==2
    manifest=load(ORIGINAL/'equivalence.json')
    assert manifest['schema']=='trident/local-remote-certificate-byte-equivalence/v2'
    assert manifest['scope']==receipt['scope']
    assert manifest['local_closure_sources']==source_map
    assert manifest['local']['before']==dict(identity=identity(before_path),observation=receipt['before'])
    assert manifest['local']['after']==dict(identity=identity(after_path),observation=receipt['after'])
    assert manifest['local']['preparation']==receipt['before']['local_preparation']
    assert manifest['local']['entries']==prepared['admitted']['entries']
    assert manifest['local']['source_revisions']==prepared['admitted']['source_revisions']
    assert manifest['local']['binary']==prepared['admitted']['binary']
    assert manifest['local']['original_metadata']==receipt['retained_original_metadata']
    assert manifest['remote_body_replay']==admitted and manifest['worker_observation']==worker and manifest['packing_observation']==packing
    assert manifest['original_remote_proof']==dict(run=expected['run'],entries=admitted['checked']['entries'])
    assert receipt['retained_original_metadata']['sha256']==selected['original_metadata']['sha256']
    REPORT.update(local_commands=50,retained_assets=uploaded,default_ref=transport.baseline,
                  source_and_original_receipt_unchanged=True,
                  scope='Authenticated retained original Actions ZIP, 356 GET observations including22 complete body observations, two ordered whole hashes, local before/after scan receipts and50 closure operations including unique fixed-draft assets with actual independent readbacks. No new network, proof reread or native workload. Full body equality follows the authenticated remote worker and prior local scans; this offline audit does not substitute a new body scan or SH8 acceptance.')
    assert gate.sources()==source_map
    assert identity(ORIGINAL/'receipt.json')=={k:REPORT['closure'][k] for k in ('bytes','sha256')}
    REPORT['status']='passed-actual-retained-byte-closure-review'
except BaseException:
    REPORT.update(status='failed-review',error=traceback.format_exc())
    raise
finally:
    REPORT.update(ended_ns=time.time_ns(),elapsed_seconds=time.monotonic()-START)
    with (ROOT/'receipt.json').open('x') as output:
        json.dump(REPORT,output,indent=2);output.write('\n')
    print(json.dumps(dict(status=REPORT['status'],receipt=ref(ROOT/'receipt.json'))))
