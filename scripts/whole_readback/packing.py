"""Bounded metadata ZIP with separate final packing resource observations."""
import json
import os
from pathlib import Path
import shutil
import time
import zipfile

from common import identity, require
from contracts import MIB
from bounded import process_rows


class CappedFile:
    def __init__(self,stream,limit,budget):self.stream=stream;self.limit=limit;self.budget=budget
    def write(self,data):
        require(self.stream.tell()+len(data)<=self.limit,'compressed evidence ZIP cap')
        self.budget(len(data));return self.stream.write(data)
    def seek(self,*args):return self.stream.seek(*args)
    def tell(self):return self.stream.tell()
    def flush(self):return self.stream.flush()


def pack(transport,artifact):
    directory=transport.directory;transport.sample()
    expanded={f'whole-v2-{phase}-c{g}-1' for phase in ('producer','verifier','pending') for g in (1,2)}
    # Retain original authenticated ZIPs; duplicate decoded directories are replayed locally.
    files={str(p.relative_to(directory)):identity(p) for p in sorted(directory.rglob('*')) if p.is_file() and p!=directory/'chunk' and p.relative_to(directory).parts[0] not in expanded}
    require(len(files)<=10000 and sum(v['bytes'] for v in files.values())<=512*MIB,'bounded metadata membership')
    require('receipt.json' in files and not any(n=='chunk' or n.endswith('.joysc') for n in files),'no complete or partial proof bodies')
    manifest=directory/'evidence-files.json'
    raw=(json.dumps(files,indent=2)+'\n').encode();transport.budget(len(raw))
    with manifest.open('xb') as stream:stream.write(raw)
    files['evidence-files.json']=identity(manifest)
    base_bytes=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and p!=directory/'chunk')
    artifact.parent.mkdir(exist_ok=False)
    observations=[];sample_tick=-1;peak=0;started=time.time_ns()
    def budget(reserve=0):
        nonlocal sample_tick,peak
        require(time.monotonic()-transport.tick<=5400,'90-minute deadline includes packing')
        size=artifact.stat().st_size if artifact.exists() else 0
        require(base_bytes+size+reserve+MIB<=512*MIB,'metadata plus compressed artifact sidecar cap')
        require(shutil.disk_usage(directory).free>=8*1024**3+reserve,'packing free-space floor')
        now=time.monotonic()
        if now-sample_tick>=1:
            rows=[r for r in process_rows() if r['pid']==os.getpid()];require(len(rows)==1,'actual packing process')
            rss=rows[0]['rss_bytes'];peak=max(peak,rss);require(peak<=2*1024**3,'packing sampled RSS ceiling')
            require(len(observations)<6000,'bounded packing samples');observations.append(dict(time_ns=time.time_ns(),rss_bytes=rss,processes=rows));sample_tick=now
    with artifact.open('xb') as raw:
        capped=CappedFile(raw,250*MIB,budget)
        with zipfile.ZipFile(capped,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=False) as archive:
            for name,wanted in files.items():
                source=directory/name;require(identity(source)==wanted,'stable metadata before packing')
                archive.write(source,name);require(identity(source)==wanted,'stable metadata after packing')
    sample_tick=-1;budget()
    result=dict(schema='trident/remote-byte-replay-packing/v1',status='passed',archive=identity(artifact),members=files,started_ns=started,ended_ns=time.time_ns(),elapsed_total_monotonic_seconds=time.monotonic()-transport.tick,sampled_peak_rss_bytes=peak,samples=observations,scope='metadata only; failed proof-part bytes are excluded')
    raw=(json.dumps(result,indent=2)+'\n').encode();require(len(raw)<=MIB,'reserved packing receipt cap')
    with (artifact.parent/'packing.json').open('xb') as stream:stream.write(raw)
    require(sum(p.stat().st_size for p in artifact.parent.iterdir())<=251*MIB,'final original Actions payload bound below256MiB')
    return result
