"""Offline replay of original positive Linux evidence; never execute archived code."""
import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CONTRACT = ROOT / 'replay-contract'


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(path):
    require(path.is_file() and not path.is_symlink(), 'regular retained file')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(bytes=path.stat().st_size, sha256=digest)


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'unique JSON keys')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def same(path, expected):
    require(identity(path) == {k: expected[k] for k in ('bytes', 'sha256')}, 'identity: ' + str(path))


def source_gate():
    same(CONTRACT/'adoption-independent-review.json', dict(bytes=9500, sha256=
         'ac75f6e0112c7907faf1158f123fabe62fce4ed43bcc0aa70d51916acd8feac6'))
    same(CONTRACT/'adoption-sources.json', dict(bytes=2192, sha256=
         'a9be736fee399466967e56c7d077faf978b1f1c131b235a226cc74101b2d5305'))
    same(CONTRACT/'adoption-root-final-review.json', dict(bytes=1668, sha256=
         '85fdfa51a80e8f55ff2f0711cc28ccf5e8c9526f57801471b3bcda2834f52786'))
    reviewed = load(CONTRACT/'adoption-independent-review.json')
    require(reviewed['status'] == 'passed-source-review' and
            reviewed['sources'] == load(CONTRACT/'adoption-sources.json'), 'reviewed helper provenance')
    names = ('common.py', 'contracts.py', 'archives.py', 'evidence.py', 'remote.py',
             'expected.json', 'local-preparation.json')
    for name in names:
        same(CONTRACT/name, reviewed['sources'][name])
    sys.path.insert(0, str(CONTRACT))


def archive(name, collected, destination=None):
    import archives
    path = ROOT/'raw'/(name+'.zip')
    row = collected['archives'][name]
    same(path, row)
    wanted = collected['extracted'][name]
    archives.zip_preflight(path)
    actual = {}
    seen = set()
    with zipfile.ZipFile(path) as stream:
        members = stream.infolist()
        require(len(members) <= 10000 and sum(m.file_size for m in members) <= 128*1024**2,
                'bounded original archive')
        for member in members:
            name = member.filename.removesuffix('/') if member.is_dir() else member.filename
            archives.safe(name)
            require(name not in seen and stat.S_IFMT(member.external_attr >> 16) in
                    (0, stat.S_IFREG, stat.S_IFDIR), 'unique regular archive path')
            seen.add(name)
            if member.is_dir():
                continue
            require(name not in actual and member.file_size <= 32*1024**2, 'unique bounded member')
            with stream.open(member) as body:
                digest = hashlib.file_digest(body, 'sha256').hexdigest()
            actual[name] = dict(bytes=member.file_size, sha256=digest)
    require(actual == wanted, 'complete original archive member inventory')
    if destination is not None:
        result = archives.extract_zip(path, destination, lambda size: require(size <= 128*1024**2, 'expansion cap'))
        require(result == actual, 'actual extracted member identities')
    return actual


def collection():
    import contracts
    raw = ROOT/'raw'
    collected = load(raw/'receipt.json')
    require(collected['status'] == 'passed' and collected['conclusion'] == 'success', 'successful evidence collection')
    same(ROOT/'collect.py', collected['collector'])
    run, jobs, listing = (load(raw/(n+'.json')) for n in ('run', 'jobs', 'artifacts'))
    contracts.admit_run(run, jobs)
    require(collected['run'] == contracts.RUN and collected['expected_head'] == contracts.HEAD, 'exact collection run')
    names = {f'whole-v2-{phase}-c{g}-1' for g in (1, 2) for phase in ('producer', 'verifier', 'pending')}
    require(listing['total_count'] == len(listing['artifacts']) == 6 and
            {a['name'] for a in listing['artifacts']} == names and
            set(collected['archives']) == set(collected['extracted']) == names | {'run-logs'},
            'all six original Actions artifacts and logs')
    require(len({a['id'] for a in listing['artifacts']}) == 6, 'distinct original artifacts')
    require(sum(a['size_in_bytes'] for a in listing['artifacts']) <= 256*1024**2, 'bounded original metadata archives')
    labels = {a['id']: a['name'] for a in listing['artifacts']}
    for value in listing['artifacts']:
        row = collected['archives'][value['name']]
        require(row['metadata'] == value, 'exact authenticated artifact listing')
        same(raw/(value['name']+'.zip'), contracts.artifact(value, value['name']))
    endpoints = [f'repos/cyberia-to/trisha/actions/runs/{contracts.RUN}',
                 f'repos/cyberia-to/trisha/actions/runs/{contracts.RUN}/jobs?per_page=100',
                 f'repos/cyberia-to/trisha/actions/runs/{contracts.RUN}/artifacts?per_page=100',
                 *[f'repos/cyberia-to/trisha/actions/artifacts/{v["id"]}/zip' for v in listing['artifacts']],
                 f'repos/cyberia-to/trisha/actions/runs/{contracts.RUN}/logs']
    require([r['command'] for r in collected['commands']] == [['gh', 'api', endpoint] for endpoint in endpoints],
            'exact read-only collection commands')
    for row, endpoint in zip(collected['commands'], endpoints):
        require(row['exit_code'] == 0, 'collection command success')
        label = ('artifacts' if '/artifacts?' in endpoint else 'jobs' if '/jobs?' in endpoint
                 else 'run-logs' if endpoint.endswith('/logs') else 'run')
        if '/actions/artifacts/' in endpoint:
            label = labels[int(endpoint.split('/')[-2])]
        suffix = '.zip' if label == 'run-logs' or label.startswith('whole-v2-') else '.json'
        same(raw/(label+suffix), row['stdout'])
        same(raw/(label+'.stderr'), row['stderr'])
    return collected


