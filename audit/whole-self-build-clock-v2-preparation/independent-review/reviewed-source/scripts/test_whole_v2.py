"""Offline orchestration and bounded transport checks; no compiler execution."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import whole_v2_common as common
import whole_v2_transport as transport
import whole_self_inputs as frozen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('whole_v2_driver', ROOT / 'scripts/whole-v2.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def asset(number, name, value):
    return dict(id=number, name=name, size=value['bytes'], state='uploaded', digest='sha256:'+value['sha256'],
                url=f'https://api.github.com/repos/cyberia-to/trisha/releases/assets/{number}',
                browser_download_url='https://github.com/cyberia-to/trisha/releases/download/test/'+name)


def fixture(directory, chunk=7):
    work, results = directory / 'work', directory / 'results'; work.mkdir(); results.mkdir()
    compiler, job = directory / 'compiler', directory / 'job'; compiler.write_bytes(b'compiler'); job.write_bytes(b'job')
    report = dict(phase='verifier', status='prepared', generation=1, run=dict(repository='cyberia-to/trisha',run_id='1',attempt='1',head='a'*40),
                  profile=common.profile(ROOT, enabled=False), source_selector=dict(sources={'joy':'a'*40}), input_asset={'asset_id':604704433})
    state = SimpleNamespace(work=work, results=results, report=report, paths=lambda:(Path(sys.executable).resolve(),compiler,job), persist=lambda:None)
    data=b'complete public certificate fixture'; source=directory/'source';source.write_bytes(data)
    parts, source_parts=[],{}
    with source.open('rb') as stream:
        offset=0
        while offset<len(data):
            path=directory/f'chunk{len(parts)}';value=transport.write_chunk(stream,path,chunk)
            server=asset(len(parts)+1,path.name,value);source_parts[server['id']]=path
            parts.append(dict(sequence=len(parts),offset=offset,**value,asset=server,downloaded_verified=True));offset+=value['bytes']
    pending=dict(schema='trident/whole-proof-pending/v2',status='pending-fresh-verification',
                 **{k:report[k] for k in ('run','generation','profile','source_selector','input_asset')},
                 proof=frozen.identity(source),parts=parts,downloaded_reconstruction=frozen.identity(source),
                 compiler=frozen.identity(compiler),job=frozen.identity(job),production={'records':1})
    handoff=directory/'handoff';handoff.mkdir();frozen_data=json.dumps(pending).encode();(handoff/'pending.json').write_bytes(frozen_data)
    expected=frozen.identity(handoff/'pending.json');server=asset(100,'pending.json',expected)
    pointer=dict(schema='trident/whole-proof-handoff/v2',status='pending-fresh-verification',run=report['run'],generation=1,manifest=expected,asset=server)
    (handoff/'pointer.json').write_text(json.dumps(pointer));source_parts[100]=handoff/'pending.json'
    return state,pending,pointer,handoff,source_parts,data


class ProfileTests(unittest.TestCase):
    def test_disabled_profile_and_exact_clocks(self):
        value=common.profile(ROOT,enabled=False)
        self.assertEqual(value['producer_time_ms'],14400000)
        self.assertEqual(value['verifier_time_ms'],7200000)
        with tempfile.TemporaryDirectory() as tmp:
            checkout=Path(tmp);(checkout/'.github').mkdir()
            path=checkout/'.github/whole-v2-profile.json'
            path.write_text(json.dumps(dict(value,enabled=False)))
            with self.assertRaises(ValueError): common.profile(checkout)
            path.write_text(json.dumps(dict(value,enabled=True)))
            self.assertTrue(common.profile(checkout)['enabled'])
        for phase in ('producer','verifier'):
            actual=common.flags(phase,value);before=frozen.flags()
            changed=[i for i,(a,b) in enumerate(zip(actual,before)) if a!=b]
            self.assertEqual(changed,[] if phase=='verifier' else [before.index('--time-ms')+1])
            self.assertEqual(len(actual),len(before))

    def test_activation_requires_exact_authorized_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.github').mkdir()
            selected=dict(format='whole-proof-clock-v2-activation',repository='cyberia-to/trisha',branch='test/0.4-whole-self-build-ci',push_authorized=True,pending_transport_authorized=True)
            path=root/'.github/whole-v2-activation.json';path.write_text(json.dumps(selected))
            env=dict(GITHUB_REPOSITORY='cyberia-to/trisha',GITHUB_EVENT_NAME='push',GITHUB_REF='refs/heads/test/0.4-whole-self-build-ci',GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='2',GITHUB_SHA='a'*40)
            with patch.dict(os.environ,env,clear=True): self.assertEqual(common.authorization(root)['attempt'],'2')
            for key,value in [('GITHUB_REF','refs/heads/master'),('GITHUB_REPOSITORY','foreign/repo'),('GITHUB_EVENT_NAME','pull_request'),('GITHUB_RUN_ID','0'),('GITHUB_SHA','abcd')]:
                with patch.dict(os.environ,dict(env,**{key:value}),clear=True),self.assertRaises(ValueError): common.authorization(root)
            path.write_text(json.dumps(dict(selected,pending_transport_authorized=False)))
            with patch.dict(os.environ,env,clear=True),self.assertRaises(ValueError): common.authorization(root)

    def test_bootstrap_covers_both_workflows_and_merged_source_pin(self):
        b=common.bootstrap(ROOT)
        for name in ('.github/workflows/whole-self-build-v2.yml','.github/workflows/whole-self-build-v2-generation.yml',
                     '.github/whole-v2-profile.json','.github/whole-v2-sources.json','.github/whole-v2-activation.json',
                     'scripts/whole-v2.py','scripts/whole_v2_common.py','scripts/whole_v2_transport.py'):
            self.assertEqual(b[name],frozen.identity(ROOT/name))
        selected=common.native.selector(ROOT/'.github/whole-v2-sources.json')
        original=common.native.selector(ROOT/'.github/whole-self-build-sources.json')
        self.assertEqual(selected['sources']['joy'],'dd61df9128f6da1f97d4698f45f154f05312fe51')
        self.assertEqual({k:v for k,v in selected['sources'].items() if k!='joy'},{k:v for k,v in original['sources'].items() if k!='joy'})


class PendingTests(unittest.TestCase):
    def test_manifest_admission_checks_every_binding_and_chunk_order(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(transport,'CHUNK',7):
            state,pending,_,_,_,_=fixture(Path(tmp));transport.validate_pending(pending,state)
            variants=[]
            for key,value in [('status','fresh-verified'),('generation',2),('run',{}),('source_selector',{}),('profile',{}),('input_asset',{}),('compiler',{}),('job',{}),('downloaded_reconstruction',{})]:
                p=copy.deepcopy(pending);p[key]=value;variants.append(p)
            for action in ('reverse','omit','duplicate','offset','foreign','not-uploaded','size','readback','digest'):
                p=copy.deepcopy(pending)
                if action=='reverse': p['parts'].reverse()
                elif action=='omit': p['parts'].pop()
                elif action=='duplicate': p['parts'][1]=copy.deepcopy(p['parts'][0])
                elif action=='offset': p['parts'][1]['offset']+=1
                elif action=='foreign': p['parts'][0]['asset']['url']='https://evil.test/asset/1'
                elif action=='not-uploaded': p['parts'][0]['asset']['state']='new'
                elif action=='size': p['proof']['bytes']=PROFILE_WIRE+1
                elif action=='readback': p['parts'][0]['downloaded_verified']=False
                elif action=='digest': p['parts'][0]['sha256']='0'*64
                variants.append(p)
            for p in variants:
                with self.subTest(p=p.get('status')),self.assertRaises((ValueError,KeyError)): transport.validate_pending(p,state)

    def test_handoff_is_small_same_run_and_exactly_bound(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(transport,'CHUNK',7):
            state,pending,pointer,handoff,_,_=fixture(Path(tmp))
            self.assertEqual(driver.admit_handoff(state,handoff),(pointer,pending))
            pointer['run']=dict(pointer['run'],attempt='2');(handoff/'pointer.json').write_text(json.dumps(pointer))
            with self.assertRaises(ValueError): driver.admit_handoff(state,handoff)
            (handoff/'extra').write_bytes(b'')
            with self.assertRaises(ValueError): driver.admit_handoff(state,handoff)

    def test_reconstruction_rejects_corrupt_and_reordered_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,pending,_,_,paths,data=fixture(Path(tmp))
            reconstruction=transport.Reconstruction();output=io.BytesIO()
            for part in pending['parts']: reconstruction.append(paths[part['asset']['id']],{k:part[k] for k in ('bytes','sha256')},output)
            self.assertEqual(reconstruction.finish(pending['proof']),pending['proof']);self.assertEqual(output.getvalue(),data)
            reconstruction=transport.Reconstruction()
            for part in reversed(pending['parts']): reconstruction.append(paths[part['asset']['id']],{k:part[k] for k in ('bytes','sha256')})
            with self.assertRaises(ValueError): reconstruction.finish(pending['proof'])
            paths[1].write_bytes(b'changed')
            with self.assertRaises(ValueError): transport.Reconstruction().append(paths[1],{k:pending['parts'][0][k] for k in ('bytes','sha256')})

    def test_download_authenticates_whole_stream_before_verifier_state(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(transport,'CHUNK',7):
            state,pending,_,handoff,paths,data=fixture(Path(tmp))
            class FakeTransport:
                def __init__(self,_,label): self.directory=state.work/('transport-'+label);self.directory.mkdir()
                def download(self,label,server,expected):
                    p=self.directory/(label+'.download');shutil.copyfile(paths[server['id']],p)
                    if frozen.identity(p)!=expected: raise ValueError('downloaded bytes')
                    return p
                def disk_guard(self,*_): pass
                def finish(self,_): pass
                def failed(self): pass
            with patch.object(driver,'Transport',FakeTransport),patch.object(driver.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)):
                driver.download(state,handoff)
            self.assertEqual(state.report['status'],'downloaded-pending-verification')
            self.assertEqual(Path(state.report['proof']['path']).read_bytes(),data)
            self.assertNotIn('verification',state.report)

    def test_completion_requires_actual_fresh_success_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            state,*_=fixture(Path(tmp))
            for status in ('prepared','produced-pending-fresh-verification','pending-staged','downloaded-pending-verification','failed'):
                state.report['status']=status
                with patch.object(driver,'Transport',side_effect=AssertionError('must not publish')),self.assertRaises(ValueError): driver.complete(state)

    def test_fresh_verifier_checks_semantics_and_producer_counters_before_completion(self):
        old=dict(program_particle='p',input_particle='i',output_particle='o',charged_reductions=3,
                 peak_frames=5,compaction={'evaluator_checkpoints':8},compiler_job={'complete':True})
        checked=dict(program_particle='p',input_particle='i',output_particle='o',charged_reductions=3,
                     logical_peak_frames=5,expanded_steps=7,compiler_job={'complete':True},
                     format='joy-nox-disclosed-compiler-v1',disclosure='complete public witness',
                     physical_resource_claim='unattested',invocations=2,semantic_events=3,records=4,transport={'frames':1})
        for changed in ({'output_particle':'other'},{'charged_reductions':4},{'records':5},{'prover_observations':{}},
                        {'compiler_job':{'complete':False}},{'expanded_steps':8}):
            with tempfile.TemporaryDirectory() as tmp:
                state,pending,_,_,_,_=fixture(Path(tmp))
                state.package=state.work/'frozen';(state.package/'inputs').mkdir(parents=True)
                (state.package/'inputs/accepted-c2-step.json').write_text(json.dumps({'execution':{'execution':old}}))
                state.report.update(status='downloaded-pending-verification',proof=dict(path=str(Path(tmp)/'source'),**pending['proof']),production=checked)
                result=dict(ok=True,schema='joy/artifact-verification/v1',verification=dict(checked,**changed))
                with patch.object(driver,'bounded',return_value=result),self.assertRaises(ValueError): driver.verify(state)
                self.assertNotIn('verification',state.report)
                self.assertNotEqual(state.report['status'],'fresh-verified')

    def test_fixed_server_identity_rejects_origin_state_digest(self):
        value=dict(bytes=7,sha256='a'*64);a=asset(1,'part',value);transport.check_asset(a,'part',value)
        for changed in ({'url':'https://api.github.com/repos/other/repo/releases/assets/1'},{'state':'new'},{'id':True},{'digest':'sha256:'+'b'*64},{'name':'other'},{'size':8}):
            with self.subTest(changed=changed),self.assertRaises(ValueError): transport.check_asset(dict(a,**changed),'part',value)


class RuntimeTests(unittest.TestCase):
    def test_bounded_child_has_empty_path_and_retained_identity_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state,*_=fixture(Path(tmp));state.report.update(phase='verifier',proof_commands=[])
            _,compiler,job=state.paths()
            # Plain awk exposes the exec environment; macOS framework Python adds
            # __CF_USER_TEXT_ENCODING during its own startup.
            probe=Path('/usr/bin/awk').resolve()
            state.paths=lambda:(probe,compiler,job)
            program='BEGIN { printf "{"; sep=""; for (k in ENVIRON) { printf "%s\\\"%s\\\":\\\"%s\\\"", sep, k, ENVIRON[k]; sep="," } print "}" }'
            with patch.object(common.shutil,'disk_usage',return_value=SimpleNamespace(free=9*1024**3)),patch.dict(os.environ,{'GH_TOKEN':'fixture-only-token','RUNNER_TRACKING_ID':'fixture-tracking'}):
                value=common.bounded(state,[probe,program],[compiler])
            expected={'PATH':'','LANG':'C.UTF-8','RUNNER_TRACKING_ID':'fixture-tracking'}
            self.assertEqual(value,expected)
            row=state.report['proof_commands'][0];self.assertEqual(row['environment'],expected);self.assertNotIn('GH_TOKEN',row['environment'])
            self.assertEqual(row['status'],'passed');self.assertEqual(row['binary_before'],row['binary_after']);self.assertEqual(row['inputs_before'],row['inputs_after'])

    def test_outer_clock_failure_preserves_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state,*_=fixture(Path(tmp));state.report.update(phase='verifier',proof_commands=[])
            state.report['profile']=dict(state.report['profile'],verifier_outer_seconds=0)
            with patch.object(common.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),self.assertRaises(ValueError):
                common.bounded(state,[sys.executable,'-c','import time; time.sleep(10)'],[])
            row=state.report['proof_commands'][0];self.assertEqual(row['status'],'failed');self.assertEqual(row['resource_stop'],'wall')

    def test_producer_retains_original_48_gib_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            state,*_=fixture(Path(tmp));state.report.update(phase='producer',proof_commands=[])
            with patch.object(common.shutil,'disk_usage',return_value=SimpleNamespace(free=47*1024**3)),self.assertRaisesRegex(ValueError,'free-start'):
                common.bounded(state,[sys.executable,'-c','raise Exception("must not execute")'],[])
            self.assertEqual(state.report['proof_commands'],[])


class TransportGuardTests(unittest.TestCase):
    def test_actual_child_file_size_overflow_is_bounded_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GH_TOKEN':'fixture-only-token'}):
            state,*_=fixture(Path(tmp));client=transport.Transport(state,'overflow')
            command=[str(Path(sys.executable).resolve()),'-c','import os; os.write(1,b"x"*4096); os.write(1,b"y"*4096)']
            with patch.object(transport.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),self.assertRaises(ValueError):
                client.run('actual-overflow',command,cap=64)
            row=client.record['commands'][0]
            self.assertNotEqual(row['exit_code'],0)
            self.assertLessEqual(row['stdout']['bytes'],64);self.assertLessEqual(row['stderr']['bytes'],64)
            self.assertEqual(row['stdout'],frozen.identity(state.results/'overflow-actual-overflow.stdout'))
            self.assertEqual(row['stderr'],frozen.identity(state.results/'overflow-actual-overflow.stderr'))

    def test_fixed_draft_requires_unpublished_release_and_absent_tag(self):
        release=dict(id=transport.RELEASE,draft=True,tag_name=transport.TAG,published_at=None)
        variants=[(release,{'status':'404'},[[asset(1,'part',dict(bytes=1,sha256='a'*64))]],True)]
        for changed in ({'draft':False},{'published_at':'2026-10-02T00:00:00Z'},{'tag_name':'other'},{'id':1}):
            variants.append((dict(release,**changed),{'status':'404'},[],False))
        variants.extend([(release,{'status':'403'},[],False),(release,{'object':{'sha':'a'*40}},[],False),
                         (release,{'status':'404'},[[{'id':1}],[{'id':1}]],False)])
        for selected,tag,pages,passed in variants:
            with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GH_TOKEN':'fixture-only-token'}):
                state,*_=fixture(Path(tmp));client=transport.Transport(state,'draft');calls=[]
                def request(name,command,expected_exit=0,**_):
                    calls.append((name,command,expected_exit))
                    data=tag if name.endswith('-tag') else pages if name.endswith('-assets') else selected
                    path=state.results/(name+'.json');path.write_text(json.dumps(data));return path
                with patch.object(client,'run',side_effect=request):
                    if passed:
                        self.assertEqual(len(client.draft('guard')),1)
                        self.assertIn('--paginate',calls[-1][1]);self.assertIn('--slurp',calls[-1][1])
                        self.assertEqual(calls[1][2],1)
                    else:
                        with self.assertRaises(ValueError):client.draft('guard')
                self.assertFalse(any('POST' in c[1] for c in calls))

    def test_download_requires_exact_fixed_draft_membership_before_fetch(self):
        expected=dict(bytes=7,sha256='a'*64);server=asset(1,'part',expected)
        for listing in ([],[asset(2,'part',expected)],[server,server],
                        [dict(server,digest='sha256:'+'b'*64)],[dict(server,state='new')]):
            with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'GH_TOKEN':'fixture-only-token'}):
                state,*_=fixture(Path(tmp));client=transport.Transport(state,'membership')
                with patch.object(client,'draft',return_value=listing),patch.object(client,'run',side_effect=AssertionError('must not fetch')),self.assertRaises(ValueError):
                    client.download('part',server,expected)


PROFILE_WIRE=frozen.PROFILE['wire_bytes']
if __name__=='__main__': unittest.main()
