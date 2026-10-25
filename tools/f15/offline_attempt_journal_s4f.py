"""F15 S4f synthetic-only durable restart-attempt reservation model.

NO Worldserver/Authserver, daemon supervision, GDB, log or host integration.
Refuses paths outside freshly created direct-child private synthetic test dirs.
The caller's facts are deliberately unauthenticated; never use for deployment.
"""

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
ATTEMPT = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
VALID_RESULTS = {"succeeded", "failed", "unverified"}


class UnsafeJournal(ValueError):
    pass


class OfflineAttemptJournal:
    """Fail-closed synthetic journal; pending never silently expires."""

    def __init__(self, root):
        root = Path(root)
        # This model intentionally does not accept arbitrary owner/service paths.
        if (root.parent != Path(tempfile.gettempdir()) or
                not root.name.startswith("f15-s4f-synthetic-")):
            raise UnsafeJournal("only direct synthetic test directories allowed")
        self._dirfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            st = os.fstat(self._dirfd)
            if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) != 0o700):
                raise UnsafeJournal("private owned 0700 directory required")
            self._lockfd = os.open(".attempt.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                                   0o600, dir_fd=self._dirfd)
            st = os.fstat(self._lockfd)
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1):
                raise UnsafeJournal("unsafe lock")
        except BaseException:
            if hasattr(self, "_lockfd"):
                os.close(self._lockfd)
            os.close(self._dirfd)
            raise

    def close(self):
        os.close(self._lockfd)
        os.close(self._dirfd)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _locked(self):
        fcntl.flock(self._lockfd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(self._lockfd, fcntl.LOCK_UN)

    @staticmethod
    def _identity(service, incident_id, attempt):
        if service not in ("worldserver", "authserver") or not UUID.fullmatch(incident_id) or not ATTEMPT.fullmatch(attempt):
            raise UnsafeJournal("invalid synthetic attempt identity")
        key = [service, incident_id, attempt]
        token = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).hexdigest()
        return token, key

    @staticmethod
    def _encode(key, state):
        return (json.dumps({"key": key, "state": state}, sort_keys=True,
                           separators=(",", ":")) + "\n").encode()

    def _read(self, name, key, allowed_states):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=self._dirfd)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise UnsafeJournal("unsafe reservation entry") from exc
        try:
            st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1 or
                    st.st_size > 1024):
                raise UnsafeJournal("unsafe reservation metadata")
            payload = os.read(fd, 1025)
            try:
                obj = json.loads(payload)
            except (ValueError, UnicodeDecodeError) as exc:
                raise UnsafeJournal("corrupt immutable reservation") from exc
            if (not isinstance(obj, dict) or obj.get("key") != key or
                    obj.get("state") not in allowed_states or
                    payload != self._encode(key, obj["state"])):
                raise UnsafeJournal("unverified reservation contents")
            return obj["state"]
        finally:
            os.close(fd)

    def _publish(self, name, key, state):
        # No-clobber create. Torn/corrupt files remain visible and block reissue.
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self._dirfd)
        try:
            data = self._encode(key, state)
            while data:
                n = os.write(fd, data)
                if n <= 0:
                    raise OSError("short reservation write")
                data = data[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(self._dirfd)

    def begin(self, service, incident_id, attempt):
        token, key = self._identity(service, incident_id, attempt)
        pending, done = token + ".pending", token + ".done"
        with self._locked():
            pending_state = self._read(pending, key, {"pending"})
            final_state = self._read(done, key, VALID_RESULTS)
            if final_state is not None and pending_state is None:
                raise UnsafeJournal("orphan completion without reservation")
            if pending_state is not None:
                return "completed:" + final_state if final_state else "pending"
            self._publish(pending, key, "pending")
            return "reserved"

    def complete_synthetic(self, service, incident_id, attempt, result):
        # This method accepts a synthetic caller assertion, NOT real readiness.
        if result not in VALID_RESULTS:
            raise UnsafeJournal("invalid synthetic terminal state")
        token, key = self._identity(service, incident_id, attempt)
        with self._locked():
            if self._read(token + ".pending", key, {"pending"}) is None:
                raise UnsafeJournal("no reserved attempt")
            previous = self._read(token + ".done", key, VALID_RESULTS)
            if previous is not None:
                if previous == result:
                    return "already:" + result
                raise UnsafeJournal("terminal conflict")
            self._publish(token + ".done", key, result)
            return "recorded:" + result
