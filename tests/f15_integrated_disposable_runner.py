"""F15 integrated DISPOSABLE console-archive runner: TEST FIXTURE ONLY.

NEVER import into server services, cron, PM2, tmux, launch scripts or any
production tooling. It has no command-line entry point and refuses to run on
any directory other than its own tempfile.TemporaryDirectory workspace.

One chain, one authority (see docs/research/F15-INTEGRATED-DISPOSABLE-RUNNER.md):

  fake source file --poll--> immutable journal records --seal--> daily .txt
     (append by inode+offset)  + one checksummed checkpoint     + manifest
                               per stream                         --expire-->

* Journal records are numbered per stream (seq 1, 2, 3, ...). A record is
  either a byte segment or a note (bootstrap-skip, replaced, truncated,
  incomplete-utf8-tail). Its file name carries the UTC *observation* day and
  the full SHA-256 of its content, so the day a byte belongs to is fixed when
  it is first published and survives any crash.
* The checkpoint only says how far the journal has been adopted. A record
  published before a crash is adopted on restart (never copied twice); a
  record that was never published is simply read again.
* A daily archive is built only from validated journal records, never from a
  second offset, so publishing and sealing cannot disagree.
* Naming and retention planning reuse PR #249's tools/f15/console_archive_policy.py
  unchanged; plan_increment classifies every observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile

_POLICY_PATH = Path(__file__).resolve().parents[1] / "tools" / "f15" / "console_archive_policy.py"
_spec = importlib.util.spec_from_file_location("f15_console_archive_policy_for_runner", _POLICY_PATH)
policy = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = policy
_spec.loader.exec_module(policy)

UTC = timezone.utc
DAY = timedelta(days=1)
STREAMS = {
    "Worldserver-out": ("Worldserver", "out"),
    "Worldserver-err": ("Worldserver", "err"),
    "Authserver-native": ("Authserver", "native"),
}
DEFAULT_SOURCE_NAMES = {
    "Worldserver-out": "World-out.log",
    "Worldserver-err": "World-err.log",
    "Authserver-native": "Auth-native.log",
}
COMPLETENESS = {
    "Worldserver-out": "PM2 stdout log file as observed by polling",
    "Worldserver-err": "PM2 stderr log file as observed by polling; stderr text is not a crash diagnosis",
    "Authserver-native": "native Authserver log file only; NOT a PTY console transcript",
}
ENCODING_LABEL = ("raw source bytes, unchanged; a .txt is valid UTF-8 only when utf8_valid is true; "
                  "invalid UTF-8 is flagged, never repaired or replaced")
TIME_LABEL = "UTC observation day of the poll that first read the bytes; not the event time"
MAX_SEGMENT = 4096
MAX_CLOCK_JUMP = timedelta(days=62)
MARKER = ".f15-integrated-disposable-root"
POLL_FAILPOINTS = (None, "before-record-publish", "after-record-publish",
                   "before-checkpoint-publish", "after-checkpoint", "enospc")
SEAL_FAILPOINTS = (None, "before-archive-publish", "after-archive-publish")
EXPIRE_FAILPOINTS = (None, "after-unlink-before-manifest")
_SOURCE_NAME_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z", re.ASCII)
_RECORD_RE = re.compile(
    r"\A(?P<stream>Worldserver-out|Worldserver-err|Authserver-native)__(?P<seq>\d{12})__"
    r"(?P<kind>seg|note-[a-z0-9-]+)__(?P<dev>\d+)__(?P<ino>\d+)__(?P<start>\d+)__(?P<end>\d+)__"
    r"(?P<day>\d{8})__(?P<sha>[0-9a-f]{64})\.rec\Z", re.ASCII)


class SyntheticCrash(RuntimeError):
    """A simulated process stop at a named failure point."""


class FailClosed(RuntimeError):
    """An unsafe or inconsistent condition; nothing further was written."""


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must have an explicit UTC offset")
    return value.astimezone(UTC)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def incomplete_utf8_tail(data):
    """Length (1-3) of a trailing UTF-8 sequence that is not yet complete, else 0."""
    n = len(data)
    for k in range(1, min(3, n) + 1):
        c = data[n - k]
        if c & 0xC0 == 0x80:
            continue
        if c & 0xE0 == 0xC0:
            need = 2
        elif c & 0xF0 == 0xE0:
            need = 3
        elif c & 0xF8 == 0xF0:
            need = 4
        else:
            return 0
        return k if k < need else 0
    return 0


def _write_all(fd, data, enospc=False):
    if enospc:
        os.write(fd, data[: len(data) // 2])
        raise OSError(errno.ENOSPC, "No space left on device (injected)")
    at = 0
    while at < len(data):
        n = os.write(fd, data[at:])
        if n <= 0:
            raise OSError(errno.EIO, "short write")
        at += n


def _dir_sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_regular(path):
    """Read a file we own: no symlink, regular, single link."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise FailClosed(f"untrusted file {Path(path).name}")
        chunks = []
        while True:
            block = os.read(fd, 1 << 16)
            if not block:
                return b"".join(chunks), meta
            chunks.append(block)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class Record:
    path: Path
    stream: str
    seq: int
    kind: str
    dev: int
    ino: int
    start: int
    end: int
    day: date
    sha: str


