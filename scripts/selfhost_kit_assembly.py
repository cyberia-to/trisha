"""One-time kit assembly, delegated to the committed original 36-phase authority."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import selfhost_kit as K

PATH_ARGUMENTS = ('restored', 'stores', 'indices', 'inputs', 'runner-directory',
                  'expected', 'aggregate-job', 'final-run')
CONFIG_KEYS = {*PATH_ARGUMENTS, 'indices-sha256', 'aggregate-id', 'producer-name'}


def copy(source, destination, expected=None):
    before = K.identity(source)
    K.require(expected is None or before == expected, 'selected input identity')
    with source.open('rb') as incoming, destination.open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing, 1 << 20)
    K.require(K.identity(destination) == before == K.identity(source), 'input changed during copy')


def retained(root, row):
    path = root / str(K.relative(row['path']))
    K.require(path.resolve().is_relative_to(root.resolve()), 'retained path escape')
    K.require(K.identity(path) == {key: row[key] for key in ('bytes', 'sha256')}, 'retained input identity')
    return path


def authority(validator, config_path, work):
    K.require(os.environ.get('GITHUB_ACTIONS') != 'true', 'final36 assembly requires local replay, outside CI')
    K.require(K.sha(validator) == K.VALIDATOR, 'committed final36 validator SHA256')
    config = K.load(config_path)
    K.require(set(config) == CONFIG_KEYS, 'explicit complete validator configuration')
    K.require(all(Path(config[key]).is_absolute() for key in PATH_ARGUMENTS), 'absolute validator input paths')
    paths = {key: Path(config[key]).resolve() for key in PATH_ARGUMENTS}
    for path in paths.values():
        K.separate(work, path)
    work.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-B', '-W', 'error', str(validator)]
    for key in PATH_ARGUMENTS:
        command += ['--' + key, str(paths[key])]
    command += ['--indices-sha256', config['indices-sha256'], '--aggregate-id', str(config['aggregate-id']),
                '--output', str(work / 'validation')]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with (work / 'validator.stdout').open('xb') as stdout, (work / 'validator.stderr').open('xb') as stderr:
        result = subprocess.run(command, env=env, stdout=stdout, stderr=stderr)
    K.write(work / 'command.json', dict(argv=command, cwd=str(Path.cwd()), exit_code=result.returncode,
                                      validator=K.identity(validator), config=K.identity(config_path)))
    K.require(K.sha(validator) == K.VALIDATOR and result.returncode == 0, 'original final36 acceptance failed')
    proof = K.load(work / 'validation/verification.json')
    K.require(proof['status'] == 'passed' and proof['validator_sha256'] == K.VALIDATOR, 'authority completion')
    selected = next(row for row in proof['phases'] if row['name'] == config['producer-name'])
    producer = paths['restored'] / str(K.relative(config['producer-name']))
    K.require(K.sha(producer / 'receipt.json') == selected['receipt']['sha256'], 'original selected producer')
    return producer, work / 'validation'


def assemble(args):
    K.require(args.output.name.endswith('.tar.gz'), 'portable kit must be .tar.gz')
    inputs = [args.trident, args.guide]
    if args.command == 'assemble':
        inputs += [args.validator, args.config]
        config = K.load(args.config)
        inputs += [Path(config[key]) for key in PATH_ARGUMENTS]
    else:
        inputs += [args.compiler, args.inventory, args.fixed_point]
    K.separate(args.work, *inputs, args.output)
    K.separate(args.output, *inputs, args.work)
    producer = validation = None
    if args.command == 'assemble':
        producer, validation = authority(args.validator, args.config, args.work)
    else:
        args.work.mkdir(parents=True, exist_ok=False)
    root = args.work / 'kit'
    root.mkdir()
    selection = None
    if producer is not None:
        raw = K.load(producer / 'receipt.json')
        K.require(raw['phase'] == 'producer' and raw['status'] == 'produced', 'selected native producer role')
        row = raw['repetitions'][0]
        K.require(row['c2']['path'] == f"repeat-{raw['repeat']}/c2.dag", 'original C2 path')
        for key, name in (('c2', 'compiler.dag'), ('inventory', 'inventory.json'), ('fixed_point', 'fixed-point.json')):
            copy(retained(producer, row[key]), root / name)
        copy(producer / 'receipt.json', root / 'producer.json')
        copy(retained(producer, raw['files']), root / 'producer-files.json')
        copy(validation / 'verification.json', root / 'acceptance.json')
        copy(validation / 'original-aggregate.json', root / 'aggregate.json')
        copy(validation / 'original-aggregate-files.json', root / 'aggregate-files.json')
        selection = dict(name=producer.name, receipt_sha256=K.sha(root / 'producer.json'), compiler_path=row['c2']['path'])
    else:
        for source, name in ((args.compiler, 'compiler.dag'), (args.inventory, 'inventory.json'),
                             (args.fixed_point, 'fixed-point.json')):
            copy(source, root / name)
    for name, expected in K.GUIDE.items():
        K.require(K.sha(args.guide / name) == expected, 'exact guide input')
        copy(args.guide / name, root / name)
    status = 'accepted' if producer is not None else 'rehearsal'
    (root / 'README.md').write_text(
        '# Portable Trident compiler\n\nStatus: ' + status + '.\n\n'
        'Keep these files together. From this directory with the supplied Joy on PATH:\n\n'
        '```sh\njoy pack-job --compiler compiler.dag --manifest package.json --output job.dag\n'
        'joy run-artifact compiler.dag --input job.dag --emit program --output sample.dag\n'
        'joy run-artifact sample.dag --input zero.dag --output answer.dag\n```\n\n'
        'The expected result is the canonical atom 13. kit.json pins every payload file.\n'
        'The compiler is a portable compiler-job NOXDAG artifact; Joy executes it.\n'
        'Rehearsal status is not release acceptance. Native bootstrap provenance and\n'
        'installed-runtime smoke are separate from compilation proofs (SH7/SH8).\n', encoding='utf-8', newline='\n')
    manifest = dict(schema=K.SCHEMA, status=status, files=K.files(root), producer=selection,
                    compiler=dict(role='C2', particle=K.PARTICLE, **K.identity(root / 'compiler.dag')))
    K.write(root / 'kit.json', manifest)
    K.check(root, args.trident, rehearsal=producer is None)
    spec = importlib.util.spec_from_file_location('archive_source', Path(__file__).with_name('archive-source.py'))
    archive = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive)
    archive.archive(root, args.output, 0, 'trident-selfhost')
    K.write(args.work / 'assembly.json', dict(schema='trident/selfhost-kit-assembly/v1', status=status,
                                            archive=dict(path=str(args.output), **K.identity(args.output)),
                                            manifest=K.identity(root / 'kit.json')))
