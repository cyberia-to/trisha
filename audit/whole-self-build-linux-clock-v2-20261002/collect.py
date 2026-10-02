"""Read-only collection for the reviewed completed v2 Actions run."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import time
import zipfile

ROOT = Path(__file__).resolve().parent
RUN = 36976540959
HEAD = '142198726fdec26dae87e2f694da2c2252fefb0f'
REPO = 'cyberia-to/trisha'
GIB = 1024**3


def identity(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024**2):
            digest.update(chunk)
            size += len(chunk)
    return dict(bytes=size, sha256=digest.hexdigest())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def extract(archive, target):
    target.mkdir()
    with zipfile.ZipFile(archive) as stream:
        members = stream.infolist()
        require(len(members) <= 10000 and sum(m.file_size for m in members) <= GIB, 'bounded ZIP inventory')
        seen = set()
        for member in members:
            name = member.filename[:-1] if member.is_dir() else member.filename
            path = PurePosixPath(name)
            require(name and str(path) == name and not path.is_absolute() and '..' not in path.parts and
                    '\\' not in name and ':' not in name and name not in seen, 'unique safe ZIP member')
            seen.add(name)
            mode = member.external_attr >> 16
            require(not stat.S_ISLNK(mode) and (stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)), 'regular ZIP member')
            destination = target / name
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with stream.open(member) as source, destination.open('xb') as output:
                    shutil.copyfileobj(source, output, length=1024**2)
        return {str(p.relative_to(target)): identity(p) for p in sorted(target.rglob('*')) if p.is_file()}


def main():
    out = ROOT / 'completed'
    out.mkdir()
    receipt = dict(schema='whole-self-build-actions-collection-v2', run=RUN, expected_head=HEAD,
                   collector=identity(Path(__file__)), commands=[], archives={}, extracted={}, status='running')

    def save():
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def run(label, endpoint, suffix='.json', cap=256 * 1024**2):
        require(shutil.disk_usage(out).free >= 8 * GIB, 'local evidence free-space floor')
        path = out / (label + suffix)
        error = out / (label + '.stderr')
        command = ['gh', 'api', endpoint]
        row = dict(command=command, started_ns=time.time_ns())
        receipt['commands'].append(row)
        save()
        with path.open('xb') as stdout, error.open('xb') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            try:
                start = time.monotonic()
                while process.poll() is None:
                    require(time.monotonic() - start < 1200, 'bounded evidence download time')
                    require(path.stat().st_size <= cap, 'bounded evidence download bytes')
                    time.sleep(0.25)
                row['exit_code'] = process.returncode
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                row.update(stdout=identity(path), stderr=identity(error))
                save()
        require(row['exit_code'] == 0 and path.stat().st_size <= cap, 'evidence API command failed or exceeded bound')
        return path

    try:
        value = json.loads(run('run', f'repos/{REPO}/actions/runs/{RUN}').read_text())
        require(value['head_sha'] == HEAD and value['event'] == 'push' and value['run_attempt'] == 1 and
                value['status'] == 'completed' and value['path'] == '.github/workflows/whole-self-build-v2.yml', 'exact completed reviewed v2 push run required')
        receipt['conclusion'] = value['conclusion']
        run('jobs', f'repos/{REPO}/actions/runs/{RUN}/jobs?per_page=100')
        listing = json.loads(run('artifacts', f'repos/{REPO}/actions/runs/{RUN}/artifacts?per_page=100').read_text())
        artifacts = listing['artifacts']
        require(listing['total_count'] == len(artifacts) and len(artifacts) <= 6, 'complete bounded artifact list')
        require(len({a['name'] for a in artifacts}) == len(artifacts), 'unique artifact names')
        require(sum(a['size_in_bytes'] for a in artifacts) <= GIB, 'one GiB aggregate ZIP cap')
        expanded = 0
        for asset in artifacts:
            require(asset['name'] in {f'whole-v2-{phase}-c{generation}-1' for phase in ('producer', 'verifier', 'pending') for generation in (1, 2)} and
                    not asset['expired'] and 0 < asset['size_in_bytes'] <= 256 * 1024**2,
                    'expected bounded metadata artifact')
            label = asset['name']
            path = run(label, f"repos/{REPO}/actions/artifacts/{asset['id']}/zip", '.zip')
            value = identity(path)
            require(value['bytes'] == asset['size_in_bytes'], 'server archive byte count')
            if asset.get('digest'):
                require(asset['digest'] == 'sha256:' + value['sha256'], 'server artifact digest')
            receipt['archives'][label] = dict(**value, metadata=asset)
            with zipfile.ZipFile(path) as stream:
                declared = sum(member.file_size for member in stream.infolist())
            require(expanded + declared <= 2 * GIB, 'aggregate decoded cap before extraction')
            receipt['extracted'][label] = extract(path, out / label)
            expanded += sum(row['bytes'] for row in receipt['extracted'][label].values())
            require(expanded <= 2 * GIB, 'two GiB aggregate decoded metadata cap')
            save()
        logs = run('run-logs', f'repos/{REPO}/actions/runs/{RUN}/logs', '.zip')
        receipt['archives']['run-logs'] = identity(logs)
        receipt['extracted']['run-logs'] = extract(logs, out / 'run-logs')
        receipt['status'] = 'passed'
    except BaseException as error:
        receipt.update(status='failed', error=repr(error))
        raise
    finally:
        save()
    print(json.dumps(dict(status=receipt['status'], conclusion=receipt['conclusion'], artifacts=list(receipt['extracted']))))


if __name__ == '__main__':
    main()
