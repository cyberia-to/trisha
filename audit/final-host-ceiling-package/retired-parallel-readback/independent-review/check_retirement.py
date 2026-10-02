from pathlib import Path
import hashlib,json,subprocess,time
O=Path(__file__).resolve().parent;M=O.parent/'measurements';D=M/'parallel-readback-retirement';P=M/'remote-package-parallel-readback'
def identity(p):
 with p.open('rb') as f:d=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),bytes=p.stat().st_size,sha256=d)
def parse(data):
 out={}
 for line in data.decode().splitlines():
  a=line.strip().split(None,8);out[int(a[0])]=dict(pid=int(a[0]),ppid=int(a[1]),birth=' '.join(a[2:7]),state=a[7],command=a[8])
 return out
j=json.loads((D/'receipt.json').read_text());pause=json.loads((M/'parallel-continuation-pause.json').read_text());assert j['status']=='retired-unaccepted';assert identity(M/'retire-final-parallel-readback.py')['sha256']==j['script_sha256']
expected=[75925,75929,75948,75562];assert [r['pid'] for r in j['signals']]==expected and all(r['signal_number']==9 and r['signal']=='SIGKILL' for r in j['signals'])
first=parse((D/'before.stdout').read_bytes());assert set(first)==set(pause['owned_pids'])
assert {str(k):v for k,v in first.items()}==j['verified_ownership']
for x in j['signals']:
 pid=x['pid'];before=parse((D/('before-signal-'+str(pid)+'.stdout')).read_bytes());assert before[pid]==first[pid] and x['birth']==first[pid]['birth'] and first[pid]['state'].startswith('T')
 assert pid==75562 or first[pid]['ppid']==75562
assert (D/'quiescence-0.stdout').read_bytes()==b'' and j['commands'][-1]['exit_code']==1
records=j['original_auxiliary_files'];assert len({r['path'] for r in records})==len(records)==37
assert {p.relative_to(P).as_posix() for p in P.rglob('*') if p.is_file()}=={r['path'] for r in records}
for r in records:
 p=P/r['path'];assert not p.is_symlink() and p.resolve().is_relative_to(P.resolve());actual=identity(p);assert actual['bytes']==r['bytes'] and actual['sha256']==r['sha256']
assert sum(r['bytes'] for r in records)==j['retained_payload_and_metadata_bytes']==60467568
ret=O/'retirement-originals';ret.mkdir();copies=[]
for p in sorted(D.iterdir()):
 if p.is_file():
  q=ret/p.name;q.write_bytes(p.read_bytes());assert identity(q)['sha256']==identity(p)['sha256'];copies.append(dict(original=identity(p),copy=identity(q)))
command=['/bin/ps','-p',','.join(map(str,pause['owned_pids'])),'-o','pid=,ppid=,lstart=,state=,command='];proc=subprocess.run(command,capture_output=True);(O/'retirement-current-ps.stdout').write_bytes(proc.stdout);(O/'retirement-current-ps.stderr').write_bytes(proc.stderr)
current=parse(proc.stdout);assert all(pid not in current or current[pid]['birth']!=r['birth'] for pid,r in first.items())
r=dict(status='passed-retirement-read-only-replay',observed_unix_ns=time.time_ns(),original_receipt=identity(D/'receipt.json'),retirement_source=identity(M/'retire-final-parallel-readback.py'),original_files_rehashed=37,original_bytes_rehashed=60467568,signals_exact_pids=expected,copies=copies,current_command=dict(argv=command,exit_code=proc.returncode,stdout=identity(O/'retirement-current-ps.stdout'),stderr=identity(O/'retirement-current-ps.stderr')),scope='Receipt/source/raw per-PID snapshots and original auxiliary files replayed; exact four retired identities absent in fresh read-only ps observation. No signals/network/retry performed. Original serial source and its live outputs not edited or copied as terminal.')
(O/'retirement-review.json').write_text(json.dumps(r,indent=2)+'\n');print(identity(O/'retirement-review.json'))
