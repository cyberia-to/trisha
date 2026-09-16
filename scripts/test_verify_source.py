"""Real file mutations and stub-build failure tests; no compiler/proof work."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('verify-source.py')
spec = importlib.util.spec_from_file_location('verify_source', SCRIPT)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def inventory(base):
    records = []
    for p in sorted(base.rglob('*')):
        if p.is_symlink():
            content, kind = os.readlink(p).encode(), 'symlink'
        elif p.is_file():
            content, kind = p.read_bytes(), 'file'
        else:
            continue
        records.append(dict(path=p.relative_to(base).as_posix(), type=kind,
                            bytes=len(content), sha256=hashlib.sha256(content).hexdigest()))
    return records


def builder_command(source, prefix):
    # Explicitly remove LAST_EXIT_CODE even when the parent/config supplied it.
    builder = SCRIPT.with_name('build-candidate.nu')
    command = ('hide-env -i LAST_EXIT_CODE; ^nu --no-config-file ' + json.dumps(str(builder))
               + ' ' + json.dumps(str(source)) + ' ' + json.dumps(str(prefix)))
    return ['nu', '--no-config-file', '--commands', command]


class SourceVerification(unittest.TestCase):
    def test_windows_symlink_spelling_preserves_canonical_target_identity(self):
        with patch.object(verifier.os, 'name', 'nt'):
            self.assertEqual(verifier.link_bytes('..\\queries\\highlights.scm'),
                             b'../queries/highlights.scm')
        with patch.object(verifier.os, 'name', 'posix'):
            self.assertEqual(verifier.link_bytes('literal\\name'), b'literal\\name')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        for name in ('trident', 'trisha', 'joy'):
            repo = self.source / name
            repo.mkdir()
            (repo / 'Cargo.toml').write_text('[package]\nname="fixture"\n')
            (repo / 'lib.rs').write_text('original')
        (self.source / 'trident' / 'link.rs').symlink_to('lib.rs')
        self.record()
        vendor = self.source / 'trisha' / '.vendor'
        vendor.mkdir()
        (vendor / 'lib.rs').write_text('vendor original')
        (self.source / 'vendor-sources.json').write_text(json.dumps(inventory(vendor)))
        (self.source / 'BUILD.txt').write_text('instructions')

    def record(self):
        (self.source / 'sources.json').write_text(json.dumps([
            dict(repository=name, mode='committed', files=inventory(self.source/name))
            for name in ('trident', 'trisha', 'joy')]))

    def test_unchanged_and_post_build(self):
        expected = self.root / 'verified.json'
        expected.write_text(json.dumps(verifier.verify(self.source)))
        self.assertEqual(verifier.verify(self.source, expected)['vendor_files'], 1)

    def test_mutated_missing_added_and_vendor(self):
        for relative, action in (
            ('trident/lib.rs', 'mutate'), ('joy/lib.rs', 'delete'),
            ('trisha/extra.rs', 'add'), ('trisha/.vendor/lib.rs', 'mutate')):
            with self.subTest(relative=relative):
                path = self.source / relative
                prior = path.read_bytes() if path.exists() else None
                if action == 'delete':
                    path.unlink()
                else:
                    path.write_text('altered')
                with self.assertRaises(ValueError):
                    verifier.verify(self.source)
                if prior is None:
                    path.unlink()
                else:
                    path.write_bytes(prior)

    def test_symlink_target_identity_and_escape(self):
        link = self.source / 'trident/link.rs'
        link.unlink()
        link.symlink_to('../joy/lib.rs')
        with self.assertRaises(ValueError):
            verifier.verify(self.source)
        link.unlink()
        outside = self.root / 'outside.rs'
        outside.write_text('outside')
        link.symlink_to('../../outside.rs')
        records = json.loads((self.source/'sources.json').read_text())
        records[0]['files'] = inventory(self.source/'trident')
        (self.source/'sources.json').write_text(json.dumps(records))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            verifier.verify(self.source)

    def test_rewritten_manifest_is_rejected_after_build(self):
        expected = self.root/'verified.json'
        expected.write_text(json.dumps(verifier.verify(self.source)))
        (self.source/'joy/lib.rs').write_text('new authenticated content')
        records = json.loads((self.source/'sources.json').read_text())
        records[2]['files'] = inventory(self.source/'joy')
        (self.source/'sources.json').write_text(json.dumps(records))
        with self.assertRaisesRegex(ValueError, 'changed during build'):
            verifier.verify(self.source, expected)

    def test_incomplete_committed_inventory_rejected(self):
        records = json.loads((self.source/'sources.json').read_text())
        del records[0]['files']
        (self.source/'sources.json').write_text(json.dumps(records))
        with self.assertRaisesRegex(ValueError, 'complete inventory missing'):
            verifier.verify(self.source)

    @unittest.skipUnless(shutil.which('nu'), 'Nushell required for builder process test')
    def test_dangling_and_inside_source_destinations_rejected_before_cargo(self):
        builder = SCRIPT.with_name('build-candidate.nu')
        dangling = self.root/'dangling'
        dangling.symlink_to('missing-target')
        alias = self.root/'source-alias'
        alias.symlink_to(self.source, target_is_directory=True)
        for destination in (dangling, self.source/'candidate', alias/'candidate'):
            with self.subTest(destination=destination):
                result = subprocess.run(builder_command(self.source, destination),
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('candidate', result.stderr)
                self.assertFalse((self.source/'candidate').exists())
                self.assertFalse((self.root/'missing-target').exists())
                self.assertEqual(list(self.root.rglob('*.building.*')), [])
        self.assertTrue(dangling.is_symlink())

    @unittest.skipUnless(shutil.which('nu'), 'Nushell required for builder process test')
    def test_invalid_source_and_existing_prefix_leave_no_partial_output(self):
        prefix = self.root/'candidate'
        builder = SCRIPT.with_name('build-candidate.nu')
        (self.source/'joy/lib.rs').write_text('tampered')
        command = builder_command(self.source, prefix)
        result = subprocess.run(command, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(prefix.exists())
        self.assertEqual(list(self.root.glob('candidate.building.*')), [])
        prefix.mkdir()
        marker = prefix/'preserve'
        marker.write_text('original candidate')
        result = subprocess.run(command, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'original candidate')

    @unittest.skipUnless(shutil.which('nu'), 'Nushell required for builder process test')
    def test_mktemp_failure_and_unexpected_output_are_clean(self):
        bindir = self.root/'mock-mktemp'
        bindir.mkdir()
        tool = bindir/'mktemp'
        tool.write_text("""#!/usr/bin/env python3
