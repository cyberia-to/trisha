"""Retain exact successful final remote transport/readback and inactive proposals."""
from pathlib import Path
import gzip,hashlib,json,shutil
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';O=CI/'audit/final-host-ceiling-package/remote-asset-transport'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
def main():
 readback=load(M/'remote-package-readback/receipt.json');proposal=load(M/'consumer-proposal/receipt.json');assert readback['status']=='passed' and len(readback['assets'])==20 and proposal['status']=='passed-proposal-only'
 assert proposal['remote_readback_sha256']==sha(M/'remote-package-readback/receipt.json') and readback['run_id']==37000157290
 O.mkdir();rows=[];external=[]
 def copy(p,relative):
  raw=p.read_bytes();enc='identity'
  if p.suffix in ('.stdout','.stderr','.log'):relative=Path(str(relative)+'.gz');enc='gzip-original';b=gzip.compress(raw,mtime=0)
  else:b=raw
  target=O/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b);rows.append(dict(source=str(p),stored=str(relative),encoding=enc,original_bytes=len(raw),original_sha256=hashlib.sha256(raw).hexdigest(),stored_sha256=hashlib.sha256(b).hexdigest()))
 root=M/'native-runs/37000157290/11223880977'
 for name in ['artifact.zip','api.json','retention.json']:copy(root/name,Path('original-actions')/name)
 for p in sorted((root/'restored').rglob('*')):
  if p.is_file():copy(p,Path('original-transport')/p.relative_to(root/'restored'))
 for folder in ['after-remote-package-origin','remote-package-readback','consumer-proposal']:
  for p in sorted((M/folder).rglob('*')):
   if not p.is_file():continue
   if folder=='remote-package-readback' and p.suffix in ('.gz','.zip'):continue
   copy(p,Path(folder)/p.relative_to(M/folder))
 for name in ['collect-native.py','collect-37000157290.log','check-final-origin-after-remote-packages.py','after-remote-package-origin.stdout','after-remote-package-origin.stderr','readback-final-remote-packages.py','readback-final-remote-packages.stdout','readback-final-remote-packages.stderr','prepare-final-consumers.py','consumer-proposal.stdout','consumer-proposal.stderr','watch-final-consumer-proposal.py','consumer-proposal-watch.json','consumer-proposal-watch.stdout','consumer-proposal-watch.stderr','remote-transport-activation-commit.log','remote-transport-activation-push.stdout','remote-transport-activation-push.stderr']:
  copy(M/name,Path('commands')/name)
 for row in readback['assets']:
  p=Path(row['download_path']);assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'];external.append(row)
 copy(Path(__file__),Path(__file__).name)
 (O/'retention-manifest.json').write_text(json.dumps(dict(scope='Original successful final20asset transport and complete serial authenticated readback; proposed consumer selectors not activated at this observation',files=rows,complete_downloaded_bodies=external),indent=2)+'\n')
 print('Retained',len(rows),'original transport/readback/proposal files and20externalcompletebody identities')
if __name__=='__main__':main()
