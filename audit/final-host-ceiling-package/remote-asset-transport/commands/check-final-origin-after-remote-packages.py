from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,json,subprocess
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'measurements/after-remote-package-origin';OUT.mkdir()
spec=json.loads((ROOT/'trisha-native-ci/.github/final-package-source.json').read_text())
def run(entry):
 repo=entry['repository'];path=OUT/repo;path.mkdir()
 cmd=['git','-C',str(ROOT/repo),'ls-remote','--heads','origin']
 result=subprocess.run(cmd,capture_output=True)
 (path/'heads.stdout').write_bytes(result.stdout);(path/'heads.stderr').write_bytes(result.stderr)
 if result.returncode:raise RuntimeError(repo+' origin read failed')
 refs={line.split()[1]:line.split()[0] for line in result.stdout.decode().splitlines()}
 head=refs[entry['origin_ref']]
 record=dict(repository=repo,pin=entry['commit'],origin_ref=entry['origin_ref'],current_origin_head=head,commands=[dict(command=cmd,exit_code=result.returncode)])
 if head!=entry['commit']:
  cmd=['gh','api','repos/cyberia-to/'+repo+'/compare/'+entry['commit']+'...'+head]
  result=subprocess.run(cmd,capture_output=True)
  (path/'comparison.stdout').write_bytes(result.stdout);(path/'comparison.stderr').write_bytes(result.stderr)
  record['commands'].append(dict(command=cmd,exit_code=result.returncode))
  if result.returncode:raise RuntimeError(repo+' origin ancestry read failed')
  data=json.loads(result.stdout)
  if data['status']!='ahead' or data['merge_base_commit']['sha']!=entry['commit']:raise ValueError(repo+' selected commit no longer ancestor of selected origin ref')
  record['ancestry']=dict(status=data['status'],ahead_by=data['ahead_by'],merge_base_sha=data['merge_base_commit']['sha'])
 else:record['ancestry']=dict(status='identical')
 return record
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(run,spec['sources']))
report=dict(scope='Read-only final pinned source reachability after remote package draft upload; release/0.4 may advance independently',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=spec['source_sha256'],status='passed',inputs=rows)
(OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({r['repository']:r['ancestry'] for r in rows},indent=2))
