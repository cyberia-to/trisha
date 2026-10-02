"""Check actual frozen corpus receipts on the two distinct Mac ARM consumers."""
from pathlib import Path
import hashlib,importlib.util,json
R=Path(__file__).resolve().parent.parent;M=R/'measurements';CI=R/'trisha-native-ci'
spec=importlib.util.spec_from_file_location('matrix',M/'check-corpus-matrix.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
selected=helper.load(CI/'.github/release-candidate.json');producer={'aarch64-apple-darwin':R/'local-macos-rust189/release-results'}
for id in [11207645268,11207109355,11208420793,11208532313,11210078256]:
 p=M/'native-runs/36949324686'/str(id)/'restored';producer[helper.load(p/'archive.json')['target']]=p
candidate=helper.load(producer['aarch64-apple-darwin']/'candidate.json')
floor_root=M/'native-runs/36969075321/11210653785';floor=floor_root/'restored';metadata=helper.load(floor_root/'api.json');ret=helper.load(floor_root/'retention.json')
assert metadata['digest']=='sha256:'+helper.sha(floor_root/'artifact.zip') and ret['head_sha']=='b2289e18207021fc8c53c546fe5cdcdc19bbd9c5'
for row in ret['files']:
 p=floor/row['path'];assert p.stat().st_size==row['bytes'] and helper.sha(p)==row['sha256']
report=helper.load(floor/'macos-floor-results/receipt.json');assert report['status']=='passed' and report['actual_host']==dict(system='Darwin',version='14.8.9',machine='arm64');assert report['selector_sha256']==helper.sha(CI/'.github/release-candidate.json') and report['source_sha256']==helper.SOURCE
assert report['resource_stop'] is None and report['exit_code']==0 and report['elapsed_seconds']<report['time_limit_seconds'] and report['peak_process_group_rss_bytes']<report['rss_limit_bytes']
assert report['candidate_sha256']==helper.sha(R/'local-macos-corpus-consumer/temporary/cyber-candidate/installed/cyber-tools/candidate.json')
local=R/'local-macos-corpus-consumer';driver=helper.load(local/'driver.json');assert driver['status']=='passed' and driver['exit_code']==0 and not driver['resource_stopped'];assert driver['selector']['source_sha256']==helper.SOURCE and driver['selector']['phase']=='verify'
for name in ['driver.stdout','driver.stderr','resources.jsonl']:assert helper.sha(local/name)==driver[name]['sha256']
result=[]
for name,root in [('local-macos26-arm',local/'release-results'),('github-macos14-arm',floor/'release-results')]:
 kit=helper.load(root/'verified-selfhost-smoke/receipt.json');reference=helper.load(producer['aarch64-apple-darwin']/'unpacked-selfhost-smoke/receipt.json');assert kit['status']=='passed' and kit['joy']['sha256']==reference['joy']['sha256'] and kit['kit_manifest']==reference['kit_manifest']
 for index,item in enumerate(selected['corpora']):
  receipt=root/f'verification-{index}.json';checked=helper.pair(receipt,producer[item['target']]/'proof-corpus/corpus.json',candidate)
  if name=='github-macos14-arm':assert helper.sha(receipt)==report['verifications'][index]['sha256']
  result.append(dict(consumer=name,producer=item['target'],**checked))
output=dict(scope='Two actual Mac ARM consumer measurements only; required six-native-consumer matrix remains separate',status='passed',source_sha256=helper.SOURCE,selector_sha256=helper.sha(CI/'.github/release-candidate.json'),inspector_sha256=helper.sha(Path(__file__)),case_checks=sum(p['cases'] for p in result),pairs=result)
with (M/'frozen-mac-consumers-inspection.json').open('x') as stream:stream.write(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:output[k] for k in ['status','case_checks']},indent=2))
