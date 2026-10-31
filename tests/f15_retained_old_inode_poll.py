"""F15 retired-inode tail proof — TEST-ONLY, not an operational collector.

The first authenticated-by-consent (NOT cryptographically attested) descriptor
is retained across polls, so a file renamed by a *fake* PM2 rotation can still
yield its unread old bytes. This deliberately NEVER opens/reads the new inode.
There is no automatic handoff, no promise of a complete drain, and no persistent
recovery of an old inode after process death. Source bytes are read only;
the inherited single journal + archives live only in a disposable workspace.
No command-line entry point, scheduler, PM2, tmux or host integration.
"""
import os

from f15_consented_source_poll import (ConsentedSourcePoll,
                                        _open_consented_regular)
from f15_source_admission import AdmissionError
from f15_integrated_disposable_runner import FailClosed


class RetainedOldInodePoll(ConsentedSourcePoll):
    """Hold original read-only source fd; keep its identity across pathname churn."""

    def __init__(self, workspace, pm2_json, world_name, expected_executable,
                 auth_native_path, world_root, auth_root):
        self._retained = {}
        super().__init__(workspace, pm2_json, world_name, expected_executable,
                         auth_native_path, world_root, auth_root)
        try:
            for stream, (path, root, dev, ino) in self._sources.items():
                fd, info = _open_consented_regular(path, root)
                if (info.st_dev, info.st_ino) != (dev, ino):
                    os.close(fd)
                    raise AdmissionError("source identity changed during original descriptor pin")
                self._retained[stream] = fd
        except BaseException:
            self.close()
            raise

    def source_name_status(self, stream):
        """Observed pathname identity; NOT proof the old writer has stopped."""
        if stream not in self._retained:
            raise FailClosed("unknown or closed retained stream")
        path, root, dev, ino = self._sources[stream]
        try:
            fd, info = _open_consented_regular(path, root)
        except AdmissionError:
            return "name-missing-or-unsafe; old fd still retained"
        else:
            os.close(fd)
        if (info.st_dev, info.st_ino) != (dev, ino):
            return "name-replaced; old fd still retained"
        return "same-original-inode; no completeness guarantee"

    def _open_source(self, stream):
        """Only duplicate the ORIGINAL descriptor; never adopt a replacement."""
        if stream not in self._retained:
            raise FailClosed("unknown or closed retained stream")
        fd = os.dup(self._retained[stream])
        try:
            info = os.fstat(fd)
            _path, _root, dev, ino = self._sources[stream]
            if (info.st_dev, info.st_ino) != (dev, ino):
                raise FailClosed("retained inode changed unexpectedly")
            # An old inode can be unlinked yet remain valid while already open;
            # never accept a NEW hard link that creates extra provenance ambiguity.
            if info.st_nlink not in (0, 1):
                raise FailClosed("retained source now has multiple hard links")
            return fd, info
        except BaseException:
            os.close(fd)
            raise

    def close(self):
        for fd in self._retained.values():
            os.close(fd)
        self._retained.clear()
        super().close()
