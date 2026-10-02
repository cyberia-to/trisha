"""Retain only the byte identity of the private consumer admission command inventory."""
from pathlib import Path
import gzip,hashlib,json
M=Path(__file__).resolve().parent;O=M.parent/'trisha-native-ci/audit/final-host-ceiling-package/remote-asset-transport'
manifest=O/'retention-manifest.json';old=manifest.read_bytes();j=json.loads(old);relative='consumer-proposal/processes.stdout.gz';rows=[r for r in j['files'] if r['stored']==relative];assert len(rows)==1;row=rows[0];original=Path(row['source']);copy=O/relative
assert hashlib.sha256(copy.read_bytes()).hexdigest()==row['stored_sha256'] and gzip.decompress(copy.read_bytes())==original.read_bytes()
# This is the newly generated, uncommitted duplicate only; the local original is preserved.
copy.unlink();j['files']=[r for r in j['files'] if r['stored']!=relative];j['private_observations']=[dict(source=str(original),original_bytes=original.stat().st_size,original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),scope='Full host process command inventory retained locally only; unrelated command lines excluded from public audit')]
p=O/'commands'/Path(__file__).name;raw=Path(__file__).read_bytes();p.write_bytes(raw);j['files'].append(dict(source=str(Path(__file__)),stored=str(p.relative_to(O)),encoding='identity',original_bytes=len(raw),original_sha256=hashlib.sha256(raw).hexdigest(),stored_sha256=hashlib.sha256(raw).hexdigest()));manifest.write_text(json.dumps(j,indent=2)+'\n');print('Private original preserved; public audit retains only its byte identity')
