"""Inspect committed Git objects before export; this is not a production guard receipt."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--family', type=Path, required=True)
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('impact', root / 'scripts/current-source-impact.py')
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
refs = root / 'audit/current-native-package/references'
frozen = {row['repository']: row for row in impact.reference(refs, 'frozen-sources.json.gz', impact.FROZEN)}
profile = impact.reference(refs, 'public-profile-sources.json.gz', impact.PROFILE)
inputs = json.loads((root / '.github/current-package-inputs.json').read_text())
report = dict(scope='Pre-export Git object comparison and rejection checks only; no native acceptance or completed matrix claim',
              commands=[], comparisons=[], mutation_rejections=[])
for row in inputs['sources']:
    name, revision = row['repository'], row['commit']
    repo = root if name == 'trisha' else args.family / name
    reference = profile[name] if name in ('joy', 'nox', 'zheng') else frozen[name]
    if name == 'trident':
        exclude = lambda path: path.startswith(('.claude/plans/', 'audit/')) or path == 'reference/self-hosting.md'
    elif name == 'trisha':
        exclude = lambda path: path.startswith(impact.REPORTING) or path in impact.TRISHA_AUTOMATION
    elif name in ('joy', 'nox', 'zheng'):
        exclude = lambda path: path.startswith(impact.REPORTING)
    else:
        exclude = lambda path: False
    command = ['git', '-C', str(repo), 'ls-tree', '-rz', revision]
    listing = subprocess.check_output(command)
    report['commands'].append(command)
    actual = dict(commit=revision, files=[])
    command = ['git', '-C', str(repo), 'cat-file', '--batch']
    report['commands'].append(command)
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as child:
        for line in filter(None, listing.split(b'\0')):
            header, path = line.split(b'\t', 1)
            mode, kind, oid = header.decode().split()
            path = path.decode()
            if exclude(path):
                continue
            impact.require(kind == 'blob' and mode in ('100644', '100755', '120000'), 'unsupported Git object')
            child.stdin.write((oid + '\n').encode()); child.stdin.flush()
            observed, observed_kind, size = child.stdout.readline().decode().split()
            raw = child.stdout.read(int(size)); end = child.stdout.read(1)
            impact.require(observed == oid and observed_kind == 'blob' and end == b'\n', 'Git object framing differs')
            actual['files'].append(dict(path=path, mode=mode, sha256=impact.digest(raw), bytes=len(raw)))
        child.stdin.close()
        impact.require(child.wait() == 0, 'Git batch failed')
    report['comparisons'].append(impact.compare(name, actual, reference, exclude))
    if name in ('trident', 'trisha', 'joy', 'nox', 'zheng'):
        changed = copy.deepcopy(actual)
        selected = next(entry for entry in changed['files'] if entry['path'].endswith('.rs'))
        selected['sha256'] = '0' * 64
        try:
            impact.compare(name, changed, reference, exclude)
        except ValueError as error:
            report['mutation_rejections'].append(dict(repository=name, path=selected['path'], observed=str(error)))
        else:
            raise RuntimeError('changed runtime source was accepted')
report.update(status='passed', checker_sha256=impact.digest((root / 'scripts/current-source-impact.py').read_bytes()))
with args.receipt.open('x') as stream:
    stream.write(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(status=report['status'], repositories=len(report['comparisons']), rejected_changes=len(report['mutation_rejections']))))
