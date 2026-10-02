"""Bounded fixed-draft transport, used only after an explicit reviewed execute gate."""
import os
import json
from pathlib import Path
import resource
import selectors
import shutil
import signal
import subprocess
import time
from time import monotonic as cleanup_clock
import traceback
from urllib.parse import quote

from common import CHUNK, REPO, RELEASE, TAG, check_asset, identity, load, require, save_new
from contracts import MIB, SIDECARS, SCOPE, ident


def group_exists(pgid):
    try:
        os.killpg(pgid,0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS can return EPERM after the last running group member has died.
        result=subprocess.run(['/bin/ps','-axo','pid=,pgid=,stat='],capture_output=True,timeout=5,env={'PATH':'','LANG':'C'})
        require(result.returncode==0 and len(result.stdout)<=MIB,'bounded process-group fallback probe')
        running=[line for line in result.stdout.decode().splitlines() if int(line.split()[1])==pgid and not line.split()[2].startswith('Z')]
        require(not running,'owned process-group probe denied with running members')
        return False


def stop(child,force_group=False):
    if child is None or (child.poll() is not None and not force_group):
        return dict(status='leader-complete')
    require(getattr(child,'adoption_owned_group',None)==child.pid,'recorded owned process group')
    observations=dict(group=child.pid,signals=[])
    if group_exists(child.pid):
        try:
            os.killpg(child.pid,signal.SIGTERM); observations['signals'].append('TERM')
        except ProcessLookupError:
            pass
    deadline=cleanup_clock()+10
    while group_exists(child.pid) and cleanup_clock()<deadline:
        child.poll(); time.sleep(0.05)
    if group_exists(child.pid):
        try:
            os.killpg(child.pid,signal.SIGKILL); observations['signals'].append('KILL')
        except ProcessLookupError:
            pass
    child.wait(timeout=10)
    deadline=cleanup_clock()+5
    while group_exists(child.pid) and cleanup_clock()<deadline:
        time.sleep(0.05)
    observations['group_empty']=not group_exists(child.pid)
    require(observations['group_empty'],'owned process group cleanup incomplete')
    return observations


class Transport:
    def __init__(self, directory, gh, sources, check_sources):
        self.directory=directory; self.gh=gh; self.check_sources=check_sources
        self.baseline=None; self.tick=time.monotonic(); self.sources=sources
        self.env={k:v for k,v in os.environ.items() if k in ('HOME','USER','LOGNAME','GH_TOKEN','GITHUB_TOKEN','GH_CONFIG_DIR','SSL_CERT_FILE','SSL_CERT_DIR')}
        self.env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',GH_HOST='github.com',GH_PROMPT_DISABLED='1',GH_PAGER='cat',NO_COLOR='1')
        self.receipt=dict(schema='trident/local-remote-byte-adoption/v1',status='running',scope=SCOPE,
                          repository=REPO,release_id=RELEASE,tag_name=TAG,sources=sources,commands=[],entries=[],
                          environment_keys=sorted(self.env),started_ns=time.time_ns())
        reserve=self.directory/'terminal-reserve.json'
        require(shutil.disk_usage(self.directory).free>=8*CHUNK+MIB,'emergency evidence reserve preflight')
        with reserve.open('xb') as output:
            raw=b'{"status":"reserved-failure-evidence"}\n'
            output.write(raw+b' '*(MIB-len(raw))); output.flush(); os.fsync(output.fileno())
        self.persist()

    def failure(self,error):
        """Use only already reserved evidence; no admission, retry or new transfer."""
        self.receipt.update(status='failed',error=error)
        target=self.directory/'terminal-failure.json'
        if target.exists():
            require(load(target)['status']=='failed','existing terminal failure is immutable')
            return
        record=dict(schema='trident/byte-adoption-terminal-failure/v1',status='failed',scope=SCOPE,
                    started_ns=self.receipt['started_ns'],ended_ns=time.time_ns(),error=error[:32768],
                    sources=self.sources,commands_observed=len(self.receipt['commands']),partials={})
        latest=self.receipt['commands'][-1] if self.receipt['commands'] else None
        if latest is not None:
            record['latest_command']={k:v for k,v in latest.items() if k not in ('error','cleanup_error')}
            for key in ('error','cleanup_error'):
                if key in latest: record['latest_command'][key]=latest[key][:32768]
        candidates={'receipt.json':16*MIB,'receipt.next':16*MIB,'chunk':CHUNK}
        if latest is not None:
            for field,limit in [('stdout_path',latest.get('stdout_limit',CHUNK)),('stderr_path',8*MIB)]:
                if field in latest:
                    path=Path(latest[field])
                    if path.parent==self.directory: candidates[path.name]=limit
        for name,limit in candidates.items():
            path=self.directory/name
            if path.is_file() and not path.is_symlink():
                if path.stat().st_size<=limit: record['partials'][name]=identity(path)
                else: record['partials'][name]={'bytes':path.stat().st_size,'identity_omitted':'exceeds bounded failure hash limit'}
        raw=(json.dumps(record,indent=2)+'\n').encode()
        require(len(raw)<=MIB,'bounded emergency failure receipt')
        reserve=self.directory/'terminal-reserve.json'
        require(reserve.is_file() and not reserve.is_symlink() and reserve.stat().st_size==MIB,'existing owned emergency reserve')
        with reserve.open('r+b') as output:
            output.write(raw+b' '*(MIB-len(raw))); output.flush(); os.fsync(output.fileno())
        reserve.rename(target)

    def persist(self):
        raw=(json.dumps(self.receipt,indent=2)+'\n').encode()
        require(len(raw)<=16*MIB,'bounded ordinary receipt')
        self.budget(len(raw))
        tmp=self.directory/'receipt.next'
        with tmp.open('xb') as output: output.write(raw)
        tmp.replace(self.directory/'receipt.json')

    def budget(self, reserve=0, chunk=False):
        require(time.monotonic()-self.tick <= 43200,'12-hour adoption deadline')
        paths=list(self.directory.rglob('*'))
        require(all(not p.is_symlink() for p in paths),'owned scope contains no symlinks')
        total=sum(p.stat().st_size for p in paths if p.is_file() and p != self.directory/'chunk')
        require(total+(8*MIB if chunk else reserve)<=SIDECARS,'512 MiB aggregate retained sidecars/logs')
        part=self.directory/'chunk'
        require(not part.exists() or part.stat().st_size <= CHUNK,'one bounded owned chunk')
        require(shutil.disk_usage(self.directory).free >= 8*CHUNK+reserve,'8 GiB floor plus reserved output')

    def run(self,name,args,expected_exit=0,output=None,maximum=8*MIB,data=False):
        require(self.receipt['status']!='failed' and not (self.directory/'terminal-failure.json').exists(),'failed adoption cannot start another operation')
        require(self.check_sources()==self.sources,'reviewed adoption source stable')
        require(not any(r['name']==name for r in self.receipt['commands']),'unique command name')
        require(type(maximum) is int and 0<maximum<=CHUNK,'bounded output cap')
        require(identity(self.gh['path'])==ident(self.gh),'exact installed gh executable')
        output=output or self.directory/(name+'.stdout'); error=self.directory/(name+'.stderr')
        require(output.parent==self.directory,'owned output file')
        self.budget(maximum+8*MIB,chunk=output.name=='chunk')
        timeout=1800 if data else 120; argv=[self.gh['path'],*args]
        row=dict(name=name,command=argv,expected_exit=expected_exit,started_ns=time.time_ns(),timeout_seconds=timeout,
                 stdout_limit=maximum,stdout_path=str(output),stderr_path=str(error))
        self.receipt['commands'].append(row); self.persist(); child=None; tick=time.monotonic()
        def limits():
            resource.setrlimit(resource.RLIMIT_FSIZE,(maximum,maximum))
        try:
            with output.open('xb') as stdout,error.open('xb') as stderr:
                child=subprocess.Popen(argv,cwd=self.directory,env=self.env,stdout=stdout,stderr=subprocess.PIPE,start_new_session=True,preexec_fn=limits)
                row['pid']=child.pid
                child.adoption_owned_group=child.pid; row['owned_group']=child.pid
                try:
                    require(os.getpgid(child.pid)==child.pid,'new owned session/group')
                except ProcessLookupError:
                    require(child.poll() is not None,'unobservable live group leader')
                    row['ownership_probe']='leader-already-exited'
                selector=selectors.DefaultSelector(); selector.register(child.stderr,selectors.EVENT_READ)
                stderr_bytes=0
                while child.poll() is None or selector.get_map():
                    for key,_ in selector.select(timeout=0.1):
                        data=os.read(key.fd,65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        permitted=min(len(data),max(0,8*MIB-stderr_bytes))
                        stderr.write(data[:permitted]); stderr.flush(); stderr_bytes+=len(data)
                        require(stderr_bytes<=8*MIB,'hard stderr byte cap')
                    require(time.monotonic()-tick <= timeout,'transport command deadline')
                    require(output.stat().st_size<=maximum and error.stat().st_size<=8*MIB,'command output/log bounds')
                    self.budget()
                selector.close(); child.stderr.close()
                row['exit_code']=child.wait()
                require(row['exit_code']==expected_exit,'transport command exit: '+name)
            require(output.stat().st_size<=maximum and error.stat().st_size<=8*MIB,'final command output/log bounds')
            self.budget()
            return output
        except BaseException:
            row['error']=traceback.format_exc(); raise
        finally:
            cleanup_error=None
            try:
                row['cleanup']=stop(child,force_group='error' in row)
            except BaseException as cleanup_exception:
                cleanup_error=cleanup_exception; row['cleanup_error']=traceback.format_exc()
            if 'selector' in locals(): selector.close()
            if child is not None and child.stderr is not None: child.stderr.close()
            row.update(elapsed_seconds=time.monotonic()-tick,ended_ns=time.time_ns())
            if child is not None: row['exit_code']=child.returncode
            for key,path in [('stdout',output),('stderr',error)]:
                if path.exists(): row[key]=identity(path)
            failure=row.get('error',row.get('cleanup_error'))
            if failure is not None:
                try: self.failure(failure)
                except BaseException as terminal_error: row['terminal_evidence_error']=repr(terminal_error)
                try: self.persist()
                except BaseException as persist_error: row['normal_persist_error']=repr(persist_error)
            else:
                try:
                    self.persist()
                except BaseException:
                    original=traceback.format_exc()
                    try: self.failure(original)
                    except BaseException as terminal_error: row['terminal_evidence_error']=repr(terminal_error)
                    raise
            if cleanup_error is not None and 'error' not in row: raise cleanup_error

    def api(self,label,endpoint,maximum=8*MIB):
        require(endpoint.startswith('repos/'+REPO+'/') or endpoint=='repos/'+REPO,'fixed repository API')
        return load(self.run(label,['api',endpoint],maximum=maximum))

    def draft(self,label):
        release=self.api(label+'-release',f'repos/{REPO}/releases/{RELEASE}')
        require(release['id']==RELEASE and release['draft'] is True and release['tag_name']==TAG and release['published_at'] is None,'fixed unpublished draft')
        absent=load(self.run(label+'-tag',['api',f'repos/{REPO}/git/ref/tags/{TAG}'],expected_exit=1))
        require(str(absent.get('status'))=='404','tag remains absent')
        repo=self.api(label+'-repository','repos/'+REPO); require(repo['full_name']==REPO,'fixed repository')
        branch=repo['default_branch']; require(isinstance(branch,str) and branch,'default branch')
        ref=self.api(label+'-default',f'repos/{REPO}/git/ref/heads/'+quote(branch,safe=''))
        require(ref['ref']=='refs/heads/'+branch and ref['object']['type']=='commit','default commit reference')
        baseline=dict(branch=branch,sha=ref['object']['sha'])
        if self.baseline is None: self.baseline=baseline; self.receipt['default_ref']=baseline; self.persist()
        require(self.baseline==baseline,'unchanged default branch during observations')
        pages=load(self.run(label+'-assets',['api','--paginate','--slurp',f'repos/{REPO}/releases/{RELEASE}/assets?per_page=100']))
        require(isinstance(pages,list) and all(isinstance(p,list) for p in pages),'paginated assets')
        assets=[a for p in pages for a in p]; ids=[a['id'] for a in assets]
        require(len(assets)<=1000 and all(type(i) is int and i>0 for i in ids) and len(set(ids))==len(ids),'bounded unique asset listing')
        return assets

    def member(self,label,asset,expected):
        check_asset(asset,asset['name'],expected)
        matches=[a for a in self.draft(label) if a['id']==asset['id']]
        require(len(matches)==1,'exact fixed-draft membership'); check_asset(matches[0],asset['name'],expected)

    def download(self,label,asset,expected,chunk=False):
        self.member(label+'-membership',asset,expected)
        path=self.directory/('chunk' if chunk else label+'.download')
        self.run(label+'-download',['api',f"repos/{REPO}/releases/assets/{asset['id']}",'-H','Accept: application/octet-stream'],output=path,maximum=expected['bytes'],data=True)
        require(identity(path)==expected,'independent downloaded bytes')
        return path

    def upload(self,label,path,name,expected):
        entries=self.receipt['entries']
        require(self.receipt.get('status')=='both-full-reconstructions-passed' and [e['generation'] for e in entries]==[1,2] and
                all(e['status']=='full-byte-equivalence-passed' and e['downloaded_reconstruction']==e['proof'] for e in entries) and
                sum(len(e['parts']) for e in entries)==22 and all(p['independently_downloaded'] is True for e in entries for p in e['parts']),
                'publication requires both actual complete reconstructions')
        require(path.parent==self.directory and identity(path)==expected,'owned exact publication bytes')
        before=self.draft(label+'-before'); require(name not in {a['name'] for a in before},'unique new asset name')
        endpoint=f'https://uploads.github.com/repos/{REPO}/releases/{RELEASE}/assets?name='+quote(name,safe='')
        asset=load(self.run(label+'-upload',['api','--method','POST',endpoint,'-H','Content-Type: application/octet-stream','--input',str(path)],data=True))
        check_asset(asset,name,expected)
        after=self.draft(label+'-after'); matches=[a for a in after if a['name']==name]
        require(len(matches)==1 and matches[0]['id']==asset['id'],'unique uploaded membership'); check_asset(matches[0],name,expected)
        require(identity(path)==expected,'publication input stable')
        downloaded=self.download(label+'-readback',asset,expected)
        require(identity(downloaded)==expected,'publication independent readback')
        return dict(**expected,asset={k:asset[k] for k in ('id','name','size','state','digest','url','browser_download_url')})
