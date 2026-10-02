"""Bounded parallel, read-only final transport body readback; original attempt retained."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import datetime,hashlib,importlib.util,json,shutil,subprocess,traceback
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';O=M/'remote-package-parallel-readback'
RUN=37000157290;HEAD='98b45784e61b78f39a02004bd39fa74c11e7b3a9';SELECTOR='81b1f1febf9c59d4beebf0c827d67541c106b7675c5c4ae8a75433e10de6b4e3'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,j):p.write_text(json.dumps(j,indent=2)+'\n')
def require(ok,why):
 if not ok:raise ValueError(why)
def main():
 helper=M/'inspect-final-native-producer.py';require(sha(helper)=='64572b572e3a7319f837d788307436e36b54802cc0ba6f146c541bb297d43a8a','frozen inspector differs')
 s=importlib.util.spec_from_file_location('inspector',helper);inspector=importlib.util.module_from_spec(s);s.loader.exec_module(inspector)
 selector=CI/'.github/final-package-assets.json';require(sha(selector)==SELECTOR,'reviewed selector changed');chosen=load(selector)
 root=M/'native-runs/37000157290/11223880977';api,ret,digest=inspector.container(root,RUN,HEAD);transport=load(root/'restored/receipt.json')
 require(transport['status']=='passed' and transport['selector']==chosen and len(transport['assets'])==20,'exact successful twenty-payload transport required')
 expected={}
 for item in chosen['producers']:
  d=M/'native-runs'/str(item['run_id'])/str(item['artifact_id']);inspector.container(d,item['run_id'],item['head_sha']);p=d/'restored';a=load(p/'archive.json');t=item['target']
  for kind,q in [('binary',p/a['archive']),('corpus',p/('proof-corpus-'+t+'.tar.gz')),('structured-corpus',p/('structured-corpus-'+t+'.tar.gz')),('evidence',d/'artifact.zip')]:expected[t,kind]=dict(path=str(q),bytes=q.stat().st_size,sha256=sha(q),artifact_id=item['artifact_id'])
 require(len(expected)==20 and {(x['target'],x['kind']) for x in transport['assets']}==set(expected),'exact distinct asset map required')
 O.mkdir();snapshot=(M/'remote-package-readback/receipt.json').read_bytes();(O/'original-serial-snapshot.json').write_bytes(snapshot);prior=json.loads(snapshot);reusable={x['asset_id']:x for x in prior['assets']}
 report=dict(status='running',scope='All twenty final remote bodies authenticated; bounded three parallel downloads alongside unchanged serial attempt; previously completed serial bodies rehashed against fresh API metadata',run_id=RUN,runner_revision=HEAD,selector_sha256=SELECTOR,started=datetime.datetime.now(datetime.timezone.utc).isoformat(),script_sha256=sha(Path(__file__)),transport_artifact_id=api['id'],transport_zip_sha256=digest,transport_receipt_sha256=sha(root/'restored/receipt.json'),original_serial_snapshot_sha256=hashlib.sha256(snapshot).hexdigest(),commands=[],assets=[])
 def save():dump(O/'receipt.json',report)
 def request(directory,name,url,absent=False):
  cmd=['gh','api',url];p=subprocess.run(cmd,capture_output=True)
  for stream in ['stdout','stderr']:(directory/(name+'.'+stream)).write_bytes(getattr(p,stream))
  row=dict(command=cmd,exit_code=p.returncode);j=json.loads(p.stdout)
  if absent:require(p.returncode==1 and str(j.get('status'))=='404','draft tag must stay absent')
  else:require(p.returncode==0,name+' API failed')
  return j,row
 def draft(name):
  j,c=request(O,name,'repos/cyberia-to/trisha/releases/389977897');report['commands'].append(c);require(j['id']==389977897 and j['draft'] is True and j['tag_name']=='candidate-20260916.1','existing unpublished draft required')
  _,c=request(O,name+'-tag','repos/cyberia-to/trisha/git/ref/tags/candidate-20260916.1',True);report['commands'].append(c);save()
 def worker(row):
  name=row['target']+'-'+row['kind'];d=O/name;d.mkdir();wanted=expected[row['target'],row['kind']];result=dict(status='running',asset=row,commands=[]);dump(d/'receipt.json',result)
  try:
   require(row['sha256']==wanted['sha256'] and row['bytes']==wanted['bytes'] and row['producer_run_id']==36990413939 and row['producer_artifact_id']==wanted['artifact_id'],'transport and original producer differ')
   metadata,c=request(d,'metadata','repos/cyberia-to/trisha/releases/assets/'+str(row['asset_id']));result['commands'].append(c)
   require(metadata['id']==row['asset_id'] and metadata['name']==row['name'] and metadata['size']==wanted['bytes'] and metadata['digest']=='sha256:'+wanted['sha256'],'fresh authenticated body metadata differs')
   output=d/row['name'];require(output.parent==d,'unsafe asset name');old=reusable.get(row['asset_id'])
   if old:
    require(old['sha256']==wanted['sha256'] and old['bytes']==wanted['bytes'],'prior completed body claim differs');src=Path(old['download_path']);require(src.stat().st_size==wanted['bytes'] and sha(src)==wanted['sha256'],'prior completed serial body differs');shutil.copyfile(src,output);result['reused_complete_serial_body']=str(src)
   else:
    cmd=['gh','api','-H','Accept: application/octet-stream',metadata['url']]
    with output.open('xb') as out,(d/'download.stderr').open('xb') as err:p=subprocess.run(cmd,stdout=out,stderr=err)
    result['commands'].append(dict(command=cmd,exit_code=p.returncode));require(p.returncode==0,'complete download failed')
   require(output.stat().st_size==wanted['bytes'] and sha(output)==wanted['sha256'] and sha(Path(wanted['path']))==wanted['sha256'],'complete downloaded and original producer bodies differ')
   result.update(status='passed',original_path=wanted['path'],download_path=str(output));dump(d/'receipt.json',result)
   return dict(**row,original_path=wanted['path'],download_path=str(output),body_receipt_sha256=sha(d/'receipt.json'))
  except BaseException:result.update(status='failed',error=traceback.format_exc());dump(d/'receipt.json',result);raise
 save()
 try:
  run,c=request(O,'run',f'repos/cyberia-to/trisha/actions/runs/{RUN}');report['commands'].append(c);require(run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==HEAD,'successful exact transport run required')
  fresh,c=request(O,'artifact','repos/cyberia-to/trisha/actions/artifacts/11223880977');report['commands'].append(c);require(fresh['digest']=='sha256:'+digest and fresh['workflow_run']['id']==RUN and not fresh['expired'],'fresh transport container differs')
  draft('before')
  with ThreadPoolExecutor(max_workers=3) as pool:
   futures=[pool.submit(worker,row) for row in transport['assets']]
   for future in as_completed(futures):
    row=future.result();report['assets'].append(row);save();print(len(report['assets']),row['target'],row['kind'],'complete byte readback passed',flush=True)
  require(len(report['assets'])==20,'incomplete readback');draft('after');report.update(status='passed',ended=datetime.datetime.now(datetime.timezone.utc).isoformat())
 except BaseException:report.update(status='failed',error=traceback.format_exc());raise
 finally:save()
if __name__=='__main__':main()
