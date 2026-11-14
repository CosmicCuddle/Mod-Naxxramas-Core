#!/usr/bin/env python3
"""Read-only F15 retention interruption classifier.

Classifies unfinished snapshot, crash-report and raw-evidence retention intents.
It never deletes, renames, repairs or clears an intent. Legacy intents that lack
persisted target identity are explicitly reported as identity-unproven.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

import f15_raw_evidence_bundle as raw_bundle


MAX_INTENT_BYTES = 1024 * 1024
CRASH_REPORT_RE = re.compile(
    r"^\d{8}T\d{6}Z-(?:Worldserver|Authserver)-"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\.txt$"
)


class Refused(RuntimeError):
    pass


def _root(path: Path, label: str) -> Path | None:
    path = Path(path)
    if path.is_symlink():
        raise Refused(f"{label} may not be a symlink")
    if not path.exists():
        return None
    if not path.is_dir():
        raise Refused(f"{label} must be a real directory")
    st = path.lstat()
    if st.st_mode & 0o077:
        raise Refused(f"{label} must be private")
    return path


def _read_intent(path: Path) -> dict[str, Any] | None:
    if path.is_symlink():
        return {"_classifier": "UNSAFE_INTENT", "_reason": "intent is symlink"}
    if not path.exists():
        return None
    st = path.lstat()
    if (
        not stat.S_ISREG(st.st_mode)
        or st.st_nlink != 1
        or st.st_mode & 0o077
        or st.st_size > MAX_INTENT_BYTES
    ):
        return {"_classifier": "UNSAFE_INTENT", "_reason": "intent is not one bounded private regular file"}
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return {"_classifier": "UNSAFE_INTENT", "_reason": "intent cannot be opened safely"}
    try:
        opened = os.fstat(fd)
        if opened.st_dev != st.st_dev or opened.st_ino != st.st_ino or opened.st_size != st.st_size:
            return {"_classifier": "UNSAFE_INTENT", "_reason": "intent changed while opening"}
        data = bytearray()
        offset = 0
        while offset < st.st_size:
            block = os.pread(fd, min(65536, st.st_size - offset), offset)
            if not block:
                return {"_classifier": "UNSAFE_INTENT", "_reason": "intent shortened during read"}
            data.extend(block)
            offset += len(block)
    finally:
        os.close(fd)
    try:
        value = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"_classifier": "MALFORMED_INTENT", "_reason": "intent is not valid UTF-8 JSON"}
    if not isinstance(value, dict):
        return {"_classifier": "MALFORMED_INTENT", "_reason": "intent root is not an object"}
    return value


def _safe_name(name: Any) -> bool:
    return (
        isinstance(name, str)
        and bool(name)
        and "/" not in name
        and "\\" not in name
        and name not in {".", ".."}
    )


def _valid_identity(value: Any) -> bool:
    required = {"dev", "ino", "size", "mtime_ns", "sha256"}
    if not isinstance(value, dict) or set(value) != required:
        return False
    for key in ("dev", "ino", "size", "mtime_ns"):
        if type(value.get(key)) is not int or value[key] < 0:
            return False
    digest = value.get("sha256")
    return isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)


def _hash_open_file(fd: int, size: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        block = os.pread(fd, min(1024 * 1024, size - offset), offset)
        if not block:
            raise Refused("target shortened during recovery hash")
        digest.update(block)
        offset += len(block)
    return digest.hexdigest()


def _file_state(root: Path, name: Any, expected: Any) -> dict[str, Any]:
    if not _safe_name(name) or not _valid_identity(expected):
        return {"state": "MALFORMED_EXPECTATION"}
    path = root / name
    if path.is_symlink():
        return {"state": "UNSAFE_OR_REPLACED", "reason": "symlink"}
    if not path.exists():
        return {"state": "MISSING"}
    try:
        lst = path.lstat()
    except OSError:
        return {"state": "UNSAFE_OR_REPLACED", "reason": "lstat failed"}
    if not stat.S_ISREG(lst.st_mode) or lst.st_nlink != 1 or lst.st_mode & 0o077:
        return {"state": "UNSAFE_OR_REPLACED", "reason": "not private regular single-link"}
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return {"state": "UNSAFE_OR_REPLACED", "reason": "safe open failed"}
    try:
        st = os.fstat(fd)
        try:
            digest = _hash_open_file(fd, st.st_size)
        except Refused as exc:
            return {"state": "UNSAFE_OR_REPLACED", "reason": str(exc)}
        after = os.fstat(fd)
    finally:
        os.close(fd)
    current = {
        "dev": st.st_dev,
        "ino": st.st_ino,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": digest,
    }
    if (
        after.st_dev != st.st_dev or after.st_ino != st.st_ino
        or after.st_size != st.st_size or after.st_mtime_ns != st.st_mtime_ns
        or after.st_nlink != st.st_nlink or after.st_mode != st.st_mode
    ):
        return {"state": "UNSAFE_OR_REPLACED", "reason": "changed during classification"}
    if current == expected:
        return {"state": "MATCH"}
    return {"state": "UNSAFE_OR_REPLACED", "reason": "identity/hash differs", "current": current}


def _summary(states: list[str]) -> str:
    if states and all(x == "MATCH" for x in states):
        return "PRE_DELETE_TARGETS_INTACT"
    if states and all(x == "MISSING" for x in states):
        return "TARGETS_ALREADY_ABSENT"
    if any(x in {"UNSAFE_OR_REPLACED", "MALFORMED_EXPECTATION"} for x in states):
        return "IDENTITY_MISMATCH_OR_FOREIGN"
    if any(x == "MISSING" for x in states) and any(x == "MATCH" for x in states):
        return "PARTIAL_DELETE"
    return "UNRESOLVED"


def classify_snapshot_root(snapshot_root: Path) -> dict[str, Any]:
    root = _root(snapshot_root, "snapshot root")
    if root is None:
        return {"intent": "ABSENT", "classification": "ROOT_ABSENT"}
    path = root / "retention-intent.json"
    intent = _read_intent(path)
    if intent is None:
        return {"intent": "ABSENT", "classification": "NO_UNFINISHED_INTENT"}
    if "_classifier" in intent:
        return {"intent": "PRESENT", "classification": intent["_classifier"], "reason": intent.get("_reason")}
    if intent.get("kind") != "f15_retention_30d_snapshot":
        return {"intent": "PRESENT", "classification": "FOREIGN_OR_UNKNOWN_INTENT"}
    if intent.get("version") != 2:
        return {"intent": "PRESENT", "classification": "LEGACY_IDENTITY_UNPROVEN"}
    snapshot_name = intent.get("snapshot")
    manifest_name = intent.get("manifest")
    if (
        not _safe_name(snapshot_name) or not snapshot_name.endswith(".log")
        or not _safe_name(manifest_name) or not manifest_name.endswith(".json")
        or manifest_name == "retention-intent.json"
    ):
        return {"intent": "PRESENT", "classification": "MALFORMED_INTENT"}
    snapshot = _file_state(root, snapshot_name, intent.get("snapshot_identity"))
    manifest = _file_state(root, manifest_name, intent.get("manifest_identity"))
    result = _summary([snapshot["state"], manifest["state"]])
    return {
        "intent": "PRESENT",
        "classification": result,
        "targets": {"snapshot": snapshot, "manifest": manifest},
        "recommended_action": "operator review only; do not automatically delete evidence or intent",
    }


def classify_crash_root(crash_root: Path) -> dict[str, Any]:
    root = _root(crash_root, "crash root")
    if root is None:
        return {"intent": "ABSENT", "classification": "ROOT_ABSENT"}
    path = root / "retention-intent.json"
    intent = _read_intent(path)
    if intent is None:
        return {"intent": "ABSENT", "classification": "NO_UNFINISHED_INTENT"}
    if "_classifier" in intent:
        return {"intent": "PRESENT", "classification": intent["_classifier"], "reason": intent.get("_reason")}
    if intent.get("kind") != "f15_retention_30d_crash_report":
        return {"intent": "PRESENT", "classification": "FOREIGN_OR_UNKNOWN_INTENT"}
    if intent.get("version") != 2:
        return {"intent": "PRESENT", "classification": "LEGACY_IDENTITY_UNPROVEN"}
    report_name = intent.get("report")
    if not _safe_name(report_name) or not CRASH_REPORT_RE.fullmatch(report_name):
        return {"intent": "PRESENT", "classification": "MALFORMED_INTENT"}
    report = _file_state(root, report_name, intent.get("report_identity"))
    state = report["state"]
    if state == "MATCH":
        result = "PRE_DELETE_TARGET_INTACT"
    elif state == "MISSING":
        result = "REPORT_ALREADY_ABSENT_AFTER_INTENT"
    elif state in {"UNSAFE_OR_REPLACED", "MALFORMED_EXPECTATION"}:
        result = "IDENTITY_MISMATCH_OR_FOREIGN"
    else:
        result = "UNRESOLVED"
    return {
        "intent": "PRESENT",
        "classification": result,
        "target": report,
        "recommended_action": "operator review only; do not automatically delete evidence or intent",
    }


def _valid_bundle_identity(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"dev", "ino"}
        and type(value.get("dev")) is int
        and type(value.get("ino")) is int
        and value["dev"] >= 0
        and value["ino"] > 0
    )


def classify_raw_root(raw_root: Path) -> dict[str, Any]:
    root = _root(raw_root, "raw evidence root")
    if root is None:
        return {"intent": "ABSENT", "classification": "ROOT_ABSENT", "partial_bundles": []}
    path = root / "retention-intent.json"
    intent = _read_intent(path)
    partial_without_intent = []

    for candidate in sorted(root.iterdir(), key=lambda p: p.name):
        if candidate.name == "retention-intent.json" or candidate.name.startswith(".retention-intent.json.pending."):
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        try:
            raw_bundle._verify_bundle(candidate)
            state = "COMPLETE_VERIFIED_BUNDLE"
        except Exception as exc:
            state = "PARTIAL_OR_UNVERIFIED_BUNDLE"
            partial_without_intent.append({"bundle": candidate.name, "state": state, "reason": type(exc).__name__})

    if intent is None:
        return {
            "intent": "ABSENT",
            "classification": (
                "PARTIAL_BUNDLE_WITHOUT_RETENTION_INTENT"
                if partial_without_intent else "NO_UNFINISHED_INTENT"
            ),
            "partial_bundles": partial_without_intent,
        }
    if "_classifier" in intent:
        return {
            "intent": "PRESENT", "classification": intent["_classifier"],
            "reason": intent.get("_reason"), "partial_bundles": partial_without_intent,
        }
    if intent.get("kind") != "f15_retention_30d_raw_evidence":
        return {
            "intent": "PRESENT", "classification": "FOREIGN_OR_UNKNOWN_INTENT",
            "partial_bundles": partial_without_intent,
        }
    if intent.get("version") != 2:
        return {
            "intent": "PRESENT", "classification": "LEGACY_IDENTITY_UNPROVEN",
            "partial_bundles": partial_without_intent,
        }

    bundle_name = intent.get("bundle")
    expected_bundle = intent.get("bundle_identity")
    targets = intent.get("targets")
    incident_id = intent.get("incident_id")
    if (
        not _safe_name(bundle_name)
        or not isinstance(incident_id, str)
        or not raw_bundle.INCIDENT_RE.fullmatch(incident_id)
        or not bundle_name.endswith("-" + incident_id)
        or not _valid_bundle_identity(expected_bundle)
        or not isinstance(targets, list)
        or not targets
    ):
        return {"intent": "PRESENT", "classification": "MALFORMED_INTENT"}

    bundle = root / bundle_name
    if bundle.is_symlink():
        return {"intent": "PRESENT", "classification": "IDENTITY_MISMATCH_OR_FOREIGN", "bundle_state": "SYMLINK"}
    if not bundle.exists():
        return {"intent": "PRESENT", "classification": "BUNDLE_ALREADY_ABSENT_AFTER_INTENT"}
    bst = bundle.lstat()
    if (
        not stat.S_ISDIR(bst.st_mode) or bst.st_mode & 0o077
        or bst.st_dev != expected_bundle["dev"] or bst.st_ino != expected_bundle["ino"]
    ):
        return {"intent": "PRESENT", "classification": "IDENTITY_MISMATCH_OR_FOREIGN", "bundle_state": "REPLACED"}

    target_states = {}
    seen = set()
    for record in targets:
        if not isinstance(record, dict) or set(record) != {"name", "identity"}:
            return {"intent": "PRESENT", "classification": "MALFORMED_INTENT"}
        name = record["name"]
        if (
            not _safe_name(name) or name in seen
            or (name != "manifest.json" and not raw_bundle.ARTIFACT_RE.fullmatch(name))
        ):
            return {"intent": "PRESENT", "classification": "MALFORMED_INTENT"}
        seen.add(name)
        target_states[name] = _file_state(bundle, name, record["identity"])
    if "manifest.json" not in seen:
        return {"intent": "PRESENT", "classification": "MALFORMED_INTENT"}
    result = _summary([x["state"] for x in target_states.values()])
    if result == "TARGETS_ALREADY_ABSENT":
        result = "TARGET_FILES_ABSENT_BUNDLE_DIRECTORY_REMAINS"
    return {
        "intent": "PRESENT",
        "classification": result,
        "bundle_state": "MATCH",
        "targets": target_states,
        "partial_bundles": partial_without_intent,
        "recommended_action": "operator review only; do not automatically delete evidence or intent",
    }


def classify_all(archive_root: Path, crash_root: Path) -> dict[str, Any]:
    crash_root = Path(crash_root)
    raw_root = crash_root / "Raw Evidence"
    return {
        "snapshot_archive": classify_snapshot_root(archive_root),
        "crash_reports": classify_crash_root(crash_root),
        "raw_evidence": classify_raw_root(raw_root),
        "mutations_performed": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Read-only F15 retention interruption classifier")
    p.add_argument("--archive-root", type=Path, required=True)
    p.add_argument("--crash-root", type=Path, required=True)
    args = p.parse_args(argv)
    result = classify_all(args.archive_root, args.crash_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
