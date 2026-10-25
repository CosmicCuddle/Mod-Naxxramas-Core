"""F15 S4b OFFLINE model: bounded independent WARNING/ERROR log bursts.

Synthetic-only. No tailing, file I/O, Linux supervisor, root paths, report
publishing, network access, process launch, or incident/crash counter changes.

A caller-set verified_stream boolean is NOT actual provenance. A future
owner-approved adapter MUST derive process/stream/sequence independently.
No raw log text is accepted or retained, to avoid private-data leakage.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import re

SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")
LEVELS = frozenset(("WARN", "ERROR"))
STREAMS = frozenset(("stdout", "stderr", "world-log", "auth-log"))
SERVICES = frozenset(("worldserver", "authserver"))
SOURCE = "verified-stream-fixture"


@dataclass(frozen=True)
class LogEvidence:
    service: str
    instance: str
    stream: str
    level: str
    code: str
    seq: int
    uptime_ms: int
    source: str = "unverified-text"
    verified_stream: bool = False

    def checked(self) -> "LogEvidence":
        if self.service not in SERVICES:
            raise ValueError("service must be worldserver/authserver")
        if not isinstance(self.instance, str) or not SAFE.fullmatch(self.instance):
            raise ValueError("unsafe process identity")
        if self.stream not in STREAMS:
            raise ValueError("unrecognized stream")
        if self.level not in LEVELS:
            raise ValueError("not a warning or error")
        if not isinstance(self.code, str) or not SAFE.fullmatch(self.code):
            raise ValueError("unsafe bounded error category")
        if type(self.seq) is not int or not 0 <= self.seq < (1 << 63):
            raise ValueError("sequence must be a bounded nonnegative integer")
        if type(self.uptime_ms) is not int or not 0 <= self.uptime_ms < (1 << 63):
            raise ValueError("uptime must be bounded nonnegative integer")
        if type(self.verified_stream) is not bool:
            raise ValueError("verified_stream must be bool")
        return self


@dataclass(frozen=True)
class BurstAlert:
    service: str
    instance: str
    stream: str
    level: str
    code: str
    threshold: int
    window_ms: int
    observed_uptime_ms: int

    # This has NO crash report ID, status claim, underlying log text or
    # restart result. A future warning report needs a separate safe sink.


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    alert: BurstAlert | None = None


@dataclass
class _Bucket:
    timestamps: deque[int] = field(default_factory=deque)
    emitted: bool = False


class OfflineBurstTracker:
    """In-memory deterministic model with explicit hard memory bounds.

    A stream is keyed by (service, instance, stream) and sequence numbers must
    strictly increase. No retry or replay after a reject mutates counters.
    Per category, first reaching the threshold in one sliding window emits
    one alert; sustained same-window noise never produces alert floods.
    An interval with no events in the last window rearms the category.
    """

    def __init__(self, *, threshold: int = 3, window_ms: int = 60_000,
                 max_groups: int = 256, max_streams: int = 128):
        if (any(type(x) is not int for x in
                (threshold, window_ms, max_groups, max_streams)) or
                not 2 <= threshold <= 32 or
                not 1000 <= window_ms <= 86_400_000 or
                not 1 <= max_groups <= 4096 or
                not 1 <= max_streams <= 4096):
            raise ValueError("unsafe tracker limits")
        self.threshold = threshold
        self.window_ms = window_ms
        self.max_groups = max_groups
        self.max_streams = max_streams
        self._streams: dict[tuple[str, str, str], tuple[int, int]] = {}
        self._groups: dict[tuple[str, str, str, str, str], _Bucket] = {}

    def observe(self, sample: LogEvidence) -> Decision:
        if not isinstance(sample, LogEvidence):
            return Decision("rejected", "invalid evidence type")
        try:
            sample.checked()
        except ValueError as exc:
            return Decision("rejected", str(exc))

        if sample.source != SOURCE or not sample.verified_stream:
            return Decision("unverified", "no authenticated log-stream provenance")

        stream_key = (sample.service, sample.instance, sample.stream)
        previous = self._streams.get(stream_key)
        if previous is not None and sample.seq <= previous[0]:
            return Decision("rejected", "stale/replayed or duplicate log sequence")
        if previous is not None and sample.uptime_ms < previous[1]:
            return Decision("rejected", "process stream uptime moved backwards")

        group_key = (*stream_key, sample.level, sample.code)
        if stream_key not in self._streams and len(self._streams) >= self.max_streams:
            return Decision("capacity", "maximum independent streams reached")
        if group_key not in self._groups and len(self._groups) >= self.max_groups:
            return Decision("capacity", "maximum independent categories reached")

        # All checks complete: mutations begin here.
        self._streams[stream_key] = (sample.seq, sample.uptime_ms)
        bucket = self._groups.setdefault(group_key, _Bucket())
        while bucket.timestamps and sample.uptime_ms - bucket.timestamps[0] > self.window_ms:
            bucket.timestamps.popleft()
        if not bucket.timestamps:
            bucket.emitted = False
        bucket.timestamps.append(sample.uptime_ms)
        while len(bucket.timestamps) > self.threshold:
            bucket.timestamps.popleft()

        if len(bucket.timestamps) == self.threshold and not bucket.emitted:
            bucket.emitted = True
            return Decision(
                "alert",
                "bounded synthetic warning/error burst; no OS or log attestation",
                BurstAlert(sample.service, sample.instance, sample.stream,
                           sample.level, sample.code, self.threshold,
                           self.window_ms, sample.uptime_ms),
            )
        return Decision("ignored", "below threshold or burst already emitted")

    def counts(self) -> tuple[int, int]:
        """Metadata only; not crash/restart totals."""
        return len(self._streams), len(self._groups)