@dataclass(frozen=True)
class PollResult:
    events: tuple
    captured: bytes


class DisposableWorkspace:
    """Owns the only directory the runner will touch, plus three fake sources."""

    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="f15-integrated-disposable-")
        self.root = Path(self._temporary.name)
        self.token = secrets.token_hex(16)
        fd = os.open(self.root / MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            _write_all(fd, self.token.encode("ascii"))
        finally:
            os.close(fd)
        for name in ("sources", "segments", "state", "archive"):
            (self.root / name).mkdir(mode=0o700)

    def close(self):
        self._temporary.cleanup()

    def source_path(self, stream, names=None):
        return self.root / "sources" / (names or DEFAULT_SOURCE_NAMES)[stream]

    def seed(self, stream, payload):
        fd = os.open(self.source_path(stream), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            _write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)

    def append(self, stream, payload):
        fd = os.open(self.source_path(stream), os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        try:
            _write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)


class IntegratedRunner:
    """Single-writer synthetic runner over one DisposableWorkspace."""

    def __init__(self, workspace, source_names=None):
        root = Path(workspace.root)
        tmp = Path(os.path.realpath(tempfile.gettempdir()))
        real = Path(os.path.realpath(root))
        if tmp not in real.parents:
            raise FailClosed("refusing a root outside the disposable temporary directory")
        try:
            marker, _ = _read_regular(root / MARKER)
        except (OSError, FailClosed) as exc:
            raise FailClosed("refusing a root without this workspace's marker") from exc
        if marker != str(workspace.token).encode("ascii"):
            raise FailClosed("refusing a root whose marker does not match")
        self.root = root
        self.sources = root / "sources"
        self.segments = root / "segments"
        self.state = root / "state"
        self.archive = root / "archive"
        names = dict(DEFAULT_SOURCE_NAMES if source_names is None else source_names)
        if set(names) != set(STREAMS):
            raise FailClosed("exactly World out, World err and Auth native sources are required")
        for stream, name in names.items():
            if not isinstance(name, str) or not _SOURCE_NAME_RE.fullmatch(name) or ".." in name:
                raise FailClosed(f"unsafe source name for {stream}")
        if len(set(names.values())) != len(names):
            raise FailClosed("each stream needs its own source file")
        self.source_names = names
        self._lock_fd = os.open(self.state / "runner.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self._lock_fd)
            self._lock_fd = None
            raise FailClosed("another runner already holds this workspace") from None
        self._discard_unpublished()

    def close(self):
        """Release the lock, as a stopped (or crashed) process would."""
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None

    # ---- small durable-write helpers ------------------------------------
    def _owned_pending(self, directory, name):
        """True only for a *.pending name this runner itself would create there."""
        if not name.endswith(".pending"):
            return False
        base = name[: -len(".pending")]
        if directory == self.segments:
            return _RECORD_RE.fullmatch(base) is not None
        if directory == self.state:
            return base in ("clock.json", "archives.json") or base in {
                s + ".checkpoint.json" for s in STREAMS}
        if base.endswith(".provenance.json"):
            base = base[: -len(".provenance.json")] + ".txt"
        return policy.parsed_filename(base) is not None

    _STATE_KEYS = {"clock.json": {"last"}, "archives.json": {"entries", "next_day"}}
    _CHECKPOINT_KEYS = {"seq", "dev", "ino", "offset", "held_size", "recorded_at"}

    def _pending_is_ours(self, directory, path):
        """True only if a pending file's CONTENT matches what this runner writes under
        that name; a matching name alone is not proof.

        Threat boundary: this is a self-consistency check, not authentication. It
        stops an unrelated file at a reserved name from being deleted; it cannot
        stop a writer inside the private workspace from forging a consistent one.
        """
        try:
            data, _ = _read_regular(path)
        except (OSError, FailClosed):
            return False
        base = path.name[: -len(".pending")]
        if directory == self.segments:
            match = _RECORD_RE.fullmatch(base)
            if match is None or _sha(data) != match["sha"]:
                return False
            return match["kind"] != "seg" or len(data) == int(match["end"]) - int(match["start"])
        if directory == self.state:
            try:
                wrapper = json.loads(data)
                doc = wrapper["doc"]
                body = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
                keys = self._STATE_KEYS.get(base, self._CHECKPOINT_KEYS)
                return wrapper["sha256"] == _sha(body) and set(doc) == keys
            except (ValueError, KeyError, TypeError):
                return False
        if base.endswith(".provenance.json"):
            try:
                doc = json.loads(data)
                return doc.get("name") == base[: -len(".provenance.json")] + ".txt"
            except (ValueError, AttributeError):
                return False
        parsed = policy.parsed_filename(base)
        if parsed is None:
            return False
        role, source, closed_at = parsed
        day = (closed_at - DAY).date().isoformat()
        tag = _sha(f"{role}-{source}|{day}|{_sha(data)}".encode("ascii"))[:12]
        return base[-len(tag) - 4: -4] == tag

    def _discard_unpublished(self):
        """Remove our own never-published *.pending files left by a crash; nothing else.

        A file at a reserved pending name whose content is not ours is left in place
        and the runner refuses to start, so an operator decides what it is.
        """
        for directory in (self.segments, self.state, self.archive):
            for path in directory.iterdir():
                if not self._owned_pending(directory, path.name):
                    continue
                meta = path.lstat()
                if not stat.S_ISREG(meta.st_mode):
                    raise FailClosed(f"unexpected non-regular pending file {path.name}")
                if not self._pending_is_ours(directory, path):
                    raise FailClosed(f"foreign file at reserved name {path.name}; left in place "
                                     "for an operator decision")
                path.unlink()
            _dir_sync(directory)

    def _write_new(self, path, data, enospc=False):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            try:
                _write_all(fd, data, enospc)
                os.fsync(fd)
            except OSError:
                os.close(fd)
                fd = None
                os.unlink(path)
                raise
        finally:
            if fd is not None:
                os.close(fd)

    def _publish_once(self, directory, name, data, fail_at=None, before=None, after=None, enospc=False):
        """Create `name` atomically with exactly `data`; never overwrite."""
        final = directory / name
        if final.exists() or final.is_symlink():
            existing, _ = _read_regular(final)
            if existing != data:
                raise FailClosed(f"existing {name} differs from the bytes it should hold")
            return False
        pending = directory / (name + ".pending")
        try:
            self._write_new(pending, data, enospc)
        except OSError as exc:
            raise FailClosed(f"could not write {name}: {exc.strerror}") from exc
        if fail_at is not None and fail_at == before:
            raise SyntheticCrash(f"stopped before publishing {name}")
        os.link(pending, final)
        os.unlink(pending)
        _dir_sync(directory)
        if fail_at is not None and fail_at == after:
            raise SyntheticCrash(f"stopped after publishing {name}")
        return True

    def _write_signed(self, name, doc, fail_at=None):
        body = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
        data = json.dumps({"doc": doc, "sha256": _sha(body)}, sort_keys=True).encode("utf-8")
        pending = self.state / (name + ".pending")
        if pending.exists() or pending.is_symlink():
            if not stat.S_ISREG(pending.lstat().st_mode) or not self._pending_is_ours(self.state, pending):
                raise FailClosed(f"foreign file at reserved name {pending.name}; left in place")
            pending.unlink()  # our own, never published, so never authoritative
        self._write_new(pending, data)
        if fail_at == "before-checkpoint-publish":
            raise SyntheticCrash(f"stopped before publishing {name}")
        os.replace(pending, self.state / name)
        _dir_sync(self.state)

    def _read_signed(self, name):
        path = self.state / name
        if not (path.exists() or path.is_symlink()):
            return None
        raw, _ = _read_regular(path)
        try:
            wrapper = json.loads(raw)
            doc = wrapper["doc"]
            body = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ok = wrapper["sha256"] == _sha(body)
        except (ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            raise FailClosed(f"state file {name} failed its checksum")
        return doc

    # ---- clock ------------------------------------------------------------
    def _advance_clock(self, now):
        now = _utc(now)
        doc = self._read_signed("clock.json")
        if doc is not None:
            last = datetime.fromisoformat(doc["last"])
            if now < last:
                raise FailClosed("observed UTC time moved backwards")
            if now - last > MAX_CLOCK_JUMP:
                raise FailClosed("observed UTC time jumped forward too far; operator review needed")
        self._write_signed("clock.json", {"last": now.isoformat()})
        return now

    # ---- journal ------------------------------------------------------------
    def _check_stream(self, stream):
        if stream not in STREAMS:
            raise FailClosed(f"unsupported stream {stream!r}")

    def records(self, stream):
        self._check_stream(stream)
        found = []
        for path in self.segments.iterdir():
            match = _RECORD_RE.fullmatch(path.name)
            if not match or match["stream"] != stream:
                continue
            found.append(Record(path, stream, int(match["seq"]), match["kind"], int(match["dev"]),
                                int(match["ino"]), int(match["start"]), int(match["end"]),
                                datetime.strptime(match["day"], "%Y%m%d").date(), match["sha"]))
        return sorted(found, key=lambda r: r.seq)

    def _record_bytes(self, record):
        data, _ = _read_regular(record.path)
        if _sha(data) != record.sha:
            raise FailClosed(f"journal record {record.seq} of {record.stream} is corrupt")
        if record.kind == "seg" and len(data) != record.end - record.start:
            raise FailClosed(f"journal segment {record.seq} of {record.stream} has the wrong length")
        return data

    def _checkpoint(self, stream):
        doc = self._read_signed(stream + ".checkpoint.json")
        if doc is None:
            return {"seq": 0, "dev": 0, "ino": 0, "offset": 0, "held_size": -1,
                    "recorded_at": None}
        return doc

    def _commit(self, stream, ck, fail_at=None):
        self._write_signed(stream + ".checkpoint.json", ck, fail_at)
        if fail_at == "after-checkpoint":
            raise SyntheticCrash("stopped after publishing the checkpoint")

    def _adopt(self, stream, ck):
        """Adopt records published before a stop but not yet checkpointed."""
        adopted = 0
        while True:
            nxt = [r for r in self.records(stream) if r.seq == ck["seq"] + 1]
            if not nxt:
                return ck, adopted
            if len(nxt) != 1:
                raise FailClosed("ambiguous journal sequence")
            record = nxt[0]
            data = self._record_bytes(record)
            recorded_at = ck["recorded_at"]
            if record.kind == "seg":
                if (record.dev, record.ino, record.start) != (ck["dev"], ck["ino"], ck["offset"]):
                    raise FailClosed("journal segment does not continue the checkpoint")
            else:
                recorded_at = json.loads(data)["observed_at"]
            ck = {"seq": record.seq, "dev": record.dev, "ino": record.ino, "offset": record.end,
                  "held_size": -1, "recorded_at": recorded_at}
            self._commit(stream, ck)
            adopted += 1

    def _publish_record(self, stream, seq, kind, dev, ino, start, end, day, data, fail_at):
        name = (f"{stream}__{seq:012d}__{kind}__{dev}__{ino}__{start}__{end}__"
                f"{day:%Y%m%d}__{_sha(data)}.rec")
        self._publish_once(self.segments, name, data, fail_at,
                           before="before-record-publish", after="after-record-publish",
                           enospc=fail_at == "enospc")

    def _note(self, stream, ck, kind, dev, ino, offset, now, detail, fail_at):
        doc = {"kind": kind, "observed_at": now.isoformat(), "old": [ck["dev"], ck["ino"], ck["offset"]],
               "new": [dev, ino, offset], "detail": detail}
        data = json.dumps(doc, sort_keys=True).encode("utf-8")
        seq = ck["seq"] + 1
        self._publish_record(stream, seq, "note-" + kind, dev, ino, offset, offset, now.date(), data, fail_at)
        ck = {"seq": seq, "dev": dev, "ino": ino, "offset": offset, "held_size": -1,
              "recorded_at": now.isoformat()}
        self._commit(stream, ck, fail_at if fail_at in ("before-checkpoint-publish", "after-checkpoint") else None)
        return ck

    def _open_source(self, stream):
        path = self.sources / self.source_names[stream]
        if os.path.realpath(path.parent) != os.path.realpath(self.sources):
            raise FailClosed("source escapes the workspace")
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise FailClosed(f"{stream} source is a symlink") from exc
            if exc.errno in (errno.EACCES, errno.EPERM):
                raise FailClosed(f"{stream} source is unreadable") from exc
            raise FailClosed(f"{stream} source cannot be opened: {exc.strerror}") from exc
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode):
            os.close(fd)
            raise FailClosed(f"{stream} source is not a regular file")
        if meta.st_nlink != 1:
            os.close(fd)
            raise FailClosed(f"{stream} source has {meta.st_nlink} hard links")
        return fd, meta

    def poll(self, stream, now, fail_at=None):
        """Observe one source once. Every byte read is published before it is counted."""
        self._check_stream(stream)
        if fail_at not in POLL_FAILPOINTS:
            raise ValueError("unknown failure point")
        now = self._advance_clock(now)
        fd, meta = self._open_source(stream)
        try:
            ck = self._checkpoint(stream)
            ck, adopted = self._adopt(stream, ck)
            events = ["recovered"] if adopted else []
            if ck["seq"] == 0:
                self._note(stream, ck, "bootstrap-skip", meta.st_dev, meta.st_ino, meta.st_size, now,
                           f"{meta.st_size} existing bytes not backfilled", fail_at)
                return PollResult(tuple(events + ["bootstrap-skip"]), b"")
            plan = policy.plan_increment(
                policy.StreamCheckpoint(ck["dev"], ck["ino"], ck["offset"],
                                        datetime.fromisoformat(ck["recorded_at"])),
                policy.StreamSample(meta.st_dev, meta.st_ino, meta.st_size, now))
            if plan.event in ("replaced", "truncated"):
                ck = self._note(stream, ck, plan.event, meta.st_dev, meta.st_ino, 0, now,
                                plan.warning, fail_at)
                events.append(plan.event)
                fail_at = None
            captured = []
            while ck["offset"] < meta.st_size:
                start = ck["offset"]
                n = min(MAX_SEGMENT, meta.st_size - start)
                chunk = os.pread(fd, n, start)
                if len(chunk) != n:
                    raise FailClosed("source shortened while it was being copied")
                at_eof = start + n == meta.st_size
                tail = incomplete_utf8_tail(chunk)
                stale_tail = False
                if tail and not at_eof:
                    chunk = chunk[:-tail]
                elif tail and ck["held_size"] != meta.st_size:
                    chunk = chunk[:-tail]
                    if chunk:
                        self._publish_record(stream, ck["seq"] + 1, "seg", ck["dev"], ck["ino"], start,
                                             start + len(chunk), now.date(), chunk, fail_at)
                        ck = dict(ck, seq=ck["seq"] + 1, offset=start + len(chunk))
                        captured.append(chunk)
                    ck = dict(ck, held_size=meta.st_size, recorded_at=now.isoformat())
                    self._commit(stream, ck, fail_at if fail_at in ("before-checkpoint-publish", "after-checkpoint") else None)
                    events.append("held-incomplete-utf8")
                    break
                elif tail:
                    stale_tail = True
                self._publish_record(stream, ck["seq"] + 1, "seg", ck["dev"], ck["ino"], start,
                                     start + len(chunk), now.date(), chunk, fail_at)
                ck = {"seq": ck["seq"] + 1, "dev": ck["dev"], "ino": ck["ino"],
                      "offset": start + len(chunk), "held_size": -1, "recorded_at": now.isoformat()}
                self._commit(stream, ck, fail_at if fail_at in ("before-checkpoint-publish", "after-checkpoint") else None)
                captured.append(chunk)
                fail_at = None
                if stale_tail:
                    ck = self._note(stream, ck, "incomplete-utf8-tail", ck["dev"], ck["ino"], ck["offset"],
                                    now, "source ended inside a UTF-8 sequence and did not grow; kept as-is",
                                    None)
                    events.append("incomplete-utf8-tail")
            current = os.fstat(fd)
            if (current.st_dev, current.st_ino) != (meta.st_dev, meta.st_ino):
                raise FailClosed("source replaced while it was being copied")
            if captured:
                events.append("appended")
            elif not events or events == ["recovered"]:
                events.append("unchanged")
                if ck["recorded_at"] != now.isoformat():
                    self._commit(stream, dict(ck, recorded_at=now.isoformat()))
            return PollResult(tuple(events), b"".join(captured))
        finally:
            os.close(fd)

    def _validated_chain(self, stream):
        """Every record of a stream, checked: no gaps in seq, segments continuous."""
        chain = self.records(stream)
        prev = None
        for expected, record in enumerate(chain, start=1):
            if record.seq != expected:
                raise FailClosed(f"journal record {expected} of {stream} is missing")
            data = self._record_bytes(record)
            if record.kind == "seg":
                if prev is None or (record.dev, record.ino, record.start) != prev:
                    raise FailClosed(f"journal segment {record.seq} of {stream} does not continue the chain")
                prev = (record.dev, record.ino, record.end)
            else:
                prev = (record.dev, record.ino, record.end)
            yield record, data

    # ---- daily sealing -------------------------------------------------------
    def _manifest(self):
        doc = self._read_signed("archives.json")
        return doc if doc is not None else {"entries": [], "next_day": {}}

    def seal_through(self, now, fail_at=None):
        """Close every whole UTC day before `now` that is not closed yet."""
        if fail_at not in SEAL_FAILPOINTS:
            raise ValueError("unknown failure point")
        now = self._advance_clock(now)
        today = now.date()
        manifest = self._manifest()
        done = []
        for stream in sorted(STREAMS):
            chain = list(self._validated_chain(stream))
            if not chain:
                continue
            day = date.fromisoformat(manifest["next_day"].get(stream, chain[0][0].day.isoformat()))
            while day < today:
                entry = self._seal_day(stream, day, chain, fail_at)
                manifest["entries"].append(entry)
                manifest["next_day"][stream] = (day + DAY).isoformat()
                self._write_signed("archives.json", manifest)
                done.append(entry)
                day += DAY
        return done

    def _seal_day(self, stream, day, chain, fail_at):
        role, source = STREAMS[stream]
        parts, notes, spans = [], [], []
        for record, data in chain:
            if record.day != day:
                continue
            if record.kind == "seg":
                parts.append(data)
                spans.append({"seq": record.seq, "dev": record.dev, "ino": record.ino,
                              "start": record.start, "end": record.end, "sha256": record.sha})
            else:
                notes.append(json.loads(data))
        content = b"".join(parts)
        closed_at = datetime.combine(day + DAY, time(0), UTC)
        entry = {"stream": stream, "day": day.isoformat(), "closed_at": closed_at.isoformat(),
                 "completeness": COMPLETENESS[stream], "time_label": TIME_LABEL,
                 "notes": notes, "spans": spans, "size": len(content)}
        if not content:
            return dict(entry, state="idle", name=None)
        try:
            content.decode("utf-8")
            utf8_valid = True
        except UnicodeDecodeError:
            utf8_valid = False
        tag = _sha(f"{stream}|{day.isoformat()}|{_sha(content)}".encode("ascii"))[:12]
        name = policy.archive_filename(role, source, closed_at, tag)
        sidecar = name[:-4] + ".provenance.json"
        entry = dict(entry, name=name, sidecar=sidecar, sha256=_sha(content), utf8_valid=utf8_valid,
                     encoding=ENCODING_LABEL)
        provenance = json.dumps({k: v for k, v in entry.items() if k != "sidecar"},
                                sort_keys=True, indent=1).encode("utf-8")
        self._publish_once(self.archive, sidecar, provenance)
        side = (self.archive / sidecar).lstat()
        self._publish_once(self.archive, name, content, fail_at,
                           before="before-archive-publish", after="after-archive-publish")
        meta = (self.archive / name).lstat()
        return dict(entry, state="sealed", dev=meta.st_dev, ino=meta.st_ino,
                    sidecar_dev=side.st_dev, sidecar_ino=side.st_ino, sidecar_sha256=_sha(provenance))

    def archive_entry(self, stream, day):
        for entry in self._manifest()["entries"]:
            if entry["stream"] == stream and entry["day"] == day.isoformat():
                return entry
        return None

    def archive_bytes(self, stream, day):
        entry = self.archive_entry(stream, day)
        if entry is None or entry.get("name") is None:
            return None
        data, _ = _read_regular(self.archive / entry["name"])
        return data

    # ---- retention -------------------------------------------------------------
    @staticmethod
    def _is_ours(dfd, name, dev, ino, sha):
        """True if `name` (relative to the archive directory) is still exactly the file we
        wrote: regular, one link, same device and inode, same SHA-256. None if absent.

        A check-then-unlink race remains; a real host adapter would need more.
        """
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
        except FileNotFoundError:
            return None
        except OSError:
            return False  # e.g. a symlink (ELOOP)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or (meta.st_dev, meta.st_ino) != (dev, ino):
                return False
            digest = hashlib.sha256()
            while block := os.read(fd, 1 << 16):
                digest.update(block)
            return digest.hexdigest() == sha
        finally:
            os.close(fd)

    def expire(self, now, fail_at=None):
        """Remove only manifest-owned, sealed, unchanged archives older than 30x24h."""
        if fail_at not in EXPIRE_FAILPOINTS:
            raise ValueError("unknown failure point")
        now = self._advance_clock(now)
        manifest = self._manifest()
        dfd = os.open(self.archive, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            records, by_name, missing = [], {}, []
            for entry in manifest["entries"]:
                if entry["state"] != "sealed":
                    continue
                name = entry["name"]
                if policy.parsed_filename(name) is None:
                    continue  # never act on a name that is not a plain tool-formatted basename
                try:
                    meta = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                except FileNotFoundError:
                    missing.append(entry)
                    continue
                owned = self._is_ours(dfd, name, entry["dev"], entry["ino"], entry["sha256"]) is True
                records.append(policy.ArchiveRecord(
                    name=name, closed_at=datetime.fromisoformat(entry["closed_at"]), tool_owned=owned,
                    closed=True, regular=stat.S_ISREG(meta.st_mode), symlink=stat.S_ISLNK(meta.st_mode),
                    link_count=meta.st_nlink, device=meta.st_dev, inode=meta.st_ino))
                by_name[name] = entry
            for entry in missing:
                if now > datetime.fromisoformat(entry["closed_at"]) + policy.RETENTION:
                    entry["state"] = "expired"  # finishing a retention step a stop interrupted
                    self._write_signed("archives.json", manifest)
                else:
                    raise FailClosed(f"owned archive {entry['name']} is missing before its retention date")
            removed = []
            for name in policy.retention_candidates(records, now):
                entry = by_name[name]
                meta = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                if (meta.st_dev, meta.st_ino) != (entry["dev"], entry["ino"]):
                    continue
                sidecar = entry["sidecar"]
                side = self._is_ours(dfd, sidecar, entry.get("sidecar_dev"), entry.get("sidecar_ino"),
                                     entry.get("sidecar_sha256"))
                if side is False:
                    # The provenance at that name is not provably ours: keep the whole pair
                    # rather than delete the archive and leave substituted provenance behind.
                    entry["retention_blocked"] = ("file at the sidecar name is not the one this runner "
                                                  "wrote; archive and sidecar both kept")
                    self._write_signed("archives.json", manifest)
                    continue
                if side is True:
                    os.unlink(sidecar, dir_fd=dfd)
                os.unlink(name, dir_fd=dfd)
                os.fsync(dfd)
                if fail_at == "after-unlink-before-manifest":
                    raise SyntheticCrash("stopped after unlinking an expired archive")
                entry["state"] = "expired"
                self._write_signed("archives.json", manifest)
                removed.append(name)
            return removed
        finally:
            os.close(dfd)
