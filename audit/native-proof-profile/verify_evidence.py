"""Verify retained evidence, including the deliberately preserved v2 defect."""
import hashlib
import json
from pathlib import Path
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    audit = Path(__file__).resolve().parent
    root = audit.parent.parent
    sources = json.loads((audit / 'source.json').read_text())
    for path, digest in sources['files'].items():
        assert sha((root / path).read_bytes()) == digest, path
    evidence = json.loads((audit / 'evidence.json').read_text())
    for filename, expected in evidence['archives'].items():
        archive = audit / filename
        assert sha(archive.read_bytes()) == expected['sha256'], filename
        prefix = filename.removesuffix('.tar.gz')
        with tarfile.open(archive) as stream:
            members = [m for m in stream.getmembers() if m.isfile()]
            assert len(members) == expected['files']
            data = {m.name.removeprefix(prefix + '/'): stream.extractfile(m).read()
                    for m in members}
        assert sha(data['receipt.json']) == expected['receipt_sha256']
        receipt = json.loads(data['receipt.json'])
        mismatches = []
        for command in receipt['commands']:
            for channel in ('stdout', 'stderr'):
                log = command.get(channel)
                if log and sha(data[log['path']]) != log['sha256']:
                    mismatches.append(command['name'] + '.' + channel)
        assert sorted(mismatches) == expected['command_log_hash_mismatches']
        if prefix.endswith('-v3'):
            assert not mismatches and receipt['status'] == 'passed'
            assert not receipt['failures']
            assert len({c['name'] for c in receipt['commands']}) == len(receipt['commands'])
            assert all(c['exit_code'] == 0 and not c['warnings'] for c in receipt['commands'])
            assert data['sources-before.json'] == data['sources-after.json']
            assert sha(data['sources-before.json']) == receipt['sources_before_sha256']
            assert sha(data['sources-after.json']) == receipt['sources_after_sha256']
            for path, digest in receipt['bootstrap'].items():
                assert sha((root / path).read_bytes()) == digest, path
            binary = receipt['joy_binary']
            assert len(data[binary['path']]) == binary['bytes']
            assert sha(data[binary['path']]) == binary['sha256']
        print(filename, expected['assessment'], len(members), 'files verified')
    checks = json.loads((audit / 'static-checks.json').read_text())
    for name in ('actionlint-version', 'actionlint', 'guard-tests'):
        assert checks[name]['exit_code'] == 0
        for channel in ('stdout', 'stderr'):
            assert sha((audit / (name + '.' + channel)).read_bytes()) == checks[name][channel + '_sha256']
    print('reviewed source, static checks and evidence integrity verified')


if __name__ == '__main__':
    main()
