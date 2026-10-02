"""Adversarial selected-byte/privacy checks, using temporary copies only."""
import copy
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import check
import privacy


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'packet';shutil.copytree(check.ROOT,self.root)
        self.patch=patch.object(check,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.manifest=check.load(self.root/'retention.json')

    def save(self):
        (self.root/'retention.json').write_text(json.dumps(self.manifest))

    def test_all_selected_originals_and_bindings(self):
        _,files=check.selected();check.bindings(files)

    def test_stored_tamper(self):
        p=self.root/self.manifest['records'][0]['stored'];p.write_bytes(p.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'stored file identity'):check.selected()

    def test_forged_stored_digest_does_not_change_original(self):
        row=next(r for r in self.manifest['records'] if r['encoding']=='gzip')
        p=self.root/row['stored'];raw=gzip.compress(b'{}',mtime=0);p.write_bytes(raw)
        row['stored_identity']=check.identity(raw);self.save()
        with self.assertRaisesRegex(ValueError,'decoded original identity'):check.selected()

    def test_duplicate_original(self):
        self.manifest['records'][1]['original']=self.manifest['records'][0]['original'];self.save()
        with self.assertRaisesRegex(ValueError,'unique originals'):check.selected()

    def test_unlisted_stored_file(self):
        (self.root/'retained/unlisted').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'complete retained membership'):check.selected()

    def test_parent_path_escape(self):
        self.manifest['records'][0]['stored']='../foreign';self.save()
        with self.assertRaisesRegex(ValueError,'owned canonical stored path'):check.selected()

    def test_summary_whole_cannot_change(self):
        result=check.load(self.root/'result.json');result['whole_identities'][0]['proof']['sha256']='0'*64
        (self.root/'result.json').write_text(json.dumps(result));_,files=check.selected()
        with self.assertRaisesRegex(ValueError,'derived public summary exact'):check.bindings(files)


class PrivacyTests(unittest.TestCase):
    def test_static_public_asset_link(self):
        privacy.scan(b'https://api.github.com/repos/cyberia-to/trisha/releases/assets/606263560','safe.txt')

    def test_signed_url(self):
        with self.assertRaisesRegex(ValueError,'credential-bearing'):
            privacy.scan(b'https://example.invalid/file?'+b'sig'+b'='+b'synthetic-test-value','bad.txt')

    def test_raw_host_inventory(self):
        with self.assertRaisesRegex(ValueError,'raw process snapshot'):
            privacy.scan(b'  123 456 789 Fri Oct  2 00:00:00 2026 /private/command\n','bad.txt')

    def test_embedded_raw_stream(self):
        with self.assertRaisesRegex(ValueError,'embedded raw'):
            privacy.scan(b'{"nested":{"raw_stdout":"host snapshot"}}','bad.json')


if __name__=='__main__':unittest.main()
