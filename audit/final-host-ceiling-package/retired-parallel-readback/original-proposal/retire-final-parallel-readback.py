"""Retire only the reviewed-unaccepted stopped auxiliary download attempt."""
from pathlib import Path
import datetime,hashlib,json,os,signal,subprocess,time
M=Path(__file__).resolve().parent;O=M/'parallel-readback-retirement';O.mkdir();ROOT=M/'remote-package-parallel-readback'
PIDS=[75562,75925,75929,75948];BIRTH={75562:'Fri Oct 2 11:29:12 2026',75925:'Fri Oct 2 11:29:17 2026',75929:'Fri Oct 2 11:29:18 2026',75948:'Fri Oct 2 11:29:18 2026'}
ENDPOINT={75925:605444976,75929:605445038,75948:605444778}
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def observe(name):
 command=['ps','-p',','.join(map(str,PIDS)),'-o','pid=,ppid=,lstart=,state=,command='];p=subprocess.run(command,capture_output=True)
 (O/(name+'.stdout')).write_bytes(p.stdout);(O/(name+'.stderr')).write_bytes(p.stderr);rows={}
 for line in p.stdout.decode().splitlines():
  a=line.strip().split(None,8);rows[int(a[0])]=dict(pid=int(a[0]),ppid=int(a[1]),birth=' '.join(a[2:7]),state=a[7],command=a[8])
 return rows,dict(command=command,exit_code=p.returncode)
def inventory():return [dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(ROOT.rglob('*')) if p.is_file()]
pause=json.loads((M/'parallel-continuation-pause.json').read_text());assert pause['root_pids']==[75562] and pause['owned_pids']==PIDS
assert sha(M/'readback-final-remote-parallel.py')=='53511836001f7519a970cc74f3a5f1acd43dff390532a803ffcc6e8ed979516e'
report=dict(status='running',scope='Explicit root-authorized retirement of only unaccepted paused parallel readback; original serial readback and all native/proof jobs untouched',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),script_sha256=sha(Path(__file__)),commands=[],signals=[],original_auxiliary_files=inventory(),reason='Independent review found proposed supervisor cannot ensure child quiescence on cap/exception; never resumed, never accepted, no retry')
def save():(O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
save();first,command=observe('before');report['commands'].append(command);assert set(first)==set(PIDS)
for pid,row in first.items():
 assert row['birth']==BIRTH[pid] and row['state'].startswith('T'),row
 if pid==75562:assert row['command'].endswith(' -B -W error measurements/readback-final-remote-parallel.py')
 else:assert row['ppid']==75562 and row['command']=='gh api -H Accept: application/octet-stream https://api.github.com/repos/cyberia-to/trisha/releases/assets/'+str(ENDPOINT[pid])
report['verified_ownership']=first;save()
for pid in [75925,75929,75948,75562]:
 observed,command=observe('before-signal-'+str(pid));report['commands'].append(command);assert observed[pid]==first[pid],observed.get(pid)
 os.kill(pid,signal.SIGKILL);report['signals'].append(dict(pid=pid,birth=BIRTH[pid],signal='SIGKILL',signal_number=int(signal.SIGKILL),at=datetime.datetime.now(datetime.timezone.utc).isoformat()));save()
for index in range(40):
 observed,command=observe('quiescence-'+str(index));report['commands'].append(command);remaining={pid:row for pid,row in observed.items() if row['birth']==BIRTH[pid]}
 if not remaining:break
 time.sleep(.5)
assert not remaining,remaining
assert inventory()==report['original_auxiliary_files'],'paused auxiliary bytes changed during retirement'
report.update(status='retired-unaccepted',actual_quiescence='All four exact owned PID/birth pairs absent; no process-group signal used',ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),retained_files=len(report['original_auxiliary_files']),retained_payload_and_metadata_bytes=sum(x['bytes'] for x in report['original_auxiliary_files']));save();print(json.dumps({k:report[k] for k in ['status','actual_quiescence','retained_files','retained_payload_and_metadata_bytes']}))
