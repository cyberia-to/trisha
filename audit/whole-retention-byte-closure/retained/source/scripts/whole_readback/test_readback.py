"""Offline small fixtures and real bounded child failures; no whole proof reads."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import gate
gate.frozen()
from bounded import Readback, read_only
from common import identity
from contracts import MIB
from fixtures import Fixture
from test_adoption import SyntheticTransport
import remote
import worker
from local_admission import compare


class ReadbackTests(unittest.TestCase):
    def test_only_get_shapes(self):
        accepted=[['api','repos/cyberia-to/trisha'],['api','--paginate','--slurp','repos/cyberia-to/trisha/releases/389977897/assets?per_page=100'],['api','repos/cyberia-to/trisha/releases/assets/1','-H','Accept: application/octet-stream']]
        for args in accepted:read_only(args)
        rejected=[['api','--method','POST','repos/cyberia-to/trisha'],['api','repos/cyberia-to/trisha','--input','x'],['api','https://uploads.github.com/repos/cyberia-to/trisha/releases/1/assets'],['api','repos/foreign/repo'],['release','upload','x'],['api','repos/cyberia-to/trisha','-f','a=b']]
        for args in rejected:
            with self.subTest(args=args),self.assertRaises(ValueError):read_only(args)

    def fixture(self,root):
        (root/'fixture').mkdir();f=Fixture(root/'fixture');t=SyntheticTransport(root/'observed',f);e=remote.admit(t,f.expected,f.prepared);return f,t,e

    def test_all22_actual_small_bodies_and_both_wholes(self):
        with tempfile.TemporaryDirectory() as temp:
            f,t,e=self.fixture(Path(temp));worker.replay(t,e)
            self.assertEqual([x['status'] for x in t.receipt['entries']],['ordered-whole-bytes-passed']*2)
            self.assertEqual(sum(len(x['parts']) for x in t.receipt['entries']),22)
            self.assertFalse((t.directory/'chunk').exists())

    def test_order_mismatch_keeps_failed_owned_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            f,t,e=self.fixture(Path(temp));e[0]['parts'][0]['sequence']=1
            with self.assertRaises(ValueError):worker.replay(t,e)
            self.assertTrue((t.directory/'chunk').exists())
            self.assertNotEqual(t.receipt['entries'][0]['status'],'ordered-whole-bytes-passed')

    def test_wrong_whole_does_not_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            f,t,e=self.fixture(Path(temp));e[0]['proof']['sha256']='0'*64
            with self.assertRaises(ValueError):worker.replay(t,e)
            self.assertEqual(len(t.receipt['entries']),1)

    def test_missing_part_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as temp:
            f,t,e=self.fixture(Path(temp));e[1]['parts'].pop();before=len(t.downloads)
            with self.assertRaises(ValueError):worker.replay(t,e)
            self.assertEqual(len(t.downloads),before)

    def transport(self,root,body):
        executable=root/'fake-gh';executable.write_text('#!'+sys.executable+'\n'+body);executable.chmod(0o700);out=root/'out';out.mkdir()
        with patch.object(Readback,'sample',lambda self:None):t=Readback(out,dict(path=str(executable),**identity(executable)),{},lambda:{})
        return t

    def test_real_stdout_size_bound_and_failure_record(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(Readback,'sample',lambda self:None):
            t=self.transport(Path(temp),"import os\nfor _ in range(2):os.write(1,b'x'*4096)\n")
            with self.assertRaises(ValueError):t.run('overflow',['api','repos/cyberia-to/trisha'],maximum=128)
            self.assertLessEqual((t.directory/'overflow.stdout').stat().st_size,128)
            self.assertEqual(json.loads((t.directory/'terminal-failure.json').read_text())['status'],'failed')
            with self.assertRaises(ValueError):t.run('after',['api','repos/cyberia-to/trisha'])

    def test_real_stderr_bound_and_failure_record(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(Readback,'sample',lambda self:None):
            t=self.transport(Path(temp),"import os\nfor _ in range(160):os.write(2,b'x'*65536)\n")
            with self.assertRaises(ValueError):t.run('stderr',['api','repos/cyberia-to/trisha'],maximum=MIB)
            self.assertEqual((t.directory/'stderr.stderr').stat().st_size,8*MIB)
            self.assertEqual(t.receipt['status'],'failed')

    def test_remote_upload_unavailable(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(Readback,'sample',lambda self:None):
            t=self.transport(Path(temp),'pass\n')
            with self.assertRaises(ValueError):t.upload('x','x','x',{})
            self.assertEqual(t.receipt['commands'],[])

    def test_deadline_failure_uses_reserved_evidence(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(Readback,'sample',lambda self:None):
            t=self.transport(Path(temp),'pass\n');t.tick-=5401
            with self.assertRaises(ValueError):t.budget()
            t.failure('original deadline');record=json.loads((t.directory/'terminal-failure.json').read_text())
            self.assertEqual(record['error'],'original deadline');self.assertEqual(record['schema'],'trident/remote-byte-replay-terminal-failure/v1')

    def test_local_before_after_requires_actual_success_and_identity(self):
        before=dict(schema='trident/local-certificate-byte-closure/v1',status='passed-complete-local-scan',started_ns=1,ended_ns=2,original_helper_sources={},local_preparation={'sha256':'x'},prepared={'proof':'actual synthetic'})
        after=copy.deepcopy(before);after.update(started_ns=3,ended_ns=4);compare(before,after)
        for key in ('status','local_preparation','prepared'):
            bad=copy.deepcopy(after);bad[key]='changed'
            with self.subTest(key=key),self.assertRaises(ValueError):compare(before,bad)


if __name__=='__main__':unittest.main()
