"""Prepare, without activating, exact consumers after all complete asset readbacks."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
M=Path(__file__).resolve().parent;R=M.parent;CI=R/'trisha-native-ci';O=M/'consumer-proposal'
SOURCE='73b50ebdd451908ca6da801a0c30b81ae6a9bc053e98cb8449db9a209b11f3f8'
TARGETS={'aarch64-apple-darwin','x86_64-apple-darwin','aarch64-unknown-linux-gnu','x86_64-unknown-linux-gnu','aarch64-pc-windows-msvc','x86_64-pc-windows-msvc'}
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def require(ok,why):
 if not ok:raise ValueError(why)
def main():
 remote=load(M/'remote-package-readback/receipt.json');local=load(M/'local-package-readback/receipt.json')
 require(remote['status']==local['status']=='passed' and len(remote['assets'])==20 and len(local['assets'])==3,'all23 complete authenticated package readbacks required')
 require(remote['run_id']==37000157290 and remote['runner_revision']=='98b45784e61b78f39a02004bd39fa74c11e7b3a9' and remote['selector_sha256']=='81b1f1febf9c59d4beebf0c827d67541c106b7675c5c4ae8a75433e10de6b4e3','transport selection differs')
 complete=load(M/'local-rust189-complete/receipt.json');full=load(M/'local-evidence-readback/receipt.json')
 require(complete['status']==full['status']=='passed' and complete['coverage']=='fresh_full198_performed_for_actual_final_Trisha' and complete['proof_gate']['fresh_verified_proofs']==198 and full['archive_sha256']==complete['archive']['sha256']=='9cc80e1c5d420179c1a33c7cb28ce9e1db25ff43712487da79f71ad3c6d71612','fresh final full198 and durable readback required')
 before=M/'before-remote-package-origin';after=M/'after-remote-package-origin';b=load(before/'receipt.json');a=load(after/'receipt.json')
 require(a['status']==b['status']=='passed' and a['source_sha256']==b['source_sha256']==SOURCE and len(a['inputs'])==11,'all eleven pinned source reachability observations required')
 for x in a['inputs']:
  name=x['repository'];old={line.split()[1]:line.split()[0] for line in (before/name/'heads.stdout').read_text().splitlines()};new={line.split()[1]:line.split()[0] for line in (after/name/'heads.stdout').read_text().splitlines()}
  for default in ['refs/heads/main','refs/heads/master']:require(old.get(default)==new.get(default),'default ref changed: '+name)
 assets={}
 for x in remote['assets']:
  key=x['target'],x['kind'];require(key not in assets,'duplicate remote asset');assets[key]=x
 for x in local['assets']:assets['aarch64-apple-darwin',x['kind']]=x
 require(set(t for t,k in assets)==TARGETS,'all six package producers required')
 for (target,kind),row in assets.items():
  p=Path(row['download_path']);require(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'authenticated readback bytes changed')
  if 'original_path' in row:require(sha(Path(row['original_path']))==row['sha256'],'original producer payload changed')
 current=CI/'.github/final-package-candidate.json';spec=load(current)
 require(sha(current)=='0ff11aab6d5ee47f1778965074069cbcb473455e54143419368895343117f3e5' and spec['phase']=='produce' and spec['source_sha256']==SOURCE,'original reviewed native producer selector required')
 def entry(target,kind):
  row=assets[target,kind];return dict(asset_id=row['asset_id'],sha256=row['sha256'])
 spec['phase']='verify';spec['scope']='Exact final Joy dd61 six-native installed package consumption with all legacy/structured corpora and installed deadline probes; feature-branch rehearsal, no publication'
 spec['binaries']={target:entry(target,'binary') for target in sorted(TARGETS)}
 spec['corpora']=[dict(target=target,**entry(target,'corpus')) for target in sorted(TARGETS)]
 spec['structured_corpora']=[dict(target=target,**entry(target,'structured-corpus')) for target in sorted(TARGETS)]
 O.mkdir();dump(O/'proposed-final-candidate.json',spec)
 floor=load(CI/'.github/final-package-macos-floor.json');require(floor['status']=='exported-awaiting-independent-reproduction' and floor['source_sha256']==SOURCE,'original inactive Mac14 selector required')
 floor.update(status='active',selector_sha256=sha(O/'proposed-final-candidate.json'),scope='Actual macOS14 ARM installed final Joy/Trisha with all six legacy/structured corpora, accepted kit and bounded installed deadline probes; no full198 generation or Trident/LSP floor qualification')
 dump(O/'proposed-final-macos-floor.json',floor)
 cache=load(M/'local-native-asset-cache.json')
 for (target,kind),row in assets.items():
  if kind!='evidence':cache[str(row['asset_id'])]=row['download_path']
 for asset,digest in [(spec['asset_id'],SOURCE),(spec['selfhost_kit']['asset_id'],spec['selfhost_kit']['sha256']),(spec['baseline_reference']['asset_id'],spec['baseline_reference']['sha256'])]:require(sha(Path(cache[str(asset)]))==digest,'existing cache bytes differ')
 dump(O/'local-consumer-asset-cache.json',cache)
 commands=[]
 for name,cmd in [('disk',['df','-k',str(R)]),('memory',['memory_pressure']),('processes',['ps','-axo','pid,ppid,pgid,rss,pcpu,etime,command']),('host',['uname','-a'])]:
  p=subprocess.run(cmd,capture_output=True)
  for stream in ['stdout','stderr']:(O/(name+'.'+stream)).write_bytes(getattr(p,stream))
  require(p.returncode==0,'admission observation failed');commands.append(dict(command=cmd,exit_code=p.returncode))
 free=shutil.disk_usage(R).free;require(free>=8*1024**3,'existing eightGiB disk floor not available')
 receipt=dict(status='passed-proposal-only',scope='All actual producer/readback prerequisites checked; two proposed selectors remain outside checkout until independent review',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=SOURCE,remote_transport_run=37000157290,remote_assets=20,local_assets=3,full198_actual_proofs=198,fresh_full198=dict(coverage=complete['coverage'],source_sha256=complete['source_sha256'],trisha_sha256=complete['binaries']['trisha'],archive_asset_id=full['asset']['id'],archive_sha256=full['archive_sha256'],proof_receipt_sha256=sha(R/'local-macos-final-rust189/release-results/baselines/receipt.json'),historical_baseline_reference_scope='605010237 is unchanged conditional inheritance input only; final Trisha differs and its198 coverage is fresh actual final run'),full198_readback_sha256=sha(M/'local-evidence-readback/receipt.json'),remote_readback_sha256=sha(M/'remote-package-readback/receipt.json'),local_readback_sha256=sha(M/'local-package-readback/receipt.json'),source_after_sha256=sha(after/'receipt.json'),candidate_selector_sha256=sha(O/'proposed-final-candidate.json'),macos_floor_selector_sha256=sha(O/'proposed-final-macos-floor.json'),cache_sha256=sha(O/'local-consumer-asset-cache.json'),script_sha256=sha(Path(__file__)),disk_free_bytes=free,admission_commands=commands,consumer_scope='Five native remote consumers plus one actual local ARM consumer; all36 pairs/72 corpus sets/2664 cases and six23-command probes; separate macOS14 ARM consumer444cases plus23commands under original5GiB/1800s',runner_sha256=sha(CI/'scripts/native-candidate.py'))
 dump(O/'receipt.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
