"""Authenticate original run/ZIPs and bind pending/completion before proof reads."""
from pathlib import Path

from archives import extract_zip, replay_tar
from common import REPO, identity, load, require
from contracts import RUN, MIB, admit_run, artifact, common_remote, completion_manifest, ident, pending_manifest
from evidence import phase


def actions(transport, expected):
    run=transport.api('actions-run',f'repos/{REPO}/actions/runs/{RUN}')
    jobs=transport.api('actions-jobs',f'repos/{REPO}/actions/runs/{RUN}/attempts/1/jobs?per_page=100')
    admit_run(run,jobs)
    listing=transport.api('actions-artifacts',f'repos/{REPO}/actions/runs/{RUN}/artifacts?per_page=100')
    names={f'whole-v2-{p}-c{g}-1' for p in ('producer','verifier','pending') for g in (1,2)}
    values=listing['artifacts']
    require(listing['total_count']==len(values)==6 and {a['name'] for a in values}==names,'exact six actual artifacts')
    require(len({a['id'] for a in values})==6,'distinct original artifact IDs')
    require(sum(a['size_in_bytes'] for a in values)<=256*MIB,'bounded aggregate ZIP bytes')
    result={}
    for value in values:
        name=value['name']; wanted=artifact(value,name)
        direct=transport.api(name+'-metadata',f"repos/{REPO}/actions/artifacts/{value['id']}")
        require(artifact(direct,name)==wanted and direct['id']==value['id'],'direct artifact metadata identity')
        path=transport.directory/(name+'.zip')
        transport.run(name+'-zip',['api',f"repos/{REPO}/actions/artifacts/{value['id']}/zip"],output=path,maximum=wanted['bytes'],data=True)
        require(identity(path)==wanted,'authenticated original ZIP bytes and server digest')
        dest=transport.directory/name
        members=extract_zip(path,dest,transport.budget)
        transport.receipt.setdefault('actions_artifacts',{})[name]=dict(metadata=value,zip=identity(path),members=members)
        transport.persist(); result[name]=dest
    return run,jobs,result


def transport_receipts(evidence, receipt, values):
    phase=receipt['phase']; labels={'producer':{'pending':'pending-staged'},'verifier':{'download':'downloaded-pending-verification','completion':'fresh-verified-retained'}}[phase]
    allowed={a['id']:expected for a,expected in values}
    for label,status in labels.items():
        t=load(evidence/('transport-'+label+'.json'))
        require(t['schema']=='trident/whole-proof-transport/v2' and t['status']==status and t['phase']==label and
                t['run']==receipt['run'] and t['generation']==receipt['generation'] and t['repository']==REPO and t['release_id']==389977897 and t['tag_name']=='candidate-20260916.1','original completed phase transport')
        rows=t['commands']; require(rows and len(rows)<=1000 and len({r['name'] for r in rows})==len(rows),'bounded unique original transport commands')
        for row in rows:
            args=row['command']; require(args[:2]==['gh','api'],'original gh API command')
            require('error' not in row and 'elapsed_ns' in row and row['elapsed_ns']<=1810*10**9,'successful bounded transport observation')
            tag=any(a==f'repos/{REPO}/git/ref/tags/candidate-20260916.1' for a in args)
            require(row['exit_code']==(1 if tag else 0),'original expected transport exit')
            require(identity(evidence/(label+'-'+row['name']+'.stderr'))==row['stderr'],'raw original transport stderr')
            stdout=evidence/(label+'-'+row['name']+'.stdout')
            if stdout.exists():
                require(identity(stdout)==row['stdout'],'raw original transport stdout')
            else:
                require(len(args)==5 and args[3:]==['-H','Accept: application/octet-stream'] and args[2].startswith(f'repos/{REPO}/releases/assets/'),'only removed verified body output')
                asset_id=int(args[2].rsplit('/',1)[1]); require(asset_id in allowed and row['stdout']==allowed[asset_id],'removed original body matches admitted asset')


def metadata(transport,label,value,evidence,snapshot):
    require(0<value['bytes']<=128*MIB,'bounded remote metadata archive')
    path=transport.download(label,value['asset'],ident(value))
    replay=replay_tar(path,evidence,snapshot,transport.budget)
    transport.receipt.setdefault('metadata_replays',{})[label]=replay; transport.persist()
    return replay


