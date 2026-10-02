"""Exercise native orchestration at the inheritance/fresh-proof boundary."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('native', Path(__file__).with_name('native-candidate.py'))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class FullGate(unittest.TestCase):
    def decision(self, code, status, count, reasons, *, wrong_candidate=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate, work, results = (root/name for name in ('candidate', 'work', 'results'))
            for path in (candidate, work, results):
                path.mkdir()
            (candidate/'candidate.json').write_text('{}')
            fresh = []

            def inherit(command, **kwargs):
                data = dict(status=status, fresh_run_performed=False, inherited_verified_proofs=count,
                            reasons=reasons, final_candidate_sha256='0'*64 if wrong_candidate else native.sha(candidate/'candidate.json'))
                (results/'baseline-inheritance.json').write_text(json.dumps(data))
                return SimpleNamespace(returncode=code)

            def prove(command, log, env, cwd):
                fresh.append(list(map(str, command)))
                self.assertEqual(command[-2:], ['--rss-limit-gib', '28'])
                (work/'baselines').mkdir()
                (work/'baselines/receipt.json').write_text('{"actual_test_stub":true}')

            with patch.object(native.subprocess, 'run', inherit), patch.object(native, 'run', prove):
                error = None
                try:
                    native.full_baselines(candidate, root/'source/trisha/scripts', root/'checkout', work, results, {}, True)
                except ValueError as observed:
                    error = str(observed)
            return fresh, error, (results/'baselines/receipt.json').exists()

    def test_identical_receipt_inherits_without_new_proofs(self):
        fresh, error, retained = self.decision(0, 'inherited_full198_coverage', 198, [])
        self.assertEqual((fresh, error, retained), ([], None, False))

    def test_binary_difference_runs_and_retains_fresh_guarded_gate(self):
        fresh, error, retained = self.decision(3, 'needs_fresh_full198', None, ['changed binary'])
        self.assertEqual((len(fresh), error, retained), (1, None, True))

    def test_invalid_original_evidence_fails_without_fallback(self):
        fresh, error, retained = self.decision(1, 'needs_fresh_full198', None, ['invalid original'])
        self.assertFalse(fresh or retained)
        self.assertIn('fails closed', error)

    def test_exit_and_receipt_disagreement_fails(self):
        fresh, error, retained = self.decision(0, 'needs_fresh_full198', None, ['changed binary'])
        self.assertFalse(fresh or retained)
        self.assertIsNotNone(error)

    def test_different_candidate_receipt_fails(self):
        fresh, error, retained = self.decision(0, 'inherited_full198_coverage', 198, [], wrong_candidate=True)
        self.assertFalse(fresh or retained)
        self.assertIsNotNone(error)

    def test_incomplete_inheritance_fails(self):
        fresh, error, retained = self.decision(0, 'inherited_full198_coverage', 197, [])
        self.assertFalse(fresh or retained)
        self.assertIsNotNone(error)

    def test_final_verify_route_runs_installed_deadline_probe_before_return(self):
        # Explicit orchestration stubs test the real verify branch, without
        # representing any generated certificate or source as a measurement.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout, temporary = root/'checkout', root/'temporary'
            checkout.mkdir()
            temporary.mkdir()
            (checkout/'.github').mkdir()
            archive = b'archive'
            source = b'[]'
            digest = native.hashlib.sha256(archive).hexdigest()
            inputs = checkout/'.github/final-package-inputs.json'
            inputs.write_text(json.dumps(dict(validation_profile='final-host-ceiling-v1', source_sha256=digest)))
            target = 'aarch64-apple-darwin'
            asset = dict(asset_id=1, sha256=digest)
            selector = dict(validation_profile='final-host-ceiling-v1', status='active', phase='verify',
                            asset_id=1, source_sha256=digest, inputs_sha256=native.sha(inputs),
                            selfhost_kit=asset, binaries={target: asset},
                            corpora=[dict(target=t, **asset) for t in native.NU],
                            structured_corpora=[dict(target=t, **asset) for t in native.NU])
            (checkout/'.github/release-candidate.json').write_text(json.dumps(selector))
            calls = []

            def download(selected, destination, env, maximum=None):
                destination.write_bytes(archive)

            def extract(path, destination):
                destination.mkdir()
                if destination.name == 'unpacked':
                    (destination/'cyber-source').mkdir()
                    (destination/'cyber-source/sources.json').write_bytes(source)
                elif destination.name == 'installed':
                    package = destination/'cyber-tools'
                    (package/'share/trident-selfhost').mkdir(parents=True)
                    (package/'share/trident-selfhost/kit.json').write_bytes(b'kit')
                    (package/'candidate.json').write_text(json.dumps(dict(provenance_sha256=native.hashlib.sha256(source).hexdigest())))

            def command(args, log, env, cwd):
                calls.append(list(map(str, args)))
                if 'unpack' in args:
                    kit = temporary/'cyber-candidate/selfhost-kit'
                    kit.mkdir()
                    (kit/'kit.json').write_bytes(b'kit')

            before = Path.cwd()
            try:
                os.chdir(checkout)
                environment = dict(RELEASE_TARGET=target, RELEASE_SELECTOR='.github/release-candidate.json', RUNNER_TEMP=str(temporary))
                with patch.dict(os.environ, environment), patch.object(native.platform, 'machine', lambda: 'arm64'), \
                        patch.object(native, 'download', download), patch.object(native, 'extract', extract), \
                        patch.object(native, 'run', command), patch.object(native, 'pin_toolchain') as compiler:
                    native.main()
                    compiler.assert_not_called()
            finally:
                os.chdir(before)
            probes = [i for i, row in enumerate(calls) if row[2].endswith('/check-installed-host-ceiling.py')]
            corpora = [i for i, row in enumerate(calls) if row[2].endswith('/current-structured-corpus.py')]
            self.assertEqual(len(probes), 1)
            self.assertEqual(len(corpora), 6)
            self.assertGreater(probes[0], max(corpora))
            self.assertIn(str(temporary/'cyber-candidate/installed/cyber-tools'), calls[probes[0]])


if __name__ == '__main__':
    unittest.main()
