"""Separate clock profile; immutable v1 inputs and logical/resource caps."""
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback

import native_proof_inputs as native
import whole_self_host as original_host
import whole_self_inputs as frozen

require = native.require
identity, load, save = frozen.identity, frozen.load, original_host.save
TARGET = 'x86_64-unknown-linux-gnu'
REPO = 'cyberia-to/trisha'


def profile(checkout, enabled=True):
    value = load(checkout / '.github/whole-v2-profile.json')
    expected = dict(format='native-whole-self-build-clock-v2', enabled=value.get('enabled'),
                    producer_time_ms=14400000, producer_outer_seconds=14700,
                    verifier_time_ms=7200000, verifier_outer_seconds=7500)
    require(value == expected and type(value['enabled']) is bool, 'exact v2 physical clocks')
    require(not enabled or value['enabled'], 'reviewed new Joy pin/profile must be enabled')
    return value


def authorization(checkout):
    require(os.environ.get('GITHUB_REPOSITORY') == REPO, 'fixed repository')
    selected = load(checkout / '.github/whole-v2-activation.json')
    expected = dict(format='whole-proof-clock-v2-activation', repository=REPO,
                    branch='test/0.4-whole-self-build-ci', push_authorized=True,
                    pending_transport_authorized=True)
    require(selected == expected and selected['push_authorized'] is True and
            selected['pending_transport_authorized'] is True, 'reviewed activation and pending transport')
    require(os.environ.get('GITHUB_EVENT_NAME') in ('push', 'workflow_dispatch') and
            os.environ.get('GITHUB_REF') == 'refs/heads/' + selected['branch'], 'fixed reviewed feature branch')
    for name in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
        require(os.environ.get(name, '').isdigit() and int(os.environ[name]) > 0, 'positive run coordinates')
    head = os.environ.get('GITHUB_SHA', '')
    require(len(head) == 40 and all(c in '0123456789abcdef' for c in head), 'exact workflow revision')
    return dict(repository=REPO, run_id=os.environ['GITHUB_RUN_ID'], attempt=os.environ['GITHUB_RUN_ATTEMPT'], head=head)


def bootstrap(checkout):
    names = [str(p.relative_to(checkout)) for p in (checkout / 'scripts').glob('*whole*v2*') if p.is_file()]
    names += ['scripts/native_proof_inputs.py', 'scripts/whole_self_inputs.py', 'scripts/whole_self_host.py',
              '.github/workflows/whole-self-build-v2.yml', '.github/whole-v2-sources.json',
              '.github/workflows/whole-self-build-v2-generation.yml',
              '.github/whole-v2-profile.json', '.github/whole-v2-activation.json', '.github/whole-self-build-input.json']
    return {name: identity(checkout / name) for name in sorted(names)}


def flags(phase, selected):
    result = frozen.flags()
    result[result.index('--time-ms') + 1] = str(selected[phase + '_time_ms'])
    return result


