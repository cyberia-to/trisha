"""Packaging boundary tests with synthetic binaries, never proof evidence."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

SCRIPTS = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('verify_source', SCRIPTS/'verify-source.py')
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def inventory(root):
    return [dict(path=p.relative_to(root).as_posix(), type='file',
                 bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
            for p in sorted(root.rglob('*')) if p.is_file()]


@unittest.skipUnless(shutil.which('nu'), 'Nushell is required')
class BinaryPackaging(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.prefix = self.root/'candidate'
        self.source = self.root/'source'
        (self.prefix/'bin').mkdir(parents=True)
        self.source.mkdir()
        binaries, repositories = [], []
        for name, license_name in [('trident', 'LICENSE.md'), ('trisha', 'LICENSE'), ('joy', 'LICENSE')]:
            binary = self.prefix/'bin'/name
            binary.write_bytes(b'synthetic binary')
            binary.chmod(0o755)
            binaries.append(dict(name=name, sha256=sha(binary.read_bytes())))
            repo = self.source/name
            repo.mkdir()
            (repo/license_name).write_text('synthetic license fixture')
            if name == 'trisha':
                (repo/'scripts').mkdir()
                shutil.copyfile(SCRIPTS/'smoke-release.nu', repo/'scripts/smoke-release.nu')
                shutil.copyfile(SCRIPTS/'smoke-lsp.py', repo/'scripts/smoke-lsp.py')
            repositories.append(dict(repository=name, mode='committed', files=inventory(repo)))
        binary = self.prefix/'bin/trident-lsp'
        binary.write_bytes(b'synthetic lsp binary')
        binary.chmod(0o755)
        binaries.append(dict(name='trident-lsp', sha256=sha(binary.read_bytes())))
        (self.source/'sources.json').write_text(json.dumps(repositories))
        vendor = self.source/'trisha/.vendor'
        vendor.mkdir()
        (vendor/'lib.rs').write_text('// synthetic vendor source')
        (self.source/'vendor-sources.json').write_text(json.dumps(inventory(vendor)))
        (self.source/'BUILD.txt').write_text('synthetic instructions')
        verification = self.prefix/'source-verification.json'
        verification.write_text(json.dumps(VERIFY.verify(self.source)))
        provenance = sha((self.source/'sources.json').read_bytes())
        verification_hash = sha(verification.read_bytes())
        self.fixtures = self.prefix/'share/trisha-release-smoke'
        self.fixtures.mkdir(parents=True)
        fixture_files = []
        for name in ['state.json', 'other-state.json', 'state-all.json']:
            (self.fixtures/name).write_text('{}')
            fixture_files.append(dict(name=name, sha256=sha(b'{}')))
        (self.prefix/'candidate.json').write_text(json.dumps(dict(
            schema_version=2, source=str(self.source), source_verified=True,
            source_verification_sha256=verification_hash,
            provenance_sha256=provenance, binaries=binaries)))
        self.receipt = self.root/'smoke.json'
        self.receipt.write_text(json.dumps(dict(
            schema_version=2, suite='installed-compiler-warrior-v2',
            all_checks_passed=True, source_provenance_sha256=provenance,
            source_verification_sha256=verification_hash,
            smoke_script_sha256=sha((SCRIPTS/'smoke-release.nu').read_bytes()),
            lsp_script_sha256=sha((SCRIPTS/'smoke-lsp.py').read_bytes()),
            binaries=binaries, fixture_files=fixture_files, platform={})))

    def package(self, name='archive', with_receipt=True, env=None):
        output = self.root/(name+'.tar.gz')
        command = [shutil.which('nu'), str(SCRIPTS/'package-binaries.nu'),
                   str(self.prefix), str(output)]
        if with_receipt:
            command += ['--smoke', str(self.receipt)]
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        return result, output

    def test_missing_smoke_and_changed_binary_fixture_or_source_are_rejected(self):
        result, output = self.package(with_receipt=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        for path in [self.prefix/'bin/joy', self.fixtures/'state.json',
                     self.prefix/'source-verification.json',
                     self.source/'trident/LICENSE.md', self.source/'trisha/.vendor/lib.rs',
                     self.source/'trisha/scripts/smoke-release.nu']:
            with self.subTest(path=path):
                previous = path.read_bytes()
                path.write_bytes(b'changed')
                result, output = self.package()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse(output.exists())
                path.write_bytes(previous)

    def test_staging_and_permission_failures_leave_no_archive(self):
        for tool in ['mktemp', 'chmod']:
            with self.subTest(tool=tool):
                mock = self.root/tool
                mock.mkdir()
                binary = mock/tool
                binary.write_text('#!/bin/sh\nexit 9\n')
                binary.chmod(0o755)
                env = dict(os.environ, PATH=str(mock)+os.pathsep+os.environ['PATH'])
                result, output = self.package(tool, env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_archive_reproduces_exact_tested_bytes_and_verification_receipt(self):
        archives = []
        for name in ['first', 'second']:
            result, output = self.package(name)
            self.assertEqual(result.returncode, 0, result.stderr)
            archives.append(output)
        self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())
        with tarfile.open(archives[0]) as archive:
            for name in ['trident', 'trident-lsp', 'trisha', 'joy']:
                member = archive.getmember('cyber-tools/bin/'+name)
                self.assertTrue(member.isfile())
                self.assertEqual(member.mode, 0o755)
                self.assertEqual(archive.extractfile(member).read(), (self.prefix/'bin'/name).read_bytes())
            candidate = json.load(archive.extractfile('cyber-tools/candidate.json'))
            self.assertNotIn('source', candidate)
            verification = archive.extractfile('cyber-tools/source-verification.json').read()
            self.assertEqual(sha(verification), candidate['source_verification_sha256'])
            self.assertEqual(verification, (self.prefix/'source-verification.json').read_bytes())
            self.assertEqual(archive.extractfile('cyber-tools/share/trisha-release-smoke/smoke-release.nu').read(),
                             (SCRIPTS/'smoke-release.nu').read_bytes())
        previous = archives[0].read_bytes()
        result, output = self.package('first')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
