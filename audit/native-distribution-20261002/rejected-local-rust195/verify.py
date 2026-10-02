"""Verify the byte-exact rejected attempt without executing any retained input."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--originals', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parent
record = json.loads((root / 'retention.json').read_text())
archive = root / record['archive']['path']
with archive.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
if digest != record['archive']['sha256'] or archive.stat().st_size != record['archive']['bytes']:
    raise ValueError('rejected evidence archive identity changed')
expected = {row['path']: row for row in record['files']}
if len(expected) != len(record['files']):
    raise ValueError('duplicate evidence inventory')
seen = set()
with tarfile.open(archive) as content:
    for member in content:
        if not member.isfile() or member.name not in expected or member.name in seen:
            raise ValueError('unexpected evidence member')
        row = expected[member.name]
        data = content.extractfile(member).read()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('retained evidence member changed')
        if args.originals and data != Path(row['original_path']).read_bytes():
            raise ValueError('original differs from retained evidence')
        seen.add(member.name)
if seen != set(expected):
    raise ValueError('missing evidence member')
print(f'PASS: {len(seen)} original rejected-attempt files; no acceptance claimed')
