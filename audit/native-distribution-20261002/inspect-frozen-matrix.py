"""Bind the complete frozen corpus matrix to retained authenticated CI outputs."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parent.parent;M=R/'measurements';CI=R/'trisha-native-ci';OUT=M/'frozen-corpus-matrix';OUT.mkdir()
def sha(p):
 with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
run=json.loads(subprocess.check_output(['gh','api','repos/cyberia-to/trisha/actions/runs/36969090113']));assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']=='b2289e18207021fc8c53c546fe5cdcdc19bbd9c5';(OUT/'run.json').write_text(json.dumps(run,indent=2)+'\n')
selection=dict(selector=str(CI/'.github/release-candidate.json'),producer_results={'aarch64-apple-darwin':str(R/'local-macos-rust189/release-results')},consumer_results={'aarch64-apple-darwin':str(R/'local-macos-corpus-consumer/release-results')})
for id in [11207645268,11207109355,11208420793,11208532313,11210078256]:
 p=M/'native-runs/36949324686'/str(id)/'restored';selection['producer_results'][load(p/'archive.json')['target']]=str(p)
containers=[]
for id in [11210842931,11211176216,11210134597,11211150705,11210544976]:
 p=M/'native-runs/36969090113'/str(id);api=load(p/'api.json');ret=load(p/'retention.json')
 assert api['workflow_run']['id']==ret['run_id']==run['id'] and ret['head_sha']==run['head_sha'];assert api['id']==ret['artifact_id']==id
 assert api['digest']=='sha256:'+sha(p/'artifact.zip') and ret['archive_sha256']==sha(p/'artifact.zip') and ret['archive_bytes']==(p/'artifact.zip').stat().st_size==api['size_in_bytes']
 for row in ret['files']:
  file=p/'restored'/row['path'];assert file.resolve().is_relative_to((p/'restored').resolve()) and file.stat().st_size==row['bytes'] and sha(file)==row['sha256']
 target=api['name'].removeprefix('candidate-');assert target not in selection['consumer_results'];selection['consumer_results'][target]=str(p/'restored');containers.append(dict(target=target,artifact_id=id,zip_sha256=sha(p/'artifact.zip'),retention_sha256=sha(p/'retention.json')))
assert load(R/'local-macos-corpus-consumer/driver.json')['status']=='passed'
(OUT/'selection.json').write_text(json.dumps(selection,indent=2)+'\n');(OUT/'containers.json').write_text(json.dumps(containers,indent=2)+'\n')
command=['python3','-B','-W','error',str(M/'check-corpus-matrix.py'),str(OUT/'selection.json'),str(OUT/'receipt.json')];result=subprocess.run(command,capture_output=True)
for name in ('stdout','stderr'):(OUT/('check.'+name)).write_bytes(getattr(result,name))
(OUT/'command.json').write_text(json.dumps(dict(command=command,exit_code=result.returncode,driver_sha256=sha(Path(__file__))),indent=2)+'\n');print(result.stdout.decode());print(result.stderr.decode());raise SystemExit(result.returncode)
