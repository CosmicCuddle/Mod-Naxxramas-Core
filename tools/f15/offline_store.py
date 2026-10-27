"""F15 S2: offline incident persistence ONLY, never an installed monitor.

Uses only caller-supplied *verified* synthetic process identities. There are
NO server launchers, live adapters, subprocess monitors, root paths or CLI.
Linux/POSIX only (fcntl, hard-link atomic no-clobber). Caller must provide an
existing private directory. This is not an authorization to deploy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import contextlib
import errno
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import time
import uuid

SCHEMA = "F15-S2-OFFLINE-1"
UNKNOWN = "Crash cause: Unknown — further investigation required"
NAMESPACE = uuid.UUID("86816d59-6d4f-43ad-8f4d-df60b13298ef")
NAME = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")
REPORT = re.compile(r"^(worldserver|authserver)-crash-[0-9]{8}T[0-9]{6}Z-([0-9a-f-]{36})\.txt$")
MAX_REPORT = 16_384

# OFFLINE safety ceilings, not owner-approved retention policy. Separate
# crash/error and world/auth lanes prevent a burst of warnings from consuming
# every future crash slot. Never delete an immutable report to make room.
MAX_TOTAL_REPORTS = 256
MAX_REPORTS_PER_KIND = 128
MAX_REPORTS_PER_SERVICE_KIND = 64
MAX_TOTAL_REPORT_BYTES = 2 * 1024 * 1024
LOCK_WAIT_SECONDS = 5.0
LOCK_POLL_SECONDS = 0.01
# Hard per-operation scan budget; applies to ALL files, not only final reports.
# Does not cap disk usage: hostile/legacy excess fails closed without cleanup.
MAX_DIRECTORY_SCAN_ENTRIES = 4096
ERROR_CAPACITY_REPORT = re.compile(
    r"^error-burst-(worldserver|authserver)-[0-9a-f-]{36}\.txt$"
)


def utc(value: str) -> str:
    """Reject ambiguous local timestamps, offsets and unverified wall clocks."""
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value
    ):
        raise ValueError("explicit UTC second timestamp required")
    date = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if date.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("noncanonical timestamp")
    return value


def safe_name(value: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError("unsafe or empty process identity")
    return value


@dataclass(frozen=True)
class Incident:
    service: str
    host: str
    boot: str
    invocation: str
    pid: int
    start_utc: str
    end_utc: str
    verified_actual_death: bool
    unexpected_death: bool
    planned_stop: bool = False
    signal: str | None = None
    exit_code: int | None = None

    def checked(self) -> "Incident":
        if self.service not in ("worldserver", "authserver"):
            raise ValueError("service must be worldserver/authserver")
        for value in (self.host, self.boot, self.invocation):
            safe_name(value)
        if type(self.pid) is not int or not 0 < self.pid < 1 << 31:
            raise ValueError("invalid real child PID")
        if utc(self.start_utc) > utc(self.end_utc):
            raise ValueError("death precedes process start")
        if type(self.verified_actual_death) is not bool or type(self.unexpected_death) is not bool or type(self.planned_stop) is not bool:
            raise ValueError("unverified event flags")
        if self.exit_code is not None and (type(self.exit_code) is not int or self.exit_code < 0 or self.exit_code > 255):
            raise ValueError("invalid exit code")
        if self.signal is not None and (not isinstance(self.signal, str) or
                not re.fullmatch(r"SIG[A-Z0-9]{1,10}", self.signal)):
            raise ValueError("invalid signal evidence")
        if self.signal is not None and self.exit_code is not None:
            raise ValueError("actual process death needs one independent termination kind")
        return self

    def is_reportable(self) -> bool:
        self.checked()
        if not self.verified_actual_death or not self.unexpected_death:
            return False
        if self.planned_stop and self.signal in ("SIGTERM", "SIGHUP", "SIGINT"):
            # A corroborated planned administrative stop by these ordinary
            # signals is not an incident. A genuine fatal/forced signal can
            # still be an incident during planned teardown.
            return False
        if self.signal:
            return True
        if self.exit_code == 0 or (self.service == "worldserver" and self.exit_code == 2):
            return False
        if self.planned_stop and self.exit_code is None:
            # Ambiguous wrapper/child status during planned shutdown is
            # insufficient evidence of a fatal crash.
            return False
        # An independently verified unexpected actual-child exit 1/134/139
        # during a planned stop must NOT silently disappear. High statuses
        # can be shell signal encodings, or ordinary exit codes: only a
        # trusted adapter can establish the actual signal.
        # A corroborated unexpected death without a usable status can
        # produce a minimal incident; do not guess signal/root cause.
        return self.exit_code is None or self.exit_code != 0

    def identity(self) -> str:
        self.checked()
        # No observed exit timestamp in the key; same crash noticed by GDB
        # and journal at different times must map to exactly one incident.
        key = "\x1f".join([self.host, self.boot, self.service,
                            self.invocation, str(self.pid), self.start_utc])
        return str(uuid.uuid5(NAMESPACE, key))

    def metadata(self) -> dict:
        self.checked()
        return {"schema": SCHEMA, "incident_id": self.identity(),
                "service": self.service, "host": self.host, "boot": self.boot,
                "invocation": self.invocation, "pid": self.pid,
                "start_utc": self.start_utc, "end_utc": self.end_utc,
                "termination": self.signal or (
                    "exit " + str(self.exit_code) if self.exit_code is not None
                    else "verified unexpected death; status unknown"),
                "crash_cause": UNKNOWN, "restart": "Not verified"}


def report_bytes(info: dict) -> bytes:
    data = json.dumps(info, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    head = ("COSMIC CORE - SERVER CRASH REPORT\n"
            + "Schema: " + SCHEMA + "\n"
            + "Incident ID: " + info["incident_id"] + "\n"
            + "Process: " + info["service"] + "\n"
            + "Process start (UTC): " + info["start_utc"] + "\n"
            + "Observed termination (UTC): " + info["end_utc"] + "\n"
            + "Observed termination: " + info["termination"] + "\n"
            + UNKNOWN + "\n"
            + "Automatic restart: Not verified\n"
            + "Metadata JSON: " + data + "\n").encode("utf-8")
    final = head + b"Finalized SHA-256: " + hashlib.sha256(head).hexdigest().encode("ascii") + b"\n"
    if len(final) > MAX_REPORT:
        raise ValueError("report exceeds offline size cap")
    return final


class IncidentStore:
    """Pinned-directory POSIX publisher; no supervisor, no production adapter.

    Once opened, all data/lock/index operations use the original directory
    descriptor, not a pathname re-resolved after an ancestor rename/symlink
    swap. External hostile parent permissions still require deployment review.
    """

    def __init__(self, directory: Path):
        self.root = Path(directory)
        self._fd = None
        if not self.root.is_absolute() or ".." in self.root.parts:
            raise ValueError("absolute normalized directory required")

        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open("/", flags)
        try:
            self._validate_ancestor(os.fstat(fd))
            for pos, part in enumerate(self.root.parts[1:]):
                if part in ("", ".", ".."):
                    raise ValueError("untrusted path component")
                try:
                    nextfd = os.open(part, flags, dir_fd=fd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise PermissionError("unsafe ancestor symlink/non-directory") from exc
                    raise
                try:
                    st = os.fstat(nextfd)
                    if pos < len(self.root.parts) - 2:
                        self._validate_ancestor(st)
                except BaseException:
                    os.close(nextfd)
                    raise
                os.close(fd)
                fd = nextfd
            st = os.fstat(fd)
            if (not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o077 or
                    st.st_uid != os.geteuid()):
                raise PermissionError("existing private directory must be owned by writer")
            self._fd = fd
            # Process-local, best-effort visibility only. These counts cannot
            # authenticate events or survive a restart and never hit disk.
            self._offline_rejections = {"capacity": 0, "lock_timeout": 0}
        except BaseException:
            os.close(fd)
            raise

    def offline_rejections(self):
        """Untrusted, bounded in-memory counters; NOT report provenance."""
        return dict(self._offline_rejections)

    def _count_rejection(self, reason: str):
        # Counters saturate instead of growing indefinitely under floods.
        self._offline_rejections[reason] = min(
            255, self._offline_rejections[reason] + 1
        )

    @staticmethod
    def _validate_ancestor(st):
        if not stat.S_ISDIR(st.st_mode):
            raise PermissionError("non-directory ancestor")
        # /tmp-style root-owned sticky directories permit safely created
        # private children. Other group/world-writable parents are rejected.
        if st.st_uid not in (0, os.geteuid()):
            raise PermissionError("ancestor owned by another account")
        if st.st_mode & 0o022 and not (st.st_mode & stat.S_ISVTX and st.st_uid == 0):
            raise PermissionError("writable untrusted ancestor")

    def close(self):
        fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)

    def __del__(self):
        with contextlib.suppress(OSError):
            self.close()

    def _dir_names_bounded(self):
        """Snapshot at most N names from the already pinned directory FD.

        scandir is lazy: oversized legacy/hostile directories fail before
        allocating an unbounded list of names. Called only under shared
        writer flock by quota/rebuild/sidecar/error consumers. Refuse safely
        without deleting or mutating reports at the exceeded boundary.
        """
        names = []
        with os.scandir(self._fd) as entries:
            for entry in entries:
                if len(names) >= MAX_DIRECTORY_SCAN_ENTRIES:
                    self._count_rejection("capacity")
                    raise OverflowError(
                        "F15 offline directory scan budget exceeded; "
                        "existing reports preserved, indexing/publish refused"
                    )
                names.append(entry.name)
        return names

    def _admit_report_locked(self, kind: str, service: str, new_bytes: int):
        """Bound all finalized crash/error report lanes while holding flock.

        Invalid or inaccessible names matching a report shape still consume
        space conservatively. Prior reports are neither evicted nor modified.
        This is a fixture quota, not an authenticated production rate limit.
        """
        if (kind not in ("crash", "error") or
                service not in ("worldserver", "authserver") or
                type(new_bytes) is not int or new_bytes < 0):
            raise ValueError("invalid offline report quota request")
        total = kind_count = service_kind = byte_count = 0
        for name in self._dir_names_bounded():
            crash = REPORT.fullmatch(name)
            error = ERROR_CAPACITY_REPORT.fullmatch(name)
            if not crash and not error:
                continue
            item_kind = "crash" if crash else "error"
            item_service = crash.group(1) if crash else error.group(1)
            try:
                st = os.stat(name, dir_fd=self._fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            total += 1
            byte_count += max(0, st.st_size)
            if item_kind == kind:
                kind_count += 1
                if item_service == service:
                    service_kind += 1
        if (total >= MAX_TOTAL_REPORTS or
                kind_count >= MAX_REPORTS_PER_KIND or
                service_kind >= MAX_REPORTS_PER_SERVICE_KIND or
                byte_count + new_bytes > MAX_TOTAL_REPORT_BYTES):
            self._count_rejection("capacity")
            raise OverflowError(
                "F15 offline report capacity reached; immutable records "
                "preserved, new report refused"
            )

    @contextlib.contextmanager
    def _locked(self):
        """Serialize cooperating F15 writers on a pinned directory inode.

        A named-file flock alone can split into two locking domains if a
        same-UID process renames/replaces its pathname. Linux flock on a
        NEW open file description for the pinned directory survives that
        name replacement and also serializes threads sharing this store.
        Continue taking the named lock for compatibility with older F15
        offline writers which only flock the path. The overall timeout is
        shared by both acquisitions. This is NOT hostile-UID protection.
        """
        dir_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=self._fd)
        lock_fd = None
        dir_acquired = False
        file_acquired = False
        deadline = time.monotonic() + LOCK_WAIT_SECONDS

        def take_lock(fd):
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except OSError as exc:
                    if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                        # EOPNOTSUPP/ENOSYS or other unsupported directory
                        # flock MUST fail closed; never fallback to a weak
                        # path-only lock without an explicit design review.
                        raise
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._count_rejection("lock_timeout")
                        raise TimeoutError(
                            "F15 offline lock deadline exceeded without a write"
                        ) from exc
                    time.sleep(min(LOCK_POLL_SECONDS, remaining))

        try:
            opened = os.fstat(dir_fd)
            pinned = os.fstat(self._fd)
            if (not stat.S_ISDIR(opened.st_mode) or
                    (opened.st_dev, opened.st_ino) !=
                    (pinned.st_dev, pinned.st_ino)):
                raise PermissionError("offline directory lock inode differs from pinned root")

            take_lock(dir_fd)
            dir_acquired = True

            flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
            lock_fd = os.open(".f15.offline.lock", flags, 0o600,
                              dir_fd=self._fd)
            st = os.fstat(lock_fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077 or
                    st.st_nlink != 1 or st.st_uid != os.geteuid()):
                raise PermissionError("unsafe offline legacy compatibility lock")

            take_lock(lock_fd)
            file_acquired = True
            yield
        finally:
            if file_acquired:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            if lock_fd is not None:
                os.close(lock_fd)
            if dir_acquired:
                fcntl.flock(dir_fd, fcntl.LOCK_UN)
            os.close(dir_fd)
    def _durable(self):
        os.fsync(self._fd)

    def _unlink(self, name: str):
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name, dir_fd=self._fd)

    def _temp(self, content: bytes) -> str:
        # Avoid tempfile.mkstemp(path), which re-resolves the directory path.
        # O_EXCL prevents collision and O_NOFOLLOW blocks pre-existing links.
        name = None
        fd = None
        for _ in range(5):
            name = ".f15-s2-" + secrets.token_hex(16)
            try:
                fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             os.O_NOFOLLOW, 0o600, dir_fd=self._fd)
                break
            except FileExistsError:
                continue
        if fd is None:
            raise FileExistsError("no unused temporary report name")
        try:
            with os.fdopen(fd, "wb") as file:
                fd = None
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            if fd is not None:
                os.close(fd)
            self._unlink(name)
            raise
        return name

    def _read_valid(self, name: str):
        if not REPORT.fullmatch(name):
            return None
        try:
            # O_NONBLOCK prevents a hostile FIFO/device from blocking before
            # fstat rejects non-regular files. Never follow a report symlink.
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=self._fd)
            with os.fdopen(fd, "rb") as file:
                st = os.fstat(file.fileno())
                if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_REPORT:
                    return None
                payload = file.read(MAX_REPORT + 1)
            if len(payload) > MAX_REPORT:
                return None
            body, marker = payload.rsplit(b"Finalized SHA-256: ", 1)
            if marker != hashlib.sha256(body).hexdigest().encode("ascii") + b"\n":
                return None
            line = next(x for x in body.decode("utf-8").splitlines()
                        if x.startswith("Metadata JSON: "))
            info = json.loads(line[len("Metadata JSON: "):])
            if (set(info) != {"schema", "incident_id", "service", "host", "boot",
                               "invocation", "pid", "start_utc", "end_utc",
                               "termination", "crash_cause", "restart"} or
                    info["schema"] != SCHEMA or info["crash_cause"] != UNKNOWN or
                    info["restart"] != "Not verified" or
                    info["service"] not in ("worldserver", "authserver")):
                return None
            for value in (info["host"], info["boot"], info["invocation"]):
                safe_name(value)
            utc(info["start_utc"])
            utc(info["end_utc"])
            if type(info["pid"]) is not int or info["pid"] <= 0:
                return None
            identity = "\x1f".join([info["host"], info["boot"], info["service"],
                                    info["invocation"], str(info["pid"]), info["start_utc"]])
            if info["incident_id"] != str(uuid.uuid5(NAMESPACE, identity)):
                return None
            expected = self._filename(info)
            if name != expected or payload != report_bytes(info):
                return None
            return info
        except (OSError, ValueError, KeyError, StopIteration, UnicodeError, TypeError):
            return None

    @staticmethod
    def _filename(info) -> str:
        stamp = info["start_utc"].replace("-", "").replace(":", "")
        return f"{info['service']}-crash-{stamp}-{info['incident_id']}.txt"

    def _reports(self):
        items = {}
        invalid = []
        for name in self._dir_names_bounded():
            if not REPORT.fullmatch(name):
                continue
            info = self._read_valid(name)
            if info:
                items[info["incident_id"]] = (name, info)
            else:
                invalid.append(name)
        valid = sorted(items.values(), key=lambda pair:
                       (pair[1]["end_utc"], pair[1]["incident_id"]))
        return valid, sorted(invalid)

    def rebuild(self) -> tuple[int, int]:
        with self._locked():
            return self._rebuild_locked()

    def _reject_legacy_restart_projection(self):
        """Never let an S2-only writer silently discard an S3 restart index."""
        if any(name.startswith("restart-") and name.endswith(".txt")
               for name in self._dir_names_bounded()):
            raise RuntimeError(
                "restart sidecars present: legacy S2 index would erase restart "
                "statuses; use RestartSidecarStore and rebuild with S3")

    def _rebuild_locked(self):
        self._reject_legacy_restart_projection()
        reports, invalid = self._reports()
        w = sum(info["service"] == "worldserver" for _, info in reports)
        a = sum(info["service"] == "authserver" for _, info in reports)
        lines = ["COSMIC CORE - CRASH HISTORY", "Schema: " + SCHEMA,
                 f"Worldserver: {w}", f"Authserver: {a}",
                 f"Total: {len(reports)}",
                 f"Unverified or modified report files: {len(invalid)}", ""]
        for filename, info in reports:
            lines.append(f"{info['end_utc']} | {info['service']} | "
                         f"{info['incident_id']} | {filename} | "
                         f"{info['termination']} | restart: Not verified")
        if invalid:
            lines.append("")
            lines.append("WARNING: some named reports are invalid or modified; verified totals exclude them.")
            lines.append("Do not edit immutable reports; future operator notes belong in separately reviewed sidecars.")
            for filename in invalid:
                lines.append("Unverified report: " + filename)
        temp = self._temp(("\n".join(lines) + "\n").encode("utf-8"))
        try:
            # History is derived; atomic REPLACE is appropriate here only.
            os.replace(temp, "Crash-History.txt",
                       src_dir_fd=self._fd, dst_dir_fd=self._fd)
            self._durable()
        finally:
            self._unlink(temp)
        return w, a

    def publish(self, incident: Incident) -> bool:
        """Return True for new, False for skipped/duplicate; never overwrite."""
        if not incident.is_reportable():
            return False
        info = incident.metadata()
        name = self._filename(info)
        with self._locked():
            if type(self)._rebuild_locked is IncidentStore._rebuild_locked:
                # Reject BEFORE persisting a new crash with the S2-only
                # writer. S3's overridden index builder retains projection.
                self._reject_legacy_restart_projection()
            try:
                os.stat(name, dir_fd=self._fd, follow_symlinks=False)
                exists = True
            except FileNotFoundError:
                exists = False
            if exists:
                prior = self._read_valid(name)
                if prior is None or prior["incident_id"] != info["incident_id"]:
                    # Even on a corrupt/no-clobber conflict, refresh the
                    # derived history so the warning remains visible.
                    self._rebuild_locked()
                    raise FileExistsError("final filename conflict/corruption")
                self._rebuild_locked()
                return False
            report = report_bytes(info)
            self._admit_report_locked("crash", info["service"], len(report))
            temp = self._temp(report)
            try:
                # Hard-link is atomic no-clobber (EEXIST), anchored under FD.
                os.link(temp, name, src_dir_fd=self._fd,
                        dst_dir_fd=self._fd, follow_symlinks=False)
                self._durable()
            finally:
                self._unlink(temp)
            # An index failure cannot erase the finalized report. The next
            # successful rebuild recovers it without counting a second event.
            self._rebuild_locked()
            return True
