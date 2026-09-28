#!/usr/bin/env python3
"""Retain completed installed evidence only; never run a build or proof."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
SOURCE = ROOT / 'coordinated-soft3-release-3'
REVIEW = ROOT / 'coordinated-soft3-release-3-independent-review'
MAX_COMPRESSED = 50_000_000
CHUNK = 1024 * 1024
EXCLUDED = [
    'cpu-and-proofs.py', 'cpu-and-proofs.json', 'cpu-results/**',
    'temporary/**', 'candidate пробел/build/**',
]


def identity(path):
    h = hashlib.sha256()
    size = 0
    with path.open('rb') as src:
        while block := src.read(CHUNK):
            h.update(block)
            size += len(block)
    return {'bytes': size, 'sha256': h.hexdigest()}


def load(path):
    return json.loads(path.read_bytes())


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as dst:
        json.dump(value, dst, ensure_ascii=False, indent=2)
        dst.write('\n')


def selections():
    selected = {}

    def add(base, relative, prefix='rehearsal'):
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'expected ordinary file: {path}')
        name = f'{prefix}/{relative}'
        if name in selected:
            raise ValueError(f'duplicate selection: {name}')
        selected[name] = path

    def tree(relative):
        for path in sorted((SOURCE / relative).rglob('*')):
            if path.is_file() or path.is_symlink():
                add(SOURCE, path.relative_to(SOURCE).as_posix())

    top = [
        'prepare.py', 'build.py', 'smoke.py', 'prepare-z3.py',
        'prepare.json', 'build.json', 'smoke.json',
        'source-export.vendor-bootstrap.log',
    ]
    for stem in [
        'build-source-after', 'build-source-before', 'candidate-build',
        'cargo-absolute', 'cargo-version', 'nu-version', 'package-source',
        'python-version', 'rustc-absolute', 'rustc-version', 'source-guard',
    ]:
        top.extend([stem + '.stdout', stem + '.stderr'])
    for name in top:
        add(SOURCE, name)
    for name in ['smoke пробел', 'joy-native-smoke', 'installed-results',
                 'candidate пробел/share',
                 'unpacked/cyber-source/trisha/baselines/triton']:
        tree(name)
    for name in ['candidate.json', 'source-verification.json', 'joy-boundary.json',
                 'trident-build.log', 'trisha-build.log', 'fixture-build.log',
                 'joy-build.log']:
        add(SOURCE, 'candidate пробел/' + name)
    for path in sorted((SOURCE / 'installed/cyber-tools').rglob('*')):
        if path.is_file() and 'bin' not in path.relative_to(SOURCE / 'installed/cyber-tools').parts:
            add(SOURCE, path.relative_to(SOURCE).as_posix())
    for name in ['tools/z3.json', 'tools/z3-version.stdout', 'tools/z3-version.stderr']:
        add(SOURCE, name)
    for name in ['sources.json', 'vendor-sources.json', 'BUILD.txt']:
        add(SOURCE, 'unpacked/cyber-source/' + name)
    for name in [
        'smoke-release.nu', 'smoke-lsp.py', 'verify-corpus.py',
        'archive-source.py', 'verify-source.py', 'build-candidate.nu',
        'package-binaries.nu', 'package-source.nu', 'snapshot-source.py',
        'windows_process.py', 'release-fixture.rs',
        'fixtures/Cargo.toml', 'fixtures/Cargo.lock',
    ]:
        add(SOURCE, 'unpacked/cyber-source/trisha/scripts/' + name)
    for name in ['native-installed-probes.py', 'native-neptune-fixture.rs']:
        add(SOURCE, 'unpacked/cyber-source/trisha/audit/' + name)
    for name in ['smoke-native.py', 'check-soft3-boundary.py']:
        add(SOURCE, 'unpacked/cyber-source/joy/scripts/' + name)
    for path in sorted(REVIEW.iterdir()):
        if path.is_file():
            add(REVIEW, path.name, 'independent-review')
    return dict(sorted(selected.items()))


def external_references(prepare, smoke):
    rows = []

    def add(path, role, expected=None, binding='retention-time identity'):
        observed = identity(path)
        if expected is not None:
            for key in ['bytes', 'sha256']:
                if key in expected and observed[key] != expected[key]:
                    raise ValueError(f'changed external input: {path}')
        rows.append({'path': str(path), 'role': role, 'binding': binding, **observed})

    for name, role, expected in [
        ('source-export.tar.gz', 'complete source and vendor archive', prepare['source_archive']),
        ('cyber-tools-aarch64-apple-darwin.tar.gz', 'installed binary package', smoke['binary_archive']),
        ('repacked.tar.gz', 'byte-identical repeated binary package', smoke['binary_archive']),
        ('proof-corpus-aarch64-apple-darwin.tar.gz', 'original container; full raw tree retained', smoke['proof_corpus_archive']),
    ]:
        add(SOURCE / name, role, expected, 'original producer receipt')
    for name, expected in smoke['binary_start'].items():
        if expected != smoke['binary_end'][name]:
            raise ValueError('producer binary start/end mismatch')
        for directory in ['candidate пробел/bin', 'installed/cyber-tools/bin']:
            add(SOURCE / directory / name, 'installed executable', expected,
                'original smoke start/end and candidate receipt')
    for name, tool in prepare['tool_paths'].items():
        path = Path(tool.get('actual_toolchain', tool['resolved']))
        add(path, 'measurement tool: ' + name,
            {'sha256': tool['sha256']} if 'sha256' in tool else None,
            'producer SHA and retention recheck' if 'sha256' in tool else
            'producer path/version; SHA first recorded at retention')
    z3 = load(SOURCE / 'tools/z3.json')
    for name in ['archive', 'binary']:
        add(Path(z3[name]['path']), 'Z3 ' + name, z3[name], 'original pinned-Z3 receipt')
    return rows


def archive(path, selected):
    with path.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0, compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tar:
                for name, source in selected.items():
                    info = tarfile.TarInfo(name)
                    info.size = source.stat().st_size
                    info.mode = 0o644
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ''
                    with source.open('rb') as body:
                        tar.addfile(info, body)


def verify(path, rows, originals):
    expected = {row['path']: row for row in rows}
    seen = set()
    raw_bytes = 0
    with tarfile.open(path, 'r:gz') as tar:
        for item in tar:
            if not item.isfile() or item.name not in expected or item.name in seen:
                raise ValueError(f'unexpected archive member: {item.name}')
            if (item.mode, item.uid, item.gid, item.mtime, item.uname, item.gname) != (0o644, 0, 0, 0, '', ''):
                raise ValueError('noncanonical tar metadata')
            seen.add(item.name)
            row = expected[item.name]
            if item.size != row['bytes']:
                raise ValueError('member length mismatch')
            digest = hashlib.sha256()
            with tar.extractfile(item) as member:
                source = Path(row['original_path']).open('rb') if originals else None
                try:
                    while block := member.read(CHUNK):
                        digest.update(block)
                        raw_bytes += len(block)
                        if source is not None and source.read(len(block)) != block:
                            raise ValueError(f'byte comparison failed: {item.name}')
                    if source is not None and source.read(1):
                        raise ValueError('original longer than member')
                finally:
                    if source is not None:
                        source.close()
            if digest.hexdigest() != row['sha256']:
                raise ValueError('member digest mismatch')
    if seen != expected.keys():
        raise ValueError('missing archive members')
    return {'members': len(seen), 'raw_bytes': raw_bytes,
            'direct_original_byte_comparison': originals}


def main():
    started = time.time_ns()
    selected = selections()
    prepare, build, smoke = [load(SOURCE / name) for name in
                             ['prepare.json', 'build.json', 'smoke.json']]
    review = load(REVIEW / 'review.json')
    if any(r['status'] != 'passed' for r in [prepare, build, smoke, review]):
        raise ValueError('completed evidence not passed')
    for name, expected in review['inputs'].items():
        if identity(SOURCE / name) != expected:
            raise ValueError('reviewed input changed: ' + name)
    rows = [{'path': name, 'original_path': str(path), **identity(path)}
            for name, path in selected.items()]
    references = external_references(prepare, smoke)
    pages = []
    for start in range(0, len(rows), 250):
        name = f'files-{start // 250:02}.json'
        with (OUT / name).open('x', encoding='utf-8', newline='\n') as dst:
            dst.write('[\n' + ',\n'.join(json.dumps(row, ensure_ascii=False, sort_keys=True)
                                        for row in rows[start:start + 250]) + '\n]\n')
        pages.append({'path': name, **identity(OUT / name)})
    write_json(OUT / 'external-files.json', references)
    payload = OUT / 'installed-evidence.tar.gz'
    archive(payload, selected)
    if payload.stat().st_size > MAX_COMPRESSED:
        raise ValueError('declared compressed retention ceiling exceeded')
    comparison = verify(payload, rows, True)
    repeated = OUT / 'determinism-check.tar.gz'
    archive(repeated, selected)
    if identity(repeated) != identity(payload):
        raise ValueError('repeat archive differs')
    repeated.unlink()
    if any(identity(Path(row['original_path'])) != {key: row[key] for key in ['bytes', 'sha256']}
           for row in rows):
        raise ValueError('source changed during retention')
    checks = {check['name']: check for check in review['checks']}
    receipt = {
        'schema': 'local/installed-rehearsal-retention/v1', 'status': 'passed',
        'scope': 'Completed third installed rehearsal only; no CPU/198, SH6, platform matrix or release verdict',
        'started_ns': started, 'ended_ns': time.time_ns(),
        'command': [sys.executable, '-B', '-W', 'error', str(Path(__file__).resolve())],
        'cwd': str(OUT), 'driver': identity(Path(__file__)),
        'source_root': str(SOURCE), 'source_revisions': prepare['exported_pins'],
        'original_receipts': {name: identity(SOURCE / name) for name in
                              ['prepare.json', 'build.json', 'smoke.json']},
        'independent_review': {'path': str(REVIEW / 'review.json'), **identity(REVIEW / 'review.json')},
        'archive': {'path': payload.name, **identity(payload)},
        'manifest_pages': pages, 'external_files': {'path': 'external-files.json', **identity(OUT / 'external-files.json')},
        'verification': {**comparison, 'repeat_archive_byte_identity': True,
                         'all_original_files_unchanged': True, 'compressed_ceiling_bytes': MAX_COMPRESSED,
                         'gzip_mtime': 0, 'tar_mtime': 0, 'ordinary_files_only': True},
        'retained_review_checks': checks,
        'excluded_mutable_paths': EXCLUDED,
        'excluded_scope': ['CPU suites', '198-proof gate', 'SH6', 'other native platforms', 'release/publication'],
        'large_files_policy': 'Exact local path, size and SHA retained; executables/source and repeated archive containers are external.',
        'replay_note': 'Original JSON paths and commands remain unchanged. Restore or explicitly map roots and supply exact external executable bytes. No proof/build was run during retention.',
    }
    write_json(OUT / 'receipt.json', receipt)
    print(json.dumps({'status': 'passed', 'members': len(rows), 'archive': receipt['archive'],
                      'raw_bytes': comparison['raw_bytes']}, sort_keys=True))


if __name__ == '__main__':
    main()
