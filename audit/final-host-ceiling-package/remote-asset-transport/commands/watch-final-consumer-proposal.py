"""Wait for unchanged original readback, then prepare inactive consumer proposal."""
from pathlib import Path
import datetime,hashlib,json,subprocess,time
M=Path(__file__).resolve().parent;script=M/'prepare-final-consumers.py';expected='06bd7d6e67c13ab485c5753c96514d41fa338afe80a89f72f7a8f090066c6b92'
report=dict(status='waiting-original-readback',scope='Proposal files only; no active selector writes or native launch',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),script_sha256=expected)
def save():(M/'consumer-proposal-watch.json').write_text(json.dumps(report,indent=2)+'\n')
save();start=time.monotonic()
while True:
 assert hashlib.sha256(script.read_bytes()).hexdigest()==expected,'frozen proposal helper changed'
 observed=json.loads((M/'remote-package-readback/receipt.json').read_text())
 if observed['status']=='passed':break
 if observed['status']=='failed' or time.monotonic()-start>3600:
  report.update(status='stopped',reason=observed['status']);save();raise SystemExit(1)
 time.sleep(5)
command=['python3','-B','-W','error',str(script)];report.update(status='preparing',command=command);save()
with (M/'consumer-proposal.stdout').open('xb') as out,(M/'consumer-proposal.stderr').open('xb') as err:p=subprocess.run(command,cwd=M.parent,stdout=out,stderr=err)
report.update(status='passed' if p.returncode==0 else 'failed',exit_code=p.returncode,ended=datetime.datetime.now(datetime.timezone.utc).isoformat());save();raise SystemExit(p.returncode)
