"""Execute the pinned public-proof profile gate on one actual native host."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback

import native_proof_inputs as inputs

CLI_TESTS = (
    'raw_complete_nouns_and_loop_proofs_verify_in_fresh_processes',
    'compiler_res1_success_diagnostics_and_extracted_artifact_are_bound',
    'failed_proofs_and_verification_preserve_destinations_and_remove_prefixes',
)
UNIX_CLI_TEST = 'certificate_file_admission_rejects_links_and_pipes_without_blocking'
OBSERVER_TESTS = (
    'computed_continuation_preserves_variable_topology_at_exact_budget',
    'snapshots_preserve_runtime_stats_logical_steps_and_version_one_bytes',
    'version_one_gc_stream_matches_pre_extension_golden',
)
DISCLOSED_TESTS = (
    'native_headers_and_every_cost_case_are_derived_from_prior_records',
    'all_pure_patterns_match_native_values_costs_and_frame_boundaries',
    'all_native_rules_match_finite_dag_across_a_fresh_noun_table_per_event',
)
ALLOCATIONS = {
    'disclosed_memory_allocation': ('failed_growth_preserves_validated_records_and_allows_retry',
                                   'compact_value_admission_handles_allocation_failure_without_partial_records'),
    'disclosed_evaluation_allocation': ('allocation_failures_preserve_verified_evaluations_and_retry_indices',),
    'disclosed_stream_allocation': ('constructor_failures_are_fallible_and_events_need_no_allocations',),
}


def required_cli_tests(system):
    return CLI_TESTS + ((UNIX_CLI_TEST,) if system != 'Windows' else ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selector', type=Path, default=Path('.github/native-proof-profile.json'))
    parser.add_argument('--target', default=os.environ.get('PROOF_NATIVE_TARGET'))
    parser.add_argument('--work', type=Path)
    parser.add_argument('--results', type=Path, default=Path('native-proof-results'))
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    spec = inputs.selector(args.selector)
    target = args.target
    inputs.require(target in inputs.TARGETS, 'one explicit native target required')
    checkout = Path.cwd().resolve()
    results = args.results.resolve()
    results.mkdir()
    work = args.work or Path(os.environ['RUNNER_TEMP']) / 'native-public-proof-profile'
    work = work.resolve()
    work.mkdir()
    toolchain = spec['rust'] + '-' + target
    env = inputs.sanitized(os.environ)
    env.update(RUSTUP_TOOLCHAIN=toolchain, CARGO_BUILD_JOBS='2', RUSTFLAGS='-Dwarnings',
               CARGO_TARGET_DIR=str(work / 'target'),
               CARGO_TERM_COLOR='never', RUST_TEST_THREADS='2')
    cli_tests = required_cli_tests(platform.system())
    bootstrap_env = dict(env)
    # rustup itself belongs to the runner's existing manager installation.
    # Its storage locations are used only for installation/path resolution.
    for key in ('CARGO_HOME', 'RUSTUP_HOME'):
        if key in os.environ:
            bootstrap_env[key] = os.environ[key]
    report = dict(format=spec['format'], status='running', selector=spec,
                  selector_sha256=inputs.sha(args.selector), target=target,
                  scope='changed public native proof profile; no distribution or SH7/SH8 acceptance',
                  host=dict(system=platform.system(), machine=platform.machine(), platform=platform.platform(),
                            python=sys.version, image=os.environ.get('ImageOS'), image_version=os.environ.get('ImageVersion')),
                  runner_revision=os.environ.get('GITHUB_SHA'), commands=[], failures=[],
                  required_cli_tests=cli_tests)
    family = work / 'family'

    def save():
        (results / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    def run(name, command, cwd=work, environment=None):
        inputs.require(all(row['name'] != name for row in report['commands']), 'duplicate command/log name: ' + name)
        command = list(map(str, command))
        row = dict(name=name, command=command, cwd=str(cwd),
                   started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        report['commands'].append(row)
        save()
        tick = time.monotonic_ns()
        with (results / (name + '.stdout')).open('xb') as stdout, (results / (name + '.stderr')).open('xb') as stderr:
            result = subprocess.run(command, cwd=cwd, env=environment or env, stdout=stdout, stderr=stderr)
        row.update(exit_code=result.returncode, elapsed_ns=time.monotonic_ns() - tick)
        for stream in ('stdout', 'stderr'):
            path = results / (name + '.' + stream)
            row[stream] = dict(path=path.name, bytes=path.stat().st_size, sha256=inputs.sha(path))
        output = (results / (name + '.stdout')).read_text(encoding='utf-8')
        error = (results / (name + '.stderr')).read_text(encoding='utf-8', errors='replace')
        row['warnings'] = inputs.warnings(output + '\n' + error)
        save()
        print(name, result.returncode, flush=True)
        if result.returncode:
            print(error[-6000:], flush=True)
            raise RuntimeError('gate command failed: ' + name)
        inputs.require(not row['warnings'], 'compiler/Cargo warnings: ' + name)
        return output

    def gate(name, command, cwd, tests=None):
        try:
            output = run(name, command, cwd)
            if tests is not None:
                names = inputs.passed_tests(output, tests)
                report.setdefault('tests', {})[name] = names
                save()
        except Exception:
            report['failures'].append(dict(gate=name, error=traceback.format_exc()))
            save()

    def cargo(project, *args):
        return [tools['cargo'], *args, '--manifest-path', family / project / 'Cargo.toml', '--locked', '--offline']

    save()
    try:
        report['bootstrap'] = {name: inputs.sha(checkout / name) for name in (
            '.github/workflows/native-proof-profile.yml', 'scripts/native-proof-profile.py', 'scripts/native_proof_inputs.py')}
        inputs.native_host(target, platform.system(), platform.machine())
        inputs.fetch(family, spec['sources'], run)
        before = inputs.inventory(family, spec['sources'], run, 'before')
        (results / 'sources-before.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8')
        report['sources_before_sha256'] = inputs.sha(results / 'sources-before.json')
        rustup = shutil.which('rustup', path=env['PATH'])
        inputs.require(rustup, 'rustup executable missing')
        run('rustup', [rustup, 'toolchain', 'install', toolchain, '--profile', 'minimal'], environment=bootstrap_env)
        tools = {}
        for name in ('rustc', 'cargo', 'rustdoc'):
            path = Path(run('resolve-' + name, [rustup, 'which', '--toolchain', toolchain, name], environment=bootstrap_env).strip()).resolve(strict=True)
            inputs.require(path.is_file(), 'selected compiler executable missing')
            tools[name] = str(path)
        inputs.require(len({Path(path).parent for path in tools.values()}) == 1, 'selected tools have different roots')
        env.update(CARGO_HOME=str(work / 'cargo-home'), RUSTC=tools['rustc'], RUSTDOC=tools['rustdoc'])
        env['PATH'] = str(Path(tools['cargo']).parent) + os.pathsep + env['PATH']
        report['tools'] = {name: dict(path=path, sha256=inputs.sha(Path(path))) for name, path in tools.items()}
        report['build_environment'] = {k: env[k] for k in (
            'RUSTUP_TOOLCHAIN', 'CARGO_BUILD_JOBS', 'RUSTFLAGS', 'CARGO_HOME', 'CARGO_TARGET_DIR',
            'RUST_TEST_THREADS', 'RUSTC', 'RUSTDOC')}
        rustc = run('rustc', [tools['rustc'], '-vV'])
        cargo_version = run('cargo', [tools['cargo'], '-vV'])
        inputs.native_host(target, platform.system(), platform.machine(), rustc, cargo_version)
        run('git-version', ['git', '--version'])
        for project in ('joy', 'zheng', 'nox'):
            run(project + '-cargo-fetch', [tools['cargo'], 'fetch', '--locked', '--manifest-path', family / project / 'Cargo.toml'], family / project)
            raw = run(project + '-metadata', cargo(project, 'metadata', '--format-version', '1', '--all-features'), family / project)
            report.setdefault('closures', {})[project] = inputs.closure(json.loads(raw), family, spec['sources'])
        save()
        gate('joy-boundary', [sys.executable, '-B', family / 'joy/scripts/check-soft3-boundary.py'], family / 'joy')
        gate('joy-check', cargo('joy', 'check', '--workspace', '--all-targets', '--all-features'), family / 'joy')
        gate('joy-tests', cargo('joy', 'test', '--workspace', '--release', '--no-fail-fast'), family / 'joy', cli_tests)
        gate('zheng-check', cargo('zheng', 'check', '-p', 'zheng', '--all-targets', '--all-features'), family / 'zheng')
        for suffix, features in [('default', []), ('all-features', ['--all-features'])]:
            gate('zheng-disclosed-' + suffix, cargo('zheng', 'test', '-p', 'zheng', '--release', '--lib',
                 *features, 'execution::disclosed::'), family / 'zheng', DISCLOSED_TESTS)
            for binary, required in ALLOCATIONS.items():
                gate(binary + '-' + suffix, cargo('zheng', 'test', '-p', 'zheng', '--release',
                     *features, '--test', binary), family / 'zheng', required)
        gate('nox-check', cargo('nox', 'check', '-p', 'cyber-nox', '--features', 'std', '--all-targets'), family / 'nox')
        gate('nox-observer', cargo('nox', 'test', '-p', 'cyber-nox', '--features', 'std', '--release',
             '--lib', 'sequential::observe::'), family / 'nox', OBSERVER_TESTS)
        after = inputs.inventory(family, spec['sources'], run, 'after')
        (results / 'sources-after.json').write_text(json.dumps(after, indent=2) + '\n', encoding='utf-8')
        inputs.require(after == before, 'source bytes changed during gates')
        report['sources_after_sha256'] = inputs.sha(results / 'sources-after.json')
        binary = work / 'target/release' / ('joy.exe' if os.name == 'nt' else 'joy')
        inputs.require(binary.is_file(), 'native Joy CLI was not built')
        retained = results / binary.name
        shutil.copy2(binary, retained)
        report['joy_binary'] = dict(path=retained.name, bytes=retained.stat().st_size, sha256=inputs.sha(retained))
        for row in report['commands']:
            for stream in ('stdout', 'stderr'):
                inputs.require(inputs.sha(results / row[stream]['path']) == row[stream]['sha256'], 'command log changed')
        inputs.require(not report['failures'], 'one or more changed-profile gates failed')
        report['status'] = 'passed'
    except BaseException:
        report.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
