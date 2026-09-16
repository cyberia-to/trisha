"""Own and measure a Windows proof process tree using a native Job Object.

Loaded only on Windows. Working sets are RSS-like resident bytes, not commit
charge. Closing our private job kills its members, including orphan children.
"""
import ctypes as C
from ctypes import wintypes as W

K = C.WinDLL('kernel32', use_last_error=True)
SIZE = C.c_size_t


def api(name, result, *arguments):
    function = getattr(K, name)
    function.restype, function.argtypes = result, arguments
    return function


create = api('CreateJobObjectW', W.HANDLE, C.c_void_p, W.LPCWSTR)
set_info = api('SetInformationJobObject', W.BOOL, W.HANDLE, C.c_int, C.c_void_p, W.DWORD)
query = api('QueryInformationJobObject', W.BOOL, W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p)
assign = api('AssignProcessToJobObject', W.BOOL, W.HANDLE, W.HANDLE)
close = api('CloseHandle', W.BOOL, W.HANDLE)
open_process = api('OpenProcess', W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
memory = api('K32GetProcessMemoryInfo', W.BOOL, W.HANDLE, C.c_void_p, W.DWORD)
global_memory = api('GlobalMemoryStatusEx', W.BOOL, C.c_void_p)


class Basic(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64),
                ('flags', W.DWORD), ('min_working', SIZE), ('max_working', SIZE),
                ('active_limit', W.DWORD), ('affinity', SIZE),
                ('priority', W.DWORD), ('scheduling', W.DWORD)]


class Limits(C.Structure):
    _fields_ = [('basic', Basic), ('io', C.c_uint64 * 6),
                ('process_memory', SIZE), ('job_memory', SIZE),
                ('peak_process', SIZE), ('peak_job', SIZE)]


class ProcessMemory(C.Structure):
    _fields_ = [('size', W.DWORD), ('faults', W.DWORD),
                ('peak_working', SIZE), ('working', SIZE),
                ('peak_paged', SIZE), ('paged', SIZE),
                ('peak_nonpaged', SIZE), ('nonpaged', SIZE),
                ('pagefile', SIZE), ('peak_pagefile', SIZE)]


class GlobalMemory(C.Structure):
    _fields_ = [('size', W.DWORD), ('load', W.DWORD),
                ('total', C.c_uint64), ('available', C.c_uint64),
                ('pagefile', C.c_uint64), ('available_pagefile', C.c_uint64),
                ('virtual', C.c_uint64), ('available_virtual', C.c_uint64),
                ('extended', C.c_uint64)]


def checked(success):
    if not success:
        raise C.WinError(C.get_last_error())


class Job:
    def __init__(self, process):
        self.handle = create(None, None)
        checked(self.handle)
        try:
            limits = Limits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            checked(set_info(self.handle, 9, C.byref(limits), C.sizeof(limits)))
            # The benchmark runs in this process; its native proof threads and
            # any subsequent descendants stay in the owned job.
            checked(assign(self.handle, int(process._handle)))
        except BaseException:
            self.close()
            if process.poll() is None:
                process.kill()
            process.wait()
            raise

    def pids(self):
        for count in (64, 1024, 16384):
            class Ids(C.Structure):
                _fields_ = [('assigned', W.DWORD), ('count', W.DWORD), ('pids', SIZE * count)]
            data = Ids()
            success = query(self.handle, 3, C.byref(data), C.sizeof(data), None)
            if success and data.assigned == data.count and data.count <= count:
                return list(data.pids[:data.count])
            if not success and C.get_last_error() != 234:  # ERROR_MORE_DATA
                checked(False)
        raise RuntimeError('proof job exceeds process accounting limit')

    def sample(self):
        rss = 0
        for pid in self.pids():
            handle = open_process(0x0400 | 0x0010, False, pid)
            if not handle:
                if pid not in self.pids():
                    continue  # Exited between job enumeration and OpenProcess.
                checked(False)
            try:
                info = ProcessMemory()
                info.size = C.sizeof(info)
                if not memory(handle, C.byref(info), info.size):
                    if pid not in self.pids():
                        continue
                    checked(False)
                rss += info.working
            finally:
                close(handle)
        available = GlobalMemory()
        available.size = C.sizeof(available)
        checked(global_memory(C.byref(available)))
        return rss, available.available

    def close(self):
        if self.handle:
            checked(close(self.handle))
            self.handle = None
