"""Fixed-draft immutable transport; pending and verified receipts stay distinct."""
import hashlib
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tarfile
import time
import traceback
from urllib.parse import quote

from native_proof_inputs import require, sanitized
from whole_self_inputs import GIB, PROFILE, identity, load
from whole_self_host import save, terminate
from whole_v2_common import owned_bytes

REPO, RELEASE, TAG, CHUNK = 'cyberia-to/trisha', 389977897, 'candidate-20260916.1', GIB


def check_asset(asset, name, expected):
    require(type(asset['id']) is int and asset['id'] > 0 and asset.get('state') == 'uploaded', 'uploaded numeric asset')
    require(asset['url'] == f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}", 'fixed asset API origin')
    require(asset['name'] == name and asset['size'] == expected['bytes'] and
            asset.get('digest') == 'sha256:' + expected['sha256'], 'exact server asset bytes')


def write_chunk(source, path, limit=CHUNK):
    size, digest = 0, hashlib.sha256()
    with path.open('xb') as output:
        while size < limit:
            part = source.read(min(1024**2, limit-size))
            if not part:
                break
            output.write(part); digest.update(part); size += len(part)
    return dict(bytes=size, sha256=digest.hexdigest())


class Reconstruction:
    def __init__(self):
        self.digest, self.bytes = hashlib.sha256(), 0

    def append(self, path, expected, output=None):
        digest, size = hashlib.sha256(), 0
        with path.open('rb') as source:
            while chunk := source.read(1024**2):
                if output is not None:
                    output.write(chunk)
                digest.update(chunk); self.digest.update(chunk); size += len(chunk); self.bytes += len(chunk)
        require(dict(bytes=size, sha256=digest.hexdigest()) == expected, 'downloaded chunk identity')

    def finish(self, expected):
        actual = dict(bytes=self.bytes, sha256=self.digest.hexdigest())
        require(actual == expected, 'complete ordered certificate identity')
        return actual


