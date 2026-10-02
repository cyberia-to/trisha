"""Offline no-signal fault probes of the frozen, unused readback supervisor."""
from pathlib import Path
import hashlib,importlib.util,json,signal,tempfile,unittest.mock as mock
R=Path(__file__).resolve().parents[1];M=R/'measurements';S=M/'guard-final-parallel-readback.py'
spec=importlib.util.spec_from_file_location('guard_under_review',S);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
identity=lambda p:dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
results=[]
for scenario in ('term_ignoring_descendant','snapshot_error_after_resume'):
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);body=root/'remote-package-parallel-readback';body.mkdir();(body/'receipt.json').write_text('{"status":"running"}')
  script=root/'readback-final-remote-parallel.py';script.write_bytes((M/script.name).read_bytes())
  plan=dict(parallel_script_sha256=identity(script)['sha256'],total_owned_byte_cap=0,disk_free_floor_bytes=0,wall_seconds_cap=2700,parallel_assignments=[])
  (root/'parallel-continuation-plan.json').write_text(json.dumps(plan));(root/'parallel-continuation-pause.json').write_text(json.dumps(dict(root_pids=[100],owned_pids=[100,101])))
  rows={100:(1,'python3 -B -W error measurements/readback-final-remote-parallel.py'),101:(100,'gh api')};signals=[];snapshots=[]
  def snapshot():
   snapshots.append(dict(rows))
   if scenario=='snapshot_error_after_resume' and len(snapshots)>1:raise RuntimeError('injected snapshot failure')
   return dict(rows)
  with mock.patch.object(g,'M',root),mock.patch.object(g,'ROOT',body),mock.patch.object(g,'snapshot',snapshot),mock.patch.object(g.os,'kill',side_effect=lambda pid,sig:signals.append([pid,int(sig)])),mock.patch.object(g.time,'sleep',return_value=None):
   try:g.main()
   except BaseException as exc:error=type(exc).__name__+': '+str(exc)
   else:raise AssertionError('expected fault refusal')
  receipt=json.loads((root/'parallel-readback-guard.json').read_text())
  if scenario=='term_ignoring_descendant':
   assert receipt['status']=='stopped' and receipt['guard_stop']=='owned-byte-cap'
   assert [101,int(signal.SIGTERM)] in signals and all(sig!=int(signal.SIGKILL) for _,sig in signals)
   assert 101 in rows
  else:
   assert receipt['status']=='running' and 'error' not in receipt
   assert all(sig==int(signal.SIGCONT) for _,sig in signals)
  results.append(dict(scenario=scenario,error=error,guard_receipt=receipt,simulated_signals=signals,still_live_simulated_pids=sorted(rows),snapshot_count=len(snapshots)))
print(json.dumps(dict(scope='Synthetic isolated temporary files; all signal calls mocked; no real processes or network touched',source=identity(S),probes=results),indent=2))
