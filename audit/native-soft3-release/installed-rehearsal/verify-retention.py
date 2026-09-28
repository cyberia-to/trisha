#!/usr/bin/env python3
"""Check retained bytes, optionally comparing unchanged local originals."""
import argparse
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('retention', ROOT / 'retain.py')
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


def check_file(base, row):
    path = base / row['path']
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing ordinary file: ' + str(path))
    if retention.identity(path) != {key: row[key] for key in ['bytes', 'sha256']}:
        raise ValueError('identity mismatch: ' + str(path))
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', action='store_true')
    parser.add_argument('--external', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    started = time.time_ns()
    receipt = retention.load(ROOT / 'receipt.json')
    if receipt['status'] != 'passed':
        raise ValueError('retention did not complete')
    if retention.identity(ROOT / 'retain.py') != receipt['driver']:
        raise ValueError('retention driver changed')
    rows = []
    for page in receipt['manifest_pages']:
        rows.extend(retention.load(check_file(ROOT, page)))
    names = [row['path'] for row in rows]
    if len(names) != len(set(names)) or names != sorted(names):
        raise ValueError('duplicate or unordered manifest paths')
    if any(Path(name).is_absolute() or '..' in Path(name).parts for name in names):
        raise ValueError('unsafe manifest path')
    archive = check_file(ROOT, receipt['archive'])
    header = archive.open('rb')
    with header:
        if header.read(8) != b'\x1f\x8b\x08\x00\x00\x00\x00\x00':
            raise ValueError('noncanonical gzip header')
    observed = retention.verify(archive, rows, args.originals)
    expected = receipt['verification']
    for key in ['members', 'raw_bytes']:
        if observed[key] != expected[key]:
            raise ValueError('verification count mismatch')
    external = retention.load(check_file(ROOT, receipt['external_files']))
    if args.external:
        for row in external:
            check_file(Path('/'), row)
    result = {
        'status': 'passed', 'started_ns': started, 'ended_ns': time.time_ns(),
        'receipt': retention.identity(ROOT / 'receipt.json'),
        'checker': retention.identity(Path(__file__)),
        'verification': observed,
        'external_files_rechecked': len(external) if args.external else 0,
        'scope': 'Byte retention only; no build, compiler, proof generation or proof verification invoked',
    }
    if args.output:
        retention.write_json(args.output, result)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
