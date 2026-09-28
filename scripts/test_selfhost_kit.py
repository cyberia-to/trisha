"""Kit transport/route guards plus optional real historical-C2 rehearsal.

No synthetic accepted kit or final36 acceptance fixture exists in this suite.
"""
import argparse
import gzip
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import selfhost_kit as K
import selfhost_kit_assembly as A

SCRIPTS = Path(__file__).parent.resolve()
OPTIONS = None


class Guards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.trident = self.root/'trident'
        self.trident.mkdir()

    def tar(self, members):
        path = self.root/'input.tar.gz'
        with tarfile.open(path, 'w:gz') as target:
            for name, kind, data in members:
                info = tarfile.TarInfo(name)
                info.type = kind
                info.size = len(data)
                target.addfile(info, io.BytesIO(data))
        return path

    def reject_archive(self, path):
        output = self.root/'output'
        with self.assertRaises((ValueError, tarfile.TarError, KeyError)):
            K.unpack(path, K.sha(path), output, self.trident)
        self.assertFalse(output.exists())

    def test_unsafe_names_rejected(self):
        for value in ('../x', '/x', 'a//x', 'a/./x', 'C:/x', 'a\\x', 'a/NUL.txt', 'x.', 'COM1/a'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                K.relative(value)

    def test_archive_links_escape_duplicates_and_case_aliases_rejected(self):
        cases = [
            [('trident-selfhost/x', tarfile.SYMTYPE, b'')],
            [('trident-selfhost/x', tarfile.LNKTYPE, b'')],
            [('trident-selfhost/../escape', tarfile.REGTYPE, b'x')],
            [('different/x', tarfile.REGTYPE, b'x')],
            [('trident-selfhost/x', tarfile.REGTYPE, b'a')] * 2,
            [('trident-selfhost/X', tarfile.REGTYPE, b'a'), ('trident-selfhost/x', tarfile.REGTYPE, b'b')],
        ]
        for members in cases:
            with self.subTest(members=members):
                self.reject_archive(self.tar(members))

    def test_hidden_pax_bytes_bounded_before_tar_parser(self):
        path = self.root/'pax.gz'
        path.write_bytes(gzip.compress(b'x' * 100000))
        with patch.object(K, 'MAX_BYTES', 8), patch.object(K.tarfile, 'open', side_effect=AssertionError('parser reached')):
            self.reject_archive(path)

    def test_archive_member_count_and_declared_size_bound(self):
        path = self.tar([('trident-selfhost/x', tarfile.REGTYPE, b'x' * 513)])
        self.assertLess(path.stat().st_size, 512)
        with patch.object(K, 'MAX_BYTES', 512):
            self.reject_archive(path)
        path = self.tar([(f'trident-selfhost/{i}', tarfile.REGTYPE, b'') for i in range(5)])
        with patch.object(K, 'MAX_FILES', 2):
            self.reject_archive(path)

    def test_transport_exact_file_and_byte_caps(self):
        # A transport-only parser fixture, never an accepted compiler kit.
        path = self.tar([('trident-selfhost/x', tarfile.REGTYPE, b'x' * 512)])
        with patch.object(K, 'MAX_BYTES', 512), patch.object(K, 'MAX_FILES', 1), patch.object(K, 'check', return_value=None):
            K.unpack(path, K.sha(path), self.root/'exact', self.trident)
        self.assertEqual((self.root/'exact/x').read_bytes(), b'x' * 512)
        with patch.object(K, 'MAX_BYTES', 511):
            self.reject_archive(path)
        with patch.object(K, 'MAX_FILES', 0):
            self.reject_archive(path)

    def test_wrong_archive_hash_does_not_create_output(self):
        path = self.tar([])
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            K.unpack(path, '0' * 64, self.root/'output', self.trident)
        self.assertFalse((self.root/'output').exists())

    def test_existing_output_and_symlink_parent_alias_preserved(self):
        output = self.root/'occupied'
        output.write_bytes(b'preserved')
        with self.assertRaises(ValueError):
            K.separate(output, self.trident)
        self.assertEqual(output.read_bytes(), b'preserved')
        alias = self.root/'alias'
        alias.symlink_to(self.trident, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            K.separate(alias/'new', self.trident)
        self.assertEqual(list(self.trident.iterdir()), [])

    def test_ordinary_and_file_manifest_reject_links_and_extra_bytes(self):
        root = self.root/'kit'
        root.mkdir()
        (root/'data').write_bytes(b'abc')
        with patch.object(K, 'MAX_BYTES', 2), self.assertRaises(ValueError):
            K.files(root)
        (root/'link').symlink_to(root/'data')
        with self.assertRaises(ValueError):
            K.files(root)

    def test_json_length_checked_before_read(self):
        path = self.root/'json'
        path.write_bytes(b'123')
        with patch.object(K, 'MAX_JSON', 2), patch.object(Path, 'read_bytes', side_effect=AssertionError('read')):
            with self.assertRaises(ValueError):
                K.load(path)

    def test_unpinned_validator_never_executes(self):
        path = self.root/'validator.py'
        path.write_text('raise Exception("must not run")')
        with patch.object(A.subprocess, 'run', side_effect=AssertionError('executed')):
            with self.assertRaisesRegex(ValueError, 'validator SHA256'):
                A.authority(path, self.root/'absent-config', self.root/'work')
        self.assertFalse((self.root/'work').exists())

    def test_missing_authority_config_cannot_reuse_old_pass(self):
        path = self.root/'fake.json'
        K.write(path, {'status': 'passed'})
        with patch.object(K, 'sha', return_value=K.VALIDATOR), patch.object(A.subprocess, 'run', side_effect=AssertionError('executed')):
            with self.assertRaisesRegex(ValueError, 'configuration'):
                A.authority(path, path, self.root/'work')
        self.assertFalse((self.root/'work').exists())

    def test_ci_cannot_bypass_local_authority_contract(self):
        with patch.dict(A.os.environ, GITHUB_ACTIONS='true'):
            with self.assertRaisesRegex(ValueError, 'outside CI'):
                A.authority(self.root/'validator', self.root/'config', self.root/'output')
        self.assertFalse((self.root/'output').exists())

    def test_relative_authority_paths_reject_before_work_creation(self):
        config = {key: str(self.root / key) for key in A.PATH_ARGUMENTS}
        config.update({'indices-sha256': '0' * 64, 'aggregate-id': 1, 'producer-name': 'unused'})
        config['restored'] = 'relative-input'
        path = self.root/'config.json'
        K.write(path, config)
        with patch.object(K, 'sha', return_value=K.VALIDATOR), patch.object(A.subprocess, 'run', side_effect=AssertionError('executed')):
            with self.assertRaisesRegex(ValueError, 'absolute validator input paths'):
                A.authority(path, path, self.root/'work')
        self.assertFalse((self.root/'work').exists())



@unittest.skipUnless(OPTIONS, 'invoke with --rehearsal, --trident and --joy for actual C2 rehearsal')
class ActualRehearsal(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kit пробел-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = OPTIONS.rehearsal.resolve()
        self.trident = OPTIONS.trident.resolve()

    def test_historical_kit_cannot_enter_production(self):
        with self.assertRaisesRegex(ValueError, 'production packaging'):
            K.check(self.kit, self.trident)
        self.assertEqual(K.check(self.kit, self.trident, True)['status'], 'rehearsal')

    def test_exact_rehearsal_archive_reproduces_and_roundtrips(self):
        spec = importlib.util.spec_from_file_location('archive_source', SCRIPTS/'archive-source.py')
        archive = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(archive)
        first, second = self.root/'a.tar.gz', self.root/'b.tar.gz'
        for path in (first, second):
            archive.archive(self.kit, path, 0, 'trident-selfhost')
        self.assertEqual(first.read_bytes(), second.read_bytes())
        restored = self.root/'restored'
        K.unpack(first, K.sha(first), restored, self.trident, rehearsal=True)
        self.assertEqual(K.files(restored), K.files(self.kit))
        with self.assertRaisesRegex(ValueError, 'production packaging'):
            K.unpack(first, K.sha(first), self.root/'production', self.trident)

    def test_source_drift_and_payload_tamper_fail(self):
        fixed = K.load(self.kit/'fixed-point.json')['fixed_point']['source_sha256_set']
        source = self.root/'source'
        for row in fixed.values():
            path = source / row['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.trident/row['path'], path)
        K.source_check(source, fixed)
        (source/'compiler/nox/main.tri').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source differs'):
            K.source_check(source, fixed)
        copied = self.root/'kit'
        shutil.copytree(self.kit, copied)
        (copied/'compiler.dag').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'manifest'):
            K.check(copied, self.trident, True)

    def test_supplied_real_joy_rehearsal(self):
        output = self.root/'smoke'
        result = K.smoke(self.kit, OPTIONS.joy.resolve(), output, self.trident, True)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual([r['exit_code'] for r in result['commands']], [0, 0, 0, 0, 1])
        self.assertEqual(result['answer']['sha256'], K.ANSWER)
        K.smoke_evidence(self.kit, OPTIONS.joy.resolve(), output/'receipt.json')
        with self.assertRaisesRegex(ValueError, 'requires accepted kit'):
            K.check_smoke(self.kit, OPTIONS.joy.resolve(), output/'receipt.json')
        receipt = K.load(output/'receipt.json')
        original = (output/'receipt.json').read_bytes()
        mutations = [
            lambda r: r['implementation'].update({'selfhost_kit.py': '0' * 64}),
            lambda r: r['commands'][1]['argv'].append('--budget'),
            lambda r: r['commands'][0].update(status='failed'),
            lambda r: r['outputs']['sample.dag'].update(sha256='0' * 64),
            lambda r: r['commands'][0]['stdout'].update(sha256='0' * 64),
        ]
        for mutation in mutations:
            changed = json.loads(original)
            mutation(changed)
            (output/'receipt.json').write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                K.smoke_evidence(self.kit, OPTIONS.joy.resolve(), output/'receipt.json')
        (output/'receipt.json').write_bytes(original)
        (output/'answer.dag').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            K.smoke_evidence(self.kit, OPTIONS.joy.resolve(), output/'receipt.json')

    def test_timeout_retains_attempt_and_never_passes(self):
        output = self.root/'timeout'
        with patch.object(K.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['joy'], 120)):
            with self.assertRaises(subprocess.TimeoutExpired):
                K.smoke(self.kit, OPTIONS.joy.resolve(), output, self.trident, True)
        receipt = K.load(output/'receipt.json')
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(len(receipt['commands']), 1)
        row = receipt['commands'][0]
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['argv'][1], 'pack-job')
        self.assertIsNone(row['exit_code'])
        self.assertTrue((output / row['stderr']['path']).is_file())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    for name in ('rehearsal', 'trident', 'joy'):
        parser.add_argument('--' + name, type=Path)
    options, rest = parser.parse_known_args()
    if any(vars(options).values()):
        if not all(vars(options).values()):
            parser.error('all three actual rehearsal inputs are required')
        OPTIONS = options
        ActualRehearsal.__unittest_skip__ = False
    unittest.main(argv=[sys.argv[0], *rest])
