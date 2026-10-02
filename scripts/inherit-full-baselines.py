"""Carry original full198 coverage only to identical Trisha bytes and inputs.

Exit 0 means inherited coverage; 3 requires a fresh gate; invalid evidence fails.
The original proof observation is never represented as a fresh measurement.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

PROVENANCE = '3c6f2ced084812e73f97c069169f83807fc5d389e54b581dd52f10982cd5b227'
SOURCE = '734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e'
EVIDENCE = '54db68904fc8c92f1446c46cb7b90345a05e026a92b46e6ccb259822a3328204'
TRISHA = '2b096706c9b6905e960d19c93903c1b0e8ea203d21893838dbfa650ca1e0c25a'
VENDOR = 'cf324959661a85fc94cf4345beaf5dbf274c1dbd5fc66960155e0750ace35d1b'
REPORTING = ('.claude/plans/', 'audit/', 'docs/', 'roadmap/', 'reference/', '.github/')
AUTOMATION = {
    'scripts/native-candidate.py', 'scripts/prepare-native-rehearsal.py',
    'scripts/transport-native-rehearsal.py', 'scripts/test_transport_native_rehearsal.py',
    'scripts/native-rehearsal-local.py', 'scripts/native-rehearsal-local-transport.py',
    'scripts/native-rehearsal-macos-floor.py', 'scripts/current-source-impact.py',
    'scripts/current-structured-corpus.py',
}
REPOSITORIES = {'bbg', 'hemera', 'honeycrisp', 'joy', 'lens', 'neuron', 'nox',
                'strata', 'trident', 'trisha', 'zheng'}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(row):
    result = {}
    for entry in row['files']:
        path = entry['path']
        if row['repository'] in ('trident', 'trisha') and (path.startswith(REPORTING) or path == '.gitattributes'):
            continue
        if row['repository'] == 'trisha' and path in AUTOMATION:
            continue
        require(path not in result, 'duplicate protected inventory path')
        result[path] = {key: entry[key] for key in ('type', 'sha256', 'bytes')}
    return result


def compare_sources(current, previous):
    require(len(current) == len(previous) == 11
            and all(row['mode'] == 'committed' for row in current + previous),
            'eleven committed inventory rows required')
    current = {row['repository']: row for row in current}
    previous = {row['repository']: row for row in previous}
    require(set(current) == set(previous) == REPOSITORIES, 'eleven repositories required')
    changes = []
    checked = []
    for name in sorted(REPOSITORIES - {'joy'}):
        before, after = inventory(previous[name]), inventory(current[name])
        changed = sorted(path for path in before.keys() | after.keys()
                         if before.get(path) != after.get(path))
        changes.extend(name + '/' + path for path in changed)
        checked.append(dict(repository=name, files=len(after),
                            sha256=digest(json.dumps(after, sort_keys=True).encode())))
    return changes, checked


def check(candidate_root, evidence, references):
    require(sha(evidence) == EVIDENCE, 'original full198 archive identity differs')
    previous_raw = gzip.decompress((references / 'source734-sources.json.gz').read_bytes())
    require(digest(previous_raw) == PROVENANCE, 'original source inventory identity differs')
    with tarfile.open(evidence) as archive:
        def raw(name):
            member = archive.getmember(name)
            require(member.isfile(), 'original evidence member is not a file')
            return archive.extractfile(member).read()
        started_raw = raw('release-results/baselines/started.json')
        log_raw = raw('release-results/baselines/bench.log')
        memory_raw = raw('release-results/baselines/memory.jsonl')
        receipt = json.loads(raw('release-results/baselines/receipt.json'))
        started = json.loads(started_raw)
        original = json.loads(raw('release-results/candidate.json'))
        source_receipt = raw('release-results/source-verification.json')
        driver = json.loads(raw('driver.json'))
    require(driver['status'] == 'passed' and driver['exit_code'] == 0
            and driver['resource_stopped'] is False, 'original worker failed')
    require(receipt['all_checks_passed'] is True and receipt['exit_code'] == 0
            and receipt['guard_stop'] is None and receipt['inputs_unchanged'] is True
            and receipt['evidence_error'] is None, 'original full198 gate failed')
    require(receipt['source_provenance_sha256'] == original['provenance_sha256'] == PROVENANCE
            and original['source_verified'] is True
            and digest(source_receipt) == original['source_verification_sha256']
            and json.loads(source_receipt)['manifests']['vendor-sources.json'] == VENDOR,
            'original source receipt differs')
    original_binaries = {row['name']: row['sha256'] for row in original['binaries']}
    require(original_binaries == receipt['binaries'] and original_binaries['trisha'] == TRISHA
            and started['candidate'] == original, 'original tested binaries differ')
    require(digest(started_raw) == receipt['started_sha256']
            and digest(log_raw) == receipt['log_sha256'], 'original proof streams differ')
    checker = references / 'source734-check-baselines.py'
    require(sha(checker) == started['script_sha256'], 'original proof checker differs')
    events = load_module('original_full198', checker).checked_log(
        log_raw.decode(), started['fixtures'], len(started['baselines']))
    require(events == receipt['verified_proof_events'] and len(events) == 198
            and receipt['fresh_verified_proofs'] == 198
            and receipt['positive_fixtures_passed'] == 99
            and receipt['negative_fixtures_rejected'] == 34, 'original proof coverage differs')
    samples = [json.loads(line) for line in memory_raw.splitlines()]
    require(samples and max(row['rss_bytes'] for row in samples) == receipt['peak_rss_bytes']
            and receipt['peak_rss_bytes'] <= started['rss_limit_bytes'] == 28 * 1024**3,
            'original resource observations differ')
    require(all(row['memory_free_percent'] is None or row['memory_free_percent'] >= 8
                for row in samples), 'original host memory bound failed')
    candidate_raw = (candidate_root / 'candidate.json').read_bytes()
    candidate = json.loads(candidate_raw)
    source = Path(candidate['source']).resolve(strict=True)
    verification = (candidate_root / 'source-verification.json').read_bytes()
    require(candidate['source_verified'] is True
            and digest(verification) == candidate['source_verification_sha256']
            and sha(source / 'sources.json') == candidate['provenance_sha256'],
            'final candidate source binding differs')
    verifier = load_module('final_source_verifier', source / 'trisha/scripts/verify-source.py')
    require(verifier.verify(source) == json.loads(verification), 'final physical source inventory differs')
    binaries = {row['name']: row['sha256'] for row in candidate['binaries']}
    require(set(binaries) == {'trident', 'trident-lsp', 'trisha', 'joy'}, 'four final binaries required')
    for name, expected in binaries.items():
        executable = candidate_root / 'bin' / (name + ('.exe' if (candidate_root / 'bin' / (name + '.exe')).exists() else ''))
        require(sha(executable) == expected, 'final actual binary differs from candidate: ' + name)
    changed, protected = compare_sources(json.loads((source / 'sources.json').read_bytes()),
                                         json.loads(previous_raw))
    reasons = ['protected input differs: ' + path for path in changed]
    if binaries['trisha'] != TRISHA:
        reasons.append('actual Trisha executable is not byte-identical to original198 worker')
    if sha(source / 'vendor-sources.json') != VENDOR:
        reasons.append('vendored dependency inventory differs')
    if sha(source / 'trisha/scripts/check-baselines.py') != started['script_sha256']:
        reasons.append('full proof checker differs')
    for fixture in started['fixtures']:
        if not (source / fixture['path']).is_file() or sha(source / fixture['path']) != fixture['sha256']:
            reasons.append('original baseline fixture differs: ' + fixture['path'])
    return dict(status='needs_fresh_full198' if reasons else 'inherited_full198_coverage',
                scope='Exact original Trisha executable and protected inputs only; changed Joy has separate native gates',
                fresh_run_performed=False, inherited_verified_proofs=None if reasons else 198,
                reasons=reasons, final_candidate_sha256=digest(candidate_raw),
                final_provenance_sha256=candidate['provenance_sha256'], final_binaries=binaries,
                protected_inventories=protected,
                original=dict(source_sha256=SOURCE, provenance_sha256=PROVENANCE,
                              evidence_sha256=EVIDENCE, candidate=original,
                              worker_revision=driver['bootstrap_revision'], command=started['command'],
                              receipt=receipt, memory_stream_sha256=digest(memory_raw)),
                checker_sha256=sha(Path(__file__)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--reference-archive', required=True, type=Path)
    parser.add_argument('--references', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = check(args.candidate, args.reference_archive, args.references)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'fresh_run_performed', 'inherited_verified_proofs', 'reasons')}))
    return 3 if result['reasons'] else 0


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    raise SystemExit(main())
