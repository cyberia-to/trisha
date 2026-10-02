"""GET-only operations with the distinct remote observation resource profile."""
import json
import os
from pathlib import Path
import time

import gate
# Validate the frozen local helper bytes before importing their code.
gate.frozen()
from common import CHUNK, REPO, identity, load, require
from contracts import MIB
from transport import Transport
from metadata import PROFILE

SCHEMA='trident/remote-certificate-byte-replay/v1'
SCOPE='Independent remote complete-byte readback; original local attempt remains separate; proof acceptance unchanged.'


def read_only(args):
    require(args and args[0]=='api','only gh api is available')
    if len(args)>=3 and args[1:3]==['--paginate','--slurp']:
        require(len(args)==4,'only bounded GET pagination flags');endpoint=args[3]
    else:
        require(len(args)==2 or (len(args)==4 and args[2:]==['-H','Accept: application/octet-stream']),'GET-only fixed headers; no method/body/input flags')
        endpoint=args[1]
    require(endpoint=='repos/'+REPO or endpoint.startswith('repos/'+REPO+'/'),'fixed repository relative endpoint; no upload/foreign URL')
    require(all(ord(c)>=32 for c in endpoint) and '..' not in endpoint and '#' not in endpoint,'canonical GET endpoint')
    return endpoint


def process_rows(proc=Path('/proc')):
    rows=[];paths=[p for p in proc.iterdir() if p.name.isdecimal()]
    require(len(paths)<=32768,'bounded proc inventory')
    for path in paths:
        try:
            with (path/'stat').open('rb') as source:raw=source.read(4097)
        except (FileNotFoundError,ProcessLookupError):continue
        require(len(raw)<=4096 and b') ' in raw,'bounded process stat')
        fields=raw.rsplit(b') ',1)[1].split();require(len(fields)>=22,'complete process stat')
        row=dict(pid=int(path.name),ppid=int(fields[1]),pgid=int(fields[2]),rss_bytes=int(fields[21])*os.sysconf('SC_PAGE_SIZE'))
        require(row['pid']>0 and path.name==str(row['pid']) and all(v>=0 for v in row.values()),'canonical process identity and nonnegative RSS')
        rows.append(row)
    return rows


class Readback(Transport):
    def __init__(self,directory,gh,sources,check_sources):
        self.sample_tick=-1;self.peak=0;self.sampling_closed=False
        super().__init__(directory,gh,sources,check_sources)
        self.receipt.update(schema=SCHEMA,scope=SCOPE,profile=PROFILE,observer_pid=os.getpid())
        self.persist()

    def persist(self):
        require(len((json.dumps(self.receipt,indent=2)+'\n').encode())<=PROFILE['receipt_bytes'],'4MiB ordinary worker receipt cap')
        super().persist()

    def sample(self):
        if self.sampling_closed:return
        now=time.monotonic()
        if now-self.sample_tick<1:return
        rows=process_rows();selected={os.getpid()}
        while True:
            larger=selected|{r['pid'] for r in rows if r['ppid'] in selected}
            if larger==selected:break
            selected=larger
        latest=self.receipt['commands'][-1] if self.receipt['commands'] else {}
        if 'pid' in latest and 'ended_ns' not in latest:selected|={r['pid'] for r in rows if r['pgid']==latest['pid']}
        owned=[r for r in rows if r['pid'] in selected];rss=sum(r['rss_bytes'] for r in owned);self.peak=max(self.peak,rss)
        value=dict(time_ns=time.time_ns(),rss_bytes=rss,processes=owned)
        raw=json.dumps(value)+'\n';path=self.directory/'resources.jsonl'
        require((path.stat().st_size if path.exists() else 0)+len(raw.encode())<=PROFILE['resources_bytes'],'4MiB worker resource observation cap')
        super().budget(len(raw.encode()))
        with (self.directory/'resources.jsonl').open('a') as stream:stream.write(raw)
        self.receipt.update(sampled_peak_rss_bytes=self.peak,latest_sample=value);self.sample_tick=now
        require(rss<=2*CHUNK,'sampled aggregate worker and child RSS ceiling')

    def budget(self,reserve=0,chunk=False):
        require(time.monotonic()-self.tick<=5400,'90-minute remote byte-readback deadline')
        super().budget(reserve,chunk);self.sample()

    def run(self,name,args,**kwargs):
        read_only(args)
        return super().run(name,args,**kwargs)

    def upload(self,*args,**kwargs):
        raise ValueError('remote worker has no publication operation')

    def failure(self,error):
        self.receipt.update(status='failed',error=error)
        target=self.directory/'terminal-failure.json'
        if target.exists():require(load(target)['status']=='failed','immutable failed terminal');return
        row=self.receipt['commands'][-1] if self.receipt['commands'] else None
        value=dict(schema='trident/remote-byte-replay-terminal-failure/v1',status='failed',scope=SCOPE,error=error[:32768],started_ns=self.receipt['started_ns'],ended_ns=time.time_ns(),sources=self.sources,latest_command=row,partial=None)
        part=self.directory/'chunk'
        if part.exists():
            require(part.is_file() and not part.is_symlink() and part.stat().st_size<=CHUNK,'bounded owned failed part')
            value['partial']=identity(part)
        raw=(json.dumps(value,indent=2)+'\n').encode();require(len(raw)<=MIB,'reserved failure evidence bound')
        reserve=self.directory/'terminal-reserve.json';require(reserve.is_file() and not reserve.is_symlink() and reserve.stat().st_size==MIB,'owned reserved terminal bytes')
        with reserve.open('r+b') as stream:stream.write(raw+b' '*(MIB-len(raw)));stream.flush();os.fsync(stream.fileno())
        reserve.rename(target)