class State:
    def __init__(self, results, create=False, generation=None, phase=None):
        self.results = results.resolve()
        self.checkout = Path.cwd().resolve()
        if create:
            self.results.mkdir()
            self.report = dict(schema='trident/whole-proof-native-phase/v2', status='preparing',
                               generation=generation, phase=phase, run=authorization(self.checkout),
                               profile=profile(self.checkout), bootstrap=bootstrap(self.checkout), commands=[], proof_commands=[])
        else:
            self.report = load(self.results / 'receipt.json')
            require(self.report['run'] == authorization(self.checkout) and self.report['profile'] == profile(self.checkout), 'same authorized phase')
            require(self.report['bootstrap'] == bootstrap(self.checkout), 'bootstrap source unchanged')
        self.env = native.sanitized(os.environ)
        self.work = Path(os.environ['RUNNER_TEMP']) / f"whole-v2-{self.report['phase']}-c{self.report['generation']}"
        self.family, self.package = self.work / 'family', self.work / 'frozen'
        if create:
            self.work.mkdir()
        if 'build_environment' in self.report:
            self.env.update(self.report['build_environment'])

    def persist(self):
        save(self.results / 'receipt.json', self.report)

    def run(self, name, command, cwd=None, environment=None, timeout=1800, output=None):
        require(not any(r['name'] == name for r in self.report['commands']), 'unique command')
        output = output or self.results / (name + '.stdout')
        error = self.results / (name + '.stderr')
        row = dict(name=name, command=list(map(str, command)), cwd=str(cwd or self.work), started_ns=time.time_ns())
        self.report['commands'].append(row)
        self.persist()
        tick = time.monotonic_ns()
        try:
            with output.open('xb') as stdout, error.open('xb') as stderr:
                child = subprocess.run(row['command'], cwd=cwd or self.work, env=environment or self.env,
                                       stdout=stdout, stderr=stderr, timeout=timeout)
            row.update(exit_code=child.returncode, elapsed_ns=time.monotonic_ns() - tick)
        finally:
            row.update(stdout=dict(path=str(output), **identity(output)), stderr=dict(path=str(error), **identity(error)))
            self.persist()
        require(row['exit_code'] == 0, 'command failed: ' + name)
        binary_output = output.parent != self.results
        text = '' if binary_output else output.read_text()
        require(not native.warnings(text + error.read_text(errors='replace')), 'command warnings: ' + name)
        return text

    def paths(self):
        g = self.report['generation']
        return Path(self.report['binary']['path']), self.package / f'inputs/c{g}.dag', self.package / f'inputs/c{g}-job.dag'

    def final_identities(self, label):
        after = native.inventory(self.family, self.report['source_selector']['sources'], self.run, label)
        save(self.results / ('sources-' + label + '.json'), after)
        require(after == load(self.results / 'sources-before.json'), 'unchanged full source inventory')
        inputs = {name: identity(self.package / name) for name in self.report['frozen_inputs_before']}
        require(inputs == self.report['frozen_inputs_before'], 'unchanged frozen files')
        require(bootstrap(self.checkout) == self.report['bootstrap'], 'unchanged bootstrap')
        require(identity(self.paths()[0]) == {k: self.report['binary'][k] for k in ('bytes', 'sha256')}, 'unchanged native executable')
        self.report['frozen_inputs_after'] = inputs
        self.report['source_inventory_identities'] = {p.name: identity(p) for p in self.results.glob('sources-*.json')}
        self.persist()


