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


def download(asset, destination, env):
    with destination.open('xb') as stream:
        subprocess.run(['gh', 'api', '-H', 'Accept: application/octet-stream',
                        f"repos/cyberia-to/trisha/releases/assets/{int(asset['asset_id'])}"],
                       stdout=stream, check=True, env=env)
    if sha(destination) != asset['sha256']:
        raise ValueError(f'asset hash mismatch: {destination.name}')


def main():
    checkout = Path.cwd()
    spec = json.loads((checkout/'.github/release-candidate.json').read_text())
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
               RAYON_NUM_THREADS='4', TVM_LDE_TRACE='no_cache', PYTHONDONTWRITEBYTECODE='1')
    env.pop('RUSTFLAGS', None)
    env.pop('CARGO_ENCODED_RUSTFLAGS', None)
    try:
        archive = work/'source.tar.gz'
        download(dict(asset_id=spec['asset_id'], sha256=spec['source_sha256']), archive, env)
        extension = '.zip' if os.name == 'nt' else '.tar.gz'
        if spec.get('phase') == 'verify':
            download(spec['binaries'][target], work/('binary'+extension), env)
            for index, corpus in enumerate(spec['corpora']):
                download(corpus, work/f'corpus-{index}.tar.gz', env)
        env.pop('GH_TOKEN', None)
        env.pop('GITHUB_TOKEN', None)
        if sha(archive) != spec['source_sha256']:
            raise ValueError('source archive hash mismatch')
        extract(archive, work/'unpacked')
        source = work/'unpacked/cyber-source'
        scripts = source/'trisha/scripts'
        run([sys.executable, '-B', scripts/'verify-source.py', source], results/'source.log', env, work)
        if spec.get('phase') == 'verify':
            extract(work/('binary'+extension), work/'installed')
            candidate = json.loads((work/'installed/cyber-tools/candidate.json').read_text())
            if candidate['provenance_sha256'] != sha(source/'sources.json'):
                raise ValueError('validator and installed binaries have different source inventories')
            for index, corpus in enumerate(spec['corpora']):
                extract(work/f'corpus-{index}.tar.gz', work/f'corpus-{index}')
                run([sys.executable, '-B', scripts/'verify-corpus.py',
                     work/f'corpus-{index}/proof-corpus', '--candidate', work/'installed/cyber-tools',
                     '--receipt', results/f'verification-{index}.json'],
                    results/f'verification-{index}.log', env, work)
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
        run(['rustup', 'toolchain', 'install', '1.89.0', '--profile', 'minimal'], results/'toolchain.log', env, work)
        actual_target = subprocess.check_output(['rustc', '-vV'], env=env, text=True)
        if f'host: {target}\n' not in actual_target:
            raise ValueError(f'toolchain is not native to requested target: {actual_target}')
        if os.name == 'nt':
            run([sys.executable, '-B', scripts/'test_windows_process.py'], results/'windows-process.log', env, work)
        candidate = work/'candidate'
        run([nu, '--no-config-file', scripts/'build-candidate.nu', source, candidate],
            results/'build.log', env, work)
        # Reuse Cargo outputs, while the installed copies keep their exact build
        # identities. CPU/default feature suites match the shipped feature set.
        env['CARGO_TARGET_DIR'] = str(candidate/'build')
        env['PATH'] = str(candidate/'bin') + os.pathsep + env['PATH']
        for project in ('trident', 'trisha', 'joy'):
            command = ['cargo', 'test', '--manifest-path', source/project/'Cargo.toml',
                       '--release', '--locked']
            if project == 'trisha':
                for package in ('trisha', 'trisha-rs', 'trisha-neptune', 'trisha-honeycrisp'):
                    command += ['-p', package]
            else:
                command += ['--workspace']
            run(command + ['--', '--test-threads=1'], results/(project+'-tests.log'), env, work)
        smoke = work/'smoke пробел'
        run([nu, '--no-config-file', scripts/'smoke-release.nu', candidate/'bin', smoke],
            results/'smoke.log', env, work)
        run([sys.executable, '-B', scripts/'verify-corpus.py', smoke, '--seal'],
            results/'corpus-seal.log', env, work)
        run([sys.executable, '-B', scripts/'verify-corpus.py', smoke,
             '--candidate', candidate, '--receipt', results/'local-corpus-verification.json'],
            results/'local-corpus-verification.log', env, work)
        output = results/f'cyber-tools-{target}{extension}'
        run([nu, '--no-config-file', scripts/'package-binaries.nu', candidate, output,
             '--smoke', smoke/'smoke.json'], results/'package.log', env, work)
        # Repack the exact same validated inputs and compare bytes.
        duplicate = work/('repacked'+extension)
        run([nu, '--no-config-file', scripts/'package-binaries.nu', candidate, duplicate,
             '--smoke', smoke/'smoke.json'], results/'repack.log', env, work)
        if sha(output) != sha(duplicate):
            raise ValueError('binary archives do not reproduce')
        extract(output, work/'installed')
        installed = work/'installed/cyber-tools'
        suffix = '.exe' if os.name == 'nt' else ''
        for entry in json.loads((candidate/'candidate.json').read_text())['binaries']:
            if sha(installed/'bin'/(entry['name']+suffix)) != entry['sha256']:
                raise ValueError('unpacked binary identity changed')
        run([sys.executable, '-B', scripts/'smoke-lsp.py', installed/'bin'/('trident-lsp'+suffix)],
            results/'unpacked-lsp.log', env, work)
        for name in ('candidate.json', 'source-verification.json'):
            shutil.copyfile(candidate/name, results/name)
        shutil.copytree(smoke, results/'proof-corpus')
        run([sys.executable, '-B', scripts/'archive-source.py', smoke,
             results/f'proof-corpus-{target}.tar.gz', '--prefix', 'proof-corpus', '--epoch', '0'],
            results/'corpus-package.log', env, work)
        (results/'archive.json').write_text(json.dumps(dict(target=target, source=spec,
            archive=output.name, sha256=sha(output), platform=platform.platform(),
            runner_revision=os.environ.get('GITHUB_SHA')), indent=2))
        if spec.get('full_baselines', True):
            run([sys.executable, '-B', scripts/'check-baselines.py', candidate,
                 work/'baselines', '--rss-limit-gib', '28'], results/'baseline-monitor.log', env, work)
            shutil.copytree(work/'baselines', results/'baselines')
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
