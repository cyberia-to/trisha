"""Mutate retained evidence independently of the running native producers."""
import hashlib,importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('inspector',Path(__file__).with_name('inspect-final-native-producer.py'))
inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)
HEAD='a'*40
def dump(path,value):path.write_text(json.dumps(value))
class ContainerTests(unittest.TestCase):
 def setUp(self):
  self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name);(self.root/'restored').mkdir()
 def make(self):
  raw=b'actual retained command evidence\n';(self.root/'restored/result.log').write_bytes(raw)
  with zipfile.ZipFile(self.root/'artifact.zip','w') as archive:archive.writestr('result.log',raw)
  self.rebind()
 def rebind(self):
  archive=self.root/'artifact.zip';h=inspector.sha(archive);n=archive.stat().st_size
  self.ret=dict(run_id=1,head_sha=HEAD,artifact_id=2,archive_sha256=h,archive_bytes=n,files=[dict(path='result.log',bytes=(self.root/'restored/result.log').stat().st_size,sha256=inspector.sha(self.root/'restored/result.log'))])
  dump(self.root/'retention.json',self.ret);dump(self.root/'api.json',dict(workflow_run=dict(id=1),id=2,digest='sha256:'+h,size_in_bytes=n))
 def test_exact_original_passes(self):
  self.make();inspector.container(self.root,1,HEAD)
 def test_changed_restored_bytes_and_rehashed_manifest_reject(self):
  self.make();(self.root/'restored/result.log').write_bytes(b'forged evidence\n');self.rebind()
  with self.assertRaisesRegex(ValueError,'original/retained member'):inspector.container(self.root,1,HEAD)
 def test_extra_retained_file_reject(self):
  self.make();(self.root/'restored/extra.log').write_bytes(b'not original')
  with self.assertRaisesRegex(ValueError,'inventory differs'):inspector.container(self.root,1,HEAD)
 def test_duplicate_retention_member_reject(self):
  self.make();self.ret['files']*=2;dump(self.root/'retention.json',self.ret)
  with self.assertRaisesRegex(ValueError,'duplicate retained'):inspector.container(self.root,1,HEAD)
 def test_wrong_run_reject(self):
  self.make()
  with self.assertRaisesRegex(ValueError,'runner selection differs'):inspector.container(self.root,3,HEAD)
 def test_extra_original_member_reject(self):
  self.make()
  with zipfile.ZipFile(self.root/'artifact.zip','a') as archive:archive.writestr('extra.log',b'extra')
  self.rebind()
  with self.assertRaisesRegex(ValueError,'original/retained member'):inspector.container(self.root,1,HEAD)
 def test_original_path_escape_reject(self):
  self.make()
  with zipfile.ZipFile(self.root/'artifact.zip','a') as archive:archive.writestr('../escape',b'extra')
  self.rebind()
  with self.assertRaisesRegex(ValueError,'unsafe original ZIP member'):inspector.container(self.root,1,HEAD)
 def test_original_symlink_reject(self):
  self.make()
  with zipfile.ZipFile(self.root/'artifact.zip','a') as archive:
   member=zipfile.ZipInfo('link');member.create_system=3;member.external_attr=0o120777<<16;archive.writestr(member,'result.log')
  self.rebind()
  with self.assertRaisesRegex(ValueError,'original ZIP symlink'):inspector.container(self.root,1,HEAD)
if __name__=='__main__':unittest.main()
