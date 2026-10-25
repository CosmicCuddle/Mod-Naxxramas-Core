"""F15 S4e: READ-ONLY S3 completed-attempt lookup for S4d fixture gating.

This verifies S2 incident and S3 sidecar files from an ALREADY EXISTING
0700 private test directory. Under the shared store lock it may unlink ONLY
an authenticated abandoned S2/S3 private temporary hardlink to the verified
final record. Never starts servers, reads user root paths, attests actual OS
events, runs probes or writes a restart result.

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
OWNED_TEMP = re.compile(r"^\.f15-s2-[0-9a-f]{32}$")


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
            # Verify content BEFORE any orphan cleanup; refuse to alter a
            # malformed, attacker-supplied or orphaned final record.
            info = self.store._read_sidecar(filename)
            if (info is None or info["incident_id"] != incident_id or
                    info["attempt"] != attempt or
                    info["sidecar_id"] != sidecar_id or
                    info["observed_utc"] < original_info["end_utc"] or
                    impossible_future(info["observed_utc"])):
                raise ValueError("unverified or orphan restart sidecar")
            self._safe_private_file(filename)
            if self.store._read_sidecar(filename) != info:
                raise ValueError("sidecar changed during locked validation")
            return info["outcome"]

    def _safe_private_file(self, filename: str):
        # Called ONLY with the S2/S3 shared flock held. A valid S2/S3 writer
        # links its fsynced .f15-s2-<32 hex> temp to final and unlinks temp;
        # child death between those calls leaves precisely two inode links.
        # Never allow a generic/external hardlink or reaper of unrelated files.
        try:
            fd = os.open(filename, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                         dir_fd=self.store._fd)
        except OSError as exc:
            raise ValueError("unsafe or unreadable immutable record") from exc
        try:
            st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or
                    st.st_uid != os.geteuid() or st.st_mode & 0o177):
                raise ValueError("untrusted owner, mode or link count")
            if st.st_nlink == 2:
                self._reap_matching_owned_temp_locked(st)
                # A removed temp must leave the SAME pinned final inode.
                try:
                    current = os.stat(filename, dir_fd=self.store._fd,
                                      follow_symlinks=False)
                except OSError as exc:
                    raise ValueError("immutable filename unavailable") from exc
                if (current.st_dev, current.st_ino) != (st.st_dev, st.st_ino):
                    raise ValueError("immutable filename changed")
                st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or
                    st.st_uid != os.geteuid() or st.st_mode & 0o177 or
                    st.st_nlink != 1):
                raise ValueError("untrusted owner, mode or link count")
        finally:
            os.close(fd)

    def _reap_matching_owned_temp_locked(self, final_stat):
        # Narrow S4e recovery, not a general clean-up sweep. This requires
        # validated record bytes (caller), an exact private producer filename,
        # a regular owned private candidate and the SAME device/inode.
        matches = []
        for name in os.listdir(self.store._fd):
            if not OWNED_TEMP.fullmatch(name):
                continue
            try:
                temp_fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK |
                                  os.O_NOFOLLOW, dir_fd=self.store._fd)
            except OSError:
                # Never follow/delete a hostile or unreadable temp.
                continue
            try:
                candidate = os.fstat(temp_fd)
                if (stat.S_ISREG(candidate.st_mode) and
                        candidate.st_uid == os.geteuid() and
                        not (candidate.st_mode & 0o177) and
                        candidate.st_nlink == 2 and
                        (candidate.st_dev, candidate.st_ino) ==
                        (final_stat.st_dev, final_stat.st_ino)):
                    matches.append(name)
            finally:
                os.close(temp_fd)
        if len(matches) != 1:
            raise ValueError("untrusted owner, mode or link count")
        # No external filename, broad sweep, symlink resolution or parent
        # writer change. Shared flock excludes cooperating S2/S3 publishers.
        os.unlink(matches[0], dir_fd=self.store._fd)
        self.store._durable()
