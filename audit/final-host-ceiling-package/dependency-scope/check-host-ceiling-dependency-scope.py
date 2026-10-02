"""Read-only source and resolved-dependency impact evidence for the separate Joy ceiling follow-up."""
from pathlib import Path
import datetime,gzip,hashlib,json,os,subprocess
M=Path(__file__).resolve().parent;R=M.parent;O=M/'host-ceiling-dependency-scope';O.mkdir();candidate=json.loads((R/'local-macos-current-rust189/release-results/candidate.json').read_text());source=Path(candidate['source'])
OLD='11b7bad201cbfc03955290b5479fa6684f8e2b82';NEW='dd61df9128f6da1f97d4698f45f154f05312fe51';commands=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def run(name,args,env=None):
 r=subprocess.run(args,env=env,capture_output=True);(O/(name+'.stdout.gz')).write_bytes(gzip.compress(r.stdout,mtime=0));(O/(name+'.stderr')).write_bytes(r.stderr);commands.append(dict(name=name,command=args,exit_code=r.returncode,stdout_sha256=sha(r.stdout),stdout_bytes=len(r.stdout),stderr_sha256=sha(r.stderr)));assert r.returncode==0,(name,r.stderr);return r.stdout
raw=run('joy-diff',['git','-C',str(R/'joy'),'diff',OLD,NEW]);changed=run('joy-files',['git','-C',str(R/'joy'),'diff','--name-only',OLD,NEW]).decode().splitlines();production=[p for p in changed if p.startswith(('rs/','cli/')) and '/tests/' not in p and not p.startswith('cli/tests/')]
assert production==['rs/structured/limits.rs'],production
before=run('limits-before',['git','-C',str(R/'joy'),'show',OLD+':rs/structured/limits.rs']);after=run('limits-after',['git','-C',str(R/'joy'),'show',NEW+':rs/structured/limits.rs']);assert before.replace(b'const COMPACT_TIME_MS: u64 = 7_200_000;',b'const COMPACT_TIME_MS: u64 = 14_400_000;')==after
cargo=Path(subprocess.check_output(['rustup','which','--toolchain','1.89.0-aarch64-apple-darwin','cargo'],text=True).strip());rustc=cargo.parent/'rustc';env=dict(os.environ);env['PATH']=str(cargo.parent)+os.pathsep+env['PATH'];env['RUSTC']=str(rustc);env['RUSTUP_TOOLCHAIN']='1.89.0-aarch64-apple-darwin';env['CARGO_TARGET_DIR']=str(O/'metadata-target')
for k in ['RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','CARGO_ENCODED_RUSTFLAGS','RUSTFLAGS','CARGO_BUILD_TARGET','CARGO_BUILD_RUSTC','CARGO_BUILD_RUSTC_WRAPPER','CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER']:env.pop(k,None)
run('cargo-version',[str(cargo),'-Vv'],env);closures=[]
for project,name in [('trisha','trisha'),('trident','trident-lang')]:
 data=json.loads(run(project+'-metadata',[str(cargo),'metadata','--manifest-path',str(source/project/'Cargo.toml'),'--format-version','1','--all-features','--locked','--offline'],env));packages={p['id']:p for p in data['packages']};nodes={x['id']:x for x in data['resolve']['nodes']};root=next(p['id'] for p in packages.values() if p['name']==name and p['source'] is None);closure=set();pending=[root]
 while pending:
  id=pending.pop()
  if id in closure:continue
  closure.add(id);pending += [x['pkg'] for x in nodes[id]['deps']]
 selected=[packages[id] for id in sorted(closure)];assert not any('joy' in p['name'] for p in selected)
 local=[dict(name=p['name'],version=p['version'],manifest_path=str(Path(p['manifest_path']).relative_to(source))) for p in selected if p['source'] is None]
 closures.append(dict(project=project,root_package=name,resolved_packages=len(selected),local_packages=local,joy_in_closure=False,all_features=True,locked=True,offline=True))
report=dict(status='passed',scope='Dependency/source scope for separate dd61 Joy package planning; no new package or inherited full198 verdict established',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),prior_source_sha256='734df69dc7d43467fc9ae574c7cf7b25eb9b4ec9bc08e9ca3f96b9500131f42e',prior_provenance_sha256=candidate['provenance_sha256'],joy_before=OLD,joy_after=NEW,changed_paths=changed,changed_production_paths=production,exact_production_change='COMPACT_TIME_MS 7200000 -> 14400000; all other bytes in that production file identical',dependency_closures=closures,commands=commands,script_sha256=sha(Path(__file__).read_bytes()))
(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status='passed',closures=closures),indent=2))
