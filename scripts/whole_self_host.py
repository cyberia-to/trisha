"""Recorded hosted-runner preparation and bounded process execution."""
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import time
import traceback

from native_proof_inputs import require
from whole_self_inputs import GIB, PROFILE, identity

SDK_PATHS = (
    '/usr/local/lib/android', '/usr/share/dotnet', '/opt/ghc', '/usr/local/.ghcup',
    '/usr/local/share/powershell', '/usr/local/share/boost', '/usr/share/swift',
    '/usr/lib/jvm', '/opt/hostedtoolcache/CodeQL', '/opt/hostedtoolcache/go',
    '/opt/hostedtoolcache/Java_Temurin-Hotspot_jdk',
    '/opt/hostedtoolcache/Java_Adopt_jdk', '/opt/hostedtoolcache/Ruby',
)


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def disk(path):
    return dict(zip(('total', 'used', 'free'), shutil.disk_usage(path)))


def cleanup(results, run):
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and
            os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
            os.environ.get('RUNNER_OS') == 'Linux' and os.environ.get('RUNNER_ARCH') == 'X64' and
            platform.system() == 'Linux', 'cleanup is restricted to ephemeral hosted Linux x64')
    record = dict(before=disk(results), allowlist=list(SDK_PATHS), removed=[])
    save(results / 'disk-cleanup.json', record)
    for number, name in enumerate(SDK_PATHS):
        path = Path(name)
        if not path.exists() and not path.is_symlink():
            continue
        require(path.is_dir() and not path.is_symlink(), 'SDK cleanup requires exact real directory')
        run('remove-unused-sdk-' + str(number), ['/usr/bin/sudo', '/bin/rm', '-rf', '--', name], timeout=180)
        require(not path.exists(), 'SDK cleanup failed')
        record['removed'].append(name)
        record['after'] = disk(results)
        save(results / 'disk-cleanup.json', record)
    record['after'] = disk(results)
    save(results / 'disk-cleanup.json', record)


def terminate(child):
    if child is None or child.poll() is not None:
        return
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def cancel(signum, _frame):
    raise InterruptedError('workflow termination signal: ' + str(signum))


def cancellation_handlers():
    signal.signal(signal.SIGTERM, cancel)


def bounded(name, argv, directory, results, binary, frozen, report, save_report):
    directory.mkdir()
    require(disk(directory)['free'] >= (PROFILE['minimum_free_start_bytes'] if name == 'prove' else 8 * GIB), 'whole-proof free-space preflight')
    row = dict(name=name, command=list(map(str, argv)), cwd=str(directory),
               environment={'PATH': ''}, binary_before=identity(binary),
               inputs_before={str(p): identity(p) for p in frozen},
               started_ns=time.time_ns(), sampled_peak_rss_bytes=0, status='running')
    report['proof_commands'].append(row)
    save_report()
    child = None
    tick = time.monotonic_ns()

    def limit():
        cap = PROFILE['attempt_disk_bytes']
        resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))

    try:
        with (results / (name + '.stdout')).open('xb') as stdout, (results / (name + '.stderr')).open('xb') as stderr, (results / (name + '-resources.jsonl')).open('x') as samples:
            # A positive runtime process receives no inherited tokens or build overrides.
            environment = {'PATH': '', 'LANG': 'C.UTF-8'}
            if 'RUNNER_TRACKING_ID' in os.environ:
                environment['RUNNER_TRACKING_ID'] = os.environ['RUNNER_TRACKING_ID']
            child = subprocess.Popen(row['command'], cwd=directory, env=environment, stdout=stdout,
                                     stderr=stderr, start_new_session=True, preexec_fn=limit)
            row['pid'] = child.pid
            while child.poll() is None:
                ps = subprocess.check_output(['/bin/ps', '-axo', 'pid=,pgid=,rss='], text=True)
                members = [dict(pid=p, rss_bytes=rss * 1024)
                           for p, group, rss in (map(int, line.split()) for line in ps.splitlines())
                           if group == child.pid]
                sample = dict(elapsed_ns=time.monotonic_ns() - tick, processes=members,
                              rss_bytes=sum(p['rss_bytes'] for p in members),
                              attempt_bytes=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()),
                              free_bytes=disk(directory)['free'])
                row['sampled_peak_rss_bytes'] = max(row['sampled_peak_rss_bytes'], sample['rss_bytes'])
                row['latest_sample'] = sample
                samples.write(json.dumps(sample) + '\n')
                samples.flush()
                reason = ('wall' if sample['elapsed_ns'] > PROFILE['outer_wall_seconds'] * 10**9 else
                          'rss' if sample['rss_bytes'] > PROFILE['sampled_rss_bytes'] else
                          'attempt-disk' if sample['attempt_bytes'] > PROFILE['attempt_disk_bytes'] else
                          'free-disk' if sample['free_bytes'] < 8 * GIB else None)
                if reason:
                    row['resource_stop'] = reason
                    terminate(child)
                    break
                save_report()
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            row.update(exit_code=child.wait(), elapsed_ns=time.monotonic_ns() - tick)
        require(row['exit_code'] == 0 and 'resource_stop' not in row, 'bounded native command failed')
        row['status'] = 'passed'
    except BaseException:
        terminate(child)
        row.update(status='failed', error=traceback.format_exc())
        raise
    finally:
        try:
            row['binary_after'] = identity(binary)
            row['inputs_after'] = {str(p): identity(p) for p in frozen}
            require(row['binary_before'] == row['binary_after'] and row['inputs_before'] == row['inputs_after'], 'runtime input or binary changed')
        except BaseException:
            row.update(status='identity-check-failed', identity_error=traceback.format_exc())
        row['logs'] = {stream: identity(results / (name + '.' + stream)) for stream in ('stdout', 'stderr') if (results / (name + '.' + stream)).exists()}
        save_report()
    require(row['status'] == 'passed', 'runtime receipt identity failure')
    return json.loads((results / (name + '.stdout')).read_text(encoding='utf-8'))
