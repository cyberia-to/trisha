"""Replay retained failure evidence only; never execute Joy or use the network."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
HEAD = '5d14ae46f327a7f0ee1f9812b4ba62b73cf035bc'
RUN = 36961998100


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def load(data):
    return json.loads(data, object_pairs_hook=unique)


def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def same(data, expected):
    require(identity(data) == {k: expected[k] for k in ('bytes', 'sha256')}, 'byte identity')


def archive(name, collected):
    path = ROOT / 'raw' / (name + '.zip')
    record = collected['archives'][name]
    same(path.read_bytes(), record)
    if 'metadata' in record:
        metadata = record['metadata']
        require(metadata['digest'] == 'sha256:' + record['sha256'], 'GitHub artifact digest')
        require(metadata['workflow_run']['head_sha'] == HEAD and
                metadata['workflow_run']['id'] == RUN, 'artifact run binding')
    result = {}
    with zipfile.ZipFile(path) as stream:
        members = stream.infolist()
        require(len(members) <= 10000 and sum(m.file_size for m in members) <= 1024**3, 'ZIP bounds')
        for member in members:
            name = member.filename.removesuffix('/') if member.is_dir() else member.filename
            p = PurePosixPath(name)
            require(name and str(p) == name and not p.is_absolute() and '..' not in p.parts and
                    '\\' not in name and ':' not in name, 'safe member')
            mode = member.external_attr >> 16
            require(not stat.S_ISLNK(mode) and stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), 'regular member')
            if member.is_dir():
                continue
            require(name not in result and member.file_size <= 16 * 1024**2, 'unique bounded member')
            data = stream.read(member)
            same(data, collected['extracted'][path.stem][name])
            result[name] = data
    require(set(result) == set(collected['extracted'][path.stem]), 'exact ZIP membership')
    return result


def main():
    retained = load((ROOT / 'files.json').read_bytes())
    actual_names = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p != ROOT / 'files.json'}
    require(actual_names == set(retained), 'retained package membership')
    for name, expected in retained.items():
        same((ROOT / name).read_bytes(), expected)
    collected = load((ROOT / 'raw/receipt.json').read_bytes())
    same((ROOT / 'collect.py').read_bytes(), collected['collector'])
    require(collected['status'] == 'passed' and collected['conclusion'] == 'failure', 'collection passed; run failed')
    require(collected['run'] == RUN and collected['expected_head'] == HEAD, 'collection run')
    for row in collected['commands']:
        require(row['exit_code'] == 0, 'collection command')
        endpoint = row['command'][2]
        label = ('artifacts' if '/artifacts?' in endpoint else 'jobs' if '/jobs?' in endpoint else
                 'run-logs' if endpoint.endswith('/logs') else 'run')
        if '/actions/artifacts/' in endpoint:
            number = int(endpoint.split('/')[-2])
            label = next(k for k, v in collected['archives'].items() if v.get('metadata', {}).get('id') == number)
        suffix = '.zip' if label == 'run-logs' or label.startswith('whole-self') else '.json'
        same((ROOT / 'raw' / (label + suffix)).read_bytes(), row['stdout'])
        same((ROOT / 'raw' / (label + '.stderr')).read_bytes(), row['stderr'])
    run = load((ROOT / 'raw/run.json').read_bytes())
    require(run['id'] == RUN and run['head_sha'] == HEAD and run['run_attempt'] == 1 and
            run['event'] == 'push' and run['status'] == 'completed' and run['conclusion'] == 'failure', 'Actions result')
    jobs = load((ROOT / 'raw/jobs.json').read_bytes())['jobs']
    require({j['name'] for j in jobs} == {'full (1)', 'full (2)'}, 'two jobs')
    for job in jobs:
        require(job['conclusion'] == 'failure', 'failed job')
        steps = {s['name']: s for s in job['steps']}
        require(steps['Retain verified complete proof as checked draft assets']['conclusion'] == 'skipped', 'no durable proof publication')
        require(steps['Preserve exact success or failure receipts and native executable']['conclusion'] == 'success', 'failure metadata retained')
    archive('run-logs', collected)
    manifest = (ROOT / 'frozen-input-files.json').read_bytes()
    frozen = load(manifest)
    require(identity(manifest)['sha256'] == 'ac76da93cf873e3bdf3f309e593b6e4b5173f13acf50a6ec19887adea7f11e09', 'immutable input inventory')
    reports, inventories, closures = [], [], []
    for generation in (1, 2):
        files = archive(f'whole-self-build-c{generation}-1', collected)
        receipt = load(files['receipt.json'])
        require(receipt['status'] == 'failed' and receipt['generation'] == generation and
                receipt['runner_revision'] == HEAD and receipt['native_target'] == 'x86_64-unknown-linux-gnu', 'native failed receipt')
        require(receipt['frozen_inputs_before'] == frozen, '111 frozen files')
        require('frozen_inputs_after' not in receipt and 'sources-after.json' not in files, 'post-failure closure is absent')
        for name, expected in receipt['bootstrap'].items():
            same((REPO / name).read_bytes(), expected)
        commands = receipt['commands']
        require(len({c['name'] for c in commands}) == len(commands), 'unique command logs')
        for row in commands:
            require(row['exit_code'] == 0, 'all preparation commands passed')
            for stream in ('stdout', 'stderr'):
                if row['name'] == 'input-asset-download' and stream == 'stdout':
                    same_expected = {k: receipt['input_asset'][k] for k in ('bytes', 'sha256')}
                    require({k: row[stream][k] for k in same_expected} == same_expected, 'download matches pinned asset')
                else:
                    same(files[row['name'] + '.' + stream], row[stream])
        require(b'rustc 1.89.0 ' in files['rustc-version.stdout'], 'native baseline rustc')
        require(b'cargo 1.89.0 ' in files['cargo-version.stdout'], 'native baseline cargo')
        same(files['joy-linux-x64'], receipt['binary'])
        inventory = load(files['sources-before.json'])
        same(files['sources-before.json'], receipt['source_inventory_identities']['sources-before.json'])
        require({k: v['commit'] for k, v in inventory.items()} == receipt['source_selector']['sources'], '12 pinned repository inventories')
        for path in (ROOT / 'deadline-source').rglob('*'):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT / 'deadline-source')
            repo, name = relative.parts[0], '/'.join(relative.parts[1:])
            expected = next(x for x in inventory[repo]['files'] if x['path'] == name)
            same(path.read_bytes(), expected)
        require(len(receipt['proof_commands']) == 1, 'no verifier command ran')
        proof = receipt['proof_commands'][0]
        require(proof['name'] == 'prove' and proof['exit_code'] == 1 and proof['status'] == 'failed' and
                'resource_stop' not in proof and proof['environment'] == {'PATH': ''}, 'internal failure; no outer guard stop')
        require(proof['command'][proof['command'].index('--time-ms') + 1] == '7200000', 'original deadline')
        expected_flags = ['--arena-nodes', '1000000000', '--budget', '20000000000',
                          '--frames', '65536', '--time-ms', '7200000',
                          '--validation-visits', '16777216', '--resident-nodes', '3145728',
                          '--collection-work', '10000000000', '--proof-bytes', '25769803776',
                          '--proof-decoded-bytes', '103079215104', '--proof-records', '12000000000',
                          '--proof-steps', '16000000000', '--proof-cache-slots', '262144']
        require(proof['command'][7:] == expected_flags and proof['command'][1] == 'prove-artifact' and
                proof['command'][3] == '--input' and proof['command'][5:7] == ['--output', 'proof.joysc'], 'exact production command')
        require(proof['binary_before'] == proof['binary_after'] and proof['inputs_before'] == proof['inputs_after'], 'runtime identities unchanged')
        for path, expected in proof['inputs_before'].items():
            require(expected == frozen['inputs/' + Path(path).name], 'actual compiler/JOB identity')
        for stream in ('stdout', 'stderr'):
            same(files['prove.' + stream], proof['logs'][stream])
        require(files['prove.stdout'] == b'' and files['prove.stderr'] ==
                b'error: execution error: certificate execution/capture: Capture(Cancelled)\n', 'exact deadline failure')
        samples = [load(line) for line in files['prove-resources.jsonl'].splitlines()]
        require(all(a['elapsed_ns'] < b['elapsed_ns'] for a, b in zip(samples, samples[1:])), 'ordered samples')
        peak = max(s['rss_bytes'] for s in samples)
        require(peak == proof['sampled_peak_rss_bytes'] and samples[-1] == proof['latest_sample'], 'raw resource summary')
        require(all(s['rss_bytes'] == sum(p['rss_bytes'] for p in s['processes']) for s in samples), 'process RSS accounting')
        require(peak <= receipt['profile']['sampled_rss_bytes'] and
                max(s['attempt_bytes'] for s in samples) <= receipt['profile']['attempt_disk_bytes'] and
                min(s['free_bytes'] for s in samples) >= 8 * 1024**3, 'physical bounds')
        maximum = max(samples, key=lambda s: s['attempt_bytes'])
        build = next(c for c in commands if c['name'] == 'native-build')
        reports.append(dict(generation=generation, result='failed-internal-7200-second-deadline',
                            prove_elapsed_ns=proof['elapsed_ns'], sampled_peak_rss_bytes=peak,
                            samples=len(samples), maximum_sampled_attempt_bytes=maximum['attempt_bytes'],
                            maximum_sample_elapsed_ns=maximum['elapsed_ns'], final_attempt_bytes=samples[-1]['attempt_bytes'],
                            minimum_sampled_free_bytes=min(s['free_bytes'] for s in samples),
                            native_build_elapsed_ns=build['elapsed_ns'],
                            bootstrap_to_prove_ns=proof['started_ns']-commands[0]['started_ns'],
                            binary=receipt['binary'], preparation_commands=len(commands)))
        inventories.append(inventory)
        closures.append(receipt['closure'])
    require(inventories[0] == inventories[1] and closures[0] == closures[1], 'same source inventory and package closure')
    return dict(schema='whole-self-build-linux-failure-replay-v1', status='passed-integrity-replay',
                execution_result='both-original-Linux-producers-failed', run=RUN, source=HEAD,
                archive_count=3, retained_archive_files=sum(len(v) for v in collected['extracted'].values()),
                source_repositories=len(inventories[0]), source_file_entries=sum(len(v['files']) for v in inventories[0].values()),
                complete_proofs=0, fresh_verifications=0, generations=reports)


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
