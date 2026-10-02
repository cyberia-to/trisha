"""Admit original local producer/fresh-verifier receipts without execution."""
from pathlib import Path

from common import identity, load, require, SCOPE

ROOT = Path(__file__).resolve().parent
WHOLE = ROOT.parent / 'whole-proof'
BINARY = ROOT.parent / 'production-install/installed/bin/joy'


def coordinates(old):
    expected = {k: old[k] for k in ('program_particle', 'input_particle', 'output_particle', 'charged_reductions')}
    expected.update(logical_peak_frames=old['peak_frames'],
                    expanded_steps=old['compaction']['evaluator_checkpoints'] - 1)
    return expected


def check_command(receipt, action, generation, directory, proof, profile):
    require(receipt['schema'] == 'trident/proved-bootstrap-command/v1' and
            receipt['status'] == 'passed' and receipt['exit_code'] == 0, 'successful original command')
    require(receipt['action'] == action and receipt['generation'] == generation, 'command role')
    require(not any(k in receipt for k in ('error', 'resource_stop', 'orphan_group')), 'no failed command')
    require(receipt['cwd'] == str(directory) and receipt['environment'] == {'PATH': ''}, 'original isolated command')
    flags = list(profile['host_flags'])
    for flag, key in [('proof-bytes', 'wire_bytes'), ('proof-decoded-bytes', 'decoded_bytes'),
                      ('proof-records', 'records'), ('proof-steps', 'steps'), ('proof-cache-slots', 'cache_slots')]:
        flags += ['--' + flag, str(profile[key])]
    argv = [str(BINARY), action + '-artifact', str(WHOLE / f'inputs/c{generation}.dag'),
            '--input', str(WHOLE / f'inputs/c{generation}-job.dag'), *flags]
    argv += ['--output', 'proof.joysc'] if action == 'prove' else [
        '--proof', str(proof), '--output', 'compiler.dag', '--emit', 'program']
    require(receipt['command'] == argv, 'exact original argv')
    require(receipt['profile'] == profile, 'original profile unchanged')


def semantic_report(value, action, expected, old):
    require(value.get('ok') is True, 'successful original Joy output')
    require(value['schema'] == ('joy/artifact-proof/v1' if action == 'prove' else 'joy/artifact-verification/v1'), 'Joy report schema')
    report = value['verification']
    require(all(report[k] == v for k, v in expected.items()), 'accepted SH6 coordinates')
    require(report['compiler_job'] == old['compiler_job'] and report['compiler_job']['status'] == 'success', 'complete successful compiler response')
    require(report['format'] == 'joy-nox-disclosed-compiler-v1' and
            report['disclosure'] == 'complete public witness' and
            report['physical_resource_claim'] == 'unattested', 'native disclosure and resource claim')
    if action == 'verify':
        require('prover_observations' not in report, 'fresh verifier has no producer observations')
    return {k: v for k, v in report.items() if k not in ('elapsed_micros', 'prover_observations')}


def admit():
    profile = load(WHOLE / 'profile.json')
    prepared = load(WHOLE / 'preparation.json')
    require(prepared['status'] == 'prepared', 'original complete input preparation')
    binary = identity(BINARY)
    require(binary == prepared['binary'], 'original installed binary')
    inputs = {n: identity(WHOLE / 'inputs' / n) for n in prepared['files']}
    require(inputs == prepared['files'], 'immutable complete input closure')
    evidence = {str(WHOLE / 'inputs' / n): value for n, value in inputs.items()}
    for name in ['profile.json', 'preparation.json', 'run.py', 'installed-source-receipt.json',
                 'pack-c1.stdout', 'pack-c1.stderr', 'pack-c2.stdout', 'pack-c2.stderr']:
        evidence[str(WHOLE / name)] = identity(WHOLE / name)
    evidence[str(BINARY)] = binary
    source = load(WHOLE / 'installed-source-receipt.json')
    require(source['exit'] == 0 and not source['warnings'] and
            source['binary_sha256'] == binary['sha256'] and source['binary_size'] == binary['bytes'], 'successful original install')
    entries = []
    for generation in [1, 2]:
        producer = WHOLE / f'attempts/c{generation}-selfbuild-1'
        verifier = WHOLE / f'attempts/c{generation}-fresh-verification-1'
        proof = producer / 'proof.joysc'
        p, v = load(producer / 'receipt.json'), load(verifier / 'receipt.json')
        expected_proof = p['files']['proof.joysc']
        require(proof.is_file() and not proof.is_symlink() and proof.stat().st_size == expected_proof['bytes'], 'certificate size/type')
        require(v['proof_input'] == dict(path=str(proof), **expected_proof) and
                v['proof_input_after'] == expected_proof, 'exact fresh-verifier certificate binding')
        require(p['ended_ns'] <= v['started_ns'], 'separate verification follows completed producer')
        old = load(WHOLE / f'inputs/accepted-c{generation + 1}-step.json')['execution']['execution']
        expected = coordinates(old)
        reports = []
        for action, directory, receipt in [('prove', producer, p), ('verify', verifier, v)]:
            check_command(receipt, action, generation, directory, proof, profile)
            require(receipt['binary'] == receipt['binary_after'] == binary, 'same original binary')
            require(receipt['inputs_before'] == receipt['inputs_after'] == inputs, 'unchanged command inputs')
            for field, name in [('driver', 'run.py'), ('preparation', 'preparation.json'),
                                ('profile_identity', 'profile.json'), ('installed_source_receipt', 'installed-source-receipt.json')]:
                require(receipt[field] == evidence[str(WHOLE / name)], 'original command provenance: ' + field)
            require(receipt['accepted_execution_coordinates'] == expected, 'accepted command coordinates')
            evidence[str(directory / 'receipt.json')] = identity(directory / 'receipt.json')
            for name, value in receipt['files'].items():
                require(Path(name).name == name and name not in ('.', '..'), 'simple receipt filename')
                if name != 'proof.joysc':
                    require(identity(directory / name) == value, 'original raw evidence: ' + name)
                    evidence[str(directory / name)] = value
            require(receipt['files']['stderr']['bytes'] == 0, 'original command stderr is empty')
            reports.append(semantic_report(load(directory / 'stdout'), action, expected, old))
        require(reports[0] == reports[1], 'producer and fresh verifier complete semantic claim')
        require(v['files']['compiler.dag'] == inputs['c2.dag'] and
                v['files']['compiler.dag']['sha256'] == profile['expected_artifact_sha256'], 'accepted fixed-point artifact')
        require(reports[1]['transport']['wire_bytes'] == expected_proof['bytes'], 'complete proof wire byte count')
        entries.append(dict(generation=generation, proof=dict(path=str(proof), **expected_proof),
                            producer_receipt=dict(path=str(producer / 'receipt.json'), **evidence[str(producer / 'receipt.json')]),
                            verifier_receipt=dict(path=str(verifier / 'receipt.json'), **evidence[str(verifier / 'receipt.json')]),
                            verification=reports[1], scope=SCOPE))
    return dict(scope=SCOPE, binary=dict(path=str(BINARY), **binary), source_revisions=source['inputs'],
                profile_identity=evidence[str(WHOLE / 'profile.json')], entries=entries, evidence=evidence)
