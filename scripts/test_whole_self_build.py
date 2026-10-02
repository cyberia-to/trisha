"""Orchestration tests; no compiler execution or remote publication."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import native_proof_inputs as native
import whole_self_host as host
import whole_self_inputs as inputs

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retention', ROOT / 'scripts/whole-self-retain.py')
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class Orchestration(unittest.TestCase):
    def test_only_explicit_reviewed_events_authorize_replay_and_retention(self):
        environment = dict(GITHUB_REPOSITORY='cyberia-to/trisha', GITHUB_EVENT_NAME='push',
                           GITHUB_REF='refs/heads/test/0.4-whole-self-build-ci', RETAIN_DRAFT='true')
        self.assertTrue(inputs.authorization(ROOT, environment)['retain_draft'])
        for changed in ({'GITHUB_REPOSITORY': 'elsewhere/trisha'},
                        {'GITHUB_EVENT_NAME': 'pull_request'}, {'GITHUB_EVENT_NAME': 'schedule'},
                        {'GITHUB_REF': 'refs/heads/master'}, {'RETAIN_DRAFT': 'false'},
                        {'RETAIN_DRAFT': ''}, {'RETAIN_DRAFT': '1'}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                inputs.authorization(ROOT, dict(environment, **changed))
        for selection in ('true', 'false'):
            actual = inputs.authorization(ROOT, dict(environment, GITHUB_EVENT_NAME='workflow_dispatch', RETAIN_DRAFT=selection))
            self.assertEqual(actual['retain_draft'], selection == 'true')
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            (checkout / '.github').mkdir()
            selector = inputs.load(ROOT / '.github/whole-self-build-activation.json')
            for changed in ({'push_authorized': False}, {'push_authorized': 1},
                            {'retain_draft': False}, {'retain_draft': 1},
                            {'branch': 'master'}, {'repository': 'elsewhere/trisha'},
                            {'format': 'unknown'}, {'extra': True}):
                (checkout / '.github/whole-self-build-activation.json').write_text(json.dumps(dict(selector, **changed)))
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    inputs.authorization(checkout, environment)

    def test_bootstrap_inventory_covers_workflow_and_all_selectors(self):
        actual = inputs.bootstrap(ROOT)
        for name in ('scripts/native_proof_inputs.py', '.github/workflows/whole-self-build.yml',
                     '.github/whole-self-build-sources.json', '.github/whole-self-build-input.json',
                     '.github/whole-self-build-activation.json'):
            self.assertEqual(actual[name], inputs.identity(ROOT / name))

    def test_input_and_source_selectors_are_complete_and_pinned(self):
        asset = inputs.asset_selector(ROOT / '.github/whole-self-build-input.json')
        self.assertEqual(asset['asset_id'], 604704433)
        sources = native.selector(ROOT / '.github/whole-self-build-sources.json')
        self.assertEqual(len(sources['sources']), 12)
        self.assertEqual(sources['sources']['joy'], '6e0ec4d8440e2521df08f442d64f54e667044716')
        self.assertEqual(sources['sources']['nox'], '2f09ca3c3f18ae470365310cca8db5208eda75c6')
        self.assertEqual(sources['sources']['zheng'], '0d7ba6d422d9b825f9685e903e55252f88ebecd9')

    def test_archive_names_are_regular_relative_canonical_paths(self):
        self.assertEqual(str(inputs.safe_name('whole-proof-inputs/inputs/c1.dag')), 'whole-proof-inputs/inputs/c1.dag')
        for name in ('../escape', '/absolute', 'a/../b', 'a\\b', 'a//b', 'C:drive', ''):
            with self.assertRaises(ValueError):
                inputs.safe_name(name)

    def test_chunk_reconstruction_has_exact_identity_and_boundaries(self):
        original = bytes(range(251)) * 10000
        with tempfile.TemporaryDirectory() as directory:
            stream = io.BytesIO(original)
            parts, hashes = [], []
            for n in range(3):
                path = Path(directory) / str(n)
                value = retention.write_chunk(stream, path, 1024**2)
                self.assertEqual(value, inputs.identity(path))
                self.assertLessEqual(value['bytes'], 1024**2)
                parts.append(path.read_bytes())
                hashes.append(value)
            self.assertEqual(b''.join(parts), original)
            self.assertEqual(hashlib.sha256(b''.join(parts)).hexdigest(), hashlib.sha256(original).hexdigest())
            self.assertEqual([p['bytes'] for p in hashes], [1024**2, 1024**2, len(original) - 2 * 1024**2])
            self.assertEqual(stream.read(1), b'')

    def test_cleanup_cannot_run_on_local_or_unidentified_host(self):
        commands = []
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                host.cleanup(Path('/unused'), lambda *args, **kwargs: commands.append(args))
        self.assertEqual(commands, [])
        self.assertTrue(all(Path(p).is_absolute() and '..' not in Path(p).parts for p in host.SDK_PATHS))
        self.assertNotIn('/opt/hostedtoolcache', host.SDK_PATHS)

    def test_build_sanitizer_drops_token_and_toolchain_overrides(self):
        actual = native.sanitized({'PATH': '/known', 'GH_TOKEN': 'sentinel', 'GITHUB_TOKEN': 'sentinel',
                                   'RUSTC_WRAPPER': 'bad', 'RUSTFLAGS': 'bad', 'CARGO_HOME': '/bad',
                                   'CC': 'bad', 'GIT_CONFIG_GLOBAL': '/bad'})
        for name in ('GH_TOKEN', 'GITHUB_TOKEN', 'RUSTC_WRAPPER', 'RUSTFLAGS', 'CARGO_HOME', 'CC'):
            self.assertNotIn(name, actual)
        self.assertEqual(actual['GIT_CONFIG_GLOBAL'], os.devnull)

    @unittest.skipUnless(os.environ.get('WHOLE_SELF_INPUT_ARCHIVE'), 'explicit local compact frozen input required')
    def test_actual_compact_archive_and_accepted_coordinate_mapping(self):
        asset = inputs.asset_selector(ROOT / '.github/whole-self-build-input.json')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'frozen'
            inventory = inputs.admit(Path(os.environ['WHOLE_SELF_INPUT_ARCHIVE']), path, asset)
            self.assertEqual(len(inventory), 111)
            sources = [v for n, v in inventory.items() if n.startswith('inputs/sources/')]
            self.assertEqual((len(sources), sum(v['bytes'] for v in sources)), (94, 370544))
            for generation in (1, 2):
                accepted = inputs.load(path / f'inputs/accepted-c{generation + 1}-step.json')
                old = accepted['execution']['execution']
                value = {k: old[k] for k in ('program_particle', 'input_particle', 'output_particle', 'charged_reductions', 'compiler_job')}
                value.update(logical_peak_frames=old['peak_frames'], expanded_steps=old['compaction']['evaluator_checkpoints'] - 1,
                             format='joy-nox-disclosed-compiler-v1', disclosure='complete public witness', physical_resource_claim='unattested')
                # This is a field-mapping test using historical coordinates, not a new proof result.
                inputs.compare(dict(ok=True, schema='joy/artifact-verification/v1', verification=value), accepted, 'verify')
            self.assertEqual(inputs.identity(path / 'inputs/c2.dag')['sha256'], inputs.PROFILE['expected_artifact_sha256'])


if __name__ == '__main__':
    unittest.main()
