from pathlib import Path
import datetime,hashlib,json,subprocess,traceback
M=Path(__file__).resolve().parent;R=M.parent;O=M/'local-evidence-transport';O.mkdir();report=dict(scope='Exact frozen completed Mac native/198 evidence to existing unpublished draft; no tag/publication',status='running',commands=[])
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save():(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
def command(name,argv,allowed=(0,)):
 row=dict(name=name,command=list(map(str,argv)));result=subprocess.run(row['command'],capture_output=True);row['exit_code']=result.returncode
 for field in ['stdout','stderr']:
  p=O/(name+'.'+field);p.write_bytes(getattr(result,field));row[field]=dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p))
 report['commands'].append(row);save()
 if result.returncode not in allowed:raise RuntimeError(name+' failed')
 return result.stdout.decode()
def draft(name):
 d=json.loads(command(name,['gh','api','repos/cyberia-to/trisha/releases/389977897']));assert d['draft'] is True and d['tag_name']=='candidate-20260916.1'
 absent=json.loads(command(name+'-tag',['gh','api','repos/cyberia-to/trisha/git/ref/tags/candidate-20260916.1'],allowed=(1,)));assert str(absent['status'])=='404';return d
def origins(stage):
 p=M/('check-origin-'+stage+'-evidence.py');code=(M/'check-origin-after-packages.py').read_text().replace('after-package-origin',stage+'-evidence-origin').replace('immediately after package draft upload','immediately '+stage+' completed local evidence draft upload');p.write_text(code);command(stage+'-origin',['python3','-B',p])
save()
try:
 retained=json.loads((M/'local-rust189-complete/receipt.json').read_text());assert retained['status']=='passed' and retained['proof_gate']['fresh_verified_proofs']==198
 archive=M/'local-rust189-complete'/retained['archive']['path'];assert sha(archive)==retained['archive']['sha256'] and archive.stat().st_size==retained['archive']['bytes']
 for row in retained['files']:
  p=R/'local-macos-rust189'/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
 report.update(retention_sha256=sha(M/'local-rust189-complete/receipt.json'),archive=retained['archive']);save();origins('before')
 before=draft('draft-before');assert archive.name not in {a['name'] for a in before['assets']}
 argv=['gh','release','upload','candidate-20260916.1',str(archive),'--repo','cyberia-to/trisha'];report.update(upload_command=argv,started=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
 with (O/'upload.stdout').open('xb') as out,(O/'upload.stderr').open('xb') as err:result=subprocess.run(argv,stdout=out,stderr=err)
 report['upload_exit_code']=result.returncode;save();assert result.returncode==0
 after=draft('draft-after');asset=next(a for a in after['assets'] if a['name']==archive.name);assert asset.get('digest')=='sha256:'+sha(archive) and asset['size']==archive.stat().st_size
 report['asset']=asset;save();origins('after')
 defaults={}
 for row in json.loads((M/'before-evidence-origin/receipt.json').read_text())['inputs']:
  name=row['repository'];states=[]
  for stage in ['before','after']:
   refs=dict((ref,rev) for rev,ref in (line.split() for line in (M/(stage+'-evidence-origin')/name/'heads.stdout').read_text().splitlines()));states.append({k:v for k,v in refs.items() if k in ('refs/heads/master','refs/heads/main')})
  assert states[0]==states[1];defaults[name]=states[0]
 report.update(status='passed',unchanged_default_refs=defaults,ended=datetime.datetime.now(datetime.timezone.utc).isoformat());print(json.dumps(dict(status=report['status'],asset_id=asset['id'],sha256=sha(archive)),indent=2))
except BaseException:
 report.update(status='failed',error=traceback.format_exc());raise
finally:save()
