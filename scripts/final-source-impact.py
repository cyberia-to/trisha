"""Bind the final deadline package to exact reviewed production inputs."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

JOY = 'dd61df9128f6da1f97d4698f45f154f05312fe51'
JOY_INVENTORY = '0e2fc7b13570846474001bdedf80161728a8973ec2968075548d4884d3cb47f5'
OLD_LIMITS = 'b7adbee9300d3136705270abf72081e95fc26ca810b0fff0a947e77201116447'
ACCEPTANCE = {
    'source734-local-replay.json': '9f1c1e114ad7cbf47f4ac8d3126990211ea709f320b1402cdf1f9909c85573d6',
    'source734-containers-replay.json': '9c2ebca79cd14c9216cc12e8ee9559f9371116b39ea3f65c2e855b7ea282f5f0',
    'source734-corpus-replay.json': 'ede5500b265297bb55e5132a7a05f6628c923f3bee752f07b49d53020430db3b',
}
JOY_TEST_CHANGES = {
    'cli/tests/structured_certificates.rs', 'cli/tests/structured_certificates/deadline.rs',
    'cli/tests/structured_run.rs', 'rs/structured/tests/compaction.rs',
    'rs/structured/tests/compiler/compaction.rs',
}


def helper():
    spec = importlib.util.spec_from_file_location('inheritance', Path(__file__).with_name('inherit-full-baselines.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare_rows(rows, references):
    inherited = helper()
    require, digest = inherited.require, inherited.digest
    raw = gzip.decompress((references / 'source734-sources.json.gz').read_bytes())
    require(digest(raw) == inherited.PROVENANCE, 'source734 reference identity differs')
    previous = json.loads(raw)
    changed, protected = inherited.compare_sources(rows, previous)
    require(not changed, 'non-Joy protected source changed: ' + ', '.join(changed[:30]))
    current = {row['repository']: row for row in rows}
    old = {row['repository']: row for row in previous}
    require(current['joy']['commit'] == JOY, 'final Joy must be the reviewed dd61 commit')
    raw = gzip.decompress((references / 'joy-dd61-inventory.json.gz').read_bytes())
    require(digest(raw) == JOY_INVENTORY, 'reviewed Joy inventory identity differs')
    expected = json.loads(raw)
    actual_inventory = inherited.inventory(current['joy'])
    require(actual_inventory == inherited.inventory(expected), 'final Joy files differ from exact reviewed commit')
    before = inherited.inventory(old['joy'])
    changed_joy = sorted(path for path in before.keys() | actual_inventory.keys()
                         if before.get(path) != actual_inventory.get(path))
    production = [p for p in changed_joy if not p.startswith(('.claude/plans/', 'audit/', 'specs/'))
                  and p not in JOY_TEST_CHANGES]
    require(production == ['rs/structured/limits.rs'], 'Joy production diff exceeds reviewed limit constant')
    limits = (references / 'joy11b7-limits.rs').read_bytes()
    require(digest(limits) == OLD_LIMITS and limits.count(b'const COMPACT_TIME_MS: u64 = 7_200_000;') == 1,
            'prior limit source differs')
    replacement = limits.replace(b'const COMPACT_TIME_MS: u64 = 7_200_000;',
                                 b'const COMPACT_TIME_MS: u64 = 14_400_000;')
    require(actual_inventory['rs/structured/limits.rs'] == dict(type='file', bytes=len(replacement), sha256=digest(replacement)),
            'Joy production change is not exactly the reviewed ceiling')
    acceptance = {}
    for name, expected_sha in ACCEPTANCE.items():
        data = (references / name).read_bytes()
        require(digest(data) == expected_sha, 'original accepted measurement differs: ' + name)
        acceptance[name] = dict(sha256=expected_sha, original=json.loads(data))
    return dict(protected_non_joy=protected, joy_commit=JOY, joy_inventory_sha256=JOY_INVENTORY,
                joy_changed_files=changed_joy, joy_production_changes=production,
                original_source734_acceptance=acceptance)


def check(source, inputs, references):
    inherited = helper()
    selected = json.loads(inputs.read_text())
    inherited.require(selected['validation_profile'] == 'final-host-ceiling-v1', 'final profile required')
    rows = json.loads((source / 'sources.json').read_text())
    expected = {row['repository']: row['commit'] for row in selected['sources']}
    inherited.require(len(selected['sources']) == len(expected) == 11 and
                      {row['repository']: row['commit'] for row in rows} == expected,
                      'exact eleven selected origin commits required')
    inherited.require(inherited.sha(source / 'sources.json') == selected['source_provenance_sha256'],
                      'selected provenance differs')
    inherited.require(inherited.sha(source / 'vendor-sources.json') == selected['vendor_sha256'] == inherited.VENDOR,
                      'Triton vendor inventory changed')
    return dict(status='passed', scope='Exact production source impact only; final native gates remain separate and full198 inheritance needs actual binary equality',
                source_provenance_sha256=inherited.sha(source / 'sources.json'), selector_sha256=inherited.sha(inputs),
                script_sha256=inherited.sha(Path(__file__)), **compare_rows(rows, references))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--references', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    result = check(args.source, args.inputs, args.references)
    with args.receipt.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], source_provenance_sha256=result['source_provenance_sha256'])))


if __name__ == '__main__':
    main()
