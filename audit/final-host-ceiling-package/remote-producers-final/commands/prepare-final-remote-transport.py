"""Prepare, without activating, the five exact final native producer uploads."""
from pathlib import Path
import datetime,gzip,hashlib,importlib.util,json,re,shutil,subprocess
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';O=M/'remote-producer-review'
RUN=36990413939;HEAD='5de26a93eb4d489d90f150882adec2c47d14bea4'
TARGETS={'aarch64-unknown-linux-gnu','x86_64-unknown-linux-gnu','aarch64-pc-windows-msvc','x86_64-pc-windows-msvc','x86_64-apple-darwin'}
def sha(p):
 with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def api(endpoint):return json.loads(subprocess.check_output(['gh','api',endpoint]))
def main():
 O.mkdir();run=api(f'repos/cyberia-to/trisha/actions/runs/{RUN}');jobs=api(f'repos/cyberia-to/trisha/actions/runs/{RUN}/jobs?per_page=100');assets=api(f'repos/cyberia-to/trisha/actions/runs/{RUN}/artifacts?per_page=100')
 for name,data in [('run',run),('jobs',jobs),('artifacts',assets)]:dump(O/(name+'.json'),data)
 assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==HEAD
 assert len(jobs['jobs'])==6 and all(j['conclusion']=='success' for j in jobs['jobs'])
 assert assets['total_count']==len(assets['artifacts'])==5
 spec=importlib.util.spec_from_file_location('inspector',M/'inspect-final-native-producer.py');inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector);inspector.RUN=RUN;inspector.HEAD=HEAD
 assert sha(M/'inspect-final-native-producer.py')=='64572b572e3a7319f837d788307436e36b54802cc0ba6f146c541bb297d43a8a'
 rows=[]
 for item in assets['artifacts']:
  root=M/'native-runs'/str(RUN)/str(item['id']);observed=inspector.inspect(root);target=observed['target'];assert target in TARGETS
  assert not item['expired'] and item['digest']=='sha256:'+observed['artifact_sha256'] and item['workflow_run']['id']==RUN
  d=O/target;d.mkdir();dump(d/'inspection.json',observed)
  for name in ('api.json','retention.json'):shutil.copyfile(root/name,d/name)
  job=next(j for j in jobs['jobs'] if j['name'].endswith(', '+target+')'));assert job['conclusion']=='success';dump(d/'job.json',job)
  warnings=[]
  for p in sorted((root/'restored').glob('*.log')):
   if not (p.name.endswith('-tests.log') or (p.name.startswith('candidate-') and p.name.endswith('-build.log'))):continue
   text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',p.read_text());assert not re.search(r'^warning(?:\[|:)',text,re.M);warnings.append(dict(path=p.name,sha256=sha(p)))
  dump(d/'warnings.json',dict(status='passed',recognition='ANSI CSI removed for recognition; original bytes unchanged',logs=warnings))
  rows.append(dict(target=target,run_id=RUN,head_sha=HEAD,artifact_id=item['id'],zip_sha256=observed['artifact_sha256']))
 assert len(rows)==5 and {row['target'] for row in rows}==TARGETS
 origin=M/'before-remote-package-origin';assert json.loads((origin/'receipt.json').read_text())['status']=='passed';shutil.copytree(origin,O/'before-origin')
 link=M/'final-linkage';linked=json.loads((link/'receipt.json').read_text());assert linked['status']=='passed' and linked['source_sha256']==inspector.SOURCE and len(linked['binaries'])==24
 selected=json.loads((CI/'.github/final-package-assets.json').read_text());assert selected['source_sha256']==inspector.SOURCE and selected['provenance_sha256']==inspector.PROVENANCE and selected['inputs_sha256']==inspector.INPUTS and selected['kit_sha256']==inspector.KIT and not selected['producers'] and selected['status']!='active'
 selected.update(status='active',producers=sorted(rows,key=lambda row:row['target']));dump(M/'proposed-final-assets.json',selected)
 dump(O/'receipt.json',dict(status='passed-proposal-only',scope='Five authenticated final native producers and exact24binary linkage checked; no transport/consumer activation, full198 separate',run_id=RUN,runner_revision=HEAD,source_sha256=inspector.SOURCE,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),producers=rows,proposed_selector_sha256=sha(M/'proposed-final-assets.json'),linkage_receipt_sha256=sha(link/'receipt.json'),script_sha256=sha(Path(__file__))))
 print('Five final producers inspected; exact draft transport proposal written, not activated')
if __name__=='__main__':main()
