"""Authenticate the one new Actions observation and replay its original evidence."""
import json
from pathlib import Path
import stat
import zipfile

import gate
gate.frozen()
from common import REPO, identity, load, require
from contracts import MIB
from archives import extract_zip, zip_preflight
from recorded import replay


def coordinates(value,run,head):
    selected=gate.load(gate.SELECTOR)
    require(value['id']==run and value['run_attempt']==1 and value['head_sha']==head and value['repository']['full_name']==REPO and value['head_repository']['full_name']==REPO,'exact new authenticated worker run')
    require(value['status']=='completed' and value['conclusion']=='success' and value['path']==selected['workflow'] and value['head_branch']==selected['branch'] and value['event'] in ('push','workflow_dispatch'),'entire new reviewed workflow successful')


def outer(path,directory,budget):
    zip_preflight(path)
    with zipfile.ZipFile(path) as archive:
        members=archive.infolist();require(len(members)==2 and {m.filename for m in members}=={'evidence.zip','packing.json'},'exact original successful Actions members')
        require(sum(m.file_size for m in members)<=251*MIB,'small original worker artifact')
        for member in members:
            require(not member.is_dir() and stat.S_IFMT(member.external_attr>>16) in (0,stat.S_IFREG) and not member.flag_bits&1,'regular unencrypted member')
            cap=250*MIB if member.filename=='evidence.zip' else MIB;require(member.file_size<=cap,'original Actions member cap');budget(member.file_size)
            with archive.open(member) as source,(directory/member.filename).open('xb') as out:
                size=0
                while data:=source.read(MIB):size+=len(data);require(size<=member.file_size,'exact outer expansion');out.write(data)
            require(size==member.file_size,'complete outer member')


def admit(transport,run,head):
    require(type(run) is int and run>0 and len(head)==40 and all(c in '0123456789abcdef' for c in head),'explicit new reviewed run coordinates')
    value=transport.api('new-run',f'repos/{REPO}/actions/runs/{run}');coordinates(value,run,head)
    jobs=transport.api('new-jobs',f'repos/{REPO}/actions/runs/{run}/attempts/1/jobs?per_page=100');require(jobs['total_count']==len(jobs['jobs'])==1,'one actual fresh readback job')
    job=jobs['jobs'][0];require(job['run_id']==run and job['run_attempt']==1 and job['head_sha']==head and job['name']=='readback' and job['labels']==['ubuntu-24.04'] and job['status']=='completed' and job['conclusion']=='success','native original readback job')
    require(job['steps'] and all(s['status']=='completed' and s['conclusion']=='success' for s in job['steps']),'all actual worker and artifact steps passed')
    listing=transport.api('new-artifacts',f'repos/{REPO}/actions/runs/{run}/artifacts?per_page=100');require(listing['total_count']==len(listing['artifacts'])==1,'one original metadata-only artifact')
    asset=listing['artifacts'][0];require(asset['name']==f'whole-byte-readback-{run}-1' and asset['expired'] is False and asset['workflow_run']['id']==run and asset['workflow_run']['head_sha']==head and asset['workflow_run']['head_branch']==gate.load(gate.SELECTOR)['branch'],'new artifact run binding')
    require(asset['url']==f"https://api.github.com/repos/{REPO}/actions/artifacts/{asset['id']}" and asset['archive_download_url']==asset['url']+'/zip','exact Actions origin')
    require(0<asset['size_in_bytes']<=256*MIB and asset['digest'].startswith('sha256:') and len(asset['digest'])==71,'bounded authenticated original ZIP')
    direct=transport.api('new-artifact',f"repos/{REPO}/actions/artifacts/{asset['id']}")
    require(all(direct[k]==asset[k] for k in ('id','name','size_in_bytes','digest','workflow_run','expired','url','archive_download_url')),'direct original artifact identity')
    wanted=dict(bytes=asset['size_in_bytes'],sha256=asset['digest'][7:]);path=transport.directory/'original-worker-actions.zip'
    transport.run('new-actions-zip',['api',f"repos/{REPO}/actions/artifacts/{asset['id']}/zip"],output=path,maximum=wanted['bytes'],data=True);require(identity(path)==wanted,'authenticated original Actions ZIP body')
    outer(path,transport.directory,transport.budget);packing=load(transport.directory/'packing.json');inner=transport.directory/'evidence.zip'
    require(packing['schema']=='trident/remote-byte-replay-packing/v1' and packing['status']=='passed' and identity(inner)==packing['archive'],'complete bounded inner metadata artifact')
    require(0<=packing['elapsed_total_monotonic_seconds']<=5400 and packing['sampled_peak_rss_bytes']<=2*1024**3,'original packing deadline and RSS observations')
    evidence=transport.directory/'evidence';members=extract_zip(inner,evidence,transport.budget);require(members==packing['members'],'all original inner metadata members')
    manifest=load(evidence/'evidence-files.json');require({k:v for k,v in members.items() if k!='evidence-files.json'}==manifest,'exact original metadata inventory')
    # This authenticated duplicate is recoverable inside the retained original ZIP.
    inner.unlink()
    worker=load(evidence/'receipt.json');require(worker['worker']==dict(id=run,attempt=1,head=head,repository=REPO,branch=gate.load(gate.SELECTOR)['branch'],workflow=gate.load(gate.SELECTOR)['workflow'],event=value['event']),'actual runtime worker coordinates')
    require(worker['ended_ns']<=packing['started_ns']<=packing['ended_ns'],'body observation precedes completed packing')
    samples=packing['samples'];require(samples and all(a['time_ns']<=b['time_ns'] for a,b in zip(samples,samples[1:])),'ordered original packing samples')
    require(all(s['rss_bytes']==sum(p['rss_bytes'] for p in s['processes'])<=2*1024**3 and packing['started_ns']<=s['time_ns']<=packing['ended_ns'] for s in samples),'packing sample values and interval')
    require(max(s['rss_bytes'] for s in samples)==packing['sampled_peak_rss_bytes'],'packing raw peak')
    checked=replay(evidence,worker,transport.budget)
    after=transport.api('new-run-after',f'repos/{REPO}/actions/runs/{run}');coordinates(after,run,head)
    return dict(schema='trident/authenticated-remote-byte-result/v1',status='passed',run=value,jobs=jobs,artifact=asset,original_zip=wanted,packing=identity(transport.directory/'packing.json'),checked=checked)
