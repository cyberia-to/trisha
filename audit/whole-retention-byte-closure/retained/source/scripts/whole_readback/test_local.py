"""Local publication guards and durable embedded observations, with tiny fixtures."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gate
gate.frozen()
from common import identity, load, save_new
import local


def observations():
    before=dict(schema='trident/local-certificate-byte-closure/v1',status='passed-complete-local-scan',started_ns=1,ended_ns=2,original_helper_sources={},local_preparation={'synthetic':True},prepared={'synthetic':True})
    after=copy.deepcopy(before);after.update(started_ns=3,ended_ns=4)
    return before,after


class Publication(unittest.TestCase):
    def test_upload_requires_complete_remote_and_both_local_scans(self):
        before,after=observations()
        class T:
            receipt=dict(status='ready-unique-metadata-retention',admitted_remote=dict(status='passed'),before=before,after=after)
            def draft(self,*args):raise RuntimeError('guard reached only after admission')
        with tempfile.TemporaryDirectory() as temp:
            t=T();t.directory=Path(temp);path=t.directory/'metadata';path.write_bytes(b'synthetic')
            with self.assertRaisesRegex(RuntimeError,'guard reached'):local.ClosureTransport.upload(t,'x',path,'new',identity(path))
            for field,value in [('status','running'),('admitted_remote',dict(status='failed')),('after',dict(after,status='failed'))]:
                old=t.receipt[field];t.receipt[field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):local.ClosureTransport.upload(t,'x',path,'new',identity(path))
                t.receipt[field]=old

    def test_durable_manifest_embeds_exact_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory=root/'local';directory.mkdir();(directory/'evidence').mkdir()
            source=root/'original';source.write_bytes(b'synthetic original local metadata');wanted=identity(source)
            before,after=observations();save_new(root/'before.json',before);save_new(directory/'after.json',after)
            save_new(directory/'evidence/receipt.json',dict(status='completed-byte-replay',synthetic=True));save_new(directory/'packing.json',dict(status='passed',synthetic=True))
            class T:
                sources={'synthetic':True};receipt=dict(before=before,after=after)
                def budget(self,n=0):pass
                def persist(self):pass
                def upload(self,label,path,name,expected):
                    self.published.append(dict(label=label,name=name,identity=expected));return dict(**expected,asset={'synthetic':name})
            t=T();t.directory=directory;t.published=[]
            prepared=dict(metadata=dict(path=str(source),**wanted),admitted=dict(source_revisions={'synthetic':True},binary={'synthetic':True},entries=[]))
            admitted=dict(checked=dict(entries=[]));original_load=gate.load
            def selected(path):return dict(original_metadata=wanted) if path==gate.SELECTOR else original_load(path)
            with patch.object(gate,'load',side_effect=selected):
                local.publish(t,prepared,admitted,root/'before.json',directory/'after.json','synthetic-only')
            value=load(directory/'equivalence.json')
            self.assertEqual(value['local']['before']['observation'],before);self.assertEqual(value['local']['after']['observation'],after)
            self.assertEqual(value['worker_observation'],load(directory/'evidence/receipt.json'));self.assertEqual(value['packing_observation'],load(directory/'packing.json'))
            self.assertEqual(value['local']['before']['identity'],identity(root/'before.json'))
            self.assertEqual([r['label'] for r in t.published],['original-local-metadata','equivalence'])
            self.assertEqual(identity(source),wanted)
            source.write_bytes(b'changed')
            with patch.object(gate,'load',side_effect=selected),self.assertRaises(ValueError):
                local.publish(t,prepared,admitted,root/'before.json',directory/'after.json','must-not-publish')
            self.assertEqual(len(t.published),2)


if __name__=='__main__':unittest.main()
