import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("snapshot", Path(__file__).with_name("snapshot-source.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SnapshotTest(unittest.TestCase):
    def test_preserves_dirty_sources_and_records_exact_copied_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            def git(*args):
                return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL)
            git("init")
            (root / "code.rs").write_text("old")
            (root / "deleted.rs").write_text("deleted")
            (root / ".gitignore").write_text("ignored.rs\n")
            source_target = root / "src/config/target"
            source_target.mkdir(parents=True)
            for name in ["mod.rs", "package.rs", "discover.rs"]:
                (source_target / name).write_text("// actual compiler source\n")
            (root / "cli").mkdir()
            (root / "cli/build.rs").write_text("fn main() {}")
            nested = root / "crates/helper"
            nested.mkdir(parents=True)
            (nested / "Cargo.toml").write_text('[package]\nname="helper"\nversion="0.1.0"\n')
            git("add", ".")
            git("-c", "user.name=Snapshot Test", "-c", "user.email=snapshot@example.invalid", "commit", "-m", "fixture")
            (root / "code.rs").write_text("current")
            (root / "deleted.rs").unlink()
            (root / "new.json").write_text('{"capability": true}')
            (root / "ignored.rs").write_text("ignored")
            (root / "target").mkdir()
            (root / "target/cache.rs").write_text("cache")
            (nested / "target").mkdir()
            (nested / "target/cache.rs").write_text("nested Cargo output")
            before = git("status", "--porcelain=v1")
            destination = Path(temporary) / "copy"
            record = MODULE.snapshot(root, destination)
            self.assertEqual(before, git("status", "--porcelain=v1"))
            self.assertEqual("current", (destination / "code.rs").read_text())
            self.assertTrue((destination / "new.json").exists())
            self.assertFalse((destination / "deleted.rs").exists())
            self.assertFalse((destination / "ignored.rs").exists())
            self.assertFalse((destination / "target").exists())
            self.assertFalse((destination / "crates/helper/target").exists())
            for name in ["mod.rs", "package.rs", "discover.rs"]:
                self.assertTrue((destination / "src/config/target" / name).is_file())
            self.assertTrue((destination / "cli/build.rs").is_file())
            self.assertEqual("working-tree-snapshot", record["mode"])
            self.assertTrue(record["dirty"])
            for entry in record["files"]:
                self.assertEqual(entry["sha256"], hashlib.sha256((destination / entry["path"]).read_bytes()).hexdigest())
            json.dumps(record)


if __name__ == "__main__":
    unittest.main()
