"""Final archive ceiling, pre-body capacity, and structural resource controls."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

import gate
gate.frozen()
from common import save_new
from contracts import MIB
from metadata import PROFILE, reserve, resources
import packing


class MetadataTests(unittest.TestCase):
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