def validate_pending(value, state):
    r = state.report
    require(value['schema'] == 'trident/whole-proof-pending/v2' and value['status'] == 'pending-fresh-verification', 'explicit pending schema')
    for key in ('run', 'generation', 'profile', 'source_selector', 'input_asset'):
        require(value[key] == r[key], 'pending ' + key)
    require(value['compiler'] == identity(state.paths()[1]) and value['job'] == identity(state.paths()[2]), 'pending expected compiler/JOB')
    proof = value['proof']
    require(set(proof) == {'bytes', 'sha256'} and type(proof['bytes']) is int and
            0 < proof['bytes'] <= PROFILE['wire_bytes'] and len(proof['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in proof['sha256']), 'bounded canonical certificate identity')
    parts = value['parts']
    require(len(parts) == (proof['bytes'] + CHUNK - 1)//CHUNK, 'exact chunk count')
    offset, ids, names = 0, set(), set()
    for sequence, part in enumerate(parts):
        require(part['sequence'] == sequence and part['offset'] == offset and
                part['bytes'] == min(CHUNK, proof['bytes']-offset), 'contiguous canonical chunks')
        require(len(part['sha256']) == 64 and all(c in '0123456789abcdef' for c in part['sha256']), 'chunk digest')
        check_asset(part['asset'], part['asset']['name'], part)
        require(part['asset']['id'] not in ids and part['asset']['name'] not in names, 'unique chunk identities')
        require(part['downloaded_verified'] is True, 'producer independent chunk readback')
        ids.add(part['asset']['id']); names.add(part['asset']['name']); offset += part['bytes']
    require(offset == proof['bytes'] and value['downloaded_reconstruction'] == proof, 'complete pending reconstruction')


class Transport:
    def __init__(self, state, label):
        self.state, self.results = state, state.results
        self.directory = state.work / ('transport-' + label); self.directory.mkdir()
        require(os.environ.get('GH_TOKEN'), 'explicit transport token')
        self.environment = dict(sanitized(os.environ), GH_TOKEN=os.environ['GH_TOKEN'])
        self.record = dict(schema='trident/whole-proof-transport/v2', status='running', phase=label,
                           run=state.report['run'], generation=state.report['generation'],
                           repository=REPO, release_id=RELEASE, tag_name=TAG, commands=[])
        self.path = self.results / ('transport-' + label + '.json')
        self.label = label
        self.persist()

    def persist(self):
        save(self.path, self.record)

    def disk_guard(self, reserve=0):
        evidence_bytes = owned_bytes(self.results)
        require(evidence_bytes <= 256 * 1024**2, '256 MiB raw evidence cap')
        require(owned_bytes(self.state.work) + evidence_bytes + reserve <= PROFILE['attempt_disk_bytes'], '30 GiB owned work cap')
        require(shutil.disk_usage(self.state.work).free >= 8 * GIB + reserve, '8 GiB free-space floor plus reservation')

    def run(self, name, command, expected_exit=0, output=None, cap=16 * 1024**2):
        require(not any(r['name'] == name for r in self.record['commands']), 'unique transport command')
        path = output or self.results / (self.label + '-' + name + '.stdout')
        error = self.results / (self.label + '-' + name + '.stderr')
        row = dict(name=name, command=command, started_ns=time.time_ns())
        self.record['commands'].append(row); self.persist(); child = None
        self.disk_guard(cap)
        tick = time.monotonic_ns()
        def limits():
            resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
        try:
            with path.open('xb') as stdout, error.open('xb') as stderr:
                child = subprocess.Popen(command, env=self.environment, stdout=stdout, stderr=stderr,
                                         start_new_session=True, preexec_fn=limits)
                while child.poll() is None:
                    require(time.monotonic_ns()-tick <= 1800 * 10**9, 'transport command deadline')
                    require(path.stat().st_size <= cap and error.stat().st_size <= cap, 'transport output byte caps')
                    self.disk_guard()
                    try:
                        child.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        pass
                row.update(exit_code=child.wait(), elapsed_ns=time.monotonic_ns()-tick)
            require(path.stat().st_size <= cap and error.stat().st_size <= cap, 'final transport output caps')
            require(row['exit_code'] == expected_exit, 'transport command failed: ' + name)
        finally:
            terminate(child)
            row['stdout'], row['stderr'] = identity(path), identity(error); self.persist()
        return path

    def draft(self, label):
        value = load(self.run(label, ['gh', 'api', f'repos/{REPO}/releases/{RELEASE}']))
        require(value['id'] == RELEASE and value['draft'] is True and value['tag_name'] == TAG and
                value['published_at'] is None, 'fixed unpublished evidence draft')
        absent = load(self.run(label+'-tag', ['gh', 'api', f'repos/{REPO}/git/ref/tags/{TAG}'], 1))
        require(str(absent.get('status')) == '404', 'tag remains absent')
        pages = load(self.run(label+'-assets', ['gh', 'api', '--paginate', '--slurp', f'repos/{REPO}/releases/{RELEASE}/assets?per_page=100']))
        require(isinstance(pages, list) and all(isinstance(p, list) for p in pages), 'paginated arrays')
        assets = [a for p in pages for a in p]
        ids = [a['id'] for a in assets]
        require(len(assets) <= 1000 and all(type(i) is int and i > 0 for i in ids) and len(set(ids)) == len(ids), 'bounded unique asset listing')
        return assets

    def download(self, label, asset, expected):
        listing = self.draft(label+'-membership')
        matches = [a for a in listing if a['id'] == asset['id']]
        require(len(matches) == 1, 'asset belongs to fixed draft')
        check_asset(matches[0], asset['name'], expected)
        check_asset(asset, asset['name'], expected)
        path = self.directory / (label + '.download')
        self.run(label+'-download', ['gh', 'api', f"repos/{REPO}/releases/assets/{asset['id']}", '-H', 'Accept: application/octet-stream'], output=path, cap=expected['bytes'])
        require(identity(path) == expected, 'downloaded asset bytes')
        return path

    def upload(self, label, path, name, expected):
        require(path.parent == self.directory and identity(path) == expected, 'owned immutable upload copy')
        before = self.draft(label+'-before')
        require(name not in {a['name'] for a in before}, 'unique name without overwrite')
        endpoint = f'https://uploads.github.com/repos/{REPO}/releases/{RELEASE}/assets?name=' + quote(name, safe='')
        asset = load(self.run(label+'-upload', ['gh', 'api', '--method', 'POST', endpoint, '-H', 'Content-Type: application/octet-stream', '--input', str(path)]))
        check_asset(asset, name, expected)
        after = self.draft(label+'-after')
        matches = [a for a in after if a['name'] == name]
        require(len(matches) == 1 and matches[0]['id'] == asset['id'], 'unique uploaded membership')
        check_asset(matches[0], name, expected)
        path.unlink()
        downloaded = self.download(label+'-readback', asset, expected)
        return {k: asset[k] for k in ('id', 'name', 'size', 'state', 'digest', 'url', 'browser_download_url')}, downloaded

    def metadata(self, prefix):
        evidence = {str(p.relative_to(self.results)): identity(p) for p in sorted(self.results.rglob('*')) if p.is_file()}
        require(sum(v['bytes'] for v in evidence.values()) <= 256 * 1024**2, 'bounded raw evidence')
        manifest = self.directory / 'metadata-files.json'; save(manifest, evidence)
        path = self.directory / 'metadata.tar.gz'
        self.disk_guard(256 * 1024**2)
        with tarfile.open(path, 'w:gz', compresslevel=1) as archive:
            for name in sorted(evidence):
                source = self.results / name; require(identity(source) == evidence[name], 'stable evidence')
                archive.add(source, arcname='evidence/' + name, recursive=False)
            archive.add(manifest, arcname='evidence/files.json', recursive=False)
        expected = identity(path); require(expected['bytes'] <= 256 * 1024**2, 'metadata archive cap')
        asset, downloaded = self.upload('metadata', path, prefix + '.metadata.tar.gz', expected)
        downloaded.unlink()
        return dict(**expected, asset=asset)

    def finish(self, status):
        self.draft('final-draft'); self.record['status'] = status; self.persist()

    def failed(self):
        self.record.update(status='failed', error=traceback.format_exc()); self.persist()


def prefix(state, status, proof):
    r = state.report
    result = '-'.join(['sh8v2', r['run']['run_id'], r['run']['attempt'], r['run']['head'][:12],
                       'c'+str(r['generation']), status, proof['sha256'][:12]])
    require(all(c.isalnum() or c == '-' for c in result), 'safe unique prefix')
    return result
