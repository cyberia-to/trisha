"""Replay actual final macOS14 ARM installed consumer evidence without executing it."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,subprocess
M=Path(__file__).resolve().parent;R=M.parent;CI=R/'trisha-native-ci'
s=importlib.util.spec_from_file_location('matrix',M/'check-final-corpus-matrix.py');matrix=importlib.util.module_from_spec(s);s.loader.exec_module(matrix)
load=matrix.load;sha=matrix.sha;require=matrix.require;inspector=matrix.inspector
TARGET='aarch64-apple-darwin'
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',type=int,required=True);parser.add_argument('--artifact-id',type=int,required=True);parser.add_argument('--head',required=True);parser.add_argument('--selector-sha',required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();a.output.mkdir()
 selector=CI/'.github/final-package-candidate.json';require(sha(selector)==a.selector_sha,'exact consumer selector required');selected=load(selector)
 def api(name,url):
  command=['gh','api',url];p=subprocess.run(command,capture_output=True)
  for stream in ['stdout','stderr']:(a.output/(name+'.'+stream)).write_bytes(getattr(p,stream))
  require(p.returncode==0,name+' API failed');return json.loads(p.stdout)
 run=api('run',f'repos/cyberia-to/trisha/actions/runs/{a.run_id}');require(run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==a.head,'actual exact successful Mac14 run required')
 root=M/'native-runs'/str(a.run_id)/str(a.artifact_id);metadata,ret,digest=inspector.container(root,a.run_id,a.head);fresh=api('artifact',f'repos/cyberia-to/trisha/actions/artifacts/{a.artifact_id}');require(fresh['digest']==metadata['digest'] and fresh['workflow_run']['id']==a.run_id and not fresh['expired'],'fresh Mac14 container differs')
 p=root/'restored';floor=p/'macos-floor-results';report=load(floor/'receipt.json');host=report['actual_host']
 require(report['status']=='passed' and report['revision']==a.head and host['system']=='Darwin' and host['version'].startswith('14.') and host['machine']=='arm64','actual native Mac14 ARM required')
 require(report['selector_sha256']==a.selector_sha and report['source_sha256']==matrix.SOURCE and report['target']==TARGET,'actual source/selector differs')
 require(report['rss_limit_bytes']==5*1024**3 and report['time_limit_seconds']==1800 and report['resource_stop'] is None and report['exit_code']==0,'unchanged floor bounds or outcome differ')
 require(report['elapsed_seconds']<1800 and report['peak_process_group_rss_bytes']<5*1024**3,'floor actual resources exceeded bounds')
 samples=[json.loads(line) for line in (floor/'resources.jsonl').read_text().splitlines()];require(samples and max(x['rss_bytes'] for x in samples)==report['peak_process_group_rss_bytes'] and max(x['elapsed_seconds'] for x in samples)<=report['elapsed_seconds'],'original floor resource samples differ')
 for command in report['commands']:
  require(command['exit_code']==0,'host observation failed')
  for stream in ['stdout','stderr']:
   row=command[stream];q=floor/row['path'];require(q.stat().st_size==row['bytes'] and sha(q)==row['sha256'],'host original stream differs')
 require(report['bootstrap_sha256']==sha(CI/'scripts/native-candidate.py') and report['driver_sha256']==sha(CI/'scripts/native-rehearsal-macos-floor.py'),'reviewed floor runner differs')
 producer={TARGET:R/'local-macos-final-rust189/release-results'}
 for row in load(CI/'.github/final-package-assets.json')['producers']:
  d=M/'native-runs'/str(row['run_id'])/str(row['artifact_id']);inspector.container(d,row['run_id'],row['head_sha']);producer[row['target']]=d/'restored'
 require(set(producer)==matrix.TARGETS,'all exact six producers required')
 original=load(producer[TARGET]/'candidate.json');archive=load(producer[TARGET]/'archive.json');packaged=inspector.package_candidate(producer[TARGET]/archive['archive'],original,TARGET)
 require((floor/'candidate.json').read_bytes()==packaged and report['candidate_sha256']==hashlib.sha256(packaged).hexdigest(),'actual installed floor candidate bytes differ')
 actual=p/'release-results';kit=load(actual/'verified-selfhost-smoke/receipt.json');reference=load(producer[TARGET]/'unpacked-selfhost-smoke/receipt.json');require(kit['status']=='passed' and kit['joy']['sha256']==reference['joy']['sha256'] and kit['kit_manifest']==reference['kit_manifest'],'actual installed kit differs')
 impact=load(actual/'source-impact.json');require(impact['status']=='passed' and impact['source_provenance_sha256']==matrix.PROVENANCE and impact['selector_sha256']==inspector.INPUTS and impact['script_sha256']==inspector.IMPACT,'actual final floor source closure differs')
 require(not (actual/'baselines').exists(),'bounded consumer unexpectedly generated full198')
 results=[]
 for field,receipt_field,prefix,manifest_dir,checker in [('corpora','verifications','verification','proof-corpus',matrix.pair),('structured_corpora','structured_verifications','structured-verification','structured-corpus',matrix.structured_pair)]:
  require(len(selected[field])==len(report[receipt_field])==6,'all six floor corpora required')
  for index,row in enumerate(selected[field]):
   file=actual/f'{prefix}-{index}.json';wanted=report[receipt_field][index];require(wanted['target']==row['target'] and wanted['sha256']==sha(file),'floor reported verification differs')
   results.append(dict(kind=manifest_dir,producer=row['target'],**checker(file,producer[row['target']]/manifest_dir/'corpus.json',original)))
 deadline=inspector.deadline_probe(actual,original,packaged,inspector.HELPER);require(report['installed_host_ceiling']['sha256']==deadline['receipt_sha256'],'actual floor deadline receipt differs')
 out=dict(status='passed',scope='Actual macOS14 ARM Joy/Trisha installed package+kit, six legacy/structured corpora and bounded deadline probes only; no IntelMac14, Trident/LSP floor or full198 claim',actual_host=host,run_id=a.run_id,runner_revision=a.head,artifact_id=a.artifact_id,original_zip_sha256=digest,original_members=len(ret['files']),source_sha256=matrix.SOURCE,selector_sha256=a.selector_sha,case_checks=sum(x['cases'] for x in results),installed_deadline=deadline,elapsed_seconds=report['elapsed_seconds'],peak_process_group_rss_bytes=report['peak_process_group_rss_bytes'],receipt_sha256=sha(floor/'receipt.json'),inspector_sha256=sha(Path(__file__)),pairs=results)
 require(out['case_checks']==444 and deadline['accepted']+deadline['rejected']==23,'actual floor coverage differs');(a.output/'receipt.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['status','actual_host','case_checks','elapsed_seconds','peak_process_group_rss_bytes']}))
if __name__=='__main__':main()
