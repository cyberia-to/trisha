"""Retain a completed subset of final producers without a matrix verdict."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json,re,shutil,subprocess
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';R=M/'native-runs/36990413939'
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('output_name');args=parser.parse_args();assert Path(args.output_name).name==args.output_name
 O=CI/'audit/final-host-ceiling-package'/args.output_name;O.mkdir()
 snapshot=sorted(R.glob('2026*/jobs.json'))[-1].parent
 for name in ('run.json','jobs.json','artifacts.json'):shutil.copyfile(snapshot/name,O/name)
 jobs=json.loads((snapshot/'jobs.json').read_text())['jobs'];rows=[]
 for root in sorted(R.iterdir()):
  if not (root/'inspection.json').exists():continue
  observed=json.loads((root/'inspection.json').read_text());assert observed['status']=='producer_receipts_checked' and observed['source_sha256']=='73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8'
  target=observed['target'];destination=O/target;destination.mkdir();job=next(x for x in jobs if x['name'].endswith(', '+target+')'));assert job['conclusion']=='success'
  command=['gh','api',f"repos/cyberia-to/trisha/actions/jobs/{job['id']}/logs"];result=subprocess.run(command,capture_output=True);assert result.returncode==0
  (destination/'job.log.gz').write_bytes(gzip.compress(result.stdout,mtime=0));(destination/'job-log.stderr.gz').write_bytes(gzip.compress(result.stderr,mtime=0));dump(destination/'job-log.json',dict(command=command,exit_code=result.returncode,original_bytes=len(result.stdout),original_sha256=hashlib.sha256(result.stdout).hexdigest(),stored='job.log.gz'))
  dump(destination/'job.json',job)
  for name in ('api.json','retention.json','inspection.json'):shutil.copyfile(root/name,destination/name)
  warnings=[]
  for path in sorted((root/'restored').glob('*.log')):
   if not (path.name.endswith('-tests.log') or (path.name.startswith('candidate-') and path.name.endswith('-build.log'))):continue
   normalized=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',path.read_text());assert not re.search(r'^warning(?:\[|:)',normalized,re.M);warnings.append(dict(path=path.name,bytes=path.stat().st_size,sha256=sha(path)))
  dump(destination/'warnings.json',dict(status='passed',recognition='ANSI CSI removed for recognition; original bytes remain in authenticated ZIP',logs=warnings))
  rows.append(dict(target=target,artifact_id=observed['artifact_id'],artifact_sha256=observed['artifact_sha256'],cpu=observed['cpu'],job_id=job['id']))
 assert rows
 shutil.copyfile(Path(__file__),O/Path(__file__).name);shutil.copyfile(M/'inspect-final-native-producer.py',O/'inspect-final-native-producer.py')
 dump(O/'receipt.json',dict(status='completed_producers_checked',scope='Completed subset of final native producer run only; all-five, full198, linkage and consumer verdicts remain separate',run_id=36990413939,runner_revision='5de26a93eb4d489d90f150882adec2c47d14bea4',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),producers=rows,script_sha256=sha(Path(__file__))))
 print('Retained',len(rows),'completed native producers')
if __name__=='__main__':main()
