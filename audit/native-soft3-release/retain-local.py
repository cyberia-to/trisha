from pathlib import Path
import gzip, hashlib, io, json, re, subprocess, tarfile
r=Path('/Users/master/cyber/.worktrees/selfhost-0.4-full-bootstrap')
out=r/'measurements/release-warrior-retention'
out.mkdir()
repo=r/'portable-native-smoke/trisha'
h=lambda b:hashlib.sha256(b).hexdigest()
core='8f4a2d883a47df4bfeab0f880ee7f6adba55c7e1'
lock='4f7074bbc61b86fd2355c542e0fffa2c823af755'
gates=r/'measurements/release-warrior-boundaries'
files={}
for group in ('release-warrior-boundaries','release-fixture-lock'):
 for p in sorted((r/'measurements'/group).rglob('*')):
  if p.is_file():files[group+'/'+p.relative_to(r/'measurements'/group).as_posix()]=p.read_bytes()
first=r/'measurements/coordinated-soft3-release'
for p in sorted(first.iterdir()):
 if p.is_file() and p.name!='source-export.tar.gz':files['first-export/'+p.name]=p.read_bytes()
files['first-export/sources.json']=(first/'unpacked/cyber-source/sources.json').read_bytes()
pre=json.loads((gates/'precommit-final.json').read_text())
for name,info in pre['files'].items():
 data=subprocess.check_output(['git','show',core+':'+name],cwd=repo)
 assert len(data)==info['bytes'] and h(data)==info['sha256'],name
 files['source/core/'+name]=data
files['source/fixture-lock/Cargo.lock']=subprocess.check_output(['git','show',lock+':scripts/fixtures/Cargo.lock'],cwd=repo)
rows=re.findall(r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;', (gates/'cargo-tests-locked.log').read_text())
counts=[sum(int(x[i]) for x in rows) for i in range(3)]
assert counts==[429,0,6] and len(rows)==64
for name in ('cargo-check-locked.log','cargo-tests-locked.log','cargo-build-locked.log'):
 assert not any(x.startswith(('warning:','warning[')) for x in (gates/name).read_text().splitlines()),name
preparation=json.loads((first/'prepare.json').read_text()); failure=json.loads((first/'build.json').read_text())
assert preparation['status']=='passed' and failure['status']=='failed' and failure['candidate_published'] is False
assert preparation['source_archive']['sha256']==h((first/'source-export.tar.gz').read_bytes())
manifest={name:{'bytes':len(data),'sha256':h(data)} for name,data in sorted(files.items())}
with (out/'raw-evidence.tar.gz').open('xb') as stream:
 with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as compressed:
  with tarfile.open(fileobj=compressed,mode='w') as archive:
   for name,data in sorted(files.items()):
    item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o644;item.mtime=0;archive.addfile(item,io.BytesIO(data))
(out/'files.json').write_text(json.dumps(manifest,indent=2)+'\n')
raw=(out/'raw-evidence.tar.gz').read_bytes()
receipt={'schema':'local/release-warrior-boundary-retention/v1','status':'component-checks-passed-full-rehearsal-pending','core_revision':core,'fixture_lock_revision':lock,'rust_tests':{'passed':429,'failed':0,'ignored':6,'summaries':64},'packaging_guards':16,'source_guards_repeated':10,'fixture_rust_tests':0,'source_files':pre['files'],'first_rehearsal':{'status':'failed','candidate_published':False,'source_archive':preparation['source_archive'],'scope':preparation['scope'],'exported_pins':preparation['exported_pins']},'archive':{'file':'raw-evidence.tar.gz','bytes':len(raw),'sha256':h(raw),'files':len(files),'raw_bytes':sum(map(len,files.values()))},'files_sha256':h((out/'files.json').read_bytes()),'generator_sha256':h(Path(__file__).read_bytes())}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
with tarfile.open(out/'raw-evidence.tar.gz') as archive:
 members=archive.getmembers();assert len(members)==len(files)
 for member in members:assert member.isfile() and archive.extractfile(member).read()==files[member.name]
print(json.dumps(receipt,indent=2))
