"""Export the reviewed current closure only after the original matrix passes."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,os,subprocess,sys,traceback
F=Path('/Users/master/cyber/.worktrees/selfhost-0.4-finalization-20261002');R=F/'current-distribution';CI=R/'trisha-native-ci';M=R/'measurements';OUT=M/'source-export-command';OUT.mkdir()
selected=CI/'.github/current-package-inputs.json';spec=json.loads(selected.read_text());report=dict(scope='Strict committed current-production branch source export, not a default-branch release candidate',status='running',commands=[])
env=dict(os.environ)
for key in list(env):
 if key.startswith(('GH_','GITHUB_','TRIDENT_','GIT_CONFIG_')) or key in ('RUSTC','RUSTDOC','RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','RUSTDOCFLAGS','CARGO_ENCODED_RUSTDOCFLAGS','CARGO_TARGET_DIR','CARGO_BUILD_TARGET','CARGO_BUILD_RUSTC','CARGO_BUILD_RUSTDOC','CARGO_BUILD_RUSTC_WRAPPER','CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER','PYTHONOPTIMIZE'):env.pop(key,None)
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save():(OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def run(name,args,authenticated=False):
 result=subprocess.run(list(map(str,args)),env=os.environ if authenticated else env,cwd=R,capture_output=True);row=dict(name=name,command=list(map(str,args)),exit_code=result.returncode)
 for field in ['stdout','stderr']:
  data=getattr(result,field);p=OUT/(name+'.'+field);p.write_bytes(data);row[field]=dict(path=p.name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 report['commands'].append(row);save()
 if result.returncode:raise RuntimeError(name+' failed: '+result.stderr.decode(errors='replace')[-4000:])
 print(name,'passed',flush=True);return result.stdout.decode()
save()
try:
 raw=run('frozen-run',['gh','api','repos/cyberia-to/trisha/actions/runs/36949324686'],True);observed=json.loads(raw)
 if observed['head_sha']!='c94da47247457f9e819c2682e74d34f5f1756f62' or observed['status']!='completed' or observed['conclusion']!='success':raise RuntimeError('original frozen native matrix must pass before export')
 reference=CI/'audit/current-native-package/references/frozen-run.json'
 with reference.open('x') as stream:stream.write(raw)
 producer_api=json.loads(run('frozen-artifacts',['gh','api','repos/cyberia-to/trisha/actions/runs/36949324686/artifacts?per_page=100'],True))
 helper_spec=importlib.util.spec_from_file_location('frozen_inspector',F/'distribution/measurements/inspect-native-producer.py');helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
 inspections=[]
 for item in producer_api['artifacts']:
  if item['name'].startswith('candidate-'):
   inspected=helper.inspect(F/'distribution/measurements/native-runs/36949324686'/str(item['id']))
   assert item['digest']=='sha256:'+inspected['artifact_sha256'];inspections.append(inspected)
 guard_spec=importlib.util.spec_from_file_location('current_impact',CI/'scripts/current-source-impact.py');guard=importlib.util.module_from_spec(guard_spec);guard_spec.loader.exec_module(guard);guard.original_producers(inspections)
 with (reference.parent/'frozen-producers.json').open('x') as stream:stream.write(json.dumps(inspections,indent=2)+'\n')
 for row in spec['sources']:
  name=row['repository'];assert run(name+'-head',['git','-C',R/name,'rev-parse','HEAD']).strip()==row['commit']
  assert not run(name+'-status',['git','-C',R/name,'status','--porcelain=v1','--untracked-files=all']).strip()
  refs={ref:rev for rev,ref in (line.split() for line in run(name+'-origin',['git','-C',R/name,'ls-remote','--heads','origin']).splitlines())}
  head=refs[row['origin_ref']]
  comparison=json.loads(run(name+'-reachability',['gh','api','repos/cyberia-to/'+name+'/compare/'+row['commit']+'...'+head],True))
  assert comparison['status'] in ('identical','ahead') and comparison['merge_base_commit']['sha']==row['commit']
  row['origin_head']=head
 toolchain='1.89.0-aarch64-apple-darwin';paths={name:Path(run(name+'-path',['rustup','which','--toolchain',toolchain,name]).strip()) for name in ['rustc','cargo','rustdoc']};assert len({p.parent for p in paths.values()})==1
 nu=F/'distribution/local-macos-rust189/temporary/cyber-candidate/nu/nu-0.112.2-aarch64-apple-darwin/nu'
 env.update(RUSTUP_TOOLCHAIN=toolchain,RUSTC=str(paths['rustc']),RUSTDOC=str(paths['rustdoc']),CARGO_BUILD_JOBS='2',RAYON_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
 env['PATH']=os.pathsep.join([str(paths['cargo'].parent),str(nu.parent),str(Path(sys.executable).parent),env['PATH']])
 for name,flag in [('rustc','-vV'),('cargo','-Vv'),('rustdoc','-vV')]:
  actual=run(name+'-version',[paths[name],flag]);assert actual.startswith(name+' 1.89.0 ')
  if name=='rustc':assert 'host: aarch64-apple-darwin\n' in actual
 assert run('nu-version',[nu,'--version']).strip()=='0.112.2'
 source=M/'source-export';run('export',[nu,'--no-config-file',R/'trisha/scripts/package-source.nu',source])
 archive=M/'source-export.tar.gz';digest=sha(archive);report['archive']=dict(path=str(archive),sha256=digest,bytes=archive.stat().st_size);save()
 run('source-guard',[sys.executable,'-B',source/'trisha/scripts/verify-source.py',source])
 kit=F/'distribution/trisha/audit/selfhost-kit/accepted/selfhost-kit.tar.gz'
 run('kit-guard',[sys.executable,'-B',source/'trisha/scripts/selfhost-kit.py','unpack','--archive',kit,'--sha256','a3052d95c3de6d622157988a8e74826b2f0140724a634298458c3d75f6b508bd','--trident',source/'trident','--output',M/'source-export-kit'])
 spec.update(source_sha256=digest,source_provenance_sha256=sha(source/'sources.json'),vendor_sha256=sha(source/'vendor-sources.json'),status='exported-awaiting-independent-reproduction')
 spec['inherited_compiler_cpu']['status']='original-matrix-passed'
 selected.write_text(json.dumps(spec,indent=2)+'\n')
 run('source-impact',[sys.executable,'-B',CI/'scripts/current-source-impact.py','--source',source,'--inputs',selected,'--references',CI/'audit/current-native-package/references','--receipt',OUT/'source-impact.json'])
 report.update(status='passed',inputs_sha256=sha(selected),source_provenance_sha256=spec['source_provenance_sha256'],vendor_sha256=spec['vendor_sha256'],ended=datetime.datetime.now(datetime.timezone.utc).isoformat());print(json.dumps(report['archive'],indent=2))
except BaseException:
 report.update(status='failed',error=traceback.format_exc());raise
finally:save()
