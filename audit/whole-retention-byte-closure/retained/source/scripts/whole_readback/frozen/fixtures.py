"""Synthetic offline evidence only; no actual proof result or GitHub call."""
import copy
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile

from common import REPO, identity, save_new
from contracts import ROOT, RUN, HEAD
from evidence import HOST, PROOF, SDK, phase_paths


def digest(data):
    return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def asset(number,name,raw):
    return dict(id=number,name=name,size=len(raw),state='uploaded',digest='sha256:'+hashlib.sha256(raw).hexdigest(),
                url=f'https://api.github.com/repos/{REPO}/releases/assets/{number}',browser_download_url='https://example.invalid/synthetic/'+name)


class Fixture:
    def __init__(self,root):
        self.root=root; self.api_values={}; self.assets={}; self.next_id=1; self.archives={}; self.source_dirs={}
        self.expected=json.loads((ROOT/'expected.json').read_text())
        self.prepared={'admitted':{'entries':[]}}
        self.expected['frozen_inputs']={f'inputs/c{g}{suffix}.dag':digest(f'synthetic-{g}-{suffix}'.encode()) for g in (1,2) for suffix in ('','-job')}
        self.final_artifact=b'synthetic-2-'; self.artifact_rows=[]
        for g,count in [(1,12),(2,10)]:
            data=bytes([g])*count; semantic=dict(synthetic_fixture=True,format='joy-nox-disclosed-compiler-v1',disclosure='complete public witness',physical_resource_claim='unattested',transport={'wire_bytes':count})
            entry=dict(generation=g,proof=dict(path='/synthetic/proof',**digest(data)),verification=semantic,
                       producer_receipt={},verifier_receipt={},parts=[dict(sequence=i,offset=i,**digest(data[i:i+1])) for i in range(count)])
            self.prepared['admitted']['entries'].append(entry)
            pdir=self.phase(entry,'producer'); vdir=self.phase(entry,'verifier'); self.source_dirs[(g,'producer')]=pdir; self.source_dirs[(g,'verifier')]=vdir
            p=json.loads((pdir/'receipt.json').read_text()); v=json.loads((vdir/'receipt.json').read_text())
            parts=[]
            for part in entry['parts']:
                raw=data[part['offset']:part['offset']+part['bytes']]
                parts.append(dict(part,asset=self.add_asset(f'synthetic-c{g}-part{part["sequence"]}',raw),downloaded_verified=True))
            pm=self.metadata(pdir,'producer'); vm=self.metadata(vdir,'verifier')
            pending=dict(schema='trident/whole-proof-pending/v2',status='pending-fresh-verification',**{k:p[k] for k in ('run','generation','profile','source_selector','input_asset')},
                         proof=digest(data),parts=parts,downloaded_reconstruction=digest(data),compiler=self.expected['frozen_inputs'][f'inputs/c{g}.dag'],job=self.expected['frozen_inputs'][f'inputs/c{g}-job.dag'],production=p['production'],producer_binary=p['binary'],producer_tools=p['tools'],metadata=pm,producer_receipt=identity(pdir/'producer-receipt.json'))
            pending_raw=(json.dumps(pending,indent=2)+'\n').encode(); pa=self.add_asset(f'synthetic-c{g}-pending',pending_raw)
            pointer=dict(schema='trident/whole-proof-handoff/v2',run=p['run'],generation=g,status='pending-fresh-verification',manifest=digest(pending_raw),asset=pa)
            # Verifier snapshot binds pending before completion, matching original producer code.
            v['pending']=pointer; self.write(vdir/'verifier-receipt.json',v)
            self.write(vdir/'receipt.json',v)
            vm=self.metadata(vdir,'verifier')
            comp=dict(schema='trident/whole-proof-completion/v2',status='fresh-verified',**{k:v[k] for k in ('run','generation','profile','source_selector','input_asset','verification','compiled')},proof=pending['proof'],pending=pointer,metadata=vm,verifier_binary=v['binary'],verifier_tools=v['tools'],verifier_receipt=identity(vdir/'verifier-receipt.json'))
            comp_raw=(json.dumps(comp,indent=2)+'\n').encode(); ca=self.add_asset(f'synthetic-c{g}-completion',comp_raw)
            p.update(status='pending-staged',pending=pointer); v.update(status='fresh-verified-retained',completion=dict(**digest(comp_raw),asset=ca))
            self.write(pdir/'receipt.json',p); self.write(vdir/'receipt.json',v)
            (pdir/'handoff').mkdir(); (pdir/'handoff/pending.json').write_bytes(pending_raw); self.write(pdir/'handoff/pointer.json',pointer)
            (vdir/'pending.json').write_bytes(pending_raw); self.write(vdir/'pending-pointer.json',pointer); (vdir/'completion.json').write_bytes(comp_raw)
            hdir=root/f'handoff-{g}'; hdir.mkdir(); (hdir/'pending.json').write_bytes(pending_raw); self.write(hdir/'pointer.json',pointer)
            self.action_zip(pdir,f'whole-v2-producer-c{g}-1'); self.action_zip(vdir,f'whole-v2-verifier-c{g}-1'); self.action_zip(hdir,f'whole-v2-pending-c{g}-1')
        run=dict(id=RUN,run_attempt=1,head_sha=HEAD,repository={'full_name':REPO},head_repository={'full_name':REPO},path='.github/workflows/whole-self-build-v2.yml',event='push',head_branch='test/0.4-whole-self-build-ci',status='completed',conclusion='success')
        jobs=[dict(id=100+g*2+(p=='verifier'),name=f'c{g} / {p}',run_id=RUN,run_attempt=1,head_sha=HEAD,status='completed',conclusion='success',labels=['ubuntu-24.04'],completed_at='synthetic',steps=[dict(status='completed',conclusion='success')]) for g in (1,2) for p in ('producer','verifier')]
        self.api_values[f'repos/{REPO}/actions/runs/{RUN}']=run
        self.api_values[f'repos/{REPO}/actions/runs/{RUN}/attempts/1/jobs?per_page=100']=dict(total_count=4,jobs=jobs)
        self.api_values[f'repos/{REPO}/actions/runs/{RUN}/artifacts?per_page=100']=dict(total_count=6,artifacts=self.artifact_rows)

    def write(self,path,value):
        path.write_text(json.dumps(value,indent=2)+'\n')

    def add_asset(self,name,raw):
        value=asset(self.next_id,name,raw); self.next_id+=1; self.assets[value['id']]=(value,raw); return value

    def phase(self,entry,role):
        g=entry['generation']; d=self.root/f'phase-{g}-{role}'; d.mkdir(); paths=phase_paths(g,role); work=paths['work']; family=paths['family']; commands=[]
        def command(name,argv,cwd=None,stdout=b'',stderr=b'',output=None):
            (d/(name+'.stderr')).write_bytes(stderr)
            if output is None: (d/(name+'.stdout')).write_bytes(stdout)
            commands.append(dict(name=name,command=argv,cwd=cwd or work,started_ns=1,elapsed_ns=1,exit_code=0,
                                 stdout=dict(path=output or paths['results']+'/'+name+'.stdout',**(self.expected['input_asset'] if name=='input-download' else digest(stdout))),stderr=dict(path=paths['results']+'/'+name+'.stderr',**digest(stderr))))
            if name=='input-download': commands[-1]['stdout']={k:commands[-1]['stdout'][k] for k in ('path','bytes','sha256')}
        checkout='/home/runner/work/trisha/trisha'
        command('bootstrap-head',['git','rev-parse','HEAD'],checkout,(HEAD+'\n').encode()); command('bootstrap-status',['git','status','--porcelain=v1','--untracked-files=all'],checkout)
        self.write(d/'disk-cleanup.json',dict(allowlist=SDK,removed=[],before={},after={}))
        a=self.expected['input_asset']; endpoint=f"repos/{REPO}/releases/assets/{a['asset_id']}"; meta=dict(id=a['asset_id'],name=a['name'],size=a['bytes'],digest='sha256:'+a['sha256'])
        command('input-metadata',['gh','api',endpoint],stdout=json.dumps(meta).encode()); command('input-download',['gh','api',endpoint,'-H','Accept: application/octet-stream'],output=work+'/'+a['name'])
        inventory={}
        for name,rev in self.expected['source_selector']['sources'].items():
            dest=family+'/'+name
            command(name+'-init',['git','init',dest])
            for key,value in [('autocrlf','false'),('eol','lf'),('symlinks','true')]: command(name+'-core.'+key,['git','-C',dest,'config','core.'+key,value])
            command(name+'-origin',['git','-C',dest,'remote','add','origin','https://github.com/cyberia-to/'+name+'.git'])
            command(name+'-fetch',['git','-C',dest,'fetch','--depth=1','origin',rev]); command(name+'-checkout',['git','-C',dest,'checkout','--detach','FETCH_HEAD'])
            command(name+'-head',['git','-C',dest,'rev-parse','HEAD'],stdout=(rev+'\n').encode())
            inventory[name]=dict(commit=rev,files=[dict(path='synthetic.txt',mode='100644',git_blob='0'*40,**digest(b'synthetic'))])
        for suffix in ('before','prepared','produced' if role=='producer' else 'verified'):
            self.write(d/f'sources-{suffix}.json',inventory)
            for name in inventory:
                dest=family+'/'+name; command(f'{name}-status-{suffix}',['git','-C',dest,'status','--porcelain=v1','--untracked-files=all'])
                command(f'{name}-files-{suffix}',['git','-C',dest,'ls-files','--stage','-z'],stdout=('100644 '+'0'*40+' 0\tsynthetic.txt\0').encode())
        toolchain='1.89.0-x86_64-unknown-linux-gnu'; rustup='/synthetic/rustup'; tools={n:dict(path='/synthetic/bin/'+n,**digest(b'synthetic-tool')) for n in ('cargo','rustc','rustdoc')}
        command('install-rust',[rustup,'toolchain','install',toolchain,'--profile','minimal'])
        for n,t in tools.items(): command('resolve-'+n,[rustup,'which','--toolchain',toolchain,n],stdout=(t['path']+'\n').encode())
        command('rustc-version',[tools['rustc']['path'],'-vV'],stdout=b'release: 1.89.0\nhost: x86_64-unknown-linux-gnu\n'); command('cargo-version',[tools['cargo']['path'],'-vV'],stdout=b'cargo 1.89.0 synthetic\n')
        joy=family+'/joy'; c=tools['cargo']['path']; manifest=joy+'/Cargo.toml'
        command('cargo-fetch',[c,'fetch','--manifest-path',manifest,'--locked'],joy)
        command('cargo-metadata',[c,'metadata','--manifest-path',manifest,'--format-version','1','--locked','--offline'],joy,json.dumps(dict(packages=[dict(name='joy',version='synthetic',source=None,manifest_path=manifest)])).encode())
        command('native-boundary',['/synthetic/python','-B',joy+'/scripts/check-soft3-boundary.py'],joy)
        command('native-build',[c,'build','--manifest-path',manifest,'--release','-p','cyber-joy','--locked','--offline'],joy)
        command('repack-job',[paths['binary'],'pack-job','--compiler',paths['compiler'],'--manifest',work+'/frozen/inputs/package.json','--output',work+'/repacked-job.dag',*HOST])
        binary=digest(b'synthetic-binary'); (d/'joy-linux-x64').write_bytes(b'synthetic-binary')
        flags=list(HOST); flags[flags.index('--time-ms')+1]=str(self.expected['profile'][role+'_time_ms'])
        argv=[paths['binary'],'prove-artifact' if role=='producer' else 'verify-artifact',paths['compiler'],'--input',paths['job']]
        argv+=['--output','proof.joysc'] if role=='producer' else ['--proof',paths['proof'],'--output','compiler.dag','--emit','program']
        inputs={paths['compiler']:self.expected['frozen_inputs'][f'inputs/c{g}.dag'],paths['job']:self.expected['frozen_inputs'][f'inputs/c{g}-job.dag']}
        if role=='verifier': inputs[paths['proof']]={k:entry['proof'][k] for k in ('bytes','sha256')}
        stdout=dict(ok=True,schema='joy/artifact-proof/v1' if role=='producer' else 'joy/artifact-verification/v1',verification=entry['verification'])
        self.write(d/(role+'.stdout'),stdout); (d/(role+'.stderr')).write_bytes(b'')
        sample=dict(elapsed_ns=1,processes=[],rss_bytes=0,attempt_bytes=1,free_bytes=100*1024**3); self.write(d/(role+'-resources.jsonl'),sample)
        # One actual JSONL line rather than formatted JSON.
        (d/(role+'-resources.jsonl')).write_text(json.dumps(sample)+'\n')
        native=dict(name=role,status='passed',command=argv+flags+PROOF,cwd=work+'/'+role,exit_code=0,elapsed_ns=1,started_ns=100 if role=='producer' else 200,
                    environment={'PATH':'','LANG':'C.UTF-8'},inputs_before=inputs,inputs_after=inputs,binary_before=binary,binary_after=binary,sampled_peak_rss_bytes=0,latest_sample=sample,
                    logs={k:identity(d/(role+'.'+k)) for k in ('stdout','stderr')})
        r=dict(schema='trident/whole-proof-native-phase/v2',status='produced-pending-fresh-verification' if role=='producer' else 'fresh-verified',phase=role,generation=g,
               **{k:copy.deepcopy(self.expected[k]) for k in ('run','profile','bootstrap','source_selector','input_asset')},
               frozen_inputs_before=self.expected['frozen_inputs'],frozen_inputs_after=self.expected['frozen_inputs'],host=dict(system='Linux',machine='x86_64'),
               binary=dict(path=paths['binary'],**binary),proof=dict(path=paths['proof'],**{k:entry['proof'][k] for k in ('bytes','sha256')}),commands=commands,proof_commands=[native],tools=tools,input_asset_metadata=meta,
               source_inventory_identities={p.name:identity(p) for p in d.glob('sources-*.json')},
               build_environment=dict(PATH='/synthetic/bin:/usr/bin',CARGO_HOME=work+'/cargo-home',CARGO_TARGET_DIR=work+'/target',RUSTC=tools['rustc']['path'],RUSTDOC=tools['rustdoc']['path'],RUSTUP_TOOLCHAIN=toolchain,RUSTFLAGS='-Dwarnings',CARGO_BUILD_JOBS='2'),
               closure=[dict(name='joy',version='synthetic',origin=dict(repository='joy',commit=self.expected['source_selector']['sources']['joy'],manifest='joy/Cargo.toml'))],production=entry['verification'])
        if role=='verifier':
            r.update(verification=entry['verification'],compiled=digest(self.final_artifact)); (d/'compiler.dag').write_bytes(self.final_artifact)
        for label,status in ({'pending':'pending-staged'} if role=='producer' else {'download':'downloaded-pending-verification','completion':'fresh-verified-retained'}).items():
            args=['gh','api',f'repos/{REPO}/releases/389977897']; raw=b'{}'; (d/(label+'-synthetic.stdout')).write_bytes(raw); (d/(label+'-synthetic.stderr')).write_bytes(b'')
            self.write(d/('transport-'+label+'.json'),dict(schema='trident/whole-proof-transport/v2',status=status,phase=label,run=r['run'],generation=g,repository=REPO,release_id=389977897,tag_name='candidate-20260916.1',commands=[dict(name='synthetic',command=args,exit_code=0,elapsed_ns=1,stdout=digest(raw),stderr=digest(b''))]))
        self.write(d/'receipt.json',r); self.write(d/(role+'-receipt.json'),r)
        return d

    def metadata(self,d,role):
        path=self.root/f'metadata-{self.next_id}.tar.gz'; rows={str(p.relative_to(d)):identity(p) for p in d.rglob('*') if p.is_file()}
        listing=self.root/f'meta-list-{self.next_id}.json'; self.write(listing,rows)
        with tarfile.open(path,'w:gz') as archive:
            for name in sorted(rows): archive.add(d/name,arcname='evidence/'+name,recursive=False)
            archive.add(listing,arcname='evidence/files.json',recursive=False)
        a=self.add_asset(f'synthetic-metadata-{self.next_id}',path.read_bytes()); return dict(**identity(path),asset=a)

    def action_zip(self,d,name):
        path=self.root/(name+'.zip')
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
            for p in d.rglob('*'):
                if p.is_file(): archive.write(p,str(p.relative_to(d)))
        number=1000+len(self.artifact_rows); row=dict(id=number,name=name,expired=False,url=f'https://api.github.com/repos/{REPO}/actions/artifacts/{number}',archive_download_url=f'https://api.github.com/repos/{REPO}/actions/artifacts/{number}/zip',workflow_run=dict(id=RUN,head_sha=HEAD,head_branch='test/0.4-whole-self-build-ci'),size_in_bytes=path.stat().st_size,digest='sha256:'+identity(path)['sha256'])
        self.artifact_rows.append(row); self.api_values[f'repos/{REPO}/actions/artifacts/{number}']=row; self.archives[number]=path.read_bytes()
