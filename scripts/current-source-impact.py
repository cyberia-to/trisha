"""Bind inherited compiler integration evidence to unchanged committed inputs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

FROZEN = '9fddb8002ebb49ad724dfeb20972066c1de0b75b22f806b5360609bb12eaaec5'
PROFILE = 'cda54f7ee5f34f01566cc728c22b3dd97bee63247c646c518039d9906309717f'
VENDOR = 'cf324959661a85fc94cf4345beaf5dbf274c1dbd5fc66960155e0750ace35d1b'
FROZEN_HEAD = 'c94da47247457f9e819c2682e74d34f5f1756f62'
PROFILE_HEAD = '2b7017f89a495eb43c0feca6818eb68f35c21a02'
# These reporting/automation paths are excluded explicitly. Compiler and
# runtime implementation, manifests, fixtures, examples and test code remain.
REPORTING = ('.claude/plans/', 'audit/', 'docs/', 'roadmap/', 'reference/')
TRISHA_AUTOMATION = {'.github/native-proof-profile.json',
                     '.github/workflows/native-proof-profile.yml',
                     'scripts/native-proof-profile.py', 'scripts/native_proof_inputs.py',
                     'scripts/test_native_proof_profile.py'}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reference(root, name, expected):
    raw = gzip.decompress((root / name).read_bytes())
    require(digest(raw) == expected, 'reference inventory identity differs: ' + name)
    return json.loads(raw)


def inventory(row, exclude):
    result = {}
    omitted = []
    for entry in row['files']:
        path = entry['path']
        if exclude(path):
            omitted.append(path)
            continue
        require(path not in result, 'duplicate inventory path')
        kind = entry.get('type', 'symlink' if entry.get('mode') == '120000' else 'file')
        result[path] = dict(type=kind, sha256=entry['sha256'], bytes=entry['bytes'])
    return result, omitted


def compare(name, actual, previous, exclude):
    current, excluded_current = inventory(actual, exclude)
    before, excluded_previous = inventory(previous, exclude)
    changed = sorted(path for path in current.keys() | before.keys() if current.get(path) != before.get(path))
    require(not changed, name + ' protected source changed: ' + ', '.join(changed[:30]))
    return dict(repository=name, current_commit=actual['commit'], reference_commit=previous['commit'],
                protected_files=len(current), protected_inventory_sha256=digest(json.dumps(current, sort_keys=True).encode()),
                excluded_current=excluded_current, excluded_reference=excluded_previous)


def check(source, selector, references):
    inputs = json.loads(selector.read_text())
    require(inputs['validation_profile'] == 'current-package-v1', 'unknown validation profile')
    rows = json.loads((source / 'sources.json').read_text())
    require(isinstance(rows, list) and all(row['mode'] == 'committed' for row in rows), 'committed sources required')
    current = {row['repository']: row for row in rows}
    expected = {row['repository']: row['commit'] for row in inputs['sources']}
    require(len(current) == len(rows) == len(expected) == 11, 'production closure must contain exactly eleven selected repositories')
    require({name: row['commit'] for name, row in current.items()} == expected, 'source commits differ from reviewed current inputs')
    frozen = {row['repository']: row for row in reference(references, 'frozen-sources.json.gz', FROZEN)}
    profile = reference(references, 'public-profile-sources.json.gz', PROFILE)
    receipt = json.loads((references / 'public-profile-receipt.json').read_text())
    require(receipt['status'] == 'passed' and receipt['runner_revision'] == PROFILE_HEAD
            and receipt['sources_before_sha256'] == receipt['sources_after_sha256'] == PROFILE,
            'public profile source receipt differs')
    # Successful whole-run API evidence is added only after the original
    # five remote producers finish. A running/failed matrix cannot authorize
    # inheritance. The sixth frozen local CPU receipt is checked separately.
    run = json.loads((references / 'frozen-run.json').read_text())
    require(run['id'] == 36949324686 and run['head_sha'] == FROZEN_HEAD
            and run['status'] == 'completed' and run['conclusion'] == 'success', 'frozen native matrix has not passed')
    local = json.loads((references / 'frozen-local-cpu.json').read_text())
    require(local['status'] == 'passed' and local['source_provenance_sha256'] == FROZEN
            and local['actual_rustc'].startswith('rustc 1.89.0 ')
            and local['target'] == 'aarch64-apple-darwin'
            and local['trident_passed'] > 0, 'frozen local native CPU evidence differs')
    require(digest((source / 'vendor-sources.json').read_bytes()) == VENDOR, 'Triton vendor inventory changed')
    comparisons = []
    for name in sorted(current):
        if name in ('joy', 'nox', 'zheng'):
            prior = profile[name]
            exclude = lambda path: path.startswith(REPORTING)
            authority = 'actual six-platform public-profile source inventory'
        elif name == 'trident':
            prior = frozen[name]
            exclude = lambda path: path.startswith(('.claude/plans/', 'audit/')) or path == 'reference/self-hosting.md'
            authority = 'frozen native distribution compiler integration source inventory'
        elif name == 'trisha':
            prior = frozen[name]
            exclude = lambda path: path.startswith(REPORTING) or path in TRISHA_AUTOMATION
            authority = 'frozen Triton runtime and packaging source inventory'
        else:
            prior = frozen[name]
            require(current[name]['commit'] == prior['commit'], 'unchanged production dependency pin moved: ' + name)
            exclude = lambda path: False
            authority = 'identical frozen production dependency'
        row = compare(name, current[name], prior, exclude)
        row['reference_scope'] = authority
        comparisons.append(row)
    return dict(status='passed', scope='Source impact only; inherited long compiler integration evidence is not a new binary test',
                source_provenance_sha256=digest((source / 'sources.json').read_bytes()),
                selector_sha256=digest(selector.read_bytes()), vendor_sha256=VENDOR,
                checker_sha256=digest(Path(__file__).read_bytes()),
                inherited_frozen_run_id=run['id'], inherited_frozen_runner=FROZEN_HEAD,
                inherited_public_profile_run_id=36958147193, inherited_public_profile_runner=PROFILE_HEAD,
                comparisons=comparisons)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.source, args.inputs, args.references)
    with args.receipt.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
