"""F15 test-only controlled input seam: *real file descriptors* -> disposable journal.

NO COMMAND LINE ENTRY POINT. NEVER install, schedule, import into a server or run
against owner files without separately documented permission. This proof harness
reads source bytes when explicitly called: unlike the metadata-only parent #257.
All checkpoints, archives and deletion remain inside an IntegratedRunner-owned
TemporaryDirectory. Input files are opened READ ONLY and never altered.

The source locations originate only from caller-supplied PM2 JSON and an explicit
Auth *native* log path. PM2 JSON is NOT authenticated. This seam is not an
operational collector or a completeness guarantee.
"""
import os
import stat

from f15_source_admission import (_components, _under, _pm2_paths,
                                  admit_sources, AdmissionError)
from f15_integrated_disposable_runner import IntegratedRunner, FailClosed

SOURCE_LABELS = (
    ("Worldserver-out", "world-out"),
    ("Worldserver-err", "world-err"),
    ("Authserver-native", "auth-native"),
)


def _open_consented_regular(path, root):
    """Open through directory fds; reject symlinks/alias primitives at every hop.

    Return a validated O_RDONLY descriptor; caller owns and MUST close it.
    """
    parts = _under(path, root)
    dirfd = None
    try:
        dirfd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        for comp in parts[:-1]:
            nxt = os.open(comp, os.O_RDONLY | os.O_DIRECTORY |
                          os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dirfd)
            os.close(dirfd)
            dirfd = nxt
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW |
                     os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dirfd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise AdmissionError("source is not a unique regular file")
            return fd, info
        except BaseException:
            os.close(fd)
            raise
    except OSError as exc:
        raise AdmissionError("source failed safe read-only open") from exc
    finally:
        if dirfd is not None:
            os.close(dirfd)


class ConsentedSourcePoll(IntegratedRunner):
    """Single-chain test bridge: a real file is read by the *existing* poll().

    No secondary source checkpoint or copy-forward spool. All progress records
    are the original synthetic IntegratedRunner journal/checkpoint/manifest.
    Only the _open_source hook changes; sealing never reads the input again.

    A new inode/path requires fresh explicit admission; even if PM2 rotating
    caused it, do not silently skip the unread old tail or assert complete logs.
    """

    def __init__(self, workspace, pm2_json, world_name, expected_executable,
                 auth_native_path, world_root, auth_root):
        out, err = _pm2_paths(pm2_json, world_name, expected_executable)
        samples = admit_sources(pm2_json, world_name, expected_executable,
                                auth_native_path, world_root, auth_root)
        files = (out, err, auth_native_path)
        roots = (world_root, world_root, auth_root)
        self._sources = {}
        for (stream, label), path, root, sample in zip(SOURCE_LABELS, files, roots, samples):
            if sample.stream != label:
                raise AdmissionError("source order changed during admission")
            _components(path)
            self._sources[stream] = (path, root, sample.dev, sample.ino)
        super().__init__(workspace)

        # Existing journal identity must not be silently rebound on a restart.
        try:
            for stream, (path, root, dev, ino) in self._sources.items():
                ck = self._checkpoint(stream)
                if ck["seq"] and (ck["dev"], ck["ino"]) != (dev, ino):
                    raise AdmissionError("source inode changed since previous journal; review unread tail")
        except BaseException:
            self.close()
            raise

    def _open_source(self, stream):
        if stream not in self._sources:
            raise FailClosed("unsupported input stream")
        path, root, dev, ino = self._sources[stream]
        try:
            fd, info = _open_consented_regular(path, root)
        except AdmissionError as exc:
            raise FailClosed("source no longer passes read-only admission") from exc
        if (info.st_dev, info.st_ino) != (dev, ino):
            os.close(fd)
            raise FailClosed("source was replaced/rotated; old unread tail unknown; stop for review")
        return fd, info
