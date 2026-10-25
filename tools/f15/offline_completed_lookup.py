"""F15 S4e: READ-ONLY S3 completed-attempt lookup for S4d fixture gating.

This only reads S2 incident and S3 sidecar files from an ALREADY EXISTING
0700 private test directory. Never starts servers, reads user root paths,
attests actual OS events, runs probes or writes a restart result.

A SHA-256 trailer proves consistency, NOT that the sender was a supervisor.
Lookups are advisory snapshots; a future single-writer integration must
serialize begin/finish with S3 publication, handle crashes and authenticate
the owner-approved source independently.
"""
from __future__ import annotations

import os
import re
import stat
import uuid

from offline_restart import RestartSidecarStore, impossible_future
from offline_store import NAMESPACE, safe_name

INCIDENT_ID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")


class OfflineCompletedRestartLookup:
    """Callable completed-attempt lookup consumed by S4d finished_lookup.

    Return 'succeeded'/'failed' for an existing verified offline sidecar,
    None for a new attempt whose ORIGINAL incident is verified, or raise
    ValueError on missing original, tampered, unsafe or ambiguous evidence.
    S4d fail-closes on exceptions. This does NOT prove actual child death.
    """

    def __init__(self, store: RestartSidecarStore):
        if not isinstance(store, RestartSidecarStore):
            raise TypeError("S3-compatible store required; never use legacy S2")
        self.store = store

    def __call__(self, key: tuple[str, str]):
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError("incident and attempt tuple required")
        incident_id, attempt = key
        if not isinstance(incident_id, str) or not INCIDENT_ID.fullmatch(incident_id):
            raise ValueError("noncanonical incident ID")
        try:
            canonical = str(uuid.UUID(incident_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("invalid incident ID") from exc
        if canonical != incident_id:
            raise ValueError("noncanonical incident ID")
        safe_name(attempt)

        sidecar_id = str(uuid.uuid5(NAMESPACE,
                                  "restart\x1f" + incident_id + "\x1f" + attempt))
        filename = "restart-" + incident_id + "-" + sidecar_id + ".txt"

        with self.store._locked():
            originals, _ = self.store._reports()
            original = next(((name, info) for name, info in originals
                             if info["incident_id"] == incident_id), None)
            if original is None:
                raise ValueError("original immutable crash incident unverified")
            original_name, original_info = original
            self._safe_private_file(original_name)

            try:
                os.stat(filename, dir_fd=self.store._fd, follow_symlinks=False)
            except FileNotFoundError:
                return None
            self._safe_private_file(filename)
            info = self.store._read_sidecar(filename)
            if (info is None or info["incident_id"] != incident_id or
                    info["attempt"] != attempt or
                    info["sidecar_id"] != sidecar_id or
                    info["observed_utc"] < original_info["end_utc"] or
                    impossible_future(info["observed_utc"])):
                raise ValueError("unverified or orphan restart sidecar")
            return info["outcome"]

    def _safe_private_file(self, filename: str):
        # Lock is shared with S3/S2 compatible writers; pin the existing
        # directory FD and refuse links, symlinks and any public permissions.
        try:
            fd = os.open(filename, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                         dir_fd=self.store._fd)
        except OSError as exc:
            raise ValueError("unsafe or unreadable immutable record") from exc
        try:
            st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or
                    st.st_uid != os.geteuid() or st.st_mode & 0o177):
                raise ValueError("untrusted owner, mode or link count")
        finally:
            os.close(fd)
