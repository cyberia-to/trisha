"""Materialize and export the reviewed final closure only after explicit review."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys,traceback
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reviewed-head',required=True);args=parser.parse_args()
F=Path('/Users/master/cyber/.worktrees/selfhost-0.4-finalization-20261002');R=F/'final-distribution';CI=R/'trisha-native-ci';M=R/'measurements';OUT=M/'source-preparation';OUT.mkdir()
selected=CI/'.github/final-package-inputs.json';spec=json.loads(selected.read_text());report=dict(scope='Strict exact origin feature-branch final Joy deadline source export; no official release candidate',status='running',reviewed_head=args.reviewed_head,commands=[])
env=dict(os.environ)
for key in list(env):
 if key.startswith(('GH_','GITHUB_','TRIDENT_','GIT_CONFIG_')) or key in ('RUSTC','RUSTDOC','RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','RUSTDOCFLAGS','CARGO_ENCODED_RUSTDOCFLAGS','CARGO_TARGET_DIR','CARGO_BUILD_TARGET','CARGO_BUILD_RUSTC','CARGO_BUILD_RUSTDOC','CARGO_BUILD_RUSTC_WRAPPER','CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER','PYTHONOPTIMIZE'):env.pop(key,None)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save():(OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def run(name,command,authenticated=False):
 command=list(map(str,command));result=subprocess.run(command,env=os.environ if authenticated else env,cwd=R,capture_output=True);row=dict(name=name,command=command,exit_code=result.returncode)
 for field in ('stdout','stderr'):
  raw=getattr(result,field);p=OUT/(name+'.'+field);p.write_bytes(raw);row[field]=dict(path=p.name,bytes=len(raw),sha256=sha(p))
 report['commands'].append(row);save()
 if result.returncode:raise RuntimeError(name+' failed: '+result.stderr.decode(errors='replace')[-4000:])
 print(name,'passed',flush=True);return result.stdout.decode()
def origins(stage):
 rows={}
 for row in spec['sources']:
  text=run(stage+'-'+row['repository']+'-origin',['git','ls-remote','--heads','https://github.com/cyberia-to/'+row['repository']+'.git']);refs={line.split()[1]:line.split()[0] for line in text.splitlines()}
  if refs[row['origin_ref']]!=row['origin_head']:raise ValueError('frozen origin head moved: '+row['repository'])
  if row['commit']!=row['origin_head']:raise ValueError('this final closure requires the exact observed origin source head')
  rows[row['repository']]=refs
 return rows
save()
try:
 if run('reviewed-head',['git','-C',CI,'rev-parse','HEAD']).strip()!=args.reviewed_head:raise ValueError('reviewed runner head differs')
 if run('reviewed-status',['git','-C',CI,'status','--porcelain=v1','--untracked-files=all']).strip():raise ValueError('reviewed checkout is dirty')
 report['free_disk_bytes_before']=shutil.disk_usage(R).free
 if report['free_disk_bytes_before']<16*1024**3:raise ValueError('final source preparation needs 16 GiB free admission headroom')
 before=origins('before')
 for row in spec['sources']:
  name=row['repository'];repo=CI if name=='trisha' else F/'current-distribution'/name
  run(name+'-materialize',['git','-C',repo,'worktree','add','--detach',R/name,row['commit']])
 toolchain='1.89.0-aarch64-apple-darwin';paths={name:Path(run(name+'-path',['rustup','which','--toolchain',toolchain,name]).strip()) for name in ('rustc','cargo','rustdoc')}
 if len({p.parent for p in paths.values()})!=1:raise ValueError('native pinned toolchain paths differ')
 nu=F/'distribution/local-macos-rust189/temporary/cyber-candidate/nu/nu-0.112.2-aarch64-apple-darwin/nu'
 env.update(RUSTUP_TOOLCHAIN=toolchain,RUSTC=str(paths['rustc']),RUSTDOC=str(paths['rustdoc']),CARGO_BUILD_JOBS='2',RAYON_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1');env['PATH']=os.pathsep.join([str(paths['cargo'].parent),str(nu.parent),str(Path(sys.executable).parent),env['PATH']])
 for name,flag in (('rustc','-vV'),('cargo','-Vv'),('rustdoc','-vV')):
  actual=run(name+'-version',[paths[name],flag])
  if not actual.startswith(name+' 1.89.0 '):raise ValueError('wrong actual toolchain '+name)
  if name=='rustc' and 'host: aarch64-apple-darwin\n' not in actual:raise ValueError('wrong native host')
 if run('nu-version',[nu,'--version']).strip()!='0.112.2':raise ValueError('Nushell version differs')
 report['nu']=dict(path=str(nu),sha256=sha(nu));save()
 run('vendor',[nu,'--no-config-file',R/'trisha/patches/apply.nu'])
 closure={};repos=set()
 for name in ('trisha','joy'):
  data=json.loads(run(name+'-metadata',[paths['cargo'],'metadata','--manifest-path',R/name/'Cargo.toml','--format-version','1','--all-features','--locked']))
  packages=[]
  for package in data['packages']:
   if package['source'] is None:
    manifest=Path(package['manifest_path']).resolve().relative_to(R);repository=manifest.parts[0];repos.add(repository);packages.append(dict(name=package['name'],manifest=str(manifest),repository=repository))
  closure[name]=packages
 if repos!={row['repository'] for row in spec['sources']} or len(repos)!=11:raise ValueError('actual production closure differs')
 report['production_closure']=closure;save()
 for row in spec['sources']:
  name=row['repository']
  if run(name+'-head',['git','-C',R/name,'rev-parse','HEAD']).strip()!=row['commit']:raise ValueError('input revision differs')
  if run(name+'-status',['git','-C',R/name,'status','--porcelain=v1','--untracked-files=all']).strip():raise ValueError('input source is dirty')
 source=M/'source-export';run('export',[nu,'--no-config-file',R/'trisha/scripts/package-source.nu',source]);archive=M/'source-export.tar.gz'
 report['archive']=dict(path=str(archive),sha256=sha(archive),bytes=archive.stat().st_size);save()
 run('source-guard',[sys.executable,'-B',source/'trisha/scripts/verify-source.py',source])
 kit=F/'distribution/trisha/audit/selfhost-kit/accepted/selfhost-kit.tar.gz';run('kit-guard',[sys.executable,'-B',source/'trisha/scripts/selfhost-kit.py','unpack','--archive',kit,'--sha256','a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd','--trident',source/'trident','--output',M/'source-export-kit'])
 spec.update(source_sha256=sha(archive),source_provenance_sha256=sha(source/'sources.json'),vendor_sha256=sha(source/'vendor-sources.json'),status='exported-awaiting-independent-reproduction');selected.write_text(json.dumps(spec,indent=2)+'\n')
 run('source-impact',[sys.executable,'-B',CI/'scripts/final-source-impact.py','--source',source,'--inputs',selected,'--references',CI/'audit/final-host-ceiling-package/references','--receipt',OUT/'source-impact.json'])
 after=origins('after');report['unchanged_default_refs']={}
 for name in before:
  for ref,rev in before[name].items():
   if ref in ('refs/heads/main','refs/heads/master'):
    if after[name][ref]!=rev:raise ValueError('default ref changed during export')
    report['unchanged_default_refs'].setdefault(name,{})[ref]=rev
 report.update(status='passed',inputs_sha256=sha(selected),source_provenance_sha256=spec['source_provenance_sha256'],vendor_sha256=spec['vendor_sha256'],free_disk_bytes_after=shutil.disk_usage(R).free,ended=datetime.datetime.now(datetime.timezone.utc).isoformat());print(json.dumps(report['archive']))
except BaseException:
 report.update(status='failed',error=traceback.format_exc());raise
finally:save()
