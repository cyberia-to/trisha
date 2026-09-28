"""Root review of the original archived CPU/proof logs and exact retained copies."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile

R = Path('/Users/master/cyber/.worktrees/selfhost-0.4-full-bootstrap')
ROOT = R / 'measurements/coordinated-soft3-release-3'
DELIVERY = ROOT / 'cpu-proof-delivery'
SOURCE = ROOT / 'unpacked/cyber-source'
OUT = R / 'measurements/coordinated-soft3-release-3-cpu-proof-root-review.json'

def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

index = json.loads((DELIVERY / 'files.json').read_bytes())
for row in json.loads((DELIVERY / 'delivery-files.json').read_bytes()):
    assert identity((DELIVERY / row['path']).read_bytes()) == {k: row[k] for k in ('bytes', 'sha256')}
paths = {p.relative_to(ROOT).as_posix(): p for folder in ('cpu-results', 'baseline-proofs')
         for p in (ROOT / folder).iterdir() if p.is_file()}
for name in ('cpu-and-proofs.py', 'cpu-and-proofs.json'):
    paths[name] = ROOT / name
for name in ('candidate.json', 'source-verification.json'):
    paths['metadata/' + name] = ROOT / 'candidate пробел' / name
paths['metadata/sources.json'] = SOURCE / 'sources.json'
for name in ('prepare.json', 'build.json', 'smoke.json'):
    paths['metadata/' + name] = ROOT / name
for name in ('z3.json', 'z3.stdout', 'z3.stderr'):
    if (ROOT / 'tools' / name).exists():
        paths['metadata/' + name] = ROOT / 'tools' / name
for name in ('check-baselines.py', 'native-candidate.py', 'verify-source.py'):
    paths['source/' + name] = SOURCE / 'trisha/scripts' / name
paths['source/bench.rs'] = SOURCE / 'trisha/cli/bench.rs'
contents = {}
with tarfile.open(DELIVERY / 'raw-evidence.tar.gz', 'r:gz') as tar:
    for member in tar:
        assert member.isfile() and member.name not in contents
        assert member.mode == 0o644 and member.uid == member.gid == member.mtime == 0
        raw = tar.extractfile(member).read()
        assert identity(raw) == index['files'][member.name]
        if member.name != 'metadata/tools-end.json':
            assert raw == paths[member.name].read_bytes(), member.name
        contents[member.name] = raw
assert set(contents) == set(paths) | {'metadata/tools-end.json'} == set(index['files'])
for row in index['external_containers'].values():
    assert identity(Path(row['original_path']).read_bytes()) == {k: row[k] for k in ('bytes', 'sha256')}
tools = json.loads(contents['metadata/tools-end.json'])['tools']
for name, row in tools.items():
    assert identity(Path(row['path']).read_bytes()) == row['end'] and row['unchanged'] is True
driver = json.loads(contents['cpu-and-proofs.json'])
for name, row in driver['binaries_end'].items():
    assert identity((ROOT / 'candidate пробел/bin' / name).read_bytes()) == row
for name in ('check-baselines.py', 'native-candidate.py', 'verify-source.py', 'bench.rs'):
    path = 'cli/bench.rs' if name == 'bench.rs' else 'scripts/' + name
    original = subprocess.check_output(['git', 'show', '13c5c24b93d7136624d8725f911b2aa45a175129:' + path],
                                      cwd=R / 'portable-native-smoke/trisha')
    assert contents['source/' + name] == original
memory = [json.loads(line) for line in contents['baseline-proofs/memory.jsonl'].splitlines()]
proof = json.loads(contents['baseline-proofs/receipt.json'])
assert len(memory) == 791 and max(row['rss_bytes'] for row in memory) == proof['peak_rss_bytes'] == 19917635584
installed = R / 'portable-native-smoke/trisha/audit/native-soft3-release/installed-rehearsal'
assert identity((installed / 'files.json').read_bytes())['sha256'] == index['installed_evidence']['files_sha256']
assert identity((installed / 'receipt.json').read_bytes())['sha256'] == index['installed_evidence']['receipt_sha256']
report = dict(status='passed', driver=identity(Path(__file__).read_bytes()),
              archive=identity((DELIVERY / 'raw-evidence.tar.gz').read_bytes()),
              delivery_index=identity((DELIVERY / 'delivery-files.json').read_bytes()),
              raw_members=len(contents), raw_bytes=sum(map(len, contents.values())),
              original_files_compared=len(paths), supplemental_tool_hashes_compared=len(tools),
              source_git_revision='13c5c24b93d7136624d8725f911b2aa45a175129',
              memory_samples=len(memory), peak_rss_bytes=proof['peak_rss_bytes'],
              baseline_proof_payloads_retained=False,
              scope='Independent exact originals/Git/tool/binary/metadata review; no proof rerun')
assert not OUT.exists()
OUT.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
