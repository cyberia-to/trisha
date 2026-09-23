"""Actual native Windows job ownership/accounting; no proof work."""
import os
import subprocess
import sys
import unittest

if os.name == 'nt':
    import ctypes as C
    from ctypes import wintypes as W
    from windows_process import Job, api, close, open_process


@unittest.skipUnless(os.name == 'nt', 'native Windows Job Objects required')
class WindowsProcess(unittest.TestCase):
    def test_resident_memory_and_cleanup_of_owned_process(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        job = Job(process)
        try:
            self.assertIn(process.pid, job.pids())
            rss, available = job.sample()
            self.assertGreater(rss, 0)
            self.assertGreater(available, 0)
        finally:
            job.close()
            process.wait(timeout=10)
        self.assertIsNotNone(process.returncode)
        job.close()  # Cleanup is idempotent.

    def test_orphan_child_stays_owned_after_parent_exits(self):
        code = ('import subprocess,sys; sys.stdin.readline(); '
                'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]); '
                'print(p.pid,flush=True)')
        process = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True)
        job = Job(process)
        child = None
        try:
            process.stdin.write('start\n')
            process.stdin.flush()
            pid = int(process.stdout.readline())
            process.wait(timeout=10)
            self.assertIn(pid, job.pids())
            child = open_process(0x00100000, False, pid)  # SYNCHRONIZE
            self.assertTrue(child)
            job.close()
            wait = api('WaitForSingleObject', W.DWORD, W.HANDLE, W.DWORD)
            self.assertEqual(wait(child, 10000), 0)
        finally:
            job.close()
            if child:
                close(child)
            process.wait(timeout=10)
            process.stdin.close()
            process.stdout.close()


if __name__ == '__main__':
    unittest.main()
