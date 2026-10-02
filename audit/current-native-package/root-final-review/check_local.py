"""Independently replay the immutable source734 Mac proof evidence."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / 'trisha-native-ci/audit/current-native-package/local-full198'
OUT = Path(__file__).resolve().parent / 'local-replay.json'

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def load(path):
    return json.loads(path.read_bytes())

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

retention = load(AUDIT / 'retention.json')
archive = ROOT / 'measurements/local-rust189-complete' / retention['archive']['path']
assert sha(archive) == retention['archive']['sha256'] == '54db68904fc8c92f1446c46cb7b90345a05e026a92b46e6ccb259822a3328204'
assert archive.stat().st_size == retention['archive']['bytes'] == 85557916
expected = {row['path']: row for row in retention['files']}
assert len(expected) == len(retention['files'])
seen = set()
with tarfile.open(archive) as tar:
    for member in tar:
        assert member.isfile() and member.name in expected and member.name not in seen
        assert not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
        row = expected[member.name]
        stream = tar.extractfile(member)
        with stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert member.size == row['bytes'] and digest == row['sha256']
        seen.add(member.name)
assert seen == set(expected)
receipt = load(AUDIT / 'baseline-receipt.json')
candidate = load(AUDIT / 'candidate.json')
driver = load(AUDIT / 'driver.json')
started_bytes = gzip.decompress((AUDIT / 'started.json.gz').read_bytes())
bench_bytes = gzip.decompress((AUDIT / 'bench.log.gz').read_bytes())
started = json.loads(started_bytes)
assert hashlib.sha256(started_bytes).hexdigest() == receipt['started_sha256']
assert hashlib.sha256(bench_bytes).hexdigest() == receipt['log_sha256']
assert receipt['all_checks_passed'] is True and receipt['exit_code'] == 0
assert receipt['guard_stop'] is None and receipt['inputs_unchanged'] is True
assert receipt['evidence_error'] is None
assert driver['status'] == 'passed' and driver['exit_code'] == 0
assert driver['resource_stopped'] is False
assert started['candidate'] == candidate
assert receipt['binaries'] == {row['name']: row['sha256'] for row in candidate['binaries']}
assert receipt['binaries']['trisha'] == '2b096706c9b6905e960d19c93903c1b0e8ea203d21893838dbfa650ca1e0c25a'
assert started['command'][1] == 'bench' and started['command'][-1] == '--full'
assert sha(Path(started['command'][0])) == receipt['binaries']['trisha']
source = Path(candidate['source'])
checker = source / 'trisha/scripts/check-baselines.py'
assert sha(checker) == started['script_sha256']
events = module('baseline_reader', checker).checked_log(bench_bytes.decode(), started['fixtures'], len(started['baselines']))
assert events == receipt['verified_proof_events'] and len(events) == receipt['fresh_verified_proofs'] == 198
assert len(started['baselines']) == 43
assert sum(not row['negative'] for row in started['fixtures']) == receipt['positive_fixtures_passed'] == 99
assert sum(row['negative'] for row in started['fixtures']) == receipt['negative_fixtures_rejected'] == 34
for row in started['fixtures']:
    assert sha(source / row['path']) == row['sha256']
assert module('source_reader', source / 'trisha/scripts/verify-source.py').verify(source) == load(AUDIT / 'source-verification.json')
assert sha(source / 'sources.json') == receipt['source_provenance_sha256'] == candidate['provenance_sha256']
samples = [json.loads(line) for line in gzip.decompress((AUDIT / 'memory.jsonl.gz').read_bytes()).splitlines()]
assert max(row['rss_bytes'] for row in samples) == receipt['peak_rss_bytes'] <= started['rss_limit_bytes'] == 28 * 1024**3
assert all(row['memory_free_percent'] is None or row['memory_free_percent'] >= 8 for row in samples)
report = dict(status='passed', scope='Read-only replay of original source734 local full198 receipt and complete original archive; no new proofs or later Joy coverage',
    source_revision=driver['bootstrap_revision'], command=started['command'], binaries=receipt['binaries'],
    full198_receipt_sha256=sha(AUDIT / 'baseline-receipt.json'), archive=retention['archive'], members=len(seen),
    verified_events=len(events), resource_samples=len(samples), peak_rss_bytes=receipt['peak_rss_bytes'],
    checker_sha256=sha(checker), replay_sha256=sha(Path(__file__)))
with OUT.open('x') as stream:
    stream.write(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(status='passed', members=len(seen), verified_events=len(events))))