def admit(transport,expected,prepared):
    run,jobs,artifacts=actions(transport,expected); entries=[]; all_ids=set()
    for entry in prepared['admitted']['entries']:
        g=entry['generation']; pdir=artifacts[f'whole-v2-producer-c{g}-1']; vdir=artifacts[f'whole-v2-verifier-c{g}-1']; hdir=artifacts[f'whole-v2-pending-c{g}-1']
        p,pcmd=phase(pdir,expected,entry,'producer'); v,vcmd=phase(vdir,expected,entry,'verifier')
        require(pcmd['started_ns']+pcmd['elapsed_ns']<=vcmd['started_ns'],'fresh verifier follows completed producer')
        pointer=p['pending']; require(pointer==v['pending']==load(pdir/'handoff/pointer.json')==load(hdir/'pointer.json')==load(vdir/'pending-pointer.json'),'same authenticated pending pointer across jobs/handoff')
        require(pointer['schema']=='trident/whole-proof-handoff/v2' and pointer['status']=='pending-fresh-verification' and pointer['run']==expected['run'] and pointer['generation']==g,'original pointer coordinates')
        require({x.name for x in hdir.iterdir()}=={'pending.json','pointer.json'},'exact Actions handoff members')
        for path in (pdir/'handoff/pending.json',hdir/'pending.json',vdir/'pending.json'):
            require(identity(path)==pointer['manifest'],'all original pending copies byte-identical')
        require(0<pointer['manifest']['bytes']<=2*MIB,'bounded pending manifest')
        path=transport.download(f'c{g}-pending',pointer['asset'],pointer['manifest'])
        pending=pending_manifest(load(path),expected,entry)
        require(pending['producer_receipt']==identity(pdir/'producer-receipt.json') and pending['producer_binary']==p['binary'] and pending['producer_tools']==p['tools'] and pending['production']==p['production'],'pending actual producer provenance')
        require(ident(v['completion'])==identity(vdir/'completion.json') and 0<v['completion']['bytes']<=2*MIB,'original completion pointer bytes')
        cpath=transport.download(f'c{g}-completion',v['completion']['asset'],ident(v['completion']))
        comp=completion_manifest(load(cpath),expected,entry,pointer,pending)
        require(comp['verifier_receipt']==identity(vdir/'verifier-receipt.json') and comp['verifier_binary']==v['binary'] and comp['verifier_tools']==v['tools'] and comp['verification']==v['verification'],'completion actual verifier provenance')
        metadata(transport,f'c{g}-producer-metadata',pending['metadata'],pdir,'producer-receipt.json')
        metadata(transport,f'c{g}-verifier-metadata',comp['metadata'],vdir,'verifier-receipt.json')
        assets=[(x['asset'],ident(x)) for x in pending['parts']]+[(pending['metadata']['asset'],ident(pending['metadata'])),(pointer['asset'],pointer['manifest']), (comp['metadata']['asset'],ident(comp['metadata'])),(v['completion']['asset'],ident(v['completion']))]
        for asset,value in assets:
            require(asset['id'] not in all_ids,'unique assets across both complete generations'); all_ids.add(asset['id'])
            transport.member(f'c{g}-asset-{asset["id"]}',asset,value)
        transport_receipts(pdir,p,assets); transport_receipts(vdir,v,assets)
        entries.append(dict(generation=g,pending=pointer,completion=v['completion'],proof=pending['proof'],parts=pending['parts'],
                            producer_receipt=identity(pdir/'receipt.json'),verifier_receipt=identity(vdir/'receipt.json'),
                            metadata=dict(producer=pending['metadata'],verifier=comp['metadata']),local=entry))
    require(sum(len(e['parts']) for e in entries)==22,'all 22 original part identities admitted before any body')
    # Repeat authenticated whole-run success after metadata transfer; no executing fetched source.
    after=transport.api('actions-run-after-admission',f'repos/{REPO}/actions/runs/{RUN}')
    admit_run(after,jobs)
    transport.receipt['remote_admission']=dict(run=run,jobs=jobs,entries=entries)
    transport.persist()
    return entries
