"""Bounded portable kit transport and supplied-Joy smoke; no compiler build path."""
import hashlib
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time

SCHEMA = 'trident/selfhost-kit/v1'
VALIDATOR = '72cd11ec62e410e908590a785c79011989ea2c6c32872c5db31d72a62947c0ec'
COMPILER = '76a07c08265bd2ef525164472b6b53ac3f0e6cbbedce3250c4202f40ffba34c8'
PARTICLE = '2eea2ac5f611012877b4e7291a3a6f534aee7281bb358a0b8e5fabe2ac1f9fbe'
INVENTORY = 'd35d263c7f9f27cbe7ea760a34393105ae8140dc6ab84d484151b6fe04960571'
GUIDE = {
    'sample.tri': '5011b65fb188237be5dfa07b6dec6040f7a8ac9287391f618ca96db6ea868669',
    'package.json': '7e623737987cc4d68068537ad3c3957cc04a9e6354993d120ea83df7191c7e21',
    'zero.dag': '7b658a799adf0f027ec2b44fdb463847b2ef4bf49f7f7af1166a3291781f66cd',
}
ANSWER = '348d22b1dca51095cf13e13a4674727db537c8cd07f21af53009022b5e7bb94a'
MAX_BYTES, MAX_FILES, MAX_JSON = 128 << 20, 32, 16 << 20


def require(ok, message):
    if not ok:
        raise ValueError(message)


def ordinary(path, maximum=MAX_BYTES):
    require(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= maximum,
            f'bounded ordinary file required: {path}')
    return path


def sha(path):
    with ordinary(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(path):
    return dict(bytes=ordinary(path).stat().st_size, sha256=sha(path))


def implementation():
    return {name: sha(Path(__file__).with_name(name))
            for name in ('selfhost-kit.py', 'selfhost_kit.py', 'selfhost_kit_assembly.py')}


def recorded(path, row):
    require(identity(path) == {key: row[key] for key in ('bytes', 'sha256')}, 'recorded size/SHA256')


def load(path):
    return json.loads(ordinary(path, MAX_JSON).read_bytes())


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def relative(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._/-]+', value), 'safe relative path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value and
            all(x not in ('', '.', '..') and not x.endswith('.') for x in path.parts), 'canonical relative path')
    devices = {'CON', 'PRN', 'AUX', 'NUL', *[f'{p}{i}' for p in ('COM', 'LPT') for i in range(10)]}
    require(all(x.split('.')[0].upper() not in devices for x in path.parts), 'portable relative path')
    return path


def separate(output, *inputs):
    out = output.resolve()
    require(not output.exists() and not output.is_symlink(), 'fresh output required')
    for path in inputs:
        resolved = path.resolve()
        require(not out.is_relative_to(resolved) and not resolved.is_relative_to(out), 'input/output overlap')


def files(root):
    require(root.is_dir() and not root.is_symlink(), 'ordinary kit directory')
    result, total, names = {}, 0, set()
    for index, path in enumerate(root.rglob('*'), 1):
        require(index <= MAX_FILES * 2, 'kit entry count bound')
        name = path.relative_to(root).as_posix()
        relative(name)
        require(name.casefold() not in names, 'portable distinct kit paths')
        names.add(name.casefold())
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'ordinary kit entries only')
        if stat.S_ISREG(mode):
            result[name] = identity(path)
            total += result[name]['bytes']
            require(len(result) <= MAX_FILES and total <= MAX_BYTES, 'kit file/byte bound')
    return result


def source_check(trident, source_map):
    require(isinstance(source_map, dict) and len(source_map) == 94, 'exact 94 source modules')
    paths = set()
    for row in source_map.values():
        name = str(relative(row['path']))
        require(name not in paths, 'distinct source paths')
        paths.add(name)
        path = trident / name
        require(path.resolve().is_relative_to(trident.resolve()), 'source escaped Trident')
        require(identity(path) == dict(bytes=row['source_bytes'], sha256=row['sha256']),
                f'packaged compiler source differs: {name}')


