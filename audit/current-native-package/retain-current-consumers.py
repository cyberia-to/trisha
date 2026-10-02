"""Retain exact completed current matrix and additional Mac14 consumer containers."""
from pathlib import Path
import gzip,hashlib,json,shutil,subprocess
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';A=CI/'audit/current-native-package';O=A/'consumers';O.mkdir()
def load(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def log(dst,job):
 command=['gh','api',f"repos/cyberia-to/trisha/actions/jobs/{job['id']}/logs"];r=subprocess.run(command,capture_output=True);assert r.returncode==0;(dst/'job.log.gz').write_bytes(gzip.compress(r.stdout,mtime=0));(dst/'job-log.stderr').write_bytes(r.stderr);dump(dst/'job-log.json',dict(command=command,exit_code=r.returncode,bytes=len(r.stdout),sha256=hashlib.sha256(r.stdout).hexdigest(),retained_as='job.log.gz'));dump(dst/'job.json',job)
result=load(M/'current-corpus-matrix/receipt.json');assert result['status']=='passed' and (result['native_pairs'],result['corpus_pairs'],result['case_checks'])==(36,72,2664)
jobs=load(M/'current-corpus-matrix/jobs.json')['jobs']
for row in load(M/'current-corpus-matrix/containers.json'):
 root=M/'native-runs/36974227589'/str(row['artifact_id']);dst=O/row['target'];dst.mkdir()
 for name in ['api.json','retention.json']:shutil.copy2(root/name,dst/name)
 shutil.copy2(root/'artifact.zip',dst/'original-artifact.zip');job=next(j for j in jobs if j['name'].endswith(', '+row['target']+')'));assert job['conclusion']=='success';log(dst,job)
shutil.copytree(M/'current-corpus-matrix',A/'corpus-matrix')
for name in ['inspect-current-matrix.py','check-current-corpus-matrix.py','inspect-current-mac-consumers.py','retain-current-consumers.py','current-mac-consumers-inspection.json']:shutil.copy2(M/name,A/name)
root=M/'native-runs/36974208978/11212737111';dst=A/'macos14-arm-consumer';dst.mkdir()
for name in ['api.json','retention.json']:shutil.copy2(root/name,dst/name)
shutil.copy2(root/'artifact.zip',dst/'original-artifact.zip');shutil.copy2(root/'restored/macos-floor-results/receipt.json',dst/'receipt.json')
run=json.loads(subprocess.check_output(['gh','api','repos/cyberia-to/trisha/actions/runs/36974208978']));assert run['head_sha']=='a5cdd95cb652d76a023fad1e40aefe54f6387445' and run['conclusion']=='success';dump(dst/'run.json',run)
j=json.loads(subprocess.check_output(['gh','api','repos/cyberia-to/trisha/actions/runs/36974208978/jobs?per_page=100']));assert len(j['jobs'])==1 and j['jobs'][0]['conclusion']=='success';log(dst,j['jobs'][0]);print('retained five native consumer original ZIPs and additional Mac14 original ZIP')
