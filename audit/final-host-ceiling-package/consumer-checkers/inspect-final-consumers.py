"""Authenticate exact final native consumers and independently replay all36pairs."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,subprocess
M=Path(__file__).resolve().parent;R=M.parent;CI=R/'trisha-native-ci'
_spec=importlib.util.spec_from_file_location('matrix',M/'check-final-corpus-matrix.py');matrix=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(matrix)
inspect=matrix.inspector;load=matrix.load;sha=matrix.sha;require=matrix.require
PRODUCER=36990413939;PRODUCER_HEAD='5de26a93eb4d489d90f150882adec2c47d14bea4'
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',type=int,required=True);parser.add_argument('--head',required=True);parser.add_argument('--selector-sha',required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
 out=a.output;out.mkdir();selector=CI/'.github/final-package-candidate.json';require(sha(selector)==a.selector_sha,'exact reviewed consumer selector required');selected=load(selector)
 require(selected['phase']=='verify' and selected['source_sha256']==matrix.SOURCE and selected['validation_profile']=='final-host-ceiling-v1','final verified profile required')
 def api(name,endpoint):
  cmd=['gh','api',endpoint];r=subprocess.run(cmd,capture_output=True)
  for stream in ['stdout','stderr']:(out/(name+'.'+stream)).write_bytes(getattr(r,stream))
  require(r.returncode==0,name+' API failed');return json.loads(r.stdout)
 run=api('run',f'repos/cyberia-to/trisha/actions/runs/{a.run_id}');require(run['head_sha']==a.head and run['status']=='completed' and run['conclusion']=='success','exact completed successful consumer run required')
 artifacts=api('artifacts',f'repos/cyberia-to/trisha/actions/runs/{a.run_id}/artifacts?per_page=100');require(artifacts['total_count']==len(artifacts['artifacts'])==5,'exact five remote consumers required')
 jobs=api('jobs',f'repos/cyberia-to/trisha/actions/runs/{a.run_id}/jobs?per_page=100');require(len(jobs['jobs'])==6 and all(x['conclusion']=='success' for x in jobs['jobs']),'all select and consumer jobs must pass')
 selection=dict(selector=str(selector),producer_results={'aarch64-apple-darwin':str(R/'local-macos-final-rust189/release-results')},consumer_results={'aarch64-apple-darwin':str(R/'local-macos-final-corpus-consumer/release-results')})
 producers=load(CI/'.github/final-package-assets.json')['producers']
 for row in producers:
  require(row['run_id']==PRODUCER and row['head_sha']==PRODUCER_HEAD,'producer selection changed');root=M/'native-runs'/str(PRODUCER)/str(row['artifact_id']);inspect.container(root,PRODUCER,PRODUCER_HEAD);selection['producer_results'][row['target']]=str(root/'restored')
 containers=[]
 for observed in artifacts['artifacts']:
  root=M/'native-runs'/str(a.run_id)/str(observed['id']);metadata,ret,digest=inspect.container(root,a.run_id,a.head);target=metadata['name'].removeprefix('candidate-');p=root/'restored'
  require(observed['digest']==metadata['digest'] and observed['workflow_run']==metadata['workflow_run'] and not observed['expired'],'fresh consumer artifact API differs')
  require(target in selected['targets'] and target not in selection['consumer_results'],'unexpected or repeated native consumer')
  impact=load(p/'source-impact.json');require(impact['status']=='passed' and impact['source_provenance_sha256']==matrix.PROVENANCE and impact['selector_sha256']==inspect.INPUTS and impact['script_sha256']==inspect.IMPACT,'exact final source impact differs')
  require(impact['joy_commit']=='dd61df9128f6da1f97d4698f45f154f05312fe51' and len(impact['protected_non_joy'])==10,'source closure changed')
  # Verify phase executes installed package bytes and returns before compiler setup.
  # Native Rust identity is authenticated in each producer package, not a new consumer build.
  expected_helper=inspect.WINDOWS_HELPER if 'windows' in target else inspect.HELPER
  for index in range(6):require(load(p/f'structured-verification-{index}.json')['verifier_sha256']==expected_helper,'structured consumer checker changed')
  selection['consumer_results'][target]=str(p);containers.append(dict(target=target,artifact_id=metadata['id'],zip_sha256=digest,members=len(ret['files']),retention_sha256=sha(root/'retention.json')))
 local=R/'local-macos-final-corpus-consumer';driver=load(local/'driver.json');require(driver['status']=='passed' and driver['bootstrap_revision']==a.head and driver['exit_code']==0 and driver['resource_stopped'] is False,'actual local consumer failed or wrong runner')
 expected=dict(selected,full_baselines=True,targets=['aarch64-apple-darwin']);require(driver['selector']==expected,'actual local consumer selector differs')
 require(driver['peak_process_group_rss_bytes']<=driver['resource_guard_bytes']==28*1024**3,'local consumer resource bound failed')
 for name in ['driver.stdout','driver.stderr','resources.jsonl']:require(sha(local/name)==driver[name]['sha256'] and (local/name).stat().st_size==driver[name]['bytes'],'local driver stream differs')
 localimpact=load(local/'release-results/source-impact.json');require(localimpact['status']=='passed' and localimpact['source_provenance_sha256']==matrix.PROVENANCE and localimpact['selector_sha256']==inspect.INPUTS and localimpact['script_sha256']==inspect.IMPACT,'local exact source impact differs')
 require(not (local/'release-results/baselines').exists(),'verify-only consumer unexpectedly ran full198')
 dump(out/'selection.json',selection);dump(out/'containers.json',containers)
 command=['python3','-B','-W','error',str(M/'check-final-corpus-matrix.py'),str(out/'selection.json'),str(out/'receipt.json')];result=subprocess.run(command,capture_output=True)
 for stream in ['stdout','stderr']:(out/('check.'+stream)).write_bytes(getattr(result,stream))
 dump(out/'command.json',dict(command=command,exit_code=result.returncode,driver_sha256=sha(Path(__file__)),run_id=a.run_id,runner_revision=a.head,selector_sha256=a.selector_sha));print(result.stdout.decode(),end='');require(result.returncode==0,'final matrix replay failed')
 report=load(out/'receipt.json');require(report['native_pairs']==36 and report['corpus_pairs']==72 and report['case_checks']==2664 and report['installed_deadline_commands']==138,'complete final consumer coverage differs')
if __name__=='__main__':main()
