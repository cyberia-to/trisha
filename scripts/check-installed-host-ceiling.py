"""Check the changed Joy host deadline using the exact installed executable."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    helper_path = Path(__file__).with_name('current-structured-corpus.py')
    spec = importlib.util.spec_from_file_location('structured', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    source, candidate, output = args.source.resolve(), args.candidate.resolve(), args.output.resolve()
    metadata, joy = helper.candidate(candidate)
    helper.require(metadata['provenance_sha256'] == helper.sha(source / 'sources.json'), 'fixture source differs')
    vector_path = source / 'joy/cli/tests/compiler_vectors.json'
    vectors = json.loads(vector_path.read_text())['files']
    output.mkdir()
    commands = output / 'commands'
    commands.mkdir()
    for name in ('compiler', 'job', 'generated', 'zero', 'fourteen'):
        (output / name).write_bytes(bytes.fromhex(vectors[name]))
    report = dict(status='running', scope='Bounded actual installed Joy host-deadline contract; no whole-compiler proof claim',
                  joy=helper.identity(joy), source_provenance_sha256=metadata['provenance_sha256'],
                  fixture=helper.identity(vector_path), candidate_sha256=helper.sha(candidate / 'candidate.json'),
                  script_sha256=helper.sha(Path(__file__)), helper_sha256=helper.sha(helper_path), commands=[])
    compact = ['--resident-nodes', '196608', '--collection-work', '100000000']
    proof_bytes, claim = None, None
    def execute(name, command, expected=0):
        result = helper.execute(joy, command, output, commands, name, report['commands'], expected)
        helper.write(output / 'receipt.json', report)
        return result
    try:
        for producer_ms in ('30000', '7200000', '14400000'):
            proof = 'proof-' + producer_ms
            execute('prove-' + producer_ms, ['prove-artifact', 'compiler', '--input', 'job', '-o', proof,
                                            '--time-ms', producer_ms, *compact])
            actual = (output / proof).read_bytes()
            helper.require(len(actual) <= 256 * 1024**2, 'bounded certificate exceeds allowance')
            if proof_bytes is None:
                proof_bytes = actual
            helper.require(actual == proof_bytes, 'proof bytes changed with producer host deadline')
            for verifier_ms in ('30000', '7200000', '14400000'):
                result = execute('verify-' + producer_ms + '-' + verifier_ms,
                                 ['verify-artifact', 'compiler', '--input', 'job', '--proof', proof,
                                  '-o', 'compiled', '--emit', 'program', '--force', '--time-ms', verifier_ms, *compact])
                observed = dict(result['verification'])
                observed.pop('elapsed_micros', None)
                helper.require(observed['physical_resource_claim'] == 'unattested'
                               and observed.get('prover_observations') is None, 'unexpected resource attestation')
                if claim is None:
                    claim = observed
                helper.require(observed == claim, 'claim changed with producer/verifier host deadline')
                helper.require((output / 'compiled').read_bytes() == (output / 'generated').read_bytes(), 'compiled output differs')
        execute('compiled-program-run', ['run-artifact', 'compiled', '--input', 'zero', '-o', 'result'])
        helper.require((output / 'result').read_bytes() == (output / 'fourteen').read_bytes(), 'compiled program result differs')
        for operation in ('prove-artifact', 'verify-artifact'):
            for value in ('0', '14400001', '18446744073709551615'):
                (output / 'destination').write_bytes(b'previous destination')
                name = operation + '-invalid-' + value
                command = [operation, 'compiler', '--input', 'job', '-o', 'destination', '--force', '--time-ms', value, *compact]
                if operation == 'verify-artifact':
                    command += ['--proof', 'proof-14400000']
                execute(name, command, 1)
                helper.require('limit time_ms must be in 1..=14400000' in (commands / (name + '.stderr')).read_text(), 'wrong compacting ceiling diagnostic')
                helper.require((output / 'destination').read_bytes() == b'previous destination', 'invalid deadline replaced destination')
        execute('ordinary-prove-limit', ['prove-artifact', 'compiler', '--input', 'job', '-o', 'ordinary-proof', '--time-ms', '300000'])
        execute('ordinary-verify-limit', ['verify-artifact', 'compiler', '--input', 'job', '--proof', 'ordinary-proof',
                                         '-o', 'ordinary-result', '--emit', 'program', '--time-ms', '300000'])
        helper.require((output / 'ordinary-result').read_bytes() == (output / 'generated').read_bytes(), 'ordinary ceiling changes output')
        for operation in ('prove-artifact', 'verify-artifact'):
            (output / 'destination').write_bytes(b'previous destination')
            name = operation + '-ordinary-over-limit'
            command = [operation, 'compiler', '--input', 'job', '-o', 'destination', '--force', '--time-ms', '300001']
            if operation == 'verify-artifact':
                command += ['--proof', 'ordinary-proof']
            execute(name, command, 1)
            helper.require('limit time_ms must be in 1..=300000' in (commands / (name + '.stderr')).read_text(), 'ordinary ceiling changed')
            helper.require((output / 'destination').read_bytes() == b'previous destination', 'ordinary deadline rejection replaced destination')
        helper.require(helper.identity(joy) == report['joy'] and helper.identity(vector_path) == report['fixture'], 'binary or fixtures changed')
        helper.require(not any(p.name.startswith('.') for p in output.iterdir()), 'temporary publication remains')
        report.update(status='passed', accepted=sum(row['exit_code'] == 0 for row in report['commands']),
                      rejected=sum(row['exit_code'] == 1 for row in report['commands']), proof_sha256=helper.sha(output / 'proof-14400000'))
    except BaseException:
        report.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        helper.write(output / 'receipt.json', report)


if __name__ == '__main__':
    main()
