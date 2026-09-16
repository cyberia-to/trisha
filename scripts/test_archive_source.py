import importlib.util
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location("archive", Path(__file__).with_name("archive-source.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ArchiveTest(unittest.TestCase):
    def test_zip_reproduces_binary_bytes_and_rejects_overwrite_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent/'source'
            (root/'bin').mkdir(parents=True)
            (root/'bin/tool.exe').write_bytes(b'PE binary fixture')
            (root/'readme.txt').write_bytes(b'portable archive')
            first, second = parent/'a.zip', parent/'b.zip'
            MODULE.archive(root, first, 0, 'cyber-tools')
            os.utime(root/'bin/tool.exe', (12345, 12345))
            MODULE.archive(root, second, 99, 'cyber-tools')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as result:
                self.assertEqual(result.read('cyber-tools/bin/tool.exe'), b'PE binary fixture')
                self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in result.infolist()))
            with self.assertRaises(FileExistsError):
                MODULE.archive(root, first, 0, 'cyber-tools')
            (root/'link').symlink_to('readme.txt')
            with self.assertRaises(ValueError):
                MODULE.archive(root, parent/'bad.zip', 0, 'cyber-tools')
            self.assertFalse((parent/'bad.zip').exists())

    def test_bytes_ignore_machine_paths_and_mtimes_and_preserve_build_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            for folder, mtime in [("first", 1), ("different-name", 5000)]:
                root = parent / folder
                root.mkdir()
                (root / "lib.rs").write_bytes(b"// source\n")
                (root / "run.nu").write_bytes(b"#!/usr/bin/env nu\n")
                (root / "run.nu").chmod(0o755)
                (root / "linked.rs").symlink_to("lib.rs")
                (root / "nested").mkdir()
                (root / "nested" / ("x" * 120)).write_bytes(b"long path")
                for path in [root, *root.rglob("*")]:
                    os.utime(path, (mtime, mtime), follow_symlinks=False)
                MODULE.archive(root, parent / (folder + ".tar.gz"), 1000)
            first = parent / "first.tar.gz"
            self.assertEqual(first.read_bytes(), (parent / "different-name.tar.gz").read_bytes())
            with tarfile.open(first) as result:
                self.assertEqual(b"// source\n", result.extractfile("cyber-source/lib.rs").read())
                self.assertEqual(0o755, result.getmember("cyber-source/run.nu").mode)
                self.assertEqual("lib.rs", result.getmember("cyber-source/linked.rs").linkname)
                self.assertTrue(result.getmember("cyber-source/linked.rs").issym())
                self.assertTrue(all(m.uid == m.gid == 0 and m.mtime == 1000 for m in result))
            original = first.read_bytes()
            with self.assertRaises(FileExistsError):
                MODULE.archive(parent / "first", first, 1000)
            self.assertEqual(original, first.read_bytes())
            (parent / "alias").symlink_to(parent / "first", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "outside"):
                MODULE.archive(parent / "first", parent / "alias/inside.tar.gz", 1000)
            self.assertFalse((parent / "first/inside.tar.gz").exists())
            (parent / "occupied.tar.gz").symlink_to(parent / "missing.tar.gz")
            with self.assertRaises(FileExistsError):
                MODULE.archive(parent / "first", parent / "occupied.tar.gz", 1000)
            self.assertFalse((parent / "missing.tar.gz").exists())


if __name__ == "__main__":
    unittest.main()