def check(root, trident=None, rehearsal=False):
    actual = files(root)
    manifest = load(root / 'kit.json')
    require(manifest['schema'] == SCHEMA, 'kit schema')
    require(manifest['status'] in (('accepted', 'rehearsal') if rehearsal else ('accepted',)),
            'production packaging requires accepted kit')
    require({k: v for k, v in actual.items() if k != 'kit.json'} == manifest['files'], 'exact kit file manifest')
    for name, digest in dict(GUIDE, **{'compiler.dag': COMPILER, 'inventory.json': INVENTORY}).items():
        require(actual[name]['sha256'] == digest, f'pinned portable input: {name}')
    require(manifest['compiler'] == dict(role='C2', particle=PARTICLE, **actual['compiler.dag']), 'C2 identity')
    fixed = load(root / 'fixed-point.json')['fixed_point']
    require(fixed['artifact_sha256'] == COMPILER and fixed['particle'] == PARTICLE and
            fixed['compiler_chain_bound'] is True and fixed['exact_artifact_bytes_equal'] is True, 'fixed-point compiler binding')
    inventory = load(root / 'inventory.json')
    require(inventory['module_count'] == 94 and set(inventory['modules']) == set(fixed['source_sha256_set']), 'inventory closure')
    if trident is not None:
        source_check(trident, fixed['source_sha256_set'])
    if manifest['status'] == 'accepted':
        proof = load(root / 'acceptance.json')
        require(proof['validator_sha256'] == VALIDATOR and proof['status'] == 'passed' and
                proof['compiler_sha256'] == COMPILER and proof['native_repetitions'] == 12 and
                proof['native_corpus_jobs'] == 24, 'pinned authority result')
        selected = manifest['producer']
        phase = next(p for p in proof['phases'] if p['name'] == selected['name'])
        recorded(root / 'producer.json', phase['receipt'])
        require(phase['receipt']['sha256'] == selected['receipt_sha256'], 'original producer receipt')
        producer = load(root / 'producer.json')
        row = producer['repetitions'][0]
        require(producer['phase'] == 'producer' and producer['status'] == 'produced' and
                row['c2']['path'] == selected['compiler_path'] and row['c2']['sha256'] == COMPILER, 'original C2 role')
        for name, entry in [('compiler.dag', row['c2']), ('inventory.json', row['inventory']),
                            ('fixed-point.json', row['fixed_point']), ('producer-files.json', producer['files']),
                            ('aggregate.json', proof['original_aggregate']['receipt']),
                            ('aggregate-files.json', proof['original_aggregate']['manifest'])]:
            recorded(root / name, entry)
        aggregate = load(root / 'aggregate.json')
        require(aggregate['phase'] == 'matrix' and aggregate['status'] == 'passed' and
                aggregate['compiler_sha256'] == COMPILER and
                aggregate['ci_origin'] == producer['ci_origin'] == proof['expected_origin'], 'original aggregate origin')
        recorded(root / 'aggregate-files.json', aggregate['files'])
        require(load(root / 'aggregate-files.json') == {}, 'original aggregate empty file manifest')
        members = {PurePosixPath(row['path'].replace('\\', '/')).parent.name: row['sha256']
                   for row in aggregate['phase_reports']}
        require(len(members) == len(aggregate['phase_reports']) == 36 and
                members[selected['name']] == selected['receipt_sha256'], 'aggregate includes original selected producer')
    return manifest


def unpack(archive, digest, output, trident, rehearsal=False):
    separate(output, archive, trident)
    require(sha(archive) == digest, 'pinned kit archive SHA256')
    # Bound raw tar bytes before tarfile can allocate a hidden PAX/GNU header.
    # The temporary file bounds disk bytes; no expanded archive is held in RAM.
    with tempfile.TemporaryFile() as raw, gzip.open(archive, 'rb') as compressed:
        remaining = MAX_BYTES + MAX_FILES * 1024 + 10240
        while chunk := compressed.read(min(1 << 20, remaining + 1)):
            remaining -= len(chunk)
            require(remaining >= 0, 'expanded tar transport bound')
            raw.write(chunk)
        raw.seek(0)
        with tarfile.open(fileobj=raw, mode='r:') as source:
            return extract(source, output, trident, rehearsal)


