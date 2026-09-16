"""Seal installed-smoke artifacts and verify them on another native platform.

The caller authenticates the corpus archive digest. Its inventory then pins
every file and exact native STARK claim; Joy additionally pins source, inputs,
output and state through its public verification interface.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tomllib


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('corpus may not contain symbolic links')
        if path.is_file() and path != root/'corpus.json':
            files[path.relative_to(root).as_posix()] = sha(path)
    return files


def cases(root):
    result = []
    entry = ['7', '19', '1', *map(str, range(101, 121)), '31']
    inner = tomllib.loads((root/'inner.proof.toml').read_text())['claim']
    expected_inner = json.loads((root/'expected-inner.json').read_text())
    if any(list(map(str, expected_inner[key])) != inner[key]
           for key in ('program_hash', 'public_input', 'public_output')):
        raise ValueError('recursive expected claim differs from the authorized inner proof')
    # The outer public input commits to the complete inner claim, including I/O.
    commitment = json.loads((root/'recursive-witness.json').read_text())['public']
    triton = [
        ('inner.proof.toml', ['5'], ['38']),
        ('outer.proof.toml', commitment, ['1']),
        ('proofs/main.proof.toml', ['5'], ['38']),
        ('proofs/witness.proof.toml', ['5'], ['12']),
        ('imported.proof.toml', ['3', '5'], ['803']),
    ]
    for profile in ('debug', 'release'):
        triton += [(f'typed-entry-{profile}.proof.toml', entry, ['719', '31']),
                   (f'stack-ram-{profile}.proof.toml', ['97'], ['1001','1','7','8','97','999','1001'])]
    for name, inputs, outputs in triton:
        claim = tomllib.loads((root/name).read_text())['claim']
        if claim['public_input'] != inputs or claim['public_output'] != outputs:
            raise ValueError(f'corpus differs from source fixture: {name}')
        result.append(dict(binary='trisha', args=['verify', name], exit_code=0,
                           file=name, claim=claim))
    rejected = ['main.proof.toml', 'forged-outer.proof.toml', 'imported-bad-output.proof.toml']
    for profile in ('debug', 'release'):
        rejected += [f'typed-entry-{profile}-bad-input.proof.toml',
                     f'typed-entry-{profile}-bad-output.proof.toml',
                     f'stack-ram-{profile}-bad-output.proof.toml']
    result += [dict(binary='trisha', args=['verify', name], exit_code=1) for name in rejected]
    nox_input = '7,19,0,101,103,107,307,311,313,317'
    joy = [
        ('arithmetic', 'arithmetic', 'release', '5', '38', None),
        ('private', 'private', 'release', '5', '1769', None),
        ('state', 'state', 'debug', '11', '82', 'state.json'),
        ('private-state', 'private-state', 'debug', '5', '82', 'state-all.json'),
        ('typed-nox-debug', 'typed-nox', 'debug', nox_input, '719', None),
        ('typed-nox-release', 'typed-nox', 'release', nox_input, '719', None),
        ('typed-private', 'typed-private', 'release', '19,0', '42', None),
        ('loop-private', 'loop-private', 'release', '5', '42', None),
        ('imported', 'imported-nox', 'release', '3,5', '803', None),
    ]
    for artifact, source, profile, inputs, output, state in joy:
        args = ['verify', source+'.tri', '--target', 'nox', '--profile', profile,
                '--proof', artifact+'.zheng', '--input-values', inputs, '--claim', output]
        if state:
            args += ['--state', state]
        result.append(dict(binary='joy', args=args, exit_code=0))
        changed = args.copy()
        changed[changed.index('--claim')+1] = str(int(output)+1)
        result.append(dict(binary='joy', args=changed, exit_code=1))
        changed = args.copy()
        values = inputs.split(',')
        values[0] = str(int(values[0])+1)
        changed[changed.index('--input-values')+1] = ','.join(values)
        result.append(dict(binary='joy', args=changed, exit_code=1))
        if state:
            changed = args.copy()
            changed[changed.index('--state')+1] = 'other-state.json'
            result.append(dict(binary='joy', args=changed, exit_code=1))
    return result


def seal(root):
    smoke = json.loads((root/'smoke.json').read_text())
    if smoke.get('schema_version') != 2 or smoke.get('all_checks_passed') is not True:
        raise ValueError('completed installed smoke v2 required')
    record = dict(schema_version=1, source_provenance_sha256=smoke['source_provenance_sha256'],
                  producer_platform=smoke['platform'], producer_binaries=smoke['binaries'],
                  cases=cases(root), files=inventory(root))
    with (root/'corpus.json').open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)


def verify(root, prefix, output):
    record = json.loads((root/'corpus.json').read_text())
    candidate = json.loads((prefix/'candidate.json').read_text())
    if candidate['provenance_sha256'] != record['source_provenance_sha256']:
        raise ValueError('producer and consumer have different source inventories')
    if record.get('schema_version') != 1 or record['files'] != inventory(root):
        raise ValueError('corpus identity changed')
    if record['cases'] != cases(root):
        raise ValueError('corpus does not match the mandatory acceptance cases')
    binaries = {name: prefix/'bin'/(name + ('.exe' if os.name == 'nt' else ''))
                for name in ('trisha', 'joy')}
    identities = {name: sha(path) for name, path in binaries.items()}
    expected = {entry['name']: entry['sha256'] for entry in candidate['binaries']}
    if any(expected.get(name) != value for name, value in identities.items()):
        raise ValueError('consumer binary differs from its candidate receipt')
    checked = []
    for case in record['cases']:
        result = subprocess.run([str(binaries[case['binary']]), *case['args']],
                                cwd=root, capture_output=True, timeout=180)
        if result.returncode != case['exit_code']:
            raise ValueError(f"{case['args']}: exit {result.returncode}, expected {case['exit_code']}; "
                             + result.stderr.decode(errors='replace'))
        checked.append(dict(args=case['args'], exit_code=result.returncode))
    if record['files'] != inventory(root) or identities != {name: sha(path) for name, path in binaries.items()}:
        raise ValueError('inputs changed during verification')
    receipt = dict(all_checks_passed=True, corpus_sha256=sha(root/'corpus.json'),
                   producer_platform=record['producer_platform'], consumer_binaries=identities, cases=checked)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
    print(f'PASS: {len(checked)} exact-claim cross-platform verification checks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path)
    parser.add_argument('--seal', action='store_true')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.seal:
        seal(args.corpus.resolve())
    elif args.candidate and args.receipt:
        verify(args.corpus.resolve(), args.candidate.resolve(), args.receipt.resolve())
    else:
        parser.error('--seal or --candidate and --receipt required')
