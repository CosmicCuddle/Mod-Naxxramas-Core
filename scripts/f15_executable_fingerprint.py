"""Bounded prelaunch executable sample; never claims kernel execution identity."""
import hashlib
import os
from pathlib import Path
import shutil
import stat

MAX_EXECUTABLE_BYTES=512*1024*1024


def sample_executable(command, max_bytes=MAX_EXECUTABLE_BYTES):
    base={"kind":"prelaunch_regular_file_sample","status":"UNKNOWN"}
    if not isinstance(command,str) or not command or "\0" in command:
        return dict(base,reason="INVALID_COMMAND")
    try:
        found=shutil.which(command)
        if not found:return dict(base,reason="UNAVAILABLE")
        path=Path(found).resolve(strict=True)
        fd=os.open(path,os.O_RDONLY|getattr(os,"O_NONBLOCK",0)|getattr(os,"O_NOFOLLOW",0)|getattr(os,"O_CLOEXEC",0))
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):return dict(base,reason="NOT_REGULAR")
            if before.st_size>max_bytes:return dict(base,reason="TOO_LARGE")
            digest=hashlib.sha256();total=0
            while True:
                data=os.read(fd,min(1024*1024,max_bytes-total+1))
                if not data:break
                total+=len(data)
                if total>max_bytes:return dict(base,reason="TOO_LARGE")
                digest.update(data)
            after=os.fstat(fd)
            fields=("st_dev","st_ino","st_mode","st_size","st_mtime_ns","st_ctime_ns")
            if total!=before.st_size or any(getattr(before,k)!=getattr(after,k) for k in fields):
                return dict(base,reason="CHANGED_DURING_SAMPLE")
            return dict(base,status="SAMPLED",resolved_path=str(path),size=total,sha256=digest.hexdigest())
        finally:os.close(fd)
    except (OSError,ValueError,RuntimeError):
        return dict(base,reason="UNAVAILABLE")
