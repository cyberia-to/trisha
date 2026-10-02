"""Run final package draft transport between exact origin reachability checks."""
from pathlib import Path
import datetime,hashlib,json,subprocess,traceback
M=Path(__file__).resolve().parent;OUT=M/'local-package-transport-coordination';OUT.mkdir();report=dict(status='running',scope='Distinct final source package transport only; full198 result remains separate',commands=[],started=datetime.datetime.now(datetime.timezone.utc).isoformat())
def sha(p):
 with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save():(OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def run(name,file):
 command=['python3','-B','-W','error',str(M/file)];row=dict(name=name,command=command,script_sha256=sha(M/file));report['commands'].append(row);save()
 with (OUT/(name+'.stdout')).open('xb') as out,(OUT/(name+'.stderr')).open('xb') as err:p=subprocess.run(command,stdout=out,stderr=err)
 row['exit_code']=p.returncode;save()
 if p.returncode:raise RuntimeError(name+' failed')
 print(name,'passed',flush=True)
try:
 run('before','check-final-origin-before-packages.py');run('upload','upload-final-local-packages.py');run('after','check-final-origin-after-packages.py')
 defaults={}
 for row in json.loads((M/'before-package-origin/receipt.json').read_text())['inputs']:
  name=row['repository'];states=[]
  for stage in ['before','after']:
   refs={ref:rev for rev,ref in (line.split() for line in (M/(stage+'-package-origin')/name/'heads.stdout').read_text().splitlines())};states.append({k:v for k,v in refs.items() if k in ('refs/heads/master','refs/heads/main')})
  if states[0]!=states[1]:raise ValueError('default ref changed during package transport: '+name)
  defaults[name]=states[0]
 report.update(status='passed',unchanged_default_refs=defaults,ended=datetime.datetime.now(datetime.timezone.utc).isoformat())
except BaseException:
 report.update(status='failed',error=traceback.format_exc());raise
finally:save()
