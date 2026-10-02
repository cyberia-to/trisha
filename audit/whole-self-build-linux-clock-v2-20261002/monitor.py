"""Bounded read-only phase observations for the reviewed v2 Actions run."""
import datetime
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time

ROOT = Path(__file__).resolve().parent
RUN = 36976540959
HEAD = '142198726fdec26dae87e2f694da2c2252fefb0f'
MAX_SECONDS = 12 * 60 * 60
MAX_BYTES = 128 * 1024**2


def identity(path):
    return dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def command(directory, label, endpoint):
    output, error = directory / (label + '.json'), directory / (label + '.stderr')
    argv = ['gh', 'api', endpoint]
    record = dict(argv=argv, started_ns=time.time_ns())
    def bound():
        resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024**2,) * 2)
    try:
        with output.open('xb') as stdout, error.open('xb') as stderr:
            result = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=60, preexec_fn=bound)
        record['exit_code'] = result.returncode
    finally:
        record.update(ended_ns=time.time_ns(), stdout=identity(output), stderr=identity(error))
        (directory / (label + '.command.json')).write_text(json.dumps(record, indent=2) + '\n')
    if record['exit_code']:
        raise RuntimeError(label + ': read-only API request failed; raw bytes retained')
    return json.loads(output.read_text())


def main():
    directory = ROOT / 'snapshots'; directory.mkdir()
    previous, failures = None, 0
    started = time.monotonic()
    index = 0
    with (ROOT / 'phase-events.jsonl').open('x') as events:
        while time.monotonic() - started < MAX_SECONDS:
            if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) > MAX_BYTES:
                raise RuntimeError('128 MiB monitor evidence ceiling; remote run untouched')
            stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            label = f'{index:04d}'; index += 1
            try:
                value = command(directory, label+'-run', f'repos/cyberia-to/trisha/actions/runs/{RUN}')
                if (value['head_sha'], value['run_attempt'], value['event'], value['path']) != (HEAD, 1, 'push', '.github/workflows/whole-self-build-v2.yml'):
                    raise RuntimeError('Reviewed run identity changed')
                jobs = command(directory, label+'-jobs', f'repos/cyberia-to/trisha/actions/runs/{RUN}/jobs?per_page=100')
                if jobs['total_count'] != len(jobs['jobs']) or len(jobs['jobs']) > 4:
                    raise RuntimeError('Unexpected job inventory')
                summary = dict(run=RUN, head=HEAD, attempt=1, status=value['status'], conclusion=value['conclusion'],
                               jobs=[dict(id=j['id'], name=j['name'], status=j['status'], conclusion=j['conclusion'],
                                          active=[s['name'] for s in j['steps'] if s['status']=='in_progress']) for j in jobs['jobs']])
                if any(j['name'] not in ('c1 / producer','c2 / producer','c1 / verifier','c2 / verifier') for j in summary['jobs']):
                    raise RuntimeError('Unexpected job names')
                failures = 0
                if summary != previous:
                    observed = dict(observed_at=stamp, **summary)
                    events.write(json.dumps(observed)+'\n'); events.flush()
                    print(json.dumps(observed), flush=True)
                    previous = summary
                if value['status'] == 'completed':
                    (ROOT/'monitor-completed.json').write_text(json.dumps(dict(observed_at=stamp, **summary),indent=2)+'\n')
                    return
            except Exception as error:
                failures += 1
                observed = dict(observed_at=stamp, read_only_monitor_error=repr(error), consecutive_errors=failures)
                events.write(json.dumps(observed)+'\n');events.flush();print(json.dumps(observed),flush=True)
                if failures >= 3:
                    raise
            time.sleep(60)
    raise RuntimeError('12-hour local monitor deadline; remote workflow untouched')


if __name__ == '__main__':
    main()
