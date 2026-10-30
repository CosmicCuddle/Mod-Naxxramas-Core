"""F15 synthetic restart-safe byte-range journal: TEST FIXTURE ONLY.

NEVER import into server services, cron, PM2, or production tooling.
Every path is created inside an internal tempfile.TemporaryDirectory.
This is a proof-of-concept for durable checkpoints and failure injection, NOT
a production-grade collector or retention engine.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

STREAMS = frozenset({"Worldserver-out", "Worldserver-err", "Authserver-native"})
MAX_CHUNK = 64


class SyntheticCrash(RuntimeError):
    pass


class JournalFixture:
    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="f15-journal-synthetic-")
        self.root = Path(self._temporary.name)
        self.source = self.root / "source"
        self.archive = self.root / "segments"
        self.state = self.root / "checkpoints"
        for directory in (self.source, self.archive, self.state):
            directory.mkdir(mode=0o700)

    def close(self):
        self._temporary.cleanup()

    @staticmethod
    def _check_stream(stream):
        if stream not in STREAMS:
            raise ValueError("unknown fixture stream")

    def _path(self, stream):
        self._check_stream(stream)
        return self.source / (stream + ".log")

    def _state_path(self, stream):
        return self.state / (stream + ".json")

    def seed(self, stream, payload):
        self._check_stream(stream)
        fd = os.open(self._path(stream), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            self._write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)

    def append(self, stream, payload):
        self._check_stream(stream)
        fd = os.open(self._path(stream), os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW)
        try:
            self._write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _write_all(fd, data):
        at = 0
        while at < len(data):
            n = os.write(fd, data[at:])
            if n <= 0:
                raise IOError("short write")
            at += n

    @staticmethod
    def _dir_sync(directory):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _serialize(state):
        data = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("ascii")
        digest = hashlib.sha256(data).hexdigest()
        return json.dumps({"state": state, "sha256": digest}, sort_keys=True).encode("ascii")

    def _read_state(self, stream):
        file = self._state_path(stream)
        if not file.exists():
            return None
        raw = file.read_bytes()
        doc = json.loads(raw)
        state = doc["state"]
        if hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest() != doc["sha256"]:
            raise ValueError("corrupted manifest checksum")
        if set(state) != {"dev", "ino", "offset"} or not all(
                isinstance(state[x], int) and state[x] >= (0 if x == "offset" else 1)
                for x in state):
            raise ValueError("untrusted manifest content")
        return state

    def checkpoint(self, stream):
        self._check_stream(stream)
        x = self._read_state(stream)
        return None if x is None else dict(x)

    def _commit(self, stream, state, fail_at=None):
        # Unique internal temp path; atomic replace + directory sync for the
        # disposable Linux runner. Not protected against malicious writers.
        # A simulated crash can leave a fully fsynced .pending manifest. On
        # recovery, reuse it only if it matches the EXACT expected next state.
        temp = self.state / (stream + ".pending")
        serialized = self._serialize(state)
        if temp.exists() or temp.is_symlink():
            meta = temp.lstat()
            if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                    or temp.read_bytes() != serialized):
                raise ValueError("untrusted or mismatched orphaned pending manifest")
        else:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                self._write_all(fd, serialized)
                os.fsync(fd)
            finally:
                os.close(fd)
        if fail_at == "before-manifest-publish":
            raise SyntheticCrash("simulated stop before checkpoint manifest publication")
        os.replace(temp, self._state_path(stream))
        self._dir_sync(self.state)

    def _chunk_name(self, stream, state, start, end, chunk):
        digest = hashlib.sha256(chunk).hexdigest()[:16]
        return f"{stream}-{state['dev']}-{state['ino']}-{start}-{end}-{digest}.chunk"

    def _publish(self, stream, state, start, chunk, fail_at):
        end = start + len(chunk)
        name = self._chunk_name(stream, state, start, end, chunk)
        dest = self.archive / name
        if dest.exists():
            if dest.read_bytes() != chunk:
                raise ValueError("existing segment changed")
            return
        temp = self.archive / (name + ".pending")
        if temp.exists():
            oldmeta = temp.lstat()
            if (not stat.S_ISREG(oldmeta.st_mode) or oldmeta.st_nlink != 1
                    or temp.read_bytes() != chunk):
                raise ValueError("untrusted orphaned pending segment")
        else:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                self._write_all(fd, chunk)
                os.fsync(fd)
            finally:
                os.close(fd)
        if fail_at == "before-publish":
            raise SyntheticCrash("simulated stop before segment publication")
        os.replace(temp, dest)
        self._dir_sync(self.archive)
        if fail_at == "after-publish":
            raise SyntheticCrash("simulated stop after segment publication")

    def _recover(self, stream, state):
        """Reconcile contiguous immutable segments committed before state update."""
        pattern = re.compile(
            rf"\A{re.escape(stream)}-(\d+)-(\d+)-(\d+)-(\d+)-([0-9a-f]{{16}})\.chunk\Z")
        recovered = 0
        for _ in range(100):
            matches = []
            for p in self.archive.iterdir():
                m = pattern.fullmatch(p.name)
                if not m:
                    continue
                dev, ino, start, end = map(int, m.group(1, 2, 3, 4))
                if (dev, ino, start) != (state["dev"], state["ino"], state["offset"]):
                    continue
                matches.append((p, end, m.group(5)))
            if not matches:
                return state, recovered
            if len(matches) != 1:
                raise ValueError("ambiguous checkpoint recovery")
            file, end, digest = matches[0]
            metadata = file.lstat()
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                    or end <= state["offset"] or end - state["offset"] > MAX_CHUNK):
                raise ValueError("untrusted archived segment")
            payload = file.read_bytes()
            if len(payload) != end - state["offset"] or hashlib.sha256(payload).hexdigest()[:16] != digest:
                raise ValueError("corrupt archived segment")
            state = {"dev": state["dev"], "ino": state["ino"], "offset": end}
            self._commit(stream, state)
            recovered += 1
        raise ValueError("unbounded recovery sequence")

    def poll(self, stream, fail_at=None):
        """Capture one <=64 byte fixture span. All files are synthetic."""
        self._check_stream(stream)
        if fail_at not in (None, "before-publish", "after-publish", "before-checkpoint-publish", "after-checkpoint"):
            raise ValueError("invalid synthetic crash point")
        fd = os.open(self._path(stream), os.O_RDONLY | os.O_NOFOLLOW)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                raise ValueError("unsafe synthetic source")
            state = self._read_state(stream)
            if state is None:
                state = {"dev": meta.st_dev, "ino": meta.st_ino, "offset": meta.st_size}
                self._commit(stream, state)
                return "bootstrap-skipped", b""
            state, recovered = self._recover(stream, state)
            warning = None
            if (state["dev"], state["ino"]) != (meta.st_dev, meta.st_ino):
                warning = "source replaced: old unread tail not guaranteed"
                state = {"dev": meta.st_dev, "ino": meta.st_ino, "offset": 0}
                self._commit(stream, state)
            elif meta.st_size < state["offset"]:
                warning = "source truncated: old unread tail not guaranteed"
                state = {"dev": meta.st_dev, "ino": meta.st_ino, "offset": 0}
                self._commit(stream, state)
            remaining = meta.st_size - state["offset"]
            if remaining <= 0:
                return ("recovered" if recovered else "unchanged"), b""
            nbytes = min(MAX_CHUNK, remaining)
            chunk = os.pread(fd, nbytes, state["offset"])
            if len(chunk) != nbytes:
                raise IOError("source shortened while copying")
            current = os.fstat(fd)
            if (current.st_dev, current.st_ino) != (meta.st_dev, meta.st_ino) or current.st_size < state["offset"] + nbytes:
                raise IOError("source replaced while copying")
            self._publish(stream, state, state["offset"], chunk, fail_at)
        finally:
            os.close(fd)
        new_state = {"dev": state["dev"], "ino": state["ino"], "offset": state["offset"] + len(chunk)}
        self._commit(stream, new_state,
                     fail_at="before-manifest-publish" if fail_at == "before-checkpoint-publish" else None)
        if fail_at == "after-checkpoint":
            raise SyntheticCrash("simulated stop after checkpoint publication")
        return (warning or ("recovered-and-append" if recovered else "appended")), chunk

    def published(self, stream):
        self._check_stream(stream)
        return [p for p in self.archive.iterdir() if p.name.startswith(stream + "-") and p.name.endswith(".chunk")]

    def published_bytes(self, stream):
        """Sort only tests' immutable segments by their numeric START offset."""
        pattern = re.compile(rf"\A{re.escape(stream)}-\d+-\d+-(\d+)-(\d+)-[0-9a-f]{{16}}\.chunk\Z")
        items = []
        for path in self.published(stream):
            match = pattern.fullmatch(path.name)
            if match:
                items.append((int(match.group(1)), int(match.group(2)), path.read_bytes()))
        return b"".join(content for _, _, content in sorted(items))
