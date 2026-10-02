"""Read back every complete authenticated final local draft package asset."""
from pathlib import Path
import datetime,hashlib,json,subprocess,traceback
M=Path(__file__).resolve().parent
O=M/'local-package-readback'
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def main():
 transport=json.loads((M/'local-package-transport/receipt.json').read_text())
 coordinated=json.loads((M/'local-package-transport-coordination/receipt.json').read_text())
 if transport['status']!='passed' or coordinated['status']!='passed':raise ValueError('complete guarded package transport required')
 proposed=json.loads((M/'local-package-transport-proposal.json').read_text())
 expected={row['proposed_asset_name']:row for row in proposed['payloads']}
 if len(transport['assets'])!=3 or {row['name'] for row in transport['assets']}!=expected.keys():raise ValueError('exact three reviewed package assets required')
 O.mkdir()
 report=dict(status='running',scope='Complete byte readback of three final local draft archives; full198 and consumers remain separate',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),script_sha256=sha(Path(__file__)),transport_sha256=sha(M/'local-package-transport/receipt.json'),coordination_sha256=sha(M/'local-package-transport-coordination/receipt.json'),commands=[],assets=[])
 def save():(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
 def api(name,endpoint,absent=False):
  command=['gh','api',endpoint];r=subprocess.run(command,capture_output=True)
  for field in ('stdout','stderr'):(O/(name+'.'+field)).write_bytes(getattr(r,field))
  report['commands'].append(dict(command=command,exit_code=r.returncode));save();value=json.loads(r.stdout)
  if absent:
   if r.returncode!=1 or str(value.get('status'))!='404':raise ValueError('draft tag must remain absent')
  elif r.returncode:raise RuntimeError(name+' API failed')
  return value
 def draft(name):
  value=api(name,'repos/cyberia-to/trisha/releases/389977897')
  if value['draft'] is not True or value['tag_name']!='candidate-20260916.1':raise ValueError('existing unpublished draft required')
  api(name+'-tag','repos/cyberia-to/trisha/git/ref/tags/candidate-20260916.1',True)
 save()
 try:
  draft('before')
  for entry in transport['assets']:
   wanted=expected[entry['name']];kind=entry['kind'];metadata=api(kind+'-metadata','repos/cyberia-to/trisha/releases/assets/'+str(entry['asset_id']))
   if metadata['name']!=entry['name'] or metadata['size']!=wanted['bytes'] or metadata['digest']!='sha256:'+wanted['sha256'] or entry['sha256']!=wanted['sha256']:raise ValueError('authenticated package asset identity differs')
   path=O/entry['name'];command=['gh','api','-H','Accept: application/octet-stream',metadata['url']]
   with path.open('xb') as out,(O/(kind+'-download.stderr')).open('xb') as err:r=subprocess.run(command,stdout=out,stderr=err)
   report['commands'].append(dict(command=command,exit_code=r.returncode));save()
   if r.returncode or path.stat().st_size!=wanted['bytes'] or sha(path)!=wanted['sha256'] or sha(Path(wanted['path']))!=wanted['sha256']:raise ValueError('complete original and downloaded package bytes differ')
   report['assets'].append(dict(kind=kind,asset_id=entry['asset_id'],name=entry['name'],bytes=path.stat().st_size,sha256=sha(path),download_path=str(path)));save();print(kind,entry['asset_id'],'complete byte readback passed',flush=True)
  draft('after');report.update(status='passed',ended=datetime.datetime.now(datetime.timezone.utc).isoformat())
 except BaseException:
  report.update(status='failed',error=traceback.format_exc());raise
 finally:save()
if __name__=='__main__':main()
