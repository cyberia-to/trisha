"""Wait for actual current native completion, then retain and transport its originals."""
from pathlib import Path
import datetime,hashlib,json,subprocess,time,traceback
M=Path(__file__).resolve().parent;R=M.parent;O=M/'local-completion-watch';O.mkdir();scripts=['retain-current-local.py','upload-current-local-evidence.py']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
report=dict(scope='Complete current Mac198 acceptance only after actual native driver exits successfully',status='waiting',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),scripts={name:sha(M/name) for name in scripts},commands=[])
def save():(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def run(name):
 if sha(M/name)!=report['scripts'][name]:raise ValueError('completion helper changed after watcher started')
 argv=['python3','-B','-W','error',str(M/name)];record=dict(command=argv);report['commands'].append(record);save()
 with (O/(name+'.stdout')).open('xb') as stdout,(O/(name+'.stderr')).open('xb') as stderr:result=subprocess.run(argv,stdout=stdout,stderr=stderr)
 record['exit_code']=result.returncode;save()
 if result.returncode:raise RuntimeError(name+' failed')
 print(name,'passed',flush=True)
save()
try:
 while True:
  driver=json.loads((R/'local-macos-current-rust189/driver.json').read_text())
  if driver['status']!='running':break
  time.sleep(15)
 if driver['status']!='passed' or driver['exit_code']!=0 or driver['resource_stopped']:raise ValueError('actual current Mac producer did not pass')
 report.update(status='retaining',driver_sha256=sha(R/'local-macos-current-rust189/driver.json'));save();run(scripts[0]);report['status']='transporting';save();run(scripts[1]);report.update(status='passed',ended=datetime.datetime.now(datetime.timezone.utc).isoformat())
except BaseException:
 report.update(status='failed',error=traceback.format_exc());raise
finally:save()
