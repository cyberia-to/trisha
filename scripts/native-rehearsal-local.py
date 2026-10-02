"""Execute the committed native bootstrap on the actual Mac ARM host."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,signal,subprocess,time
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--family',type=Path,required=True)
parser.add_argument('--output-name',default='local-macos-rust189')
parser.add_argument('--cache',type=Path,help='Exact local asset-id to archive-path mapping; hashes still come from selector')
args=parser.parse_args()
if Path(args.output_name).name!=args.output_name or args.output_name in ('','.','..'):raise ValueError('output name must be a fresh direct child')
ROOT=args.family.resolve()
CHECKOUT=Path(__file__).resolve().parent.parent
WORK=ROOT/args.output_name
WORK.mkdir();(WORK/'.github').mkdir();(WORK/'scripts').mkdir();(WORK/'temporary').mkdir()
selector=json.loads((CHECKOUT/'.github/release-candidate.json').read_text())
selector['full_baselines']=True
selector['targets']=['aarch64-apple-darwin']
(WORK/'.github/release-candidate.json').write_text(json.dumps(selector,indent=2)+'\n')
shutil.copyfile(CHECKOUT/'scripts/native-candidate.py',WORK/'scripts/native-candidate.py')
shutil.copyfile(CHECKOUT/'scripts/native-rehearsal-local-transport.py',WORK/'local-transport.py')
if args.cache:
 shutil.copyfile(args.cache.resolve(),WORK/'asset-cache.json')
if selector.get('validation_profile')=='current-package-v1':
 shutil.copyfile(CHECKOUT/'.github/current-package-inputs.json',WORK/'.github/current-package-inputs.json')
 for name in ('current-source-impact.py','current-structured-corpus.py'):
  shutil.copyfile(CHECKOUT/'scripts'/name,WORK/'scripts'/name)
 shutil.copytree(CHECKOUT/'audit/current-native-package/references',WORK/'audit/current-native-package/references')
env=dict(os.environ,RELEASE_TARGET='aarch64-apple-darwin',RUNNER_TEMP=str(WORK/'temporary'),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
for key in ('RUSTC','RUSTDOC','RUSTDOCFLAGS','CARGO_ENCODED_RUSTDOCFLAGS','RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','CARGO_BUILD_TARGET','CARGO_BUILD_RUSTC','CARGO_BUILD_RUSTDOC','CARGO_BUILD_RUSTC_WRAPPER','CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER','CARGO_TARGET_DIR','TRIDENT_STDLIB','TRIDENT_OSLIB','TRIDENT_EXTLIB','TRIDENT_TARGET_PACKAGES','PYTHONOPTIMIZE'):env.pop(key,None)
env['GITHUB_SHA']=subprocess.check_output(['git','-C',str(CHECKOUT),'rev-parse','HEAD'],text=True).strip()
toolchain='1.89.0-aarch64-apple-darwin'
rustc=Path(subprocess.check_output(['rustup','which','--toolchain',toolchain,'rustc'],text=True).strip())
cargo=Path(subprocess.check_output(['rustup','which','--toolchain',toolchain,'cargo'],text=True).strip())
rustdoc=Path(subprocess.check_output(['rustup','which','--toolchain',toolchain,'rustdoc'],text=True).strip())
if len({rustc.parent,cargo.parent,rustdoc.parent})!=1:raise ValueError('pinned Rust tools must share the selected toolchain')
env['PATH']=str(rustc.parent)+os.pathsep+env['PATH']
env['RUSTC']=str(rustc);env['RUSTDOC']=str(rustdoc);env['RUSTUP_TOOLCHAIN']=toolchain
preflight=[]
for name,path in [('rustc',rustc),('cargo',cargo),('rustdoc',rustdoc)]:
 resolved=Path(shutil.which(name,path=env['PATH'])).resolve()
 if resolved!=path.resolve():raise ValueError('PATH selected a different '+name)
 command=[str(path),'-Vv' if name=='cargo' else '-vV']
 result=subprocess.run(command,env=env,capture_output=True,text=True)
 if result.returncode or not result.stdout.startswith(name+' 1.89.0 '):raise ValueError('actual '+name+' is not pinned 1.89.0')
 if name=='rustc' and 'host: aarch64-apple-darwin\n' not in result.stdout:raise ValueError('Rust toolchain is not native Mac ARM')
 (WORK/(name+'-preflight.stdout')).write_text(result.stdout)
 (WORK/(name+'-preflight.stderr')).write_text(result.stderr)
 with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
 preflight.append(dict(command=command,resolved=str(resolved),sha256=digest,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
(WORK/'toolchain-preflight.json').write_text(json.dumps(dict(expected='1.89.0',tools=preflight,PATH=env['PATH'],RUSTC=env['RUSTC']),indent=2)+'\n')
def identity(path):
 with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(bytes=path.stat().st_size,sha256=digest)
report=dict(schema='local/native-distribution-macos/v1',scope='Actual native Mac ARM feature-branch rehearsal; no default-branch release/tag/publication',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='running',bootstrap_revision=env['GITHUB_SHA'],bootstrap=identity(WORK/'scripts/native-candidate.py'),selector=selector,command=['python3','-B','local-transport.py'],transport_adapter=identity(WORK/'local-transport.py'),cwd=str(WORK),peak_process_group_rss_bytes=0,resource_guard_bytes=28*1024**3)
def save():(WORK/'driver.json').write_text(json.dumps(report,indent=2)+'\n')
save();started=time.monotonic();stopped=False
with (WORK/'driver.stdout').open('xb') as out,(WORK/'driver.stderr').open('xb') as err,(WORK/'resources.jsonl').open('x') as resources:
 child=subprocess.Popen(report['command'],cwd=WORK,env=env,stdout=out,stderr=err,start_new_session=True)
 report['pid']=child.pid;save()
 while child.poll() is None:
  rows=subprocess.check_output(['/bin/ps','-axo','pid,pgid,rss'],text=True).splitlines()[1:]
  rss=sum(int(v[2])*1024 for line in rows if len(v:=line.split())==3 and int(v[1])==child.pid)
  report['peak_process_group_rss_bytes']=max(report['peak_process_group_rss_bytes'],rss)
  resources.write(json.dumps(dict(elapsed_seconds=time.monotonic()-started,rss_bytes=rss,peak_rss_bytes=report['peak_process_group_rss_bytes']))+'\n');resources.flush();save()
  if rss>report['resource_guard_bytes']:
   stopped=True;os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
   break
  time.sleep(5)
 report.update(exit_code=child.wait(),resource_stopped=stopped)
report.update(status='passed' if report['exit_code']==0 and not stopped else 'failed',ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started)
for name in ('driver.stdout','driver.stderr','resources.jsonl'):report[name]=identity(WORK/name)
save();print(json.dumps({k:report[k] for k in ('status','exit_code','peak_process_group_rss_bytes','elapsed_seconds')},indent=2),flush=True)
raise SystemExit(report['exit_code'] or int(stopped))