def extract(source, output, trident, rehearsal):
    # Inspect every header before creating any destination; never use extractall.
    entries, names, total = [], set(), 0
    for member in source:
        require(len(entries) < MAX_FILES * 2, 'archive entry count bound')
        parts = relative(member.name).parts
        require(parts[0] == 'trident-selfhost' and (member.isfile() or member.isdir()), 'kit archive prefix/type')
        require(member.name.casefold() not in names and len(parts) <= 3, 'unique bounded kit paths')
        names.add(member.name.casefold())
        total += member.size
        require(0 <= member.size <= MAX_BYTES and total <= MAX_BYTES, 'expanded kit byte bound')
        entries.append(member)
    require(len([m for m in entries if m.isfile()]) <= MAX_FILES, 'archive file count bound')
    output.mkdir(parents=True, exist_ok=False)
    for member in entries:
        destination = output.joinpath(*PurePosixPath(member.name).parts[1:])
        if member.isdir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as incoming, destination.open('xb') as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1 << 20)
    return check(output, trident, rehearsal)


def smoke(root, joy, output, trident, rehearsal=False):
    require(joy.is_absolute(), 'absolute supplied Joy path required')
    separate(output, root, joy, trident)
    manifest = check(root, trident, rehearsal)
    before = files(root)
    binary = identity(joy)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='trident/selfhost-kit-smoke/v1', status='running', kit_status=manifest['status'],
                  kit_manifest=identity(root / 'kit.json'), joy=dict(path=str(joy), **binary),
                  implementation=implementation(),
                  commands=[], started_ns=time.time_ns(), scope='supplied Joy distribution compatibility; no new SH6/proof acceptance')
    try:
        for name in ('compiler.dag', *GUIDE):
            shutil.copyfile(root / name, output / name)
        def run(argv, expected=0):
            index = len(report['commands'])
            stdout, stderr = output / f'{index}.stdout', output / f'{index}.stderr'
            row = dict(argv=[str(joy), *argv], cwd=str(output), status='running', started_ns=time.time_ns(), exit_code=None)
            report['commands'].append(row)
            try:
                with stdout.open('xb') as out, stderr.open('xb') as err:
                    result = subprocess.run([str(joy), *argv], cwd=output, stdout=out, stderr=err, timeout=120)
                row.update(status='completed', exit_code=result.returncode)
            except BaseException as error:
                row.update(status='failed', error=f'{type(error).__name__}: {error}')
                raise
            finally:
                row.update(ended_ns=time.time_ns(), stdout=dict(path=stdout.name, **identity(stdout)),
                           stderr=dict(path=stderr.name, **identity(stderr)))
            require(result.returncode == expected, f'Joy command {index} exit: {result.returncode}')
            if expected == 0:
                return load(stdout)
            require(ordinary(stdout, MAX_JSON).stat().st_size == 0 and
                    ordinary(stderr, MAX_JSON).read_bytes().startswith(b'error: guest compilation failed:'),
                    'rejection must be a guest compilation diagnostic')
        packed = run(['pack-job', '--compiler', 'compiler.dag', '--manifest', 'package.json', '--output', 'job.dag'])
        compiled = run(['run-artifact', 'compiler.dag', '--input', 'job.dag', '--emit', 'program', '--output', 'sample.dag'])
        executed = run(['run-artifact', 'sample.dag', '--input', 'zero.dag', '--output', 'answer.dag'])
        require(packed['ok'] is True and compiled['ok'] is True and executed['ok'] is True and
                packed['package']['compiler_particle'] == PARTICLE and
                compiled['execution']['compiler_job']['status'] == 'success', 'guest compiler success/identity')
        package = load(root / 'package.json')
        for key in ('limits', 'options'):
            require(packed['package'][key] == compiled['execution']['compiler_job'][key] == package[key],
                    'unchanged guide options/limits')
        require(identity(output / 'answer.dag') == dict(bytes=85, sha256=ANSWER), 'canonical atom 13')
        (output / 'sample.tri').write_bytes(b'program sample\nfn main() -> Field { missing }\n')
        run(['pack-job', '--compiler', 'compiler.dag', '--manifest', 'package.json', '--output', 'bad-job.dag'])
        sentinel = b'preserve existing output\n'
        (output / 'rejected.dag').write_bytes(sentinel)
        run(['run-artifact', 'compiler.dag', '--input', 'bad-job.dag', '--emit', 'program', '--output', 'rejected.dag', '--force'], 1)
        require((output / 'rejected.dag').read_bytes() == sentinel, 'rejected source preserves output')
        require(files(root) == before and identity(joy) == binary, 'runtime or kit changed during smoke')
        require(implementation() == report['implementation'], 'smoke implementation changed')
        report.update(status='passed', answer=identity(output / 'answer.dag'), rejected_output_preserved=True,
                      outputs={name: identity(output / name) for name in
                               ('job.dag', 'sample.dag', 'answer.dag', 'bad-job.dag', 'rejected.dag')})
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        report['ended_ns'] = time.time_ns()
        write(output / 'receipt.json', report)
    return report


