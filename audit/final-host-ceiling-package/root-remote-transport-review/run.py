import hashlib,json,subprocess,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FM=ROOT.parent
WT=FM.parent/'trisha-native-ci'
PY='/opt/homebrew/opt/python@3.14/bin/python3.14'
HEAD='5de26a93eb4d489d90f150882adec2c47d14bea4'
def ident(p):
 with p.open('rb') as f:return dict(bytes=p.stat().st_size,sha256=hashlib.file_digest(f,'sha256').hexdigest())
def command(name,argv,cwd=WT,allow404=False):
 result=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=120)
 for stream in ('stdout','stderr'):(ROOT/(name+'.'+stream)).write_bytes(getattr(result,stream))
 report['commands'].append(dict(name=name,argv=argv,cwd=str(cwd),exit_code=result.returncode))
 if allow404:assert result.returncode==1 and str(json.loads(result.stdout).get('status'))=='404'
 else:assert result.returncode==0,(name,result.stderr.decode(errors='replace'))
 return result.stdout
report=dict(status='running',started_ns=time.time_ns(),scope='Root review of exact final remote transport selector only; no consumer activation or release publication',commands=[])
try:
 selector=FM/'proposed-final-assets.json';assert ident(selector)['sha256']=='81b1f1febf9c59d4beebf0c827d67541c106b7675c5c4ae8a75433e10de6b4e3'
 before=json.loads((WT/'.github/final-package-assets.json').read_text());spec=json.loads(selector.read_text())
 assert {k for k in set(before)|set(spec) if before.get(k)!=spec.get(k)}=={'status','producers'}
 assert spec['status']=='active' and len(spec['producers'])==5 and len({p['target'] for p in spec['producers']})==5
 for path in ['scripts/transport-native-rehearsal.py','.github/workflows/final-package-assets.yml']:
  assert command('source-'+Path(path).name,['git','show',HEAD+':'+path])==(WT/path).read_bytes()
 run=json.loads(command('run',['gh','api','repos/cyberia-to/trisha/actions/runs/36990413939']))
 assert run['head_sha']==HEAD and run['status']=='completed' and run['conclusion']=='success'
 draft=json.loads(command('draft',['gh','api','repos/cyberia-to/trisha/releases/389977897']))
 assert draft['draft'] is True and draft['tag_name']==spec['release_tag']
 command('tag',['gh','api','repos/cyberia-to/trisha/git/ref/tags/'+spec['release_tag']],allow404=True)
 assert not any(a['name'].startswith(spec['asset_prefix']+'-') for a in draft['assets'])
 reviewed=[]
 for row in spec['producers']:
  assert row['run_id']==36990413939 and row['head_sha']==HEAD
  source=FM/'native-runs/36990413939'/str(row['artifact_id']);out=ROOT/(row['target']+'.json')
  command(row['target'],[PY,'-B','-W','error',str(FM/'inspect-final-native-producer.py'),str(source),str(out),'--run-id','36990413939','--head',HEAD])
  actual=json.loads(out.read_text());assert actual['target']==row['target'] and actual['artifact_sha256']==row['zip_sha256']
  reviewed.append(dict(target=row['target'],receipt=ident(out),artifact=ident(source/'artifact.zip')))
 report.update(status='passed-transport-selector-review',selector=ident(selector),producer_reviews=reviewed,inspector=ident(FM/'inspect-final-native-producer.py'),source_guard='transport source and workflow unchanged from actual producer runner revision',authorization='Activate exact reviewed selector only; preserve existing unique draft, no tag or publication; all transport bodies require authenticated readback before consumer selector review.')
except BaseException:
 report.update(status='failed',error=traceback.format_exc());raise
finally:
 report['ended_ns']=time.time_ns();report['script']=ident(Path(__file__));(ROOT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status=report['status'],receipt=ident(ROOT/'receipt.json'))))
