"""Reject the observed PATH-shadowing error before preserving native assets."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'transport_native_rehearsal', Path(__file__).with_name('transport-native-rehearsal.py'))
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class ActualToolchainTests(unittest.TestCase):
    target = 'aarch64-apple-darwin'

    def test_pinned_native_rust_is_accepted(self):
        observed = ('rustc 1.89.0 (29483883e 2025-08-04)\n'
                    'host: aarch64-apple-darwin\nrelease: 1.89.0\n')
        self.assertEqual(transport.require_pinned_toolchain(
            {'toolchain': observed}, self.target), observed)

    def test_homebrew_path_shadowing_is_rejected(self):
        observed = ('rustc 1.95.0 (59807616e 2026-04-14) (Homebrew)\n'
                    'host: aarch64-apple-darwin\nrelease: 1.95.0\n')
        with self.assertRaisesRegex(ValueError, 'actual native Rust 1.89.0'):
            transport.require_pinned_toolchain({'toolchain': observed}, self.target)

    def test_cross_target_or_missing_version_is_rejected(self):
        for observed in ('', 'rustc 1.89.0 (29483883e 2025-08-04)\n',
                         'rustc 1.89.0 (29483883e 2025-08-04)\n'
                         'host: x86_64-apple-darwin\nrelease: 1.89.0\n'):
            with self.subTest(observed=observed), self.assertRaises(ValueError):
                transport.require_pinned_toolchain({'toolchain': observed}, self.target)


if __name__ == '__main__':
    unittest.main()
