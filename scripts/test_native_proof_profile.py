"""Adversarial tests for selector, native-host and source-closure guards."""
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import native_proof_inputs as guard


class NativeProofInputs(unittest.TestCase):
    def test_selector_requires_exact_complete_unique_source_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'selector.json'
            value = dict(format='native-public-proof-profile-v1', rust='1.89.0',
                         sources={name: 'a' * 40 for name in guard.REPOSITORIES})
            path.write_text(json.dumps(value))
            self.assertEqual(guard.selector(path), value)
            for bad in [dict(value, rust='stable'), dict(value, extra=True),
                        dict(value, sources={k: v for k, v in value['sources'].items() if k != 'tade'}),
                        dict(value, sources=dict(value['sources'], joy='main'))]:
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    guard.selector(path)
            path.write_text('{"format":1,"format":2}')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                guard.selector(path)

    def test_os_python_architecture_compiler_host_and_versions_all_bind(self):
        target = 'aarch64-pc-windows-msvc'
        rustc = 'rustc 1.89.0\nhost: ' + target + '\nrelease: 1.89.0\n'
        cargo = 'cargo 1.89.0 (abc 2025-06-23)\n'
        guard.native_host(target, 'Windows', 'ARM64', rustc, cargo)
        for system, machine, rust, carg in [
            ('Linux', 'ARM64', rustc, cargo), ('Windows', 'AMD64', rustc, cargo),
            ('Windows', 'ARM64', rustc.replace('aarch64-', 'x86_64-'), cargo),
            ('Windows', 'ARM64', rustc.replace('1.89.0', '1.90.0'), cargo),
            ('Windows', 'ARM64', rustc, cargo.replace('1.89.0', '1.90.0')),
        ]:
            with self.assertRaises(ValueError):
                guard.native_host(target, system, machine, rust, carg)

    def test_build_environment_drops_authentication_and_git_overrides(self):
        original = dict(PATH='tools', HOME='owner', GH_TOKEN='s', GITHUB_TOKEN='s',
                        ACTIONS_RUNTIME_TOKEN='s', AWS_SECRET_ACCESS_KEY='s', PASSWORD='s',
                        SSH_AUTH_SOCK='s', GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='x',
                        GIT_CONFIG_VALUE_0='s', RUSTFLAGS='wrong', CARGO_BUILD_TARGET='wrong',
                        RUSTC='wrong', RUSTDOC='wrong', RUSTC_WRAPPER='wrong',
                        RUSTC_WORKSPACE_WRAPPER='wrong', CARGO_TARGET_X_RUSTFLAGS='wrong',
                        RUSTC_BOOTSTRAP='wrong', CC='wrong', SDKROOT='wrong')
        clean = guard.sanitized(original)
        self.assertEqual(clean['HOME'], 'owner')
        self.assertEqual(clean['PATH'], 'tools')
        self.assertFalse(any(key in clean for key in original if key not in {'HOME', 'PATH'}))
        self.assertEqual(clean['GIT_CONFIG_GLOBAL'], os.devnull)

    def test_required_native_tests_cannot_be_filtered_or_ignored(self):
        for log in ['', 'test result: ok. 0 passed; 0 failed', 'test cli ... ignored\n', 'test other ... ok\n']:
            with self.assertRaises(ValueError):
                guard.passed_tests(log, ['cli'])
        self.assertEqual(guard.passed_tests('test module::cli ... ok\n', ['cli']), ['module::cli'])

    def test_warning_output_and_platform_specific_cli_requirements(self):
        self.assertEqual(guard.warnings('normal output\n'), [])
        self.assertEqual(len(guard.warnings('warning: manifest key\nwarning[unused]: code\n')), 2)
        spec = importlib.util.spec_from_file_location('native_profile', Path(__file__).with_name('native-proof-profile.py'))
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        self.assertEqual(len(driver.required_cli_tests('Windows')), 3)
        for system in ('Darwin', 'Linux'):
            self.assertEqual(len(driver.required_cli_tests(system)), 4)
            self.assertIn(driver.UNIX_CLI_TEST, driver.required_cli_tests(system))
        self.assertNotIn(driver.UNIX_CLI_TEST, driver.required_cli_tests('Windows'))

    def test_metadata_must_close_over_selected_real_local_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp); family = top / 'family'; (family / 'joy').mkdir(parents=True)
            manifest = family / 'joy/Cargo.toml'; manifest.write_text('[package]\n')
            package = dict(name='joy-rs', version='1', source=None, manifest_path=str(manifest))
            value = guard.closure(dict(packages=[package]), family, {'joy': 'a' * 40})
            self.assertEqual(value[0]['origin']['repository'], 'joy')
            outside = top / 'outside.toml'; outside.write_text('')
            for path, selected in [(outside, {'joy': 'a' * 40}), (manifest, {})]:
                with self.assertRaises(ValueError):
                    guard.closure(dict(packages=[dict(package, manifest_path=str(path))]), family, selected)

    def test_inventory_detects_changed_missing_extra_and_ignored_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            family = Path(tmp); root = family / 'joy'; root.mkdir()
            def run(name, command):
                return subprocess.check_output(list(map(str, command)), stderr=subprocess.DEVNULL).decode()
            run('init', ['git', 'init', root])
            for key, value in [('user.name', 'Fixture'), ('user.email', 'fixture@example.invalid')]:
                run('config', ['git', '-C', root, 'config', key, value])
            (root / 'source.rs').write_text('fn main() {}\n')
            (root / '.gitignore').write_text('ignored\n')
            run('add', ['git', '-C', root, 'add', 'source.rs', '.gitignore'])
            run('commit', ['git', '-C', root, 'commit', '-m', 'fixture'])
            revision = run('head', ['git', '-C', root, 'rev-parse', 'HEAD']).strip()
            sources = {'joy': revision}
            before = guard.inventory(family, sources, run, 'before')
            self.assertEqual(len(before['joy']['files']), 2)
            (root / 'ignored').write_text('unrecorded source')
            with self.assertRaises(ValueError):
                guard.inventory(family, sources, run, 'extra')
            (root / 'ignored').unlink()
            (root / 'source.rs').write_text('changed')
            with self.assertRaises(ValueError):
                guard.inventory(family, sources, run, 'changed')
            (root / 'source.rs').unlink()
            with self.assertRaises(ValueError):
                guard.inventory(family, sources, run, 'missing')


if __name__ == '__main__':
    unittest.main()
