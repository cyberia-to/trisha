from pathlib import Path
import gzip,hashlib,io,json,subprocess,tarfile
r=Path('/Users/master/cyber/.worktrees/selfhost-0.4-full-bootstrap');repo=r/'portable-native-smoke/trisha';attempt=r/'measurements/coordinated-soft3-release-2';fix=r/'measurements/release-import-visibility';out=repo/'audit/native-soft3-release/import-visibility';out.mkdir()
h=lambda b:hashlib.sha256(b).hexdigest();files={}
for p in sorted(attempt.iterdir()):
 if p.is_file() and p.name!='source-export.tar.gz':files['second-export/'+p.name]=p.read_bytes()
for group in ('installed-results','independent-results'):
 for p in sorted((attempt/group).rglob('*')):
  if p.is_file():files['second-export/'+p.relative_to(attempt).as_posix()]=p.read_bytes()
for p in sorted((attempt/'candidate пробел').iterdir()):
 if p.is_file():files['second-export/candidate/'+p.name]=p.read_bytes()
for name in ('release_helper.tri','imported-nox.tri','imported-triton.tri'):
 files['second-export/failed-fixtures/'+name]=(attempt/'smoke пробел'/name).read_bytes()
for name in ('receipt.json','files.json'):
 path=attempt/'joy-native-smoke'/name
 if path.exists():files['second-export/joy-native-smoke/'+name]=path.read_bytes()
for p in sorted(fix.iterdir()):
 if p.is_file():files['repair/'+p.name]=p.read_bytes()
files['repair/check-release-import.py']=(r/'measurements/check-release-import.py').read_bytes()
files['source/smoke-release.nu']=subprocess.check_output(['git','show','13c5c24b93d7136624d8725f911b2aa45a175129:scripts/smoke-release.nu'],cwd=repo)
manifest={name:{'bytes':len(b),'sha256':h(b)} for name,b in sorted(files.items())}
with (out/'raw-evidence.tar.gz').open('xb') as stream:
 with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as compressed:
  with tarfile.open(fileobj=compressed,mode='w') as archive:
   for name,b in sorted(files.items()):
    entry=tarfile.TarInfo(name);entry.size=len(b);entry.mode=0o644;entry.mtime=0;archive.addfile(entry,io.BytesIO(b))
(out/'files.json').write_text(json.dumps(manifest,indent=2)+'\n')
validation=json.loads((fix/'receipt.json').read_text());prepare=json.loads((attempt/'prepare.json').read_text());build=json.loads((attempt/'build.json').read_text());smoke=json.loads((attempt/'smoke.json').read_text())
assert validation['status']=='passed' and validation['positive_commands']==16 and validation['private_rejections']==2
assert prepare['status']==build['status']=='passed' and smoke['status']=='failed'
assert h(files['source/smoke-release.nu'])==validation['script_sha256']
receipt={'schema':'local/release-import-visibility-retention/v1','status':'fixture-repair-passed-complete-rehearsal-pending','revision':'13c5c24b93d7136624d8725f911b2aa45a175129','source_sha256':validation['script_sha256'],'second_export':prepare['source_archive'],'second_export_pins':prepare['exported_pins'],'original_smoke_status':'failed','repair':{'positive_routes':16,'private_rejections':2},'archive':{'bytes':(out/'raw-evidence.tar.gz').stat().st_size,'sha256':h((out/'raw-evidence.tar.gz').read_bytes()),'files':len(files),'raw_bytes':sum(map(len,files.values()))},'files_sha256':h((out/'files.json').read_bytes()),'large_inputs_retained_locally':{'partial_smoke':str(attempt/'smoke пробел'),'partial_manifest':'second-export/partial-smoke-files.json','source_archive':str(attempt/'source-export.tar.gz'),'candidate':str(attempt/'candidate пробел'),'joy_smoke':str(attempt/'joy-native-smoke')},'generator_sha256':h(Path(__file__).read_bytes())}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');(out/'retain-local.py').write_bytes(Path(__file__).read_bytes())
with tarfile.open(out/'raw-evidence.tar.gz') as archive:
 assert len(archive.getmembers())==len(files)
 for item in archive.getmembers():assert archive.extractfile(item).read()==files[item.name]
print(json.dumps(receipt,indent=2))
