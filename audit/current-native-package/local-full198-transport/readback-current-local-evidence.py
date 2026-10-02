"""Independently download and verify the completed immutable source734 proof asset."""
from pathlib import Path
import datetime,hashlib,json,subprocess,tarfile,time
M=Path(__file__).resolve().parent;O=M/'local-evidence-readback';O.mkdir();report=dict(status='waiting_for_upload',scope='Independent readback of complete original source734 full198 archive',commands=[])
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def save():dump(O/'receipt.json',report)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def api(name,endpoint,allowed=(0,)):
 command=['gh','api',endpoint];r=subprocess.run(command,capture_output=True)
 for ext in ['stdout','stderr']:(O/(name+'.'+ext)).write_bytes(getattr(r,ext))
 report['commands'].append(dict(command=command,exit_code=r.returncode));save();assert r.returncode in allowed;return json.loads(r.stdout)
save()
while True:
 try:uploaded=json.loads((M/'local-evidence-transport/receipt.json').read_text())
 except json.JSONDecodeError:time.sleep(1);continue
 if uploaded['status']=='passed':break
 if uploaded['status']=='failed':raise ValueError('Original upload failed; no readback acceptance')
 time.sleep(15)
asset=uploaded['asset'];ret=json.loads((M/'local-rust189-complete/receipt.json').read_text());expected=ret['archive'];assert expected['sha256']=='54db68904fc8c92f1446c46cb7b90345a05e026a92b46e6ccb259822a3328204'
metadata=api('asset','repos/cyberia-to/trisha/releases/assets/'+str(asset['id']));assert metadata['digest']=='sha256:'+expected['sha256'] and metadata['size']==expected['bytes'] and metadata['name']==expected['path']
report.update(status='downloading',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),asset=metadata);save();archive=O/'original-evidence.tar.gz';command=['gh','api','-H','Accept: application/octet-stream','repos/cyberia-to/trisha/releases/assets/'+str(asset['id'])]
with archive.open('xb') as out,(O/'download.stderr').open('xb') as err:r=subprocess.run(command,stdout=out,stderr=err)
report['commands'].append(dict(command=command,exit_code=r.returncode));save();assert r.returncode==0 and sha(archive)==expected['sha256'] and archive.stat().st_size==expected['bytes']
files={row['path']:row for row in ret['files']}
with tarfile.open(archive) as package:
 members=package.getmembers();assert len(members)==len(files) and {x.name for x in members}==set(files)
 for member in members:
  row=files[member.name];assert member.isfile() and member.size==row['bytes'];assert hashlib.file_digest(package.extractfile(member),'sha256').hexdigest()==row['sha256']
draft=api('draft-after','repos/cyberia-to/trisha/releases/389977897');assert draft['draft'] is True and draft['tag_name']=='candidate-20260916.1';absent=api('tag-after','repos/cyberia-to/trisha/git/ref/tags/candidate-20260916.1',(1,));assert str(absent['status'])=='404'
report.update(status='passed',ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,members=len(files),retention_sha256=sha(M/'local-rust189-complete/receipt.json'),script_sha256=sha(Path(__file__)));save();print(json.dumps({k:report[k] for k in ['status','archive_sha256','archive_bytes','members']}))
