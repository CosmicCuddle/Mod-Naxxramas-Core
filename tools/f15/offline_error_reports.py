"""F15 S4c OFFLINE independent immutable warning/error-burst report store.

Uses the pinned descriptor, exclusive lock, fsynced temp and link-based
no-clobber of reviewed S2/S3 primitives. Does not tail logs, attest
process identity, start services, touch /root, or publish crash incidents.
All supplied 'verified' claims are synthetic. NOT a production reporter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import stat
import uuid

from offline_error_bursts import BurstAlert, SAFE, SERVICES, STREAMS, LEVELS
from offline_restart import RestartSidecarStore, impossible_future
from offline_store import NAMESPACE, utc

ERROR_SCHEMA = "F15-S4C-OFFLINE-ERROR-BURST-1"
ERROR_FILE = re.compile(r"^error-burst-(worldserver|authserver)-([0-9a-f-]{36})\.txt$")
MAX_ERROR_FILE = 4096


@dataclass(frozen=True)
class ErrorBurstObservation:
    alert: BurstAlert
    observed_utc: str
    verified: bool

    def checked(self) -> "ErrorBurstObservation":
        b = self.alert
        if not isinstance(b, BurstAlert):
            raise ValueError("trusted offline BurstAlert fixture required")
        if not isinstance(b.service, str) or b.service not in SERVICES:
            raise ValueError("invalid service")
        if not isinstance(b.instance, str) or not SAFE.fullmatch(b.instance):
            raise ValueError("invalid incarnation")
        if not isinstance(b.stream, str) or b.stream not in STREAMS:
            raise ValueError("invalid source stream")
        if not isinstance(b.level, str) or b.level not in LEVELS:
            raise ValueError("invalid severity")
        if not isinstance(b.code, str) or not SAFE.fullmatch(b.code):
            raise ValueError("invalid category")
        if (type(b.threshold) is not int or not 2 <= b.threshold <= 32 or
                type(b.window_ms) is not int or not 1000 <= b.window_ms <= 86_400_000 or
                type(b.observed_uptime_ms) is not int or
                not 0 <= b.observed_uptime_ms < (1 << 63)):
            raise ValueError("invalid bounds or monotonic event identity")
        utc(self.observed_utc)
        if type(self.verified) is not bool:
            raise ValueError("verified must be boolean")
        return self

    def identity(self) -> str:
        b = self.checked().alert
        identity_fields = [b.service, b.instance, b.stream, b.level, b.code,
                           str(b.threshold), str(b.window_ms), str(b.observed_uptime_ms)]
        return str(uuid.uuid5(NAMESPACE, "error-burst\x1f" + "\x1f".join(identity_fields)))

    def info(self) -> dict:
        b = self.checked().alert
        return {"schema": ERROR_SCHEMA, "error_id": self.identity(),
                "service": b.service, "instance": b.instance,
                "stream": b.stream, "level": b.level, "code": b.code,
                "threshold": b.threshold, "window_ms": b.window_ms,
                "observed_uptime_ms": b.observed_uptime_ms,
                "observed_utc": self.observed_utc, "verified": self.verified}

    def filename(self) -> str:
        return "error-burst-" + self.alert.service + "-" + self.identity() + ".txt"


def error_bytes(info: dict) -> bytes:
    """Canonical redacted file; SHA is integrity check, NOT provenance/auth."""
    head = ("COSMIC CORE - SERVER WARNING/ERROR BURST REPORT\n"
            + "Schema: " + ERROR_SCHEMA + "\n"
            + "Process: " + info["service"] + "\n"
            + "Severity: " + info["level"] + "\n"
            + "Category: " + info["code"] + "\n"
            + "Observed UTC: " + info["observed_utc"] + "\n"
            + "Source verification: SYNTHETIC CLAIM ONLY\n"
            + "No raw log message, crash or restart outcome is included.\n"
            + "Metadata JSON: " + json.dumps(info, sort_keys=True,
                 ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    output = head + b"Finalized SHA-256: " + hashlib.sha256(head).hexdigest().encode("ascii") + b"\n"
    if len(output) > MAX_ERROR_FILE:
        raise ValueError("error report exceeds size limit")
    return output


class OfflineErrorReportStore(RestartSidecarStore):
    """Separate immutable error records/index; preserves S3 crash history."""

    def _read_error(self, name):
        if not ERROR_FILE.fullmatch(name):
            return None
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=self._fd)
            with os.fdopen(fd, "rb") as file:
                st = os.fstat(file.fileno())
                if (not stat.S_ISREG(st.st_mode) or st.st_size > MAX_ERROR_FILE or
                        st.st_size == 0 or st.st_nlink != 1 or
                        st.st_uid != os.geteuid() or st.st_mode & 0o077):
                    return None
                payload = file.read(MAX_ERROR_FILE + 1)
            if len(payload) > MAX_ERROR_FILE:
                return None
            body, trailer = payload.rsplit(b"Finalized SHA-256: ", 1)
            if trailer != hashlib.sha256(body).hexdigest().encode("ascii") + b"\n":
                return None
            line = next(x for x in body.decode("utf-8").splitlines()
                        if x.startswith("Metadata JSON: "))
            info = json.loads(line[len("Metadata JSON: "):])
            if set(info) != {"schema", "error_id", "service", "instance",
                             "stream", "level", "code", "threshold", "window_ms",
                             "observed_uptime_ms", "observed_utc", "verified"}:
                return None
            if info["schema"] != ERROR_SCHEMA or info["verified"] is not True:
                return None
            alert = BurstAlert(info["service"], info["instance"], info["stream"],
                               info["level"], info["code"], info["threshold"],
                               info["window_ms"], info["observed_uptime_ms"])
            event = ErrorBurstObservation(alert, info["observed_utc"], info["verified"])
            if (event.identity() != info["error_id"] or
                    event.filename() != name or error_bytes(info) != payload or
                    impossible_future(info["observed_utc"])):
                return None
            return info
        except (OSError, ValueError, KeyError, StopIteration, TypeError,
                UnicodeError, AttributeError):
            return None

    def _errors(self):
        # Unexpected names are counted, NEVER echoed in text (newline/escape
        # path injection could otherwise corrupt the human index).
        valid, invalid = {}, []
        for name in os.listdir(self._fd):
            if not (name.startswith("error-burst-") and name.endswith(".txt")):
                continue
            if not ERROR_FILE.fullmatch(name):
                invalid.append(None)
                continue
            info = self._read_error(name)
            if info is None:
                invalid.append(name)
            else:
                valid[info["error_id"]] = (name, info)
        return (sorted(valid.values(), key=lambda p:
                       (p[1]["observed_utc"], p[1]["error_id"])), invalid)

    def _rebuild_errors_locked(self):
        records, invalid = self._errors()
        worlds = sum(i["service"] == "worldserver" for _, i in records)
        auths = len(records) - worlds
        warnings = sum(i["level"] == "WARN" for _, i in records)
        errors = len(records) - warnings
        lines = ["COSMIC CORE - WARNING / ERROR HISTORY",
                 "Schema: " + ERROR_SCHEMA,
                 "Offline fixture reports, NOT authenticated service logs",
                 f"Worldserver: {worlds}", f"Authserver: {auths}",
                 f"Warnings: {warnings}", f"Errors: {errors}",
                 f"Total bursts: {len(records)}",
                 f"Invalid / modified warning reports: {len(invalid)}", ""]
        for name, info in records:
            lines.append(f"{info['observed_utc']} | {info['service']} | "
                         f"{info['level']} | {info['code']} | {info['error_id']} | {name}")
        if invalid:
            lines.extend(["", "WARNING: invalid, hostile or modified error reports excluded."])
            for name in sorted(x for x in invalid if x is not None):
                lines.append("Unverified error report: " + name)
        temp = self._temp(("\n".join(lines) + "\n").encode("utf-8"))
        try:
            os.replace(temp, "Error-History.txt", src_dir_fd=self._fd,
                       dst_dir_fd=self._fd)
            self._durable()
        finally:
            self._unlink(temp)
        return worlds, auths, warnings, errors

    def rebuild_errors(self):
        with self._locked():
            return self._rebuild_errors_locked()

    def publish_error(self, observation: ErrorBurstObservation) -> bool:
        """True on new durable synthetic report; False on duplicate/unverified."""
        if not isinstance(observation, ErrorBurstObservation):
            raise TypeError("ErrorBurstObservation required")
        observation.checked()
        if not observation.verified:
            return False
        if impossible_future(observation.observed_utc):
            raise ValueError("error observation implausibly in the future")
        info = observation.info()
        name = observation.filename()
        with self._locked():
            try:
                os.stat(name, dir_fd=self._fd, follow_symlinks=False)
                exists = True
            except FileNotFoundError:
                exists = False
            if exists:
                prior = self._read_error(name)
                if prior is None or prior != info:
                    self._rebuild_errors_locked()
                    raise FileExistsError("immutable error report conflict")
                self._rebuild_errors_locked()
                return False
            temp = self._temp(error_bytes(info))
            try:
                os.link(temp, name, src_dir_fd=self._fd,
                        dst_dir_fd=self._fd, follow_symlinks=False)
                self._durable()
            finally:
                self._unlink(temp)
            # A later derived-index fault cannot lose the durable report.
            self._rebuild_errors_locked()
            return True
