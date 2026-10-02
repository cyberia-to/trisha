"""Reviewable budget supervisor for only the paused disjoint readback attempt."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,signal,subprocess,time
M=Path(__file__).resolve().parent;ROOT=M/'remote-package-parallel-readback'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
 return {int(a[0]):(int(a[1]),a[2]) for line in subprocess.check_output(['ps','-axo','pid=,ppid=,command='],text=True).splitlines() if len(a:=line.strip().split(None,2))==3}
def main():
 plan=json.loads((M/'parallel-continuation-plan.json').read_text());pause=json.loads((M/'parallel-continuation-pause.json').read_text());root=pause['root_pids'][0]
 assert sha(M/'readback-final-remote-parallel.py')==plan['parallel_script_sha256']
 rows=snapshot();assert root in rows and rows[root][1].endswith(' -B -W error measurements/readback-final-remote-parallel.py')
 for pid in pause['owned_pids']:assert pid in rows and (pid==root or rows[pid][0]==root)
 report=dict(status='running',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='New disjoint parallel readback only. Original serial attempt untouched.',plan_sha256=sha(M/'parallel-continuation-plan.json'),script_sha256=sha(Path(__file__)),root_pid=root,guard_stop=None,peak_owned_bytes=0,minimum_disk_free_bytes=shutil.disk_usage(M).free)
 def save():(M/'parallel-readback-guard.json').write_text(json.dumps(report,indent=2)+'\n')
 save();start=time.monotonic()
 for pid in pause['owned_pids']:os.kill(pid,signal.SIGCONT)
 while root in (rows:=snapshot()):
  sizes={str(p.relative_to(ROOT)):p.stat().st_size for p in ROOT.rglob('*') if p.is_file()};owned=sum(sizes.values());free=shutil.disk_usage(M).free;elapsed=time.monotonic()-start
  report['peak_owned_bytes']=max(report['peak_owned_bytes'],owned);report['minimum_disk_free_bytes']=min(report['minimum_disk_free_bytes'],free)
  reason=None
  if owned>plan['total_owned_byte_cap']:reason='owned-byte-cap'
  elif free<plan['disk_free_floor_bytes']:reason='disk-free-floor'
  elif elapsed>plan['wall_seconds_cap']:reason='wall-cap'
  else:
   for x in plan['parallel_assignments']:
    if sizes.get(x['relative_destination'],0)>x['bytes']:reason='asset-byte-cap:'+x['relative_destination'];break
  if reason:
   ids={root}
   while True:
    new=ids|{pid for pid,(ppid,cmd) in rows.items() if ppid in ids}
    if new==ids:break
    ids=new
   for pid in sorted(ids-{root}):
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
   time.sleep(2)
   if root in snapshot():os.kill(root,signal.SIGTERM)
   report.update(status='stopped',guard_stop=reason,owned_stopped_pids=sorted(ids));save();raise RuntimeError(reason)
  save();time.sleep(1)
 completed=json.loads((ROOT/'receipt.json').read_text());assert completed['status']=='passed' and len(completed['assets'])==20
 report.update(status='passed',elapsed_seconds=time.monotonic()-start,ended=datetime.datetime.now(datetime.timezone.utc).isoformat(),receipt_sha256=sha(ROOT/'receipt.json'));save()
if __name__=='__main__':main()
