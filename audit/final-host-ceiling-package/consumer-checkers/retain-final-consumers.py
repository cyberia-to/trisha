"""Retain the actual final36pair matrix, local consumer and boundedMac14 originals."""
from pathlib import Path
import gzip,hashlib,importlib.util,json,shutil,subprocess,tarfile
M=Path(__file__).resolve().parent;R=M.parent;CI=R/'trisha-native-ci';A=CI/'audit/final-host-ceiling-package'
s=importlib.util.spec_from_file_location('inspect',M/'inspect-final-native-producer.py');inspect=importlib.util.module_from_spec(s);s.loader.exec_module(inspect)
def load(p):return json.loads(p.read_text())
def dump(p,j):p.write_text(json.dumps(j,indent=2)+'\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def joblog(dst,job):
 cmd=['gh','api',f"repos/cyberia-to/trisha/actions/jobs/{job['id']}/logs"];r=subprocess.run(cmd,capture_output=True);require(r.returncode==0,'job log read failed');(dst/'job.log.gz').write_bytes(gzip.compress(r.stdout,mtime=0));(dst/'job-log.stderr').write_bytes(r.stderr);dump(dst/'job-log.json',dict(command=cmd,exit_code=r.returncode,original_bytes=len(r.stdout),original_sha256=hashlib.sha256(r.stdout).hexdigest(),stored_sha256=sha(dst/'job.log.gz')));dump(dst/'job.json',job)
def main():
 matrix=M/'final-corpus-matrix';report=load(matrix/'receipt.json');command=load(matrix/'command.json');floor=M/'final-macos-floor-inspection';floorreport=load(floor/'receipt.json')
 require(report['status']==floorreport['status']=='passed' and (report['native_pairs'],report['corpus_pairs'],report['case_checks'],report['installed_deadline_commands'])==(36,72,2664,138),'complete final native matrix required')
 require(floorreport['case_checks']==444 and floorreport['installed_deadline']['accepted']+floorreport['installed_deadline']['rejected']==23,'complete actualMac14 consumption required')
 require(report['source_sha256']==floorreport['source_sha256']==inspect.SOURCE and report['selector_sha256']==floorreport['selector_sha256']==sha(CI/'.github/final-package-candidate.json'),'actual final consumer selectors differ')
 dest=A/'consumers';dest.mkdir();jobs=load(matrix/'jobs.stdout')['jobs'];members=[]
 for row in load(matrix/'containers.json'):
  root=M/'native-runs'/str(command['run_id'])/str(row['artifact_id']);api,ret,digest=inspect.container(root,command['run_id'],command['runner_revision']);d=dest/row['target'];d.mkdir()
  for name in ['api.json','retention.json','artifact.zip']:shutil.copyfile(root/name,d/('original-artifact.zip' if name=='artifact.zip' else name))
  require(sha(d/'original-artifact.zip')==digest,'copied consumer original differs');job=next(j for j in jobs if j['name'].endswith(', '+row['target']+')'));require(job['conclusion']=='success','consumer job failed');joblog(d,job);members.append(dict(target=row['target'],artifact_id=api['id'],archive_sha256=digest))
 shutil.copytree(matrix,A/'corpus-matrix');shutil.copytree(floor,A/'macos14-inspection')
 root=M/'native-runs'/str(floorreport['run_id'])/str(floorreport['artifact_id']);api,ret,digest=inspect.container(root,floorreport['run_id'],floorreport['runner_revision']);d=A/'macos14-arm-consumer';d.mkdir()
 for name in ['api.json','retention.json','artifact.zip']:shutil.copyfile(root/name,d/('original-artifact.zip' if name=='artifact.zip' else name))
 shutil.copyfile(root/'restored/macos-floor-results/receipt.json',d/'receipt.json')
 cmd=['gh','api',f"repos/cyberia-to/trisha/actions/runs/{floorreport['run_id']}/jobs?per_page=100"];p=subprocess.run(cmd,capture_output=True)
 for stream in ['stdout','stderr']:(d/('jobs.'+stream)).write_bytes(getattr(p,stream))
 require(p.returncode==0,'floor job API failed');jobs=json.loads(p.stdout)['jobs'];require(len(jobs)==1 and jobs[0]['conclusion']=='success','floor job failed');joblog(d,jobs[0])
 local=R/'local-macos-final-corpus-consumer';driver=load(local/'driver.json');require(driver['status']=='passed' and driver['bootstrap_revision']==command['runner_revision'],'actual local consumer differs');d=A/'local-corpus-consumer';d.mkdir()
 paths=[p for p in sorted(local.rglob('*')) if p.is_file() and 'temporary' not in p.relative_to(local).parts];paths.append(local/'temporary/cyber-candidate/installed/cyber-tools/candidate.json');files=[dict(path=p.relative_to(local).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in paths];archive=d/'original-evidence.tar.gz'
 with archive.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w') as tar:
  for row,p in zip(files,paths):
   info=tarfile.TarInfo(row['path']);info.size=row['bytes'];info.mode=0o644
   with p.open('rb') as stream:tar.addfile(info,stream)
 with tarfile.open(archive) as tar:
  require(len(tar.getmembers())==len(files),'local retained member count differs')
  for row,p in zip(files,paths):
   raw=tar.extractfile(row['path']).read();require(hashlib.sha256(raw).hexdigest()==row['sha256']==sha(p) and len(raw)==row['bytes'],'local retained original bytes differ')
 shutil.copyfile(local/'driver.json',d/'driver.json');dump(d/'receipt.json',dict(status='passed',scope='Original actual final local ARM installed consumer evidence; fresh198 retained separately',source_sha256=inspect.SOURCE,runner_revision=command['runner_revision'],selector_sha256=report['selector_sha256'],case_checks=444,installed_deadline_commands=23,archive=dict(path=archive.name,bytes=archive.stat().st_size,sha256=sha(archive)),files=files))
 helpers=A/'consumer-checkers';helpers.mkdir()
 for name in ['inspect-final-consumers.py','inspect-final-macos-floor.py','check-final-corpus-matrix.py','inspect-final-native-producer.py','retain-final-consumers.py']:shutil.copyfile(M/name,helpers/name)
 allfiles=[]
 for directory in [dest,A/'corpus-matrix',A/'macos14-inspection',A/'macos14-arm-consumer',A/'local-corpus-consumer',helpers]:
  for p in sorted(directory.rglob('*')):
   if p.is_file():allfiles.append(dict(path=p.relative_to(A).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
 dump(A/'consumer-retention.json',dict(status='passed',scope='Original five native consumer ZIPs, extraMac14 ZIP and localconsumer original archive plus exact independent replay',source_sha256=inspect.SOURCE,selector_sha256=report['selector_sha256'],consumer_run=command['run_id'],macos14_run=floorreport['run_id'],native_pairs=36,case_checks=2664,installed_deadline_commands=138,additional_mac14_case_checks=444,additional_mac14_deadline_commands=23,files=allfiles,retainer_sha256=sha(Path(__file__))));print('Retained all original consumer containers and exact independent replays')
if __name__=='__main__':main()
