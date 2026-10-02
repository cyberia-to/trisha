"""Replay every retained producer/consumer ZIP member against its original inventory."""
import hashlib
import json
from pathlib import Path
import zipfile
import tarfile

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / 'trisha-native-ci/audit/current-native-package'

def load(path):
    return json.loads(path.read_bytes())

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

rows = []
for run, ids, head in [
    (36969168806, [11211868568,11211903748,11212207445,11212455449,11212481311], 'ecdc4e2ea131c50a860036e34ee7636b91fb8dde'),
    (36974227589, [11212886258,11212836179,11212642441,11212633025,11212349713], 'a5cdd95cb652d76a023fad1e40aefe54f6387445'),
    (36974208978, [11212737111], 'a5cdd95cb652d76a023fad1e40aefe54f6387445')]:
    for aid in ids:
        root = ROOT / f'measurements/native-runs/{run}/{aid}'
        api, ret = load(root / 'api.json'), load(root / 'retention.json')
        archive = root / 'artifact.zip'
        assert api['workflow_run']['id'] == ret['run_id'] == run
        assert api['id'] == ret['artifact_id'] == aid and ret['head_sha'] == head
        assert api['digest'] == 'sha256:' + sha(archive) and ret['archive_sha256'] == sha(archive)
        assert api['size_in_bytes'] == ret['archive_bytes'] == archive.stat().st_size
        expected = {row['path']: row for row in ret['files']}
        assert len(expected) == len(ret['files'])
        seen = set()
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if entry.is_dir():
                    continue
                assert entry.filename not in seen and entry.filename in expected
                assert not Path(entry.filename).is_absolute() and '..' not in Path(entry.filename).parts
                row = expected[entry.filename]
                with z.open(entry) as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                assert entry.file_size == row['bytes'] and digest == row['sha256']
                restored = root / 'restored' / entry.filename
                assert restored.stat().st_size == row['bytes'] and sha(restored) == digest
                seen.add(entry.filename)
        assert seen == set(expected)
        rows.append(dict(run=run,head=head,artifact=aid,bytes=archive.stat().st_size,sha256=sha(archive),members=len(seen)))
report = dict(status='passed',scope='Exact authenticated ZIP and restored-member identity replay; semantic acceptance is checked separately',archives=rows,script_sha256=sha(Path(__file__)))
with (Path(__file__).resolve().parent / 'containers-replay.json').open('x') as stream:
    stream.write(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status='passed',archives=len(rows),members=sum(r['members'] for r in rows))))
