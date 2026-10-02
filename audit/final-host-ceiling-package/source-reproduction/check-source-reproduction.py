"""Authenticate independent final source reproduction and download its exact draft asset."""
from pathlib import Path
import datetime,hashlib,json,subprocess,tarfile,time,traceback
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';O=M/'source-reproduction-readback';O.mkdir()
RUN=36987731030;HEAD='6ad79cad0ab499c9dd707a5cad34de901993a8bc';SOURCE='73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8';PROVENANCE='9334dead92b990a12acf16a2565aeb762a07311dfc2c3d6cb896c0490dc5926e';VENDOR='cf324959661a85fc94cf4345beaf5dbf274c1dbd5fc66960155e0750ace35d1b'
report=dict(status='waiting_for_reproduction',scope='Independent remote final source archive plus authenticated exact draft-asset readback; native gates remain inactive',run_id=RUN,head_sha=HEAD,commands=[])
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save():(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def api(name,endpoint,allowed=(0,)):
 command=['gh','api',endpoint];r=subprocess.run(command,capture_output=True)
 for field in ('stdout','stderr'):(O/(name+'.'+field)).write_bytes(getattr(r,field))
 report['commands'].append(dict(command=command,exit_code=r.returncode));save()
 if r.returncode not in allowed:raise ValueError(name+' API failed')
 return json.loads(r.stdout)
save()
try:
 while True:
  result=json.loads(subprocess.check_output(['gh','api',f'repos/cyberia-to/trisha/actions/runs/{RUN}']))
  if result['head_sha']!=HEAD:raise ValueError('source preparer head differs')
  if result['status']=='completed':break
  time.sleep(30)
 (O/'completed-run.json').write_text(json.dumps(result,indent=2)+'\n')
 if result['conclusion']!='success':raise ValueError('independent source reproduction did not pass')
 artifacts=api('artifacts',f'repos/cyberia-to/trisha/actions/runs/{RUN}/artifacts?per_page=100')['artifacts'];items=[x for x in artifacts if x['name']=='final-package-source-preparation']
 if len(items)!=1:raise ValueError('exact original preparer artifact missing')
 item=items[0];retained=M/'native-runs'/str(RUN)/str(item['id'])
 while not (retained/'retention.json').exists():time.sleep(5)
 retention=json.loads((retained/'retention.json').read_text());assert retention['run_id']==RUN and retention['head_sha']==HEAD and item['digest']=='sha256:'+sha(retained/'artifact.zip')== 'sha256:'+retention['archive_sha256']
 original=json.loads((retained/'restored/receipt.json').read_text());impact=json.loads((retained/'restored/source-impact.json').read_text());selected=json.loads((CI/'.github/final-package-source.json').read_text())
 assert original['status']=='passed' and original['selector']==selected and original['archive']==dict(bytes=536837002,sha256=SOURCE)
 assert impact['status']=='passed' and impact['source_provenance_sha256']==PROVENANCE and impact['selector_sha256']==sha(CI/'.github/final-package-inputs.json') and impact['script_sha256']==sha(CI/'scripts/final-source-impact.py')
 asset=api('asset','repos/cyberia-to/trisha/releases/assets/'+str(original['asset']['id']));assert asset['name']==selected['asset_name'] and asset['digest']=='sha256:'+SOURCE and asset['size']==536837002
 report.update(status='downloading',artifact_id=item['id'],artifact_zip_sha256=sha(retained/'artifact.zip'),asset=asset,started=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
 archive=O/'source-export.tar.gz';command=['gh','api','-H','Accept: application/octet-stream',asset['url']]
 with archive.open('xb') as out,(O/'download.stderr').open('xb') as err:r=subprocess.run(command,stdout=out,stderr=err)
 report['commands'].append(dict(command=command,exit_code=r.returncode));save();assert r.returncode==0 and archive.stat().st_size==536837002 and sha(archive)==SOURCE==sha(M/'source-export.tar.gz')
 with tarfile.open(archive) as content:
  for name,expected in [('sources.json',PROVENANCE),('vendor-sources.json',VENDOR)]:
   raw=content.extractfile('cyber-source/'+name).read();assert hashlib.sha256(raw).hexdigest()==expected;(O/name).write_bytes(raw)
 draft=api('draft-after','repos/cyberia-to/trisha/releases/389977897');assert draft['draft'] is True and draft['tag_name']=='candidate-20260916.1'
 tag=api('tag-after','repos/cyberia-to/trisha/git/ref/tags/candidate-20260916.1',(1,));assert str(tag['status'])=='404'
 report.update(status='passed',source_sha256=SOURCE,source_provenance_sha256=PROVENANCE,vendor_sha256=VENDOR,archive_bytes=archive.stat().st_size,original_container=str(retained),script_sha256=sha(Path(__file__)),ended=datetime.datetime.now(datetime.timezone.utc).isoformat());print(json.dumps({k:report[k] for k in ('status','source_sha256','archive_bytes','artifact_id')}))
except BaseException:
 report.update(status='failed',error=traceback.format_exc());raise
finally:save()
