"""Check downloaded run 36958147193 artifacts against its committed driver."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

HEAD = '2b7017f89a495eb43c0feca6818eb68f35c21a02'
TARGETS = {
    'aarch64-apple-darwin': ('Darwin', 'arm64'),
    'x86_64-apple-darwin': ('Darwin', 'x86_64'),
    'aarch64-unknown-linux-gnu': ('Linux', 'aarch64'),
    'x86_64-unknown-linux-gnu': ('Linux', 'x86_64'),
    'aarch64-pc-windows-msvc': ('Windows', 'arm64'),
    'x86_64-pc-windows-msvc': ('Windows', 'amd64'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    def committed(path):
        return subprocess.check_output(['git', 'show', HEAD + ':' + path], cwd=root)
    selector_bytes = committed('.github/native-proof-profile.json')
    selector = json.loads(selector_bytes)
    summaries = {}
    inventory = None
    for target, (system, machine) in TARGETS.items():
        def bootstrap_bytes(data):
            # The Actions bootstrap checkout uses Windows' default CRLF
            # conversion. Fresh build-input repositories explicitly disable it.
            if system == 'Windows':
                assert b'\r' not in data
                return data.replace(b'\n', b'\r\n')
            return data
        folder = args.artifacts / ('native-proof-' + target)
        receipt_bytes = (folder / 'receipt.json').read_bytes()
        receipt = json.loads(receipt_bytes)
        assert receipt['status'] == 'passed' and not receipt['failures'], target
        assert receipt['runner_revision'] == HEAD and receipt['target'] == target
        assert receipt['selector'] == selector
        assert receipt['selector_sha256'] == sha(bootstrap_bytes(selector_bytes))
        host = receipt['host']
        assert host['system'] == system and host['machine'].lower() == machine
        rustc = (folder / 'rustc.stdout').read_text()
        assert re.search(r'^host: ' + re.escape(target) + '$', rustc, re.M)
        assert re.search(r'^release: 1\.89\.0$', rustc, re.M)
        assert (folder / 'cargo.stdout').read_text().startswith('cargo 1.89.0 ')
        assert set(receipt['bootstrap']) == {'.github/workflows/native-proof-profile.yml',
            'scripts/native-proof-profile.py', 'scripts/native_proof_inputs.py'}
        for path, digest in receipt['bootstrap'].items():
            assert sha(bootstrap_bytes(committed(path))) == digest, path
        commands = receipt['commands']
        assert len({c['name'] for c in commands}) == len(commands)
        counts = {}
        for command in commands:
            assert command['exit_code'] == 0 and not command['warnings'], command['name']
            for channel in ('stdout', 'stderr'):
                record = command[channel]
                data = (folder / record['path']).read_bytes()
                assert len(data) == record['bytes'] and sha(data) == record['sha256']
            output = (folder / command['stdout']['path']).read_text()
            if command['name'] in receipt['tests']:
                passed = sorted(set(re.findall(r'^test (\S+) \.\.\. ok$', output, re.M)))
                assert passed and passed == receipt['tests'][command['name']]
                rows = [tuple(map(int, row)) for row in re.findall(
                    r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored', output)]
                assert rows
                counts[command['name']] = dict(zip(('passed', 'failed', 'ignored'),
                    (sum(row[i] for row in rows) for i in range(3))))
                assert counts[command['name']]['failed'] == 0
        for required in receipt['required_cli_tests']:
            assert any(n == required or n.endswith('::' + required) for n in receipt['tests']['joy-tests'])
        assert len(receipt['required_cli_tests']) == (3 if system == 'Windows' else 4)
        expected_tests = {'joy-tests', 'nox-observer'}
        for mode in ('default', 'all-features'):
            expected_tests.add('zheng-disclosed-' + mode)
            for component in ('memory', 'evaluation', 'stream'):
                expected_tests.add('disclosed_' + component + '_allocation-' + mode)
        assert set(receipt['tests']) == expected_tests
        before = (folder / 'sources-before.json').read_bytes()
        after = (folder / 'sources-after.json').read_bytes()
        assert before == after and sha(before) == receipt['sources_before_sha256']
        assert sha(after) == receipt['sources_after_sha256']
        sources = json.loads(before)
        assert set(sources) == set(selector['sources'])
        for repository, revision in selector['sources'].items():
            assert sources[repository]['commit'] == revision
            assert (folder / (repository + '-head.stdout')).read_text().strip() == revision
            for phase in ('before', 'after'):
                assert not (folder / (repository + '-status-' + phase + '.stdout')).read_bytes()
        if inventory is None:
            inventory = sources
        assert sources == inventory, 'native source inventory differs: ' + target
        binary = receipt['joy_binary']
        data = (folder / binary['path']).read_bytes()
        assert len(data) == binary['bytes'] and sha(data) == binary['sha256']
        summaries[target] = dict(receipt_sha256=sha(receipt_bytes), host=host,
            tools=receipt['tools'], tests=counts, binary=binary, commands=len(commands),
            bootstrap_newlines='CRLF' if system == 'Windows' else 'LF')
    canonical_inventory = json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()
    print(json.dumps(dict(run=36958147193, head=HEAD, status='passed',
        canonical_source_inventory_sha256=sha(canonical_inventory), platforms=summaries), indent=2))


if __name__ == '__main__':
    main()
