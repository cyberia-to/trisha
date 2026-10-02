"""Read-only bounded compression samples; no whole-file size or retention claim."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parent
PREP = ROOT.parent / 'whole-local-retention/preparation.json'
EXPECTED = '489de67b014c96f7007c538f8a686af6faddcb5692dfad7de615eeaee29ff299'
assert hashlib.sha256(PREP.read_bytes()).hexdigest() == EXPECTED
preparation = json.loads(PREP.read_bytes())
rows = []
for entry in preparation['admitted']['entries']:
    proof = entry['proof']
    path = Path(proof['path'])
    before = path.stat()
    assert before.st_size == proof['bytes']
    size = 8 * 1024**2
    offsets = [0, before.st_size // 2, before.st_size-size]
    with path.open('rb') as stream:
        for offset in offsets:
            stream.seek(offset)
            raw = stream.read(size)
            assert len(raw) == size
            tick = time.monotonic_ns()
            zipped = gzip.compress(raw, compresslevel=1, mtime=0)
            elapsed = time.monotonic_ns()-tick
            assert gzip.decompress(zipped) == raw
            rows.append(dict(generation=entry['generation'],proof=proof,offset=offset,bytes=size,
                input_sha256=hashlib.sha256(raw).hexdigest(),gzip_bytes=len(zipped),
                gzip_sha256=hashlib.sha256(zipped).hexdigest(),compression_elapsed_ns=elapsed))
    after = path.stat()
    assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) == (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
report = dict(status='passed-samples-only',scope='Six8MiB ranges from original complete public certificates; no full-file compressed-size or retention claim',
    argv=sys.argv,python=sys.version,zlib=zlib.ZLIB_RUNTIME_VERSION,preparation_sha256=EXPECTED,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),samples=rows)
with (ROOT/'samples.json').open('x') as output:
    output.write(json.dumps(report,indent=2)+'\n')
print(json.dumps([dict(generation=r['generation'],offset=r['offset'],bytes=r['bytes'],gzip_bytes=r['gzip_bytes']) for r in rows]))
