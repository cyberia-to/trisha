"""Read only actual accepted-kit evidence; never run a compiler or guest."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import zipfile

sys.dont_write_bytecode = True
R = Path('/Users/master/cyber/.worktrees/selfhost-0.4-full-bootstrap')
HERE = Path(__file__).resolve().parent
D = R / 'measurements/accepted-selfhost-kit/delivery'
FINAL = R / 'measurements/ci-phases-final-acceptance'
TRISHA = R / 'trisha-selfhost-kit'
OLD = R / 'measurements/selfhost-source-execution'


def require(value, label):
    if not value:
        raise ValueError(label)


def identity(path):
    require(path.is_file() and not path.is_symlink(), 'ordinary input ' + str(path))
    with path.open('rb') as stream:
        return dict(bytes=path.stat().st_size, sha256=hashlib.file_digest(stream, 'sha256').hexdigest())


def load(path):
    return json.loads(path.read_bytes())


def same(row):
    return {k: row[k] for k in ('bytes', 'sha256')}


def tar_equal(archive, prefix, root):
    seen = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            require(member.isfile() or member.isdir(), 'ordinary package member')
            if member.isdir():
                continue
            require(member.name.startswith(prefix + '/'), 'package prefix')
            name = member.name[len(prefix) + 1:]
            require(name not in seen, 'duplicate package file')
            seen.add(name)
            require(tar.extractfile(member).read() == (root / name).read_bytes(), 'package bytes ' + name)
    require(seen == {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}, 'complete package tree')
    return len(seen)


report = dict(schema='trident/accepted-kit-independent-review/v1', status='running',
              started_ns=time.time_ns(), reviewer=identity(Path(__file__)), findings=[])
try:
    receipt = load(D / 'receipt.json')
    require(identity(D / 'receipt.json')['sha256'] == 'ca60b94f17441a22aa2d1afc8fd4ed02382d46935fcad00f4c53f45ee6ca5b04', 'reviewed delivery receipt')
    require(receipt['status'] == 'passed' and receipt['inputs_start'] == receipt['inputs_end'], 'complete stable delivery')
    require(identity(D.parent / 'run.py') == receipt['driver'] and receipt['driver']['sha256'] == 'f2387607d48577bd94ca1b3fe3a87dd8a0e508a385af2acbce852d856b2c2aa0', 'frozen driver')
    start = receipt['inputs_start']
    for name, row in start['scripts'].items():
        path = TRISHA / 'scripts' / name
        require(identity(path) == row, 'current reviewed script ' + name)
        raw = subprocess.check_output(['git', 'show', start['revision'] + ':scripts/' + name], cwd=TRISHA)
        require(raw == path.read_bytes(), 'exact 4b81 script Git bytes')
    expected_commands = ['assemble', 'unpack-kit', 'check-kit', 'installed-smoke', 'check-installed-smoke',
                         'package', 'repack', 'unpacked-smoke', 'check-unpacked-smoke', 'prepare-default',
                         'pack-full-source', 'source-guard-after']
    require([row['name'] for row in receipt['commands']] == expected_commands, 'all twelve real outer routes')
    for row in receipt['commands']:
        require(row['status'] == 'completed' and row['exit_code'] == 0, 'outer route completion')
        for key in ('stdout', 'stderr'):
            require(identity(D / (row['name'] + '.' + key)) == row[key], 'retained command logs')
    original = load(FINAL / 'validation/verification.json')
    require(identity(FINAL / 'validation/verification.json') == receipt['original_validation'], 'original final proof bytes')
    require(receipt['original_validation']['sha256'] == 'be6d76f37c0daf9694e75dad83e200adc25a32b05e593fdbeec11f4d67a69f81', 'external original proof pin')
    proof = load(D / 'assembly/validation/verification.json')
    assembly = load(D / 'assembly/command.json')
    config = load(D / 'authority-config.json')
    require(proof['status'] == original['status'] == 'passed' and len(proof['phases']) == 36, 'actual complete final authority')
    for key in ('phases', 'expected_origin', 'expected', 'indices', 'compiler_sha256', 'native_repetitions', 'native_corpus_jobs', 'validator_sha256'):
        require(proof[key] == original[key], 'same original authority input/result ' + key)
    require(proof['native_repetitions'] == 12 and proof['native_corpus_jobs'] == 24, 'original 36 phases')
    require(assembly['exit_code'] == 0 and assembly['validator'] == start['validator'] and
            assembly['config'] == identity(D / 'authority-config.json'), 'actual fresh authority command')
    require(identity(Path(assembly['argv'][4])) == start['validator'] and
            start['validator']['sha256'] == '72cd11ec62e410e908590a785c79011989ea2c6c32872c5db31d72a62947c0ec', 'exact authority implementation')
    require(identity(Path(config['indices']))['sha256'] == config['indices-sha256'], 'frozen three-store index snapshot')
    require(proof['local_command']['exit_code'] == 0 and
            load(D / 'assembly/validation/local-replay/receipt.json')['status'] == 'passed', 'fresh unchanged phase validator replay')
    for row in proof['phases']:
        require(identity(Path(config['restored']) / row['name'] / 'receipt.json') == same(row['receipt']), 'all original producer/consumer receipts')
    for key, row in proof['original_aggregate'].items():
        require(identity(Path(row['path'])) == same(row), 'original aggregate input ' + key)
        require(same(row) == same(original['original_aggregate'][key]), 'original aggregate equality ' + key)
    with zipfile.ZipFile(proof['original_aggregate']['zip']['path']) as archive:
        require(archive.read('receipt.json') == (D / 'kit/aggregate.json').read_bytes(), 'original aggregate ZIP bytes')
    kit = load(D / 'kit/kit.json')
    producer_root = Path(config['restored']) / config['producer-name']
    require(kit['producer']['name'] == config['producer-name'], 'explicit selected producer')
    producer = load(producer_root / 'receipt.json')
    require((D / 'kit/producer.json').read_bytes() == (producer_root / 'receipt.json').read_bytes(), 'original producer receipt bytes')
    c2 = producer['repetitions'][0]['c2']
    require(c2['path'] == kit['producer']['compiler_path'] == 'repeat-1/c2.dag' and
            (producer_root / c2['path']).read_bytes() == (D / 'kit/compiler.dag').read_bytes(), 'true selected C2 output')
    require(identity(D / 'selfhost-kit.tar.gz') == receipt['kit_archive'], 'portable kit archive binding')
    kit_members = tar_equal(D / 'selfhost-kit.tar.gz', 'trident-selfhost', D / 'kit')
    package = D / 'unpacked/cyber-tools'
    require((D / 'package.tar.gz').read_bytes() == (D / 'repack.tar.gz').read_bytes() and
            identity(D / 'package.tar.gz') == receipt['binary_archive'], 'exact deterministic package bytes')
    package_members = tar_equal(D / 'package.tar.gz', 'cyber-tools', package)
    for path in (D / 'kit').iterdir():
        require(path.read_bytes() == (package / 'share/trident-selfhost' / path.name).read_bytes(), 'shipped exact kit files')
    candidate = R / 'measurements/coordinated-soft3-release-3/candidate пробел'
    for name, row in start['binaries'].items():
        require(identity(candidate / 'bin' / name) == identity(package / 'bin' / name) == row, 'exact installed/unpacked binary')
    spec = importlib.util.spec_from_file_location('kit_evidence_only', TRISHA / 'scripts/selfhost_kit.py')
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    source = Path(start['source']) / 'trident'
    smoke_reports = {}
    for name, root, joy in [('installed-smoke', D / 'kit', candidate / 'bin/joy'),
                            ('unpacked-smoke', package / 'share/trident-selfhost', package / 'bin/joy')]:
        require(checks.check(root, source)['status'] == 'accepted', 'production accepted-kit validation')
        smoke = checks.smoke_evidence(root, joy, D / name / 'receipt.json')
        require(smoke['kit_status'] == 'accepted' and len(smoke['commands']) == 5, 'both actual five-route smokes')
        smoke_reports[name] = dict(receipt=identity(D / name / 'receipt.json'), commands=5,
                                  exits=[r['exit_code'] for r in smoke['commands']], answer=smoke['answer'], joy=same(smoke['joy']))
    prepared = load(D / 'prepared/receipt.json')
    require(prepared['status'] == 'prepared' and prepared['kit_status'] == 'accepted' and
            prepared['rehearsal_requested'] is False, 'default accepted preparation')
    require(prepared['implementation'] == start['helper'] and len(prepared['sources']) == 94, 'frozen helper and all sources')
    for row in prepared['sources'].values():
        require(identity(source / row['path']) == identity(D / 'prepared' / row['copy']) == same(row), '94 exact prepared source copies')
    for name, row in prepared['files'].items():
        require(identity(D / 'prepared' / name) == row, 'prepared output bytes')
    old = load(OLD / 'receipt.json')
    require(identity(OLD / 'receipt.json') == receipt['reused_full_execution'] == start['previous_full_execution'], 'reviewed previous full execution')
    require(old['status'] == 'passed' and old['exact_c3_c2_bytes_equal'] is True and old['non_time_execution_fields_equal'] is True, 'actual earlier self-build success')
    require(old['host_flags'] == prepared['host_flags'], 'same declared physical host limits')
    for name, row in receipt['prepared_bridge'].items():
        require(identity(D / 'prepared' / name) == old['inputs_start']['files'][name] == row, 'all three full execution input bridges')
    require(identity(package / 'bin/joy') == old['binary_end'] == same(old['binary']), 'same previous actual runtime')
    require(identity(OLD / 'c3.dag') == old['output'] == identity(D / 'prepared/compiler.dag'), 'actual previous C3 byte identity')
    for row in old['commands']:
        require(row['status'] == 'completed' and row['exit_code'] == 0, 'previous full compiler actual exit')
    require(receipt['additional_heavy_guest_runs'] == 0, 'no extra full execution claim')
    require(identity(D / 'receipt.json')['sha256'] == 'ca60b94f17441a22aa2d1afc8fd4ed02382d46935fcad00f4c53f45ee6ca5b04', 'unchanged reviewed receipt')
    report.update(status='clear', receipt=identity(D / 'receipt.json'), driver=receipt['driver'],
                  original_acceptance=receipt['original_validation'], fresh_authority=identity(D / 'assembly/validation/verification.json'),
                  outer_commands=12, original_phases=36, producer=kit['producer'], kit=receipt['kit_archive'],
                  kit_manifest=receipt['kit_manifest'], kit_file_members=kit_members, package=receipt['binary_archive'],
                  package_file_members=package_members, deterministic_package_bytes_equal=True, smokes=smoke_reports,
                  default_accepted_preparation=identity(D / 'prepared/receipt.json'), prepared_source_files=94,
                  exact_full_run_bridge=receipt['prepared_bridge'], prior_full_execution=receipt['reused_full_execution'],
                  prior_elapsed_micros=old['elapsed_micros'], host_limits_equal=True,
                  scope='Evidence-only review. Actual accepted kit and local installed/unpacked runtime compatibility; prior full self-build linked by exact compiler/JOB/package/runtime/limits identity. No new guest execution, proof, native CI or release publication.')
except BaseException as error:
    report.update(status='failed', error=type(error).__name__ + ': ' + str(error))
    raise
finally:
    report['ended_ns'] = time.time_ns()
    with (HERE / 'review.json').open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
