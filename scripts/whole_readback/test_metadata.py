"""Final archive ceiling, pre-body capacity, and structural resource controls."""
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
from common import save_new, identity
from contracts import MIB
from metadata import PROFILE, reserve, resources
import packing
from bounded import Readback


class MetadataTests(unittest.TestCase):
    def transport(self,root,body):
        executable=root/'fake-gh';executable.write_text('#!'+sys.executable+'\n'+body);executable.chmod(0o700)
        data=root/'data';data.mkdir();t=Readback(data,dict(path=str(executable),**identity(executable)),gate.sources(),gate.sources)
        with (data/'existing-metadata').open('xb') as stream:stream.truncate(110*MIB)
        return t

    def test_membership_growth_is_rechecked_before_actual_body(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(Readback,'sample',lambda self:None):
            root=Path(temp);marker=root/'body-executed';t=self.transport(root,'from pathlib import Path\nPath('+repr(str(marker))+').write_text("ran")\n')
            reserve(t.directory,t.sources,1,0)  # The early pre-membership observation passes.
            def membership(*args):
                with (t.directory/'membership-growth').open('xb') as stream:stream.truncate(8*MIB)
            with patch.object(t,'member',side_effect=membership),self.assertRaisesRegex(ValueError,'reserved observation capacity'):
                t.download('c1-part-0000',{'id':1},{'bytes':1,'sha256':'0'*64},chunk=True)
            self.assertFalse(marker.exists());self.assertFalse((t.directory/'chunk').exists());self.assertEqual(t.receipt['commands'],[])

    def test_actual_body_stderr_growth_preserves_capacity_failure(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(Readback,'sample',lambda self:None):
            t=self.transport(Path(temp),'import os\nos.write(2,b"x"*(7*1024*1024))\nos.write(1,b"x")\n')
            with self.assertRaisesRegex(ValueError,'reserved observation capacity'):
                t.run('c1-part-0000-download',['api','repos/cyberia-to/trisha/releases/assets/1','-H','Accept: application/octet-stream'],output=t.directory/'chunk',maximum=1,data=True)
            self.assertEqual(t.receipt['status'],'failed');self.assertTrue((t.directory/'terminal-failure.json').exists())
            self.assertLessEqual((t.directory/'c1-part-0000-download.stderr').stat().st_size,8*MIB)
            self.assertEqual(t.receipt['metadata_reservations'][0]['boundary'],'after-membership-before-body')

    def test_actual_over128_metadata_refused_before_packing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=root/'data';data.mkdir();save_new(data/'receipt.json',{'status':'synthetic'})
            with (data/'large-synthetic-metadata').open('xb') as stream:stream.truncate(135*MIB)
            class T:
                directory=data;tick=0
                def sample(self):pass
                def budget(self,n=0):pass
            with self.assertRaisesRegex(ValueError,'bounded metadata membership'):packing.pack(T(),root/'artifact/evidence.zip')
            self.assertFalse((root/'artifact').exists());self.assertEqual((data/'large-synthetic-metadata').stat().st_size,135*MIB)

    def test_capacity_is_reserved_before_any_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);save_new(root/'receipt.json',{'status':'synthetic'})
            sources={'source.py':dict(bytes=123,sha256='0'*64)};row=reserve(root,sources,1,0)
            self.assertEqual(row['required_bytes'],10*MIB+123)
            self.assertEqual(row['reserved']['source_copies'],123)
            with (root/'existing-sidecars').open('xb') as stream:stream.truncate(119*MIB)
            with self.assertRaisesRegex(ValueError,'reserved observation capacity'):reserve(root,sources,1,0)
            self.assertFalse((root/'chunk').exists())

    def test_resources_refuse_impossible_rows_for_both_phases(self):
        sample=dict(time_ns=5,rss_bytes=10,processes=[dict(pid=10,ppid=1,pgid=10,rss_bytes=10)])
        for phase in (False,True):
            resources([sample],10,1,9,10,sample,packing=phase)
            changes=[lambda s:s['processes'][0].update(rss_bytes=-1),lambda s:s['processes'][0].update(pid=True),
                     lambda s:s['processes'].append(copy.deepcopy(s['processes'][0])),lambda s:s.update(rss_bytes=-1),
                     lambda s:s['processes'][0].update(ppid=-1),lambda s:s.update(time_ns=True)]
            for change in changes:
                bad=copy.deepcopy(sample);change(bad)
                with self.subTest(packing=phase,change=change),self.assertRaises(ValueError):resources([bad],10,1,9,10,bad,packing=phase)

    def test_exact_declared_profile_matches_selector(self):
        self.assertEqual(PROFILE,gate.load(gate.SELECTOR)['bounds'])
        self.assertEqual(PROFILE['artifact_decoded_bytes'],128*MIB)
        self.assertEqual(PROFILE['sidecar_bytes'],512*MIB)


if __name__=='__main__':unittest.main()
