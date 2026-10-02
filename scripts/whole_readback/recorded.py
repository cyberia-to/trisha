"""Replay authenticated worker API observations locally without another body transfer."""
import copy
import json
from pathlib import Path

import gate
gate.frozen()
from common import CHUNK, REPO, identity, load, require
from contracts import MIB, ident
from transport import Transport
from bounded import read_only


class Recorded(Transport):
    def __init__(self,directory,receipt,budget):
        self.directory=directory;self.original=receipt;self.receipt=copy.deepcopy(receipt);self.baseline=None;self.budget=budget;self.used=[]
        self.rows={row['name']:row for row in receipt['commands']}
        require(len(self.rows)==len(receipt['commands'])<=1000,'bounded unique worker API commands')
        require(all(a['ended_ns']<=b['started_ns'] for a,b in zip(receipt['commands'],receipt['commands'][1:])),'serial original GET command observations')

    def persist(self):pass

    def run(self,name,args,expected_exit=0,output=None,maximum=8*MIB,data=False):
        read_only(args);require(name in self.rows and name not in self.used,'exact original single command observation')
        row=self.rows[name];require(row['command']==[self.original['gh']['path'],*args] and row['expected_exit']==expected_exit and row['exit_code']==expected_exit,'exact worker GET command and exit')
        require(row['timeout_seconds']==(1800 if data else 120) and row['stdout_limit']==maximum,'exact worker per-command bounds')
        require(not any(k in row for k in ('error','cleanup_error','normal_persist_error','terminal_evidence_error')),'successful complete worker command')
        require(row['cleanup'].get('status')=='leader-complete' or row['cleanup'].get('group_empty') is True,'successful original metadata child cleanup')
        require(0<=row['elapsed_seconds']<=row['timeout_seconds']+30 and self.original['started_ns']<=row['started_ns']<=row['ended_ns']<=self.original['ended_ns'],'command timing inside complete observation')
        expected_path=output or self.directory/(name+'.stdout');require(expected_path.parent==self.directory,'owned replay path')
        require(Path(row['stdout_path']).name==expected_path.name and Path(row['stderr_path']).name==name+'.stderr','exact stdout/stderr names')
        require(identity(expected_path)==row['stdout'] and row['stdout']['bytes']<=maximum,'original stdout byte identity')
        require(identity(self.directory/(name+'.stderr'))==row['stderr'] and row['stderr']['bytes']<=8*MIB,'original stderr byte identity')
        self.used.append(name);return expected_path

    def upload(self,*args,**kwargs):raise ValueError('offline replay cannot publish')


def body_observations(directory,receipt,entries,used):
    rows={r['name']:r for r in receipt['commands']};expected_names=[]
    require(len(receipt['entries'])==2,'two actual reconstruction observations')
    for entry,got in zip(entries,receipt['entries']):
        require(got['generation']==entry['generation'] and got['proof']==got['downloaded_reconstruction']==entry['proof'] and got['status']=='ordered-whole-bytes-passed','actual complete whole identity')
        require(got['parts']==[dict(p,independently_downloaded=True) for p in entry['parts']],'exact22 independently read parts in order')
        for part in entry['parts']:
            name=f"c{entry['generation']}-part-{part['sequence']:04d}-download";expected_names.append(name);row=rows[name]
            require(row['command']==[receipt['gh']['path'],'api',f"repos/{REPO}/releases/assets/{part['asset']['id']}",'-H','Accept: application/octet-stream'],'actual canonical body request')
            require(row['expected_exit']==row['exit_code']==0 and row['stdout']==ident(part) and row['stdout_limit']==part['bytes'],'complete body length and SHA observation')
            require(row['timeout_seconds']==1800 and 0<=row['elapsed_seconds']<=1830,'body physical observation bound')
            require(receipt['started_ns']<=row['started_ns']<=row['ended_ns']<=receipt['ended_ns'],'body interval')
            require(Path(row['stdout_path']).name=='chunk' and Path(row['stderr_path']).name==name+'.stderr','bounded one-part path')
            require(identity(directory/(name+'.stderr'))==row['stderr'] and row['stderr']['bytes']<=8*MIB,'raw body stderr')
            require(not any(k in row for k in ('error','cleanup_error','normal_persist_error','terminal_evidence_error')),'no failed body read')
            require(row['cleanup'].get('status')=='leader-complete' or row['cleanup'].get('group_empty') is True,'successful body child cleanup')
    positions=[next(i for i,r in enumerate(receipt['commands']) if r['name']==n) for n in expected_names]
    require(positions==sorted(positions) and len(positions)==22,'actual22 body commands in canonical order')
    for a,b in zip(expected_names,expected_names[1:]):require(rows[a]['ended_ns']<=rows[b]['started_ns'],'serial nonoverlapping full body reads')
    return expected_names


def replay(directory,receipt,budget):
    import remote
    selected,expected,prepared=gate.frozen()
    require(receipt['schema']=='trident/remote-certificate-byte-replay/v1' and receipt['status']=='completed-byte-replay','new successful remote byte schema')
    require(0<=receipt['elapsed_monotonic_seconds']<=5400,'bounded original worker duration')
    require(receipt['local_preparation']==selected['local_preparation'] and receipt['original_local_metadata']==selected['original_metadata'],'original local byte contract')
    require(receipt['sources']==gate.sources() and receipt['source_manifest']==identity(gate.MANIFEST) and receipt['selector']==identity(gate.SELECTOR),'exact reviewed execution sources')
    for name,value in receipt['sources'].items():require(identity(directory/'worker-sources'/name)==value,'actual copied execution source')
    t=Recorded(directory,receipt,budget);t.draft('initial');entries=remote.admit(t,expected,prepared)
    require(entries==selected['remote_entries'],'original full provenance and canonical parts')
    actual={n:dict(id=v['metadata']['id'],zip=v['zip']) for n,v in t.receipt['actions_artifacts'].items()};require(actual==selected['actions_artifacts'],'same original sixZIP identities')
    bodies=body_observations(directory,receipt,entries,t.used)
    for entry in entries:
        for part in entry['parts']:t.member(f"c{entry['generation']}-part-{part['sequence']:04d}-membership",part['asset'],ident(part))
    t.draft('final');require(set(t.used)|set(bodies)==set(t.rows),'all worker API operations independently replayed')
    samples=[json.loads(line) for line in (directory/'resources.jsonl').read_text().splitlines()]
    require(samples and len(samples)<=6000 and all(a['time_ns']<=b['time_ns'] for a,b in zip(samples,samples[1:])),'ordered bounded worker resource observations')
    require(all(s['rss_bytes']==sum(p['rss_bytes'] for p in s['processes'])<=2*CHUNK for s in samples),'sampled complete process RSS observations')
    require(max(s['rss_bytes'] for s in samples)==receipt['sampled_peak_rss_bytes'] and samples[-1]==receipt['latest_sample'],'raw resource summary binding')
    require(all(receipt['started_ns']<=s['time_ns']<=receipt['ended_ns'] for s in samples),'resource samples within worker observation')
    return dict(status='passed-authenticated-remote-byte-replay',entries=entries,body_commands=bodies,worker=receipt['worker'],source_manifest=receipt['source_manifest'],receipt=identity(directory/'receipt.json'))
