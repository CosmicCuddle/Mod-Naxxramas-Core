"""F15 *manual* recovery of a named rotated-old source after a simulated restart.

TEST-ONLY, no CLI/service/daemon/host integration, no automatic directory scan,
source switch or deletion. An operator supplies EVERY exact path and root in a
disposable fixture; no real PM2/Auth file or installed realm is accessed.

The prior single journal and checkpoint remain the ONLY replay authority.
Recovery succeeds only where its last checkpoint refers to an original inode,
that inode is still reachable at an explicitly consented path, and the LAST
durably journalled segment still matches its bytes. This is NOT authentication
of the owner host or proof the whole file is unchanged/complete. Lost/unlinked
old inodes cannot be recovered by a fresh process; fail closed.
"""
import hashlib
import os

from f15_consented_source_poll import _open_consented_regular
from f15_integrated_disposable_runner import IntegratedRunner, FailClosed, STREAMS
from f15_retained_old_inode_poll import RetainedOldInodePoll
from f15_source_admission import AdmissionError


class ManualOldInodeRecovery(RetainedOldInodePoll):
    """Read-only explicit original-inode reattachment, not next-file handoff."""

    def __init__(self, workspace, authorised_old_files):
        # Exactly three explicit (absolute file path, approved root) pairs,
        # NOT PM2 jlist after rotation: that describes NEW files.
        if set(authorised_old_files) != set(STREAMS):
            raise AdmissionError("three explicit old-source candidates required")
        self._sources = {}
        self._retained = {}
        IntegratedRunner.__init__(self, workspace)
        try:
            identities = set()
            for stream in sorted(STREAMS):
                pair = authorised_old_files[stream]
                if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                    raise AdmissionError("candidate must provide exact filename and approved root")
                path, root = pair
                ck = self._checkpoint(stream)
                if ck["seq"] < 2:
                    raise AdmissionError("no recorded byte segment; cannot authenticate old prefix")
                # Validate original journal chain BEFORE opening any candidate.
                chain = list(self._validated_chain(stream))
                matching = [(record, data) for record, data in chain
                            if record.seq == ck["seq"] and record.kind == "seg"]
                if len(matching) != 1:
                    raise AdmissionError("latest checkpoint is not an anchored byte segment")
                last, data = matching[0]
                if (last.dev, last.ino, last.end) != (ck["dev"], ck["ino"], ck["offset"]):
                    raise AdmissionError("journal identity/offset does not match checkpoint")
                fd, meta = _open_consented_regular(path, root)
                try:
                    if (meta.st_dev, meta.st_ino) != (ck["dev"], ck["ino"]):
                        raise AdmissionError("candidate inode does not match the journal")
                    if (meta.st_dev, meta.st_ino) in identities:
                        raise AdmissionError("old stream candidates share one physical inode")
                    if meta.st_size < ck["offset"]:
                        raise AdmissionError("candidate truncated below last journal offset")
                    if os.pread(fd, len(data), last.start) != data:
                        raise AdmissionError("last journalled source bytes differ; refuse replay")
                    # Historical size/hash identity is not a completeness guarantee.
                    identities.add((meta.st_dev, meta.st_ino))
                    self._retained[stream] = fd
                    self._sources[stream] = (path, root, meta.st_dev, meta.st_ino)
                except BaseException:
                    os.close(fd)
                    raise
        except BaseException:
            self.close()
            raise

    def recovery_label(self, stream):
        if stream not in self._retained:
            raise FailClosed("old source is closed or unrecognised")
        return ("manually reattached previous inode only; previous bytes before "
                "last segment and old-writer end/completeness NOT proven")
