"""Read exact final Git blobs and reject protected mutations before export."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--family', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('impact', root / 'scripts/final-source-impact.py')
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
helper = impact.helper()
selected = json.loads((root / '.github/final-package-inputs.json').read_text())
report = dict(scope='Read-only final committed source comparison before export; no native gate observation', commands=[], mutations=[])
rows = []
for entry in selected['sources']:
    name, revision = entry['repository'], entry['commit']
    repo = root if name == 'trisha' else args.family / name
    command = ['git', '-C', str(repo), 'ls-tree', '-rz', revision]
    listing = subprocess.check_output(command)
    report['commands'].append(command)
    row = dict(repository=name, commit=revision, mode='committed', files=[])
    command = ['git', '-C', str(repo), 'cat-file', '--batch']
    report['commands'].append(command)
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as child:
        for line in filter(None, listing.split(b'\0')):
            header, path = line.split(b'\t', 1)
            mode, kind, oid = header.decode().split()
            path = path.decode()
            if name in ('trisha', 'trident') and (path.startswith(helper.REPORTING) or path == '.gitattributes'):
                continue
            if name == 'trisha' and path in helper.AUTOMATION:
                continue
            helper.require(kind == 'blob' and mode in ('100644', '100755', '120000'), 'unsupported Git entry')
            child.stdin.write((oid + '\n').encode())
            child.stdin.flush()
            observed, observed_kind, size = child.stdout.readline().decode().split()
            data = child.stdout.read(int(size))
            helper.require(observed == oid and observed_kind == 'blob' and child.stdout.read(1) == b'\n', 'Git batch framing differs')
            row['files'].append(dict(path=path, type='symlink' if mode == '120000' else 'file', bytes=len(data), sha256=helper.digest(data)))
        child.stdin.close()
        helper.require(child.wait() == 0, 'Git batch failed')
    rows.append(row)
references = root / 'audit/final-host-ceiling-package/references'
report['comparison'] = impact.compare_rows(rows, references)
for name, path in (('trisha', 'rs/build.rs'), ('trident', 'build.rs'), ('joy', 'rs/structured/limits.rs'),
                   ('nox', 'Cargo.toml'), ('zheng', 'Cargo.toml'), ('trisha', 'scripts/check-baselines.py')):
    changed = copy.deepcopy(rows)
    row = next(row for row in changed if row['repository'] == name)
    entry = next(row for row in row['files'] if row['path'] == path)
    entry['sha256'] = '0' * 64
    try:
        impact.compare_rows(changed, references)
    except ValueError as error:
        report['mutations'].append(dict(repository=name, path=path, rejected=str(error)))
    else:
        raise ValueError('protected mutation accepted: ' + name + '/' + path)
report.update(status='passed', selector_sha256=helper.sha(root / '.github/final-package-inputs.json'),
              checker_sha256=helper.sha(root / 'scripts/final-source-impact.py'), source_commits=selected['sources'])
with args.output.open('x') as stream:
    stream.write(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(status=report['status'], repositories=len(rows), rejected_mutations=len(report['mutations']))))
