"""Produce or consume bounded public structured certificates with installed Joy."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import tempfile
import traceback

SCHEMA = 'joy/current-package-structured-corpus/v1'
RAW = {'add14': 3, 'identity_tree': 1, 'loop4097': 61460}
COMPILER = {'compiler-success': ('compiler', 'job', 'result', 'success'),
            'compiler-diagnostic': ('diagnostic-compiler', 'diagnostic-job', 'diagnostic-result', 'compile_error')}
BASES = tuple(RAW) + tuple(COMPILER)
IDS = {name + '-' + suffix for name in BASES for suffix in ('valid', 'wrong-input', 'wrong-program', 'truncated', 'corrupt')}
IDS |= {'compiler-success-extract', 'compiler-diagnostic-extract'}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(path):
    return dict(bytes=path.stat().st_size, sha256=sha(path))


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def member(root, name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.parts and all(p not in ('', '.', '..') for p in path.parts), 'unsafe corpus path')
    result = root.joinpath(*path.parts)
    require(result.resolve().is_relative_to(root.resolve()) and result.is_file() and not result.is_symlink(), 'corpus member must be a contained regular file')
    return result


def candidate(root):
    metadata = json.loads((root / 'candidate.json').read_text(encoding='utf-8'))
    binary = root / 'bin' / ('joy.exe' if os.name == 'nt' else 'joy')
    entries = [row for row in metadata['binaries'] if row['name'] == 'joy']
    require(len(entries) == 1 and binary.is_file() and not binary.is_symlink() and sha(binary) == entries[0]['sha256'], 'installed Joy identity differs')
    require(metadata['toolchain'].startswith('rustc 1.89.0 ') and 'release: 1.89.0\n' in metadata['toolchain'], 'observed Rust 1.89 required')
    return metadata, binary.resolve()


def execute(binary, args, cwd, evidence, name, commands, expected):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('TRIDENT_', 'GH_', 'GITHUB_', 'GIT_CONFIG_'))}
    env['PATH'] = ''
    command = [str(binary), *map(str, args)]
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=60)
    row = dict(name=name, command=command, cwd=str(cwd), expected_exit=expected, exit_code=result.returncode)
    for field in ('stdout', 'stderr'):
        path = evidence / (name + '.' + field)
        with path.open('xb') as stream:
            stream.write(getattr(result, field))
        row[field] = dict(path=path.name, **identity(path))
    commands.append(row)
    require(result.returncode == expected, name + ' returned an unexpected exit: ' + result.stderr.decode('utf-8', errors='replace')[-4000:])
    if expected:
        require(not result.stdout and result.stderr, name + ' failed without the expected output contract')
        return None
    return json.loads(result.stdout)


def generate(source, prefix, output):
    metadata, binary = candidate(prefix)
    provenance = sha(source / 'sources.json')
    require(provenance == metadata['provenance_sha256'], 'candidate and fixture source closure differ')
    raw_path = source / 'joy/cli/tests/artifact_vectors.json'
    compiler_path = source / 'joy/cli/tests/compiler_vectors.json'
    fixtures_start = {str(p.relative_to(source)): identity(p) for p in (raw_path, compiler_path)}
    raw_vectors = {row['name']: row for row in json.loads(raw_path.read_text(encoding='utf-8'))}
    compiler_vectors = {name: bytes.fromhex(value) for name, value in json.loads(compiler_path.read_text(encoding='utf-8'))['files'].items()}
    output.mkdir()
    evidence = output / 'generation'
    evidence.mkdir()
    report = dict(status='running', scope='Bounded public installed-artifact fixtures; no whole-compiler SH7/SH8 claim', commands=[],
                  host=platform.platform(), producer_joy=identity(binary), source_provenance_sha256=provenance, script_sha256=sha(Path(__file__)))
    try:
        programs, inputs, cases = {}, {}, []
        for name in BASES:
            root = output / name
            root.mkdir()
            if name in RAW:
                vector = raw_vectors[name]
                contents = {key: bytes(vector[key]) for key in ('program', 'input', 'expected_output')}
            else:
                program, job, expected, status = COMPILER[name]
                contents = dict(program=compiler_vectors[program], input=compiler_vectors[job], expected_output=compiler_vectors[expected])
            for key, value in contents.items():
                (root / key).write_bytes(value)
            programs[name], inputs[name] = contents['program'], contents['input']
            proved = execute(binary, ['prove-artifact', 'program', '--input', 'input', '-o', 'proof'], root, evidence, name + '-prove', report['commands'], 0)
            require(proved['schema'] == 'joy/artifact-proof/v1', 'unexpected proof schema')
            if name in RAW:
                require(proved['verification']['charged_reductions'] == RAW[name], 'fixture charged cost differs')
            else:
                require(proved['verification']['compiler_job']['status'] == status, 'fixture compiler status differs')
            require((root / 'proof').stat().st_size <= 256 * 1024**2, 'bounded fixture proof exceeds corpus allowance')
            cases.append(dict(id=name + '-valid', program=name + '/program', input=name + '/input', proof=name + '/proof',
                              expected_output=name + '/expected_output', expected_exit=0, emit='result',
                              charged_reductions=RAW.get(name), compiler_status=COMPILER[name][3] if name in COMPILER else None))
            write(output / 'generation.json', report)
        for name in BASES:
            root = output / name
            (root / 'wrong-input').write_bytes(next(value for value in inputs.values() if value != inputs[name]))
            (root / 'wrong-program').write_bytes(next(value for value in programs.values() if value != programs[name]))
            proof = (root / 'proof').read_bytes()
            require(len(proof) > 1, 'empty certificate')
            (root / 'truncated').write_bytes(proof[:-1])
            (root / 'corrupt').write_bytes(bytes([proof[0] ^ 128]) + proof[1:])
            for kind in ('wrong-input', 'wrong-program', 'truncated', 'corrupt'):
                cases.append(dict(id=name + '-' + kind, program=name + ('/wrong-program' if kind == 'wrong-program' else '/program'),
                                  input=name + ('/wrong-input' if kind == 'wrong-input' else '/input'),
                                  proof=name + ('/' + kind if kind in ('truncated', 'corrupt') else '/proof'), expected_exit=1, emit='result'))
        for name, expected in [('compiler-success', 0), ('compiler-diagnostic', 1)]:
            case = dict(id=name + '-extract', program=name + '/program', input=name + '/input', proof=name + '/proof', expected_exit=expected, emit='program')
            if not expected:
                for key in ('generated', 'zero', 'fourteen'):
                    (output / name / key).write_bytes(compiler_vectors[key])
                case.update(expected_output=name + '/generated', run_input=name + '/zero', run_output=name + '/fourteen')
            cases.append(case)
        malformed = output / 'malformed-program'
        malformed.write_bytes(b'invalid artifact')
        previous = output / 'previous-proof'
        previous.write_bytes(b'previous proof')
        execute(binary, ['prove-artifact', str(malformed.resolve()), '--input', str((output / 'add14/input').resolve()), '-o', str(previous.resolve()), '--force'],
                output, evidence, 'failed-proof-publication', report['commands'], 1)
        require(previous.read_bytes() == b'previous proof', 'failed proof replaced its destination')
        require(not any(p.name.startswith('.') for p in output.iterdir()), 'failed proof left a temporary publication')
        require(identity(binary) == report['producer_joy'], 'producer binary changed')
        require(fixtures_start == {str(p.relative_to(source)): identity(p) for p in (raw_path, compiler_path)}, 'source fixtures changed')
        report['status'] = 'passed'
        write(output / 'generation.json', report)
        manifest = dict(schema=SCHEMA, source_provenance_sha256=provenance, producer_platform=metadata['platform'],
                        producer_joy_sha256=sha(binary), fixtures=fixtures_start,
                        cases=cases, files=[dict(path=p.relative_to(output).as_posix(), **identity(p)) for p in sorted(output.rglob('*')) if p.is_file()])
        write(output / 'corpus.json', manifest)
    except BaseException:
        report.update(status='failed', error=traceback.format_exc())
        write(output / 'generation.json', report)
        raise


def verify(corpus, prefix, receipt):
    metadata, binary = candidate(prefix)
    manifest_path = corpus / 'corpus.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest['schema'] == SCHEMA and manifest['source_provenance_sha256'] == metadata['provenance_sha256'], 'corpus provenance differs from consumer')
    cases = manifest['cases']
    require(len(cases) == 27 and {row['id'] for row in cases} == IDS, 'structured case inventory differs')
    require(all(type(row['expected_exit']) is int and row['expected_exit'] in (0, 1) for row in cases), 'invalid expected exit')
    require(sum(row['expected_exit'] == 0 for row in cases) == 6 and sum(row['expected_exit'] == 1 for row in cases) == 21, 'structured acceptance/rejection counts differ')
    files = manifest['files']
    require(len({row['path'] for row in files}) == len(files), 'duplicate corpus file')
    require({p.relative_to(corpus).as_posix() for p in corpus.rglob('*') if p.is_file()} == {row['path'] for row in files} | {'corpus.json'}, 'corpus file inventory differs')
    for row in files:
        path = member(corpus, row['path'])
        require(path.stat().st_size <= 256 * 1024**2 and identity(path) == {key: row[key] for key in ('bytes', 'sha256')}, 'corpus file identity differs')
    evidence = receipt.with_suffix('')
    evidence.mkdir()
    report = dict(schema='joy/current-package-structured-verification/v1', status='running', all_checks_passed=False,
                  corpus_sha256=sha(manifest_path), source_provenance_sha256=metadata['provenance_sha256'], producer_platform=manifest['producer_platform'],
                  producer_joy_sha256=manifest['producer_joy_sha256'], consumer_platform=platform.platform(), consumer_joy=identity(binary),
                  verifier_sha256=sha(Path(__file__)), cases=[], commands=[])
    try:
        with tempfile.TemporaryDirectory(prefix='structured consumer пробел ') as temporary:
            work = Path(temporary)
            for case in cases:
                require(case['emit'] in ('result', 'program'), 'unknown extraction mode')
                destination = work / 'destination'
                destination.write_bytes(b'previous destination')
                args = ['verify-artifact', member(corpus, case['program']), '--input', member(corpus, case['input']),
                        '--proof', member(corpus, case['proof']), '-o', destination, '--force']
                if case['emit'] == 'program':
                    args += ['--emit', 'program']
                value = execute(binary, args, work, evidence, case['id'], report['commands'], case['expected_exit'])
                if case['expected_exit']:
                    require(destination.read_bytes() == b'previous destination', 'rejection changed its destination')
                else:
                    require(value['schema'] == 'joy/artifact-verification/v1', 'unexpected verification schema')
                    require(value['verification']['physical_resource_claim'] == 'unattested' and value['verification'].get('prover_observations') is None, 'unexpected physical-resource claim')
                    require(destination.read_bytes() == member(corpus, case['expected_output']).read_bytes(), 'verified output differs')
                    if case.get('charged_reductions') is not None:
                        require(value['verification']['charged_reductions'] == case['charged_reductions'], 'verified cost differs')
                    if case.get('compiler_status') is not None:
                        require(value['verification']['compiler_job']['status'] == case['compiler_status'], 'verified compiler status differs')
                    if case.get('run_input'):
                        ran = work / 'ran'
                        execute(binary, ['run-artifact', destination, '--input', member(corpus, case['run_input']), '-o', ran], work, evidence, case['id'] + '-run', report['commands'], 0)
                        require(ran.read_bytes() == member(corpus, case['run_output']).read_bytes(), 'extracted program execution differs')
                require(not any(p.name.startswith('.') for p in work.iterdir()), 'verification left a temporary publication')
                report['cases'].append(dict(id=case['id'], exit_code=case['expected_exit']))
                write(receipt, report)
        require(sha(binary) == report['consumer_joy']['sha256'], 'consumer binary changed')
        report.update(status='passed', all_checks_passed=True)
    except BaseException:
        report.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        write(receipt, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('generate')
    create.add_argument('--source', type=Path, required=True)
    create.add_argument('--candidate', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    consume = commands.add_parser('verify')
    consume.add_argument('--corpus', type=Path, required=True)
    consume.add_argument('--candidate', type=Path, required=True)
    consume.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'generate':
        generate(args.source.resolve(), args.candidate.resolve(), args.output.resolve())
    else:
        verify(args.corpus.resolve(), args.candidate.resolve(), args.receipt.resolve())


if __name__ == '__main__':
    main()