def prepare(state):
    r, run = state.report, state.run
    native.native_host(TARGET, platform.system(), platform.machine())
    r['host'] = dict(system=platform.system(), machine=platform.machine(), image=os.environ.get('ImageOS'), image_version=os.environ.get('ImageVersion'))
    r['source_selector'] = native.selector(state.checkout / '.github/whole-v2-sources.json')
    require(r['source_selector']['sources']['joy'] != '6e0ec4d8440e2521df08f442d64f54e667044716', 'new reviewed host-ceiling source required')
    r['input_asset'] = frozen.asset_selector(state.checkout / '.github/whole-self-build-input.json')
    require(run('bootstrap-head', ['git', 'rev-parse', 'HEAD'], state.checkout).strip() == r['run']['head'], 'exact checkout')
    require(not run('bootstrap-status', ['git', 'status', '--porcelain=v1', '--untracked-files=all'], state.checkout).strip(), 'clean checkout')
    original_host.cleanup(state.results, run)
    require(os.environ.get('GH_TOKEN'), 'input download token')
    download_env = dict(state.env, GH_TOKEN=os.environ['GH_TOKEN'])
    a = r['input_asset']; endpoint = f"repos/{REPO}/releases/assets/{a['asset_id']}"
    metadata = json.loads(run('input-metadata', ['gh', 'api', endpoint], environment=download_env))
    require(metadata['id'] == a['asset_id'] and metadata['size'] == a['bytes'] and
            metadata['name'] == a['name'] and metadata.get('digest') == 'sha256:' + a['sha256'], 'pinned input server metadata')
    archive = state.work / a['name']
    run('input-download', ['gh', 'api', endpoint, '-H', 'Accept: application/octet-stream'], environment=download_env, output=archive)
    r['frozen_inputs_before'] = frozen.admit(archive, state.package, a)
    r['input_asset_metadata'] = metadata
    native.fetch(state.family, r['source_selector']['sources'], run)
    save(state.results / 'sources-before.json', native.inventory(state.family, r['source_selector']['sources'], run, 'before'))
    state.env.update(RUSTUP_TOOLCHAIN='1.89.0-' + TARGET, CARGO_BUILD_JOBS='2', RUSTFLAGS='-Dwarnings',
                     CARGO_TARGET_DIR=str(state.work / 'target'), CARGO_TERM_COLOR='never')
    manager_env = dict(state.env)
    for key in ('CARGO_HOME', 'RUSTUP_HOME'):
        if key in os.environ:
            manager_env[key] = os.environ[key]
    rustup = shutil.which('rustup', path=state.env['PATH']); require(rustup, 'rustup manager')
    run('install-rust', [rustup, 'toolchain', 'install', state.env['RUSTUP_TOOLCHAIN'], '--profile', 'minimal'], environment=manager_env)
    tools = {name: str(Path(run('resolve-' + name, [rustup, 'which', '--toolchain', state.env['RUSTUP_TOOLCHAIN'], name], environment=manager_env).strip()).resolve(strict=True)) for name in ('rustc', 'cargo', 'rustdoc')}
    require(len({Path(p).parent for p in tools.values()}) == 1, 'one native toolchain')
    state.env.update(CARGO_HOME=str(state.work / 'cargo-home'), RUSTC=tools['rustc'], RUSTDOC=tools['rustdoc'])
    state.env['PATH'] = str(Path(tools['cargo']).parent) + os.pathsep + state.env['PATH']
    r['tools'] = {k: dict(path=p, **identity(p)) for k, p in tools.items()}
    r['build_environment'] = {k: state.env[k] for k in ('PATH', 'CARGO_HOME', 'CARGO_TARGET_DIR', 'RUSTC', 'RUSTDOC', 'RUSTUP_TOOLCHAIN', 'RUSTFLAGS', 'CARGO_BUILD_JOBS')}
    native.native_host(TARGET, platform.system(), platform.machine(), run('rustc-version', [tools['rustc'], '-vV']), run('cargo-version', [tools['cargo'], '-vV']))
    joy = state.family / 'joy'
    run('cargo-fetch', [tools['cargo'], 'fetch', '--manifest-path', joy / 'Cargo.toml', '--locked'], joy)
    metadata = json.loads(run('cargo-metadata', [tools['cargo'], 'metadata', '--manifest-path', joy / 'Cargo.toml', '--format-version', '1', '--locked', '--offline'], joy))
    r['closure'] = native.closure(metadata, state.family, r['source_selector']['sources'])
    run('native-boundary', [sys.executable, '-B', joy / 'scripts/check-soft3-boundary.py'], joy)
    run('native-build', [tools['cargo'], 'build', '--manifest-path', joy / 'Cargo.toml', '--release', '-p', 'cyber-joy', '--locked', '--offline'], joy, timeout=2700)
    binary = state.work / 'target/release/joy'
    shutil.copy2(binary, state.results / 'joy-linux-x64')
    r['binary'] = dict(path=str(binary), **identity(binary))
    binary, compiler, job = state.paths()
    run('repack-job', [binary, 'pack-job', '--compiler', compiler, '--manifest', state.package / 'inputs/package.json', '--output', state.work / 'repacked-job.dag', *frozen.HOST], environment={'PATH': '', 'LANG': 'C.UTF-8'})
    require(identity(state.work / 'repacked-job.dag') == identity(job), 'exact frozen JOB bytes')
    state.final_identities('prepared')
    r['status'] = 'prepared'; state.persist()


