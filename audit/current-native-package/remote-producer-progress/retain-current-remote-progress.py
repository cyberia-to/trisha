"""Retain exact completed producer observations; no matrix verdict is inferred."""
from pathlib import Path
import datetime,gzip,hashlib,json,re,shutil,subprocess
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';R=M/'native-runs/36969168806'
O=CI/'audit/current-native-package/remote-producer-progress';O.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
snapshot=sorted(p for p in R.iterdir() if p.name.startswith('2026'))[-1]
for name in ['run.json','jobs.json','artifacts.json']:shutil.copy2(snapshot/name,O/name)
jobs=json.loads((snapshot/'jobs.json').read_text())['jobs'];rows=[]
ansi=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
for root in sorted(R.iterdir()):
 if not (root/'inspection.json').exists():continue
 inspection=json.loads((root/'inspection.json').read_text());target=inspection['target'];dst=O/target;dst.mkdir()
 job=next(x for x in jobs if x['name'].endswith(', '+target+')'))
 assert job['status']=='completed' and job['conclusion']=='success'
 command=['gh','api',f"repos/cyberia-to/trisha/actions/jobs/{job['id']}/logs"]
 result=subprocess.run(command,capture_output=True);assert result.returncode==0
 (dst/'job.log.gz').write_bytes(gzip.compress(result.stdout,mtime=0));(dst/'job-log.stderr').write_bytes(result.stderr)
 dump(dst/'job-log.json',dict(command=command,exit_code=result.returncode,bytes=len(result.stdout),sha256=hashlib.sha256(result.stdout).hexdigest(),retained_as='job.log.gz'))
 dump(dst/'job.json',job)
 for name in ['api.json','retention.json','inspection.json']:shutil.copy2(root/name,dst/name)
 warning=[]
 for p in sorted((root/'restored').glob('*.log')):
  if not (p.name.endswith('-tests.log') or ('candidate-' in p.name and '-build.log' in p.name)):continue
  normalized=ansi.sub('',p.read_text(errors='strict'));found=re.findall(r'^warning(?:\[|:).*$',normalized,re.M)
  assert not found,(p,found)
  warning.append(dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p),rust_warnings=found))
 dump(dst/'warnings.json',dict(status='passed',normalization='ANSI CSI sequences removed for warning recognition; original log bytes retained unchanged in authenticated ZIP',logs=warning))
 rows.append(dict(target=target,artifact_id=inspection['artifact_id'],artifact_sha256=inspection['artifact_sha256'],cpu=inspection['cpu'],job_id=job['id']))
first=R/'11211868568';d=O/'inspector-checkout-correction';d.mkdir()
for name in ['inspection-first-command.json','inspection-first.stdout','inspection-first.stderr','checkout-script-identities.json']:shutil.copy2(first/name,d/name)
shutil.copy2(M/'inspect-current-native-producer.py',d/'inspect-current-native-producer.py');shutil.copy2(M/'check-current-inspector-v2.py',d/'check-current-inspector-v2.py');shutil.copy2(M/'current-inspector-check-v2/receipt.json',d/'local-check.json')
shutil.copy2(Path(__file__),O/Path(__file__).name)
dump(O/'receipt.json',dict(scope='Completed subset of current 734df69d native producer run; final five-producer verdict separate',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),run_id=36969168806,runner_revision='ecdc4e2ea131c50a860036e34ee7636b91fb8dde',source_sha256='734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e',status='completed_producers_checked',producers=rows,script_sha256=sha(Path(__file__))))
print(json.dumps(dict(status='retained',producers=len(rows))))
