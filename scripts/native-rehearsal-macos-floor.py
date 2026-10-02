"""Verify six exact native corpora and the installed kit on macOS 14 ARM."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback

TARGET = 'aarch64-apple-darwin'
TARGETS = {
    TARGET, 'x86_64-apple-darwin', 'aarch64-unknown-linux-gnu',
    'x86_64-unknown-linux-gnu', 'aarch64-pc-windows-msvc', 'x86_64-pc-windows-msvc',
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    actual_host = dict(system=platform.system(), version=platform.mac_ver()[0],
                       machine=platform.machine().lower())
    if (actual_host['system'] != 'Darwin' or not actual_host['version'].startswith('14.')
            or actual_host['machine'] != 'arm64'):
        raise ValueError('actual native macOS 14 ARM host required: ' + repr(actual_host))
    root = Path.cwd()
    config = json.loads((root / '.github/native-rehearsal-macos-floor.json').read_text())
    selector = root / '.github/release-candidate.json'
    selected = json.loads(selector.read_text())
    if sha(selector) != config['selector_sha256'] or selected['source_sha256'] != config['source_sha256']:
        raise ValueError('consumer selector identity changed')
    if (selected.get('phase') != 'verify' or set(selected['binaries']) != TARGETS
            or len(selected['corpora']) != 6
            or {row['target'] for row in selected['corpora']} != TARGETS):
        raise ValueError('exact six-producer verification selector required')
    output = root / 'macos-floor-results'
    output.mkdir()
    report = dict(schema='native/macos-floor-consumer/v1', scope=config['scope'],
                  actual_host=actual_host, status='running', selector_sha256=sha(selector),
                  source_sha256=selected['source_sha256'], target=TARGET,
                  started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  bootstrap_sha256=sha(root / 'scripts/native-candidate.py'),
                  driver_sha256=sha(Path(__file__)), revision=os.environ.get('GITHUB_SHA'),
                  rss_limit_bytes=5 * 1024**3, time_limit_seconds=1800,
                  peak_process_group_rss_bytes=0, commands=[])

    def save():
        (output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')

    child = None
    save()
    try:
        # These host tools are inspected only. No Cargo build, Rust compiler,
        # or prover is invoked by the selected verification phase.
        commands = {
            'os': ['sw_vers'], 'kernel': ['uname', '-a'], 'architecture': ['arch'],
            'memory': ['sysctl', '-n', 'hw.memsize'], 'python': [sys.executable, '-VV'],
            'host-rustc': ['rustc', '-vV'], 'host-cargo': ['cargo', '-Vv'],
        }
        for name, command in commands.items():
            result = subprocess.run(command, capture_output=True)
            row = dict(name=name, command=command, exit_code=result.returncode)
            for stream in ('stdout', 'stderr'):
                path = output / (name + '.' + stream)
                path.write_bytes(getattr(result, stream))
                row[stream] = dict(path=path.name, sha256=sha(path), bytes=path.stat().st_size)
            report['commands'].append(row)
            save()
            if result.returncode:
                raise RuntimeError('host inspection failed: ' + name)
        env = dict(os.environ, RELEASE_TARGET=TARGET, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
        env.pop('PYTHONOPTIMIZE', None)
        command = [sys.executable, '-B', 'scripts/native-candidate.py']
        report['consumer_command'] = command
        started = time.monotonic()
        stopped = None
        with (output / 'consumer.stdout').open('xb') as stdout, (output / 'consumer.stderr').open('xb') as stderr, (output / 'resources.jsonl').open('x') as samples:
            child = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            report['consumer_pid'] = child.pid
            while child.poll() is None:
                rows = subprocess.check_output(['ps', '-axo', 'pgid=,rss='], text=True).splitlines()
                rss = sum(int(parts[1]) * 1024 for line in rows
                          if len(parts := line.split()) == 2 and int(parts[0]) == child.pid)
                elapsed = time.monotonic() - started
                report['peak_process_group_rss_bytes'] = max(report['peak_process_group_rss_bytes'], rss)
                samples.write(json.dumps(dict(elapsed_seconds=elapsed, rss_bytes=rss)) + '\n')
                samples.flush()
                save()
                if rss > report['rss_limit_bytes'] or elapsed > report['time_limit_seconds']:
                    stopped = 'rss' if rss > report['rss_limit_bytes'] else 'time'
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                    break
                time.sleep(2)
            report.update(exit_code=child.wait(), resource_stop=stopped, elapsed_seconds=time.monotonic() - started)
        if report['exit_code'] or stopped:
            raise RuntimeError('bounded native consumer did not complete successfully')
        installed = Path(os.environ['RUNNER_TEMP']) / 'cyber-candidate/installed/cyber-tools/candidate.json'
        candidate = json.loads(installed.read_text())
        helper_spec = importlib.util.spec_from_file_location('transport', root / 'scripts/transport-native-rehearsal.py')
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        report['producer_rustc'] = helper.require_pinned_toolchain(candidate, TARGET)
        shutil.copyfile(installed, output / 'candidate.json')
        report['candidate_sha256'] = sha(installed)
        report['verifications'] = []
        for index, corpus in enumerate(selected['corpora']):
            path = root / 'release-results' / f'verification-{index}.json'
            verification = json.loads(path.read_text())
            if verification.get('all_checks_passed') is not True or len(verification['cases']) != 47:
                raise ValueError('incomplete corpus verification')
            report['verifications'].append(dict(target=corpus['target'], receipt=path.name, sha256=sha(path)))
        report['status'] = 'passed'
    except BaseException:
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        report.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        report['ended'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    main()
