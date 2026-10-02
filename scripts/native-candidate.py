"""Build and test a hash-pinned coordinated source archive on a native CI host.

The checkout supplies only this bootstrap and the candidate selector. Compiler,
warrior, packaging and test implementations all come from the verified archive.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import traceback
import urllib.request
import zipfile

NU = {
    'aarch64-apple-darwin': 'a61806761db7bc2eddfc313d5ec496c92776a37124bc64a3036374bd55e8c881',
    'x86_64-apple-darwin': '8de1dc4a918a1af29fce75d263a8f673f16d35c04ebaa5e3c3ac4ce1eb154f3f',
    'aarch64-unknown-linux-gnu': 'c25a713f4c10bd886162c62c278db6cf8a657754be53d33379af70fbadab07b8',
    'x86_64-unknown-linux-gnu': '4038c171dd2618f2413a2aa615b8dab7e9d04852be8200f1755df3e422328395',
    'aarch64-pc-windows-msvc': 'badc7536bf502b3d46c5abf6dc84d394641f407617e6be99cc8346fe946c5550',
    'x86_64-pc-windows-msvc': 'db57750ec878365135e7baebee9f5ec74b84c80158ed0168f1ccbe15d6ec251d',
}

Z3 = {
    'aarch64-apple-darwin': ('z3-4.15.3-arm64-osx-13.7.6.zip', '941659417b5464a361c49089658509f3118a0c3e8d4f8a1dc999f8b5cd1f3c71'),
    'x86_64-apple-darwin': ('z3-4.15.3-x64-osx-13.7.6.zip', '82df675b8b7c4af2e7d8ef94056fcd6fb626198e2855d976134c878f243c96a0'),
    'aarch64-unknown-linux-gnu': ('z3-4.15.3-arm64-glibc-2.34.zip', '78b383374905a20af7f38cb3e8e9e8e38c5cb3d23a8c2fbf8f54ff4b41a9c605'),
    'x86_64-unknown-linux-gnu': ('z3_solver-4.15.3.0-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl', 'a9afd9ceb290482097474d43f08415bcc1874f433189d1449f6c1508e9c68384'),
    'aarch64-pc-windows-msvc': ('z3-4.15.3-arm64-win.zip', '3883e683d81c54a43a5d5bd7d8a6e87174223e0f9b8c76d64d19de7b7bcca373'),
    'x86_64-pc-windows-msvc': ('z3-4.15.3-x64-win.zip', '5091684243e7d7cd57da81991d27ee50aa97333757e53d42d0fc1b7429c99408'),
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(command, log, env, cwd):
    print('Running:', ' '.join(map(str, command)), flush=True)
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(list(map(str, command)), stdout=stream,
                                stderr=subprocess.STDOUT, env=env, cwd=cwd)
    if result.returncode:
        print(log.read_text(encoding='utf-8', errors='replace')[-16000:], flush=True)
        raise RuntimeError(f'command exited {result.returncode}; see {log.name}')


def pin_toolchain(env, target, results, work):
    # RUSTUP_TOOLCHAIN affects rustup shims, not a Homebrew/system compiler
    # earlier in PATH. Resolve the actual tools before compiling any source.
    toolchain = '1.89.0-' + target
    for name in ('RUSTC', 'RUSTDOC', 'RUSTC_WRAPPER', 'RUSTC_WORKSPACE_WRAPPER',
                 'RUSTDOCFLAGS', 'CARGO_ENCODED_RUSTDOCFLAGS', 'CARGO_BUILD_TARGET',
                 'CARGO_BUILD_RUSTC', 'CARGO_BUILD_RUSTDOC', 'CARGO_BUILD_RUSTC_WRAPPER',
                 'CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER', 'CARGO_BUILD_RUSTDOCFLAGS'):
        env.pop(name, None)
    env['RUSTUP_TOOLCHAIN'] = toolchain
    paths = {}
    for name in ('rustc', 'cargo', 'rustdoc'):
        log = results / (name + '-path.log')
        run(['rustup', 'which', '--toolchain', toolchain, name], log, env, work)
        paths[name] = Path(log.read_text(encoding='utf-8').strip())
    if len({path.parent for path in paths.values()}) != 1:
        raise ValueError('Rust, Cargo and rustdoc must come from the same pinned toolchain')
    env['PATH'] = str(paths['rustc'].parent) + os.pathsep + env['PATH']
    env['RUSTC'] = str(paths['rustc'])
    env['RUSTDOC'] = str(paths['rustdoc'])
    observed = {}
    for name, flag in (('rustc', '-vV'), ('cargo', '-Vv'), ('rustdoc', '-vV')):
        log = results / (name + '.log')
        run([paths[name], flag], log, env, work)
        version = log.read_text(encoding='utf-8')
        if not version.startswith(name + ' 1.89.0 '):
            raise ValueError('actual ' + name + ' is not pinned 1.89.0')
        observed[name] = dict(path=str(paths[name]), sha256=sha(paths[name]), version=version)
    if f'host: {target}\n' not in observed['rustc']['version']:
        raise ValueError('pinned toolchain is not native to requested target')
    (results / 'toolchain-paths.json').write_text(json.dumps(observed, indent=2) + '\n')


def extract(archive, destination):
    destination.mkdir()
    if archive.suffix in ('.zip', '.whl'):
        with zipfile.ZipFile(archive) as content:
            for entry in content.infolist():
                if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                    raise ValueError('ZIP entry escapes extraction root')
            content.extractall(destination)
    else:
        with tarfile.open(archive) as content:
            content.extractall(destination, filter='data')


def download(asset, destination, env, maximum=None):
    with destination.open('xb') as stream:
        command = ['gh', 'api', '-H', 'Accept: application/octet-stream',
                   f"repos/cyberia-to/trisha/releases/assets/{int(asset['asset_id'])}"]
        if maximum is None:
            subprocess.run(command, stdout=stream, check=True, env=env)
        else:
            with subprocess.Popen(command, stdout=subprocess.PIPE, env=env) as child:
                try:
                    remaining = maximum
                    while block := child.stdout.read(min(1 << 20, remaining + 1)):
                        if len(block) > remaining:
                            raise ValueError('download byte limit exceeded')
                        stream.write(block)
                        remaining -= len(block)
                    if child.wait():
                        raise ValueError('asset download failed')
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait()
    if sha(destination) != asset['sha256']:
        raise ValueError(f'asset hash mismatch: {destination.name}')


def full_baselines(candidate, scripts, checkout, work, results, env, final):
    if final:
        command = [sys.executable, '-B', checkout/'scripts/inherit-full-baselines.py',
                   '--candidate', candidate, '--reference-archive', work/'source734-full198.tar.gz',
                   '--references', checkout/'audit/final-host-ceiling-package/references',
                   '--output', results/'baseline-inheritance.json']
        print('Running:', ' '.join(map(str, command)), flush=True)
        with (results/'baseline-inheritance.log').open('w', encoding='utf-8') as stream:
            observed = subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.STDOUT, env=env, cwd=work)
        if observed.returncode not in (0, 3):
            raise ValueError('original full198 evidence check failed; inheritance fails closed')
        inheritance = json.loads((results/'baseline-inheritance.json').read_text())
        expected = 'inherited_full198_coverage' if observed.returncode == 0 else 'needs_fresh_full198'
        if (inheritance['status'] != expected or inheritance['fresh_run_performed'] is not False
                or inheritance['final_candidate_sha256'] != sha(candidate/'candidate.json')):
            raise ValueError('full198 inheritance decision differs from actual candidate')
        if observed.returncode == 0:
            if inheritance['inherited_verified_proofs'] != 198 or inheritance['reasons']:
                raise ValueError('inherited full198 coverage is incomplete')
            return
        if inheritance['inherited_verified_proofs'] is not None or not inheritance['reasons']:
            raise ValueError('fresh full198 fallback decision is incomplete')
    run([sys.executable, '-B', scripts/'check-baselines.py', candidate,
         work/'baselines', '--rss-limit-gib', '28'], results/'baseline-monitor.log', env, work)
    shutil.copytree(work/'baselines', results/'baselines')


def main():
    # Native Windows redirected consoles otherwise use cp1252, including when
    # printing a failing Rust diagnostic or the Unicode smoke directory.
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    checkout = Path.cwd()
    selector = checkout / os.environ.get('RELEASE_SELECTOR', '.github/release-candidate.json')
    spec = json.loads(selector.read_text())
    profile = spec.get('validation_profile', 'original')
    if profile not in ('original', 'current-package-v1', 'final-host-ceiling-v1'):
        raise ValueError('unknown native validation profile')
    final = profile == 'final-host-ceiling-v1'
    if final and spec.get('status') != 'active':
        raise ValueError('final package selector is not activated')
    current = profile in ('current-package-v1', 'final-host-ceiling-v1')
    if current:
        inputs = checkout / ('.github/final-package-inputs.json' if final else '.github/current-package-inputs.json')
        if sha(inputs) != spec['inputs_sha256']:
            raise ValueError('current package input selector differs')
        selected_inputs = json.loads(inputs.read_text())
        if selected_inputs['source_sha256'] != spec['source_sha256']:
            raise ValueError('current package source selection differs')
        if selected_inputs['validation_profile'] != profile:
            raise ValueError('input validation profile differs')
        if spec.get('phase') == 'verify':
            expected = set(NU)
            for field in ('corpora', 'structured_corpora'):
                rows = spec[field]
                if len(rows) != 6 or {row['target'] for row in rows} != expected:
                    raise ValueError('all six unique producer corpora are required')
    target = os.environ['RELEASE_TARGET']
    expected_machine = 'arm64' if target.startswith('aarch64') else 'x86_64'
    actual_machine = platform.machine().lower().replace('amd64', 'x86_64').replace('aarch64', 'arm64')
    if actual_machine != expected_machine:
        raise ValueError(f'native architecture mismatch: {actual_machine} != {expected_machine}')
    work = Path(os.environ['RUNNER_TEMP'])/'cyber-candidate'
    work.mkdir()
    results = checkout/'release-results'
    results.mkdir()
    env = dict(os.environ, RUSTUP_TOOLCHAIN='1.89.0', CARGO_BUILD_JOBS='2',
               RAYON_NUM_THREADS='4', TVM_LDE_TRACE='no_cache', PYTHONDONTWRITEBYTECODE='1',
               PYTHONUTF8='1')
    env.pop('RUSTFLAGS', None)
    env.pop('CARGO_ENCODED_RUSTFLAGS', None)
    try:
        archive = work/'source.tar.gz'
        download(dict(asset_id=spec['asset_id'], sha256=spec['source_sha256']), archive, env)
        kit_archive = work/'selfhost-kit.tar.gz'
        download(spec['selfhost_kit'], kit_archive, env, maximum=128 << 20)
        if spec.get('neptune_intent'):
            download(spec['neptune_intent'], work/'deployment-intent.json', env)
        if final and spec.get('full_baselines', False):
            reference = spec['baseline_reference']
            if reference != dict(asset_id=605010237, sha256='54db68904fc8c92f1446c46cb7b90345a05e026a92b46e6ccb259822a3328204'):
                raise ValueError('exact original source734 full198 reference required')
            download(reference, work/'source734-full198.tar.gz', env, maximum=96 << 20)
        extension = '.zip' if os.name == 'nt' else '.tar.gz'
        if spec.get('phase') == 'verify':
            download(spec['binaries'][target], work/('binary'+extension), env)
            for index, corpus in enumerate(spec['corpora']):
                download(corpus, work/f'corpus-{index}.tar.gz', env)
            if current:
                for index, corpus in enumerate(spec['structured_corpora']):
                    download(corpus, work/f'structured-{index}.tar.gz', env)
        env.pop('GH_TOKEN', None)
        env.pop('GITHUB_TOKEN', None)
        if sha(archive) != spec['source_sha256']:
            raise ValueError('source archive hash mismatch')
        extract(archive, work/'unpacked')
        source = work/'unpacked/cyber-source'
        scripts = source/'trisha/scripts'
        run([sys.executable, '-B', scripts/'verify-source.py', source], results/'source.log', env, work)
        if current:
            impact = 'final-source-impact.py' if final else 'current-source-impact.py'
            references = 'final-host-ceiling-package' if final else 'current-native-package'
            run([sys.executable, '-B', checkout/'scripts'/impact, '--source', source,
                 '--inputs', inputs, '--references', checkout/'audit'/references/'references',
                 '--receipt', results/'source-impact.json'], results/'source-impact.log', env, work)
        kit = work/'selfhost-kit'
        run([sys.executable, '-B', scripts/'selfhost-kit.py', 'unpack', '--archive', kit_archive,
             '--sha256', spec['selfhost_kit']['sha256'], '--trident', source/'trident', '--output', kit],
            results/'selfhost-kit.log', env, work)
        def kit_smoke(binary_root, inputs, output):
            if sha(inputs/'kit.json') != sha(kit/'kit.json'):
                raise ValueError('shipped kit differs from selected portable archive')
            run([sys.executable, '-B', scripts/'selfhost-kit.py', 'smoke', '--kit', inputs,
                 '--joy', binary_root/'bin'/('joy.exe' if os.name == 'nt' else 'joy'),
                 '--trident', source/'trident', '--output', output],
                output.with_suffix('.log'), env, work)
        if spec.get('phase') == 'verify':
            extract(work/('binary'+extension), work/'installed')
            candidate = json.loads((work/'installed/cyber-tools/candidate.json').read_text())
            if candidate['provenance_sha256'] != sha(source/'sources.json'):
                raise ValueError('validator and installed binaries have different source inventories')
            kit_smoke(work/'installed/cyber-tools', work/'installed/cyber-tools/share/trident-selfhost',
                      results/'verified-selfhost-smoke')
            for index, corpus in enumerate(spec['corpora']):
                extract(work/f'corpus-{index}.tar.gz', work/f'corpus-{index}')
                run([sys.executable, '-B', scripts/'verify-corpus.py',
                     work/f'corpus-{index}/proof-corpus', '--candidate', work/'installed/cyber-tools',
                     '--receipt', results/f'verification-{index}.json'],
                    results/f'verification-{index}.log', env, work)
            if current:
                for index, corpus in enumerate(spec['structured_corpora']):
                    extract(work/f'structured-{index}.tar.gz', work/f'structured-{index}')
                    run([sys.executable, '-B', checkout/'scripts/current-structured-corpus.py', 'verify',
                         '--corpus', work/f'structured-{index}/structured-corpus',
                         '--candidate', work/'installed/cyber-tools',
                         '--receipt', results/f'structured-verification-{index}.json'],
                        results/f'structured-verification-{index}.log', env, work)
            return
        nu_archive = work/('nu'+extension)
        url = f'https://github.com/nushell/nushell/releases/download/0.112.2/nu-0.112.2-{target}{extension}'
        with urllib.request.urlopen(url, timeout=60) as response, nu_archive.open('xb') as stream:
            shutil.copyfileobj(response, stream)
        if sha(nu_archive) != NU[target]:
            raise ValueError('Nushell archive hash mismatch')
        extract(nu_archive, work/'nu')
        nu = next((work/'nu').rglob('nu.exe' if os.name == 'nt' else 'nu'))
        # Python is a build/test tool, never a dependency of the shipped binaries.
        env['PATH'] = os.pathsep.join([str(nu.parent), str(Path(sys.executable).parent), env['PATH']])
        z3_name, z3_sha = Z3[target]
        z3_archive = work/z3_name
        with urllib.request.urlopen('https://github.com/Z3Prover/z3/releases/download/z3-4.15.3/' + z3_name,
                                    timeout=60) as response, z3_archive.open('xb') as stream:
            shutil.copyfileobj(response, stream)
        if sha(z3_archive) != z3_sha:
            raise ValueError('Z3 archive hash mismatch')
        extract(z3_archive, work/'z3')
        z3 = next(p for p in (work/'z3').rglob('z3.exe' if os.name == 'nt' else 'z3') if p.is_file())
        if os.name != 'nt':
            z3.chmod(0o755)
        env['PATH'] = str(z3.parent) + os.pathsep + env['PATH']
        run([z3, '--version'], results/'z3.log', env, work)
        run(['rustup', 'toolchain', 'install', '1.89.0-' + target, '--profile', 'minimal'], results/'toolchain.log', env, work)
        pin_toolchain(env, target, results, work)
        if os.name == 'nt':
            run([sys.executable, '-B', scripts/'test_windows_process.py'], results/'windows-process.log', env, work)
        candidate = work/'candidate'
        run([nu, '--no-config-file', scripts/'build-candidate.nu', source, candidate],
            results/'build.log', env, work)
        kit_smoke(candidate, kit, results/'installed-selfhost-smoke')
        # Reuse Cargo outputs, while the installed copies keep their exact build
        # identities. CPU/default feature suites match the shipped feature set.
        env['RUSTFLAGS'] = json.loads((candidate/'candidate.json').read_text())['rustflags']
        env['PATH'] = str(candidate/'bin') + os.pathsep + env['PATH']
        test_failures = []
        for project in (('trident', 'trisha', 'joy', 'nox') if current else ('trident', 'trisha', 'joy')):
            env['CARGO_TARGET_DIR'] = str(candidate/'build'/project)
            command = ['cargo', 'test', '--manifest-path', source/project/'Cargo.toml',
                       '--release', '--locked', '--no-fail-fast']
            if project == 'trisha':
                for package in ('trisha', 'trisha-rs', 'trisha-neptune', 'trisha-honeycrisp'):
                    command += ['-p', package]
            elif current and project == 'trident':
                command += ['--workspace', '--lib']
            elif project == 'nox':
                command += ['-p', 'cyber-nox', '--features', 'std', '--lib']
            else:
                command += ['--workspace']
            try:
                run(command + ['--', '--test-threads=1'], results/(project+'-tests.log'), env, work)
            except RuntimeError as error:
                test_failures.append(str(error))
        if test_failures:
            raise RuntimeError('workspace tests failed: ' + '; '.join(test_failures))
        # Joy owns the native soft3 proof profiles independently of Trisha.
        run([sys.executable, '-B', source/'joy/scripts/smoke-native.py',
             '--joy', candidate/'bin'/('joy.exe' if os.name == 'nt' else 'joy'),
             '--fixtures', candidate/'share/trisha-release-smoke',
             '--output', results/'joy-native-smoke'], results/'joy-native-smoke.log', env, work)
        run([sys.executable, '-B', source/'trisha/audit/native-installed-probes.py',
             candidate, results/'native-process-files.json'], results/'native-process-files.log', env, work)
        if spec.get('neptune_intent'):
            env['CARGO_TARGET_DIR'] = str(candidate/'build/trisha')
            env['TRISHA_DEPLOY_INTENT'] = str(work/'deployment-intent.json')
            run(['cargo', 'test', '--manifest-path', source/'trisha/Cargo.toml', '--release',
                 '--locked', '-p', 'trisha', '--test', 'deploy_transaction',
                 'genuine_transaction_prepare_and_mock_gateway_process', '--', '--ignored',
                 '--exact', '--test-threads=1'], results/'neptune-client.log', env, work)
            assembly = results/'neptune-lock.tasm'
            run([candidate/'bin'/('trisha'+('.exe' if os.name == 'nt' else '')), 'build',
                 source/'trisha/neptune/tests/fixtures/custom_lock.tri', '--target', 'neptune',
                 '--profile', 'release', '--output', assembly], results/'neptune-lock.log', env, work)
            env['TRISHA_DEPLOY_ASSEMBLY'] = str(assembly)
            run(['cargo', 'test', '--manifest-path', source/'trisha/Cargo.toml', '--release',
                 '--locked', '-p', 'trisha-neptune', '--test', 'deployment',
                 'genuine_custom_lock_transaction_and_binding_mutations', '--', '--ignored',
                 '--exact', '--test-threads=1'], results/'neptune-binding.log', env, work)
            env.pop('TRISHA_DEPLOY_ASSEMBLY')
            env.pop('TRISHA_DEPLOY_INTENT')
        suffix = '.exe' if os.name == 'nt' else ''
        run([candidate/'bin'/('trisha'+suffix), 'bench', source/'trisha/baselines/triton'],
            results/'baseline-execution.log', env, work)
        execution = (results/'baseline-execution.log').read_text(encoding='utf-8').splitlines()
        if (execution.count('133 / 133 fixtures passed; 43 / 43 baselines verified') != 1
                or sum(line.endswith('\tPASS') for line in execution) != 99
                or sum(line.endswith('\tPASS (both executions rejected)') for line in execution) != 34):
            raise ValueError('native baseline execution coverage is incomplete')
        (results/'baseline-execution.json').write_text(json.dumps(dict(
            all_checks_passed=True, source_provenance_sha256=sha(source/'sources.json'),
            candidate_sha256=sha(candidate/'candidate.json'), log_sha256=sha(results/'baseline-execution.log'),
            target=target, baselines=43, positive_fixtures=99, negative_fixtures=34,
            generated_proofs=0), indent=2))
        smoke = work/'smoke пробел'
        run([nu, '--no-config-file', scripts/'smoke-release.nu', candidate/'bin', smoke],
            results/'smoke.log', env, work)
        run([sys.executable, '-B', scripts/'verify-corpus.py', smoke, '--seal'],
            results/'corpus-seal.log', env, work)
        run([sys.executable, '-B', scripts/'verify-corpus.py', smoke,
             '--candidate', candidate, '--receipt', results/'local-corpus-verification.json'],
            results/'local-corpus-verification.log', env, work)
        output = results/f'cyber-tools-{target}{extension}'
        kit_flags = ['--selfhost-kit', kit_archive, '--selfhost-kit-sha256', spec['selfhost_kit']['sha256'],
                     '--selfhost-smoke', results/'installed-selfhost-smoke/receipt.json']
        run([nu, '--no-config-file', scripts/'package-binaries.nu', candidate, output,
             '--smoke', smoke/'smoke.json', *kit_flags], results/'package.log', env, work)
        # Repack the exact same validated inputs and compare bytes.
        duplicate = work/('repacked'+extension)
        run([nu, '--no-config-file', scripts/'package-binaries.nu', candidate, duplicate,
             '--smoke', smoke/'smoke.json', *kit_flags], results/'repack.log', env, work)
        if sha(output) != sha(duplicate):
            raise ValueError('binary archives do not reproduce')
        extract(output, work/'installed')
        installed = work/'installed/cyber-tools'
        suffix = '.exe' if os.name == 'nt' else ''
        for entry in json.loads((candidate/'candidate.json').read_text())['binaries']:
            if sha(installed/'bin'/(entry['name']+suffix)) != entry['sha256']:
                raise ValueError('unpacked binary identity changed')
        kit_smoke(installed, installed/'share/trident-selfhost', results/'unpacked-selfhost-smoke')
        run([sys.executable, '-B', scripts/'smoke-lsp.py', installed/'bin'/('trident-lsp'+suffix)],
            results/'unpacked-lsp.log', env, work)
        if final:
            run([sys.executable, '-B', checkout/'scripts/check-installed-host-ceiling.py', '--source', source,
                 '--candidate', installed, '--output', results/'installed-host-ceiling'],
                results/'installed-host-ceiling.log', env, work)
        if current:
            structured = results/'structured-corpus'
            helper = checkout/'scripts/current-structured-corpus.py'
            run([sys.executable, '-B', helper, 'generate', '--source', source,
                 '--candidate', installed, '--output', structured], results/'structured-generate.log', env, work)
            run([sys.executable, '-B', helper, 'verify', '--corpus', structured,
                 '--candidate', installed, '--receipt', results/'local-structured-verification.json'],
                results/'local-structured-verification.log', env, work)
            run([sys.executable, '-B', scripts/'archive-source.py', structured,
                 results/f'structured-corpus-{target}.tar.gz', '--prefix', 'structured-corpus', '--epoch', '0'],
                results/'structured-package.log', env, work)
        for name in ('candidate.json', 'source-verification.json'):
            shutil.copyfile(candidate/name, results/name)
        shutil.copytree(smoke, results/'proof-corpus')
        run([sys.executable, '-B', scripts/'archive-source.py', smoke,
             results/f'proof-corpus-{target}.tar.gz', '--prefix', 'proof-corpus', '--epoch', '0'],
            results/'corpus-package.log', env, work)
        (results/'archive.json').write_text(json.dumps(dict(target=target, source=spec,
            archive=output.name, sha256=sha(output), platform=platform.platform(),
            runner_revision=os.environ.get('GITHUB_SHA')), indent=2))
        if spec.get('full_baselines', False):
            full_baselines(candidate, scripts, checkout, work, results, env, final)
    except BaseException:
        (results/'failure.txt').write_text(traceback.format_exc())
        raise
    finally:
        for log in work.glob('candidate*/**/*.log'):
            shutil.copyfile(log, results/('candidate-'+log.name))
        if (work/'baselines').exists() and not (results/'baselines').exists():
            shutil.copytree(work/'baselines', results/'baselines')


if __name__ == '__main__':
    main()
