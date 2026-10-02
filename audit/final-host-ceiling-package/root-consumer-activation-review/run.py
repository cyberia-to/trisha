import hashlib,json,subprocess,time
from pathlib import Path
O=Path(__file__).resolve().parent;M=O.parent;CI=M.parent/'trisha-native-ci';P=M/'consumer-proposal'
def identity(p):
 with p.open('rb') as f:return dict(bytes=p.stat().st_size,sha256=hashlib.file_digest(f,'sha256').hexdigest())
def load(p):return json.loads(p.read_text())
def api(name,path,absent=False):
 argv=['gh','api',path];r=subprocess.run(argv,capture_output=True,timeout=90)
 for k in ['stdout','stderr']:(O/(name+'.'+k)).write_bytes(getattr(r,k))
 commands.append(dict(argv=argv,exit_code=r.returncode));d=json.loads(r.stdout)
 if absent:assert r.returncode==1 and str(d.get('status'))=='404'
 else:assert r.returncode==0
 return d
commands=[]
assert identity(P/'proposed-final-candidate.json')['sha256']=='084bfe4821114455881b1fd2718d8a10373e48562d97093ef3a580b0fb9626ba'
assert identity(P/'proposed-final-macos-floor.json')['sha256']=='35bed4ce88573d2bb61c9e712fe867e57d71d5068e208276fe18e9e4424debce'
proposal=load(P/'receipt.json');assert proposal['status']=='passed-proposal-only'
s=load(P/'proposed-final-candidate.json');old=load(CI/'.github/final-package-candidate.json')
assert {k for k in set(s)|set(old) if s.get(k)!=old.get(k)}=={'scope','phase','binaries','corpora','structured_corpora'}
assert s['phase']=='verify' and s['status']=='active' and s['source_sha256']=='73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8'
f=load(P/'proposed-final-macos-floor.json');oldf=load(CI/'.github/final-package-macos-floor.json')
assert {k for k in set(f)|set(oldf) if f.get(k)!=oldf.get(k)}=={'scope','status','selector_sha256'}
assert f['status']=='active' and f['selector_sha256']==identity(P/'proposed-final-candidate.json')['sha256'] and f['source_sha256']==s['source_sha256']
targets={'aarch64-apple-darwin','x86_64-apple-darwin','aarch64-unknown-linux-gnu','x86_64-unknown-linux-gnu','aarch64-pc-windows-msvc','x86_64-pc-windows-msvc'}
assert set(s['binaries'])==targets and all(len(s[n])==6 and {x['target'] for x in s[n]}==targets for n in ['corpora','structured_corpora'])
remote=load(M/'remote-package-readback/receipt.json');local=load(M/'local-package-readback/receipt.json')
assert remote['status']==local['status']=='passed' and len(remote['assets'])==20 and len(local['assets'])==3
assert identity(M/'remote-package-readback/receipt.json')['sha256']==proposal['remote_readback_sha256']=='c2071e1328ff504b73827ef8eb018b7269d472cd229df79a66cd3f6e1475b430'
assert identity(M/'local-package-readback/receipt.json')['sha256']==proposal['local_readback_sha256']
assets={}
for row in remote['assets']:
 key=row['target'],row['kind'];assert key not in assets;assets[key]=row
for row in local['assets']:assets['aarch64-apple-darwin',row['kind']]=row
release=api('draft','repos/cyberia-to/trisha/releases/389977897');assert release['draft'] is True and release['tag_name']=='candidate-20260916.1'
api('tag','repos/cyberia-to/trisha/git/ref/tags/candidate-20260916.1',True)
current={a['id']:a for a in release['assets']}
for key,row in assets.items():
 assert identity(Path(row['download_path']))==dict(bytes=row['bytes'],sha256=row['sha256'])
 if 'original_path' in row:assert identity(Path(row['original_path']))==dict(bytes=row['bytes'],sha256=row['sha256'])
 meta=current[row['asset_id']];assert meta['size']==row['bytes'] and meta['digest']=='sha256:'+row['sha256']
 for kind,name in [('corpus','corpora'),('structured-corpus','structured_corpora')]:
  if key[1]==kind:assert next(x for x in s[name] if x['target']==key[0])==dict(target=key[0],asset_id=row['asset_id'],sha256=row['sha256'])
 if key[1]=='binary':assert s['binaries'][key[0]]==dict(asset_id=row['asset_id'],sha256=row['sha256'])
full=load(M/'local-rust189-complete/receipt.json');back=load(M/'local-evidence-readback/receipt.json')
assert full['status']==back['status']=='passed' and full['proof_gate']['fresh_verified_proofs']==198 and full['coverage']=='fresh_full198_performed_for_actual_final_Trisha'
assert full['binaries']['trisha']=='fe069879a44b582a47069c5cd849b1eb3da4c75a037e72aa9d107742ecc8173f' and full['archive']['sha256']==back['archive_sha256']=='9cc80e1c5d420179c1a33c7cb28ce9e1db25ff43712487da79f71ad3c6d71612' and back['asset']['id']==605413707
sources={}
for path in ['scripts/native-candidate.py','scripts/native-rehearsal-macos-floor.py','scripts/current-structured-corpus.py','scripts/check-installed-host-ceiling.py','.github/workflows/final-package-native.yml','.github/workflows/final-package-macos-floor.yml']:
 original=subprocess.check_output(['git','show','5de26a93eb4d489d90f150882adec2c47d14bea4:'+path],cwd=CI);assert (CI/path).read_bytes()==original;sources[path]=identity(CI/path)
for name in ['before-remote-package-origin','after-remote-package-origin']:
 assert load(M/name/'receipt.json')['status']=='passed'
cache=load(P/'local-consumer-asset-cache.json')
for row in assets.values():
 if row['kind']!='evidence':assert identity(Path(cache[str(row['asset_id'])]))==dict(bytes=row['bytes'],sha256=row['sha256'])
report=dict(status='passed-exact-consumer-selector-review',observed_ns=time.time_ns(),candidate=identity(P/'proposed-final-candidate.json'),macos_floor=identity(P/'proposed-final-macos-floor.json'),proposal=identity(P/'receipt.json'),source_files=sources,commands=commands,remote_bodies=20,local_bodies=3,full198='Fresh actual finalTrisha proof gate retained and authenticated separately; historical baseline_reference is not coverage',authorization='Activate only the two exact reviewed selectors; run five remote and one local original bounded consumers plus separate macOS14 ARM gate. No release publication or source/profile/cap changes.',source=identity(Path(__file__)))
(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status=report['status'],receipt=identity(O/'receipt.json'))))
