#!/usr/bin/env python3
"""Read-only NT1 installed-source compatibility preflight (NOT a C++ build).

Uses only local file reads and Git metadata inspection. Prints to stdout; it
does not write reports, run builds, change source, query databases, or contact
GitHub. A passing source preflight is NOT permission to deploy or Apply.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CORE_FILES = {
    "Player.h": "src/server/game/Entities/Player/Player.h",
    "Player.cpp": "src/server/game/Entities/Player/Player.cpp",
    "Unit.h": "src/server/game/Entities/Unit/Unit.h",
    "Item.h": "src/server/game/Entities/Item/Item.h",
    "Chat.h": "src/server/game/Chat/Chat.h",
}
# Exact API/protected-state evidence. Text checks are ONLY smoke tests and
# cannot resolve overloads, types across headers, or local patches.
CORE_CHECKS = (
    ("Player.h", r"\bHasTalent\s*\(\s*uint32\s+\w+\s*,\s*uint8\s+\w+\s*\)\s*const", "per-spec HasTalent"),
    ("Player.h", r"\bGetTalentMap\s*\(\s*\)\s*const", "const talent map"),
    ("Player.h", r"\bGetSpellMap\s*\(\s*\)\s*const", "const spell map"),
    ("Player.h", r"\bGetActiveSpec\s*\(\s*\)\s*const", "active spec getter"),
    ("Player.h", r"\bGetSpecsCount\s*\(\s*\)\s*const", "spec count getter"),
    ("Player.h", r"\bGetGlyph\s*\(\s*uint8\s+\w+\s*\)\s*const", "active-spec glyph getter"),
    ("Player.h", r"\bGetQuestStatus\s*\(\s*uint32\s+\w+\s*\)\s*const", "quest status getter"),
    ("Player.h", r"\bGetItemByPos\s*\(\s*uint8\s+\w+\s*,\s*uint8\s+\w+\s*\)\s*const", "equipment slot getter"),
    ("Player.h", r"\bCanTitanGrip\s*\(\s*\)\s*const", "Titan's Grip getter"),
    ("Player.h", r"\bstruct\s+PlayerTalent\s*\{", "PlayerTalent record"),
    ("Player.h", r"\buint8\s+specMask\s*:", "spec-mask field"),
    ("Player.h", r"\buint32\s+talentID\s*;", "talent ID field"),
    ("Player.cpp", r"\bbool\s+Player::HasTalent\s*\(", "HasTalent implementation"),
    ("Player.cpp", r"\bPlayer::resetTalents\s*\(", "talent reset implementation"),
    ("Player.cpp", r"\bPlayer::AutoUnequipOffhandIfNeed\s*\(", "offhand relocation implementation"),
    ("Player.cpp", r"\bPlayer::ActivateSpec\s*\(", "spec activation implementation"),
    ("Unit.h", r"\bCanDualWield\s*\(\s*\)\s*const", "dual wield getter"),
    ("Item.h", r"\bGetTemplate\s*\(\s*\)\s*const", "item template getter"),
    ("Chat.h", r"\bPSendSysMessage\s*\(\s*char\s+const\s*\*\s*fmt", "formatted chat output"),
)

SKIP_DIRS = {".git", "build", "node_modules", "vendor", "deps", "sql",
             "docs", "tests", "__pycache__", "CMakeFiles"}
PLAYERBOT_HEADERS = {
    "PlayerbotAI.h": ("GetMaster",),
    "PlayerbotMgr.h": ("GetPlayerbotAI",),
    "RandomPlayerbotMgr.h": ("IsRandomBot",),
}

def result(severity, scope, detail):
    return {"status": severity, "scope": scope, "detail": detail}


def read_text(path, max_bytes=10_000_000):
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def inspect_git(directory, label, runner=subprocess.run):
    """Read Git only. Disallow optional index locks and network prompts."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    def invoke(*args):
        try:
            completed = runner(
                ["git", "--no-optional-locks", "-C", str(directory)] + list(args),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=15, env=env, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout.strip() if completed.returncode == 0 else None

    head = invoke("rev-parse", "HEAD")
    toplevel = invoke("rev-parse", "--show-toplevel")
    status = invoke("status", "--porcelain", "--untracked-files=normal")
    if not head or not re.fullmatch(r"[0-9a-f]{40,64}", head) or not toplevel or status is None:
        return {"label": label, "head": None, "toplevel": toplevel, "dirty": None}
    return {"label": label, "head": head, "toplevel": str(Path(toplevel).resolve()),
            "dirty": bool(status)}


def find_named_headers(root, desired, max_dirs=6000):
    """Bounded, deterministic local-only discovery; never follow symlinks."""
    found = {}
    count = 0
    for folder, dirs, files in os.walk(str(root), followlinks=False):
        count += 1
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and
                         not d.startswith("."))
        for filename in sorted(files):
            if filename in desired and filename not in found:
                found[filename] = Path(folder) / filename
        if len(found) == len(desired) or count >= max_dirs:
            break
    return found


