from pathlib import Path
import datetime,hashlib,json,os,subprocess,tarfile,time
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'measurements'
env=dict(os.environ,RUSTUP_TOOLCHAIN='1.89.0',CARGO_BUILD_JOBS='2',RAYON_NUM_THREADS='4',TVM_LDE_TRACE='no_cache',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
for key in ('RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','CARGO_BUILD_TARGET','CARGO_TARGET_DIR','TRIDENT_STDLIB','TRIDENT_OSLIB','TRIDENT_EXTLIB','TRIDENT_TARGET_PACKAGES','PYTHONOPTIMIZE'):env.pop(key,None)
report=dict(schema='local/native-distribution-prepare/v1',scope='Committed/pushed release-0.4 branch rehearsal; default branches untouched; no release/tag/publication',status='running',commands=[])
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save():
 (OUT/'prepare.json').write_text(json.dumps(report,indent=2)+'\n')
def run(name,argv,cwd=ROOT/'trisha'):
 row=dict(name=name,argv=list(map(str,argv)),cwd=str(cwd),status='running');report['commands'].append(row);save()
 start=time.monotonic_ns()
 with (OUT/(name+'.stdout')).open('xb') as out,(OUT/(name+'.stderr')).open('xb') as err:
  result=subprocess.run(row['argv'],cwd=cwd,env=env,stdout=out,stderr=err)
 row.update(status='completed',exit_code=result.returncode,elapsed_ns=time.monotonic_ns()-start)
 for stream in ('stdout','stderr'):
  p=OUT/(name+'.'+stream);row[stream]=dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p))
 save();print(name,result.returncode,flush=True)
 if result.returncode:raise RuntimeError(name+' failed')
 return (OUT/(name+'.stdout')).read_text()
try:
 run('vendor-bootstrap',['rustup','run','1.89.0','nu','--no-config-file',ROOT/'trisha/patches/apply.nu'])
 run('package-source',['rustup','run','1.89.0','nu','--no-config-file',ROOT/'trisha/scripts/package-source.nu',OUT/'source-export'])
 archive=OUT/'source-export.tar.gz'
 report['source_archive']=dict(path=str(archive),bytes=archive.stat().st_size,sha256=sha(archive))
 manifest=json.loads((OUT/'source-export/sources.json').read_text())
 report['source_pins']={row['repository']:row['commit'] for row in manifest}
 expected={row['repository']:row['revision'] for row in json.loads((OUT/'origin-inputs.json').read_text())['inputs']}
 if report['source_pins']!=expected:raise RuntimeError('Source closure changed')
 unpacked=OUT/'unpacked';unpacked.mkdir()
 with tarfile.open(archive) as content:content.extractall(unpacked,filter='data')
 source=unpacked/'cyber-source'
 run('source-guard',['python3','-B',source/'trisha/scripts/verify-source.py',source])
 kit=ROOT/'trisha/audit/selfhost-kit/accepted/selfhost-kit.tar.gz'
 run('accepted-kit-unpack',['python3','-B',source/'trisha/scripts/selfhost-kit.py','unpack','--archive',kit,'--sha256','a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd','--trident',source/'trident','--output',OUT/'accepted-kit'])
 report['status']='passed'
except BaseException as e:
 report.update(status='failed',error=repr(e));raise
finally:save()
