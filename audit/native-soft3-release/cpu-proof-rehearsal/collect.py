#!/usr/bin/env python3
"""Retain completed local CPU/proof evidence without changing any measured file."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'unpacked/cyber-source'
OUT = ROOT / 'cpu-proof-delivery'


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def file_identity(path):
    with path.open('rb') as stream:
        return dict(bytes=path.stat().st_size,
                    sha256=hashlib.file_digest(stream, 'sha256').hexdigest())


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


report = json.loads((ROOT / 'cpu-and-proofs.json').read_text())
require(report['status'] in ('passed', 'failed'), 'original driver must have finished')
require(not OUT.exists() and not OUT.is_symlink(), 'fresh delivery required')
paths = {p.relative_to(ROOT).as_posix(): p for folder in ('cpu-results', 'baseline-proofs')
         for p in sorted((ROOT / folder).iterdir()) if p.is_file()}
for name in ('cpu-and-proofs.py', 'cpu-and-proofs.json'):
    paths[name] = ROOT / name
for name in ('candidate.json', 'source-verification.json'):
    paths['metadata/' + name] = ROOT / 'candidate пробел' / name
paths['metadata/sources.json'] = SOURCE / 'sources.json'
for name in ('prepare.json', 'build.json', 'smoke.json'):
    paths['metadata/' + name] = ROOT / name
for name in ('z3.json', 'z3.stdout', 'z3.stderr'):
    path = ROOT / 'tools' / name
    if path.exists():
        paths['metadata/' + name] = path
for name in ('check-baselines.py', 'native-candidate.py', 'verify-source.py'):
    paths['source/' + name] = SOURCE / 'trisha/scripts' / name
paths['source/bench.rs'] = SOURCE / 'trisha/cli/bench.rs'
members = {name: path.read_bytes() for name, path in paths.items()}
prepare = json.loads(members['metadata/prepare.json'])
tools_end = dict(scope='Supplemental post-run hashes made by this collector', tools={})
for name in ('cargo', 'rustc'):
    row = prepare['tool_paths'][name]
    current = file_identity(Path(row['actual_toolchain']))
    tools_end['tools'][name] = dict(path=row['actual_toolchain'], start_sha256=row['sha256'],
                                    end=current, unchanged=current['sha256'] == row['sha256'])
z3 = json.loads(members['metadata/z3.json'])['binary']
current = file_identity(Path(z3['path']))
tools_end['tools']['z3'] = dict(path=z3['path'], start_sha256=z3['sha256'], end=current,
                              unchanged=current['sha256'] == z3['sha256'])
members['metadata/tools-end.json'] = (json.dumps(tools_end, indent=2, sort_keys=True) + '\n').encode()
require(len(members) <= 128 and sum(map(len, members.values())) < 64 << 20, 'retention byte/count bound')
tar_buffer = io.BytesIO()
with tarfile.open(fileobj=tar_buffer, mode='w', format=tarfile.USTAR_FORMAT) as tar:
    for name, data in sorted(members.items()):
        info = tarfile.TarInfo(name)
        info.size, info.mode, info.mtime = len(data), 0o644, 0
        info.uid = info.gid = 0
        tar.addfile(info, io.BytesIO(data))
raw = tar_buffer.getvalue()
compressed = gzip.compress(raw, compresslevel=9, mtime=0)
require(len(compressed) <= 32 << 20, 'unexpected archive growth: review chunking before publishing')
external = {}
for name in ('source-export.tar.gz', 'cyber-tools-aarch64-apple-darwin.tar.gz',
             'proof-corpus-aarch64-apple-darwin.tar.gz'):
    external[name] = dict(original_path=str(ROOT / name), **file_identity(ROOT / name))
index = dict(schema='local/cpu-proof-retention/v1', archive=identity(compressed), tar=identity(raw),
             files={name: identity(data) for name, data in sorted(members.items())},
             external_containers=external,
             installed_evidence=dict(repository='trisha', revision='f512e87e197df477eb4b8d952886f5d3a38a1d2b',
                 path='audit/native-soft3-release/installed-rehearsal/',
                 files_sha256='420caa7fbcca506da6cfdb9db11dd73abedcc9d11aeafef544a97d9ef1a84d97',
                 receipt_sha256='d6a61584758d41353662f26e34bddb5362f51f25e630e330eca9baf5e11c1ec7'),
             collector=file_identity(Path(__file__)), checker=file_identity(ROOT / 'check-cpu-proof-retention.py'))
OUT.mkdir()
with (OUT / 'raw-evidence.tar.gz').open('xb') as stream:
    stream.write(compressed)
write_json(OUT / 'files.json', index)
for original, final in [('check-cpu-proof-retention.py', 'check.py'),
                        ('collect-cpu-proof-retention.py', 'collect.py')]:
    with (OUT / final).open('xb') as stream:
        stream.write((ROOT / original).read_bytes())
require(all(path.read_bytes() == members[name] for name, path in paths.items()), 'original evidence changed during collection')
print(json.dumps(dict(directory=str(OUT), raw_files=len(members), raw_bytes=sum(map(len, members.values())),
                      archive=identity(compressed), original_status=report['status']), indent=2))