def owned_bytes(path):
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


def bounded(state, argv, inputs):
    r = state.report; phase = r['phase']; selected = r['profile']; binary = state.paths()[0]
    directory = state.work / phase; directory.mkdir()
    free_start = frozen.PROFILE['minimum_free_start_bytes'] if phase == 'producer' else 8 * frozen.GIB
    require(shutil.disk_usage(state.work).free >= free_start, 'phase free-start floor')
    env = {'PATH': '', 'LANG': 'C.UTF-8'}
    if 'RUNNER_TRACKING_ID' in os.environ:
        env['RUNNER_TRACKING_ID'] = os.environ['RUNNER_TRACKING_ID']
    row = dict(name=phase, command=list(map(str, argv)), cwd=str(directory), environment=env,
               binary_before=identity(binary), inputs_before={str(p): identity(p) for p in inputs},
               started_ns=time.time_ns(), status='running', sampled_peak_rss_bytes=0)
    r['proof_commands'].append(row); state.persist()
    tick = time.monotonic_ns(); child = None
    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (frozen.PROFILE['attempt_disk_bytes'],) * 2)
    try:
        with (state.results / (phase + '.stdout')).open('xb') as stdout, (state.results / (phase + '.stderr')).open('xb') as stderr, (state.results / (phase + '-resources.jsonl')).open('x') as samples:
            child = subprocess.Popen(row['command'], cwd=directory, env=env, stdout=stdout, stderr=stderr, start_new_session=True, preexec_fn=limits)
            row['pid'] = child.pid
            while child.poll() is None:
                ps = subprocess.check_output(['/bin/ps', '-axo', 'pid=,pgid=,rss='], text=True)
                members = [dict(pid=p, rss_bytes=rss * 1024) for p, group, rss in (map(int, line.split()) for line in ps.splitlines()) if group == child.pid]
                sample = dict(elapsed_ns=time.monotonic_ns()-tick, processes=members, rss_bytes=sum(p['rss_bytes'] for p in members), attempt_bytes=owned_bytes(state.work)+owned_bytes(state.results), free_bytes=shutil.disk_usage(state.work).free)
                row['sampled_peak_rss_bytes'] = max(row['sampled_peak_rss_bytes'], sample['rss_bytes']); row['latest_sample'] = sample
                samples.write(json.dumps(sample)+'\n'); samples.flush(); state.persist()
                reason = ('wall' if sample['elapsed_ns'] > selected[phase + '_outer_seconds'] * 10**9 else
                          'rss' if sample['rss_bytes'] > frozen.PROFILE['sampled_rss_bytes'] else
                          'disk' if sample['attempt_bytes'] > frozen.PROFILE['attempt_disk_bytes'] else
                          'free-disk' if sample['free_bytes'] < 8 * frozen.GIB else None)
                if reason:
                    row['resource_stop'] = reason; original_host.terminate(child); break
                try:
                    child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            row.update(exit_code=child.wait(), elapsed_ns=time.monotonic_ns()-tick)
        require(row['exit_code'] == 0 and 'resource_stop' not in row, 'bounded native phase failed')
        row['status'] = 'passed'
    except BaseException:
        original_host.terminate(child); row.update(status='failed', error=traceback.format_exc()); raise
    finally:
        row['binary_after'] = identity(binary); row['inputs_after'] = {str(p): identity(p) for p in inputs}
        row['logs'] = {s: identity(state.results / (phase + '.' + s)) for s in ('stdout', 'stderr')}
        if row['binary_before'] != row['binary_after'] or row['inputs_before'] != row['inputs_after']:
            row['status'] = 'identity-check-failed'
        state.persist()
    require(row['status'] == 'passed', 'phase identities')
    return load(state.results / (phase + '.stdout'))
