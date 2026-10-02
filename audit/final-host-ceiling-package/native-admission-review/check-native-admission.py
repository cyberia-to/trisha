"""Capture actual concurrent host resources immediately before final native work."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,subprocess
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args();args.output.mkdir()
report=dict(status='running',scope='Actual host admission for one final native worker; other proof processes remain untouched',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=[],caps=dict(cargo_build_jobs=2,rayon_threads=4,worker_rss_bytes=28*1024**3,full198_rss_bytes=28*1024**3,full198_host_free_percent=8),free_disk_bytes=shutil.disk_usage(args.output).free)
for name,command in [('host',['sw_vers']),('memory',['sysctl','-n','hw.memsize']),('cpus',['sysctl','-n','hw.ncpu']),('memory-pressure',['memory_pressure','-Q']),('processes',['ps','-axo','pid=,ppid=,pgid=,%cpu=,rss=,comm='])]:
 r=subprocess.run(command,capture_output=True);row=dict(name=name,command=command,exit_code=r.returncode)
 for field in ('stdout','stderr'):
  data=getattr(r,field);p=args.output/(name+'.'+field);p.write_bytes(data);row[field]=dict(path=p.name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 report['commands'].append(row)
 if r.returncode:raise RuntimeError('host admission observation failed: '+name)
free_line=next(line for line in (args.output/'memory-pressure.stdout').read_text().splitlines() if 'System-wide memory free percentage:' in line);report['memory_free_percent']=int(free_line.rsplit(':',1)[1].strip().rstrip('%'))
report['memory_bytes']=int((args.output/'memory.stdout').read_text());report['cpus']=int((args.output/'cpus.stdout').read_text())
if report['memory_free_percent']<8 or report['free_disk_bytes']<16*1024**3:report['status']='rejected'
else:report['status']='passed'
(args.output/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({key:report[key] for key in ('status','free_disk_bytes','memory_bytes','memory_free_percent','cpus')}));raise SystemExit(report['status']!='passed')
