"""Authenticate every complete remote final-package transport body, read only."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,subprocess,traceback
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci'
RUN=37000157290;HEAD='98b45784e61b78f39a02004bd39fa74c11e7b3a9'
PRODUCER=36990413939;PRODUCER_HEAD='5de26a93eb4d489d90f150882adec2c47d14bea4'
SELECTOR='81b1f1febf9c59d4beebf0c827d67541c106b7675c5c4ae8a75433e10de6b4e3'
O=M/'remote-package-readback'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
def require(ok,why):
 if not ok:raise ValueError(why)
def main():
 helper=M/'inspect-final-native-producer.py'
 require(sha(helper)=='64572b572e3a7319f837d788307436e36b54802cc0ba6f146c541bb297d43a8a','frozen inspector changed')
 spec=importlib.util.spec_from_file_location('inspector',helper);inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)
 selection=CI/'.github/final-package-assets.json';require(sha(selection)==SELECTOR,'reviewed transport selector changed')
 chosen=load(selection)
 roots=[p for p in (M/'native-runs'/str(RUN)).iterdir() if (p/'retention.json').is_file()]
 require(len(roots)==1,'exact one retained transport container required');root=roots[0]
 artifact,retention,digest=inspector.container(root,RUN,HEAD);r=load(root/'restored/receipt.json')
 require(r['status']=='passed' and r['selector']==chosen and len(r['assets'])==20,'transport receipt did not pass exact selector')
 expected={}
 for row in chosen['producers']:
  target=row['target'];p=M/'native-runs'/str(PRODUCER)/str(row['artifact_id']);inspector.container(p,PRODUCER,PRODUCER_HEAD)
  result=p/'restored';archive=load(result/'archive.json')
  for kind,path in [('binary',result/archive['archive']),('corpus',result/('proof-corpus-'+target+'.tar.gz')),('structured-corpus',result/('structured-corpus-'+target+'.tar.gz')),('evidence',p/'artifact.zip')]:
   expected[target,kind]=dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path),artifact_id=row['artifact_id'])
 require(len(expected)==20 and len({(x['target'],x['kind']) for x in r['assets']})==20,'distinct exact twenty payloads required')
 O.mkdir();report=dict(status='running',scope='Complete authenticated readback of twenty final remote draft payloads; consumer activation separate',run_id=RUN,runner_revision=HEAD,started=datetime.datetime.now(datetime.timezone.utc).isoformat(),script_sha256=sha(Path(__file__)),transport_artifact_id=artifact['id'],transport_zip_sha256=digest,transport_receipt_sha256=sha(root/'restored/receipt.json'),selector_sha256=SELECTOR,commands=[],assets=[])
 def save():(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
 def api(name,url,absent=False):
  cmd=['gh','api',url];p=subprocess.run(cmd,capture_output=True)
  for stream in ('stdout','stderr'):(O/(name+'.'+stream)).write_bytes(getattr(p,stream))
  report['commands'].append(dict(command=cmd,exit_code=p.returncode));save();value=json.loads(p.stdout)
  if absent:require(p.returncode==1 and str(value.get('status'))=='404','tag must stay absent')
  else:require(p.returncode==0,name+' API failed')
  return value
 def draft(name):
  j=api(name,'repos/cyberia-to/trisha/releases/389977897');require(j['id']==389977897 and j['draft'] is True and j['tag_name']=='candidate-20260916.1','existing unpublished draft required')
  api(name+'-tag','repos/cyberia-to/trisha/git/ref/tags/candidate-20260916.1',True)
 save()
 try:
  run=api('run','repos/cyberia-to/trisha/actions/runs/'+str(RUN));require(run['head_sha']==HEAD and run['status']=='completed' and run['conclusion']=='success','exact successful transport run required')
  fresh=api('artifact','repos/cyberia-to/trisha/actions/artifacts/'+str(artifact['id']));require(fresh['workflow_run']['id']==RUN and fresh['digest']=='sha256:'+digest and not fresh['expired'],'fresh authenticated transport artifact changed')
  draft('before')
  for row in r['assets']:
   name=row['target']+'-'+row['kind'];wanted=expected[row['target'],row['kind']]
   require(row['sha256']==wanted['sha256'] and row['bytes']==wanted['bytes'] and row['producer_run_id']==PRODUCER and row['producer_artifact_id']==wanted['artifact_id'],'transport differs from inspected original')
   metadata=api(name+'-metadata','repos/cyberia-to/trisha/releases/assets/'+str(row['asset_id']))
   require(metadata['id']==row['asset_id'] and metadata['name']==row['name'] and metadata['size']==wanted['bytes'] and metadata['digest']=='sha256:'+wanted['sha256'],'authenticated asset metadata differs')
   output=O/row['name'];require(output.parent==O,'unsafe asset name')
   cmd=['gh','api','-H','Accept: application/octet-stream',metadata['url']]
   with output.open('xb') as out,(O/(name+'-download.stderr')).open('xb') as err:p=subprocess.run(cmd,stdout=out,stderr=err)
   report['commands'].append(dict(command=cmd,exit_code=p.returncode));save()
   require(p.returncode==0 and output.stat().st_size==wanted['bytes'] and sha(output)==wanted['sha256'] and sha(Path(wanted['path']))==wanted['sha256'],'complete body differs from original producer')
   report['assets'].append(dict(**row,original_path=wanted['path'],download_path=str(output)));save();print(name,row['asset_id'],'complete readback passed',flush=True)
  draft('after');report.update(status='passed',ended=datetime.datetime.now(datetime.timezone.utc).isoformat())
 except BaseException:report.update(status='failed',error=traceback.format_exc());raise
 finally:save()
if __name__=='__main__':main()
