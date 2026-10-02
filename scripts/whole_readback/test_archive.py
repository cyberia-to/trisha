"""Complete small synthetic remote/API/archive replay; no real proof or network."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

import gate
gate.frozen()
from common import REPO, RELEASE, TAG, identity, load, require, save_new
from contracts import MIB
from fixtures import Fixture
from transport import Transport
import packing
import recorded
import remote
import result
import worker
from metadata import PROFILE, record_body


class Observed(Transport):
    """Produce real fixture files and complete synthetic GET command receipts."""
    def __init__(self,directory,fixture):
        directory.mkdir();self.fixture=fixture
        super().__init__(directory,dict(path='/synthetic/gh',bytes=0,sha256='0'*64),gate.sources(),gate.sources)
        self.receipt['gh']=self.gh

    def sample(self):pass

    def run(self,name,args,expected_exit=0,output=None,maximum=8*MIB,data=False):
        from bounded import read_only
        read_only(args);record_body(self,name,output,data);started=time.time_ns();endpoint=args[3] if '--paginate' in args else args[1]
        exit_code=0
        if endpoint==f'repos/{REPO}/releases/{RELEASE}':value=dict(id=RELEASE,draft=True,tag_name=TAG,published_at=None)
        elif endpoint==f'repos/{REPO}/git/ref/tags/{TAG}':value=dict(status='404');exit_code=1
        elif endpoint==f'repos/{REPO}':value=dict(full_name=REPO,default_branch='master')
        elif endpoint==f'repos/{REPO}/git/ref/heads/master':value=dict(ref='refs/heads/master',object=dict(type='commit',sha='a'*40))
        elif endpoint==f'repos/{REPO}/releases/{RELEASE}/assets?per_page=100':value=[[a for a,_ in self.fixture.assets.values()]]
        else:value=self.fixture.api_values.get(endpoint)
        if value is not None:raw=json.dumps(value).encode()
        elif endpoint.endswith('/zip'):raw=self.fixture.archives[int(endpoint.split('/')[-2])]
        elif endpoint.startswith(f'repos/{REPO}/releases/assets/'):raw=self.fixture.assets[int(endpoint.rsplit('/',1)[1])][1]
        else:raise ValueError('unexpected synthetic endpoint: '+endpoint)
        require(exit_code==expected_exit and len(raw)<=maximum,'synthetic exact bounded command')
        output=output or self.directory/(name+'.stdout');error=self.directory/(name+'.stderr')
        with output.open('xb') as stream:stream.write(raw)
        with error.open('xb') as stream:stream.write(b'')
        self.receipt['commands'].append(dict(name=name,command=[self.gh['path'],*args],expected_exit=expected_exit,exit_code=exit_code,started_ns=started,ended_ns=time.time_ns(),elapsed_seconds=0,timeout_seconds=1800 if data else 120,stdout_limit=maximum,stdout_path=str(output),stderr_path=str(error),stdout=identity(output),stderr=identity(error),cleanup=dict(status='leader-complete')))
        self.persist();return output


class Archives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='remote-archive-fixture-');cls.root=Path(cls.temp.name)
        (cls.root/'fixture').mkdir();cls.fixture=Fixture(cls.root/'fixture');t=Observed(cls.root/'worker',cls.fixture)
        t.draft('initial');entries=remote.admit(t,cls.fixture.expected,cls.fixture.prepared)
        worker.replay(t,entries);t.draft('final')
        for name in gate.sources():
            target=t.directory/'worker-sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(gate.REPOSITORY/name,target)
        sample=dict(time_ns=time.time_ns(),rss_bytes=1,processes=[dict(pid=os.getpid(),ppid=0,pgid=os.getpid(),rss_bytes=1)])
        (t.directory/'resources.jsonl').write_text(json.dumps(sample)+'\n')
        cls.selected=copy.deepcopy(gate.load(gate.SELECTOR));cls.selected.update(remote_entries=entries,actions_artifacts={n:dict(id=v['metadata']['id'],zip=v['zip']) for n,v in t.receipt['actions_artifacts'].items()})
        cls.worker=dict(id=12345,attempt=1,head='b'*40,repository=REPO,branch=cls.selected['branch'],workflow=cls.selected['workflow'],event='push')
        t.receipt.update(schema='trident/remote-certificate-byte-replay/v1',status='completed-byte-replay',worker=cls.worker,profile=PROFILE,observer_pid=os.getpid(),elapsed_monotonic_seconds=1,ended_ns=time.time_ns(),local_preparation=cls.selected['local_preparation'],original_local_metadata=cls.selected['original_metadata'],sources=gate.sources(),source_manifest=identity(gate.MANIFEST),selector=identity(gate.SELECTOR),sampled_peak_rss_bytes=1,latest_sample=sample)
        t.persist();cls.receipt=copy.deepcopy(t.receipt)
        with patch.object(packing,'process_rows',return_value=[dict(pid=os.getpid(),ppid=0,pgid=os.getpid(),rss_bytes=1)]):
            cls.packed=packing.pack(t,cls.root/'artifact/evidence.zip')
        cls.outer=cls.root/'actions.zip'
        with zipfile.ZipFile(cls.outer,'w',compression=zipfile.ZIP_STORED) as archive:
            for name in ('evidence.zip','packing.json'):archive.write(cls.root/'artifact'/name,name)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def patches(self):return patch.object(gate,'frozen',return_value=(self.selected,self.fixture.expected,self.fixture.prepared))

    def unpack(self,root):
        result.outer(self.outer,root,lambda n:None)
        from archives import extract_zip
        path=root/'evidence';extract_zip(root/'evidence.zip',path,lambda n:None)
        return path

    def test_complete_metadata_pack_and_independent_replay(self):
        with tempfile.TemporaryDirectory() as temp,self.patches():
            path=self.unpack(Path(temp));got=recorded.replay(path,load(path/'receipt.json'),lambda n:None)
            self.assertEqual(got['status'],'passed-authenticated-remote-byte-replay')
            self.assertEqual(len(got['body_commands']),22)
            self.assertEqual(got['entries'],self.selected['remote_entries'])
            self.assertTrue((path/'whole-v2-producer-c1-1/receipt.json').exists())
        self.assertFalse(any(n.startswith('whole-v2-producer-c1-1/') for n in self.packed['members']))
        self.assertFalse(any(n=='chunk' or n.endswith('.joysc') for n in self.packed['members']))

    def test_command_and_resource_mutations(self):
        changes=[lambda r:r.update(status='running'),lambda r:r.pop('profile'),lambda r:r.update(profile={}),lambda r:r['profile'].update(total_seconds=5400.0),
                 lambda r:r['metadata_reservations'][0].update(required_bytes=0),lambda r:r.update(source_manifest={}),
                 lambda r:r['metadata_reservations'][0].update(time_ns=r['started_ns']),
                 lambda r:r['entries'][0]['parts'].reverse(),lambda r:r['commands'][0].update(exit_code=9),
                 lambda r:r['commands'][-1]['command'].append('--method'),lambda r:r.update(sampled_peak_rss_bytes=2),
                 lambda r:r.update(latest_sample={}),lambda r:r.update(ended_ns=0)]
        for change in changes:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp,self.patches():
                path=self.unpack(Path(temp));receipt=load(path/'receipt.json');change(receipt)
                with self.assertRaises((ValueError,KeyError)):recorded.replay(path,receipt,lambda n:None)

    def test_new_run_coordinates_and_job_artifact_replay(self):
        run=dict(id=12345,run_attempt=1,head_sha='b'*40,repository=dict(full_name=REPO),head_repository=dict(full_name=REPO),status='completed',conclusion='success',path=self.selected['workflow'],head_branch=self.selected['branch'],event='push')
        job=dict(run_id=12345,run_attempt=1,head_sha='b'*40,name='readback',labels=['ubuntu-24.04'],status='completed',conclusion='success',steps=[dict(status='completed',conclusion='success')])
        asset=dict(id=555,name='whole-byte-readback-12345-1',expired=False,workflow_run=dict(id=12345,head_sha='b'*40,head_branch=self.selected['branch']),url=f'https://api.github.com/repos/{REPO}/actions/artifacts/555',archive_download_url=f'https://api.github.com/repos/{REPO}/actions/artifacts/555/zip',size_in_bytes=identity(self.outer)['bytes'],digest='sha256:'+identity(self.outer)['sha256'])
        def execute(change=None):
            values=dict(run=copy.deepcopy(run),jobs=dict(total_count=1,jobs=[copy.deepcopy(job)]),artifacts=dict(total_count=1,artifacts=[copy.deepcopy(asset)]),asset=copy.deepcopy(asset))
            if change:change(values)
            with tempfile.TemporaryDirectory() as temp,self.patches():
                class Local:
                    directory=Path(temp)
                    def budget(self,n=0):pass
                    def api(self,label,*args):return values[{'new-run':'run','new-run-after':'run','new-jobs':'jobs','new-artifacts':'artifacts','new-artifact':'asset'}[label]]
                    def run(self,*args,output=None,**kwargs):shutil.copyfile(self_outer,output);return output
                self_outer=self.outer
                return result.admit(Local(),12345,'b'*40)
        got=execute();self.assertEqual(got['status'],'passed');self.assertEqual(len(got['checked']['body_commands']),22)
        changes=[lambda v:v['run'].update(run_attempt=2),lambda v:v['run'].update(head_sha='c'*40),lambda v:v['run'].update(conclusion='failure'),lambda v:v['jobs']['jobs'].clear(),lambda v:v['jobs']['jobs'][0].update(conclusion='failure'),lambda v:v['asset'].update(digest='sha256:'+'c'*64),lambda v:v['artifacts']['artifacts'][0].update(expired=True)]
        for change in changes:
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):execute(change)

    def test_outer_archive_exact_members_and_size(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bad=root/'bad.zip'
            with zipfile.ZipFile(bad,'w') as archive:archive.writestr('../evidence.zip',b'x');archive.writestr('packing.json',b'{}')
            with self.assertRaises(ValueError):result.outer(bad,root,lambda n:None)
            data=root/'data';data.mkdir();save_new(data/'receipt.json',{'status':'synthetic'})
            with patch.object(packing.time,'monotonic',return_value=10**30),self.assertRaises(ValueError):
                packing.pack(type('T',(),dict(directory=data,tick=0,sample=lambda self:None,budget=lambda self,n=0:None))(),root/'artifact/evidence.zip')


if __name__=='__main__':unittest.main()