import os,pathlib,sys
mode=os.environ['MKTEMP_CASE']
if mode=='empty': sys.exit(0)
if mode=='nonzero': sys.exit(9)
path=pathlib.Path(sys.argv[-1].replace('XXXXXX','ABC123'))
if mode!='missing': path.mkdir()
print(path)
if mode=='created_nonzero': sys.exit(9)
""")
        tool.chmod(0o755)
        env = dict(os.environ, PATH=str(bindir)+os.pathsep+os.environ['PATH'])
        env.pop('LAST_EXIT_CODE', None)
        for mode in ('empty', 'nonzero', 'missing', 'created_nonzero'):
            with self.subTest(mode=mode):
                prefix = self.root/('candidate-'+mode)
                result = subprocess.run(builder_command(self.source, prefix),
                                        env=dict(env, MKTEMP_CASE=mode), capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('env::column_not_found', result.stderr)
                self.assertFalse(prefix.exists())
                self.assertEqual(list(self.root.glob(prefix.name+'.building.*')), [])

    @unittest.skipUnless(shutil.which('nu'), 'Nushell required for builder process test')
    def test_atomic_build_failure_and_source_mutation(self):
        bindir = self.root/'mock-bin'
        bindir.mkdir()
        cargo = bindir/'cargo'
        cargo.write_text('''#!/usr/bin/env python3
import json,os,pathlib,sys
args=sys.argv[1:]
if args[0]=='metadata':
 names=['triton-vm','triton-air','triton-isa','triton-constraint-circuit','triton-constraint-builder','tasm-lib','tasm-object-derive']
 print(json.dumps({'packages':[{'name':n,'version':'7.0.0','source':'registry'} for n in names]}))
elif args[0]=='build':
 release=pathlib.Path(os.environ['CARGO_TARGET_DIR'])/'release';release.mkdir(parents=True,exist_ok=True)
 for name in ['trident','trident-lsp','trisha','joy']: (release/name).write_text('stub binary')
elif args[0]=='run':
 if os.environ.get('FAIL_FIXTURE'): sys.exit(2)
 if os.environ.get('MUTATE_SOURCE'): (pathlib.Path.cwd()/'joy/lib.rs').write_text('mutated during build')
 pathlib.Path(args[-1]).mkdir(parents=True)
''')
        cargo.chmod(0o755)
        environment = dict(os.environ, PATH=str(bindir)+os.pathsep+os.environ['PATH'])
        builder = SCRIPT.with_name('build-candidate.nu')
        for mode in ('FAIL_FIXTURE', 'MUTATE_SOURCE', 'SUCCESS'):
            with self.subTest(mode=mode):
                prefix = self.root/mode
                result = subprocess.run(builder_command(self.source, prefix),
                                        env=dict(environment, **{mode:'1'}), capture_output=True, text=True)
                if mode == 'SUCCESS':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue((prefix/'candidate.json').is_file())
                    self.assertTrue((prefix/'source-verification.json').is_file())
                    candidate = json.loads((prefix/'candidate.json').read_text())
                    self.assertEqual(candidate['source_verification_sha256'], hashlib.sha256((prefix/'source-verification.json').read_bytes()).hexdigest())
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(prefix.exists())
                    self.assertEqual(list(self.root.glob(mode+'.building.*')), [])
                    (self.source/'joy/lib.rs').write_text('original')


if __name__ == '__main__':
    unittest.main()
