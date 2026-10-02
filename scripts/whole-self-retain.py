"""Retain one successfully verified whole certificate on the fixed existing draft."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import traceback
from urllib.parse import quote

from native_proof_inputs import require, sanitized
from whole_self_host import cancellation_handlers, save
from whole_self_inputs import GIB, authorization, bootstrap, identity, load

REPO = 'cyberia-to/trisha'
RELEASE = 389977897
TAG = 'candidate-20260916.1'
CHUNK = GIB


def write_chunk(source, path, limit=CHUNK):
    digest, size = hashlib.sha256(), 0
    with path.open('xb') as output:
        while size < limit:
            part = source.read(min(1024**2, limit - size))
            if not part:
                break
            output.write(part)
            digest.update(part)
            size += len(part)
    return dict(bytes=size, sha256=digest.hexdigest())


def listed_assets(run, label):
    pages = load(run(label, ['gh', 'api', '--paginate', '--slurp',
                            f'repos/{REPO}/releases/{RELEASE}/assets?per_page=100']))
    require(isinstance(pages, list) and all(isinstance(p, list) for p in pages), 'paginated asset arrays')
    assets = [asset for page in pages for asset in page]
    require(len(assets) <= 1000, 'bounded release asset count')
    ids = [asset['id'] for asset in assets]
    require(all(type(value) is int and value > 0 for value in ids) and len(set(ids)) == len(ids), 'unique numeric asset IDs')
    return assets


def check_asset(asset, name, expected):
    require(type(asset['id']) is int and asset['id'] > 0 and asset.get('state') == 'uploaded', 'uploaded asset with numeric ID')
    require(asset['url'] == f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}", 'exact fixed-repository API asset URL')
    require(asset['name'] == name and asset['size'] == expected['bytes'] and
            asset.get('digest') == 'sha256:' + expected['sha256'], 'server part identity')


class Reconstruction:
    def __init__(self):
        self.digest = hashlib.sha256()
        self.bytes = 0

    def append(self, path, expected_part):
        part, size = hashlib.sha256(), 0
        with path.open('rb') as stream:
            while chunk := stream.read(1024**2):
                part.update(chunk)
                self.digest.update(chunk)
                size += len(chunk)
                self.bytes += len(chunk)
        require(dict(bytes=size, sha256=part.hexdigest()) == expected_part, 'independently downloaded part bytes')

    def finish(self, expected):
        actual = dict(bytes=self.bytes, sha256=self.digest.hexdigest())
        require(actual == expected, 'complete ordered download reconstruction')
        return actual


def main():
    cancellation_handlers()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    results = args.results.resolve()
    checked = load(results / 'receipt.json')
    require(checked['status'] == 'passed', 'successful full proof and fresh verification required')
    authorized = authorization(Path.cwd().resolve(), os.environ)
    require(authorized['retain_draft'], 'explicit draft retention authorization required')
    require(authorized == checked['authorization'], 'same replay and retention authorization')
    require(bootstrap(Path.cwd().resolve()) == checked['bootstrap'], 'reviewed bootstrap source unchanged')
    token = os.environ.get('GH_TOKEN')
    require(token, 'explicit draft transport token required')
    environment = dict(sanitized(os.environ), GH_TOKEN=token)
    source = Path(checked['proof']['path'])
    expected = {k: checked['proof'][k] for k in ('bytes', 'sha256')}
    require(identity(source) == expected, 'verified certificate bytes')
    prefix = '-'.join(['sh8', os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT'],
                       os.environ['GITHUB_SHA'][:12], 'c' + str(checked['generation']), expected['sha256'][:12]])
    require(all(c.isalnum() or c == '-' for c in prefix), 'safe unique asset prefix')
    directory = Path(load(results / 'retention-input.json')['work']) / 'retention'
    directory.mkdir()
    receipt = dict(schema='trident/whole-proof-draft-retention/v1', status='running',
                   repository=REPO, release_id=RELEASE, tag_name=TAG, proof=expected,
                   generation=checked['generation'], input_asset=checked['input_asset'],
                   authorization=authorized,
                   source_selector=checked['source_selector'], binary=checked['binary'],
                   verified_receipt=identity(results / 'receipt.json'), driver=identity(Path(__file__)),
                   commands=[], parts=[], scope='Unique complete evidence assets on existing unpublished draft; no promotion, tags or overwrite')

    def persist():
        save(results / 'retention-receipt.json', receipt)

    def run(name, command, expected_exit=0, output=None):
        require(not any(r['name'] == name for r in receipt['commands']), 'unique transport command')
        path = output or results / (name + '.stdout')
        error = results / (name + '.stderr')
        row = dict(name=name, command=command, started_ns=time.time_ns())
        receipt['commands'].append(row)
        persist()
        try:
            with path.open('xb') as stdout, error.open('xb') as stderr:
                process = subprocess.run(command, env=environment, stdout=stdout, stderr=stderr, timeout=1800)
            row['exit_code'] = process.returncode
        finally:
            row['stdout'], row['stderr'] = identity(path), identity(error)
            persist()
        require(row['exit_code'] == expected_exit, 'transport command failed: ' + name)
        return path

    def draft(label):
        value = load(run(label, ['gh', 'api', f'repos/{REPO}/releases/{RELEASE}']))
        require(value['id'] == RELEASE and value['draft'] and value['tag_name'] == TAG and value['published_at'] is None,
                'fixed existing unpublished draft required')
        absent = load(run(label + '-tag', ['gh', 'api', f'repos/{REPO}/git/ref/tags/{TAG}'], 1))
        require(str(absent.get('status')) == '404', 'draft tag remains absent')
        return listed_assets(run, label + '-assets')

    def upload(label, path, name, expected_part, reconstruction=None):
        before = draft(label + '-before')
        require(name not in {a['name'] for a in before}, 'unique asset name, no overwrite')
        endpoint = f'https://uploads.github.com/repos/{REPO}/releases/{RELEASE}/assets?name=' + quote(name, safe='')
        asset = load(run(label + '-upload', ['gh', 'api', '--method', 'POST', endpoint,
                     '-H', 'Content-Type: application/octet-stream', '--input', str(path)]))
        check_asset(asset, name, expected_part)
        after = draft(label + '-after')
        matches = [a for a in after if a['name'] == name]
        require(len(matches) == 1 and matches[0]['id'] == asset['id'], 'asset belongs to fixed draft')
        check_asset(matches[0], name, expected_part)
        # Release the owned upload copy before creating the independent download.
        path.unlink()
        downloaded = directory / (name + '.download')
        run(label + '-download', ['gh', 'api', f"repos/{REPO}/releases/assets/{asset['id']}", '-H', 'Accept: application/octet-stream'], output=downloaded)
        if reconstruction is None:
            require(identity(downloaded) == expected_part, 'independently downloaded bytes')
        else:
            reconstruction.append(downloaded, expected_part)
        downloaded.unlink()
        return {k: asset[k] for k in ('id', 'name', 'size', 'state', 'digest', 'url', 'browser_download_url')}

    persist()
    try:
        reconstruction = Reconstruction()
        with source.open('rb') as stream:
            remaining = expected['bytes']
            sequence = 0
            while remaining:
                path = directory / 'part'
                part = write_chunk(stream, path)
                require(0 < part['bytes'] <= min(CHUNK, remaining), 'bounded nonempty part')
                name = prefix + f'.part{sequence:04d}'
                asset = upload(f'part-{sequence:04d}', path, name, part, reconstruction)
                receipt['parts'].append(dict(sequence=sequence, offset=expected['bytes'] - remaining,
                                             **part, asset=asset, downloaded_verified=True))
                remaining -= part['bytes']
                sequence += 1
                persist()
            require(not stream.read(1), 'no appended certificate bytes')
        require(identity(source) == expected, 'original certificate unchanged after chunking')
        receipt['downloaded_reconstruction'] = reconstruction.finish(expected)
        persist()
        evidence = {str(p.relative_to(results)): identity(p) for p in sorted(results.rglob('*')) if p.is_file()}
        require(sum(v['bytes'] for v in evidence.values()) <= 256 * 1024**2, 'bounded raw receipt evidence')
        evidence_manifest = results / 'durable-metadata-files.json'
        save(evidence_manifest, evidence)
        metadata_path = directory / 'metadata.tar.gz'
        with tarfile.open(metadata_path, 'w:gz', compresslevel=1) as archive:
            for name in sorted(evidence):
                path = results / name
                require(identity(path) == evidence[name], 'receipt changed while archiving')
                archive.add(path, arcname='evidence/' + name, recursive=False)
            archive.add(evidence_manifest, arcname='evidence/durable-metadata-files.json', recursive=False)
        metadata_identity = identity(metadata_path)
        receipt['metadata'] = dict(**metadata_identity,
                                  asset=upload('metadata', metadata_path, prefix + '.metadata.tar.gz', metadata_identity))
        # This manifest is independently downloadable and names every immutable part.
        manifest = dict(schema='trident/whole-proof-parts/v1', proof=expected, parts=receipt['parts'],
                        downloaded_reconstruction=receipt['downloaded_reconstruction'],
                        generation=checked['generation'], verification=checked['verification'],
                        source_selector=checked['source_selector'], input_asset=checked['input_asset'],
                        binary=checked['binary'], tools=checked['tools'], metadata=receipt['metadata'],
                        command_receipt=identity(results / 'receipt.json'), reconstruction='Concatenate parts in sequence order; verify each part and then the complete SHA256.')
        manifest_path = directory / 'manifest.json'
        save(manifest_path, manifest)
        manifest_identity = identity(manifest_path)
        shutil_copy = results / 'parts-manifest.json'
        shutil_copy.write_bytes(manifest_path.read_bytes())
        receipt['manifest'] = dict(**manifest_identity,
                                  asset=upload('manifest', manifest_path, prefix + '.manifest.json', manifest_identity))
        draft('draft-final')
        receipt['status'] = 'passed'
    except BaseException:
        receipt.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        persist()
    print(json.dumps(dict(status=receipt['status'], manifest=receipt['manifest'])))


if __name__ == '__main__':
    main()
