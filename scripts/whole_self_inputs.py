"""Immutable complete self-build inputs and exact accepted claim comparison."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from native_proof_inputs import require, sha

GIB = 1024**3
PROFILE = dict(wire_bytes=24 * GIB, decoded_bytes=96 * GIB, records=12_000_000_000,
               steps=16_000_000_000, cache_slots=262144, outer_wall_seconds=7500,
               sampled_rss_bytes=6 * GIB, attempt_disk_bytes=30 * GIB,
               minimum_free_start_bytes=48 * GIB,
               expected_artifact_sha256='76a07c08265bd2ef525164472b6b53ac3f0e6cbbedce3250c4202f40ffba34c8')
HOST = ['--arena-nodes', '1000000000', '--budget', '20000000000', '--frames', '65536',
        '--time-ms', '7200000', '--validation-visits', '16777216',
        '--resident-nodes', '3145728', '--collection-work', '10000000000']


def identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'regular input required: ' + str(path))
    return dict(bytes=path.stat().st_size, sha256=sha(path))


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate JSON key')
        value[key] = item
    return value


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def asset_selector(path):
    asset = load(path)
    require(asset['format'] == 'whole-self-build-input-v1', 'input format')
    require(asset['repository'] == 'cyberia-to/trisha' and asset['release_id'] == 389977897,
            'fixed evidence repository/release')
    require(type(asset['asset_id']) is int and asset['asset_id'] > 0, 'reviewed immutable asset ID required')
    require(asset['root'] == 'whole-proof-inputs' and asset['files'] == 111, 'frozen archive layout')
    require(asset['bytes'] == 16637580 and asset['sha256'] ==
            '7929925282e338a2f761510167575bfe4494c2713ac6fb9182fe59ef6223b9b8', 'frozen archive identity')
    require(asset['manifest_sha256'] == 'ac76da93cf873e3bdf3f309e593b6e4b5173f13acf50a6ec19887adea7f11e09', 'frozen manifest identity')
    return asset


def safe_name(name):
    value = PurePosixPath(name)
    require(name and not value.is_absolute() and '..' not in value.parts and '\\' not in name,
            'unsafe archive member')
    require(str(value) == name and ':' not in name, 'noncanonical archive member')
    return value


def admit(archive, destination, asset):
    require(identity(archive) == {k: asset[k] for k in ('bytes', 'sha256')}, 'archive bytes')
    root = asset['root'] + '/'
    with tarfile.open(archive, 'r:gz') as stream:
        seen = set()
        members = []
        manifest_bytes = None
        for member in stream:
            safe_name(member.name)
            require(member.isfile() and member.name.startswith(root) and member.name not in seen,
                    'unique regular member in fixed root')
            require(member.size <= 32 * 1024**2, 'archive member size')
            seen.add(member.name)
            members.append(member)
            require(len(members) <= asset['files'] + 1, 'archive member count')
            if member.name == root + 'files.json':
                require(member.size <= 1024**2, 'manifest size')
                manifest_bytes = stream.extractfile(member).read()
        require(manifest_bytes is not None and hashlib.sha256(manifest_bytes).hexdigest() == asset['manifest_sha256'], 'manifest bytes')
        manifest = json.loads(manifest_bytes, object_pairs_hook=unique)
        require(len(manifest) == asset['files'], 'manifest count')
        for name, expected in manifest.items():
            safe_name(name)
            require(set(expected) == {'bytes', 'sha256'} and 0 <= expected['bytes'] <= 32 * 1024**2, 'manifest identity')
        require(seen == {root + name for name in manifest} | {root + 'files.json'}, 'exact archive membership')
        destination.mkdir()
        for member in members:
            relative = member.name.removeprefix(root)
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, path.open('xb') as target:
                while chunk := source.read(1024**2):
                    target.write(chunk)
            if relative != 'files.json':
                require(identity(path) == manifest[relative], 'member bytes: ' + relative)
    profile = load(destination / 'profile.json')
    require(profile['host_flags'] == HOST, 'unchanged host profile')
    require(all(profile[k] == v for k, v in PROFILE.items()), 'unchanged whole-proof caps')
    before = {name: identity(destination / name) for name in manifest}
    return before


def flags():
    result = list(HOST)
    for flag, key in [('proof-bytes', 'wire_bytes'), ('proof-decoded-bytes', 'decoded_bytes'),
                      ('proof-records', 'records'), ('proof-steps', 'steps'), ('proof-cache-slots', 'cache_slots')]:
        result += ['--' + flag, str(PROFILE[key])]
    return result


def compare(value, accepted, action):
    require(value.get('ok') is True, 'successful Joy receipt')
    require(value.get('schema') == ('joy/artifact-proof/v1' if action == 'prove' else 'joy/artifact-verification/v1'), 'versioned Joy receipt')
    current = value['verification']
    old = accepted['execution']['execution']
    for key in ('program_particle', 'input_particle', 'output_particle', 'charged_reductions'):
        require(current[key] == old[key], 'accepted self-build coordinate: ' + key)
    require(current['logical_peak_frames'] == old['peak_frames'], 'accepted logical depth')
    require(current['expanded_steps'] == old['compaction']['evaluator_checkpoints'] - 1, 'accepted expanded steps')
    require(current['compiler_job'] == old['compiler_job'], 'exact complete compiler response')
    require(current['format'] == 'joy-nox-disclosed-compiler-v1' and
            current['disclosure'] == 'complete public witness' and current['physical_resource_claim'] == 'unattested', 'proof disclosure/profile')
    if action == 'verify':
        require('prover_observations' not in current, 'fresh verifier has no prover observations')
    return current
