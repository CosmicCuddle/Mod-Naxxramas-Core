"""F15 OFFLINE ONLY archive/retention policy. NO file IO, process control, or deletion.

The caller would need to supply independently verified stream and archive metadata.
This file is NOT an operational Worldserver/Authserver log collector.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Literal

UTC = timezone.utc
ROLE = Literal["Worldserver", "Authserver"]
SOURCE = Literal["out", "err", "native"]
ARCHIVE_RE = re.compile(
    r"\A(Worldserver|Authserver)-Console-"
    r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}Z)-"
    r"(out|err|native)-([0-9a-f]{12})\.txt\Z", re.ASCII
)
RETENTION = timedelta(days=30)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must have an explicit UTC offset")
    return value.astimezone(UTC)


def archive_filename(role: ROLE, source: SOURCE, closed_at: datetime, session_tag: str) -> str:
    """Return only a filename. No path operations or file writing."""
    if role not in ("Worldserver", "Authserver") or source not in ("out", "err", "native"):
        raise ValueError("invalid stream identity")
    if not re.fullmatch(r"[0-9a-f]{12}", session_tag, flags=re.ASCII):
        raise ValueError("session tag must be a lowercase twelve-digit hex string")
    t = _utc(closed_at)
    return f"{role}-Console-{t:%Y-%m-%d_%H-%M-%S}Z-{source}-{session_tag}.txt"


def parsed_filename(name: str) -> tuple[str, str, datetime] | None:
    """Allow only a tool-formatted BASENAME, never an arbitrary path."""
    if not isinstance(name, str) or not (match := ARCHIVE_RE.fullmatch(name)):
        return None
    try:
        closed_at = datetime.strptime(match.group(2), "%Y-%m-%d_%H-%M-%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None
    return match.group(1), match.group(3), closed_at


@dataclass(frozen=True)
class ArchiveRecord:
    """Metadata a future collector must verify using trusted directory/file handles."""
    name: str
    closed_at: datetime
    tool_owned: bool
    closed: bool
    regular: bool
    symlink: bool
    link_count: int
    device: int
    inode: int


def retention_candidates(records: list[ArchiveRecord], now: datetime) -> tuple[str, ...]:
    """Conservative *plan* for closed-archive expiry. NEVER deletes anything.

    Actual production pruning additionally needs pinned directory FDs, locks,
    manifests, ownership checks, and identity revalidation to resist races.
    """
    current = _utc(now)
    duplicates = Counter(r.name for r in records)
    eligible: list[str] = []
    for item in records:
        parsed = parsed_filename(item.name)
        if not parsed or duplicates[item.name] != 1:
            continue
        closed_timestamp = _utc(item.closed_at)
        if not (item.tool_owned and item.closed and item.regular and not item.symlink
                and item.link_count == 1 and item.device > 0 and item.inode > 0):
            continue
        if parsed[2] != closed_timestamp.replace(microsecond=0):
            continue
        # "Older than 30 days" strictly exceeds the boundary.
        if current > closed_timestamp + RETENTION:
            eligible.append(item.name)
    return tuple(sorted(eligible))


@dataclass(frozen=True)
class StreamCheckpoint:
    device: int
    inode: int
    offset: int
    recorded_at: datetime


@dataclass(frozen=True)
class StreamSample:
    device: int
    inode: int
    size: int
    observed_at: datetime


@dataclass(frozen=True)
class ReadPlan:
    event: Literal["bootstrap-skip", "append", "unchanged", "truncated", "replaced"]
    start: int
    stop: int
    warning: str | None
    checkpoint: StreamCheckpoint


def plan_increment(checkpoint: StreamCheckpoint | None, sample: StreamSample) -> ReadPlan:
    """Non-destructive incremental byte-range model; makes NO filesystem reads.

    Initial observation deliberately skips historical cumulative PM2 log bytes
    rather than backfilling many GiB without a separate owner decision.
    A truncation or rotation cannot guarantee recovery of the old unseen tail.
    """
    now = _utc(sample.observed_at)
    if sample.device <= 0 or sample.inode <= 0 or sample.size < 0:
        raise ValueError("invalid source metadata")
    next_state = StreamCheckpoint(sample.device, sample.inode, sample.size, now)
    if checkpoint is None:
        return ReadPlan("bootstrap-skip", sample.size, sample.size,
                        "Existing bytes are not backfilled automatically", next_state)
    prior_time = _utc(checkpoint.recorded_at)
    if checkpoint.device <= 0 or checkpoint.inode <= 0 or checkpoint.offset < 0:
        raise ValueError("invalid previous checkpoint")
    if now < prior_time:
        raise ValueError("observed time moved backwards")
    if (sample.device, sample.inode) != (checkpoint.device, checkpoint.inode):
        return ReadPlan("replaced", 0, sample.size,
                        "Source inode changed; the prior stream tail may be missing", next_state)
    if sample.size < checkpoint.offset:
        return ReadPlan("truncated", 0, sample.size,
                        "Source shrank; bytes between observations may be missing", next_state)
    if sample.size == checkpoint.offset:
        return ReadPlan("unchanged", sample.size, sample.size, None, next_state)
    return ReadPlan("append", checkpoint.offset, sample.size, None, next_state)
