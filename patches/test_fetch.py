import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("fetch", Path(__file__).with_name("fetch.py"))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def crate(extra=None):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        for name, value in [("example-1.0.0/Cargo.toml", b"[package]\n"),
                            *(([extra]) if extra else [])]:
            member = tarfile.TarInfo(name)
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    return data.getvalue()


class FetchTests(unittest.TestCase):
    def test_archive_bytes_override_mutable_source_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "registry/src/host/example-1.0.0"
            source.mkdir(parents=True)
            (source / "Cargo.toml").write_text("tampered source")
            cache = root / "registry/cache/host"
            cache.mkdir(parents=True)
            data = crate()
            expected = hashlib.sha256(data).hexdigest()
            (cache / "example-1.0.0.crate").write_bytes(data)
            with patch.object(fetch.urllib.request, "urlopen", side_effect=AssertionError("unexpected network")):
                actual = fetch.source_bytes("example", "1.0.0", expected, root)
            destination = root / "vendor/example"
            fetch.install(actual, "example", "1.0.0", expected, destination)
            self.assertEqual((destination / "Cargo.toml").read_bytes(), b"[package]\n")

    def test_checksum_and_traversal_errors_preserve_existing_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "example"
            destination.mkdir()
            (destination / "preserved").write_text("old installation")
            data = crate()
            with self.assertRaisesRegex(ValueError, "checksum"):
                fetch.install(data, "example", "1.0.0", "0" * 64, destination)
            data = crate(("example-1.0.0/../../escaped", b"hostile"))
            with self.assertRaisesRegex(ValueError, "archive entry"):
                fetch.install(data, "example", "1.0.0", hashlib.sha256(data).hexdigest(), destination)
            self.assertEqual((destination / "preserved").read_text(), "old installation")
            self.assertFalse((root / "escaped").exists())
            self.assertEqual(list(root.iterdir()), [destination])


if __name__ == "__main__":
    unittest.main()
