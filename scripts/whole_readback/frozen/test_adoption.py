"""Offline synthetic controls and mutations; never consume actual whole proofs."""
import copy
import io
import json
import os
import time
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import adopt
from archives import extract_zip, replay_tar
from common import REPO, Reconstruction, check_asset, identity, load, require, save_new
from contracts import (RUN, MIB, admit_run, artifact, completion_manifest, fixed, ident,
                       pending_manifest)
from evidence import phase
from fixtures import Fixture, asset, digest
import remote
from transport import Transport


class SyntheticTransport(Transport):
    """In-memory endpoint bodies; no subprocess, network or live remote writes."""
    def __init__(self,directory,fixture):
        directory.mkdir(); self.fixture=fixture; self.downloads=[]; self.publications=[]
        super().__init__(directory,dict(path='synthetic',bytes=0,sha256='0'*64),{'fixture':'synthetic'},lambda:{'fixture':'synthetic'})

    def draft(self,label):
        self.baseline=dict(branch='synthetic',sha='0'*40); self.receipt['default_ref']=self.baseline
        return [a for a,_ in self.fixture.assets.values()]

    def run(self,name,args,expected_exit=0,output=None,maximum=8*MIB,data=False):
        self.budget(maximum if output is None or output.name!='chunk' else 0)
        require(expected_exit==0,'synthetic positive API only'); output=output or self.directory/(name+'.stdout')
        if '--method' in args:
            raw=Path(args[args.index('--input')+1]).read_bytes(); label=args[3].split('name=',1)[1]
            value=self.fixture.add_asset(label,raw); self.publications.append(value); body=json.dumps(value).encode()
        else:
            endpoint=args[1]
            if endpoint.endswith('/zip'):
                number=int(endpoint.split('/')[-2]); body=self.fixture.archives[number]
            elif endpoint.startswith(f'repos/{REPO}/releases/assets/'):
                number=int(endpoint.rsplit('/',1)[1]); body=self.fixture.assets[number][1]; self.downloads.append(number)
            else:
                body=json.dumps(self.fixture.api_values[endpoint]).encode()
        require(len(body)<=maximum,'synthetic bounded response')
        with output.open('xb') as target: target.write(body)
        (self.directory/(name+'.stderr')).write_bytes(b'')
        self.receipt['commands'].append(dict(name=name,synthetic=True,stdout=identity(output)))
        self.persist(); return output


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='adoption-synthetic-'); cls.root=Path(cls.temp.name)
        cls.fixture=Fixture(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fixed_preparation_and_frozen_admission_hashes(self):
        v=fixed(); self.assertEqual(v['local_preparation']['sha256'],'489de67b014c96f7007c538f8a686af6faddcb5692dfad7de615eeaee29ff299')

    def pending(self,g=1):
        p=load(self.fixture.source_dirs[(g,'producer')]/'receipt.json')['pending']
        return json.loads(self.fixture.assets[p['asset']['id']][1]),p

    def test_synthetic_complete_admission_reconstruction_publication(self):
        with tempfile.TemporaryDirectory(prefix='adoption-control-') as temp:
            transport=SyntheticTransport(Path(temp)/'run',self.fixture)
            entries=remote.admit(transport,self.fixture.expected,self.fixture.prepared)
            # No actual certificate part body was read during metadata admission.
            part_ids={p['asset']['id'] for e in entries for p in e['parts']}
            self.assertFalse(part_ids.intersection(transport.downloads))
            adopt.reconstruct(transport,entries)
            self.assertEqual(transport.receipt['status'],'both-full-reconstructions-passed')
            self.assertEqual(len(part_ids.intersection(transport.downloads)),22)
            self.assertFalse((transport.directory/'chunk').exists())
            prepared=copy.deepcopy(self.fixture.prepared); local=Path(temp)/'local-metadata'; local.write_bytes(b'synthetic original local metadata')
            prepared['metadata']=dict(path=str(local),**identity(local)); prepared['admitted'].update(binary={'fixture':'synthetic'},source_revisions={'fixture':'synthetic'},profile_identity={'fixture':'synthetic'})
            expected=dict(self.fixture.expected,local_preparation={'fixture':'synthetic'})
            adopt.publish(transport,prepared,expected,entries,'synthetic-only')
            self.assertEqual(len(transport.publications),2)
            self.assertEqual(identity(local),ident(prepared['metadata']))
            manifest=load(transport.directory/'equivalence.json')
            self.assertIn('SH8 acceptance remains separate',manifest['acceptance'])
            self.assertEqual(manifest['local']['entries'],prepared['admitted']['entries'])

    def test_manifest_mutations_rejected_before_part_bodies(self):
        pending,pointer=self.pending(); entry=self.fixture.prepared['admitted']['entries'][0]
        mutations=[lambda p:p['proof'].update(bytes=1),lambda p:p['proof'].update(sha256='f'*64),lambda p:p['parts'].reverse(),lambda p:p['parts'].pop(),
                   lambda p:p['parts'].append(copy.deepcopy(p['parts'][0])),lambda p:p['parts'][0].update(offset=1),lambda p:p['parts'][0].update(sha256='a'*64),
                   lambda p:p['parts'][0]['asset'].update(url='https://example.invalid/asset'),lambda p:p['parts'][0]['asset'].update(state='new'),
                   lambda p:p['run'].update(head='f'*40),lambda p:p['run'].update(run_id='1'),lambda p:p['run'].update(attempt='2'),
                   lambda p:p.update(generation=2),lambda p:p['compiler'].update(sha256='f'*64),lambda p:p['job'].update(sha256='f'*64),
                   lambda p:p['profile'].update(producer_time_ms=1),lambda p:p['source_selector']['sources'].update(joy='f'*40),lambda p:p.update(status='fresh-verified'),
                   lambda p:p['production']['transport'].update(wire_bytes=1),lambda p:p['parts'][0].update(downloaded_verified=False)]
        for mutate in mutations:
            bad=copy.deepcopy(pending); mutate(bad)
            with self.subTest(mutation=mutate),self.assertRaises((ValueError,KeyError)):
                pending_manifest(bad,self.fixture.expected,entry)
        self.assertEqual(pending_manifest(pending,self.fixture.expected,entry),pending)

    def test_completion_and_retained_status_are_distinct(self):
        pending,pointer=self.pending(); entry=self.fixture.prepared['admitted']['entries'][0]
        r=load(self.fixture.source_dirs[(1,'verifier')]/'receipt.json'); comp=json.loads(self.fixture.assets[r['completion']['asset']['id']][1])
        completion_manifest(comp,self.fixture.expected,entry,pointer,pending)
        for field,value in [('status','fresh-verified-retained'),('status','pending-fresh-verification'),('schema','wrong')]:
            bad=copy.deepcopy(comp); bad[field]=value
            with self.assertRaises(ValueError): completion_manifest(bad,self.fixture.expected,entry,pointer,pending)
        bad=copy.deepcopy(comp); bad['verification']['prover_observations']={}
        with self.assertRaises(ValueError): completion_manifest(bad,self.fixture.expected,entry,pointer,pending)

    def test_exact_run_four_jobs_and_artifact_origin(self):
        run=self.fixture.api_values[f'repos/{REPO}/actions/runs/{RUN}']; jobs=self.fixture.api_values[f'repos/{REPO}/actions/runs/{RUN}/attempts/1/jobs?per_page=100']
        admit_run(run,jobs)
        for field,value in [('run_attempt',2),('status','in_progress'),('conclusion','failure'),('head_sha','f'*40),('event','workflow_dispatch')]:
            bad=dict(run); bad[field]=value
            with self.assertRaises(ValueError): admit_run(bad,jobs)
        bad=copy.deepcopy(jobs); bad['jobs'][0]['conclusion']='failure'
        with self.assertRaises(ValueError): admit_run(run,bad)
        bad=copy.deepcopy(jobs); bad['jobs'].pop()
        with self.assertRaises(ValueError): admit_run(run,bad)
        a=copy.deepcopy(self.fixture.artifact_rows[0]); artifact(a,a['name'])
        for field,value in [('expired',True),('url','https://example.invalid'),('digest','sha256:'+'z'*64)]:
            bad=dict(a); bad[field]=value
            with self.assertRaises(ValueError): artifact(bad,a['name'])

    def test_native_receipt_semantic_command_environment_and_hash_mutations(self):
        source=self.fixture.source_dirs[(1,'verifier')]; expected=self.fixture.expected; entry=self.fixture.prepared['admitted']['entries'][0]
        phase(source,expected,entry,'verifier')
        original=(source/'receipt.json').read_bytes()
        mutations=[lambda r:r.update(status='fresh-verified'),lambda r:r['proof_commands'][0]['environment'].update(GH_TOKEN='synthetic-secret'),
                   lambda r:r['proof_commands'][0]['command'].append('--foreign'),lambda r:r['proof_commands'][0].update(exit_code=1),
                   lambda r:r['proof_commands'][0]['inputs_after'][r['proof']['path']].update(sha256='f'*64),
                   lambda r:r['bootstrap'].clear(),lambda r:r['frozen_inputs_after'].clear(),lambda r:r['commands'].pop(),
                   lambda r:r['commands'][0].update(command=['false']),lambda r:r['source_inventory_identities'].clear()]
        try:
            for mutate in mutations:
                r=json.loads(original); mutate(r); source.joinpath('receipt.json').write_text(json.dumps(r))
                with self.subTest(mutation=mutate),self.assertRaises((ValueError,KeyError)): phase(source,expected,entry,'verifier')
        finally: source.joinpath('receipt.json').write_bytes(original)

    def test_archive_traversal_links_duplicates_and_expansion(self):
        with tempfile.TemporaryDirectory(prefix='adoption-archive-') as temp:
            root=Path(temp)
            for number,(name,mode) in enumerate([('../escape',0),('absolute/../escape',0),('link',0o120777)]):
                path=root/f'bad{number}.zip'
                with zipfile.ZipFile(path,'w') as z:
                    entry=zipfile.ZipInfo(name); entry.external_attr=mode<<16; z.writestr(entry,b'x')
                with self.assertRaises(ValueError): extract_zip(path,root/f'out{number}',lambda n:None)
            good=root/'good.zip'
            with zipfile.ZipFile(good,'w') as z:z.writestr('safe.json',b'{}')
            with patch('archives.MAX_EXPANSION',1),self.assertRaises(ValueError): extract_zip(good,root/'over',lambda n:None)
            badtar=root/'bad.tar.gz'
            with tarfile.open(badtar,'w:gz') as t:
                m=tarfile.TarInfo('evidence/link'); m.type=tarfile.SYMTYPE; m.linkname='/outside'; t.addfile(m)
            with self.assertRaises(ValueError): replay_tar(badtar,root,'receipt.json',lambda n:None)

    def test_order_whole_hash_and_failed_partial_preserved(self):
        with tempfile.TemporaryDirectory(prefix='adoption-parts-') as temp:
            p=Path(temp)/'chunk'; p.write_bytes(b'synthetic'); part=dict(sequence=0,offset=0,**identity(p)); r=Reconstruction()
            bad=dict(part,offset=1)
            with self.assertRaises(ValueError):r.append(p,bad)
            r.append(p,part)
            with self.assertRaises(ValueError):r.finish(dict(bytes=1,sha256='0'*64))
            self.assertTrue(p.exists())
            transport=SyntheticTransport(Path(temp)/'run',self.fixture)
            a,raw=next(iter(self.fixture.assets.values())); bad=dict(bytes=len(raw),sha256='f'*64)
            with self.assertRaises(ValueError):transport.download('bad',a,bad,chunk=True)
            self.assertEqual(transport.publications,[])

    def test_publication_requires_both_reconstructions(self):
        with tempfile.TemporaryDirectory(prefix='adoption-publish-') as temp:
            t=SyntheticTransport(Path(temp)/'run',self.fixture); p=t.directory/'file'; p.write_bytes(b'x')
            with self.assertRaises(ValueError): t.upload('no','wrong','name',digest(b'x'))
            t.receipt['entries']=[{'status':'full-byte-equivalence-passed'}]
            with self.assertRaises(ValueError): t.upload('one',p,'name',identity(p))
            self.assertFalse(t.publications)

    def test_real_file_size_overflow_is_bounded(self):
        with tempfile.TemporaryDirectory(prefix='adoption-overflow-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); gh=dict(path=str(python),**identity(python))
            t=Transport(root,gh,{},lambda:{})
            with self.assertRaises(ValueError):t.run('overflow',['-c','import os; os.write(1, b"x" * 8192); os.write(1, b"x")'],maximum=4096)
            self.assertLessEqual((root/'overflow.stdout').stat().st_size,4096)
            self.assertIn('error',t.receipt['commands'][0]); self.assertNotEqual(t.receipt['commands'][0]['exit_code'],0)

    def test_real_success_drains_delayed_stderr_and_records_output(self):
        with tempfile.TemporaryDirectory(prefix='adoption-real-child-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            t.run('success',['-c','import os,time; os.write(2,b"before"); time.sleep(0.3); os.write(2,b"after"); os.write(1,b"done")'],maximum=4096)
            self.assertEqual((root/'success.stdout').read_bytes(),b'done')
            self.assertEqual((root/'success.stderr').read_bytes(),b'beforeafter')
            self.assertEqual(t.receipt['commands'][0]['exit_code'],0)

    def test_real_stderr_overflow_is_hard_capped(self):
        with tempfile.TemporaryDirectory(prefix='adoption-stderr-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            with self.assertRaises(ValueError):t.run('stderr-overflow',['-c','import os; os.write(2,b"x"*(9*1024*1024))'],maximum=16*MIB)
            self.assertEqual((root/'stderr-overflow.stderr').stat().st_size,8*MIB)
            self.assertIn('hard stderr byte cap',t.receipt['commands'][0]['error'])

    def test_failed_readback_preserves_owned_chunk_and_stops_publication(self):
        with tempfile.TemporaryDirectory(prefix='adoption-failed-body-') as temp:
            t=SyntheticTransport(Path(temp)/'run',self.fixture)
            pending,_=self.pending(); part=pending['parts'][0]; number=part['asset']['id']
            previous=self.fixture.assets[number]
            try:
                self.fixture.assets[number]=(previous[0],b'x')
                with self.assertRaises(ValueError):t.download('failed-body',part['asset'],ident(part),chunk=True)
                self.assertTrue((t.directory/'chunk').exists())
                self.assertEqual((t.directory/'chunk').read_bytes(),b'x')
                self.assertFalse(t.publications)
            finally:self.fixture.assets[number]=previous

    def test_altered_original_local_metadata_refuses_publication(self):
        with tempfile.TemporaryDirectory(prefix='adoption-metadata-') as temp:
            t=SyntheticTransport(Path(temp)/'run',self.fixture); t.receipt['status']='both-full-reconstructions-passed'
            path=Path(temp)/'original'; path.write_bytes(b'original'); prepared={'metadata':dict(path=str(path),**identity(path))}
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):adopt.publish(t,prepared,{},[],'synthetic')
            self.assertFalse(t.publications)

    def test_hidden_tar_headers_and_sidecar_reservations_bounded(self):
        with tempfile.TemporaryDirectory(prefix='adoption-bounds-') as temp:
            root=Path(temp); t=SyntheticTransport(root/'run',self.fixture)
            with patch('transport.SIDECARS',1),self.assertRaises(ValueError):t.budget()
            with patch('transport.shutil.disk_usage',return_value=type('Disk',(),{'free':1})()),self.assertRaises(ValueError):t.budget(1)
            archive=root/'metadata.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                m=tarfile.TarInfo('evidence/x'); m.size=1; tar.addfile(m,io.BytesIO(b'x'))
            with patch('archives.MAX_TAR_STREAM',1024),self.assertRaises(ValueError):replay_tar(archive,root,'receipt.json',lambda n:None)

    def test_real_deadline_terminates_owned_child(self):
        with tempfile.TemporaryDirectory(prefix='adoption-timeout-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            original_tick=t.tick
            ticks=iter([original_tick]*3+[original_tick+121]*100)
            with patch('transport.time.monotonic',side_effect=lambda:next(ticks)),self.assertRaises(ValueError):
                t.run('timeout',['-c','import time; time.sleep(60)'],maximum=4096)
            self.assertIn('deadline',t.receipt['commands'][0]['error'])
            self.assertLess(t.receipt['commands'][0]['exit_code'],0)

    def test_exited_leader_orphan_stderr_holder_is_killed(self):
        with tempfile.TemporaryDirectory(prefix='adoption-orphan-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            clock=time.monotonic; start=clock()
            script='import os,signal,time; p=os.fork();\nif p==0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN); os.write(2,b"orphan ready"); time.sleep(60)\nelse:\n os.write(1,str(p).encode()); os._exit(0)'
            with patch('transport.time.monotonic',side_effect=lambda:clock()+(121 if clock()-start>0.5 else 0)),self.assertRaises(ValueError):
                t.run('orphan',['-c',script],maximum=4096)
            row=t.receipt['commands'][0]
            self.assertEqual(row['exit_code'],0)  # Leader exited before the descendant-held pipe deadline.
            self.assertIn('deadline',row['error']); self.assertEqual(row['cleanup']['signals'],['TERM','KILL'])
            self.assertTrue(row['cleanup']['group_empty'])
            with self.assertRaises(ProcessLookupError):os.kill(int((root/'orphan.stdout').read_text()),0)

    def test_expired_total_clock_keeps_reserved_terminal_failure(self):
        with tempfile.TemporaryDirectory(prefix='adoption-expired-terminal-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            t.tick-=43201
            with self.assertRaisesRegex(ValueError,'12-hour'):
                try:t.run('must-not-start',['-c','raise SystemExit(99)'],maximum=4096)
                except ValueError as error:
                    t.failure(str(error))
                    try:t.persist()
                    except ValueError:pass
                    raise
            final=load(root/'terminal-failure.json')
            self.assertEqual(final['status'],'failed'); self.assertIn('12-hour',final['error'])
            self.assertEqual(final['commands_observed'],0); self.assertEqual((root/'terminal-failure.json').stat().st_size,MIB)
            self.assertEqual(load(root/'receipt.json')['status'],'running')  # Explicit terminal record supersedes this earlier snapshot.
            with self.assertRaisesRegex(ValueError,'cannot start'):t.run('no-retry',['-c','pass'])

    def test_actual_sidecar_boundary_keeps_reserved_terminal_failure(self):
        with tempfile.TemporaryDirectory(prefix='adoption-sidecar-terminal-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            used=sum(p.stat().st_size for p in root.iterdir())
            with (root/'owned-sparse-sidecar').open('xb') as output:output.truncate(512*MIB-used-1)
            t.budget()
            with self.assertRaisesRegex(ValueError,'512 MiB'):
                try:t.persist()
                except ValueError as error:
                    t.failure(str(error))
                    raise
            final=load(root/'terminal-failure.json'); self.assertEqual(final['status'],'failed'); self.assertIn('512 MiB',final['error'])
            self.assertLessEqual(sum(p.stat().st_size for p in root.iterdir()),512*MIB)
            before=identity(root/'terminal-failure.json'); t.failure('later finalizer error')
            self.assertEqual(identity(root/'terminal-failure.json'),before)
            self.assertFalse((root/'terminal-reserve.json').exists())
            with self.assertRaisesRegex(ValueError,'cannot start'):t.run('no-retry',['-c','pass'])

    def test_disappearing_probe_cleans_known_owned_live_child(self):
        with tempfile.TemporaryDirectory(prefix='adoption-probe-live-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            with patch('transport.os.getpgid',side_effect=ProcessLookupError),self.assertRaisesRegex(ValueError,'unobservable live group leader'):
                t.run('probe-live',['-c','import time; time.sleep(60)'],maximum=4096)
            row=t.receipt['commands'][0]
            self.assertEqual(row['owned_group'],row['pid']); self.assertTrue(row['cleanup']['group_empty'])
            self.assertIn('TERM',row['cleanup']['signals']); self.assertLess(row['exit_code'],0)
            self.assertEqual(load(root/'terminal-failure.json')['status'],'failed')

    def test_rapid_exited_leader_probe_retains_ownership(self):
        with tempfile.TemporaryDirectory(prefix='adoption-probe-exited-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            def vanished(_pid):
                time.sleep(0.5)
                raise ProcessLookupError()
            with patch('transport.os.getpgid',side_effect=vanished):
                t.run('probe-exited',['-c','import os; os.write(1,b"done")'],maximum=4096)
            row=t.receipt['commands'][0]
            self.assertEqual(row['exit_code'],0); self.assertEqual(row['ownership_probe'],'leader-already-exited')
            self.assertEqual(row['owned_group'],row['pid']); self.assertEqual((root/'probe-exited.stdout').read_bytes(),b'done')

    def test_fixed_draft_tag_default_and_membership_guards(self):
        with tempfile.TemporaryDirectory(prefix='adoption-guards-') as temp:
            root=Path(temp); python=Path(sys.executable).resolve(); t=Transport(root,dict(path=str(python),**identity(python)),{},lambda:{})
            release=dict(id=389977897,draft=True,tag_name='candidate-20260916.1',published_at=None)
            repo=dict(full_name=REPO,default_branch='master'); ref=dict(ref='refs/heads/master',object=dict(type='commit',sha='a'*40)); current={'release':release,'repo':repo,'ref':ref,'tag':{'status':'404'},'assets':[]}
            def api(label,endpoint,maximum=8*MIB):
                return copy.deepcopy(current['release' if '/releases/' in endpoint else 'ref' if '/git/ref/heads/' in endpoint else 'repo'])
            def run(label,args,expected_exit=0,**kw):
                p=root/(label+'.json'); save_new(p,current['tag' if label.endswith('-tag') else 'assets']); return p
            with patch.object(t,'api',api),patch.object(t,'run',run):
                t.draft('valid')
                for number,(key,field,value) in enumerate([('release','draft',False),('release','published_at','now'),('release','id',1),('tag','status','200'),('ref','object',dict(type='commit',sha='b'*40))]):
                    old=copy.deepcopy(current[key]); current[key][field]=value
                    with self.assertRaises(ValueError):t.draft('bad'+str(number))
                    current[key]=old
                a=asset(1,'synthetic',b'x')
                with self.assertRaises(ValueError):t.member('missing',a,digest(b'x'))


if __name__=='__main__':
    unittest.main()
