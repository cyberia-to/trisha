"""Retain native CI raw artifacts with their exact API archive identities."""
from pathlib import Path
import argparse,datetime,hashlib,json,stat,subprocess,time,zipfile
parser=argparse.ArgumentParser();parser.add_argument('run_id',type=int);parser.add_argument('--watch',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parent/'native-runs'/str(args.run_id);ROOT.mkdir(parents=True,exist_ok=True)
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def api(endpoint):return json.loads(subprocess.check_output(['gh','api',endpoint],text=True))
previous=None
while True:
 timestamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 snapshot=ROOT/timestamp;snapshot.mkdir()
 run=api(f'repos/cyberia-to/trisha/actions/runs/{args.run_id}')
 jobs=api(f'repos/cyberia-to/trisha/actions/runs/{args.run_id}/jobs?per_page=100')
 artifacts=api(f'repos/cyberia-to/trisha/actions/runs/{args.run_id}/artifacts?per_page=100')
 for name,data in [('run',run),('jobs',jobs),('artifacts',artifacts)]:
  (snapshot/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
 states=[(j['name'],j['status'],j['conclusion']) for j in jobs['jobs']]
 if states!=previous:
  print(json.dumps(dict(timestamp=timestamp,run_id=args.run_id,head_sha=run['head_sha'],jobs=states)),flush=True);previous=states
 for artifact in artifacts['artifacts']:
  if artifact['expired']:raise ValueError('Native artifact expired before retention')
  destination=ROOT/str(artifact['id'])
  if destination.exists():continue
  destination.mkdir()
  (destination/'api.json').write_text(json.dumps(artifact,indent=2)+'\n')
  archive=destination/'artifact.zip'
  with archive.open('xb') as out:subprocess.run(['gh','api',artifact['archive_download_url']],stdout=out,check=True)
  digest=sha(archive)
  if artifact['digest']!='sha256:'+digest:raise ValueError('GitHub native artifact digest mismatch')
  restored=destination/'restored';restored.mkdir()
  with zipfile.ZipFile(archive) as content:
   names=set()
   for member in content.infolist():
    if not (restored/member.filename).resolve().is_relative_to(restored.resolve()):raise ValueError('Artifact path escapes restore root')
    if member.filename in names:raise ValueError('Duplicate artifact entry')
    names.add(member.filename)
    if stat.S_ISLNK(member.external_attr >> 16):raise ValueError('Artifact symlink')
   content.extractall(restored)
  files=[dict(path=str(p.relative_to(restored)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(restored.rglob('*')) if p.is_file()]
  (destination/'retention.json').write_text(json.dumps(dict(run_id=args.run_id,head_sha=run['head_sha'],artifact_name=artifact['name'],artifact_id=artifact['id'],archive_sha256=digest,archive_bytes=archive.stat().st_size,files=files),indent=2)+'\n')
  failure=restored/'failure.txt'
  print(json.dumps(dict(retained=artifact['name'],artifact_id=artifact['id'],raw_zip_sha256=digest,failure=failure.read_text() if failure.exists() else None)),flush=True)
 if run['status']=='completed' or not args.watch:
  print(json.dumps(dict(run_id=args.run_id,status=run['status'],conclusion=run['conclusion'])),flush=True)
  break
 time.sleep(60)
