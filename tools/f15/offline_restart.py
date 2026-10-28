"""F15 S3: immutable, offline restart-result sidecars for existing S2 reports.

Synthetic-only, no supervisor/process monitor, no root-path creation, and no
assertion that an actual Worldserver/Authserver restart occurred. Callers MUST
supply independently verified restart outcomes; they cannot be inferred here.
The S3 subclass must be used by all writers/readers in a future integration:
legacy S2 index rebuild does not project sidecar statuses.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import uuid

import offline_store as _store
from offline_store import IncidentStore, NAMESPACE, SCHEMA, MAX_REPORT, utc, safe_name

SIDECAR_SCHEMA = "F15-S3-OFFLINE-RESTART-1"
SIDECAR_PATTERN = re.compile(r"^restart-([0-9a-f-]{36})-([0-9a-f-]{36})\.txt$")
SIDECAR_LIMIT = 4096
# P30 offline TEST-FIXTURE ceilings, NOT owner-approved retention policy.
MAX_RESTART_SIDECARS_PER_INCIDENT = 8
MAX_RESTART_SIDECARS_PER_SERVICE = 128
MAX_TOTAL_RESTART_SIDECARS = 256
MAX_FUTURE_CLOCK_SKEW = timedelta(minutes=5)


def impossible_future(stamp):
    """Wall-clock sanity check only; NOT real-event provenance validation."""
    when = datetime.strptime(utc(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return when > datetime.now(timezone.utc) + MAX_FUTURE_CLOCK_SKEW



@dataclass(frozen=True)
class RestartObservation:
    incident_id: str
    attempt: str
    observed_utc: str
    outcome: str
    verified: bool

    def checked(self):
        try:
            incident = uuid.UUID(self.incident_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("invalid incident identity") from exc
        if str(incident) != self.incident_id:
            raise ValueError("noncanonical incident identity")
        safe_name(self.attempt)
        utc(self.observed_utc)
        if self.outcome not in ("succeeded", "failed"):
            raise ValueError("restart outcome must be succeeded or failed")
        if type(self.verified) is not bool:
            raise ValueError("verified status must be bool")
        return self

    def identity(self):
        self.checked()
        return str(uuid.uuid5(NAMESPACE, "restart\x1f" + self.incident_id + "\x1f" + self.attempt))

    def info(self):
        self.checked()
        return {
            "schema": SIDECAR_SCHEMA,
            "incident_id": self.incident_id,
            "sidecar_id": self.identity(),
            "attempt": self.attempt,
            "observed_utc": self.observed_utc,
            "outcome": self.outcome,
            "verified": self.verified,
        }

    def filename(self):
        return "restart-" + self.incident_id + "-" + self.identity() + ".txt"


def sidecar_bytes(info):
    header = ("COSMIC CORE - RESTART OUTCOME SIDECAR\n"
              "Schema: " + SIDECAR_SCHEMA + "\n"
              "Incident ID: " + info["incident_id"] + "\n"
              "Verified restart: " + info["outcome"] + "\n"
              "Metadata JSON: " + json.dumps(info, sort_keys=True, ensure_ascii=False,
                                             separators=(",", ":")) + "\n").encode("utf-8")
    out = header + b"Finalized SHA-256: " + hashlib.sha256(header).hexdigest().encode("ascii") + b"\n"
    if len(out) > SIDECAR_LIMIT:
        raise ValueError("sidecar length")
    return out


class RestartSidecarStore(IncidentStore):
    """S3 additive projection of immutable restart evidence into crash history."""

    def _read_sidecar(self, name):
        if not SIDECAR_PATTERN.fullmatch(name):
            return None
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=self._fd)
            with os.fdopen(fd, "rb") as file:
                import stat
                st = os.fstat(file.fileno())
                if not stat.S_ISREG(st.st_mode) or st.st_size > SIDECAR_LIMIT:
                    return None
                data = file.read(SIDECAR_LIMIT + 1)
            if len(data) > SIDECAR_LIMIT:
                return None
            _, marker = data.rsplit(b"Finalized SHA-256: ", 1)
            body = data[:-(len(marker) + len(b"Finalized SHA-256: "))]
            if marker != hashlib.sha256(body).hexdigest().encode("ascii") + b"\n":
                return None
            line = next(x for x in body.decode("utf-8").splitlines()
                        if x.startswith("Metadata JSON: "))
            info = json.loads(line[len("Metadata JSON: "):])
            if set(info) != {"schema", "incident_id", "sidecar_id", "attempt",
                             "observed_utc", "outcome", "verified"}:
                return None
            if info["schema"] != SIDECAR_SCHEMA or info["verified"] is not True:
                return None
            obs = RestartObservation(info["incident_id"], info["attempt"],
                                     info["observed_utc"], info["outcome"],
                                     info["verified"]).checked()
            if (obs.identity() != info["sidecar_id"] or obs.filename() != name
                    or sidecar_bytes(info) != data):
                return None
            return info
        except (OSError, ValueError, KeyError, StopIteration,
                TypeError, UnicodeError):
            return None

    def _sidecars(self, valid_incidents):
        attached, invalid = {}, []
        for name in self._dir_names_bounded():
            if not SIDECAR_PATTERN.fullmatch(name):
                continue
            info = self._read_sidecar(name)
            if (info is None or info["incident_id"] not in valid_incidents or
                    info["observed_utc"] < valid_incidents[info["incident_id"]]["end_utc"] or
                    impossible_future(info["observed_utc"])):
                # A reported restart before the incident ended cannot be
                # projected as the latest outcome, even if the sidecar bytes
                # themselves have a valid hash.
                invalid.append(name)
            else:
                attached.setdefault(info["incident_id"], []).append(info)
        for entries in attached.values():
            entries.sort(key=lambda item: (item["observed_utc"], item["sidecar_id"]))
        return attached, sorted(invalid)

    def _rebuild_locked(self):
        reports, bad_reports = self._reports()
        valid_incidents = {info["incident_id"]: info for _, info in reports}
        sidecars, bad_sidecars = self._sidecars(valid_incidents)
        world = sum(info["service"] == "worldserver" for _, info in reports)
        auth = len(reports) - world
        lines = ["COSMIC CORE - CRASH HISTORY", "Schema: " + SCHEMA,
                 f"Worldserver: {world}", f"Authserver: {auth}",
                 f"Total: {len(reports)}",
                 f"Unverified or modified report files: {len(bad_reports)}",
                 f"Unverified or orphan restart sidecars: {len(bad_sidecars)}", ""]
        for name, info in reports:
            attempts = sidecars.get(info["incident_id"], [])
            if not attempts:
                state = "Not verified"
            else:
                # Equal-second observation times cannot establish ordering
                # of distinct restart attempts. Never choose "succeeded"
                # merely by sorting UUID text as a tie-breaker.
                latest_utc = attempts[-1]["observed_utc"]
                tied = [x for x in attempts if x["observed_utc"] == latest_utc]
                if len(tied) > 1:
                    state = ("Ambiguous (" + str(len(tied)) +
                             " attempts observed at " + latest_utc +
                             "; sequence not verified)")
                else:
                    state = attempts[-1]["outcome"] + " (attempt " + attempts[-1]["attempt"] + ")"
            lines.append(f"{info['end_utc']} | {info['service']} | "
                         f"{info['incident_id']} | {name} | "
                         f"{info['termination']} | restart: {state}")
        if bad_reports:
            lines.extend(["", "WARNING: some named reports are invalid or modified; verified totals exclude them.",
                          "Do not edit immutable reports; future operator notes belong in reviewed sidecars."])
            lines.extend("Unverified report: " + name for name in bad_reports)
        if bad_sidecars:
            lines.extend(["", "WARNING: modified, invalid or orphan restart sidecars are excluded."])
            lines.extend("Unverified restart sidecar: " + name for name in bad_sidecars)
        temp = self._temp(("\n".join(lines) + "\n").encode("utf-8"))
        try:
            os.replace(temp, "Crash-History.txt",
                       src_dir_fd=self._fd, dst_dir_fd=self._fd)
            self._durable()
        finally:
            self._unlink(temp)
        return world, auth

    def _admit_restart_locked(self, incident_id: str, service: str,
                              valid, new_bytes: int):
        """P30: bound S3 restart sidecars while holding the verified lock.

        One bounded scan counts this incident's sidecars, sidecars of the
        same daemon (via the finalized incident's service), ALL
        restart-shaped names (malformed, orphaned or symlinked ones too,
        conservatively) and the one byte budget shared with finalized
        crash/error reports. Nothing is evicted, renamed or overwritten.
        Limits are offline TEST FIXTURES, not an owner retention policy,
        and a refusal is an untrusted diagnostic, not a real daemon event.
        """
        if (service not in ("worldserver", "authserver") or
                type(new_bytes) is not int or new_bytes < 0):
            raise ValueError("invalid offline restart quota request")
        owner = {info["incident_id"]: info["service"] for _, info in valid}
        total = per_incident = per_service = byte_count = 0
        for name in self._dir_names_bounded():
            if _store.RESTART_SHAPED.fullmatch(name):
                total += 1
                byte_count += self._lstat_size(name)
                match = SIDECAR_PATTERN.fullmatch(name)
                if match:
                    if match.group(1) == incident_id:
                        per_incident += 1
                    if owner.get(match.group(1)) == service:
                        per_service += 1
            elif (_store.REPORT.fullmatch(name) or
                    _store.ERROR_CAPACITY_REPORT.fullmatch(name)):
                byte_count += self._lstat_size(name)
        if (per_incident >= MAX_RESTART_SIDECARS_PER_INCIDENT or
                per_service >= MAX_RESTART_SIDECARS_PER_SERVICE or
                total >= MAX_TOTAL_RESTART_SIDECARS or
                byte_count + new_bytes > _store.MAX_TOTAL_REPORT_BYTES):
            self._count_rejection("capacity")
            raise OverflowError(
                "F15 offline restart sidecar capacity reached; immutable "
                "records preserved, new sidecar refused")

    def publish_restart(self, observation: RestartObservation):
        """Atomic immutable sidecar; True new, False duplicate/not verified."""
        observation.checked()
        if not observation.verified:
            return False
        if impossible_future(observation.observed_utc):
            # Impossible future timestamps must not win latest-outcome
            # projection indefinitely. Keep a bounded adapter clock skew.
            raise ValueError("restart observation is implausibly in the future")
        name = observation.filename()
        with self._locked():
            valid, _ = self._reports()
            originals = {info["incident_id"]: info for _, info in valid}
            original = originals.get(observation.incident_id)
            if original is None:
                # Never claim a restart for an absent/corrupt crash report.
                raise ValueError("original finalized incident does not exist")
            if observation.observed_utc < original["end_utc"]:
                # The S3 synthetic caller must supply a chronology that does
                # not predate the recorded death. Adapter clock skew and
                # event-source provenance require later explicit review.
                raise ValueError("restart observation predates incident death")
            try:
                os.stat(name, dir_fd=self._fd, follow_symlinks=False)
                exists = True
            except FileNotFoundError:
                exists = False
            if exists:
                old = self._read_sidecar(name)
                if old is None or old != observation.info():
                    self._rebuild_locked()
                    raise FileExistsError("restart attempt sidecar conflict")
                self._rebuild_locked()
                return False
            payload = sidecar_bytes(observation.info())
            # P30: bounded AFTER duplicate idempotence, BEFORE any write.
            self._admit_restart_locked(observation.incident_id,
                                       original["service"], valid, len(payload))
            temp = self._temp(payload)
            try:
                os.link(temp, name, src_dir_fd=self._fd,
                        dst_dir_fd=self._fd, follow_symlinks=False)
                self._durable()
            finally:
                self._unlink(temp)
            self._rebuild_locked()
            return True