def check_core(core):
    results = []
    sources = {label: read_text(core / rel) for label, rel in CORE_FILES.items()}
    for label, expression, description in CORE_CHECKS:
        source = sources[label]
        if source is None:
            results.append(result("MISSING", "core", label + " is absent/unreadable"))
        elif not re.search(expression, source):
            results.append(result("MISSING", "core", description + " signature not found in " + label))
        else:
            results.append(result("FOUND", "core", description))
    # These are critical risk conditions in the *source*, not proof their
    # behavior survives every module hook or runtime talent modification.
    player = sources["Player.cpp"] or ""
    for expression, description in (
        (r"\bAutoUnequipOffhandIfNeed\s*\(\s*\)\s*;", "reset invokes offhand recheck"),
        (r"\bRemovePet\s*\(", "pet state may be affected"),
        (r"\bSetCanTitanGrip\s*\(\s*false\s*\)", "Titan's Grip may be cleared"),
        (r"\bSetCanDualWield\s*\(\s*false\s*\)", "Dual Wield may be cleared"),
    ):
        results.append(result("REVIEW" if re.search(expression, player) else "MISSING",
                              "reset-risk", description +
                              ("; KEEP ALT BOT APPLY BLOCKED" if re.search(expression, player)
                               else "; behavior differs or could not be found")))
    return results


def check_playerbots(root):
    findings = []
    headers = find_named_headers(root, set(PLAYERBOT_HEADERS))
    for name, methods in PLAYERBOT_HEADERS.items():
        source = read_text(headers[name]) if name in headers else None
        if source is None:
            findings.append(result("MISSING", "playerbots", name + " not found/readable"))
            continue
        for method in methods:
            findings.append(result(
                "FOUND" if re.search(r"\b" + re.escape(method) + r"\s*\(", source)
                else "MISSING", "playerbots", name + ": " + method))
    return findings


def check_ip(root):
    # Locate the modern IP API as a manual-review clue only; there is no
    # guaranteed stable header/schema for every installed version.
    headers = find_named_headers(root, {"IndividualProgression.h"})
    head = headers.get("IndividualProgression.h")
    src = read_text(head) if head else None
    if src is None:
        return [result("REVIEW", "individual-progression",
                       "IndividualProgression.h not found; verify IP stage schema manually")]
    return [result("REVIEW", "individual-progression",
                   "IndividualProgression.h found; manually compare rewarded hidden quests "
                   "66001..66018, stage 8/13 thresholds and ProgressionLimit")]


def check_module(root):
    path = root / "src" / "Systems" / "BotTalentImport.cpp"
    src = read_text(path)
    if src is None:
        return [result("REVIEW", "naxxramas",
                       "BotTalentImport.cpp missing; live module may predate PR #16")]
    findings = []
    for marker in (
        "HandleSafetyPreview(", "PrintAltBotTalentMapIntegrity(",
        "Alt Bot NT1 Apply blocked: an offhand item is",
        "Alt Bot NT1 Apply blocked: the bot has an active",
        "IsReadOnlyAccessMode()",
    ):
        findings.append(result("FOUND" if marker in src else "REVIEW",
                               "naxxramas", "module source contains " + marker))
    return findings


def audit(paths):
    findings = []
    repo_details = []
    for label, directory in paths.items():
        if not directory.is_dir():
            findings.append(result("MISSING", label, "supplied directory not found"))
            continue
        info = inspect_git(directory, label)
        repo_details.append(info)
        if not info["head"]:
            findings.append(result("MISSING", label, "Git HEAD/top-level/status unavailable"))
        elif info["dirty"]:
            findings.append(result("REVIEW", label,
                                   "tracked/untracked working tree changes; HEAD alone is not complete"))
        else:
            findings.append(result("FOUND", label, "Git revision captured"))
    if paths["core"].is_dir():
        findings.extend(check_core(paths["core"]))
    if paths["playerbots"].is_dir():
        findings.extend(check_playerbots(paths["playerbots"]))
    if paths["ip"].is_dir():
        findings.extend(check_ip(paths["ip"]))
    if paths["module"].is_dir():
        findings.extend(check_module(paths["module"]))
    owner = next((r for r in repo_details if r["label"] == "core"), None)
    for record in repo_details:
        if owner and record["label"] != "core" and record["toplevel"] == owner["toplevel"]:
            findings.append(result("REVIEW", record["label"],
                                   "shares parent Git repository: not an independent module SHA"))
    findings.append(result("REVIEW", "runtime",
                           "installed binary provenance, local patches, hook semantics, "
                           "DBC versions and real C++ compilation NOT verified"))
    findings.append(result("REVIEW", "safety",
                           "no result permits talent Apply, spec switching, gear movement "
                           "or skipping full offline characters-DB recovery testing"))
    return {"repositories": repo_details, "findings": findings,
            "failed": any(x["status"] == "MISSING" for x in findings)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for label in ("core", "playerbots", "ip", "module"):
        parser.add_argument("--" + label, required=True, type=Path,
                            help="EXISTING local source directory (read-only)")
    parser.add_argument("--json", action="store_true", help="print report as JSON to stdout")
    args = parser.parse_args(argv)
    paths = {label: getattr(args, label).expanduser().resolve()
             for label in ("core", "playerbots", "ip", "module")}
    report = audit(paths)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("NT1 source preflight ONLY; no compile, changes, or server access")
        for r in report["repositories"]:
            print("GIT {}: {} (top-level {}; working tree changes: {})".format(
                r["label"], r["head"] or "UNKNOWN",
                r["toplevel"] or "UNKNOWN", r["dirty"]))
        for finding in report["findings"]:
            print("[{}] {}: {}".format(
                finding["status"], finding["scope"], finding["detail"]))
        print("Outcome: {}. Never treats this as Apply/merge/build approval.".format(
            "SOURCE GAPS FOUND" if report["failed"] else "SOURCE SMOKE TEST ONLY"))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
