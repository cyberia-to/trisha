"""Activate consumption only of authenticated, retained current native packages."""
from pathlib import Path
import hashlib,json,shutil
M=Path(__file__).resolve().parent;CI=M.parent/'trisha-native-ci';O=CI/'audit/current-native-package/remote-asset-transport';O.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
root=M/'native-runs/36973773801/11212184914';ret=load(root/'retention.json');api=load(root/'api.json');p=root/'restored';r=load(p/'receipt.json')
assert ret['head_sha']=='a12f032f3dfd866025e07fd6f1347b0bf0b2d48d' and ret['run_id']==api['workflow_run']['id']==36973773801
assert sha(root/'artifact.zip')==ret['archive_sha256']==api['digest'].removeprefix('sha256:')
for f in ret['files']:
 q=p/f['path'];assert q.stat().st_size==f['bytes'] and sha(q)==f['sha256']
assert r['status']=='passed' and len(r['assets'])==20
assert r['selector']==load(CI/'.github/current-package-assets.json')
for q in p.glob('*-tag.stdout'):assert str(load(q)['status'])=='404'
for q in p.glob('*draft.stdout'):assert load(q)['draft'] is True and load(q)['id']==389977897
assert load(p/'draft-before.stdout')['draft'] is True
spec=load(CI/'.github/release-candidate.json');assert spec['phase']=='build' and spec['source_sha256']==r['selector']['source_sha256'];dump(O/'original-build-selector.json',spec)
producers={}
for d in (M/'native-runs/36969168806').iterdir():
 if (d/'inspection.json').exists():producers[load(d/'inspection.json')['target']]=d/'restored'
producers['aarch64-apple-darwin']=M.parent/'local-macos-current-rust189/release-results';assert len(producers)==6
assets={}
for x in r['assets']:
 target=x['target'];q=producers[target];a=load(q/'archive.json')
 original=q/a['archive'] if x['kind']=='binary' else q/('proof-corpus-'+target+'.tar.gz') if x['kind']=='corpus' else q/('structured-corpus-'+target+'.tar.gz') if x['kind']=='structured-corpus' else q.parent/'artifact.zip'
 assert sha(original)==x['sha256'] and original.stat().st_size==x['bytes'];assert (target,x['kind']) not in assets;assets[target,x['kind']]=x
local=load(M/'local-package-transport/receipt.json');assert local['status']=='passed';assert len(local['assets'])==3
for x in local['assets']:
 name=x['name'];kind='structured-corpus' if 'structured-corpus' in name else 'corpus' if 'proof-corpus' in name else 'binary';assets['aarch64-apple-darwin',kind]=x
before=M/'before-remote-package-origin';after=M/'after-remote-package-origin'
assert load(after/'receipt.json')['status']=='passed'
for x in load(after/'receipt.json')['inputs']:
 name=x['repository'];old=dict(line.split()[::-1] for line in (before/name/'heads.stdout').read_text().splitlines());new=dict(line.split()[::-1] for line in (after/name/'heads.stdout').read_text().splitlines())
 for default in ['refs/heads/main','refs/heads/master']:assert old.get(default)==new.get(default),(name,default)
shutil.copytree(after,O/'after-origin');shutil.copy2(M/'check-current-origin-after-remote-packages.py',O/'check-current-origin-after-remote-packages.py')
for name in ['api.json','retention.json']:shutil.copy2(root/name,O/name)
shutil.copy2(root/'artifact.zip',O/'original-artifact.zip');shutil.copy2(p/'receipt.json',O/'receipt.json')
def entry(target,kind):
 row=assets[target,kind];return dict(asset_id=row['asset_id'],sha256=row['sha256'])
order=sorted(producers);spec['phase']='verify';spec['binaries']={target:entry(target,'binary') for target in order};spec['corpora']=[dict(target=target,**entry(target,'corpus')) for target in order];spec['structured_corpora']=[dict(target=target,**entry(target,'structured-corpus')) for target in order]
spec['scope']='Current 734df69d exact six native package consumer rehearsal; both legacy and structured corpora; no default-branch release/tag/publication'
dump(CI/'.github/release-candidate.json',spec)
dump(CI/'.github/current-package-macos-floor.json',dict(scope='Actual macOS14 ARM installed current734 Joy/Trisha legacy and structured corpus plus accepted-kit consumer only; no whole proof generation or Trident/LSP floor qualification',selector_sha256=sha(CI/'.github/release-candidate.json'),source_sha256=spec['source_sha256']))
cache=load(M/'local-asset-cache.json')
for target,q in producers.items():
 a=load(q/'archive.json')
 for kind in ['binary','corpus','structured-corpus']:
  x=assets[target,kind];path=q/a['archive'] if kind=='binary' else q/('proof-corpus-'+target+'.tar.gz') if kind=='corpus' else q/('structured-corpus-'+target+'.tar.gz');assert sha(path)==x['sha256'];cache[str(x['asset_id'])]=str(path)
dump(M/'local-consumer-asset-cache.json',cache)
D=CI/'audit/current-native-package/matrix-helper-checks';D.mkdir()
for name in ['check-current-corpus-matrix.py','check-current-matrix-helper.py']:shutil.copy2(M/name,D/name)
shutil.copy2(M/'matrix-helper-six-producers/receipt.json',D/'receipt.json');shutil.copy2(Path(__file__),O/Path(__file__).name)
dump(O/'activation.json',dict(status='passed',scope='Authenticated transport and unchanged default refs checked before six-native consumer activation; final corpus/full198 verdict separate',transport_run=36973773801,producer_run=36969168806,selector_sha256=sha(CI/'.github/release-candidate.json'),source_sha256=spec['source_sha256'],script_sha256=sha(Path(__file__)),remote_assets=20,local_assets=3))
print(json.dumps(dict(status='passed',selector_sha256=sha(CI/'.github/release-candidate.json'))))