def generation(root, expected, entry):
    import contracts
    import evidence
    import remote
    g = entry['generation']
    pdir, vdir, hdir = (root/f'whole-v2-{phase}-c{g}-1' for phase in ('producer', 'verifier', 'pending'))
    p, pc = evidence.phase(pdir, expected, entry, 'producer')
    v, vc = evidence.phase(vdir, expected, entry, 'verifier')
    require(pc['started_ns']+pc['elapsed_ns'] <= vc['started_ns'], 'fresh verifier follows producer')
    pointer = p['pending']
    require(pointer == v['pending'] == load(pdir/'handoff/pointer.json') ==
            load(hdir/'pointer.json') == load(vdir/'pending-pointer.json'), 'identical original handoff')
    require(pointer['schema'] == 'trident/whole-proof-handoff/v2' and pointer['status'] == 'pending-fresh-verification'
            and pointer['run'] == expected['run'] and pointer['generation'] == g, 'explicit pending original provenance')
    require({x.name for x in hdir.iterdir()} == {'pending.json', 'pointer.json'}, 'exact handoff archive')
    for path in (pdir/'handoff/pending.json', hdir/'pending.json', vdir/'pending.json'):
        same(path, pointer['manifest'])
    pending = contracts.pending_manifest(load(hdir/'pending.json'), expected, entry)
    same(vdir/'completion.json', v['completion'])
    complete = contracts.completion_manifest(load(vdir/'completion.json'), expected, entry, pointer, pending)
    require(pending['producer_receipt'] == identity(pdir/'producer-receipt.json') and
            pending['producer_binary'] == p['binary'] and pending['producer_tools'] == p['tools'] and
            pending['production'] == p['production'], 'pending actual producer coordinates')
    require(complete['verifier_receipt'] == identity(vdir/'verifier-receipt.json') and
            complete['verifier_binary'] == v['binary'] and complete['verifier_tools'] == v['tools'] and
            complete['verification'] == v['verification'], 'completion actual verifier coordinates')
    assets = [(a['asset'], contracts.ident(a)) for a in pending['parts']]
    assets += [(pending['metadata']['asset'], contracts.ident(pending['metadata'])),
               (pointer['asset'], pointer['manifest']), (complete['metadata']['asset'], contracts.ident(complete['metadata'])),
               (v['completion']['asset'], contracts.ident(v['completion']))]
    remote.transport_receipts(pdir, p, assets)
    remote.transport_receipts(vdir, v, assets)
    return dict(generation=g, proof=contracts.ident(entry['proof']), compiled=v['compiled'],
                produce_elapsed_ns=pc['elapsed_ns'], verify_elapsed_ns=vc['elapsed_ns'],
                produce_peak_rss_bytes=pc['sampled_peak_rss_bytes'], verify_peak_rss_bytes=vc['sampled_peak_rss_bytes'],
                producer_receipt=identity(pdir/'receipt.json'), verifier_receipt=identity(vdir/'receipt.json'),
                pending=pointer, completion=v['completion'], parts=pending['parts'])


def main():
    source_gate()
    retained = load(ROOT/'files.json')
    paths = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p != ROOT/'files.json'}
    require(paths == set(retained), 'exact retained package membership')
    for name, value in retained.items():
        same(ROOT/name, value)
    expected = load(CONTRACT/'expected.json')
    prepared = load(CONTRACT/'local-preparation.json')
    same(CONTRACT/'local-preparation.json', expected['local_preparation'])
    for name, value in expected['bootstrap'].items():
        same(REPO/name, value)
    collected = collection()
    require(shutil.disk_usage(ROOT).free >= 8*1024**3, 'temporary replay free-space floor')
    with tempfile.TemporaryDirectory(prefix='whole-v2-evidence-') as directory:
        temp = Path(directory)
        for name in collected['archives']:
            archive(name, collected, None if name == 'run-logs' else temp/name)
        result = [generation(temp, expected, entry) for entry in prepared['admitted']['entries']]
    require([r['generation'] for r in result] == [1, 2] and sum(len(r['parts']) for r in result) == 22,
            'both complete generation part inventories')
    require(len({p['asset']['id'] for r in result for p in r['parts']}) == 22, 'distinct original certificate parts')
    return dict(schema='trident/linux-whole-self-build-positive-replay/v1', status='passed-offline-evidence-replay',
                run=expected['run'], generations=result,
                scope='Original remote positive runs and original transport evidence only; complete local download/adoption and composite SH8 acceptance are separate.')


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
