"""Read-only replay of retained local preparation bytes and test outcomes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def identity(path):
    return dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    manifest = json.loads((ROOT / 'files.json').read_text())
    files = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and p != ROOT / 'files.json'}
    assert files == set(manifest), 'exact retained membership'
    for name, expected in manifest.items():
        assert identity(ROOT / name) == expected, name
    review = json.loads((ROOT / 'review-fixes.json').read_text())
    for name, expected in review['sources'].items():
        assert identity(ROOT / 'reviewed-disabled-source' / name) == expected, name
    validation = json.loads((ROOT / 'validation.json').read_text())
    for row in validation['commands']:
        assert row['exit_code'] == 0
        out, err = (ROOT / row['stdout']).read_text(), (ROOT / row['stderr']).read_text()
        if 'tests' in row:
            assert f"Ran {row['tests']} tests" in err and err.endswith('\nOK\n') and 'skipped' not in err
        else:
            assert not out and not err, 'zero actionlint diagnostics'
    assert validation['runtime_profile_enabled'] is False and validation['push_activation_enabled'] is False
    activated = json.loads((ROOT / 'activation/selection.json').read_text())
    repo = ROOT.parents[1]
    for name, expected in activated['enabled_sources'].items():
        assert identity(repo / name) == expected, name
        if name not in activated['changes']:
            assert expected == activated['reviewed_sources'][name], name
        else:
            before = json.loads((ROOT / 'reviewed-disabled-source' / name).read_text())
            after = json.loads((repo / name).read_text())
            for field in activated['changes'][name]:
                assert before[field] is False and after[field] is True
                before[field] = True
            assert before == after, name
    assert identity(ROOT / 'independent-review/review.json')['sha256'] == activated['independent_review_sha256']
    commands = json.loads((ROOT / 'activation/commands.json').read_text())
    assert len(commands) == 2 and all(row['exit_code'] == 0 for row in commands)
    for row in commands:
        for stream in ('stdout', 'stderr'):
            assert identity(ROOT / 'activation' / (row['name'] + '.' + stream)) == row['logs'][stream]
    assert 'Ran 26 tests' in (ROOT / 'activation/tests.stderr').read_text()
    assert (ROOT / 'activation/tests.stderr').read_text().endswith('\nOK\n')
    assert not (ROOT / 'activation/actionlint.stdout').read_bytes()
    assert not (ROOT / 'activation/actionlint.stderr').read_bytes()
    return dict(status='passed-preparation-integrity-replay', files=len(files), reviewed_sources=len(review['sources']), new_tests=16, original_tests=10, remote_v2_execution='not-run')


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
