"""Select five successful authenticated current producers for draft transport."""
from pathlib import Path
import datetime,gzip,hashlib,json,re,shutil,subprocess,tarfile
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';R=M/'native-runs/36969168806';O=CI/'audit/current-native-package/remote-producers-final';O.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
snapshot=sorted(p for p in R.iterdir() if p.name.startswith('2026'))[-1];run=json.loads((snapshot/'run.json').read_text());assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']=='ecdc4e2ea131c50a860036e34ee7636b91fb8dde'
for name in ['run.json','jobs.json','artifacts.json']:shutil.copy2(snapshot/name,O/name)
rows=[];jobs=json.loads((snapshot/'jobs.json').read_text())['jobs'];targets={'aarch64-unknown-linux-gnu','x86_64-unknown-linux-gnu','aarch64-pc-windows-msvc','x86_64-pc-windows-msvc','x86_64-apple-darwin'}
for root in sorted(R.iterdir()):
 if not (root/'inspection.json').exists():continue
 x=json.loads((root/'inspection.json').read_text());target=x['target'];assert x['source_sha256']=='734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e';d=O/target;d.mkdir()
 for name in ['api.json','retention.json','inspection.json']:shutil.copy2(root/name,d/name)
 job=next(j for j in jobs if j['name'].endswith(', '+target+')'));assert job['conclusion']=='success';dump(d/'job.json',job)
 if target=='x86_64-apple-darwin':
  command=['gh','api',f"repos/cyberia-to/trisha/actions/jobs/{job['id']}/logs"];r=subprocess.run(command,capture_output=True);assert r.returncode==0;(d/'job.log.gz').write_bytes(gzip.compress(r.stdout,mtime=0));(d/'job-log.stderr').write_bytes(r.stderr);dump(d/'job-log.json',dict(command=command,exit_code=r.returncode,bytes=len(r.stdout),sha256=hashlib.sha256(r.stdout).hexdigest(),retained_as='job.log.gz'))
 warnings=[]
 for p in sorted((root/'restored').glob('*.log')):
  if not (p.name.endswith('-tests.log') or (p.name.startswith('candidate-') and p.name.endswith('-build.log'))):continue
  normalized=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',p.read_text());assert not re.search(r'^warning(?:\[|:)',normalized,re.M);warnings.append(dict(path=p.name,sha256=sha(p)))
 dump(d/'warnings.json',dict(status='passed',recognition='ANSI CSI sequences removed; raw original bytes retained unchanged',logs=warnings))
 rows.append(dict(target=target,run_id=x['run_id'],head_sha=x['runner_revision'],artifact_id=x['artifact_id'],zip_sha256=x['artifact_sha256']))
assert len(rows)==5 and {r['target'] for r in rows}==targets
origin=M/'before-remote-package-origin';assert json.loads((origin/'receipt.json').read_text())['status']=='passed';shutil.copytree(origin,O/'before-origin')
link=M/'current-linkage';assert json.loads((link/'receipt.json').read_text())['status']=='passed';d=O/'linkage';d.mkdir()
for p in link.iterdir():
 if p.is_file():shutil.copy2(p,d/p.name)
shutil.copy2(M/'inspect-current-linkage.py',d/'inspect-current-linkage.py');shutil.copy2(M/'check-current-origin-before-remote-packages.py',O/'check-current-origin-before-remote-packages.py')
spec=dict(scope='Current 734df69d committed feature-branch rehearsal transport; exact eleven source pins remain fixed; no default-branch release candidate/tag/publication',release_id=389977897,release_tag='candidate-20260916.1',asset_prefix='rehearsal-20261002-734df69d-remote',source_sha256='734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e',kit_sha256='a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd',provenance_sha256='3c6f2ced084812e73f97c069169f83807fc5d389e54b581dd52f10982cd5b227',validation_profile='current-package-v1',inputs_sha256='e8e03c81f97d6aa5f7b3ab23faca44e058a2bd13dcf1228ffde1c81edb75619f',producers=rows)
dump(CI/'.github/current-package-assets.json',spec);shutil.copy2(Path(__file__),O/Path(__file__).name)
dump(O/'receipt.json',dict(scope='All five current producer receipts accepted before transport activation; full198 and all-pair corpus consumption remain separate',status='passed',source_sha256=spec['source_sha256'],runner_revision=run['head_sha'],run_id=run['id'],observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),producers=rows,script_sha256=sha(Path(__file__))))
print(json.dumps(dict(status='passed',producers=len(rows))))
