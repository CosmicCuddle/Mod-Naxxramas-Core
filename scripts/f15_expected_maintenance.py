#!/usr/bin/env python3
"""F15 expected-maintenance marker state.

This module never stops, restarts or signals a service.  It only records a
bounded, service-specific intent supplied by the actual maintenance owner and
requires a second success confirmation before an observed transition can be
treated as expected.

An armed-but-unconfirmed marker can temporarily defer an exact non-fatal
transition while owner confirmation is pending, but it cannot permanently
consume that transition. Expired, malformed, mismatched or insecure state has
no suppression authority and normal incident reporting remains active.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

import f15_incident_checkpoint as checkpoint

MAX_WINDOW = timedelta(minutes=30)
OPERATION_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
TRANSITIONS = {"stop", "restart"}
SERVICES = {"Worldserver", "Authserver"}
CLEAN_MAINTENANCE_SIGNALS = {"SIGINT", "SIGTERM"}


class Refused(RuntimeError):
    pass


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise Refused("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _parse_iso(value: Any) -> datetime:
    if not isinstance(value, str):
        raise Refused("marker timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Refused("invalid marker timestamp") from exc
    return _utc(parsed)


class ExpectedMaintenanceStore:
    def __init__(self, state_root: Path, service: str):
        if service not in SERVICES:
            raise Refused("unsupported service")
        self.root = checkpoint._private_dir(Path(state_root))
        self.service = service
        self.path = self.root / f"{service}.expected-maintenance.json"
        self.lock_path = self.root / f"{service}.checkpoint.lock"

    def _read_unlocked(self) -> dict[str, Any] | None:
        try:
            marker = checkpoint._read_json(self.path)
        except checkpoint.Refused as exc:
            raise Refused(str(exc)) from exc
        if marker is None:
            return None
        required = {
            "version", "service", "operation_id", "transition", "status",
            "created_utc", "expires_utc", "before_identity",
        }
        if set(marker) - (required | {"confirmed_utc"}):
            raise Refused("unexpected marker fields")
        if not required.issubset(marker):
            raise Refused("marker missing required fields")
        if marker["version"] != 1 or marker["service"] != self.service:
            raise Refused("marker identity mismatch")
        if marker["transition"] not in TRANSITIONS:
            raise Refused("invalid expected transition")
        if marker["status"] not in {"armed", "confirmed"}:
            raise Refused("invalid marker status")
        if not isinstance(marker["operation_id"], str) or not OPERATION_RE.fullmatch(marker["operation_id"]):
            raise Refused("invalid operation id")
        if not isinstance(marker["before_identity"], dict):
            raise Refused("invalid before identity")
        created = _parse_iso(marker["created_utc"])
        expires = _parse_iso(marker["expires_utc"])
        if expires <= created or expires - created > MAX_WINDOW:
            raise Refused("invalid expected-maintenance window")
        if marker["status"] == "confirmed":
            confirmed = _parse_iso(marker.get("confirmed_utc"))
            if confirmed < created or confirmed > expires:
                raise Refused("invalid confirmation time")
        elif "confirmed_utc" in marker:
            raise Refused("armed marker may not contain confirmation time")
        return marker

    def read(self) -> dict[str, Any] | None:
        with checkpoint._exclusive_lock(self.lock_path):
            return self._read_unlocked()

    def arm(self, operation_id: str, transition: str,
            created_utc: datetime, expires_utc: datetime) -> dict[str, Any]:
        if not isinstance(operation_id, str) or not OPERATION_RE.fullmatch(operation_id):
            raise Refused("invalid operation id")
        if transition not in TRANSITIONS:
            raise Refused("invalid expected transition")
        created = _utc(created_utc)
        expires = _utc(expires_utc)
        if expires <= created or expires - created > MAX_WINDOW:
            raise Refused("expected-maintenance window must be >0 and <=30 minutes")
        with checkpoint._exclusive_lock(self.lock_path):
            state_path = self.root / f"{self.service}.checkpoint.json"
            try:
                state = checkpoint._read_json(state_path)
            except checkpoint.Refused as exc:
                raise Refused(str(exc)) from exc
            if state is None or state.get("service") != self.service or not isinstance(state.get("identity"), dict):
                raise Refused("valid service checkpoint required before arming maintenance")
            marker = {
                "version": 1,
                "service": self.service,
                "operation_id": operation_id,
                "transition": transition,
                "status": "armed",
                "created_utc": _iso(created),
                "expires_utc": _iso(expires),
                "before_identity": dict(state["identity"]),
            }
            existing = self._read_unlocked()
            if existing is not None:
                if existing == marker:
                    return existing
                raise Refused("expected-maintenance marker already exists")
            checkpoint._atomic_json(self.path, marker)
        return marker

    def confirm(self, operation_id: str, confirmed_utc: datetime) -> dict[str, Any]:
        when = _utc(confirmed_utc)
        with checkpoint._exclusive_lock(self.lock_path):
            marker = self._read_unlocked()
            if marker is None:
                raise Refused("no expected-maintenance marker")
            if marker["operation_id"] != operation_id:
                raise Refused("operation id mismatch")
            if marker["status"] == "confirmed":
                # Confirmation is idempotent by operation identity. A caller
                # retrying after a lost response need not reproduce the exact
                # timestamp from the first successful confirmation.
                return marker
            created = _parse_iso(marker["created_utc"])
            expires = _parse_iso(marker["expires_utc"])
            if when < created or when > expires:
                raise Refused("confirmation outside expected-maintenance window")
            marker = dict(marker)
            marker["status"] = "confirmed"
            marker["confirmed_utc"] = _iso(when)
            checkpoint._atomic_json(self.path, marker)
            return marker

    @staticmethod
    def _world_matches(transition: str, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        before = previous.get("restart_time")
        after = current.get("restart_time")
        if not isinstance(before, int) or isinstance(before, bool):
            return False
        if not isinstance(after, int) or isinstance(after, bool):
            return False
        prev_live = previous.get("status") == "online" and isinstance(previous.get("pid"), int) and previous.get("pid") > 0
        cur_live = current.get("status") == "online" and isinstance(current.get("pid"), int) and current.get("pid") > 0
        if transition == "stop":
            return prev_live and not cur_live and after == before
        return (
            transition == "restart"
            and prev_live and cur_live
            and after == before + 1
            and (
                current.get("pid") != previous.get("pid")
                or current.get("pm_uptime") != previous.get("pm_uptime")
            )
        )

    @staticmethod
    def _auth_matches(transition: str, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        before = (previous.get("pid"), previous.get("start_ticks"))
        after = (current.get("pid"), current.get("start_ticks"))
        prev_present = all(isinstance(v, int) and not isinstance(v, bool) for v in before)
        cur_present = all(isinstance(v, int) and not isinstance(v, bool) for v in after)
        if transition == "stop":
            return prev_present and current.get("pid") is None and current.get("start_ticks") is None
        return transition == "restart" and prev_present and cur_present and after != before


    def evaluate_unlocked(self, previous_identity: dict[str, Any], current_identity: dict[str, Any],
                          incident: dict[str, Any], observed_utc: datetime) -> dict[str, Any] | None:
        """Evaluate while the service checkpoint lock is already held.

        Invalid/insecure maintenance state has no suppression authority: it is
        treated as no matching marker so the normal incident path can report
        the unexpected transition. Administrative read/arm/confirm remain
        strict and still surface the invalid marker for recovery review.

        Returns status=pending for an exact transition that is armed but not
        yet confirmed, and status=expected only for a confirmed exact
        transition.
        """
        when = _utc(observed_utc)
        try:
            marker = self._read_unlocked()
        except Refused:
            return None
        if marker is None:
            return None
        if when > _parse_iso(marker["expires_utc"]):
            return None
        if marker["before_identity"] != previous_identity:
            return None

        exit_code = incident.get("exit_code")
        signal_name = incident.get("signal_name")
        classification = incident.get("classification")

        # Explicit fatal/non-zero evidence always wins over maintenance intent.
        if exit_code not in (None, 0):
            return None
        if classification in {"FATAL_SIGNAL_EXIT", "NONZERO_EXIT"}:
            return None

        # Only normal operator termination signals are eligible to accompany
        # an otherwise exact confirmed World maintenance transition.
        if signal_name is not None and signal_name not in CLEAN_MAINTENANCE_SIGNALS:
            return None
        if classification == "SIGNAL_EXIT_CAUSE_UNPROVEN" and signal_name not in CLEAN_MAINTENANCE_SIGNALS:
            return None

        if self.service == "Worldserver":
            structural = self._world_matches(marker["transition"], previous_identity, current_identity)
        else:
            structural = self._auth_matches(marker["transition"], previous_identity, current_identity)
        if not structural:
            return None

        return {
            "status": "expected" if marker["status"] == "confirmed" else "pending",
            "operation_id": marker["operation_id"],
            "transition": marker["transition"],
            "service": self.service,
            "observed_utc": _iso(when),
            "confirmed_utc": marker.get("confirmed_utc"),
            "signal_name": signal_name,
        }

    def finalize_expected_unlocked(self, decision: dict[str, Any]) -> None:
        """Persist one expected-maintenance audit record, then consume marker.

        Caller must already hold the service checkpoint lock and must call this
        only after the checkpoint has advanced to the expected post-state.
        """
        if decision.get("status") != "expected":
            raise Refused("only confirmed expected maintenance may be finalized")
        marker = self._read_unlocked()
        if marker is None or marker.get("operation_id") != decision.get("operation_id"):
            raise Refused("expected-maintenance marker changed before finalization")
        audit = {
            "version": 1,
            "service": self.service,
            "operation_id": marker["operation_id"],
            "transition": marker["transition"],
            "created_utc": marker["created_utc"],
            "confirmed_utc": marker.get("confirmed_utc"),
            "observed_utc": decision["observed_utc"],
            "result": "EXPECTED_TRANSITION_CONFIRMED",
        }
        checkpoint._atomic_json(self.root / f"{self.service}.last-expected-maintenance.json", audit)
        try:
            self.path.unlink()
        except OSError as exc:
            raise Refused("cannot consume expected-maintenance marker") from exc
        dfd = checkpoint.os.open(self.root, checkpoint.os.O_RDONLY | getattr(checkpoint.os, "O_DIRECTORY", 0))
        try:
            checkpoint.os.fsync(dfd)
        finally:
            checkpoint.os.close(dfd)


    def _read_audit_unlocked(self) -> dict[str, Any] | None:
        path = self.root / f"{self.service}.last-expected-maintenance.json"
        try:
            audit = checkpoint._read_json(path)
        except checkpoint.Refused as exc:
            raise Refused(str(exc)) from exc
        if audit is None:
            return None
        required = {
            "version", "service", "operation_id", "transition",
            "created_utc", "confirmed_utc", "observed_utc", "result",
        }
        if set(audit) != required:
            raise Refused("expected-maintenance audit fields are invalid")
        if audit["version"] != 1 or audit["service"] != self.service:
            raise Refused("expected-maintenance audit identity mismatch")
        if not isinstance(audit["operation_id"], str) or not OPERATION_RE.fullmatch(audit["operation_id"]):
            raise Refused("invalid expected-maintenance audit operation id")
        if audit["transition"] not in TRANSITIONS:
            raise Refused("invalid expected-maintenance audit transition")
        if audit["result"] != "EXPECTED_TRANSITION_CONFIRMED":
            raise Refused("invalid expected-maintenance audit result")
        created = _parse_iso(audit["created_utc"])
        confirmed = _parse_iso(audit["confirmed_utc"])
        observed = _parse_iso(audit["observed_utc"])
        if confirmed < created or observed < confirmed:
            raise Refused("invalid expected-maintenance audit timestamps")
        return audit

    def classify_recovery(self) -> dict[str, Any]:
        """Classify durable marker/audit/checkpoint state without mutating it."""
        with checkpoint._exclusive_lock(self.lock_path):
            try:
                marker = self._read_unlocked()
            except Refused as exc:
                return {
                    "status": "MARKER_INVALID_OR_UNSAFE",
                    "service": self.service,
                    "reason": str(exc),
                }

            try:
                state = checkpoint._read_json(self.root / f"{self.service}.checkpoint.json")
            except checkpoint.Refused as exc:
                return {
                    "status": "CHECKPOINT_INVALID_OR_UNSAFE",
                    "service": self.service,
                    "reason": str(exc),
                }
            if state is None or state.get("service") != self.service or not isinstance(state.get("identity"), dict):
                return {"status": "CHECKPOINT_INVALID_OR_MISSING", "service": self.service}

            try:
                audit = self._read_audit_unlocked()
            except Refused as exc:
                return {
                    "status": "AUDIT_INVALID_OR_UNSAFE",
                    "service": self.service,
                    "reason": str(exc),
                }

            if marker is None and audit is None:
                return {"status": "CLEAN", "service": self.service}

            if marker is None and audit is not None:
                return {
                    "status": "AUDIT_ONLY_CLEAN",
                    "service": self.service,
                    "operation_id": audit["operation_id"],
                }

            marker_id = marker["operation_id"]
            checkpoint_advanced = marker.get("before_identity") != state.get("identity")

            if audit is None:
                return {
                    "status": "STALE_CONFIRMED_MARKER_AFTER_CHECKPOINT" if (
                        checkpoint_advanced and marker.get("status") == "confirmed"
                    ) else "ACTIVE_OR_EXPIRED_MARKER_NO_AUDIT",
                    "service": self.service,
                    "operation_id": marker_id,
                    "checkpoint_advanced": checkpoint_advanced,
                    "marker_status": marker["status"],
                }

            if audit.get("operation_id") != marker_id:
                return {
                    "status": "MARKER_AUDIT_MISMATCH",
                    "service": self.service,
                    "operation_id": marker_id,
                    "checkpoint_advanced": checkpoint_advanced,
                }

            return {
                "status": "STALE_MARKER_WITH_MATCHING_AUDIT" if checkpoint_advanced else "ACTIVE_MARKER_WITH_MATCHING_AUDIT",
                "service": self.service,
                "operation_id": marker_id,
                "checkpoint_advanced": checkpoint_advanced,
                "marker_status": marker["status"],
            }

    def matches_expected(self, previous_identity: dict[str, Any], current_identity: dict[str, Any],
                         incident: dict[str, Any], observed_utc: datetime) -> bool:
        """Compatibility/test helper: confirmed exact expected transition only."""
        with checkpoint._exclusive_lock(self.lock_path):
            decision = self.evaluate_unlocked(
                previous_identity, current_identity, incident, observed_utc
            )
            return bool(decision and decision.get("status") == "expected")
