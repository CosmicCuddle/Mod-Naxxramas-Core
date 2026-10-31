"""F15: opt-in, read-only *admission* of three real log sources.

No CLI, daemon, copying, file creation, log-content reads, cleanup, or PM2 calls.
NOT a collector or production authority. Caller must independently obtain an
explicitly authorised PM2 JSON export and approved source roots.
"""
from dataclasses import dataclass
import json
import os
from pathlib import PurePosixPath
import stat


class AdmissionError(ValueError):
    pass


@dataclass(frozen=True)
class Sample:
    stream: str
    dev: int
    ino: int
    size: int
    mtime_ns: int
    ctime_ns: int


def _components(path):
    if not isinstance(path, str) or not path.startswith('/') or '\x00' in path:
        raise AdmissionError('expected an explicit absolute POSIX path')
    parts = path.split('/')[1:]
    if not parts or any(p in ('', '.', '..') for p in parts):
        raise AdmissionError('ambiguous/path-traversing path')
    return tuple(parts)


def _under(file_path, root_path):
    file_parts, root_parts = _components(file_path), _components(root_path)
    if len(file_parts) <= len(root_parts) or file_parts[:len(root_parts)] != root_parts:
        raise AdmissionError('file outside the explicitly approved source root')
    return file_parts


def _sample_file(stream, file_path, approved_root):
    parts = _under(file_path, approved_root)
    # Directory-component-by-component open; rejects symlinks even in parents.
    dirfd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for comp in parts[:-1]:
            newfd = os.open(comp, os.O_RDONLY | os.O_DIRECTORY |
                            os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dirfd)
            os.close(dirfd)
            dirfd = newfd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW |
                     os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dirfd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise AdmissionError('source must be a unique regular file')
            return Sample(stream, info.st_dev, info.st_ino, info.st_size,
                          info.st_mtime_ns, info.st_ctime_ns)
        finally:
            os.close(fd)
    except OSError as e:
        raise AdmissionError('source cannot be safely opened') from e
    finally:
        os.close(dirfd)


def _pm2_paths(export_json, world_name, expected_executable):
    """Consume an operator-supplied PM2 jlist JSON snapshot, never invoke PM2."""
    if not world_name or not expected_executable or '/' in expected_executable:
        raise AdmissionError('explicit World process name/executable required')
    try:
        data = json.loads(export_json)
    except (TypeError, ValueError) as e:
        raise AdmissionError('invalid PM2 JSON') from e
    if not isinstance(data, list):
        raise AdmissionError('PM2 snapshot must be a process list')
    choices = [p for p in data if isinstance(p, dict) and p.get('name') == world_name]
    if len(choices) != 1:
        raise AdmissionError('World PM2 process is missing or ambiguous')
    p = choices[0]
    env = p.get('pm2_env')
    if not isinstance(env, dict) or env.get('status') != 'online':
        raise AdmissionError('World process not reported online in the supplied snapshot')
    exe = env.get('pm_exec_path')
    if not isinstance(exe, str) or PurePosixPath(exe).name != expected_executable:
        raise AdmissionError('unexpected World executable in PM2 snapshot')
    out, err = env.get('pm_out_log_path'), env.get('pm_err_log_path')
    _components(out)
    _components(err)
    if out == err:
        raise AdmissionError('PM2 stdout/stderr must remain distinct')
    return out, err


def admit_sources(export_json, world_name, expected_executable, auth_native_path,
                  world_approved_root, auth_approved_root):
    """Return only metadata; no content, filenames or sensitive log lines."""
    out, err = _pm2_paths(export_json, world_name, expected_executable)
    specs = (
        ('world-out', out, world_approved_root),
        ('world-err', err, world_approved_root),
        ('auth-native', auth_native_path, auth_approved_root),
    )
    samples = tuple(_sample_file(*s) for s in specs)
    if len({(s.dev, s.ino) for s in samples}) != 3:
        raise AdmissionError('the three streams alias the same physical source')
    return samples


def compare_sample(before, after):
    """Observational hint, NOT gap-free proof; never rewrites the originals."""
    if before.stream != after.stream:
        raise AdmissionError('cannot compare different streams')
    if (before.dev, before.ino) != (after.dev, after.ino):
        return 'replaced-or-rotated: old unread tail unknown'
    if after.size < before.size:
        return 'truncated: missing bytes unknown'
    if after.size > before.size:
        return 'grown: appended bytes unverified'
    if (before.mtime_ns, before.ctime_ns) != (after.mtime_ns, after.ctime_ns):
        return 'same-size-write-suspected: no completeness guarantee'
    return 'unchanged-observation: no completeness guarantee'
