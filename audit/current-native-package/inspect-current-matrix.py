"""Authenticate original current consumer containers, then check the complete matrix."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parent.parent;M=R/'measurements';CI=R/'trisha-native-ci';OUT=M/'current-corpus-matrix'
RUN=36974227589;HEAD='a5cdd95cb652d76a023fad1e40aefe54f6387445';SELECTOR='58263dbc6b7c09f96cd1598fa8982d7c5e305aee771f83da7dcc81d494172da0';INPUTS='e8e03c81f97d6aa5f7b3ab23faca44e058a2bd13dcf1228ffde1c81edb75619f';PROV='3c6f2ced084812e73f97c069169f83807fc5d389e54b581dd52f10982cd5b227'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def api(endpoint):return json.loads(subprocess.check_output(['gh','api',endpoint]))
def main():
 OUT.mkdir();selector=CI/'.github/release-candidate.json';assert sha(selector)==SELECTOR
 run=api(f'repos/cyberia-to/trisha/actions/runs/{RUN}');dump(OUT/'run.json',run);assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==HEAD
 inventory=api(f'repos/cyberia-to/trisha/actions/runs/{RUN}/artifacts?per_page=100');dump(OUT/'artifacts.json',inventory);assert inventory['total_count']==len(inventory['artifacts'])==5
 jobs=api(f'repos/cyberia-to/trisha/actions/runs/{RUN}/jobs?per_page=100');dump(OUT/'jobs.json',jobs);assert len(jobs['jobs'])==6 and all(j['conclusion']=='success' for j in jobs['jobs'])
 selection=dict(selector=str(selector),producer_results={'aarch64-apple-darwin':str(R/'local-macos-current-rust189/release-results')},consumer_results={'aarch64-apple-darwin':str(R/'local-macos-current-corpus-consumer/release-results')})
 for id in [11211868568,11211903748,11212207445,11212455449,11212481311]:
  p=M/'native-runs/36969168806'/str(id)/'restored';selection['producer_results'][load(p/'archive.json')['target']]=str(p)
 containers=[]
 for observed in inventory['artifacts']:
  id=observed['id'];p=M/'native-runs'/str(RUN)/str(id);metadata=load(p/'api.json');ret=load(p/'retention.json');target=metadata['name'].removeprefix('candidate-')
  assert observed['digest']==metadata['digest'] and observed['workflow_run']==metadata['workflow_run'] and not observed['expired']
  assert metadata['workflow_run']['id']==ret['run_id']==RUN and ret['head_sha']==HEAD and metadata['id']==ret['artifact_id']==id
  digest=sha(p/'artifact.zip');assert metadata['digest']=='sha256:'+digest and ret['archive_sha256']==digest and ret['archive_bytes']==(p/'artifact.zip').stat().st_size==metadata['size_in_bytes']
  restored=p/'restored';assert {q.relative_to(restored).as_posix() for q in restored.rglob('*') if q.is_file()}=={row['path'] for row in ret['files']}
  for row in ret['files']:
   q=restored/row['path'];assert q.resolve().is_relative_to(restored.resolve()) and not q.is_symlink() and q.stat().st_size==row['bytes'] and sha(q)==row['sha256']
  impact=load(restored/'source-impact.json');expected_impact='bfbae6ef8ef5b46c96d1d05863848a7487579b28708a2630b81ce259e865ecb1' if 'windows' in target else 'cffe213b0f0d0930c7d5c13d57cf97eecc3165d84662f7f8e30df0a07b005942'
  expected_helper='e64ac2ee0e34d3de9e7acde94f839363f7c91f62b90e08f2a923e055421ddaf4' if 'windows' in target else '5caa737b7c7b8b1fef0dd024a56e78f394273b8140b12a1832f29c8dad891a94'
  assert impact['status']=='passed' and impact['source_provenance_sha256']==PROV and impact['selector_sha256']==INPUTS and impact['checker_sha256']==expected_impact
  for i in range(6):assert load(restored/f'structured-verification-{i}.json')['verifier_sha256']==expected_helper
  assert target not in selection['consumer_results'];selection['consumer_results'][target]=str(restored);containers.append(dict(target=target,artifact_id=id,zip_sha256=digest,retention_sha256=sha(p/'retention.json')))
 local=load(R/'local-macos-current-corpus-consumer/driver.json');assert local['status']=='passed' and local['bootstrap_revision']==HEAD and local['exit_code']==0 and not local['resource_stopped']
 localcheck=load(CI/'audit/current-native-package/local-corpus-consumer/receipt.json');assert localcheck['status']=='passed' and localcheck['selector_sha256']==SELECTOR and localcheck['case_checks']==444
 dump(OUT/'selection.json',selection);dump(OUT/'containers.json',containers)
 command=['python3','-B','-W','error',str(M/'check-current-corpus-matrix.py'),str(OUT/'selection.json'),str(OUT/'receipt.json')];r=subprocess.run(command,capture_output=True)
 for name in ('stdout','stderr'):(OUT/('check.'+name)).write_bytes(getattr(r,name))
 dump(OUT/'command.json',dict(command=command,exit_code=r.returncode,driver_sha256=sha(Path(__file__))));print(r.stdout.decode());print(r.stderr.decode());raise SystemExit(r.returncode)
if __name__=='__main__':main()
