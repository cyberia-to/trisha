"""Fixed local and remote admission contracts; no network or proof execution."""
import importlib
from pathlib import Path

from common import CHUNK, REPO, check_asset, identity, load, require, scan_parts

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT.parent / 'whole-local-retention'
EXPECTED = dict(bytes=19882, sha256='795ffd98018083d6b50871ea47e559046bc6bb3d0a041a84bc5a0d879ef78bb7')
MIB = 1024**2
SIDECARS = 512 * MIB
RUN = 36976540959
HEAD = '142198726fdec26dae87e2f694da2c2252fefb0f'
SCOPE = 'byte-equivalent durable transport adoption; separate local and remote runs; SH8 acceptance pending'


def ident(value):
    return {k: value[k] for k in ('bytes', 'sha256')}


def fixed():
    require(identity(ROOT / 'expected.json') == EXPECTED, 'fixed reviewed expected data')
    value = load(ROOT / 'expected.json')
    for name, expected in value['frozen_admission'].items():
        require(identity(ROOT / name) == expected, 'frozen local admission source')
    require(identity(ROOT / 'local-preparation.json') == value['local_preparation'], 'original preparation snapshot')
    return value


def local_admission(expected, scan=False):
    require(identity(LOCAL / 'preparation.json') == expected['local_preparation'], 'original preparation unchanged')
    prepared = load(LOCAL / 'preparation.json')
    require(prepared['schema'] == 'trident/local-whole-retention-preparation/v1' and prepared['status'] == 'prepared', 'local preparation schema')
    admitted = prepared['admitted']
    wanted = dict(admitted, entries=[{k: v for k, v in entry.items() if k != 'parts'} for entry in admitted['entries']])
    require(importlib.import_module('admission').admit() == wanted, 'original four receipts and admitted evidence')
    require(identity(prepared['metadata']['path']) == ident(prepared['metadata']), 'original local metadata bytes')
    require(identity(LOCAL / 'metadata-files.json') == ident(prepared['metadata_manifest']), 'original local metadata inventory')
    require([e['generation'] for e in admitted['entries']] == [1, 2] and sum(len(e['parts']) for e in admitted['entries']) == 22, 'original pair and 22 parts')
    if scan:
        for entry in admitted['entries']:
            require(scan_parts(entry['proof']['path'], ident(entry['proof'])) == entry['parts'], 'current complete local bytes and every prepared part')
    return prepared


def admit_run(run, jobs):
    require(run['id'] == RUN and run['run_attempt'] == 1 and run['head_sha'] == HEAD and
            run['repository']['full_name'] == REPO and run['head_repository']['full_name'] == REPO,
            'exact authenticated original run')
    require(run['path'] == '.github/workflows/whole-self-build-v2.yml' and run['event'] == 'push' and
            run['head_branch'] == 'test/0.4-whole-self-build-ci', 'original workflow activation')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'entire remote run completed successfully')
    require(jobs['total_count'] == 4 and len(jobs['jobs']) == 4, 'exactly four actual jobs')
    require({j['name'] for j in jobs['jobs']} == {f'c{g} / {p}' for g in (1, 2) for p in ('producer', 'verifier')}, 'exact generation jobs')
    require(len({j['id'] for j in jobs['jobs']}) == 4, 'distinct native jobs')
    for job in jobs['jobs']:
        require(job['run_id'] == RUN and job['run_attempt'] == 1 and job['head_sha'] == HEAD and
                job['status'] == 'completed' and job['conclusion'] == 'success', 'job coordinates and success')
        require(job['labels'] == ['ubuntu-24.04'] and job['completed_at'], 'actual native Linux job')
        require(all(s['status'] == 'completed' and s['conclusion'] == 'success' for s in job['steps']), 'all original job steps passed')
    return {j['name']: j for j in jobs['jobs']}


def artifact(value, name):
    require(type(value['id']) is int and value['id'] > 0 and value['name'] == name and value['expired'] is False, 'live original Actions artifact')
    require(value['url'] == f"https://api.github.com/repos/{REPO}/actions/artifacts/{value['id']}" and
            value['archive_download_url'] == value['url'] + '/zip', 'fixed Actions artifact origin')
    run = value['workflow_run']
    require(run['id'] == RUN and run['head_sha'] == HEAD and run['head_branch'] == 'test/0.4-whole-self-build-ci', 'artifact original run binding')
    require(type(value['size_in_bytes']) is int and 0 < value['size_in_bytes'] <= 128 * MIB, 'bounded original ZIP')
    digest = value['digest']
    require(isinstance(digest, str) and digest.startswith('sha256:') and len(digest) == 71 and
            all(c in '0123456789abcdef' for c in digest[7:]), 'server ZIP digest')
    return dict(bytes=value['size_in_bytes'], sha256=digest[7:])


def common_remote(value, expected, generation):
    for key in ('run', 'profile', 'source_selector', 'input_asset'):
        require(value[key] == expected[key], 'fixed remote ' + key)
    require(type(value['generation']) is int and value['generation'] == generation, 'exact generation')


def semantics(value, local):
    require({k: v for k, v in value.items() if k not in ('elapsed_micros', 'prover_observations')} == local,
            'all logical, compiler, transport and complete-record coordinates equal local')


def pending_manifest(value, expected, entry):
    generation = entry['generation']; common_remote(value, expected, generation)
    require(value['schema'] == 'trident/whole-proof-pending/v2' and value['status'] == 'pending-fresh-verification', 'pending schema')
    require(value['proof'] == ident(entry['proof']) and value['downloaded_reconstruction'] == value['proof'], 'whole proof equal local before body download')
    require(value['compiler'] == expected['frozen_inputs'][f'inputs/c{generation}.dag'] and
            value['job'] == expected['frozen_inputs'][f'inputs/c{generation}-job.dag'], 'exact compiler and complete JOB')
    semantics(value['production'], entry['verification'])
    require(len(value['parts']) == len(entry['parts']), 'exact part count')
    ids, names = set(), set()
    for got, local in zip(value['parts'], entry['parts']):
        require({k: got[k] for k in ('sequence', 'offset', 'bytes', 'sha256')} == local, 'every canonical part equals local')
        require(got['downloaded_verified'] is True, 'producer independent part readback')
        asset = got['asset']; check_asset(asset, asset['name'], local)
        require(asset['id'] not in ids and asset['name'] not in names, 'unique part assets')
        ids.add(asset['id']); names.add(asset['name'])
    return value


def completion_manifest(value, expected, entry, pointer, pending):
    common_remote(value, expected, entry['generation'])
    require(value['schema'] == 'trident/whole-proof-completion/v2' and value['status'] == 'fresh-verified', 'completion manifest success schema')
    require(value['proof'] == pending['proof'] == ident(entry['proof']) and value['pending'] == pointer, 'completion binds exact pending and proof')
    require(value['compiled'] == expected['frozen_inputs']['inputs/c2.dag'], 'complete accepted C2/C3 bytes')
    semantics(value['verification'], entry['verification'])
    require('prover_observations' not in value['verification'], 'independent verifier observations')
    return value
