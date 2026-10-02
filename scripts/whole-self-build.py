"""Replay one exact accepted full self-build on native free Linux CI."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback

import native_proof_inputs as native
import whole_self_host as host
import whole_self_inputs as frozen


def main():
    host.cancellation_handlers()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generation', type=int, choices=(1, 2), required=True)
    parser.add_argument('--results', type=Path, default=Path('whole-self-build-results'))
    args = parser.parse_args()
    checkout = Path.cwd().resolve()
    results = args.results.resolve()
    results.mkdir()
    target = 'x86_64-unknown-linux-gnu'
    work = Path(os.environ['RUNNER_TEMP']) / ('whole-self-build-c' + str(args.generation))
    work.mkdir()
    spec = native.selector(checkout / '.github/whole-self-build-sources.json')
    asset = frozen.asset_selector(checkout / '.github/whole-self-build-input.json')
    env = native.sanitized(os.environ)
    env.update(RUSTUP_TOOLCHAIN=spec['rust'] + '-' + target, CARGO_BUILD_JOBS='2',
               RUSTFLAGS='-Dwarnings', CARGO_TARGET_DIR=str(work / 'target'), CARGO_TERM_COLOR='never')
    report = dict(schema='trident/native-whole-self-build/v1', status='running',
                  generation=args.generation, source_selector=spec, input_asset=asset,
                  native_target=target, host=dict(system=platform.system(), machine=platform.machine(),
                  platform=platform.platform(), python=sys.version, image=os.environ.get('ImageOS'),
                  image_version=os.environ.get('ImageVersion')), runner_revision=os.environ.get('GITHUB_SHA'),
                  commands=[], proof_commands=[], durable_retention=('pending' if os.environ.get('RETAIN_DRAFT') == 'true' else 'not-requested'), profile=frozen.PROFILE)

    def save():
        host.save(results / 'receipt.json', report)

    def run(name, command, cwd=work, environment=None, timeout=1800, binary_output=None):
        native.require(not any(r['name'] == name for r in report['commands']), 'unique command names')
        row = dict(name=name, command=list(map(str, command)), cwd=str(cwd), started_ns=time.time_ns())
        report['commands'].append(row)
        save()
        output = binary_output or results / (name + '.stdout')
        error = results / (name + '.stderr')
        tick = time.monotonic_ns()
        try:
            with output.open('xb') as stdout, error.open('xb') as stderr:
                process = subprocess.run(row['command'], cwd=cwd, env=environment or env,
                                         stdout=stdout, stderr=stderr, timeout=timeout)
            row.update(exit_code=process.returncode, elapsed_ns=time.monotonic_ns() - tick)
        finally:
            row['stdout'] = dict(path=str(output), **frozen.identity(output))
            row['stderr'] = dict(path=str(error), **frozen.identity(error))
            save()
        native.require(row['exit_code'] == 0, 'command failed: ' + name)
        text = '' if binary_output else output.read_text(encoding='utf-8')
        native.require(not native.warnings(text + error.read_text(encoding='utf-8', errors='replace')), 'warnings: ' + name)
        return text

    save()
    try:
        native.native_host(target, platform.system(), platform.machine())
        native.require(os.environ.get('GITHUB_REPOSITORY') == 'cyberia-to/trisha' and
                       os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'reviewed manual repository dispatch')
        actual = run('bootstrap-head', ['git', 'rev-parse', 'HEAD'], checkout).strip()
        native.require(actual == os.environ['GITHUB_SHA'], 'exact workflow checkout')
        native.require(not run('bootstrap-status', ['git', 'status', '--porcelain=v1', '--untracked-files=all'], checkout).strip(), 'clean workflow checkout')
        report['bootstrap'] = {str(p.relative_to(checkout)): frozen.identity(p)
                               for p in sorted((checkout / 'scripts').glob('*whole*self*')) if p.is_file()}
        report['bootstrap']['scripts/native_proof_inputs.py'] = frozen.identity(checkout / 'scripts/native_proof_inputs.py')
        host.cleanup(results, run)
        token = os.environ.get('GH_TOKEN')
        native.require(token, 'read-only input asset token required')
        download_env = dict(env, GH_TOKEN=token)
        endpoint = f"repos/{asset['repository']}/releases/assets/{asset['asset_id']}"
        metadata = json.loads(run('input-asset-metadata', ['gh', 'api', endpoint], environment=download_env))
        native.require(metadata['id'] == asset['asset_id'] and metadata['name'] == asset['name'] and
                       metadata['size'] == asset['bytes'] and metadata.get('digest') == 'sha256:' + asset['sha256'], 'server input asset identity')
        archive = work / asset['name']
        run('input-asset-download', ['gh', 'api', endpoint, '-H', 'Accept: application/octet-stream'],
            environment=download_env, binary_output=archive)
        package = work / 'frozen'
        report['frozen_inputs_before'] = frozen.admit(archive, package, asset)
        report['input_asset_metadata'] = metadata
        family = work / 'family'
        native.fetch(family, spec['sources'], run)
        before = native.inventory(family, spec['sources'], run, 'before')
        host.save(results / 'sources-before.json', before)
        rustup = shutil.which('rustup', path=env['PATH'])
        native.require(rustup, 'rustup executable required')
        bootstrap_env = dict(env)
        for key in ('CARGO_HOME', 'RUSTUP_HOME'):
            if key in os.environ:
                bootstrap_env[key] = os.environ[key]
        run('install-rust', [rustup, 'toolchain', 'install', env['RUSTUP_TOOLCHAIN'], '--profile', 'minimal'], environment=bootstrap_env)
        tools = {}
        for name in ('rustc', 'cargo', 'rustdoc'):
            tools[name] = str(Path(run('resolve-' + name, [rustup, 'which', '--toolchain', env['RUSTUP_TOOLCHAIN'], name], environment=bootstrap_env).strip()).resolve(strict=True))
        native.require(len({Path(p).parent for p in tools.values()}) == 1, 'one native toolchain directory')
        env.update(CARGO_HOME=str(work / 'cargo-home'), RUSTC=tools['rustc'], RUSTDOC=tools['rustdoc'])
        env['PATH'] = str(Path(tools['cargo']).parent) + os.pathsep + env['PATH']
        report['tools'] = {name: dict(path=p, **frozen.identity(p)) for name, p in tools.items()}
        report['build_environment'] = {k: env[k] for k in ('PATH', 'CARGO_HOME', 'CARGO_TARGET_DIR', 'RUSTC', 'RUSTDOC', 'RUSTUP_TOOLCHAIN', 'RUSTFLAGS', 'CARGO_BUILD_JOBS')}
        rustc = run('rustc-version', [tools['rustc'], '-vV'])
        cargo = run('cargo-version', [tools['cargo'], '-vV'])
        native.native_host(target, platform.system(), platform.machine(), rustc, cargo)
        joy = family / 'joy'
        run('cargo-fetch', [tools['cargo'], 'fetch', '--manifest-path', joy / 'Cargo.toml', '--locked'], joy)
        metadata = json.loads(run('cargo-metadata', [tools['cargo'], 'metadata', '--manifest-path', joy / 'Cargo.toml', '--format-version', '1', '--locked', '--offline'], joy))
        report['closure'] = native.closure(metadata, family, spec['sources'])
        run('native-boundary', [sys.executable, '-B', joy / 'scripts/check-soft3-boundary.py'], joy)
        run('native-build', [tools['cargo'], 'build', '--manifest-path', joy / 'Cargo.toml', '--release', '-p', 'cyber-joy', '--locked', '--offline'], joy, timeout=2700)
        binary = work / 'target/release/joy'
        retained = results / 'joy-linux-x64'
        shutil.copy2(binary, retained)
        report['binary'] = dict(path=str(binary), **frozen.identity(binary))
        original = package / 'inputs'
        compiler, job = original / f'c{args.generation}.dag', original / f'c{args.generation}-job.dag'
        accepted = frozen.load(original / f'accepted-c{args.generation + 1}-step.json')
        run('repack-job', [binary, 'pack-job', '--compiler', compiler, '--manifest', original / 'package.json', '--output', work / 'repacked-job.dag', *frozen.HOST], environment={'PATH': '', 'LANG': 'C.UTF-8'})
        native.require(frozen.identity(work / 'repacked-job.dag') == frozen.identity(job), 'exact frozen JOB1 reconstruction')
        proof_dir, verify_dir = work / 'prove', work / 'verify'
        proved = host.bounded('prove', [binary, 'prove-artifact', compiler, '--input', job, '--output', 'proof.joysc', *frozen.flags()],
                             proof_dir, results, binary, [compiler, job], report, save)
        proof_report = frozen.compare(proved, accepted, 'prove')
        proof = proof_dir / 'proof.joysc'
        verified = host.bounded('verify', [binary, 'verify-artifact', compiler, '--input', job, '--proof', proof,
                               '--output', 'compiler.dag', '--emit', 'program', *frozen.flags()],
                               verify_dir, results, binary, [compiler, job, proof], report, save)
        verify_report = frozen.compare(verified, accepted, 'verify')
        for key in ('invocations', 'semantic_events', 'records', 'transport'):
            native.require(proof_report[key] == verify_report[key], 'fresh report coordinate: ' + key)
        artifact = verify_dir / 'compiler.dag'
        native.require(frozen.identity(artifact)['sha256'] == frozen.PROFILE['expected_artifact_sha256'], 'exact C2/C3 ART1 bytes')
        shutil.copy2(artifact, results / 'compiler.dag')
        after = native.inventory(family, spec['sources'], run, 'after')
        host.save(results / 'sources-after.json', after)
        native.require(after == before, 'source files changed')
        report['frozen_inputs_after'] = {name: frozen.identity(package / name) for name in report['frozen_inputs_before']}
        native.require(report['frozen_inputs_after'] == report['frozen_inputs_before'], 'frozen inputs changed')
        native.require(frozen.identity(binary) == {k: report['binary'][k] for k in ('bytes', 'sha256')}, 'binary changed')
        report.update(status='passed', verification=verify_report, proof=dict(path=str(proof), **frozen.identity(proof)),
                      compiled=frozen.identity(artifact))
        host.save(results / 'retention-input.json', dict(proof=report['proof'], generation=args.generation,
                  report=str(results / 'receipt.json'), work=str(work)))
    except BaseException:
        report.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        report['source_inventory_identities'] = {name: frozen.identity(results / name) for name in ('sources-before.json', 'sources-after.json') if (results / name).exists()}
        save()


if __name__ == '__main__':
    main()
