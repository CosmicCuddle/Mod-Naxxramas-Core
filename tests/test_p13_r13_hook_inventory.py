#!/usr/bin/env python3
"""P13-R13 tracked-source hook inventory. Source only, never host installation proof.

CI invocation:
  python3 -I tests/test_p13_r13_hook_inventory.py . pinned-core pinned-playerbots

Every scan uses immutable *commit objects* and git grep (NOT GitHub code indexing).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

MOD_SHA = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
BOTS_SHA = "d750b4b3a50effdf22bedc8032f0e8e5f7cb8091"
SOURCE_SUFFIXES = (".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx")
NEEDLES = ("OnPlayerMoneyChanged", "PLAYERHOOK_ON_MONEY_CHANGED")

# Pinned core framework references are NOT automatically enabled subscriptions.
FRAMEWORK_PATHS = {
    "src/server/game/Entities/Player/Player.cpp",
    "src/server/game/Scripting/ScriptMgr.h",
    "src/server/game/Scripting/ScriptDefines/PlayerScript.h",
    "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp",
}

def git(root: pathlib.Path, *args: str, allow_no_match: bool = False) -> str:
    result = subprocess.run(["git", "-C", str(root), *args],
                            capture_output=True, text=True, check=False)
    accepted = (0, 1) if allow_no_match else (0,)
    if result.returncode not in accepted:
        raise RuntimeError(f"git command failed: {args!r}, {result.stderr[:300]}")
    return result.stdout.strip()

def tracked_files(root: pathlib.Path, sha: str, paths: tuple[str, ...]) -> list[str]:
    rows = git(root, "ls-tree", "-r", "--name-only", sha, "--", *paths).splitlines()
    return sorted(path for path in rows if path.endswith(SOURCE_SUFFIXES))

def grep_lines(root: pathlib.Path, sha: str, paths: tuple[str, ...], needle: str) -> list[tuple[str, int, str]]:
    output = git(root, "grep", "-I", "-n", "-F", needle, sha, "--", *paths,
                 allow_no_match=True)
    found = []
    if not output:
        return found
    for line in output.splitlines():
        parts = line.split(":", 3)  # COMMIT:path:line:source content
        assert len(parts) == 4 and parts[0] == sha, f"bad immutable grep record: {line!r}"
        path, number, text = parts[1], parts[2], parts[3]
        assert number.isdecimal(), f"non-numeric line in grep: {line!r}"
        if path.endswith(SOURCE_SUFFIXES):
            found.append((path, int(number), text.strip()))
    return sorted(found)

def classify(origin: str, path: str) -> str:
    if origin == "pinned-core" and path in FRAMEWORK_PATHS:
        return "core-api-or-dispatch"
    return "nonframework-source-candidate"

def synthetic_scan_guards() -> None:
    fake = [
        ("pinned-core", "src/server/game/Scripting/ScriptDefines/PlayerScript.h",
         "virtual void OnPlayerMoneyChanged(Player*, int32& amount);", "core-api-or-dispatch"),
        ("pinned-core", "src/server/scripts/Custom/SyntheticOnly.cpp",
         "void OnPlayerMoneyChanged(Player*, int32& amount) override { amount /= 2; }",
         "nonframework-source-candidate"),
        ("pinned-playerbots", "src/SyntheticOnly.cpp",
         "PLAYERHOOK_ON_MONEY_CHANGED", "nonframework-source-candidate"),
        ("protected-mod-main", "src/SyntheticOnly.cpp",
         "void OnPlayerMoneyChanged(Player*, int32& amount) override;", "nonframework-source-candidate"),
    ]
    for origin, path, text, expected in fake:
        assert any(k in text for k in NEEDLES)
        assert classify(origin, path) == expected
    assert classify("pinned-core", "src/server/scripts/Custom/OnPlayerMoneyChanged.cpp") != "core-api-or-dispatch"
    print("PASS: 4 synthetic source/registration scanner guards (NOT real subscriptions)")

def verify_known_framework(core: pathlib.Path) -> None:
    original = {
        "src/server/game/Entities/Player/Player.cpp":
            ("138e7eab4905ec366338a54cc18e6cfe749a3670",
             "sScriptMgr->OnPlayerMoneyChanged(this, amount);"),
        "src/server/game/Scripting/ScriptDefines/PlayerScript.h":
            ("0d2314edf7715f383bbab996c6c5fc010b282308",
             "virtual void OnPlayerMoneyChanged(Player* /*player*/, int32& /*amount*/)"),
        "src/server/game/Scripting/ScriptDefines/PlayerScript.cpp":
            ("4ac4571a3d7d8c0f3f27e8477ff5d7f0734e6e05",
             "script->OnPlayerMoneyChanged(player, amount)"),
        "src/server/game/Scripting/ScriptMgr.h":
            ("7f0f30d3ca46cb290636c33ca8e1b2b9c0ffa1f8",
             "void OnPlayerMoneyChanged(Player* player, int32& amount);"),
    }
    for path, (blob, excerpt) in original.items():
        assert git(core, "rev-parse", f"{CORE_SHA}:{path}") == blob, path
        contents = git(core, "show", f"{CORE_SHA}:{path}")
        assert excerpt in contents, path
    print("PASS: 4 real pinned framework blobs and authoritative hook anchors")

def scan(origin: str, root: pathlib.Path, sha: str, paths: tuple[str, ...]) -> dict:
    assert git(root, "rev-parse", "HEAD") == sha or origin == "protected-mod-main"
    source_files = tracked_files(root, sha, paths)
    assert source_files, f"NO source files found under {origin}:{paths}"
    file_set = set(source_files)
    by_site: dict[tuple[str, int], set[str]] = {}
    snippets: dict[tuple[str, int], str] = {}
    for needle in NEEDLES:
        for path, line, text in grep_lines(root, sha, paths, needle):
            assert path in file_set, f"out-of-inventory result {origin}:{path}"
            by_site.setdefault((path, line), set()).add(needle)
            snippets[(path, line)] = text

    candidates = []
    api = []
    for (path, line), terms in sorted(by_site.items()):
        kind = classify(origin, path)
        item = (path, line, snippets[(path, line)], tuple(sorted(terms)))
        (api if kind == "core-api-or-dispatch" else candidates).append(item)
        print(f"HOOK-SITE {origin} [{kind}] {path}:{line} terms={','.join(sorted(terms))}: {snippets[(path, line)][:180]}")

    print(f"SCAN-SUMMARY {origin} commit={sha} paths={','.join(paths)} "
          f"source_files={len(source_files)} matching_lines={len(by_site)} "
          f"framework_lines={len(api)} nonframework_candidate_lines={len(candidates)} "
          f"candidate_files={len({x[0] for x in candidates})}")
    assert len(by_site) <= 200, "Large match inventory; preserve complete evidence, do not truncate"
    if candidates:
        print(f"LIMIT {origin}: nonframework source references are CANDIDATES, NOT confirmed live registrations")
    else:
        print(f"LIMIT {origin}: no nonframework hook-name references in selected tracked-source paths; "
              "NOT absence on owner's installed host")
    return {"sources": len(source_files), "sites": len(by_site),
            "framework": len(api), "candidates": len(candidates)}

def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    mod, core, bots = map(pathlib.Path, argv[1:])
    assert git(mod, "rev-parse", f"{MOD_SHA}:src/Systems/HonorOverflow.cpp") == (
        "d4f70c511ac5a3e32c7e6b8f913d095915da707c"
    )
    git(mod, "merge-base", "--is-ancestor", MOD_SHA, "HEAD")
    assert git(core, "rev-parse", "HEAD") == CORE_SHA
    assert git(bots, "rev-parse", "HEAD") == BOTS_SHA
    synthetic_scan_guards()
    verify_known_framework(core)
    results = {
        "pinned-core": scan("pinned-core", core, CORE_SHA, ("src", "modules")),
        "protected-mod-main": scan("protected-mod-main", mod, MOD_SHA, ("src",)),
        "pinned-playerbots": scan("pinned-playerbots", bots, BOTS_SHA, ("src",)),
    }
    assert results["pinned-core"]["framework"] >= 4, (
        "missing pinned core known framework hooks"
    )
    print("PASS: R13 complete bounded tracked-source git-grep inventory for three pinned trees")
    print("LIMIT: SOURCE coverage excludes external installed scripts, overlays, real config, "
          "submodules not present in pinned git trees, and actual runtime hook registration")
    print("LIMIT: NO production modification, server startup, client/gameplay/DB/SQL/DBC activity")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError, RuntimeError, subprocess.CalledProcessError) as error:
        print("FAIL: " + str(error))
        sys.exit(1)
