"""Replay frozen final consumer receipts only after completed retained runs."""
from pathlib import Path
import hashlib,json,subprocess,time,datetime
M=Path(__file__).resolve().parent
HEAD='dd858356251101f285c785cb04fba1644a612fce';SELECTOR='084bfe4821114455881b1fd2718d8a10373e48562d97093ef3a580b0fb9626ba'
selected=[dict(kind='matrix',run=37003795408,artifacts=5,script='inspect-final-consumers.py',output='final-corpus-matrix'),dict(kind='macos14',run=37003795418,artifacts=1,script='inspect-final-macos-floor.py',output='final-macos-floor-inspection')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
frozen={name:sha(M/name) for name in ['inspect-final-consumers.py','inspect-final-macos-floor.py','check-final-corpus-matrix.py','inspect-final-native-producer.py']}
report=dict(status='waiting',scope='Read-only exact original consumer receipt replay after successful retained run; no native retries or selector edits',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_helpers=frozen,checks=[])
def save():(M/'consumer-checks-watch.json').write_text(json.dumps(report,indent=2)+'\n')
save()
while selected:
 for name,digest in frozen.items():assert sha(M/name)==digest,'active observer helper changed'
 for item in selected[:]:
  base=M/'native-runs'/str(item['run']);snapshots=sorted(p for p in base.iterdir() if (p/'run.json').is_file())
  if not snapshots:continue
  run=json.loads((snapshots[-1]/'run.json').read_text())
  if run['status']!='completed':continue
  if run['conclusion']!='success':report.update(status='failed',error='Native consumer run failed: '+str(item['run']));save();raise SystemExit(1)
  roots=[p for p in base.iterdir() if (p/'retention.json').is_file()]
  if len(roots)!=item['artifacts']:continue
  command=['python3','-B','-W','error',str(M/item['script']),'--run-id',str(item['run']),'--head',HEAD,'--selector-sha',SELECTOR,'--output',str(M/item['output'])]
  if item['kind']=='macos14':command+=['--artifact-id',roots[0].name]
  with (M/(item['kind']+'-final-check.stdout')).open('xb') as out,(M/(item['kind']+'-final-check.stderr')).open('xb') as err:p=subprocess.run(command,cwd=M.parent,stdout=out,stderr=err)
  report['checks'].append(dict(kind=item['kind'],command=command,exit_code=p.returncode));save()
  if p.returncode:report.update(status='failed');save();raise SystemExit(p.returncode)
  selected.remove(item)
 if selected:time.sleep(5)
report.update(status='passed',ended=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