def check_smoke(root, joy, receipt):
    tested = smoke_evidence(root, joy, receipt)
    require(tested['kit_status'] == 'accepted', 'production selfhost smoke requires accepted kit')


def smoke_evidence(root, joy, receipt):
    """Validate actual raw smoke evidence, retaining accepted/rehearsal distinction."""
    before = identity(receipt)
    tested = load(receipt)
    require(tested['schema'] == 'trident/selfhost-kit-smoke/v1' and tested['status'] == 'passed' and
            tested['kit_status'] == load(root / 'kit.json')['status'] and
            tested['kit_manifest'] == identity(root / 'kit.json') and
            {k: tested['joy'][k] for k in ('bytes', 'sha256')} == identity(joy) and
            tested['answer'] == dict(bytes=85, sha256=ANSWER) and tested['rejected_output_preserved'] is True and
            tested['implementation'] == implementation(),
            'installed selfhost smoke binding')
    routes = [
        ['pack-job', '--compiler', 'compiler.dag', '--manifest', 'package.json', '--output', 'job.dag'],
        ['run-artifact', 'compiler.dag', '--input', 'job.dag', '--emit', 'program', '--output', 'sample.dag'],
        ['run-artifact', 'sample.dag', '--input', 'zero.dag', '--output', 'answer.dag'],
        ['pack-job', '--compiler', 'compiler.dag', '--manifest', 'package.json', '--output', 'bad-job.dag'],
        ['run-artifact', 'compiler.dag', '--input', 'bad-job.dag', '--emit', 'program', '--output', 'rejected.dag', '--force'],
    ]
    require(len(tested['commands']) == len(routes), 'all five supplied-Joy commands required')
    for index, (row, route) in enumerate(zip(tested['commands'], routes)):
        require(row['argv'] == [tested['joy']['path'], *route] and row['status'] == 'completed' and
                row['exit_code'] == (1 if index == 4 else 0),
                'supplied-Joy route/exit changed')
        for key in ('stdout', 'stderr'):
            log = row[key]
            require(log['path'] == f'{index}.{key}' and identity(receipt.parent / log['path']) ==
                    {k: log[k] for k in ('bytes', 'sha256')}, 'raw smoke log binding')
    for name in ('job.dag', 'sample.dag', 'answer.dag', 'bad-job.dag', 'rejected.dag'):
        recorded(receipt.parent / name, tested['outputs'][name])
    require(identity(receipt.parent / 'answer.dag') == dict(bytes=85, sha256=ANSWER), 'retained canonical atom13')
    require((receipt.parent / 'rejected.dag').read_bytes() == b'preserve existing output\n' and
            (receipt.parent / '4.stdout').read_bytes() == b'' and
            (receipt.parent / '4.stderr').read_bytes().startswith(b'error: guest compilation failed:'), 'retained guest rejection')
    packed, compiled, executed = [load(receipt.parent / f'{n}.stdout') for n in (0, 1, 2)]
    require(packed['ok'] is True and compiled['ok'] is True and executed['ok'] is True and
            packed['package']['compiler_particle'] == compiled['execution']['program_particle'] == PARTICLE and
            packed['package']['job_particle'] == compiled['execution']['input_particle'] and
            compiled['published_particle'] == executed['execution']['program_particle'] and
            compiled['execution']['compiler_job']['status'] == 'success', 'retained execution chain')
    package = load(root / 'package.json')
    for key in ('limits', 'options'):
        require(packed['package'][key] == compiled['execution']['compiler_job'][key] == package[key],
                'retained guide options/limits')
    require(identity(receipt) == before, 'smoke receipt changed during validation')
    return tested
