"""Windows Job Object: applies only to our newly spawned stdin-blocked worker."""
from __future__ import annotations
import os

class WindowsJob:
    def __init__(self, process, memory_bytes):
        if os.name != 'nt':
            raise RuntimeError('Windows only')
        import ctypes as C
        from ctypes import wintypes as W
        self.k = C.WinDLL('kernel32', use_last_error=True)
        class Basic(C.Structure):
            _fields_ = [('ProcessTime',C.c_longlong),('JobTime',C.c_longlong),('LimitFlags',W.DWORD),
                ('MinWorking',C.c_size_t),('MaxWorking',C.c_size_t),('ActiveProcessLimit',W.DWORD),
                ('Affinity',C.c_size_t),('Priority',W.DWORD),('Scheduling',W.DWORD)]
        class IO(C.Structure):
            _fields_ = [(n,C.c_ulonglong) for n in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
        class Extended(C.Structure):
            _fields_ = [('Basic',Basic),('IO',IO),('ProcessMemory',C.c_size_t),('JobMemory',C.c_size_t),
                        ('PeakProcessMemory',C.c_size_t),('PeakJobMemory',C.c_size_t)]
        self.k.CreateJobObjectW.argtypes = [C.c_void_p,W.LPCWSTR]
        self.k.CreateJobObjectW.restype = W.HANDLE
        self.k.SetInformationJobObject.argtypes = [W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
        self.k.SetInformationJobObject.restype = W.BOOL
        self.k.AssignProcessToJobObject.argtypes = [W.HANDLE,W.HANDLE]
        self.k.AssignProcessToJobObject.restype = W.BOOL
        self.k.CloseHandle.argtypes = [W.HANDLE]
        self.k.CloseHandle.restype = W.BOOL
        self.handle = self.k.CreateJobObjectW(None,None)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        info = Extended()
        info.Basic.LimitFlags = 0x2000 | 0x100 | 0x8
        info.Basic.ActiveProcessLimit = 4
        info.ProcessMemory = memory_bytes
        try:
            if not self.k.SetInformationJobObject(self.handle,9,C.byref(info),C.sizeof(info)):
                raise C.WinError(C.get_last_error())
            if not self.k.AssignProcessToJobObject(self.handle,W.HANDLE(int(process._handle))):
                raise C.WinError(C.get_last_error())
        except Exception:
            self.close()
            raise
    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None
