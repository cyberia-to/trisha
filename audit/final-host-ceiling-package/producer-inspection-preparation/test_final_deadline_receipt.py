"""Mutations of actual final local installed deadline evidence, in scratch copies."""
import hashlib,importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
M=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('inspector',M/'inspect-final-native-producer.py')
inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)
ACTUAL=M.parent/'local-macos-final-rust189/release-results'
class DeadlineReceiptTests(unittest.TestCase):
 def setUp(self):
  self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)
  shutil.copytree(ACTUAL/'installed-host-ceiling',self.root/'installed-host-ceiling')
  self.receipt=self.root/'installed-host-ceiling/receipt.json';self.report=json.loads(self.receipt.read_text())
  self.candidate=json.loads((ACTUAL/'candidate.json').read_text());archive=json.loads((ACTUAL/'archive.json').read_text())
  self.packaged=inspector.package_candidate(ACTUAL/archive['archive'],self.candidate,archive['target'])
 def save(self):self.receipt.write_text(json.dumps(self.report))
 def check(self):return inspector.deadline_probe(self.root,self.candidate,self.packaged,inspector.HELPER)
 def test_actual_final_probe_passes(self):self.check()
 def test_build_metadata_digest_rejects(self):
  self.report['candidate_sha256']=inspector.sha(ACTUAL/'candidate.json');self.save()
  with self.assertRaisesRegex(ValueError,'candidate identity differs'):self.check()
 def test_wrong_source_rejects(self):
  self.report['source_provenance_sha256']='0'*64;self.save()
  with self.assertRaisesRegex(ValueError,'candidate identity differs'):self.check()
 def test_changed_clock_case_rejects(self):
  self.report['commands'][0]['name']='prove-14400001';self.save()
  with self.assertRaisesRegex(ValueError,'case map differs'):self.check()
 def test_changed_claim_even_with_updated_stream_digest_rejects(self):
  row=next(r for r in self.report['commands'] if r['name']=='verify-30000-14400000');path=self.root/'installed-host-ceiling/commands'/row['stdout']['path'];value=json.loads(path.read_text());value['verification']['physical_resource_claim']='attested';raw=json.dumps(value).encode();path.write_bytes(raw);row['stdout'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());self.save()
  with self.assertRaisesRegex(ValueError,'unexpectedly attests resources'):self.check()
 def test_clock_dependent_certificate_rejects(self):
  with (self.root/'installed-host-ceiling/proof-14400000').open('ab') as stream:stream.write(b'changed')
  with self.assertRaisesRegex(ValueError,'changed certificate bytes'):self.check()
 def test_changed_extracted_program_rejects(self):
  with (self.root/'installed-host-ceiling/compiled').open('ab') as stream:stream.write(b'changed')
  with self.assertRaisesRegex(ValueError,'extracted or executed output differs'):self.check()
 def test_rejected_command_replaced_destination_rejects(self):
  (self.root/'installed-host-ceiling/destination').write_bytes(b'replaced')
  with self.assertRaisesRegex(ValueError,'rejection replaced output'):self.check()
if __name__=='__main__':unittest.main()
